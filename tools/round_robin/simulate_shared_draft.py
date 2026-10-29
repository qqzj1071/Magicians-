"""Four-player 12-round construction curriculum with online reward updates.

No elimination in this training curriculum: all four complete all twelve rounds.
This is not a finished tournament/elimination implementation.
"""
import argparse
import copy
import gzip
import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import cards as C
from learning_core import DRAW, SEARCH, SHUFFLE
from shared_draft_pool import Pool, CFG, RANK, ELEMENTS, SPECIAL
from shared_draft_combat import ENGINE as E, battle
from draft_economy import REVISED, LEGACY, free_purchase_rarity, purchase_price, deletion_limit, deletion_price,is_free_purchase,study_income

TARGETS=copy.deepcopy(C.DECKS)
IDS=list(TARGETS)
TARGET_NAMES={i:Counter(x['name'] for x in d['entries']) for i,d in TARGETS.items()}
START=['攻击强化','攻击强化','防御强化','防御强化','护盾','检索附魔','短促','重洗']
KEYS=['bias','value','cheap','element','target','draw','search','shuffle','specialize','route','counter','curve','size','fallback','save','refresh','delete']
PRIOR=dict(zip(KEYS,[.2,.55,.25,1.4,3.5,2,1.5,1.1,1.8,3.5,1.0,1.6,.6,1.2,.65,1.2,.8]))
UNSUPPORTED_ACTIONS=set()


def seed(*parts):return int.from_bytes(hashlib.sha256(':'.join(map(str,parts)).encode()).digest()[:8],'big')
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def dot(w,f):return sum(w[k]*f.get(k,0) for k in w)
def names(p):return [n for n,t in p.deck]
def score_similarity(a,b):
    a,b=Counter(a),Counter(b);overlap=sum((a&b).values());union=sum((a|b).values())
    return dict(jaccard=overlap/max(1,union),dice=2*overlap/max(1,sum(a.values())+sum(b.values())),
                precision=overlap/max(1,sum(a.values())),recall=overlap/max(1,sum(b.values())),overlap=overlap)


@dataclass
class Player:
    pid:int
    affinity:str
    deck:list=field(default_factory=lambda:[(n,None) for n in START])
    spec:str=''
    target:str=''
    spec_round:int=0
    bank:int=0
    points:int=0
    streak:int=0
    bought_elements:set=field(default_factory=set)
    decisions:list=field(default_factory=list)
    average_reward:float=0
    total_reward:float=0
    refreshes:int=0
    route_changes:int=0
    denied_generic:int=0
    purchases:int=0
    deletes:int=0
    economy:str=REVISED
    current_round:int=1
    free_used:bool=False
    free_purchases:int=0
    deletion_points:int=0
    actions:list=field(default_factory=list)


class Learner:
    def __init__(self):self.w=dict(PRIOR);self.updates=0
    def update(self,p,reward):
        advantage=max(-1,min(1,reward-p.average_reward))
        p.average_reward=.8*p.average_reward+.2*reward
        p.total_reward+=reward
        # Both sides update from the observed outcome. Contextual bandit credit
        # with shrinkage, not a claim of individual-card causal value.
        for f in p.decisions:
            norm=max(1,sum(v*v for v in f.values()))
            for k in self.w:
                self.w[k]+=.035*advantage*f.get(k,0)/math.sqrt(norm)
        for k in self.w:self.w[k]=max(.05,min(8,.998*self.w[k]+.002*PRIOR[k]))
        self.updates+=1


def pick_target(p,players,w):
    ns=names(p);hist=Counter(C.CARDS[n].element for n in ns if C.CARDS[n].element!='generic' and C.CARDS[n].kind!='specialization')
    current_route=next((n for n in ns if C.CARDS[n].kind=='route_legendary'),'')
    best=None
    for did,d in TARGETS.items():
        if p.spec and d['element']!=p.spec:continue
        overlap=sum(v*(1 if C.CARDS[n].element!='generic' else .2) for n,v in (Counter(ns)&TARGET_NAMES[did]).items())
        peers=sum(q.spec==d['element'] for q in players if q.pid!=p.pid)
        value=overlap*w['target']+hist[d['element']]*w['element']+3*(did==p.affinity)-.8*peers
        value+=2*w['route']*(current_route==d['route'])
        if best is None or value>best[0]:best=(value,did)
    p.target=best[1]


