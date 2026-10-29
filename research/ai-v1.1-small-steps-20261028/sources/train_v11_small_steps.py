"""Exactly 10 x 100 four-player rooms; bounded evolutionary AI-only training."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MAGICIANS_CARD_LIBRARY']=str(ROOT/'decks/trained-v1.1-poison.json')
import json,copy,random,hashlib,gzip,statistics
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import strategic_tournament_ai as I
import survival_tournament as Q
from ai_v11_policy import bind
from run_v11_balance_test import compact_episode
RUN='ai-v1.1-small-steps-20261028'
OUT=ROOT/'research'/RUN

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def frozen():
 m=json.loads((ROOT/'releases/v1.1/freeze-manifest.json').read_text(encoding='utf-8'))
 for n,h in m['sha256'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 return m

def model(data):
 I.install();return bind(I.Learner(data),data.get('ai_v11',{}))

def trial(base,phase):
 d=copy.deepcopy(base);rng=random.Random(2026102800+phase);changes={}
 keys=[k for k in ['mana_fit','instant','reserve_plan','coin','bank','specialization_jump','next_counter','tempo_streak'] if k in d['draft']]
 for k in rng.sample(keys,min(2,len(keys))):
  old=d['draft'][k];step=max(.005,abs(old)*.02)*rng.choice([-1,1]);d['draft'][k]=old+step;changes['draft.'+k]=[old,d['draft'][k]]
 pairs=[('energy','draw'),('core_priority','cost_power'),('damage','tempo_value'),('health','sustain_value'),('energy','budget_fit')]
 for k in pairs[(phase-1)%len(pairs)]:
  lo,hi=I.J.BOUNDS[k];sign=1 if k!='cost_power' else -1
  if phase>5:sign*=rng.choice([-1,1])
  for stage,cell in d['combat']['context'].items():
   old=cell.get(k,0);cell[k]=max(-(hi-lo)*.3,min((hi-lo)*.3,old+sign*(hi-lo)*.01));changes['combat.context.'+stage+'.'+k]=[old,cell[k]]
 cfg=d.setdefault('ai_v11',{});old=cfg.get('resource_projection',0);cfg['resource_projection']=min(1,old+.1)
 changes['ai_v11.resource_projection']=[old,cfg['resource_projection']]
 return d,changes

def worker(job):
 phase,ids,candidate,incumbent,table,cfg=job
 rows=[]
 for idx in ids:
  start=idx%4;newids={start,(start+1)%4}
  actors={pid:model(candidate if pid in newids else incumbent) for pid in range(4)}
  ep=Q.simulate('small-step',idx,model(incumbent),table,cfg,False,RUN+f'-batch-{phase}',seat_models=actors)
  short=compact_episode(ep);short.update(batch=phase,candidate_seats=sorted(newids),split='development' if idx<80 else 'sealed',inventory_audited=True)
  short['candidate_points']=sum(p['points'] for p in short['placements'] if p['pid'] in newids)
  short['candidate_wins']=sum(p['win_share'] for p in short['placements'] if p['pid'] in newids)
  short['baseline_points']=-short['candidate_points'];short['baseline_wins']=1-short['candidate_wins']
  if idx<2:short['audit_rounds']=ep['rounds']
  rows.append(short)
 return rows

def scores(rows):
 n=len(rows)
 return dict(games=n,candidate_mean_points=sum(e['candidate_points'] for e in rows)/(2*n),baseline_mean_points=sum(e['baseline_points'] for e in rows)/(2*n),candidate_win_rate=sum(e['candidate_wins'] for e in rows)/(2*n),baseline_win_rate=sum(e['baseline_wins'] for e in rows)/(2*n))

def main():
 OUT.mkdir(parents=True,exist_ok=False);freeze=frozen()
 pointer=json.loads((ROOT/'docs/ai/current-tournament.json').read_text(encoding='utf-8-sig'));initial=json.loads((ROOT/pointer['model']).read_text(encoding='utf-8'));initial.setdefault('ai_v11',{'resource_projection':0})
 incumbent=copy.deepcopy(initial);history=[];allrows=[]
 cfg=json.loads((ROOT/'releases/deckbuilding-v1.0/probabilities.json').read_text(encoding='utf-8'));table=json.loads((ROOT/'releases/deckbuilding-v1.0/damage.json').read_text(encoding='utf-8'))['table']
 save(OUT/'initial-model.json',initial);save(OUT/'protocol.json',dict(batches=10,rooms_per_batch=100,total_rooms=1000,development_per_batch=80,sealed_per_batch=20,method='bounded evolutionary continuation; two candidate seats versus two incumbent seats; seat rotation',draft_step='2% of current weight (minimum .005)',combat_step='1% of allowed parameter range',logic_step='0.1 resource-credit valuation weight',accept='development mean points > 0 and candidate champion share >= incumbent',sealed='never inspected until all ten updates finish; cohort comparison, not a fixed-final-policy terminal test',initial_pointer=pointer,frozen_manifest=freeze))
 with ProcessPoolExecutor(max_workers=12) as pool,gzip.open(OUT/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
  for phase in range(1,11):
   frozen();candidate,changes=trial(incumbent,phase);save(OUT/f'batch-{phase:02d}-candidate.json',candidate);rows=[]
   jobs=[(phase,list(range(start,min(100,start+5))),candidate,incumbent,table,cfg) for start in range(0,100,5)]
   for part in pool.map(worker,jobs):rows.extend(part)
   rows.sort(key=lambda x:x['index']);assert len(rows)==100
   development=[e for e in rows if e['split']=='development'];s=scores(development)
   accepted=s['candidate_mean_points']>0 and s['candidate_win_rate']>=s['baseline_win_rate']
   if accepted:incumbent=candidate
   record=dict(batch=phase,development=s,accepted=accepted,changes=changes);history.append(record)
   for row in rows:
    raw.write(json.dumps(row,ensure_ascii=False)+'\n');allrows.append({k:v for k,v in row.items() if k!='audit_rounds'})
   raw.flush();save(OUT/f'batch-{phase:02d}-checkpoint.json',incumbent);save(OUT/'history.json',history)
   frozen();print(json.dumps(dict(batch=phase,completed=phase*100,accepted=accepted,development=s),ensure_ascii=False),flush=True)
 # Only now open the sealed observations; never use them to modify weights.
 sealed=scores([e for e in allrows if e['split']=='sealed'])
 for e in allrows:
  assert len(e['placements'])==4 and len({p['pid'] for p in e['placements']})==4
  assert abs(sum(p['points'] for p in e['placements']))<1e-8
  assert abs(sum(p['win_share'] for p in e['placements'])-1)<1e-8
 save(OUT/'selected-model.json',incumbent)
 save(OUT/'summary.json',dict(games=1000,batches=10,accepted_batches=sum(h['accepted'] for h in history),sealed_cohort=sealed,independent_final_model_improvement='not established: sealed rooms evaluate evolving candidates against their incumbents',validation=dict(settlements=4000,points_conserved=True,winner_shares_conserved=True,inventory_audited=True,frozen_hashes_unchanged=True),model_sha256=hashlib.sha256((OUT/'selected-model.json').read_bytes()).hexdigest()))
 save(OUT/'episodes.compact.json',allrows);frozen();print('V11_SMALL_STEPS_COMPLETE',flush=True)
if __name__=='__main__':main()
