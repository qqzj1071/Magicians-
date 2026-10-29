"""Replay money/free entitlement/deletion ledger against recorded deck states."""
import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import cards as C
from draft_economy import REVISED,LEGACY,free_purchase_rarity,deletion_limit,deletion_price
from simulate_shared_draft import START


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    out=C.ROOT/'research'/args.run
    exp=json.loads((out/'experiment.json').read_text(encoding='utf-8'))
    for name,digest in exp['source_hashes'].items():
        assert hashlib.sha256((out/'sources'/name).read_bytes()).hexdigest()==digest,name
    assert hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()==exp['card_sha256']
    assert hashlib.sha256((out/'construction-probabilities.json').read_bytes()).hexdigest()==exp['configuration_sha256']
    counts=Counter();fees=Counter()
    for file in ['episodes.jsonl.gz','balanced-affinity.jsonl.gz']:
        with gzip.open(out/file,'rt',encoding='utf-8') as f:
            for line in f:
                ep=json.loads(line);counts['episodes']+=1
                assert len(ep['rounds'])==12
                decks=[Counter(START) for _ in range(4)];banks=[0]*4;streaks=[0]*4
                for row in ep['rounds']:
                    r=row['round'];profile=ep['economy']
                    assert len(row['battles'])==2
                    assert sorted(v for b in row['battles'] for v in [b['a'],b['b']])==[0,1,2,3]
                    counts['battles']+=2
                    for point,p in zip(row['points'],row['players']):
                        pid=point['pid'];assert pid==p['pid']
                        base=2 if r<=2 else 3 if r<=5 else 4
                        bonus=int(abs(streaks[pid])>0 and abs(streaks[pid])%3==0)
                        assert point['income']==base+banks[pid]+bonus
                        money=point['income'];free_used=False;deleted=0;refreshes=0;deck=decks[pid]
                        for a in point['actions']:
                            fee=a['cost'];assert fee>=0
                            if a['kind']=='buy':
                                n=a['name'];c=C.CARDS[n];assert deck[n]==0
                                free=not free_used and c.rarity==free_purchase_rarity(r,profile)
                                expected=0 if free else {'common':1,'rare':2,'epic':3,'legendary':4}[c.rarity]
                                if a['replaced']:
                                    old=a['replaced'];assert deck[old]>0
                                    if c.kind=='route_legendary' and C.CARDS[old].kind=='route_legendary':expected=2
                                    deck[old]-=1
                                assert fee==expected,(r,n,fee,expected)
                                if free:free_used=True;fees['free_purchases']+=1
                                deck[n]+=1
                                # Auto specialization is a generated card, not a purchase.
                                spec=p['spec']
                                if spec:
                                    spec_name=next(n for n,c in C.CARDS.items() if c.element==spec and c.kind=='specialization')
                                    own=sum(q for n,q in deck.items() if C.CARDS[n].element==spec and C.CARDS[n].kind!='specialization')
                                    if own>=3 and not deck[spec_name]:deck[spec_name]=1
                            elif a['kind']=='delete':
                                assert fee==deletion_price(r,deleted,profile)
                                n=a['name'];assert deck[n]>0 and C.CARDS[n].kind!='specialization'
                                deck[n]-=1;deleted+=1;fees['deletion_points']+=fee
                            elif a['kind']=='refresh':assert fee==1;refreshes+=1
                            else:raise AssertionError(a)
                            money-=fee;assert money>=0
                        assert deleted<=deletion_limit(r,profile) and refreshes<=1
                        assert money==point['remaining'] and point['bank']==min(2,money)
                        assert +deck==Counter(p['names']),(r,pid)
                        banks[pid]=point['bank'];streaks[pid]=point['streak']
                        counts['player_round_ledgers']+=1
    result=dict(status='passed',counts=dict(counts),fees=dict(fees),
                card_and_source_and_config_hashes=True,point_balance=True,free_entitlement=True,
                deletion_schedule=True,deck_reconstructed=True)
    (out/'economy-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