def features(p,n,players):
    c=C.CARDS[n];ns=names(p);d=TARGETS[p.target];element=p.spec or d['element']
    counts=Counter(C.CARDS[x].element for x in ns if C.CARDS[x].kind!='specialization')
    own=c.element==element;resources={k:len(set(ns)&s) for k,s in [('draw',DRAW),('search',SEARCH),('shuffle',SHUFFLE)]}
    avg=sum(C.CARDS[x].cost for x in ns)/len(ns)
    new_avg=(avg*len(ns)+c.cost)/(len(ns)+1)
    opponents=[q.spec for q in players if q.pid!=p.pid]
    text=c.text
    counter=(('穿透' in text)*opponents.count('earth')+('回复量降低' in text)*opponents.count('water')+('移除' in text or '净化' in text)*opponents.count('poison'))/3
    existing_route=next((x for x in ns if C.CARDS[x].kind=='route_legendary'),'')
    f=dict(bias=1,value=(c.attack+1.5*c.defense)/8,cheap=float(c.cost<=1),
           element=float(own),target=float(n in TARGET_NAMES[p.target]),
           draw=float(n in DRAW)*max(0,2-resources['draw']),search=float(n in SEARCH)*max(0,2-resources['search']),
           shuffle=float(n in SHUFFLE)*max(0,1-resources['shuffle']),
           specialize=float(not p.spec and own)*min(2,counts[element])/2,
           route=float(c.kind=='route_legendary')*(1 if not existing_route else float(n==d['route'])),
           counter=counter,curve=-max(0,new_avg-1.5),size=-max(0,len(ns)-22)/5,
           fallback=float(c.rarity=='legendary' and c.element=='generic' and n not in TARGET_NAMES[p.target]))
    if c.element!='generic' and not own:f['element']=-1.5
    return f


def price_and_replace(p,n,w,players):
    c=C.CARDS[n];ns=names(p)
    if n in ns or n in UNSUPPORTED_ACTIONS:return None,None
    if p.spec and c.element not in ('generic',p.spec):return None,None
    route=next((x for x in ns if C.CARDS[x].kind=='route_legendary'),None)
    legends=[x for x in ns if C.CARDS[x].rarity=='legendary']
    if c.kind=='route_legendary':
        # Before specializing a route would commit to a not-yet-active mechanic;
        # this agent declines those offers, not a card-pool rule restriction.
        if not p.spec:return None,None
        if route:return 2,route
    if c.rarity=='legendary' and len(legends)>=3:
        options=[x for x in legends if C.CARDS[x].kind!='route_legendary']
        if not options:return None,None
        replace_name=min(options,key=lambda x:dot(w,features(p,x,players)))
        if C.CARDS[replace_name].element!='generic':
            count=sum(C.CARDS[x].element==p.spec and C.CARDS[x].kind!='specialization' for x in ns)
            if count<=3 and c.element!=p.spec:return None,None
        return 4,replace_name
    base_price=RANK[c.rarity]+1
    return purchase_price(base_price,c.rarity,p.current_round,p.free_used,p.economy),None


def maybe_specialize(p,r):
    if p.spec:return
    counts=Counter(C.CARDS[n].element for n in names(p) if C.CARDS[n].element!='generic' and C.CARDS[n].kind!='specialization')
    eligible=[e for e,v in counts.items() if v>=3]
    if eligible:
        preferred=TARGETS[p.target]['element']
        p.spec=preferred if preferred in eligible else max(eligible,key=lambda e:counts[e])
        p.spec_round=r;p.deck.append((SPECIAL[p.spec],None))


