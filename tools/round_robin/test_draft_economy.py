"""Price entitlement and deletion-stage boundaries, including zero-point buys."""
import random
from draft_economy import *
from simulate_shared_draft import Player,Learner,purchase_phase,delete_phase,names
from shared_draft_pool import Pool
import cards as C


def offer(pool,pid,names_):
    pool.release(pid)
    board=[None]*8
    for i,n in enumerate(names_):board[i]=pool.free[n].pop()
    pool.offers[pid]=board


def main():
    for r in range(1,13):
        for used in [False,True]:
            for rarity,price in [('common',1),('rare',2),('epic',3),('legendary',4)]:
                expected=0 if not used and (r<=3 and rarity=='common' or 4<=r<=6 and rarity=='rare') else price
                assert purchase_price(price,rarity,r,used)==expected
        expected=[] if r<=3 else [1] if r<=6 else [0,1]
        assert [deletion_price(r,i) for i in range(deletion_limit(r))]==expected
        assert deletion_price(r,len(expected)) is None
    pool=Pool();p=Player(0,'fire-01');p.target='fire-01';p.points=0
    m=Learner();rng=random.Random(42)
    ordinary=[n for n,c in C.CARDS.items() if c.element=='fire' and c.rarity=='common']
    offer(pool,0,ordinary[:1]);purchase_phase(p,[p],pool,m,1,rng,False)
    assert p.free_used and p.points==0 and p.free_purchases==1
    offer(pool,0,ordinary[1:2]);purchase_phase(p,[p],pool,m,1,rng,False)
    assert p.free_purchases==1 and ordinary[1] not in names(p)
    p.free_used=False;p.current_round=2
    purchase_phase(p,[p],pool,m,2,rng,False)
    assert ordinary[1] in names(p) and p.free_purchases==2
    p.points=2;before=len(p.deck);delete_phase(p,[p],pool,m,3)
    assert len(p.deck)==before and p.points==2
    p.points=0;delete_phase(p,[p],pool,m,4)
    assert len(p.deck)==before
    p.points=1;delete_phase(p,[p],pool,m,4)
    assert len(p.deck)==before-1 and p.points==0 and p.actions[-1]['cost']==1
    p.deck.extend([(ordinary[2],None),(ordinary[3],None)])
    p.points=0;before=len(p.deck);delete_phase(p,[p],pool,m,7)
    assert len(p.deck)==before-1 and p.points==0 and p.actions[-1]['cost']==0
    print('growth-v2 prices, cross-face entitlement, zero-point free buy and deletion boundaries: passed')


if __name__=='__main__':main()
