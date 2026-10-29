"""Room-clustered performance, banking opportunities and broadcast diagnostics."""
import argparse
import copy
import gzip
import json
import statistics as st
from collections import Counter,defaultdict
import train_public_saving as U
from analyze_dice_optimization import interval
T=U.T


def load(out):
    groups=defaultdict(list)
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line);groups[ep['condition']].append(ep)
    return groups


def early_probe(out,groups):
    saved=json.loads((out/'selected-model.json').read_text(encoding='utf-8'));model=U.N.Learner();U.restore_combat(model,saved['combat'])
    previous=json.loads((out/'previous-model.json').read_text(encoding='utf-8'));enemy=U.N.Learner();U.restore_combat(enemy,previous['combat'])
    rows=[]
    for selected in groups['final-selected']:
        i=selected['index']
        for r in (1,2,5,6):
            for pid in range(4):
                T.deck(groups['final-legacy'][i]['rounds'][r-1]['players'][(pid+1)%4],'saving-enemy')
                for label,condition in [('saving','final-selected'),('no_saving','final-no-saving')]:
                    T.deck(groups[condition][i]['rounds'][r-1]['players'][pid],'saving-own')
                    pa=model.combat.policy('saving-own','saving-enemy',r);pb=enemy.combat.policy('saving-enemy','saving-own',r)
                    for flip in range(2):
                        seed=T.S.seed(out.name,'sealed-early-cost',i,pid,r,flip)
                        a,b=('saving-own','saving-enemy') if not flip else ('saving-enemy','saving-own')
                        result=model.combat.play(a,b,seed,pa if not flip else pb,pb if not flip else pa)
                        rows.append(dict(episode=i,pid=pid,round=r,flip=flip,seed=seed,model=label,score=T.score(result,'saving-own')))
        print(f'early saving probe {i+1}/{len(groups["final-selected"])}',flush=True)
    T.S.save(out/'early-saving-probe.json',dict(rows=rows))