def purchase_phase(p,players,pool,model,r,rng,learn):
    bought=set();board=pool.offers[p.pid]
    while True:
        pick_target(p,players,model.w)
        options=[]
        for i,t in enumerate(board):
            if not t:continue
            n=pool.tokens[t];cost,replacement=price_and_replace(p,n,model.w,players)
            if cost is None or cost>p.points:continue
            f=features(p,n,players);value=dot(model.w,f)
            if replacement:value-=.6*dot(model.w,features(p,replacement,players))
            # Price is a real opportunity cost, not merely battle mana.
            value=value/max(1,cost)**.65
            if learn:value+=rng.gauss(0,.35)
            options.append((value,i,n,cost,replacement,f))
        threshold=model.w['save']*(1 if p.points<=2 else .25)
        if not options or max(options)[0]<=threshold:break
        value,i,n,cost,replacement,f=max(options)
        if replacement:
            old=next(x for x in p.deck if x[0]==replacement);p.deck.remove(old);pool.remove(old[1])
            p.route_changes+=C.CARDS[n].kind=='route_legendary'
        token=pool.buy(p.pid,i);p.deck.append((n,token));p.points-=cost;p.purchases+=1;bought.add(i)
        if cost==0:
            assert is_free_purchase(C.CARDS[n].rarity,r,p.free_used,p.economy)
            p.free_used=True;p.free_purchases+=1
        p.actions.append(dict(kind='buy',name=n,slot=i,cost=cost,replaced=replacement))
        if C.CARDS[n].element!='generic':p.bought_elements.add(C.CARDS[n].element)
        p.decisions.append(f);maybe_specialize(p,r)
    return bought


def delete_phase(p,players,pool,model,r):
    for deleted in range(deletion_limit(r,p.economy)):
        fee=deletion_price(r,deleted,p.economy)
        if fee is None or p.points<fee:break
        if len(p.deck)<=8:break  # agent preference, not a formal deck-size rule
        options=[];ns=names(p)
        for index,(n,t) in enumerate(p.deck):
            c=C.CARDS[n]
            if c.kind=='specialization':continue
            if c.element==p.spec and sum(C.CARDS[x].element==p.spec and C.CARDS[x].kind!='specialization' for x in ns)<=3:continue
            f=features(p,n,players)
            unwanted=n not in TARGET_NAMES[p.target]
            duplicates=ns.count(n)>1
            value=unwanted*(1+len(ns)/12)+duplicates+max(0,c.cost-1.5)*model.w['curve']
            value-=float(n in TARGET_NAMES[p.target])*3
            value-=float(c.rarity=='legendary')*3
            # Do not delete the sole resource tool without a learned tradeoff.
            value-=sum(n in s and len(set(ns)&s)<=1 for s in (DRAW,SEARCH,SHUFFLE))*2
            options.append((value,index,dict(delete=value/5,size=max(0,len(ns)-18)/8,curve=max(0,c.cost-1.5))))
        if not options or max(options)[0]*model.w['delete']<1.5+fee*model.w['save']:break
        value,index,f=max(options);n,t=p.deck.pop(index);pool.remove(t);p.deletes+=1
        p.points-=fee;p.deletion_points+=fee;f['save']=-fee;p.decisions.append(f)
        p.actions.append(dict(kind='delete',name=n,cost=fee))


def metrics(p):
    ns=names(p);matches={did:score_similarity(ns,list(TARGET_NAMES[did].elements())) for did in IDS}
    nearest=max(matches,key=lambda d:matches[d]['jaccard'])
    actual_route=next((n for n in ns if C.CARDS[n].kind=='route_legendary'),'')
    actual_id=next((did for did,d in TARGETS.items() if d['route']==actual_route),None)
    return dict(pid=p.pid,affinity=p.affinity,target=p.target,spec=p.spec,spec_round=p.spec_round,
                route=actual_route,size=len(ns),average_cost=statistics.mean(C.CARDS[n].cost for n in ns),
                resources={k:len(set(ns)&s) for k,s in [('draw',DRAW),('search',SEARCH),('shuffle',SHUFFLE)]},
                nearest=nearest,similarity=matches[nearest],actual_route_similarity=matches.get(actual_id),
                original_affinity_similarity=matches[p.affinity],names=ns,
                refreshes=p.refreshes,purchases=p.purchases,deletes=p.deletes,route_changes=p.route_changes,
                denied_generic=p.denied_generic,free_purchases=p.free_purchases,deletion_points=p.deletion_points)


