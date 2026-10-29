"""Actual shared-pool tournaments, survival damage, public scheduling and ghosts."""
import copy
import itertools
import math
import random
from collections import Counter
import tournament_draft as A
from draft_economy import CURRENT,deletion_limit
T=A.T;S=T.S


def validate_table(table):
    previous=(0,0.)
    for r in range(1,len(table)+1):
        m,n=table[str(r)];assert isinstance(m,int) and m>=1
        assert n>=0 and abs(n*10-round(n*10))<1e-8
        assert m>=previous[0] and n>=previous[1];previous=m,n


def parameters(table,r):
    if str(r) in table:return table[str(r)]
    m,n=table[str(len(table))]
    return m+5*(r-len(table)),round(n+.1*(r-len(table)),1)


def damage(m,n,x,draw=False):
    return m if draw else m+math.floor(math.log(max(x,1))*n)


def schedule(players,dead,last,meetings,rng):
    ids=[p.pid for p in players]
    if len(ids)==4:
        a,b,c,d=ids;options=[[(a,b),(c,d)],[(a,c),(b,d)],[(a,d),(b,c)]]
    elif len(ids)==3:
        options=[]
        for ghost_player in ids:
            others=[p for p in ids if p!=ghost_player]
            for ghost in dead:options.append([(others[0],others[1]),(ghost_player,'g'+str(ghost['pid']))])
    elif len(ids)==2:options=[[(ids[0],ids[1])]]
    else:return []
    def value(pairs):
        repeats=sum(last.get(a)==b or last.get(b)==a for a,b in pairs)
        return repeats,sum(meetings[tuple(sorted((str(a),str(b))))] for a,b in pairs),rng.random()
    selected=min(options,key=value)
    for a,b in selected:
        last[a]=b;last[b]=a;meetings[tuple(sorted((str(a),str(b))))]+=1
    return selected


def deck(snapshot,did):
    S.C.DECKS[did]=dict(id=did,element=snapshot['spec'] or S.TARGETS[snapshot['target']]['element'],
        specialization_selected=bool(snapshot['spec']),route=snapshot['route'],
        entries=[dict(name=n,quantity=1) for n in snapshot['names']])


def snapshot(p):
    result=T.A.metrics(p);result.update(tournament_hp=p.tournament_hp,streak=p.streak,bank=p.bank)
    return result


