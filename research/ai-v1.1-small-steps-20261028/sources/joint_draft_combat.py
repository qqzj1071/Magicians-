"""Actual-deck staged controller, historical transfer, bounded online evolution.

No frozen engine/planner or canonical historical policy is edited. The research
planner projects through the research engine and never reads the future pile.
"""
import copy
import json
import random
import sys
import types
from collections import Counter
from dataclasses import asdict,replace
from pathlib import Path
import cards as C
from shared_draft_combat import ENGINE as E

source=(Path(__file__).parent/'planner.py').read_text(encoding='utf-8')
source=source.replace('import engine as E','from shared_draft_combat import ENGINE as E')
source=source.replace("if st[j].element=='poison' and st[1-j].poison:","if st[j].poison_layers and st[1-j].poison:")
P=types.ModuleType('joint_draft_planner');P.__file__=str(Path(__file__).parent/'planner.py')
sys.modules[P.__name__]=P;exec(compile(source,P.__file__,'exec'),P.__dict__)
original_queue=E.choose_queue


def phase(states,i,t,p):
    s,e=states[i],states[1-i]
    effective=max(1,e.hp)+float(e.shield)*(1-float(E.shield_pen(s)))
    if E.estimate(states,i,t,100)*p.finish_ratio>=effective:return 'finish'
    names={v['name'] for v in C.DECKS[s.deck_id]['entries']}
    missing_spec=any(C.CARDS[n].kind=='specialization' for n in names) and not s.spec
    missing_route=any(C.CARDS[n].kind=='route_legendary' for n in names) and not s.route
    return 'startup' if missing_spec or missing_route else 'operation'


P.phase=phase


def queue(snapshot,i,pool,policy,t,discard=()):
    if policy.mode=='staged':return P.choose(snapshot,i,pool,policy,t,discard)
    return original_queue(snapshot,i,pool,policy,t,discard)


E.choose_queue=queue
HISTORY=json.loads((Path(__file__).parent/'policies.json').read_text(encoding='utf-8'))
REFS=copy.deepcopy(C.DECKS)
ROUTE_ID={v['route']:k for k,v in REFS.items()}
KEYS=['core_priority','startup_resource','operation_layer','finish_burst','panic','penetration_value',
      'tempo_value','sustain_value','shield_engine','epic_cycle','budget_fit','damage','health',
      'layer','draw','energy','search','cost_power','cleanse','reserve']
BOUNDS={k:(min(P.RANGES[k]),max(P.RANGES[k])) if k in P.RANGES else (2.,40.) for k in KEYS}


def bucket(r):return '1-3' if r<=3 else '4-7' if r<=7 else '8-14'
def route_id(did):return ROUTE_ID.get(C.DECKS[did].get('route',''))


class CombatLearner:
    def __init__(self):
        self.stage={k:{} for k in ['1-3','4-7','8-14']};self.route={k:{} for k in REFS}
        self.updates=0;self.accepts=0;self.experience=Counter();self.log=[];self.games=0

    def policy(self,own,other,r,mode='adaptive'):
        did=route_id(own);op=route_id(other);p=P.initial(own,other)
        if mode=='greedy':return E.GREEDY
        if mode!='generic' and did:
            # Transfer the complete route prior, already trained across opponents.
            data=HISTORY['routes'][did];p=replace(p,**{k:v for k,v in data.items() if k not in ('own','opponent')})
            # Blend all historical own-side matchup profiles, then condition a small
            # component on a publicly held opponent route; no hidden target access.
            profiles=[cell['policies'][did] for cell in HISTORY.get('matchups',{}).values()
                      if did in cell.get('policies',{})]
            if profiles:
                p=replace(p,**{k:.8*getattr(p,k)+.2*sum(v[k] for v in profiles)/len(profiles) for k in KEYS})
            pair=HISTORY.get('matchups',{}).get('|'.join(sorted((did,op or ''))),{})
            if did in pair.get('policies',{}):
                p=replace(p,**{k:.8*getattr(p,k)+.2*pair['policies'][did][k] for k in KEYS})
        else:p=replace(p,**HISTORY['common'])
        if mode=='adaptive':
            delta=Counter(self.stage[bucket(r)])
            if did:delta.update(self.route[did])
            p=replace(p,**{k:max(BOUNDS[k][0],min(BOUNDS[k][1],getattr(p,k)+delta[k])) for k in delta})
        # Missing cards must not be imagined. Resource value comes from actual
        # pool projections in the planner; own/opponent IDs point to actual decks.
        return replace(p,own=own,opponent=other,lethal_candidates=int(p.lethal_candidates))

    def play(self,a,b,seed,pa,pb):
        self.games+=1
        return E.simulate(a,b,seed,pa,pb,validate=True)

    def fight(self,a,b,r,seed,learn=False):
        pa=self.policy(a,b,r);pb=self.policy(b,a,r)
        result=self.play(a,b,seed,pa,pb)
        if learn:self.learn_pair(a,b,r,seed,pa,pb,result)
        return result

    @staticmethod
    def reward(result,own,other):
        x=result['players'][own];y=result['players'][other]
        score=.5 if result['winner']=='draw' else float(result['winner']==own)
        margin=max(-1,min(1,(x['hp']-y['hp'])/1000))
        waste=x['wasted']/max(1,x['granted'])
        return score+.05*margin-.025*waste

    def learn_pair(self,a,b,r,seed,pa,pb,base):
        rng=random.Random(seed^723192)
        # Independent unilateral interventions keep the opponent frozen. Both
        # winners and losers test one bounded candidate, even after a draw.
        for own,other,current,opponent in [(a,b,pa,pb),(b,a,pb,pa)]:
            did=route_id(own);scope='route' if did and rng.random()<.65 else 'stage'
            cell=self.route[did] if scope=='route' else self.stage[bucket(r)]
            change={}
            for k in rng.sample(KEYS,2):
                lo,hi=BOUNDS[k];step=(hi-lo)*.075*rng.choice([-1,1])
                value=max(lo,min(hi,getattr(current,k)+step));change[k]=value-getattr(current,k)
            candidate=replace(current,**{k:getattr(current,k)+v for k,v in change.items()})
            trial=self.play(a,b,seed,candidate if own==a else opponent,opponent if own==a else candidate)
            gain=self.reward(trial,own,other)-self.reward(base,own,other)
            accepted=gain>.0025
            if accepted:
                for k,v in change.items():cell[k]=cell.get(k,0)+v
                self.accepts+=1
            self.updates+=1;self.experience[(did or 'generic:'+bucket(r))+'|'+(route_id(other) or 'unknown')]+=1
            self.log.append(dict(round=r,seed=seed,own=own,route=did,opponent=route_id(other),scope=scope,
                                 changes=change,gain=gain,accepted=accepted))

    def dump(self):
        return dict(stage=self.stage,route=self.route,updates=self.updates,accepts=self.accepts,
                    experience=dict(self.experience),games=self.games)
