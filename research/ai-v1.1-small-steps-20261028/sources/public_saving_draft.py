"""Public broadcasts, finite route replanning, operational value and bank choices.

No future offers or other players' private decks enter decisions. Study points
are distinct from battle energy; banking never changes rarity probabilities.
"""
import copy
import math
from collections import Counter
from functools import lru_cache
import train_joint_draft as T
from draft_economy import CURRENT,is_free_purchase,free_purchase_rarities,deletion_limit,deletion_price

ORIGINAL_METRICS=T.A.metrics
PRIOR=dict(dice=8.,main=4.,draw=2.,search=2.,shuffle=1.5,progress=4.,quality=1.2,layer=1.,
           size=.5,foreign=.8,coin=.12,refresh=.8,save=.2,counter=.2,core=3.,
           route_epic=1.2,route_rare=.7,energy=3.,draw_capacity=3.,search_capacity=2.,
           cycle_capacity=1.5,bank=1.2)


@lru_cache(maxsize=8192)
def signature(name,element,route,specialized):
    E=T.J.E
    did='resource-projection-'+element
    T.S.C.DECKS.setdefault(did,dict(element=element,entries=[]))
    s=E.State(element,deck_id=did,hp=800,energy=20,spec=specialized,specialization_selected=specialized,route=route,
              layers=3,**{e+'_layers':3 if e==element else 0 for e in ['fire','water','earth','wind','poison']})
    states=[s,E.State('earth',hp=800)];plan=E.card_plan(states,0,name,0);after=E.resolve_cards(states,[plan],0)[0]
    search=plan.search[2] if plan.search else 0
    return (max(0,after.next_draw-s.next_draw),max(0,after.next_energy-s.next_energy),search,int(plan.shuffle),
            int(after.contract and not s.contract))


def resources(p,ns,did=None):
    element=p.spec or T.S.TARGETS[did or p.target or p.affinity]['element'];route=T.A.route_of(ns)
    sums=[0.]*5
    for n in ns:
        for i,v in enumerate(signature(n,element,route,bool(p.spec))):sums[i]+=v
    return dict(draw=sums[0],energy=sums[1]+sums[4],search=sums[2],shuffle=sums[3])


def vector(p,ns,did=None):
    v=T.vector(p,ns,did);q=resources(p,ns,did)
    # Projected effects are heuristics; real fights, not these proxies, select models.
    v.update(draw_capacity=min(1,q['draw']/6),energy=min(1,q['energy']/3),
             search_capacity=min(1,q['search']/4),cycle_capacity=min(1,q['shuffle']/2))
    return v


def pick_target(p,players,w):
    ns=T.S.names(p);route=T.A.route_of(ns)
    if route:p.target=T.A.ROUTE_ID[route];return
    market=p.public_market
    unavailable={v['route'] for pid,v in market['players'].items() if int(pid)!=p.pid and v['route']}
    unavailable|={n for n,r in market['release_round'].items() if r>p.current_round}
    legal=[did for did,d in T.S.TARGETS.items() if not p.spec or d['element']==p.spec]
    options=[did for did in legal if T.S.TARGETS[did]['route'] not in unavailable] or legal
    pool=getattr(p,'visible_route_pool',None)
    if pool is not None and p.current_round>=8:
        visible=[]
        for t in pool.offers[p.pid]:
            if not t:continue
            n=pool.tokens[t]
            if T.S.C.CARDS[n].kind!='route_legendary':continue
            cost,_=T.A.price(p,n,w,players)
            if cost is not None and cost<=p.points:visible.append(T.A.ROUTE_ID[n])
        selected=[did for did in options if did in visible]
        if selected:options=selected
    scores=[]
    for did in options:
        d=T.S.TARGETS[did];value=T.A.dot(w,vector(p,ns,did))+.12*(did==p.affinity)+.05*(did==p.target)
        value-=.15*sum(v['spec']==d['element'] for pid,v in market['players'].items() if int(pid)!=p.pid)
        scores.append((value,did))
    p.target=max(scores)[1]


def bank_value(p,points):
    b=min(2,max(0,points));r=p.current_round
    if r>=14:return 0. # No value from unused points after the evaluation horizon.
    q=resources(p,T.S.names(p));gap=max(0,1-(q['draw']/6+q['energy']/3)/2)
    result=b*(.12+.12*gap)
    if r==1:
        result+=.35*(b>=1)+.15*(b>=2) # next-round 3-cost first-face / 4-cost refresh+epic
    if r==5:
        result+=.25*(b>=1)+.15*(b>=2) # refresh+legend affordability, not higher odds
    if r+1 in (8,10,12):
        result+=(.4 if not T.A.route_of(T.S.names(p)) else .2)*(b>=1)+.15*(b>=2)
    # Sacrificing present strength costs more after a bad prior battle.
    risk=max(0,-getattr(p,'recent_reward',0))
    return result*max(.35,1-.65*risk)