def simulate(label,index,model,table,config,learn=False,namespace='survival-v6',raw_sink=None,seat_models=None):
    validate_table(table)
    seed_label=label.replace('-before','-validation').replace('-after','-validation')
    rng=random.Random(S.seed(namespace,seed_label,index));pool=S.Pool(config=config)
    players=[S.Player(i,S.IDS[(index*4+i)%15],economy=CURRENT) for i in range(4)]
    for p in players:p.tournament_hp=100;p.next_public={};p.ghost_public=None;p.loss_estimate=8
    all_players=list(players);model.on_episode_start(players)
    actors={p.pid:(seat_models[p.pid] if seat_models else model) for p in players}
    if seat_models:
        assert not learn,'Mixed-policy tests must not learn'
        for actor in actors.values():actor.public=model.public;actor.events=model.events
    for p in players:p.actor_weights=actors[p.pid].w
    dead=[];last={};meetings=Counter();records=[];r=0;battles_count=0
    while len(players)>1:
        r+=1
        if r>80:raise RuntimeError('Tournament failed to terminate; no artificial champion')
        pool.begin();pairs=schedule(players,dead,last,meetings,rng);byid={p.pid:p for p in players}
        archives={v['pid']:v for v in dead};m,n=parameters(table,r)
        for a,b in pairs:
            if isinstance(b,str):
                ghost=archives[int(b[1:])];byid[a].next_pid=b
                byid[a].ghost_public={k:ghost[k] for k in ('spec','route')}
            else:
                byid[a].next_pid=b;byid[b].next_pid=a;byid[a].ghost_public=None;byid[b].ghost_public=None
        A.sync_opponents(players,model)
        for p in players:
            p.current_round=r;p.decisions=[];p.bought_elements=set();p.free_used=False;p.actions=[];p.explanations=[]
            p.loss_estimate=damage(m,n,500);bonus=int(abs(p.streak)>0 and abs(p.streak)%3==0)
            p.points=(2 if r<=2 else 3 if r<=5 else 4)+p.bank+bonus;p.round_income=p.points;p.round_bonus=bonus
            A.pick_target(p,players,actors[p.pid].w)
        announced=[dict(a=a,b=b,ghost=isinstance(b,str)) for a,b in pairs]
        templates={face:{} for face in (0,1)}
        for face in (0,1):
            for p in players:
                trng=random.Random(S.seed(namespace,'templates',seed_label,index,r,p.pid,face))
                probs=S.CFG['rarities'][str(r) if r<8 else '8_plus'][face]
                ranks=trng.choices(range(4),probs,k=8)
                if face==0 and r in (8,10,12):ranks[:3]=[3]*3
                templates[face][p.pid]=ranks
        pool.generate(players,templates[0],r,0,rng)
        first_tokens=copy.deepcopy(pool.offers);first={p.pid:[pool.tokens[t] if t else None for t in pool.offers[p.pid]] for p in players}
        bought={p.pid:A.purchase(p,players,pool,actors[p.pid],r,rng,learn) for p in players};second={};second_tokens={}
        for pid in [(r-1+i)%4 for i in range(4)]:
            if pid not in byid:continue
            p=byid[pid]
            if p.points<1 or len(bought[pid])==8:continue
            p.refresh_slots=8-len(bought[pid]);f,should=actors[pid].refresh_decision(p,players,r,rng,learn)
            if not should:continue
            pool.release(pid);pool.generate([p],templates[1],r,1,rng,bought)
            second_tokens[pid]=list(pool.offers[pid]);second[pid]=[pool.tokens[t] if t else None for t in pool.offers[pid]]
            p.points-=1;p.refreshes+=1;p.decisions.append(f);p.actions.append(dict(kind='refresh',cost=1))
            A.purchase(p,players,pool,actors[pid],r,rng,learn)
        ledger=[]
        for p in players:
            A.delete(p,players,pool,actors[p.pid],r);p.bank=min(2,p.points)
            if hasattr(actors[p.pid],'close_shop'):actors[p.pid].close_shop(p)
            assert p.points==p.round_income-sum(a['cost'] for a in p.actions) and p.points>=0
            assert sum(a['kind']=='delete' for a in p.actions)<=deletion_limit(r,CURRENT)
            pool.audit(players)
            ledger.append(dict(pid=p.pid,income=p.round_income,bonus=p.round_bonus,remaining=p.points,bank=p.bank,
                               previous_streak=p.streak,actions=copy.deepcopy(p.actions),next_public=p.next_public,
                               decision_reasons=copy.deepcopy(p.explanations)))
        before=[snapshot(p) for p in players]
        for p in before:deck(p,'survivor-'+str(p['pid']))
        hp_before={p.pid:p.tournament_hp for p in players};battles=[];settlement={}
        for a,b in pairs:
            aid='survivor-'+str(a);ghost=isinstance(b,str)
            if ghost:deck(archives[int(b[1:])],'ghost');bid='ghost'
            else:bid='survivor-'+str(b)
            battle_seed=S.seed(namespace,'battle',seed_label,index,r,a,b)
            if seat_models:
                ca=actors[a].combat;cb=actors[b].combat if not ghost else model.combat
                result=ca.play(aid,bid,battle_seed,ca.policy(aid,bid,r),cb.policy(bid,aid,r))
            else:result=model.combat.fight(aid,bid,r,battle_seed,learn)
            battles_count+=1
            winner=result['winner'];draw=winner=='draw'
            both=[(a,aid,bid)]+([] if ghost else [(b,bid,aid)])
            for pid,own,enemy in both:
                p=byid[pid];won=winner==own;outcome=0 if draw else 1 if won else -1
                loss=0 if won else damage(m,n,result['players'][enemy]['hp'],draw)
                p.tournament_hp-=loss
                p.streak=0 if draw else max(0,p.streak)+1 if won else min(0,p.streak)-1
                # One bonus point has bounded utility; health loss dominates at
                # low HP. Deliberate losing is permitted, never rewarded for free.
                milestone=int(abs(p.streak)>0 and abs(p.streak)%3==0)
                margin=max(-1,min(1,(result['players'][own]['hp']-result['players'][enemy]['hp'])/1000))
                reward=.65*outcome+.1*margin-.6*loss/max(15,hp_before[pid])+.04*milestone
                if p.tournament_hp<=0:reward-=.5
                if learn:model.update(p,reward)
                settlement[pid]=dict(loss=loss,hp=p.tournament_hp,streak=p.streak,reward=reward)
            battles.append(dict(a=a,b=b,ghost=ghost,result=result))
        for p in players:pool.release(p.pid)
        eliminated=[p for p in players if p.tournament_hp<=0];diagnostics=model.round_diagnostics(players,r)
        eliminated_snapshots=[]
        for p in eliminated:
            saved=snapshot(p);saved['eliminated_round']=r;dead.append(saved);eliminated_snapshots.append(saved)
            for _,token in p.deck:pool.remove(token)
            prior=model.public['players'][str(p.pid)]
            if prior['route']:model.public['release_round'][prior['route']]=r+1
            model.public['players'][str(p.pid)]=dict(spec='',route='')
        players=[p for p in players if p.tournament_hp>0];pool.audit(players)
        records.append(dict(round=r,parameters=[m,n],announced_pairs=announced,players=before,first=first,second=second,
            first_tokens=first_tokens,second_tokens=second_tokens,templates=templates,ledger=ledger,battles=battles,
            hp_before=hp_before,settlement=settlement,eliminated=eliminated_snapshots,
            remaining=[p.pid for p in players],weights=copy.deepcopy(model.w),**diagnostics))
        if raw_sink:raw_sink(records[-1])
    # If all remaining contenders die on the same round, user approved co-champions.
    champions=[snapshot(p) for p in players] if players else records[-1]['eliminated']
    if learn and hasattr(model,'finish_episode'):model.finish_episode(all_players,champions,r)
    return dict(label=label,index=index,rounds=records,end_round=r,champions=champions,
        tied=not players,eliminated=dead,battles=battles_count,pool_stats=dict(pool.stats))


