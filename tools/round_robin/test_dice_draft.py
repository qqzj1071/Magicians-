"""New entitlement, tuning permission guardrails, 14-round replay and audits."""
import copy
from draft_economy import CURRENT,is_free_purchase,purchase_price,deletion_limit,deletion_price
import dice_draft_agent as A
import simulate_shared_draft as S
from optimize_dice_draft import initial_config,propose,guard,summarize


def main():
    for r in range(1,15):
        eligible={'common'} if r<=3 else {'common','rare'} if r<=6 else set()
        for rarity,fee in [('common',1),('rare',2),('epic',3),('legendary',4)]:
            assert purchase_price(fee,rarity,r,False,CURRENT)==(0 if rarity in eligible else fee)
            assert purchase_price(fee,rarity,r,True,CURRENT)==fee
        expected=[] if r<=3 else [0] if r<=6 else [0,1]
        assert [deletion_price(r,i,CURRENT) for i in range(deletion_limit(r,CURRENT))]==expected
    # Whichever eligible rarity was purchased consumes the same one entitlement.
    assert is_free_purchase('common',4,False,CURRENT) and not is_free_purchase('rare',4,True,CURRENT)
    assert is_free_purchase('rare',4,False,CURRENT) and not is_free_purchase('common',4,True,CURRENT)
    cfg=initial_config();cfg2,_=propose(cfg,dict(spec_by5=.5,main_recall14_mean=.5),2)
    cfg3,_=propose(cfg2,dict(spec_by5=.5,main_recall14_mean=.5),3)
    guard(cfg2,cfg);guard(cfg3,cfg2)
    bad=copy.deepcopy(cfg2);bad['legendary_copy_counts']['generic']=3
    try:guard(bad,cfg)
    except AssertionError:pass
    else:raise AssertionError('Legendary modification accepted')
    A.install();m=A.Learner()
    a=S.simulate_episode('replay',1,m,True,economy=CURRENT,namespace='dice-unit-test',config=cfg,total_rounds=14)
    b=S.simulate_episode('replay',1,A.Learner(),True,economy=CURRENT,namespace='dice-unit-test',config=cfg,total_rounds=14)
    assert a==b and m.updates==56 and a['combat_count']==28
    assert all(len(row['battles'])==2 for row in a['rounds'])
    print('growth-v3 entitlement, deletion prices, legendary/rareness guardrails, copy-step limits and 14-round deterministic learning: passed')


if __name__=='__main__':main()
