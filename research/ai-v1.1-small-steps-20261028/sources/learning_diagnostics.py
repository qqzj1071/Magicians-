"""Fixed hierarchical ablation and trace audits, never model selection."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
import argparse,copy,json
from learning_core import *

def ablation_job(ctx,a,b):
 records=[]
 for own,other in ((a,b),(b,a)):
  base=P.initial(own,other);shared=replace(base,**ctx['common']);route=base_policy(ctx,own,other);full=policy(ctx,own,other)
  for kind,p in [('common',shared),('route',route),('matchup',full)]:
   rows=batch(ctx,own,other,'hierarchy-final',99,own+'|'+other,12,p,policy(ctx,other,own))
   records.append(dict(own=own,opponent=other,kind=kind,rows=rows))
 result=dict(a=a,b=b,records=records);log_job('hierarchy-final',99,a+'__'+b,result);return result

def trace_job(ctx,a,b):
 install(ctx);s=seed('trace-audit',99,a,b,0);pa,pb=policy(ctx,a,b),policy(ctx,b,a)
 first=game(a,b,s,pa,pb,False,True,True);second=game(a,b,s,pa,pb,False,True)
 assert {k:v for k,v in first.items() if k!='log'}==second
 opposite=game(a,b,s,pa,pb,True,True)
 if a!=b:assert first['winner']==opposite['winner'] and first['players']==opposite['players']
 else:
  assert first['winner']==(-1 if opposite['winner']==-1 else 1-opposite['winner'])
  assert first['players']==opposite['players'][::-1]
 log_job('trace-audit',99,a+'__'+b,dict(a=a,b=b,result=first))
 return dict(a=a,b=b,seed=s,replay=True,seat_equivalent=a!=b,mirror_stream_equivalent=a==b,simulations=3)

def main(workers=20):
 ctx=read(OUT/'selected-context.json');ablation_pairs=[(a,b) for i,(a,b) in enumerate(PAIRS) if i%4==0 and a!=b];results=[];traces=[]
 with ProcessPoolExecutor(max_workers=workers) as pool:
  jobs=[pool.submit(ablation_job,ctx,a,b) for a,b in ablation_pairs]
  for f in as_completed(jobs):results.append(f.result())
  jobs=[pool.submit(trace_job,ctx,a,b) for a,b in PAIRS]
  for f in as_completed(jobs):traces.append(f.result())
 report={}
 for kind in ('common','route','matchup'):
  rows=[row for x in results for q in x['records'] if q['kind']==kind for row in q['rows']]
  report[kind]=dict(n=len(rows),score=score(rows),win_rate=strict(rows))
 save(OUT/'hierarchy-summary.json',dict(fixed_pair_indices='every fourth non-mirror entry in the original 120-pair enumeration',pairs=len(ablation_pairs),arms=report))
 save(OUT/'trace-audit.json',dict(pairs=len(traces),replay_passes=len(traces),seat_checks=sum(x['seat_equivalent'] for x in traces),mirror_checks=sum(x['mirror_stream_equivalent'] for x in traces),simulation_count=sum(x['simulations'] for x in traces),records=traces))
 print(json.dumps(dict(hierarchy=report,replay_passes=len(traces))),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=20);args=p.parse_args();main(args.workers)
