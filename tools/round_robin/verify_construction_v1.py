"""Immutable rule hashes, odds hard caps, copies, actual economy and starters."""
import hashlib
import json
import math
from pathlib import Path
import shared_draft_pool as P
import simulate_shared_draft as S
from draft_economy import CURRENT,free_purchase_rarities,deletion_limit,deletion_price


def main():
    root=S.C.ROOT/'releases/deckbuilding-v1.0';manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest['sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name
    c=json.loads((root/'probabilities.json').read_text(encoding='utf-8'));P.assert_uniform_counts(c)
    assert P.CFG==c and sum(P.copies(card,c) for card in S.C.CARDS.values())==1060
    assert json.loads((S.C.ROOT/'docs/deckbuilding/construction-probabilities.json').read_text(encoding='utf-8'))==c
    e=json.loads((root/'economy.json').read_text(encoding='utf-8'));assert S.START==e['starter']
    for r in range(1,8):
        f=free_purchase_rarities(r,CURRENT)
        assert f==(('common',) if r<=3 else ('common','rare') if r<=6 else ())
        assert deletion_limit(r,CURRENT)==(0 if r<=3 else 1 if r<=6 else 2)
        if r>=4:assert deletion_price(r,0,CURRENT)==0
    for key,faces in c['rarities'].items():
        for face in faces:assert abs(sum(face)-1)<1e-9
    both=lambda r,k:1-(1-c['rarities'][str(r)][0][k])**8*(1-c['rarities'][str(r)][1][k])**8
    assert 1-(1-c['rarities']['2'][0][2])**8<=.2 and both(2,2)<=.5
    assert both(6,3)<=.1 and both(7,3)<=.2
    t=json.loads((root/'damage.json').read_text(encoding='utf-8'))['table']
    for start in range(1,73):
        rows=[t[str(r)] for r in range(start,start+9)]
        assert sum(m for m,n in rows)<100
        assert sum(m+math.floor(math.log(500)*n) for m,n in rows)>=100
    assert all(.8<=n<=6 for m,n in t.values())
    print(json.dumps(dict(status='passed',files=len(manifest['sha256']),pool=1060,epic2_both=both(2,2),legend6_both=both(6,3),legend7_both=both(7,3))))


if __name__=='__main__':main()
