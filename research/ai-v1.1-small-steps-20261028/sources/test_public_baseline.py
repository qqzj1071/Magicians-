"""Explicit public protocol without replacing previous construction weights."""
import public_baseline_inference as B
T=B.T


def main():
    checkpoint=T.S.C.ROOT/'research/shared-draft-v5-saving01/previous-model.json'
    model=B.load_model(checkpoint)
    ps=[T.S.Player(i,'water-01') for i in range(4)]
    model.on_episode_start(ps);p=ps[0];p.spec='water';p.current_round=1;p.target='water-01'
    p.deck=[(n,None) for n in T.S.TARGET_NAMES['water-01'] if T.S.C.CARDS[n].kind!='route_legendary']
    B.announce(model,p,ps)
    ps[1].spec='water';ps[1].deck=[(T.S.TARGETS['water-01']['route'],None)]
    B.pick_target(p,ps,model.w);assert p.target=='water-01'
    B.announce(model,ps[1],ps);assert p.target!='water-01'
    assert all(x['receivers']==[0,1,2,3] for x in model.events)
    cfg=T.config()
    a=T.S.simulate_episode('compat',0,B.load_model(checkpoint),False,config=cfg,total_rounds=14,namespace='public-baseline-test')
    b=T.S.simulate_episode('compat',0,B.load_model(checkpoint),False,config=cfg,total_rounds=14,namespace='public-baseline-test')
    assert a==b and a['combat_count']==28
    assert sum(x['kind']=='spec' for r in a['rounds'] for x in r['broadcasts'])==4
    print('Public baseline: private-state isolation, immediate broadcast retargeting and deterministic 14-round replay passed.')


if __name__=='__main__':main()
