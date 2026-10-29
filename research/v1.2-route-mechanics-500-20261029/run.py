"""Frozen five-element AI evaluation; exactly 500 new four-player rooms."""
import sys,json,gzip,hashlib,random,time
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import ELEMENTS,ROUTES,export
from tools.sim_v12.analytics import Statistics
from tools.sim_v12.quick_test import save,reports
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'research/v1.2-element-styles-1500-20261029'

def worker(i,policies):
 from tools.sim_v12.tournament import simulate
 seed=303000+i
 missing=i%5; cycle=i//5
 elements=[e for j,e in enumerate(ELEMENTS) if j!=missing]
 # Rotate seats in each four-room block, and balance route intentions.
 elements=elements[cycle%4:]+elements[:cycle%4]
 configs=[]
 for e in elements:
  c=deepcopy(policies[e]);c['route_intent']=ROUTES[e][cycle%3];configs.append(c)
 r=simulate(seed,policy_by_seat=configs,sequence_mode='locked')
 r['evaluation_assignment']=[dict(seat=j,element=e,route=c['route_intent'],checkpoint=c['checkpoint']) for j,(e,c) in enumerate(zip(elements,configs))]
 with gzip.open(OUT/'rooms'/f'room-{seed}.json.gz','wt',encoding='utf-8') as h:json.dump(r,h,ensure_ascii=False)
 return r

def main():
 (OUT/'rooms').mkdir(exist_ok=False);export(OUT)
 policies={e:json.loads((SOURCE/f'{e}-final-policy.json').read_text(encoding='utf-8')) for e in ELEMENTS}
 save(OUT/'frozen-policies.json',policies)
 files=list((ROOT/'tools/sim_v12').rglob('*.py'))+list((ROOT/'tools/sim_v12/rules').glob('*.json'))+list((ROOT/'docs/cards-v1.2').glob('*.md'))+list((ROOT/'docs/cards-v1.2').glob('*.json'))+list(SOURCE.glob('*-final-policy.json'))+[Path(__file__)]
 hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 save(OUT/'inputs.json',dict(games=500,seeds=[303000,303499],sha256=hashes,protocol='five omitted-element groups x100; each element400 seats, each seat100; route intents132/132/136; frozen latest element policies; no training',thresholds=dict(score_rate=.1,win_rate=.55,championship_rate=.30,low_conversion=.1)))
 stats=Statistics();start=time.monotonic()
 try:
  with ProcessPoolExecutor(max_workers=12) as pool:
   for f in as_completed([pool.submit(worker,i,policies) for i in range(500)]):
    stats.add(f.result())
    if stats.rooms%10==0:
     p=dict(completed=stats.rooms,battles=stats.battles,elapsed=round(time.monotonic()-start,1));save(OUT/'progress.json',p);print(json.dumps(p),flush=True)
  for p,h in hashes.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
  result=stats.result();result['input_hashes_verified']=True
  assert result['games']==500 and result['players']==2000 and sum(result['sequence_skips'].values())==0
  save(OUT/'statistics.json',result);reports(OUT,result)
  print('COMPLETE',flush=True)
 except BaseException as exc:
  save(OUT/'failure.json',dict(completed=stats.rooms,error=repr(exc)));raise
if __name__=='__main__':main()
