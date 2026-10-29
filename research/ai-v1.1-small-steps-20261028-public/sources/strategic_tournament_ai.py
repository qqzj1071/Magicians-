"""Explainable bounded self-play updates under immutable construction v1.0."""
import copy
import math
import random
from collections import Counter
from dataclasses import replace
import tournament_draft as A
import joint_draft_combat as J
T=A.T;S=T.S
BASE_VECTOR=A.vector
EXTRA=dict(reserve_plan=.55,mana_fit=.8,instant=.65)


def vector(p,ns,did=None):
    v=BASE_VECTOR(p,ns,did)
    costs=[S.C.CARDS[n].cost for n in ns]
    mean=sum(costs)/max(1,len(costs))
    # A curve preference is a feature, not proof of effective turn throughput.
    v['mana_fit']=-max(0,mean-2.5)/3
    v['instant']=sum(S.C.CARDS[n].attack+1.5*S.C.CARDS[n].defense for n in ns)/max(1,len(ns))/100
    return v


def reserve_plan(p,points):
    saved=min(2,max(0,points));next_income=2 if p.current_round<2 else 3 if p.current_round<5 else 4
    # Only published future income/odds; no future template or hidden inventory.
    threshold=3 if p.current_round<5 else 4
    unlock=float(next_income<threshold<=next_income+saved)
    safety=max(0,min(1,(p.tournament_hp-p.loss_estimate)/max(1,3*p.loss_estimate)))
    return safety*(.15*saved+.35*unlock)


def stage(r):return '1-4' if r<=4 else '5-8' if r<=8 else '9-12' if r<=12 else '13-14' if r<=14 else '15-16' if r<=16 else '17+'


class Combat(J.CombatLearner):
    def __init__(self,saved):
        super().__init__()
        self.stage=copy.deepcopy(saved['stage']);self.route=copy.deepcopy(saved['route'])
        self.updates=saved['updates'];self.accepts=saved['accepts'];self.experience.update(saved['experience'])
        self.context=copy.deepcopy(saved.get('context',{k:{} for k in ['1-4','5-8','9-12','13-14','15-16','17+']}))
        self.matchup=copy.deepcopy(saved.get('matchup',{}));self.support=Counter(saved.get('support',{}))
        self.log=[];self.games=0

    def policy(self,own,other,r,mode='adaptive'):
        p=super().policy(own,other,r,mode)
        if mode!='adaptive':return p
        did=J.route_id(own);op=J.route_id(other);key=(did or 'generic')+'|'+(op or 'unknown')
        delta=Counter(self.context[stage(r)])
        # Small route/opponent residual, shrunken until multiple examples exist.
        if did and op:
            shrink=self.support[key]/(self.support[key]+16)
            delta.update({k:v*shrink for k,v in self.matchup.get(key,{}).items()})
        return replace(p,**{k:max(J.BOUNDS[k][0],min(J.BOUNDS[k][1],getattr(p,k)+v)) for k,v in delta.items()})

    def learn_pair(self,a,b,r,seed,pa,pb,base):
        rng=random.Random(seed^0x48A198)
        # A second shuffle seed tests both policies: never inspect future piles.
        check_seed=seed^0x1F38B426
        reference=self.play(a,b,check_seed,pa,pb)
        for own,other,current,opponent in [(a,b,pa,pb),(b,a,pb,pa)]:
            if own=='ghost':continue
            did=J.route_id(own);op=J.route_id(other);key=(did or 'generic')+'|'+(op or 'unknown')
            scope='matchup' if did and op and rng.random()<.25 else 'route' if did and rng.random()<.6 else 'context'
            cell=self.matchup.setdefault(key,{}) if scope=='matchup' else self.route[did] if scope=='route' else self.context[stage(r)]
            changes={}
            for k in rng.sample(J.KEYS,2):
                lo,hi=J.BOUNDS[k];step=(hi-lo)*.04*rng.choice([-1,1])
                changes[k]=max(lo,min(hi,getattr(current,k)+step))-getattr(current,k)
            candidate=replace(current,**{k:getattr(current,k)+v for k,v in changes.items()})
            trials=[]
            for trial_seed,baseline in [(seed,base),(check_seed,reference)]:
                trial=self.play(a,b,trial_seed,candidate if own==a else opponent,opponent if own==a else candidate)
                trials.append(self.reward(trial,own,other)-self.reward(baseline,own,other))
            gain=sum(trials)/2;accepted=gain>.005 and min(trials)>=-.03
            if accepted:
                for k,v in changes.items():
                    lo,hi=J.BOUNDS[k];bound=(hi-lo)*.3
                    cell[k]=max(-bound,min(bound,.998*cell.get(k,0)+.3*v))
                self.accepts+=1
            self.updates+=1;self.support[key]+=1;self.experience[key]+=1
            self.log.append(dict(round=r,route=did,opponent=op,scope=scope,changes=changes,gain=gain,
                seed_gains=trials,accepted=accepted,outcome='win' if base['winner']==own else 'draw' if base['winner']=='draw' else 'loss',
                reason='two_shuffle_mean_gain_and_no_large_regression' if accepted else 'insufficient_or_unstable_gain'))

    def dump(self):
        data=super().dump();data.update(context=self.context,matchup=self.matchup,support=dict(self.support));return data


