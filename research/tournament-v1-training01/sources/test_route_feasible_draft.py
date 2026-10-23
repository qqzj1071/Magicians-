"""Public route ownership, affordable visible offers and exhausted-pool fallback."""
from types import SimpleNamespace
import route_feasible_draft as R


def main():
    T=R.T;R.install();model=T.JointLearner()
    ps=[T.S.Player(i,'water-01',economy=T.CURRENT) for i in range(4)]
    p=ps[0];p.spec='water';p.target='water-01';p.current_round=8;p.points=4
    p.deck=[(n,None) for n in T.S.TARGET_NAMES['water-01'] if T.S.C.CARDS[n].kind!='route_legendary']
    routes={k:T.S.TARGETS[k]['route'] for k in ['water-01','water-02','water-03']}
    ps[1].deck=[(routes['water-01'],None)];ps[2].deck=[(routes['water-02'],None)]
    R.pick_target(p,ps,model.w);assert p.target=='water-03'
    ps[3].deck=[(routes['water-03'],None)]
    R.pick_target(p,ps,model.w);assert p.target in routes
    for q in ps[1:]:q.deck=[]
    p.visible_route_pool=SimpleNamespace(offers={0:['visible']},tokens={'visible':routes['water-02']})
    R.pick_target(p,ps,model.w);assert p.target=='water-02'
    p.points=3;R.pick_target(p,ps,model.w);assert p.target=='water-01'
    p.points=4;p.deck.append((routes['water-01'],None))
    R.pick_target(p,ps,model.w);assert p.target=='water-01'
    print('Unavailable route exclusion, same-element exhaustion fallback, affordable offer commitment and owned-route retention: passed')


if __name__=='__main__':main()
