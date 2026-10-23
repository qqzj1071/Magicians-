"""Survival-aware actor; explicit specialization threshold and public opponent.

Research heuristics with bounded contextual updates, not an optimal planner.
"""
import copy
import math
from collections import Counter
import public_baseline_inference as B
from draft_economy import CURRENT,is_free_purchase,deletion_limit,deletion_price
T=B.T
PRIOR_SPECIALIZE=T.S.maybe_specialize


def effective(p,ns):
    if p.spec:return p.spec
    return next((T.S.C.CARDS[n].element for n in ns if T.S.C.CARDS[n].kind=='specialization'),'')


def counter_value(p,ns):
    enemy=getattr(p,'next_public',{})
    element=enemy.get('spec','');route=enemy.get('route','')
    text=' '.join(T.S.C.CARDS[n].text for n in ns)
    # Public mechanics, no opponent private card list or future card draws.
    value=0.
    if element=='earth':value+=min(2,text.count('穿透')+text.count('无视'))*.25
    if element=='water':value+=min(2,text.count('回复量降低')+text.count('禁疗'))*.35
    if element=='poison':value+=min(2,text.count('清除')+text.count('净化'))*.3
    if element in ('fire','wind'):value+=min(2,text.count('护盾')+text.count('防御'))*.12
    own_route=T.A.route_of(ns)
    if own_route:
        c=T.S.C.CARDS[own_route]
        if element=='earth' and ('穿透' in c.text or '无视' in c.text):value+=.5
        if element=='poison' and ('净化' in c.text or '回复' in c.text):value+=.3
        if route and route==own_route:value+=0 # no invented fixed counter table
    return value


def vector(p,ns,did=None):
    v=T.vector(p,ns,did);element=effective(p,ns) or T.S.TARGETS[did or p.target or p.affinity]['element']
    own=[T.S.C.CARDS[n] for n in ns if T.S.C.CARDS[n].element==element and T.S.C.CARDS[n].kind!='specialization']
    layers=sum(c.layers for c in own);chosen=bool(effective(p,ns))
    # Third card activates an explicit discontinuity, beyond linear progress.
    # Includes the pre-existing enchantments' ordinary layer-rate uplift.
    v['specialization_jump']=float(chosen)*(1+min(20,layers)/20)
    v['effective_layers']=min(25,layers)/25*(1 if chosen else .5)
    v['next_counter']=counter_value(p,ns)
    return v


def pick_target(p,players,w):
    # Preserve available-route logic, replacing only its public-aware score.
    ns=T.S.names(p);route=T.A.route_of(ns)
    if route:p.target=T.A.ROUTE_ID[route];return
    blocked={v['route'] for pid,v in p.public_market['players'].items() if int(pid)!=p.pid and v['route']}
    blocked|={n for n,r in p.public_market['release_round'].items() if r>p.current_round}
    legal=[did for did,d in T.S.TARGETS.items() if not p.spec or d['element']==p.spec]
    options=[did for did in legal if T.S.TARGETS[did]['route'] not in blocked] or legal
    pool=getattr(p,'visible_route_pool',None)
    if pool and p.current_round>=8:
        visible=[]
        for t in pool.offers[p.pid]:
            if not t:continue
            n=pool.tokens[t]
            if T.S.C.CARDS[n].kind=='route_legendary':
                cost,_=T.A.price(p,n,w,players)
                if cost is not None and cost<=p.points:visible.append(T.A.ROUTE_ID[n])
        subset=[did for did in options if did in visible]
        if subset:options=subset
    def score(did):
        d=T.S.TARGETS[did];future=ns if d['route'] in ns else ns+[d['route']]
        return (T.A.dot(w,vector(p,ns,did))+.18*(did==p.affinity)+.08*(did==p.target)
                +w.get('next_counter',1)*.25*counter_value(p,future)
                -.05*sum(v['spec']==d['element'] for pid,v in p.public_market['players'].items() if int(pid)!=p.pid),did)
    p.target=max(options,key=score)


def announce(model,p,players):
    current=dict(spec=p.spec,route=T.A.route_of(T.S.names(p)));old=model.public['players'][str(p.pid)]
    for key in ['spec','route']:
        if old[key]==current[key]:continue
        previous=old[key];old[key]=current[key]
        if key=='route' and previous:model.public['release_round'][previous]=p.current_round+1
        before={q.pid:q.target for q in players}
        sync_opponents(players,model)
        for q in players:pick_target(q,players,getattr(q,'actor_weights',model.w))
        model.events.append(dict(seq=len(model.events)+1,round=p.current_round,pid=p.pid,kind=key,
            previous=previous,value=current[key],receivers=[q.pid for q in players],
            retargets={str(q.pid):dict(old=before[q.pid],new=q.target) for q in players if q.target!=before[q.pid]}))


def sync_opponents(players,model):
    for p in players:
        if getattr(p,'ghost_public',None) is not None:p.next_public=copy.deepcopy(p.ghost_public)
        else:p.next_public=copy.deepcopy(model.public['players'].get(str(getattr(p,'next_pid',-1)),{}))