def announce(model,p,players):
    current=dict(spec=p.spec,route=T.A.route_of(T.S.names(p)));old=model.public['players'][str(p.pid)]
    for key in ['spec','route']:
        if old[key]==current[key]:continue
        previous=old[key];old[key]=current[key]
        if key=='route' and previous:model.public['release_round'][previous]=p.current_round+1
        before={q.pid:q.target for q in players}
        for q in players:pick_target(q,players,model.w)
        model.events.append(dict(seq=len(model.events)+1,round=p.current_round,pid=p.pid,kind=key,
            previous=previous,value=current[key],receivers=[0,1,2,3],
            retargets={str(q.pid):dict(old=before[q.pid],new=q.target) for q in players if q.target!=before[q.pid]}))


def purchase(p,players,pool,model,r,rng,learn):
    bought=set();p.visible_route_pool=pool
    try:
        while True:
            pick_target(p,players,model.w);ns=T.S.names(p);before=vector(p,ns);options=[]
            for i,t in enumerate(pool.offers[p.pid]):
                if not t:continue
                n=pool.tokens[t];cost,old=T.A.price(p,n,model.w,players)
                if cost is None or cost>p.points:continue
                after=ns.copy()
                if old:after.remove(old)
                after.append(n);after=T.A.projected(p,after);vec=vector(p,after)
                f={k:vec[k]-before[k] for k in before};f['coin']=-cost
                f['bank']=bank_value(p,p.points-cost)-bank_value(p,p.points) if model.saving else 0
                c=T.S.C.CARDS[n];specs=[v['spec'] for pid,v in model.public['players'].items() if int(pid)!=p.pid]
                f['counter']=float('穿透' in c.text and 'earth' in specs or '回复量降低' in c.text and 'water' in specs)
                value=T.A.dot(model.w,f)+(rng.gauss(0,.035) if learn else 0)
                options.append((value,i,n,cost,old,f))
            if not options or max(options,key=lambda x:x[0])[0]<=.025:
                model.finance.append(dict(round=r,pid=p.pid,kind='stop_buy',points=p.points,
                    best_gain=max((x[0] for x in options),default=None),bank_value=bank_value(p,p.points)))
                if model.saving:p.decisions.append(dict(bank=bank_value(p,p.points)))
                break
            value,i,n,cost,old,f=max(options,key=lambda x:x[0])
            if old:
                item=next(x for x in p.deck if x[0]==old);p.deck.remove(item);pool.remove(item[1]);p.route_changes+=T.S.C.CARDS[n].kind=='route_legendary'
            token=pool.buy(p.pid,i);p.deck.append((n,token));p.points-=cost;p.purchases+=1;bought.add(i)
            if cost==0:
                assert is_free_purchase(T.S.C.CARDS[n].rarity,r,p.free_used,p.economy)
                p.free_used=True;p.free_purchases+=1
            p.actions.append(dict(kind='buy',name=n,slot=i,cost=cost,replaced=old,score=value))
            if T.S.C.CARDS[n].element!='generic':p.bought_elements.add(T.S.C.CARDS[n].element)
            p.decisions.append(f);T.S.maybe_specialize(p,r);announce(model,p,players)
    finally:p.visible_route_pool=None
    return bought


def delete(p,players,pool,model,r):
    for index in range(deletion_limit(r,p.economy)):
        cost=deletion_price(r,index,p.economy)
        if p.points<cost or len(p.deck)<=8:break
        options=[];ns=T.S.names(p);before=vector(p,ns)
        for i,(n,t) in enumerate(p.deck):
            c=T.S.C.CARDS[n]
            if c.kind in ('specialization','route_legendary'):continue
            if p.spec and c.element==p.spec and sum(T.S.C.CARDS[x].element==p.spec and T.S.C.CARDS[x].kind!='specialization' for x in ns)<=3:continue
            after=ns.copy();after.pop(i);v=vector(p,after);f={k:v[k]-before[k] for k in before};f['coin']=-cost
            f['bank']=bank_value(p,p.points-cost)-bank_value(p,p.points) if model.saving else 0
            options.append((T.A.dot(model.w,f),i,f))
        if not options or max(options,key=lambda x:x[0])[0]<=.025:break
        value,i,f=max(options,key=lambda x:x[0]);n,t=p.deck.pop(i);pool.remove(t);p.points-=cost
        p.deletes+=1;p.deletion_points+=cost;p.decisions.append(f);p.actions.append(dict(kind='delete',name=n,cost=cost,score=value))


