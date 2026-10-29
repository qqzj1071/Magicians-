"""Room-cluster uncertainty, economies, learning diagnostics and champions."""
import argparse
import gzip
import json
import math
import random
import statistics as st
from collections import Counter,defaultdict
import survival_tournament as Q
S=Q.S


def interval(values,seed=723):
    rng=random.Random(seed);n=len(values);means=sorted(st.mean(rng.choices(values,k=n)) for _ in range(3000))
    return dict(mean=st.mean(values),low=means[int(.025*len(means))],high=means[int(.975*len(means))],rooms=n)


def wilson(k,n):
    z=1.95996398454;p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return dict(mean=p,low=max(0,mid-half),high=min(1,mid+half),n=n,k=k)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--duration-only',action='store_true');args=ap.parse_args()
    out=S.C.ROOT/'research'/args.run;eps=[];counts=Counter();train_battles=0;stages=defaultdict(list)
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        while True:
            try:line=f.readline()
            except EOFError:
                if args.duration_only:break
                raise
            if not line:break
            ep=json.loads(line);counts['rooms']+=1;counts['course_battles']+=ep['battles'];stages[ep['label']].append(ep)
            if ep['label'].endswith('-train'):train_battles+=ep['battles']
            if ep['label']=='sealed-final':eps.append(ep)
    s12=[];s15=[];playerstats=[];finance=defaultdict(list);rewards=Counter();counter_buys=0;milestone_choices=Counter()
    for ep in eps:
        hp={i:100 for i in range(4)};h12=h15=None
        for row in ep['rounds']:
            for pid,x in row['settlement'].items():hp[int(pid)]=max(0,x['hp'])
            if row['round']==12:h12=sum(v>40 for v in hp.values())/4
            if row['round']==15:h15=sum(v>0 for v in hp.values())/4
            for ledger in row['ledger']:
                pid=ledger['pid'];before=row['hp_before'][str(pid)];band='low<=30' if before<=30 else 'mid31-60' if before<=60 else 'high>60'
                finance[(row['round'],band)].append(dict(bank=ledger['bank'],refresh=any(a['kind']=='refresh' for a in ledger['actions']),
                    purchases=sum(a['kind']=='buy' for a in ledger['actions']),discarded=max(0,ledger['remaining']-2)))
                if ledger['bonus']:rewards['win' if ledger['previous_streak']>0 else 'loss']+=1
                if abs(ledger['previous_streak'])%3==2:
                    key='two_wins' if ledger['previous_streak']>0 else 'two_losses';milestone_choices[key+'_rounds']+=1
                    milestone_choices[key+'_bank_total']+=ledger['bank']
        s12.append(h12 if h12 is not None else sum(v>40 for v in hp.values())/4)
        s15.append(h15 if h15 is not None else sum(v>0 for v in hp.values())/4)
        allp=ep['eliminated']+([] if ep['tied'] else ep['champions']);playerstats+=allp
    if args.duration_only:
        duration=dict(strong12=interval(s12),alive15=interval(s15),ended18=wilson(sum(e['end_round']<=18 for e in eps),len(eps)))
        simple={}
        for r in [1,2,5,6,8,12,13,15,16,17]:
            xs=[v for (rr,_),values in finance.items() if rr==r for v in values]
            if xs:simple[str(r)]={key:st.mean(x[key] for x in xs) for key in ('bank','refresh','purchases','discarded')}
        result=dict(duration=duration,finance=simple,bonus_points=dict(rewards),
            route_changes=sum(p['route_changes'] for p in playerstats),spec_rounds=dict(Counter(p['spec_round'] for p in playerstats)))
        S.save(out/'duration-validation.json',result);print(json.dumps(result));return
    rows=json.loads((out/'champion-matrix.json').read_text(encoding='utf-8'))['rows'];group=defaultdict(lambda:defaultdict(list))
    for x in rows:group[x['condition']][x['room']].append(x['score'])
    scores={k:interval([st.mean(v) for _,v in sorted(rooms.items())]) for k,rooms in group.items()}
    paired={}
    for other in ('old_combat','full_reference'):
        paired[other]=interval([st.mean(group['candidate'][i])-st.mean(group[other][i]) for i in sorted(group['candidate'])])
    final=dict(strong12=interval(s12),alive15=interval(s15),ended18=wilson(sum(e['end_round']<=18 for e in eps),len(eps)))
    income={f'{r}:{band}':dict(n=len(xs),bank=st.mean(x['bank'] for x in xs),refresh=st.mean(x['refresh'] for x in xs),
        purchases=st.mean(x['purchases'] for x in xs),discarded=st.mean(x['discarded'] for x in xs)) for (r,band),xs in finance.items()}
    rounds=defaultdict(lambda:dict(players=0,alive=0,strong=0))
    for r in range(1,max(e['end_round'] for e in eps)+1):
        for ep in eps:
            hp={i:100 for i in range(4)}
            for row in ep['rounds'][:r]:
                for pid,x in row['settlement'].items():hp[int(pid)]=max(0,x['hp'])
            rounds[r]['players']+=4;rounds[r]['alive']+=sum(v>0 for v in hp.values());rounds[r]['strong']+=sum(v>40 for v in hp.values())
    matrix_games=sum(json.loads(p.read_text(encoding='utf-8'))['games'] for p in out.glob('*-matrix.json'))
    operation={key:dict(plays=st.mean(x['plays'] for x in rows if x['condition']==key),
        granted=st.mean(x['granted'] for x in rows if x['condition']==key),
        waste_ratio=st.mean(x['wasted']/max(1,x['granted']) for x in rows if x['condition']==key),
        duration=st.mean(x['duration'] for x in rows if x['condition']==key)) for key in group}
    opponent_scores={oid:{key:st.mean(x['score'] for x in rows if x['opponent']==oid and x['condition']==key)
                         for key in group} for oid in S.TARGETS}
    result=dict(final_intervals=final,champion_scores=scores,champion_paired=paired,finance=income,
        opponent_scores=opponent_scores,
        champion_operation=operation,route_changes=sum(p['route_changes'] for p in playerstats),
        alive15_room_histogram=dict(Counter(int(v*4) for v in s15)),
        milestones=dict(milestone_choices),bonus_points=dict(rewards),survival_by_round=dict(rounds),
        spec_rounds=dict(Counter(p['spec_round'] for p in playerstats)),
        route_rounds=dict(Counter(next((row['round'] for row in e['rounds'] for p in row['players'] if p['pid']==pid and p['route']),0)
            for e in eps for pid in range(4))),
        missing_standard=dict(Counter(n for e in eps for p in e['champions'] for n in
            (S.TARGET_NAMES[Q.T.J.ROUTE_ID.get(p['route'],p['target'])]-Counter(p['names'])).elements()).most_common(20)),
        stages={k:Q.summarize(v) for k,v in stages.items()},counts=dict(counts,training_trials=train_battles*2,matrix_games=matrix_games,
            total_formal_games=counts['course_battles']+train_battles*2+matrix_games))
    S.save(out/'analysis.json',result);print(json.dumps(dict(final=final,scores=scores,counts=result['counts'])))


if __name__=='__main__':main()
