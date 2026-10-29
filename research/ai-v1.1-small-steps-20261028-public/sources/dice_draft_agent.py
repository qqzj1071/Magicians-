"""Reference-guided, marginal-Dice construction actor with online updates.

Exact state scoring encodes the human objective; weights learn from both battle
outcomes and dense progress. This is not an end-to-end learned planner.
"""
import copy
import math
from collections import Counter
import simulate_shared_draft as S
from draft_economy import CURRENT,is_free_purchase,deletion_limit,deletion_price,free_purchase_rarities,purchase_price
from learning_core import DRAW,SEARCH,SHUFFLE

BASE_METRICS=S.metrics
ROUTE_ID={d['route']:did for did,d in S.TARGETS.items()}
PRIOR=dict(dice=32.,main=9.,draw=2.4,search=2.4,shuffle=2.,progress=2.2,
           quality=.5,layer=.3,size=2.,foreign=1.,coin=.22,refresh=1.,save=.22,counter=.12,core=2.)


def dot(w,f):return sum(w.get(k,0)*v for k,v in f.items())
def route_of(ns):return next((n for n in ns if S.C.CARDS[n].kind=='route_legendary'),'')


def reference(p,ns=None):
    ns=ns if ns is not None else S.names(p)
    return ROUTE_ID.get(route_of(ns),p.target or p.affinity)


def vector(p,ns,did=None):
    did=did or reference(p,ns);d=S.TARGETS[did];target=S.TARGET_NAMES[did];counts=Counter(ns)
    overlap=sum((counts&target).values());element=p.spec or d['element']
    main={n for n in target if S.C.CARDS[n].element==element}
    main_hits=sum(n in counts for n in main)
    own=sum(S.C.CARDS[n].element==element and S.C.CARDS[n].kind!='specialization' for n in ns)
    foreign=sum(S.C.CARDS[n].element not in ('generic',element) for n in ns)
    quality=sum((S.C.CARDS[n].attack+1.5*S.C.CARDS[n].defense)/max(1,S.C.CARDS[n].cost) for n in ns)/max(1,len(ns))/10
    committed=bool(route_of(ns))
    return dict(dice=2*overlap/max(1,len(ns)+sum(target.values()))*(1 if committed else .75),main=main_hits/max(1,len(main)),core=float(committed),
                draw=min(2,len(set(ns)&DRAW))/2,search=min(2,len(set(ns)&SEARCH))/2,
                shuffle=min(1,len(set(ns)&SHUFFLE)),progress=min(3,own)/3*(1 if p.current_round<=6 else .5),
                quality=quality,layer=min(20,sum(S.C.CARDS[n].layers for n in ns if S.C.CARDS[n].element==element))/20,
                size=-max(0,len(ns)-sum(target.values())-2)/10,foreign=-foreign/max(1,len(ns)))


def pick_target(p,players,w):
    ns=S.names(p);route=route_of(ns)
    if route:p.target=ROUTE_ID[route];return
    options=[]
    unavailable={route_of(S.names(q)) for q in players if q.pid!=p.pid}
    for did,d in S.TARGETS.items():
        if p.spec and d['element']!=p.spec:continue
        value=dot(w,vector(p,ns,did))+.18*(did==p.affinity)+.08*(did==p.target)
        value-=.05*sum(q.spec==d['element'] for q in players if q.pid!=p.pid)
        value-=2.*(d['route'] in unavailable)
        options.append((value,did))
    p.target=max(options)[1]


def projected(p,ns):
    ns=list(ns)
    if not p.spec:
        counts=Counter(S.C.CARDS[n].element for n in ns if S.C.CARDS[n].element!='generic')
        eligible=[e for e,v in counts.items() if v>=3]
        if eligible:
            e=S.TARGETS[p.target]['element']
            if e not in eligible:e=eligible[0]
            ns.append(S.SPECIAL[e])
    return ns


def price(p,n,w,players):
    c=S.C.CARDS[n];ns=S.names(p)
    if c.kind=='specialization':return None,None
    if n in ns or p.spec and c.element not in ('generic',p.spec):return None,None
    route=route_of(ns)
    if c.kind=='route_legendary':
        if not p.spec and sum(S.C.CARDS[x].element==c.element for x in ns)<2:return None,None
        if route:return 2,route
    legends=[x for x in ns if S.C.CARDS[x].rarity=='legendary']
    if c.rarity=='legendary' and len(legends)>=3:
        candidates=[x for x in legends if S.C.CARDS[x].kind!='route_legendary']
        legal=[]
        for old in candidates:
            after=ns.copy();after.remove(old);after.append(n)
            if p.spec and sum(S.C.CARDS[x].element==p.spec and S.C.CARDS[x].kind!='specialization' for x in after)<3:continue
            legal.append((dot(w,vector(p,after)),old))
        return (4,max(legal)[1]) if legal else (None,None)
    base=S.RANK[c.rarity]+1
    return purchase_price(base,c.rarity,p.current_round,p.free_used,p.economy),None


def removal_options(p,model,ns=None):
    ns=list(ns if ns is not None else S.names(p));before=vector(p,ns);result=[]
    for i,n in enumerate(ns):
        c=S.C.CARDS[n]
        if c.kind=='specialization':continue
        if p.spec and c.element==p.spec and sum(S.C.CARDS[x].element==p.spec and S.C.CARDS[x].kind!='specialization' for x in ns)<=3:continue
        after=ns.copy();after.pop(i)
        # Do not migrate reference merely by deleting a route.
        vec=vector(p,after,did=reference(p,ns));f={k:vec[k]-before[k] for k in before}
        result.append((dot(model.w,f),i,f))
    return sorted(result,reverse=True,key=lambda x:x[0])


