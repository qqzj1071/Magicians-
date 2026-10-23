"""Independent final comparisons and descriptive competition/offer diagnostics."""
import argparse
import gzip
import json
import math
import statistics
import random
from collections import Counter, defaultdict
import cards as C
from simulate_shared_draft import TARGETS, TARGET_NAMES, score_similarity, seed, START
from shared_draft_combat import ENGINE as E, battle


def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def install(name,p):
    C.DECKS[name]=dict(id=name,element=p['spec'] or TARGETS[p['target']]['element'],specialization_selected=bool(p['spec']),
                       route=p['route'],entries=[dict(name=n,quantity=1) for n in p['names']])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    out=C.ROOT/'research'/args.run
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    results=defaultdict(list);diagnostics={}
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:results[json.loads(line)['condition']].append(json.loads(line))
    for condition,episodes in results.items():
        coverage=[];rounds=defaultdict(list);denied=[];not_denied=[];achieved=[];affinities=Counter()
        final_players=[];core_times=[];core_eligible=0
        for ep in episodes:
            for p in ep['players']:
                final_players.append(p)
                pid=p['pid'];seen=set(START);affinities[p['affinity']]+=1
                for row in ep['rounds']:
                    for face in ['first','second']:
                        seen.update(n for n in row[face].get(str(pid),[]) if n)
                    current=row['players'][pid]
                    seen.update(n for n in current['names'] if C.CARDS[n].kind=='specialization')
                    rounds[row['round']].append(current)
                # Optimistic ceiling conditioned on faces actually requested;
                # ignores cost, purchase timing and forced retained cards.
                ceilings={did:len(seen&set(TARGET_NAMES[did]))/sum(TARGET_NAMES[did].values()) for did in TARGETS}
                coverage.append(max(ceilings.values()))
                target=p['actual_route_similarity']
                if p['similarity']['jaccard']>=.8:achieved.append(dict(episode=ep['index'],pid=pid))
                (denied if p['denied_generic'] else not_denied).append(p['similarity']['jaccard'])
                if p['spec'] and p['route']:
                    core_eligible+=1
                    spec_name=next(n for n,c in C.CARDS.items() if c.element==p['spec'] and c.kind=='specialization')
                    final_battle=next(b for b in ep['rounds'][-1]['battles'] if pid in (b['a'],b['b']))
                    activations=final_battle['players'][f'draft-p{pid}']['activations']
                    if spec_name in activations and p['route'] in activations:
                        core_times.append(max(activations[spec_name],activations[p['route']]))
        diagnostics[condition]=dict(
            candidate_coverage_ceiling_mean=statistics.mean(coverage),
            candidate_coverage_ceiling_ge80=sum(x>=.8 for x in coverage)/len(coverage),
            denied_players=len(denied),denied_players_jaccard_mean=statistics.mean(denied) if denied else None,
            others_jaccard_mean=statistics.mean(not_denied) if not_denied else None,
            precision_mean=statistics.mean(p['similarity']['precision'] for p in final_players),
            recall_mean=statistics.mean(p['similarity']['recall'] for p in final_players),
            recall_ge80_count=sum(p['similarity']['recall']>=.8 for p in final_players),
            dice_ge80_count=sum(p['similarity']['dice']>=.8 for p in final_players),
            selected_spec_round_mean=statistics.mean(p['spec_round'] for p in final_players if p['spec']),
            final_core_owned=core_eligible,final_core_completed=len(core_times),
            final_core_time_median=statistics.median(core_times) if core_times else None,
            achieved=achieved,affinity_curriculum=dict(affinities),
            round_metrics={str(r):dict(mean_size=statistics.mean(p['size'] for p in ps),
                                     mean_cost=statistics.mean(p['average_cost'] for p in ps),
                                     specialized_rate=sum(bool(p['spec']) for p in ps)/len(ps),
                                     jaccard_mean=statistics.mean(p['similarity']['jaccard'] for p in ps),
                                     mean_draw=statistics.mean(p['resources']['draw'] for p in ps),
                                     mean_search=statistics.mean(p['resources']['search'] for p in ps))
                           for r,ps in rounds.items()})
    # Matched-seed comparisons of final constructed decks, fresh battle seeds.
    by_condition={k:{(ep['index'],p['pid']):p for ep in eps for p in ep['players']} for k,eps in results.items()}
    matches=[]
    for key,p in by_condition['learned'].items():
        q=by_condition['prior'][key]
        install('comparison-learned',p);install('comparison-prior',q)
        for flip in range(2):
            a,b=('comparison-learned','comparison-prior') if not flip else ('comparison-prior','comparison-learned')
            s=seed(args.run,'heldout-final-comparison',key[0],key[1],flip)
            result=battle(a,b,s,E.GREEDY,E.GREEDY)
            matches.append(dict(episode=key[0],pid=key[1],flip=flip,seed=s,winner=result['winner'],
                                time=result['time'],score=.5 if result['winner']=='draw' else float(result['winner']=='comparison-learned')))
    economy_matches=[]
    if 'old_economy' in by_condition:
        for key,p in by_condition['learned'].items():
            q=by_condition['old_economy'][key]
            install('comparison-current-economy',p);install('comparison-old-economy',q)
            for flip in range(2):
                a,b=('comparison-current-economy','comparison-old-economy') if not flip else ('comparison-old-economy','comparison-current-economy')
                s=seed(args.run,'heldout-economy-comparison',key[0],key[1],flip)
                result=battle(a,b,s,E.GREEDY,E.GREEDY)
                economy_matches.append(dict(episode=key[0],pid=key[1],flip=flip,seed=s,winner=result['winner'],
                     score=.5 if result['winner']=='draw' else float(result['winner']=='comparison-current-economy')))
    for condition in ['learned','prior']:
        benchmarks=[]
        for key,p in by_condition[condition].items():
            install('comparison-constructed',p)
            # All candidates of one route face the same nearest reference chosen
            # from their own data; this is descriptive, not a shared-opponent causal test.
            ref=p['nearest']
            result=battle('comparison-constructed',ref,seed(args.run,'heldout-reference-battle',condition,*key),E.GREEDY,E.GREEDY)
            benchmarks.append(.5 if result['winner']=='draw' else float(result['winner']=='comparison-constructed'))
        diagnostics[condition]['nearest_reference_battle_score']=statistics.mean(benchmarks)
    report=dict(diagnostics=diagnostics,
                learned_vs_prior_final_battles=dict(n=len(matches),score=statistics.mean(x['score'] for x in matches),
                    wins=sum(x['score']==1 for x in matches),draws=sum(x['score']==.5 for x in matches)),
                interpretation='Offer ceilings and denial groups are descriptive. Generic-copy and noncompetitive controls are interventions with matched stream names; downstream actions and random consumption diverge. No human-player or full-elimination claims.')
    if economy_matches:
        report['new_vs_old_economy_final_battles']=dict(n=len(economy_matches),score=statistics.mean(x['score'] for x in economy_matches),
                      wins=sum(x['score']==1 for x in economy_matches),draws=sum(x['score']==.5 for x in economy_matches))
        write(out/'economy-comparison-battles.json',economy_matches)
    rng=random.Random(seed(args.run,'episode-cluster-bootstrap'))
    for key,rows in [('learned_vs_prior_final_battles',matches),('new_vs_old_economy_final_battles',economy_matches)]:
        if not rows:continue
        groups=defaultdict(list)
        for row in rows:groups[row['episode']].append(row['score'])
        keys=list(groups);samples=[]
        for _ in range(10000):
            values=[v for i in rng.choices(keys,k=len(keys)) for v in groups[i]]
            samples.append(statistics.mean(values))
        samples.sort();report[key]['episode_cluster_bootstrap_95']=[samples[250],samples[9749]]
    write(out/'analysis.json',report);write(out/'final-comparison-battles.json',matches)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