class Learner(A.Learner):
    def __init__(self,saved):
        super().__init__(saved)
        self.w=copy.deepcopy(saved['draft']);self.prior=copy.deepcopy(saved.get('prior',self.w));self.updates=saved['updates']
        for k,v in EXTRA.items():self.w.setdefault(k,v);self.prior.setdefault(k,v)
        self.combat=Combat(saved['combat']);self.terminal_updates=0
        self.draft_strategy_enabled=saved.get('draft_strategy_enabled',False)
        if not self.draft_strategy_enabled:
            for k in EXTRA:self.w.pop(k,None);self.prior.pop(k,None)

    def enable_training(self):
        self.draft_strategy_enabled=True
        for k,v in EXTRA.items():self.w.setdefault(k,v);self.prior.setdefault(k,v)

    def explain(self,p,kind,f,score,options,**detail):
        f=dict(f)
        contributions={k:self.w.get(k,0)*v for k,v in f.items() if v and self.w.get(k,0)}
        alternatives=[]
        for row in sorted(options,key=lambda x:x[0],reverse=True)[:3]:
            alternatives.append(dict(name=row[2],score=row[0],cost=row[3]))
        p.explanations.append(dict(kind=kind,round=p.current_round,target=p.target,
            points=p.points,hp=p.tournament_hp,next_public=copy.deepcopy(p.next_public),
            score=score,features=f,contributions=contributions,alternatives=alternatives,
            reason='best_positive_legal_marginal_value' if kind=='buy' else 'no_legal_purchase_beats_hold' if kind=='hold' else 'positive_removal_value',**detail))

    def payment_features(self,p,f,cost):
        if self.draft_strategy_enabled:f['reserve_plan']=reserve_plan(p,p.points-cost)-reserve_plan(p,p.points)

    def refresh_decision(self,p,players,r,rng,learn):
        if not self.draft_strategy_enabled:return super().refresh_decision(p,players,r,rng,learn)
        f,allowed=super().refresh_decision(p,players,r,rng,False)
        if f:
            f['reserve_plan']=reserve_plan(p,p.points-1)-reserve_plan(p,p.points)
        score=T.A.dot(self.w,f) if f else 0
        decision=bool(f) and score+(rng.gauss(0,.015) if learn else 0)>0
        p.explanations.append(dict(kind='refresh' if decision else 'skip_refresh',round=r,points=p.points,
            hp=p.tournament_hp,features=f,score=score,
            contributions={k:self.w.get(k,0)*v for k,v in f.items()},
            reason='expected_search_value_exceeds_coin_and_reserve_cost' if decision else 'preserve_points_or_no_affordable_improvement'))
        return f,decision

    def close_shop(self,p):
        if not self.draft_strategy_enabled:return
        f=dict(bank=A.bank_value(p,p.points),reserve_plan=reserve_plan(p,p.points))
        if p.bank:p.decisions.append(f)
        p.explanations.append(dict(kind='bank',points=p.points,carried=p.bank,discarded=max(0,p.points-2),
            features=f,reason='carry_cap_two_and_current_survival_budget'))

    def update(self,p,reward):
        advantage=max(-1,min(1,reward-p.average_reward));p.average_reward=.85*p.average_reward+.15*reward
        current=Counter()
        for f in p.decisions:
            norm=max(1,math.sqrt(sum(v*v for v in f.values())))
            for k in self.w:current[k]+=f.get(k,0)/norm/max(1,len(p.decisions))
        old=getattr(p,'credit',{})
        p.credit={k:.6*old.get(k,0)+current[k] for k in self.w}
        for k in self.w:
            self.w[k]+=.012*advantage*p.credit[k]
            base=self.prior[k];self.w[k]=max(base*.5,min(base*1.5,.998*self.w[k]+.002*base))
        p.total_reward+=reward;self.updates+=1

    def finish_episode(self,players,champions,r):
        winners={p['pid'] for p in champions}
        for p in players:
            outcome=1 if p.pid in winners else -.25
            for k,value in getattr(p,'credit',{}).items():
                base=self.prior[k];self.w[k]=max(base*.5,min(base*1.5,self.w[k]+.004*outcome*value))
            self.terminal_updates+=1


def install():
    A.vector=vector;A.install()


def dump(model):
    return dict(construction_profile='tournament-v1',draft=model.w,prior=model.prior,updates=model.updates,
        combat=model.combat.dump(),terminal_updates=model.terminal_updates,draft_strategy_enabled=model.draft_strategy_enabled)
