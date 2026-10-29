"""Independent diagnostics and fixed-card generic-policy ablation."""
import argparse
import gzip
import json
import statistics as st
import time
from collections import Counter,defaultdict
import train_joint_draft as T
from analyze_dice_optimization import interval


def load(out):
    groups=defaultdict(list)
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line);groups[ep['condition']].append(ep)
    return groups


def generic_probe(out,eps,model):
    initial=T.J.CombatLearner();rows=[];start=time.time()
    for ep in eps:
        for p in ep['players']:
            T.deck(p,'eval-own')
            for oid in T.S.TARGETS:
                T.S.C.DECKS['eval-enemy']=T.copy.deepcopy(T.S.TARGETS[oid])
                own=model.policy('eval-own','eval-enemy',14,'generic')
                # Remove route transfer/personality but retain the learned common
                # stage, isolating personalization rather than all learning.
                delta=model.stage['8-14']
                own=T.J.replace(own,**{k:max(T.J.BOUNDS[k][0],min(T.J.BOUNDS[k][1],getattr(own,k)+v)) for k,v in delta.items()})
                enemy=initial.policy('eval-enemy','eval-own',14,'historical')
                for flip in range(2):
                    seed=T.S.seed(out.name,'sealed-matrix',ep['index'],p['pid'],oid,flip)
                    a,b=('eval-own','eval-enemy') if not flip else ('eval-enemy','eval-own')
                    result=model.play(a,b,seed,own if not flip else enemy,enemy if not flip else own)
                    rows.append(dict(episode=ep['index'],pid=p['pid'],route=p['route'],opponent=oid,
                                     flip=flip,seed=seed,model='generic',score=T.score(result,'eval-own')))
        print(f'generic probe {ep["index"]+1}/{len(eps)} {time.time()-start:.1f}s',flush=True)
    T.S.save(out/'final-generic-probe.json',dict(rows=rows));return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--generic-probe',action='store_true');args=ap.parse_args()
    out=T.S.C.ROOT/'research'/args.run;groups=load(out);eps=groups['final-selected']
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    model=T.J.CombatLearner();saved=json.loads((out/'selected-model.json').read_text(encoding='utf-8'))
    model.stage=saved['combat']['stage'];model.route=saved['combat']['route']
    matrix=json.loads((out/'final-matrix.json').read_text(encoding='utf-8'))
    rows=list(matrix['rows'])
    if args.generic_probe:rows+=generic_probe(out,eps,model)
    elif (out/'final-generic-probe.json').exists():rows+=json.loads((out/'final-generic-probe.json').read_text(encoding='utf-8'))['rows']
    means={};room_scores={}
    for label in sorted(set(x['model'] for x in rows)):
        rs=[x for x in rows if x['model']==label];byroom=defaultdict(list)
        for x in rs:byroom[x['episode']].append(x['score'])
        room_scores[label]={k:st.mean(v) for k,v in byroom.items()}
        means[label]=dict(n=len(rs),win_rate=st.mean(x['score']==1 for x in rs),
                         draw_rate=st.mean(x['score']==.5 for x in rs),**interval(list(room_scores[label].values())))
    paired={label:interval([room_scores['adaptive'][i]-room_scores[label][i] for i in room_scores['adaptive']])
            for label in room_scores if label!='adaptive'}
    bank=json.loads((out/'final-controller-bank.json').read_text(encoding='utf-8'))['rows']
    byround={}
    for r in [3,6,8,10,12,14]:
        rs=[x for x in bank if x['round']==r]
        byround[r]={label:dict(n=sum(x['model']==label for x in rs),
            score=st.mean(x['score'] for x in rs if x['model']==label),
            unused=st.mean(x['unused'] for x in rs if x['model']==label)) for label in ['new','old']}
    flow={};missing=Counter();route_missing=defaultdict(Counter);route_ps=defaultdict(list);first_routes=[]
    for r in [3,5,6,8,10,12,14]:
        ps=[p for ep in eps for p in ep['rounds'][r-1]['players']]
        flow[r]=dict(spec=st.mean(bool(p['spec']) for p in ps),route=st.mean(bool(p['route']) for p in ps),
            resources={k:st.mean(p['resources'][k] for p in ps) for k in ['draw','search','shuffle']},
            operation_complete=st.mean(p['resources']['draw']>=2 and p['resources']['search']>=2 and p['resources']['shuffle']>=1 for p in ps),
            size=st.mean(p['size'] for p in ps),cost=st.mean(p['average_cost'] for p in ps))
    rarities=defaultdict(list);missing_groups=Counter();owned_groups=Counter();all_main_complete=[]
    for ep in eps:
        for p in ep['players']:
            rs=[row['round'] for row in ep['rounds'] if row['players'][p['pid']]['route']]
            first_routes.append(min(rs) if rs else None)
            route_ps[p['route']].append(p)
            rid=T.J.ROUTE_ID.get(p['route'])
            if not rid:continue
            target=T.S.TARGET_NAMES[rid];actual=Counter(p['names']);gaps=target-actual
            for n,q in gaps.items():
                c=T.S.C.CARDS[n];group=c.rarity+'-'+('generic' if c.element=='generic' else 'enchantment')
                missing[n]+=q;route_missing[p['route']][n]+=q;missing_groups[group]+=q
            for n in actual:
                c=T.S.C.CARDS[n];owned_groups[c.rarity+'-'+('generic' if c.element=='generic' else 'enchantment')]+=1
            for rarity in ['common','rare','epic','legendary']:
                ns={n for n in target if T.S.C.CARDS[n].rarity==rarity}
                if ns:rarities[rarity].append(len(ns&set(actual))/len(ns))
            ns={n for n in target if T.S.C.CARDS[n].element==p['spec'] and T.S.C.CARDS[n].kind not in ('specialization','route_legendary')}
            all_main_complete.append(all(n in actual for n in ns))
    routes={}
    for route,ps in route_ps.items():
        rs=[x for x in rows if x['route']==route]
        routes[route]=dict(n=len(ps),dice=st.mean(p['route_dice'] for p in ps),main=st.mean(p['route_main_recall'] for p in ps),
            scores={label:st.mean(x['score'] for x in rs if x['model']==label) for label in means},
            missing=dict(route_missing[route].most_common(8)))
    failures=[];route_failures=[]
    for ep in eps:
        for p in ep['players']:
            if p['route_dice']<.8:failures.append(dict(episode=ep['index'],pid=p['pid'],spec=p['spec'],route=p['route'],dice=p['route_dice'],resources=p['resources']))
            if not p['route']:
                offers=[]
                for row in ep['rounds']:
                    pid=p['pid'];point=row['points'][pid];money=point['income'];first_spend=0
                    for act in point['actions']:
                        if act['kind']=='refresh':break
                        if act['kind']=='buy':first_spend+=act['cost']
                    for key,face,budget in [('first',0,money),('second',1,money-first_spend-1)]:
                        board=row[key].get(str(pid),[])
                        available=[n for n in board if n and T.S.C.CARDS[n].kind=='route_legendary' and T.S.C.CARDS[n].element==p['spec']]
                        if available:offers.append(dict(round=row['round'],face=face,names=available,starting_points=budget,affordable=budget>=4))
                route_failures.append(dict(episode=ep['index'],pid=p['pid'],element=p['spec'],offers=offers,
                    had_affordable_offer=any(x['affordable'] for x in offers),
                    competing_routes=[q['route'] for q in ep['players'] if q['pid']!=p['pid'] and q['spec']==p['spec']]))
    result=dict(matrix=means,paired=paired,stage_control=byround,flow=flow,routes=routes,
        first_route_rounds=dict(Counter(str(x) for x in first_routes)),missing_top=dict(missing.most_common(20)),
        missing_groups=dict(missing_groups),rarity_recall={k:st.mean(v) for k,v in rarities.items()},
        main_enchantment_complete=st.mean(all_main_complete) if all_main_complete else 0,
        portfolio_choices=dict(Counter(x['selected'] for x in matrix['calibration'])),failures=failures,route_failures=route_failures,
        distinct_elements=dict(Counter(ep['elements'] for ep in eps)),
        limitation='Room-clustered exploratory intervals, frozen opponents, finite calibration portfolio is not an optimal-play bound')
    T.S.save(out/'analysis.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