def purchase_phase(p,players,pool,model,r,rng,learn):
    bought=set();board=pool.offers[p.pid]
    while True:
        pick_target(p,players,model.w);ns=S.names(p);before=vector(p,ns);options=[]
        removal=removal_options(p,model) if r>=7 else []
        reserve=max(0,removal[1][0]-model.w['coin']) if len(removal)>=2 else 0
        for i,t in enumerate(board):
            if not t:continue
            n=pool.tokens[t];cost,old=price(p,n,model.w,players)
            if cost is None or cost>p.points:continue
            after=ns.copy()
            if old:after.remove(old)
            after.append(n);after=projected(p,after)
            vec=vector(p,after);f={k:vec[k]-before[k] for k in before};f['coin']=-cost
            c=S.C.CARDS[n];opponents=[q.spec for q in players if q.pid!=p.pid]
            f['counter']=float('穿透' in c.text and 'earth' in opponents or '回复量降低' in c.text and 'water' in opponents)
            value=dot(model.w,f)
            if cost and p.points-cost==0:value-=reserve
            if learn:value+=rng.gauss(0,.045)
            options.append((value,i,n,cost,old,f))
        if not options or max(options,key=lambda x:x[0])[0]<=.025:break
        value,i,n,cost,old,f=max(options,key=lambda x:x[0])
        if old:
            item=next(x for x in p.deck if x[0]==old);p.deck.remove(item);pool.remove(item[1]);p.route_changes+=S.C.CARDS[n].kind=='route_legendary'
        token=pool.buy(p.pid,i);p.deck.append((n,token));p.points-=cost;p.purchases+=1;bought.add(i)
        if cost==0:
            assert is_free_purchase(S.C.CARDS[n].rarity,r,p.free_used,p.economy)
            p.free_used=True;p.free_purchases+=1
        p.actions.append(dict(kind='buy',name=n,slot=i,cost=cost,replaced=old,score=value))
        if S.C.CARDS[n].element!='generic':p.bought_elements.add(S.C.CARDS[n].element)
        p.decisions.append(f);S.maybe_specialize(p,r)
    return bought


def delete_phase(p,players,pool,model,r):
    for deleted in range(deletion_limit(r,p.economy)):
        fee=deletion_price(r,deleted,p.economy)
        if fee is None or p.points<fee or len(p.deck)<=8:break
        options=removal_options(p,model)
        if not options:break
        gain,index,f=options[0]
        if gain-fee*model.w['coin']<=.025:break
        n,t=p.deck.pop(index);pool.remove(t);p.points-=fee;p.deletes+=1;p.deletion_points+=fee
        f['coin']=-fee;p.decisions.append(f);p.actions.append(dict(kind='delete',name=n,cost=fee,score=gain-fee*model.w['coin']))


def metrics(p):
    m=BASE_METRICS(p);ns=S.names(p);route=route_of(ns);actual=ROUTE_ID.get(route)
    dice_matches={did:S.score_similarity(ns,list(S.TARGET_NAMES[did].elements())) for did in S.TARGETS}
    near=max(dice_matches,key=lambda d:dice_matches[d]['dice'])
    m['nearest_dice']=near;m['nearest_dice_score']=dice_matches[near]['dice']
    m['route_dice']=dice_matches[actual]['dice'] if actual else 0
    target=actual or p.target;main={n for n in S.TARGET_NAMES[target] if S.C.CARDS[n].element==S.TARGETS[target]['element']}
    m['main_recall']=len(main&set(ns))/max(1,len(main))
    m['route_main_recall']=m['main_recall'] if actual else 0
    m['foreign_count']=sum(S.C.CARDS[n].element not in ('generic',p.spec or S.TARGETS[p.target]['element']) for n in ns)
    return m


class Learner:
    def __init__(self):self.w=copy.deepcopy(PRIOR);self.updates=0

    def refresh_decision(self,p,players,r,rng,learn):
        ns=S.names(p);target=S.TARGET_NAMES[p.target];missing=[n for n in target if n not in ns]
        free_available=not p.free_used and bool(free_purchase_rarities(r,p.economy))
        if p.points<=1 and not free_available:return {},False
        minimum=min((price(p,n,self.w,players)[0] for n in missing if price(p,n,self.w,players)[0] is not None),default=99)
        if p.points-1<minimum and not free_available:return {},False
        estimate=.2+.7*len(missing)/len(target)+.15*(not route_of(ns) and r in (8,10,12))
        f=dict(refresh=estimate,coin=-1)
        score=dot(self.w,f)+(rng.gauss(0,.04) if learn else 0)
        return f,score>.025

    def update(self,p,battle_reward):
        did=reference(p);vec=vector(p,S.names(p),did)
        previous=getattr(p,'last_progress',dict(dice=0.,main=0.))
        dense=2*(vec['dice']-previous['dice'])+(vec['main']-previous['main'])
        reward=.65*battle_reward+.35*max(-1,min(1,dense))
        p.last_progress=vec
        advantage=max(-1,min(1,reward-p.average_reward));p.average_reward=.8*p.average_reward+.2*reward
        p.total_reward+=reward
        for f in p.decisions:
            norm=max(.1,math.sqrt(sum(v*v for v in f.values())))
            for k in self.w:self.w[k]+=.035*advantage*f.get(k,0)/norm
        for k in self.w:
            base=PRIOR[k];self.w[k]=max(base*.25,min(base*2,.999*self.w[k]+.001*base))
        self.updates+=1


def install():
    S.pick_target=pick_target;S.purchase_phase=purchase_phase;S.delete_phase=delete_phase;S.metrics=metrics
