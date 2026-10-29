import copy
import json
import random
from collections import Counter
import survival_tournament as Q
A=Q.A;S=Q.S


def main():
    assert Q.damage(3,.8,0)==3 and Q.damage(3,.8,100)==6
    assert Q.damage(3,.8,100,True)==3
    table={str(r):[1,0.] for r in range(1,13)}
    table.update({str(r):[15+(r-13)*10,1.] for r in range(13,19)})
    Q.validate_table(table)
    ps=[S.Player(i,'water-01') for i in range(4)];last={};counts=Counter();rng=random.Random(1)
    first=Q.schedule(ps,[],last,counts,rng);second=Q.schedule(ps,[],last,counts,rng)
    assert not ({frozenset(p) for p in first}&{frozenset(p) for p in second})
    ghosts=[dict(pid=3)]
    assert any(isinstance(b,str) for a,b in Q.schedule(ps[:3],ghosts,last,counts,rng))
    saved=json.loads((S.C.ROOT/'releases/deckbuilding-v1.0/initial-ai.json').read_text(encoding='utf-8'))
    A.install();m=A.Learner(saved);p=ps[0];p.target='water-01';p.tournament_hp=100;p.streak=0
    ns=[n for n in S.TARGET_NAMES['water-01'] if S.C.CARDS[n].element=='water' and S.C.CARDS[n].kind not in ('specialization','route_legendary')][:3]
    v2=A.vector(p,ns[:2]);v3=A.vector(p,Q.T.A.projected(p,ns))
    assert v2['specialization_jump']==0 and v3['specialization_jump']>1
    assert v3['effective_layers']>v2['effective_layers']
    before=copy.deepcopy(p);p.tournament_hp=5;assert A.bank_value(p,2)<A.bank_value(before,2)
    ep=Q.simulate('unit',0,m,table,Q.T.config(),namespace='survival-unit')
    assert ep['end_round']>=13 and ep['champions']
    for row in ep['rounds']:
        ids=[p['pid'] for p in row['players']]
        appearances=[pid for pair in row['announced_pairs'] for pid in [pair['a'],pair['b']] if isinstance(pid,int)]
        assert sorted(ids)==sorted(appearances)
        for b in row['battles']:
            result=b['result'];a,bid=b['a'],b['b'];m,n=row['parameters']
            for pid,other in [(a,'ghost' if b['ghost'] else 'survivor-'+str(bid))]+([] if b['ghost'] else [(bid,'survivor-'+str(a))]):
                expected=0 if result['winner']=='survivor-'+str(pid) else Q.damage(m,n,result['players'][other]['hp'],result['winner']=='draw')
                assert row['settlement'][pid]['loss']==expected
    print('Survival formula, threshold uplift, low-HP banking, scheduling, ghost, elimination and full tournament passed.')


if __name__=='__main__':main()
