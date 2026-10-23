"""Independent physical-copy, money, offer and actual-route Dice replay."""
import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
import cards as C
from draft_economy import CURRENT,is_free_purchase,deletion_limit,deletion_price
from shared_draft_pool import copies

START=['攻击强化','攻击强化','防御强化','防御强化','护盾','检索附魔','短促','重洗']
SPECIAL={c.element:n for n,c in C.CARDS.items() if c.kind=='specialization'}
RANK={'common':0,'rare':1,'epic':2,'legendary':3}


def digest(c):return hashlib.sha256(json.dumps(c,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    out=C.ROOT/'research'/args.run;exp=json.loads((out/'experiment.json').read_text(encoding='utf-8'))
    for n,h in exp['source_hashes'].items():assert hashlib.sha256((out/'sources'/n).read_bytes()).hexdigest()==h,n
    assert hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()==exp['card_sha256']
    configs={}
    for file in out.glob('*config.json'):
        cfg=json.loads(file.read_text(encoding='utf-8'));configs[digest(cfg)]=cfg
    baseline=json.loads((out/'phase1-previous-config.json').read_text(encoding='utf-8'))
    fixed=['rarities','legendary_copy_counts','legendary_types','first_face_legendary_guarantees','second_face_legendary_guarantees','hard_caps']
    for cfg in configs.values():
        assert all(cfg[k]==baseline[k] for k in fixed)
        for n in cfg.get('card_copy_overrides',{}):assert C.CARDS[n].rarity in ('common','rare','epic')
        for card in C.CARDS.values():
            if card.rarity=='legendary':assert copies(card,cfg)==copies(card,baseline)
            elif card.rarity!='specialization':assert -1<=copies(card,cfg)-copies(card,baseline)<=2
    references=json.loads((out/'reference-decks.json').read_text(encoding='utf-8'))
    by_route={d['route']:Counter(x['name'] for x in d['entries']) for d in references}
    counts=Counter();observed=Counter();fees=Counter()
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as raw:
        for line in raw:
            ep=json.loads(line);cfg=configs[ep['config_hash']];assert ep['economy']==CURRENT
            counts['episodes']+=1;counts['training_updates']+=56 if ep['condition'].endswith('-train') else 0
            universe={f'{n}#{i}':n for n,c in C.CARDS.items() for i in range(copies(c,cfg))}
            free=set(universe);owned={};pending=set();decks=[Counter(START) for _ in range(4)]
            selected=['']*4;banks=[0]*4;streaks=[0]*4
            assert len(ep['rounds'])==14
            for row in ep['rounds']:
                r=row['round'];free|=pending;pending=set();seen=set();seen_names=[set() for _ in range(4)]
                boards={};bought=[set() for _ in range(4)];money=[];free_used=[False]*4
                for pid,point in enumerate(row['points']):
                    bonus=int(abs(streaks[pid])>0 and abs(streaks[pid])%3==0)
                    income=(2 if r<=2 else 3 if r<=5 else 4)+banks[pid]+bonus
                    assert income==point['income'];money.append(income)

                def receive(pid,board,face):
                    active=[i for i in range(8) if i not in bought[pid]]
                    ranks=row['templates'][str(face)][str(pid)]
                    lowest=min((ranks[i] for i in active),default=3)
                    before_spec=selected[pid];elements=[];local=set()
                    for i,t in enumerate(board):
                        if i in bought[pid]:assert t is None
                        if not t:continue
                        assert t in free and t not in local,(ep['condition'],r,pid,t)
                        local.add(t);n=universe[t];c=C.CARDS[n]
                        assert decks[pid][n]==0
                        if before_spec:assert c.element in ('generic',before_spec)
                        elif c.element!='generic':elements.append(c.element)
                        assert RANK[c.rarity]<=ranks[i] or face==1 and r in (8,10,12) and ranks[i]==lowest
                        if c.rarity=='legendary':
                            assert t not in seen and n not in seen_names[pid]
                            seen.add(t);seen_names[pid].add(n)
                        if before_spec:
                            observed['post_slots']+=1;observed['post_main']+=c.element==before_spec
                        else:
                            observed['pre_slots']+=1;observed['pre_enchantment']+=c.element!='generic'
                    assert len([universe[t] for t in local])==len(set(universe[t] for t in local))
                    if not before_spec:assert len(elements)==len(set(elements))
                    free.difference_update(local);boards[pid]=list(board);counts['offered_copies']+=len(local)

                def buy(pid,a):
                    i=a['slot'];t=boards[pid][i];assert t and universe[t]==a['name'];n=a['name'];c=C.CARDS[n]
                    assert decks[pid][n]==0
                    if selected[pid]:assert c.element in ('generic',selected[pid])
                    free_buy=is_free_purchase(c.rarity,r,free_used[pid],CURRENT)
                    fee=0 if free_buy else RANK[c.rarity]+1
                    old=a.get('replaced')
                    if old:
                        assert decks[pid][old]>0
                        if c.kind=='route_legendary' and C.CARDS[old].kind=='route_legendary':fee=2
                        old_token=next(t for t,p in owned.items() if p==pid and universe[t]==old)
                        del owned[old_token];pending.add(old_token);decks[pid][old]-=1
                    assert fee==a['cost'];money[pid]-=fee;assert money[pid]>=0
                    if free_buy:free_used[pid]=True;fees['free_purchases']+=1
                    boards[pid][i]=None;owned[t]=pid;decks[pid][n]+=1;bought[pid].add(i)
                    if not selected[pid]:
                        histogram=Counter()
                        for name,q in decks[pid].items():
                            if C.CARDS[name].element!='generic' and C.CARDS[name].kind!='specialization':histogram[C.CARDS[name].element]+=q
                        eligible=[e for e,v in histogram.items() if v>=3]
                        if eligible:
                            assert row['players'][pid]['spec'] in eligible
                            selected[pid]=row['players'][pid]['spec'];decks[pid][SPECIAL[selected[pid]]]+=1
                    assert sum(q for n,q in decks[pid].items() if C.CARDS[n].rarity=='legendary')<=3
                    assert sum(q for n,q in decks[pid].items() if C.CARDS[n].kind=='route_legendary')<=1
                    counts['purchases']+=1

                phases=[]
                for point in row['points']:
                    phase=0;first=[];second=[];deletes=[];refresh=False
                    for a in point['actions']:
                        if a['kind']=='refresh':assert not refresh;refresh=True;phase=1
                        elif a['kind']=='delete':deletes.append(a)
                        elif a['kind']=='buy':(first if phase==0 else second).append(a)
                        else:raise AssertionError(a)
                    phases.append((first,second,deletes,refresh))
                for pid in range(4):receive(pid,row['first_tokens'][str(pid)],0)
                for pid in range(4):
                    for a in phases[pid][0]:buy(pid,a)
                for pid in [(r-1+i)%4 for i in range(4)]:
                    if not phases[pid][3]:continue
                    assert money[pid]>=1 and len(bought[pid])<8
                    money[pid]-=1;fees['refresh_points']+=1
                    free.update(t for t in boards[pid] if t)
                    receive(pid,row['second_tokens'][str(pid)],1)
                    for a in phases[pid][1]:buy(pid,a)
                for pid in range(4):
                    deletes=phases[pid][2];assert len(deletes)<=deletion_limit(r,CURRENT)
                    for index,a in enumerate(deletes):
                        assert a['cost']==deletion_price(r,index,CURRENT)
                        money[pid]-=a['cost'];assert money[pid]>=0;fees['delete_points']+=a['cost']
                        n=a['name'];assert decks[pid][n]>0 and C.CARDS[n].kind!='specialization'
                        candidates=[t for t,p in owned.items() if p==pid and universe[t]==n]
                        if candidates:t=candidates[0];del owned[t];pending.add(t)
                        decks[pid][n]-=1;counts['deletions']+=1
                    p=row['players'][pid];point=row['points'][pid]
                    assert +decks[pid]==Counter(p['names']) and selected[pid]==p['spec']
                    if selected[pid]:assert sum(q for n,q in decks[pid].items() if C.CARDS[n].element==selected[pid] and C.CARDS[n].kind!='specialization')>=3
                    assert money[pid]==point['remaining'] and point['bank']==min(2,money[pid])
                    banks[pid]=point['bank'];streaks[pid]=point['streak']
                    route=p['route'];expected=0;main_recall=0
                    if route:
                        target=by_route[route];expected=2*sum((decks[pid]&target).values())/(sum(decks[pid].values())+sum(target.values()))
                        main={n for n in target if C.CARDS[n].element==selected[pid]}
                        main_recall=sum(decks[pid][n]>0 for n in main)/len(main)
                    assert abs(p['route_dice']-expected)<1e-10 and abs(p['route_main_recall']-main_recall)<1e-10
                    free.update(t for t in boards[pid] if t);counts['player_rounds']+=1
                assert len(free)+len(owned)+len(pending)==len(universe)
                assert not(free&set(owned) or free&pending or set(owned)&pending)
                assert sorted(v for b in row['battles'] for v in (b['a'],b['b']))==[0,1,2,3]
                counts['course_battles']+=2
    result=dict(status='passed',counts=dict(counts),fees=dict(fees),observed=dict(observed),
                actual_post_main_share=observed['post_main']/max(1,observed['post_slots']),
                source_and_card_hashes=True,legendary_and_rarity_unchanged=True,
                physical_inventory_replayed=True,entitlements_and_money_replayed=True,actual_route_dice_recomputed=True)
    (out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
