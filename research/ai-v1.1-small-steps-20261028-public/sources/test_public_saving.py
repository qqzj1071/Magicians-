"""Broadcast privacy, financial caps, risk tradeoff and deterministic learning."""
import copy
import public_saving_draft as N
T=N.T


def main():
    N.install();m=N.Learner();ps=[T.S.Player(i,'water-01',economy=N.CURRENT) for i in range(4)]
    m.on_episode_start(ps);p=ps[0];p.spec='water';p.current_round=1;p.target='water-01'
    p.deck=[(n,None) for n in T.S.TARGET_NAMES['water-01'] if T.S.C.CARDS[n].kind!='route_legendary']
    N.announce(m,p,ps)
    assert N.bank_value(p,2)==N.bank_value(p,9)>N.bank_value(p,1)>N.bank_value(p,0)
    safe=N.bank_value(p,2);p.recent_reward=-1;assert N.bank_value(p,2)<safe
    p.current_round=14;assert N.bank_value(p,2)==0
    ps[1].spec='water';ps[1].deck=[(T.S.TARGETS['water-01']['route'],None)]
    N.pick_target(p,ps,m.w);assert p.target=='water-01' # no private-deck access
    N.announce(m,ps[1],ps);assert p.target!='water-01'
    assert all(x['receivers']==[0,1,2,3] for x in m.events)
    assert N.signature('禁忌知识','water','',True)[:2]==(3,1)
    assert N.signature('速读','water','',True)[:2]==(1,0)
    assert N.signature('禁咒目录','water','',True)[2]==2
    cfg=T.config();before=copy.deepcopy(cfg['rarities']);model=N.Learner()
    a=T.S.simulate_episode('replay',0,model,True,economy=N.CURRENT,namespace='public-saving-unit',config=cfg,total_rounds=14)
    b=T.S.simulate_episode('replay',0,N.Learner(),True,economy=N.CURRENT,namespace='public-saving-unit',config=cfg,total_rounds=14)
    assert a==b and model.updates==56 and model.combat.updates==56
    assert before==cfg['rarities'] and a['combat_count']==28
    assert all('broadcasts' in r and 'finance' in r for r in a['rounds'])
    print('Public-only target updates, four-player broadcasts, bank cap/end horizon/risk, resource effects and deterministic learning: passed')


if __name__=='__main__':main()
