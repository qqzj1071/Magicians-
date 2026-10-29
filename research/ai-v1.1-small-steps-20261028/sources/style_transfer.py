"""Sealed opponent-style transfer test; no decisions may be changed using its outcomes."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
import argparse,copy,json
from learning_core import *
STYLES={
 'tempo':dict(core_priority=100,operation_layer=12,horizon=240,damage=1.65,finish_burst=1.75,tempo_value=2.2,panic=.9,cost_power=.65,reserve=.2),
 'sustain':dict(health=1.7,shield=1.9,defense=1.6,panic=2.4,sustain_value=2.2,horizon=520),
 'counterplay':dict(counterplay_value=2.4,cleanse=1.6,penetration_value=2.6,tempo_value=2.1,search=22,startup_resource=85,reserve=.2)}
def worker(ctx,a,b,style):
 opponent=replace(P.initial(b,a),**STYLES[style]);arms=[]
 for label,p in [('initial',P.initial(a,b)),('route',base_policy(ctx,a,b)),('personal',policy(ctx,a,b))]:
  rows=batch(ctx,a,b,'style-transfer-final',99,a+':'+style,4,p,opponent)
  arms.append(dict(label=label,rows=rows))
 result=dict(a=a,b=b,style=style,opponent_policy=asdict(opponent),arms=arms);log_job('style-transfer-final',99,a+'__'+b+'__'+style,result);return result
def main(workers=6):
 ctx=read(OUT/'selected-context.json');save(OUT/'style-profiles-frozen.json',dict(context_sha256=digest(ctx),styles=STYLES,used_for_selection=False))
 tasks=[(a,b,style) for a in IDS for b in balanced_opponents(a,0,6) for style in STYLES]
 results=[]
 with ProcessPoolExecutor(max_workers=workers) as pool:
  fs=[pool.submit(worker,ctx,*args) for args in tasks]
  for f in as_completed(fs):results.append(f.result())
 report={}
 for style in STYLES:
  report[style]={}
  for label in ('initial','route','personal'):
   rows=[row for r in results if r['style']==style for arm in r['arms'] if arm['label']==label for row in arm['rows']]
   report[style][label]=dict(n=len(rows),score=score(rows),win_rate=strict(rows))
 save(OUT/'style-summary.json',dict(studies=report,simulations=sum(len(arm['rows']) for r in results for arm in r['arms']),opponent_styles_unseen_during_training=True))
 print(json.dumps(read(OUT/'style-summary.json')),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);a=p.parse_args();main(a.workers)