def simulate_episode(stage,index,model,learn=False,unlimited=False,noncompetitive=False,economy=REVISED,namespace='shared-draft-v2',config=None,total_rounds=12):
    rng=random.Random(seed(namespace,stage,index));pool=Pool(unlimited,noncompetitive,config)
    # Rotating affinity curriculum covers all 15 routes; no route/element is
    # forcibly assigned and every player still starts with identical 8 cards.
    ps=[Player(i,IDS[(index*4+i)%15],economy=economy) for i in range(4)]
    if hasattr(model,'on_episode_start'):model.on_episode_start(ps)
    records=[];combat_count=0
    for r in range(1,total_rounds+1):
        pool.begin()
        for p in ps:
            p.decisions=[];p.bought_elements=set();p.free_used=False;p.actions=[];p.current_round=r
            bonus=int(abs(p.streak)>0 and abs(p.streak)%3==0)
            p.points=study_income(r,economy)+p.bank+bonus
            p.round_income=p.points
            pick_target(p,ps,model.w)
        pairs=[[(0,1),(2,3)],[(0,2),(1,3)],[(0,3),(1,2)]][(r-1)%3]
        templates={face:{} for face in [0,1]}
        for face in [0,1]:
            for p in ps:
                trng=random.Random(seed(namespace,'templates',stage,index,r,p.pid,face))
                probs=CFG['rarities'][str(r) if r<8 else '8_plus'][face]
                ranks=trng.choices(range(4),probs,k=8)
                if face==0 and r in (8,10,12):ranks[:3]=[3]*3
                templates[face][p.pid]=ranks
        pool.generate(ps,templates[0],r,0,rng)
        first_tokens=copy.deepcopy(pool.offers)
        first={p.pid:[pool.tokens[t] if t else None for t in pool.offers[p.pid]] for p in ps}
        bought={p.pid:purchase_phase(p,ps,pool,model,r,rng,learn) for p in ps}
        second={};second_tokens={}
        for pid in [(r-1+i)%4 for i in range(4)]:
            p=ps[pid]
            if p.points<1 or len(bought[pid])==8:continue
            ns=names(p);missing=sum(n not in ns for n in TARGET_NAMES[p.target])
            f=dict(refresh=missing/20,save=-float(p.points<=2))
            if hasattr(model,'refresh_decision'):
                p.refresh_slots=8-len(bought[pid])
                f,should=model.refresh_decision(p,ps,r,rng,learn)
                if not should:continue
            elif dot(model.w,f)+(rng.gauss(0,.15) if learn else 0)<=0:continue
            pool.release(pid)
            pool.generate([p],templates[1],r,1,rng,bought)
            second_tokens[pid]=list(pool.offers[pid])
            p.points-=1;p.refreshes+=1;p.decisions.append(f)
            p.actions.append(dict(kind='refresh',cost=1))
            second[pid]=[pool.tokens[t] if t else None for t in pool.offers[pid]]
            purchase_phase(p,ps,pool,model,r,rng,learn)
        for p in ps:
            pick_target(p,ps,model.w)
            # Observe desired generic legends unavailable because of other owners.
            for n in TARGET_NAMES[p.target]:
                if C.CARDS[n].rarity=='legendary' and C.CARDS[n].element=='generic' and n not in names(p):
                    owners=[pool.owner[t] for t,name in pool.tokens.items() if name==n and t in pool.owner]
                    available_total=sum(name==n for name in pool.tokens.values())
                    p.denied_generic+=len(owners)>=available_total
            delete_phase(p,ps,pool,model,r)
            assert p.points==p.round_income-sum(a['cost'] for a in p.actions)
            assert p.points>=0
            assert sum(a['kind']=='delete' for a in p.actions)<=deletion_limit(r,p.economy)
            assert sum(a['kind']=='buy' and a['cost']==0 for a in p.actions)<=1
            p.bank=min(2,p.points)
            pool.audit(ps)
        snapshots=[metrics(p) for p in ps]
        for p in ps:
            did=f'draft-p{p.pid}'
            C.DECKS[did]=dict(id=did,element=p.spec or TARGETS[p.target]['element'],specialization_selected=bool(p.spec),
                             route=next((n for n in names(p) if C.CARDS[n].kind=='route_legendary'),''),
                             entries=[dict(name=n,quantity=1) for n in names(p)])
        battles=[]
        for a,b in pairs:
            battle_seed=seed(namespace,'battle',stage,index,r,a,b)
            if hasattr(model,'combat'):
                result=model.combat.fight(f'draft-p{a}',f'draft-p{b}',r,battle_seed,learn)
            else:result=battle(f'draft-p{a}',f'draft-p{b}',battle_seed,E.GREEDY,E.GREEDY)
            combat_count+=1
            winner=-1 if result['winner']=='draw' else a if result['winner']==f'draft-p{a}' else b
            for pid,other in [(a,b),(b,a)]:
                state=result['players'][f'draft-p{pid}'];enemy=result['players'][f'draft-p{other}']
                outcome=0 if winner<0 else 1 if winner==pid else -1
                margin=max(-1,min(1,(state['hp']-enemy['hp'])/1000))
                reward=.75*outcome+.25*margin
                if hasattr(model,'observe_result'):model.observe_result(ps[pid],reward)
                if winner<0:ps[pid].streak=0
                elif outcome>0:ps[pid].streak=max(0,ps[pid].streak)+1
                else:ps[pid].streak=min(0,ps[pid].streak)-1
                if learn:model.update(ps[pid],reward)
            battles.append(dict(a=a,b=b,winner=winner,time=result['time'],seed=result['seed'],players=result['players']))
        for p in ps:pool.release(p.pid)
        pool.audit(ps)
        records.append(dict(round=r,first=first,second=second,first_tokens=first_tokens,second_tokens=second_tokens,
                            templates=templates,players=snapshots,battles=battles,weights=dict(model.w),
                            points=[dict(pid=p.pid,income=p.round_income,remaining=p.points,bank=p.bank,streak=p.streak,actions=p.actions) for p in ps]))
        if hasattr(model,'round_diagnostics'):records[-1].update(model.round_diagnostics(ps,r))
    return dict(stage=stage,index=index,economy=economy,namespace=namespace,players=[metrics(p) for p in ps],rounds=records,
                elements=len({p.spec for p in ps if p.spec}),pool_stats=dict(pool.stats),combat_count=combat_count)