def finance(eps):
    result={};total=len(eps)*4
    for r in (1,2,3,5,6,7,8,10,12,14):
        points=[v for e in eps for v in e['rounds'][r-1]['points']]
        result[r]=dict(bank=st.mean(v['bank'] for v in points),bank_ge1=st.mean(v['bank']>=1 for v in points),
            bank2=st.mean(v['bank']==2 for v in points),income=st.mean(v['income'] for v in points),
            refresh=st.mean(any(a['kind']=='refresh' for a in v['actions']) for v in points),
            paid_buy_points=st.mean(sum(a['cost'] for a in v['actions'] if a['kind']=='buy') for v in points),
            discarded_points=st.mean(max(0,v['remaining']-2) for v in points))
    opportunities=Counter()
    for e in eps:
        for r,rank,price in [(2,'epic',3),(6,'legendary',4)]:
            row=e['rounds'][r-1]
            for pid,v in enumerate(row['points']):
                first=[n for n in row['first'][str(pid)] if n and T.S.C.CARDS[n].rarity==rank]
                opportunities[f'r{r}_first_seen']+=bool(first)
                opportunities[f'r{r}_first_affordable_income']+=v['income']>=price
                opportunities[f'r{r}_first_seen_affordable']+=bool(first) and v['income']>=price
                second_phase=False;first_spend=0
                for act in v['actions']:
                    if act['kind']=='refresh':second_phase=True
                    if act['kind']=='buy':
                        if not second_phase:first_spend+=act['cost']
                        if T.S.C.CARDS[act['name']].rarity==rank:opportunities[f'r{r}_bought']+=1
                opportunities[f'r{r}_can_refresh_and_pay_after_first']+=v['income']-first_spend>=price+1
    return dict(rounds=result,opportunities=dict(opportunities),players=total)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--early-probe',action='store_true');args=ap.parse_args()
    out=T.S.C.ROOT/'research'/args.run;groups=load(out)
    if args.early_probe:early_probe(out,groups)
    matrix=json.loads((out/'final-matrix.json').read_text(encoding='utf-8'))['rows']
    bymodel={};room_means={}
    for label in sorted(set(x['model'] for x in matrix)):
        rows=[x for x in matrix if x['model']==label];rooms=defaultdict(list)
        for x in rows:rooms[x['episode']].append(x['score'])
        room_means[label]={k:st.mean(v) for k,v in rooms.items()}
        bymodel[label]=dict(n=len(rows),**interval(list(room_means[label].values())),
            win_rate=st.mean(st.mean(x==1 for x in values) for values in rooms.values()),
            draw_rate=st.mean(st.mean(x==.5 for x in values) for values in rooms.values()),
            unused=st.mean(x['unused'] for x in rows),granted=st.mean(x['granted'] for x in rows),
            plays=st.mean(x['plays'] for x in rows),duration=st.mean(x['duration'] for x in rows))
    paired={k:interval([room_means['selected'][i]-v[i] for i in room_means['selected']]) for k,v in room_means.items() if k!='selected'}
    final_finance={k:finance(v) for k,v in groups.items() if k.startswith('final-')}
    stage={}
    for r in (3,6,8,10,12,14):
        rows=[x for x in json.loads((out/'final-controller-bank.json').read_text(encoding='utf-8'))['rows'] if x['round']==r]
        stage[r]={k:st.mean(x['score'] for x in rows if x['model']==k) for k in ['new','old']}
    early={}
    if (out/'early-saving-probe.json').exists():
        rows=json.loads((out/'early-saving-probe.json').read_text(encoding='utf-8'))['rows']
        for r in (1,2,5,6):
            current=[x for x in rows if x['round']==r];rooms=defaultdict(list)
            for x in current:rooms[(x['model'],x['episode'])].append(x['score'])
            early[r]=dict(score={k:st.mean(x['score'] for x in current if x['model']==k) for k in ['saving','no_saving']},
                paired=interval([st.mean(rooms[('saving',i)])-st.mean(rooms[('no_saving',i)]) for i in range(len(groups['final-selected']))]))
    flow={};missing=Counter();reroutes=Counter();unavailable_targets=0;capacity={};route_missing=defaultdict(Counter)
    for condition in ['final-selected','final-legacy','final-no-saving','final-initial-new']:
        eps=groups[condition];flow[condition]={}
        for r in (3,5,6,8,10,12,14):
            ps=[p for e in eps for p in e['rounds'][r-1]['players']]
            flow[condition][r]=dict(spec=st.mean(bool(p['spec']) for p in ps),route=st.mean(bool(p['route']) for p in ps),
                size=st.mean(p['size'] for p in ps),cost=st.mean(p['average_cost'] for p in ps),
                dice=st.mean(p['route_dice'] for p in ps))
        for ep in eps:
            for row in ep['rounds']:
                for ev in row.get('broadcasts',[]):
                    reroutes[condition+':'+ev['kind']]+=1
                    reroutes[condition+':target_changes']+=len(ev['retargets'])
                if 'public_state' in row:
                    public=row['public_state'];owned={v['route'] for v in public['players'].values() if v['route']}
                    for p in row['players']:
                        if not p['route'] and T.S.TARGETS[p['target']]['route'] in owned:unavailable_targets+=condition=='final-selected'
    ps=[p for e in groups['final-selected'] for p in e['players']]
    for p in ps:
        rid=T.J.ROUTE_ID.get(p['route'])
        if rid:
            for n,q in (T.S.TARGET_NAMES[rid]-Counter(p['names'])).items():missing[n]+=q;route_missing[p['route']][n]+=q
    for key in ['draw','energy','search','shuffle']:
        capacity[key]=st.mean(p['operation_effects'][key] for p in ps)
    result=dict(matrix=bymodel,paired=paired,stage_combat=stage,early_saving=early,finance=final_finance,
        flow=flow,broadcast_counts=dict(reroutes),selected_blocked_target_rounds=unavailable_targets,
        missing_top=dict(missing.most_common(20)),route_missing={k:dict(v.most_common(6)) for k,v in route_missing.items()},
        selected_operation_projection=capacity,opponent_roster=sorted(set(x['opponent'] for x in matrix)),
        limitation='Room-clustered exploratory intervals; fixed opponent roster; no claim of optimal play or complete tournament')
    T.S.save(out/'analysis.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
