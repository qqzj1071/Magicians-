"""Add a pure-heuristic construction control without retraining or rerunning other arms."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,copy,json
from learning_core import *
from draft_learning import generate_deck
def worker(ctx,a):
 model=dict(card_rewards={},weights={},coefficient_scale=4);tests=[]
 for k in range(3):
  d,offers=generate_deck(ctx['decks'][a],model,seed('draft-offer-final',99,a,'draft',k),True);valid=legal(d);rows=[]
  if valid:
   local=copy.deepcopy(ctx);local['decks'][a]=d
   for b in balanced_opponents(a,0,6):rows+=batch(local,a,b,'draft-battle-final',99,a+':'+str(k),6,policy(ctx,a,b),policy(ctx,b,a))
  tests.append(dict(draft=k,legal=valid,deck=d,offers=offers,rows=rows))
 result=dict(a=a,tests=tests);log_job('draft-prior-final',99,a,result);return result
def main(workers=10):
 ctx=read(OUT/'selected-context.json');results=[]
 save(OUT/'draft-prior-control.json',dict(training_rewards=False,ridge=False,all_other_offer_heuristics_identical=True,model_selection_forbidden=True,uses_same_draft_and_combat_seeds=True))
 with ProcessPoolExecutor(max_workers=workers) as pool:
  fs=[pool.submit(worker,ctx,a) for a in IDS]
  for f in as_completed(fs):results.append(f.result())
 tests=[t for r in results for t in r['tests']];rows=[row for t in tests for row in t['rows']]
 report=read(OUT/'draft-final-summary.json');report['prior']=dict(decks=len(tests),legal_decks=sum(t['legal'] for t in tests),games=len(rows),score=score(rows),strict_win_rate=strict(rows))
 save(OUT/'draft-final-summary.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=10);a=p.parse_args();main(a.workers)