def copies_for_generic(unlimited):return 4 if unlimited else 2


def aggregate(episodes):
    players=[p for ep in episodes for p in ep['players']]
    js=[p['similarity']['jaccard'] for p in players]
    return dict(episodes=len(episodes),players=len(players),battles=sum(ep['combat_count'] for ep in episodes),
                jaccard_mean=statistics.mean(js),jaccard_max=max(js),jaccard_ge_80=sum(x>=.8 for x in js)/len(js),
                dice_mean=statistics.mean(p['similarity']['dice'] for p in players),
                actual_route_jaccard_mean=statistics.mean(p['actual_route_similarity']['jaccard'] if p['actual_route_similarity'] else 0 for p in players),
                spec_round_mean=statistics.mean(p['spec_round'] or 13 for p in players),
                unspecialized=sum(not p['spec'] for p in players),
                mean_distinct_elements=statistics.mean(ep['elements'] for ep in episodes),
                element_distribution=dict(Counter(p['spec'] for p in players)),
                actual_route_coverage=dict(Counter(p['route'] for p in players)),
                mean_size=statistics.mean(p['size'] for p in players),mean_cost=statistics.mean(p['average_cost'] for p in players),
                resource_means={k:statistics.mean(p['resources'][k] for p in players) for k in ['draw','search','shuffle']},
                generic_denial_player_rounds=sum(p['denied_generic'] for p in players),
                route_changes=sum(p['route_changes'] for p in players),
                mean_free_purchases=statistics.mean(p['free_purchases'] for p in players),
                mean_deletion_points=statistics.mean(p['deletion_points'] for p in players),
                mean_deletes=statistics.mean(p['deletes'] for p in players),
                pool_stats=dict(sum((Counter(ep['pool_stats']) for ep in episodes),Counter())))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--train',type=int,default=16);ap.add_argument('--eval',type=int,default=12)
    ap.add_argument('--run',default='shared-draft-v1');args=ap.parse_args()
    if not args.run.replace('-','').replace('_','').isalnum():raise ValueError('Invalid run name')
    out=C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError('Use a new run ID; completed research is never overwritten')
    out.mkdir(parents=True)
    save(out/'experiment.json',dict(train=args.train,evaluation=args.eval,starter=START,
         card_sha256=hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
         scope='Four remain active 12 rounds; no elimination, no ghost or event-health tuning',
         learning='online contextual-bandit feature weights; win/loss both update after each fight',
         unsupported_agent_actions=sorted(UNSUPPORTED_ACTIONS),
         source_hashes={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in
                        ['simulate_shared_draft.py','shared_draft_pool.py','shared_draft_combat.py','engine.py','construction_templates.py','draft_economy.py']},
         configuration_sha256=hashlib.sha256((C.ROOT/'docs/deckbuilding/construction-probabilities.json').read_bytes()).hexdigest(),
         economy=REVISED,seed_namespace=args.run,
         defaults='initial outside pool; specialization at 3; max 3 legends/1 route; growth-v2 free purchases/deletion fees; pending returns next round'))
    model=Learner();all_results={};t=time.time()
    stages=[('train',args.train,True,False,False),('learned',args.eval,False,False,False),
            ('prior',args.eval,False,False,False),('generic_four_copies',args.eval,False,True,False),
            ('noncompetitive_pool',args.eval,False,False,True),('old_economy',args.eval,False,False,False)]
    frozen=None
    with gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for stage,count,learn,unlimited,noncompetitive in stages:
            if stage=='learned':frozen=copy.deepcopy(model)
            active=Learner() if stage=='prior' else model if learn else copy.deepcopy(frozen)
            eps=[]
            for i in range(count):
                # Evaluation and controls share all named random streams.
                seed_stage='train' if learn else 'evaluation'
                ep=simulate_episode(seed_stage,i,active,learn,unlimited,noncompetitive,
                                    LEGACY if stage=='old_economy' else REVISED,args.run)
                ep['condition']=stage;eps.append(ep);raw.write(json.dumps(ep,ensure_ascii=False)+'\n');raw.flush()
                print(f'{stage} {i+1}/{count} meanJ={statistics.mean(p["similarity"]["jaccard"] for p in ep["players"]):.3f} elapsed={time.time()-t:.1f}s',flush=True)
            all_results[stage]=aggregate(eps)
            save(out/f'{stage}-summary.json',all_results[stage])
            save(out/f'{stage}-final-decks.json',[dict(episode=ep['index'],players=ep['players']) for ep in eps])
        save(out/'learned-weights.json',dict(prior=PRIOR,learned=frozen.w,updates=frozen.updates))
    save(out/'summary.json',dict(results=all_results,elapsed_seconds=time.time()-t,
         achieved_80_percent=all_results['learned']['jaccard_ge_80'],
         caveat='Nearest-target similarity is optimistic; actual-route similarity also reported. Controls use matched seeds but adaptive decisions change downstream pools.'))
    print(json.dumps(all_results,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
