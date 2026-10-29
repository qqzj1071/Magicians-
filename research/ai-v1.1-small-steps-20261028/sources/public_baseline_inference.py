"""Previous construction/checkpoint with explicit public announcement delivery.

Compatibility adapter only: no claim of additional battle-strength improvement.
"""
import copy
import json
from pathlib import Path
import route_feasible_draft as R
T=R.T
ORIGINAL_SPECIALIZE=T.S.maybe_specialize


def pick_target(p,players,w):
    ns=T.S.names(p);route=T.A.route_of(ns)
    if route:p.target=T.A.ROUTE_ID[route];return
    market=p.public_market
    blocked={v['route'] for pid,v in market['players'].items() if int(pid)!=p.pid and v['route']}
    blocked|={n for n,r in market['release_round'].items() if r>p.current_round}
    legal=[did for did,d in T.S.TARGETS.items() if not p.spec or d['element']==p.spec]
    options=[did for did in legal if T.S.TARGETS[did]['route'] not in blocked] or legal
    pool=getattr(p,'visible_route_pool',None)
    if pool is not None and p.current_round>=8:
        visible=[]
        for token in pool.offers[p.pid]:
            if not token:continue
            name=pool.tokens[token]
            if T.S.C.CARDS[name].kind!='route_legendary':continue
            cost,_=T.A.price(p,name,w,players)
            if cost is not None and cost<=p.points:visible.append(T.A.ROUTE_ID[name])
        choices=[did for did in options if did in visible]
        if choices:options=choices
    def value(did):
        result=T.A.dot(w,T.A.vector(p,ns,did))+.18*(did==p.affinity)+.08*(did==p.target)
        result-=.05*sum(v['spec']==T.S.TARGETS[did]['element'] for pid,v in market['players'].items() if int(pid)!=p.pid)
        return result,did
    p.target=max(options,key=value)


def announce(model,p,players):
    current=dict(spec=p.spec,route=T.A.route_of(T.S.names(p)));old=model.public['players'][str(p.pid)]
    for key in ['spec','route']:
        if old[key]==current[key]:continue
        previous=old[key];old[key]=current[key]
        if key=='route' and previous:model.public['release_round'][previous]=p.current_round+1
        before={q.pid:q.target for q in players}
        for q in players:pick_target(q,players,model.w)
        model.events.append(dict(seq=len(model.events)+1,round=p.current_round,pid=p.pid,kind=key,
            previous=previous,value=current[key],receivers=[q.pid for q in players],
            retargets={str(q.pid):dict(old=before[q.pid],new=q.target) for q in players if q.target!=before[q.pid]}))


def maybe_specialize(p,r):
    ORIGINAL_SPECIALIZE(p,r)
    observer=getattr(p,'public_observer',None)
    if observer:announce(observer[0],p,observer[1])


class PublicBaseline(T.JointLearner):
    def on_episode_start(self,players):
        self.public=dict(players={str(p.pid):dict(spec='',route='') for p in players},release_round={})
        self.events=[]
        for p in players:p.public_market=self.public;p.public_observer=(self,players)

    def round_diagnostics(self,players,r):
        for p in players:
            assert self.public['players'][str(p.pid)]==dict(spec=p.spec,route=T.A.route_of(T.S.names(p)))
        return dict(broadcasts=[x for x in self.events if x['round']==r],public_state=copy.deepcopy(self.public))


def load_model(checkpoint):
    data=json.loads(Path(checkpoint).read_text(encoding='utf-8'))
    R.install();T.A.pick_target=pick_target;T.S.pick_target=pick_target;T.S.maybe_specialize=maybe_specialize
    model=PublicBaseline();model.w=data['draft']
    model.combat.stage=data['combat']['stage'];model.combat.route=data['combat']['route']
    model.combat.updates=data['combat']['updates'];model.combat.accepts=data['combat']['accepts']
    model.combat.experience.update(data['combat']['experience'])
    return model
