import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from concurrent.futures import ProcessPoolExecutor,as_completed
from tools.sim_v12.construction import THIN_INITIAL
from tools.sim_v12.train import worker,group_metrics
def main():
 out=Path(__file__).parent/'pilot';out.mkdir()
 weights=json.loads(Path('research/v1.2-training-1000-final-20261028/final-policy.json').read_text(encoding='utf-8'))['weights']
 new=dict(kind='thin',weights=weights,construction=THIN_INITIAL,checkpoint='thin-pilot')
 old=dict(kind='mechanism',weights=weights,checkpoint='heavy-pilot')
 rooms=[]
 with ProcessPoolExecutor(max_workers=6) as pool:
  futures=[pool.submit(worker,288000+i,new,old,str(out),'pilot') for i in range(6)]
  for f in as_completed(futures):rooms.append(f.result())
 print('NEW',group_metrics(rooms));print('OLD',group_metrics(rooms,False))
 for group in (True,False):
  ps=[p for r in rooms for p in r['placements'] if (p['pid'] in r['comparison']['first_seats'])==group]
  print('deck',group,sum(len(p['deck']) for p in ps)/len(ps))
if __name__=='__main__':main()
