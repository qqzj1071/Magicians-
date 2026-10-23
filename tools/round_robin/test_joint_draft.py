"""Uniformity rejection, actual-core phases, history transfer and online replay."""
import copy
from dataclasses import replace
import train_joint_draft as T
from shared_draft_pool import assert_uniform_counts,Pool


def main():
    cfg=T.config();assert_uniform_counts(cfg)
    bad=copy.deepcopy(cfg);bad['card_copy_overrides']={'短促':99}
    try:Pool(config=bad)
    except AssertionError:pass
    else:raise AssertionError('Per-name stock bias accepted')
    T.S.C.DECKS['test-no-core']=dict(element='fire',route='',entries=[dict(name='攻击强化',quantity=1)])
    states=[T.J.E.State('fire',deck_id='test-no-core'),T.J.E.State('water',deck_id='test-no-core')]
    p=T.J.P.Policy(own='test-no-core',opponent='test-no-core')
    assert T.J.phase(states,0,0,p)=='operation'
    T.S.C.DECKS['test-core']=copy.deepcopy(T.S.TARGETS['fire-01'])
    states[0]=replace(states[0],deck_id='test-core')
    assert T.J.phase(states,0,0,p)=='startup'
    m=T.J.CombatLearner();historical=m.policy('fire-01','water-01',14,'historical')
    generic=m.policy('fire-01','water-01',14,'generic')
    assert historical!=generic and historical.mode=='staged'
    T.install();model=T.JointLearner()
    a=T.S.simulate_episode('test',0,model,True,economy=T.CURRENT,namespace='joint-replay',config=cfg,total_rounds=14)
    b=T.S.simulate_episode('test',0,T.JointLearner(),True,economy=T.CURRENT,namespace='joint-replay',config=cfg,total_rounds=14)
    assert a==b and model.updates==56 and model.combat.updates==56
    assert model.combat.games==84 and len(model.combat.log)==56
    assert all(len(r['battles'])==2 for r in a['rounds'])
    print('Uniform buckets, actual available cores, historical route transfer, deterministic mixed-deck learning for both sides: passed')


if __name__=='__main__':main()