def bank_value(p,points):
    saved=min(2,max(0,points));hp=getattr(p,'tournament_hp',100);loss=getattr(p,'loss_estimate',8)
    survival=max(.05,min(1,(hp-loss)/max(1,loss*3)))
    value=saved*.17
    if p.current_round in (1,5,7,9,11):value+=.15*min(1,saved)
    # All future rounds retain value; no artificial R14 evaluation cutoff.
    return value*survival


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
                after.append(n);after=T.A.projected(p,after);v=vector(p,after)
                f={k:v[k]-before[k] for k in before};f['coin']=-cost
                f['bank']=bank_value(p,p.points-cost)-bank_value(p,p.points)
                pressure=1+max(0,1-p.tournament_hp/50)
                f['next_counter']*=pressure
                # A streak milestone may add at most one point next round. No
                # reward for losing independent of the actual health cost.
                f['tempo_streak']=f['specialization_jump']*.2*int(abs(p.streak)%3==2)
                if hasattr(model,'payment_features'):model.payment_features(p,f,cost)
                gain=T.A.dot(model.w,f)+(rng.gauss(0,.035) if learn else 0)
                options.append((gain,i,n,cost,old,f))
            if not options or max(options,key=lambda x:x[0])[0]<=.025:
                if hasattr(model,'explain'):model.explain(p,'hold',{},0,options)
                break
            gain,i,n,cost,old,f=max(options,key=lambda x:x[0])
            if hasattr(model,'explain'):model.explain(p,'buy',f,gain,options,name=n,cost=cost)
            if old:
                item=next(x for x in p.deck if x[0]==old);p.deck.remove(item);pool.remove(item[1]);p.route_changes+=T.S.C.CARDS[n].kind=='route_legendary'
            token=pool.buy(p.pid,i);p.deck.append((n,token));p.points-=cost;p.purchases+=1;bought.add(i)
            if cost==0:
                assert is_free_purchase(T.S.C.CARDS[n].rarity,r,p.free_used,p.economy)
                p.free_used=True;p.free_purchases+=1
            if T.S.C.CARDS[n].element!='generic':p.bought_elements.add(T.S.C.CARDS[n].element)
            p.actions.append(dict(kind='buy',name=n,slot=i,cost=cost,replaced=old,score=gain))
            p.decisions.append(f);PRIOR_SPECIALIZE(p,r);announce(model,p,players)
    finally:p.visible_route_pool=None
    return bought


def delete(p,players,pool,model,r):
    for index in range(deletion_limit(r,p.economy)):
        cost=deletion_price(r,index,p.economy)
        if p.points<cost or len(p.deck)<=8:break
        ns=T.S.names(p);before=vector(p,ns);options=[]
        for i,n in enumerate(ns):
            c=T.S.C.CARDS[n]
            if c.kind in ('specialization','route_legendary'):continue
            if p.spec and c.element==p.spec and sum(T.S.C.CARDS[x].element==p.spec and T.S.C.CARDS[x].kind!='specialization' for x in ns)<=3:continue
            after=ns.copy();after.pop(i);v=vector(p,after);f={k:v[k]-before[k] for k in before}
            f['coin']=-cost;f['bank']=bank_value(p,p.points-cost)-bank_value(p,p.points)
            if hasattr(model,'payment_features'):model.payment_features(p,f,cost)
            options.append((T.A.dot(model.w,f),i,f))
        if not options or max(options,key=lambda x:x[0])[0]<=.025:break
        gain,i,f=max(options,key=lambda x:x[0]);n,t=p.deck.pop(i);pool.remove(t);p.points-=cost
        if hasattr(model,'explain'):model.explain(p,'delete',f,gain,[],name=n,cost=cost)
        p.deletes+=1;p.deletion_points+=cost;p.decisions.append(f);p.actions.append(dict(kind='delete',name=n,cost=cost,score=gain))


class Learner(B.PublicBaseline):
    def __init__(self,saved):
        super().__init__();self.w=copy.deepcopy(saved['draft']);self.w.update(specialization_jump=3.5,effective_layers=1.5,next_counter=1.,bank=.35,tempo_streak=.25)
        self.prior=copy.deepcopy(self.w)
        c=saved['combat'];self.combat.stage=copy.deepcopy(c['stage']);self.combat.route=copy.deepcopy(c['route'])
        self.combat.updates=c['updates'];self.combat.accepts=c['accepts'];self.combat.experience.update(c['experience'])

    def refresh_decision(self,p,players,r,rng,learn):
        f,_=super().refresh_decision(p,players,r,rng,False)
        if not f:return f,False
        f['bank']=bank_value(p,p.points-1)-bank_value(p,p.points)
        value=T.A.dot(self.w,f)+(rng.gauss(0,.025) if learn else 0)
        return f,value>0

    def update(self,p,reward):
        advantage=max(-1,min(1,reward-p.average_reward));p.average_reward=.8*p.average_reward+.2*reward
        for f in p.decisions:
            norm=max(1,math.sqrt(sum(v*v for v in f.values())))
            for k in self.w:self.w[k]+=.02*advantage*f.get(k,0)/norm
        for k in self.w:self.w[k]=max(self.prior[k]*.4,min(self.prior[k]*1.8,.999*self.w[k]+.001*self.prior[k]))
        self.updates+=1

    def round_diagnostics(self,players,r):
        for p in players:assert self.public['players'][str(p.pid)]==dict(spec=p.spec,route=T.A.route_of(T.S.names(p)))
        return dict(broadcasts=[e for e in self.events if e['round']==r],public_state=copy.deepcopy(self.public))


def install():
    T.A.vector=vector;T.A.pick_target=pick_target;T.S.pick_target=pick_target
    T.S.purchase_phase=purchase;T.S.delete_phase=delete