class Learner:
    def __init__(self):
        self.w=copy.deepcopy(PRIOR);self.combat=T.J.CombatLearner();self.updates=0;self.saving=True

    def on_episode_start(self,players):
        self.public=dict(players={str(p.pid):dict(spec='',route='') for p in players},release_round={})
        self.events=[];self.finance=[]
        for p in players:p.public_market=self.public;p.recent_reward=0

    def observe_result(self,p,reward):p.recent_reward=reward

    def round_diagnostics(self,players,r):
        for p in players:
            assert self.public['players'][str(p.pid)]==dict(spec=p.spec,route=T.A.route_of(T.S.names(p)))
        return dict(broadcasts=[x for x in self.events if x['round']==r],public_state=copy.deepcopy(self.public),
                    finance=[x for x in self.finance if x['round']==r])

    def refresh_decision(self,p,players,r,rng,learn):
        if p.points<1:return {},False
        before=vector(p,T.S.names(p));budget=p.points-1;pool=p.visible_route_pool if getattr(p,'visible_route_pool',None) else None
        # Current offer size is supplied explicitly by the simulator; no future
        # second-face concrete card or pre-generated rank is inspected.
        slots=getattr(p,'refresh_slots',8);ranks=T.S.CFG['rarities'][str(r) if r<8 else '8_plus'][1]
        gains={k:[] for k in range(4)}
        ns=T.S.names(p)
        unavailable={v['route'] for pid,v in self.public['players'].items() if int(pid)!=p.pid}
        for n,c in T.S.C.CARDS.items():
            if c.kind=='specialization' or c.kind=='route_legendary' and n in unavailable:continue
            cost,old=T.A.price(p,n,self.w,players)
            if cost is None or cost>budget:continue
            after=ns.copy()
            if old:after.remove(old)
            after.append(n);after=T.A.projected(p,after);v=vector(p,after)
            f={k:v[k]-before[k] for k in before};f['coin']=-cost
            gains[T.S.RANK[c.rarity]].append(max(0,T.A.dot(self.w,f)))
        estimates=[]
        for rank,values in gains.items():
            if not values:continue
            values.sort();potential=values[int(.75*(len(values)-1))]
            probability=1-(1-ranks[rank])**slots
            if rank==3 and r in (8,10,12) and slots:probability=1.
            estimates.append(potential*probability)
        expected=max(estimates,default=0)+.15*sum(estimates)
        f=dict(refresh=expected,coin=-1,bank=(bank_value(p,budget)-bank_value(p,p.points)) if self.saving else 0)
        value=T.A.dot(self.w,f)+(rng.gauss(0,.025) if learn else 0)
        choice=value>.08
        self.finance.append(dict(round=r,pid=p.pid,kind='refresh_decision',points=p.points,slots=slots,
            expected_gain=expected,score=value,refresh=choice,bank_value=bank_value(p,p.points)))
        return f,choice

    def update(self,p,reward):
        # Primarily combat reward. Operational change is a small dense guide;
        # Dice changes are deliberately not used as the training reward.
        v=vector(p,T.S.names(p));progress=(v['progress']+v['draw_capacity']+v['energy']+v['cycle_capacity'])/4
        old=getattr(p,'last_readiness',0);p.last_readiness=progress;p.recent_reward=reward
        shaped=.9*reward+.1*max(-1,min(1,progress-old));advantage=max(-1,min(1,shaped-p.average_reward))
        p.average_reward=.8*p.average_reward+.2*shaped
        for f in p.decisions:
            norm=max(.2,math.sqrt(sum(x*x for x in f.values())))
            for k in self.w:self.w[k]+=.025*advantage*f.get(k,0)/norm
        for k in self.w:self.w[k]=max(PRIOR[k]*.25,min(PRIOR[k]*2,.999*self.w[k]+.001*PRIOR[k]))
        self.updates+=1


def metrics(p):
    m=ORIGINAL_METRICS(p);m['operation_effects']=resources(p,T.S.names(p));return m


def install():
    T.A.vector=vector;T.A.pick_target=pick_target
    T.S.pick_target=pick_target;T.S.purchase_phase=purchase;T.S.delete_phase=delete;T.S.metrics=metrics
