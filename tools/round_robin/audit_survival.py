"""Independent replay of ledgers, public events, pairing and tournament damage."""
import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
import survival_tournament as Q
from draft_economy import PREVIOUS,is_free_purchase,purchase_price,deletion_price,deletion_limit,study_income
from shared_draft_pool import copies,assert_uniform_counts
S=Q.S


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--partial',action='store_true');args=ap.parse_args()
    out=S.C.ROOT/'research'/args.run;read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
    exp=read('experiment.json');cfg=read('config.json');assert_uniform_counts(cfg)
    for name,h in exp['source_hashes'].items():assert hashlib.sha256((out/'sources'/name).read_bytes()).hexdigest()==h,name
    assert hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()==exp['card_sha256']
    tokens={f'{n}#{i}':n for n,c in S.C.CARDS.items() for i in range(copies(c,cfg))};counts=Counter();final=[]
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        while True:
            try:line=f.readline()
            except EOFError:
                if args.partial:break
                raise
            if not line:break
            ep=json.loads(line);profile=ep.get('economy',PREVIOUS);counts['rooms']+=1;alive=set(range(4));hp={i:100 for i in alive};streak=Counter();banks=Counter()
            decks={i:Counter(S.START) for i in alive};owned={};previous={};public={str(i):dict(spec='',route='') for i in alive}
            last_seq=0;archive={};last_table=(0,0);coefs=[]
            for row in ep['rounds']:
                r=row['round'];m,n=row['parameters'];assert isinstance(m,int) and m>=last_table[0] and n>=last_table[1]
                assert abs(n*10-round(n*10))<1e-8;last_table=m,n
                coefs.append((m,n))
                if 'alive14' in exp.get('targets',{}) and len(coefs)>=9:
                    assert sum(a for a,b in coefs[-9:])<100
                    assert sum(a+math.floor(math.log(500)*b) for a,b in coefs[-9:])>=100
                assert {p['pid'] for p in row['players']}==alive
                announced=row['announced_pairs'];appear=[v for p in announced for v in (p['a'],p['b']) if isinstance(v,int)]
                assert sorted(appear)==sorted(alive)
                if len(alive)==4:
                    assert all(previous.get(p['a'])!=p['b'] for p in announced)
                elif len(alive)==3:
                    assert sum(p['ghost'] for p in announced)==1
                    assert all(previous.get(p['a'])!=p['b'] for p in announced)
                for pair in announced:
                    a,b=pair['a'],pair['b'];previous[a]=b;previous[b]=a
                    if pair['ghost']:assert int(b[1:]) in archive
                # Check actual face allocation and global legendary reservation.
                legends=set();per_player={p:set() for p in alive};round_offer={};round_pending=set()
                for face in ('first','second'):
                    allocation=row[face+'_tokens'];flat=[t for xs in allocation.values() for t in xs if t]
                    assert len(flat)==len(set(flat))
                    for pid,xs in allocation.items():
                        pid=int(pid);assert pid in alive
                        for t in xs:
                            if not t:continue
                            assert t in tokens and t not in owned
                            name=tokens[t]
                            if S.C.CARDS[name].rarity=='legendary':
                                assert t not in legends and name not in per_player[pid]
                                legends.add(t);per_player[pid].add(name)
                            round_offer[(face,pid,t)]=name
                # Replay all buy/delete transitions, then automatic specialization.
                for ledger in row['ledger']:
                    pid=ledger['pid'];assert ledger['previous_streak']==streak[pid]
                    bonus=int(abs(streak[pid])>0 and abs(streak[pid])%3==0)
                    assert ledger['bonus']==bonus
                    points=study_income(r,profile)+banks[pid]+bonus
                    assert ledger['income']==points;free=False;deleted=0;refreshed=False;deck=decks[pid]
                    for action in ledger['actions']:
                        kind=action['kind'];cost=action['cost']
                        if kind=='refresh':assert not refreshed and cost==1;refreshed=True
                        elif kind=='delete':
                            name=action['name'];assert deck[name]>0 and cost==deletion_price(r,deleted,profile)
                            assert S.C.CARDS[name].kind not in ('specialization','route_legendary')
                            deck[name]-=1;deleted+=1
                            found=next((t for t,p in owned.items() if p==pid and tokens[t]==name),None)
                            if found:del owned[found];round_pending.add(found)
                        else:
                            assert kind=='buy';name=action['name'];c=S.C.CARDS[name];assert deck[name]==0
                            old=action.get('replaced');price=2 if old and c.kind=='route_legendary' else purchase_price(S.RANK[c.rarity]+1,c.rarity,r,free,profile)
                            assert cost==price
                            if old:
                                assert deck[old]>0;deck[old]-=1
                                found=next(t for t,p in owned.items() if p==pid and tokens[t]==old)
                                del owned[found];round_pending.add(found)
                            if cost==0:assert is_free_purchase(c.rarity,r,free,profile);free=True
                            face='second' if refreshed else 'first';t=row[face+'_tokens'][str(pid)][action['slot']]
                            assert round_offer[(face,pid,t)]==name and t not in owned and t not in round_pending
                            owned[t]=pid;deck[name]+=1;counts['purchases']+=1
                        points-=cost;assert points>=0
                    assert deleted<=deletion_limit(r,profile) and points==ledger['remaining']
                    assert ledger['bank']==min(2,points);banks[pid]=ledger['bank'];counts['bonus_points']+=bonus
                    current=next(p for p in row['players'] if p['pid']==pid)
                    if current['spec']:
                        spec=S.SPECIAL[current['spec']];deck[spec]=1
                    assert +deck==Counter(current['names'])
                for e in row['broadcasts']:
                    assert e['seq']==last_seq+1;last_seq=e['seq']
                    assert sorted(e['receivers'])==sorted(alive)
                    assert public[str(e['pid'])][e['kind']]==e['previous']
                    public[str(e['pid'])][e['kind']]=e['value'];counts['broadcasts']+=1;counts['retargets']+=len(e['retargets'])
                assert public==row['public_state']['players']
                assert len(row['battles'])==len(announced)
                for pair,battle in zip(announced,row['battles']):
                    assert all(pair[k]==battle[k] for k in ('a','b','ghost'))
                    result=battle['result'];a,b=battle['a'],battle['b'];counts['battles']+=1
                    if battle['ghost']:counts['ghost_battles']+=1
                    for pid,enemy in [(a,'ghost' if battle['ghost'] else 'survivor-'+str(b))]+([] if battle['ghost'] else [(b,'survivor-'+str(a))]):
                        own='survivor-'+str(pid);draw=result['winner']=='draw';win=result['winner']==own
                        loss=0 if win else m if draw else m+math.floor(math.log(max(result['players'][enemy]['hp'],1))*n)
                        assert row['hp_before'][str(pid)]==hp[pid]
                        hp[pid]-=loss;streak[pid]=0 if draw else max(0,streak[pid])+1 if win else min(0,streak[pid])-1
                        actual=row['settlement'][str(pid)]
                        assert actual['loss']==loss and actual['hp']==hp[pid] and actual['streak']==streak[pid]
                eliminated={p['pid'] for p in row['eliminated']}
                assert eliminated=={pid for pid in alive if hp[pid]<=0}
                for p in row['eliminated']:
                    pid=p['pid'];archive[pid]=p;public[str(pid)]=dict(spec='',route='')
                    owned={t:owner for t,owner in owned.items() if owner!=pid}
                alive-=eliminated;assert set(row['remaining'])==alive
                counts['player_rounds']+=len(row['players'])
            assert len(alive)<=1 and len(ep['rounds'])==ep['end_round']
            assert {p['pid'] for p in ep['champions']}==(alive or {p['pid'] for p in ep['rounds'][-1]['eliminated']})
            if ep['label']=='sealed-final':final.append(ep)
    if args.partial:
        print(json.dumps(dict(status='partial_replay_passed',counts=counts)));return
    summary=Q.summarize(final);normalized=json.loads(json.dumps(summary));stored=read('summary.json')['final']
    assert all(stored[k]==v for k,v in normalized.items())
    matrix=read('champion-matrix.json') if (out/'champion-matrix.json').exists() else dict(rows=[])
    rows=matrix['rows'];keys=Counter()
    for x in rows:keys[(x['room'],x['pid'],x['opponent'],x['flip'],x['seed'])]+=1
    assert all(v==3 for v in keys.values())
    if rows:assert len(rows)==sum(len(e['champions']) for e in final)*15*2*3
    else:assert exp.get('training_updates')==0
    if (out/'history.json').exists():
        history=read('history.json');previous=read('initial-model.json')
        for h in history:
            phase=h['phase'];new=h['benchmark_after'];old=h['benchmark_before']
            assert h['draft_accepted']==(new['old_combat']>=old['old_combat'] and h['after']['spec_by5']>=max(.75,h['before']['spec_by5']-.1))
            assert h['combat_accepted']==(new['candidate']>=new['old_combat'])
            chosen=read(f'phase{phase}-model.json')
            if not h['draft_accepted']:assert chosen['draft']==previous['draft']
            if not h['combat_accepted']:assert chosen['combat']==previous['combat']
            previous=chosen
    S.save(out/'audit.json',dict(status='passed',counts=counts,final=summary,matrix_games=len(rows),
        scope='source hashes, card freeze, uniform copies, face reservations, purchases, money, bonus, elimination, HP, ghosts, scheduling, broadcasts, terminal champions, paired matrix'))
    print(json.dumps(dict(status='passed',counts=counts,matrix_games=len(rows))))


if __name__=='__main__':main()
