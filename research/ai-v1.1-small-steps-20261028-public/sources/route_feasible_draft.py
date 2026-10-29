"""Inference-only repair: available routes precede immediate-reference fit.

Separate from the three completed training cycles; evaluated on new seeds.
No card, pool, budget, legendary probability or combat weight is changed.
"""
import argparse
import copy
import gzip
import json
import random
from collections import Counter
import train_joint_draft as T

ORIGINAL_PURCHASE=T.A.purchase_phase


def pick_target(p,players,w):
    ns=T.S.names(p);route=T.A.route_of(ns)
    if route:p.target=T.A.ROUTE_ID[route];return
    unavailable={T.A.route_of(T.S.names(q)) for q in players if q.pid!=p.pid}
    legal=[did for did,d in T.S.TARGETS.items() if not p.spec or d['element']==p.spec]
    feasible=[did for did in legal if T.S.TARGETS[did]['route'] not in unavailable]
    # Four same-element players can exhaust all three routes; continue building
    # normally instead of inventing stock or failing an empty choice list.
    options=feasible or legal
    pool=getattr(p,'visible_route_pool',None)
    if pool is not None and p.current_round>=8:
        available=[]
        for token in pool.offers[p.pid]:
            if not token:continue
            n=pool.tokens[token]
            if T.S.C.CARDS[n].kind!='route_legendary':continue
            cost,_=T.A.price(p,n,w,players)
            if cost is not None and cost<=p.points:available.append(T.A.ROUTE_ID[n])
        visible=[did for did in options if did in available]
        if visible:options=visible
    scored=[]
    for did in options:
        d=T.S.TARGETS[did]
        value=T.A.dot(w,T.A.vector(p,ns,did))+.18*(did==p.affinity)+.08*(did==p.target)
        value-=.05*sum(q.spec==d['element'] for q in players if q.pid!=p.pid)
        scored.append((value,did))
    p.target=max(scored)[1]


def purchase(p,players,pool,model,r,rng,learn):
    p.visible_route_pool=pool
    try:return ORIGINAL_PURCHASE(p,players,pool,model,r,rng,learn)
    finally:p.visible_route_pool=None


def install():
    T.install();T.A.pick_target=pick_target;T.S.pick_target=pick_target;T.S.purchase_phase=purchase


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--rooms',type=int,default=6);args=ap.parse_args()
    parent=T.S.C.ROOT/'research'/args.run;out=parent/'route-feasibility-repair'
    if out.exists():raise FileExistsError(out)
    out.mkdir();cfg=json.loads((parent/'selected-config.json').read_text(encoding='utf-8'))
    saved=json.loads((parent/'selected-model.json').read_text(encoding='utf-8'));model=T.JointLearner()
    model.w=saved['draft'];model.combat.stage=saved['combat']['stage'];model.combat.route=saved['combat']['route']
    T.S.IDS=list(T.S.IDS);random.Random('joint-balanced-route-preferences').shuffle(T.S.IDS)
    # Old and repaired decisions share new named seeds; source experiment's final
    # seeds are not reused for this diagnostic repair evaluation.
    with gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        T.install()
        old_eps,old_s=T.stage('repair-control',args.rooms,model,cfg,False,'repair-sealed',raw,out)
        T.A.pick_target=pick_target;T.S.pick_target=pick_target;T.S.purchase_phase=purchase
        new_eps,new_s=T.stage('repair-feasible',args.rooms,model,cfg,False,'repair-sealed',raw,out)
    rows=[];initial=T.J.CombatLearner()
    for label,eps in [('control',old_eps),('repaired',new_eps)]:
        for ep in eps:
            for p in ep['players']:
                T.deck(p,'repair-own')
                for oid in T.S.TARGETS:
                    T.S.C.DECKS['repair-enemy']=copy.deepcopy(T.S.TARGETS[oid])
                    for flip in range(2):
                        seed=T.S.seed(args.run,'repair-independent-matrix',ep['index'],p['pid'],oid,flip)
                        own=model.combat.policy('repair-own','repair-enemy',14)
                        enemy=initial.policy('repair-enemy','repair-own',14,'historical')
                        a,b=('repair-own','repair-enemy') if not flip else ('repair-enemy','repair-own')
                        result=model.combat.play(a,b,seed,own if not flip else enemy,enemy if not flip else own)
                        rows.append(dict(condition=label,episode=ep['index'],pid=p['pid'],opponent=oid,flip=flip,seed=seed,
                                         score=T.score(result,'repair-own')))
            print(f'repair matrix {label} {ep["index"]+1}/{len(eps)}',flush=True)
    T.S.save(out/'matrix.json',dict(rows=rows))
    T.S.save(out/'summary.json',dict(control=old_s,repaired=new_s,training_updates=0,
        score={label:sum(x['score'] for x in rows if x['condition']==label)/sum(x['condition']==label for x in rows) for label in ['control','repaired']},
        scope='post-diagnostic inference repair; no fourth training cycle; separate seeds, same uniform pool and frozen combat weights'))


if __name__=='__main__':main()