def summarize(eps):
    def hp_at(ep,r):
        hp={i:0 for i in range(4)}
        for row in ep['rounds'][:r]:
            for pid,x in row['settlement'].items():hp[int(pid)]=max(0,x['hp'])
        return list(hp.values())
    n=len(eps);strong=sum(sum(x>40 for x in hp_at(e,12)) for e in eps)/(4*n)
    alive=sum(sum(x>0 for x in hp_at(e,15)) for e in eps)/(4*n)
    final=[p for e in eps for p in e['champions']]
    all_players=[p for e in eps for p in e['eliminated'] if p['eliminated_round']<=e['end_round']]
    for e in eps:
        if not e['tied']:all_players+=e['champions']
    return dict(rooms=n,strong12=strong,alive15=alive,ended18=sum(e['end_round']<=18 for e in eps)/n,
        mean_end=sum(e['end_round'] for e in eps)/n,max_end=max(e['end_round'] for e in eps),
        tied=sum(e['tied'] for e in eps),battles=sum(e['battles'] for e in eps),
        spec_by5=sum(bool(p['spec_round']) and p['spec_round']<=5 for p in all_players)/len(all_players),
        spec_by6=sum(bool(p['spec_round']) and p['spec_round']<=6 for p in all_players)/len(all_players),
        champion_size=sum(p['size'] for p in final)/len(final),champion_dice=sum(p['route_dice'] for p in final)/len(final),
        end_histogram=dict(Counter(e['end_round'] for e in eps)),
        mean_elements=sum(len({p['spec'] for p in [*e['eliminated'],*e['champions']] if p['spec']}) for e in eps)/n)
