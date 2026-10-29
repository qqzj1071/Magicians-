"""Audit seed partitions, input immutability, selected policies and every final row."""
from collections import Counter
from pathlib import Path
import gzip,hashlib,json,time
from learning_core import *

def walk(obj):
 if isinstance(obj,dict):
  if 'seed' in obj and 'winner' in obj and 'players' in obj:yield obj
  else:
   for v in obj.values():yield from walk(v)
 elif isinstance(obj,list):
  for v in obj:yield from walk(v)
def main():
 while not (OUT/'style-summary.json').exists():time.sleep(5)
 ctx=read(OUT/'selected-context.json');install(ctx);groups={k:set() for k in ('train','validation','feedback','baseline','final','factorial','draft','hierarchy','trace','style')};counts=Counter()
 for p in OUT.glob('round_*/*/*.json.gz'):
  with gzip.open(p,'rt',encoding='utf-8') as f:data=json.load(f)
  stage=p.parent.name
  if stage in ('route-learning','construction-learning','hard-matchup-learning','shared-learning'):
   for source,target in [('training','train'),('validation','validation')]:
    for row in walk(data[source]):groups[target].add(row['seed']);counts[target]+=1
  else:
   group={'feedback':'feedback','baseline':'baseline','checkpoint-valid':'validation','final':'final','factorial-final':'factorial','draft-final':'draft','draft-prior-final':'draft','hierarchy-final':'hierarchy','trace-audit':'trace','style-transfer-final':'style'}.get(stage)
   if group:
    for row in walk(data):groups[group].add(row['seed']);counts[group]+=1
 for i,a in enumerate(groups):
  for b in list(groups)[i+1:]:assert not groups[a]&groups[b],(a,b,'seed leakage')
 final_files=list((OUT/'round_99/final').glob('*.json.gz'));assert len(final_files)==120
 final_seeds=[]
 for p in final_files:
  with gzip.open(p,'rt',encoding='utf-8') as f:r=json.load(f)
  assert len(r['rows'])==200 and sum(x['flip'] for x in r['rows'])==100
  assert r['policies']==[asdict(policy(ctx,r['a'],r['b'])),asdict(policy(ctx,r['b'],r['a']))]
  final_seeds.extend(x['seed'] for x in r['rows'])
 assert len(final_seeds)==len(set(final_seeds))==24000
 for a,d in ctx['decks'].items():assert legal(d)
 selected=read(OUT/'selection.json');assert digest(ctx)==selected['selected_context_sha256']
 assert (OUT/'selection.json').stat().st_mtime<=min(p.stat().st_mtime for p in final_files)
 assert read(OUT/'draft-model-frozen.json')['model_sha256']==digest(read(ROOT/'docs/ai/construction-model.json'))
 config=read(OUT/'experiment.json');assert hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()==config['card_sha256']
 c=read(OUT/'completion.json')
 for module in ('engine.py','planner.py'):
  assert hashlib.sha256((ROOT/'tools/round_robin'/module).read_bytes()).hexdigest()==c['source_sha256'][module],module
 expected=dict(train=c['counts']['common']+c['counts']['route']+c['counts']['construction']+c['counts']['hard_matchup'])
 # Train+local-validation and checkpoint-validation are accounted separately in the runner.
 assert counts['train']+counts['validation']==expected['train']+c['counts']['checkpoint_validation']
 for key in ('feedback','baseline','final','factorial'):assert counts[key]==c['counts'][key],(key,counts[key],c['counts'][key])
 assert counts['style']==read(OUT/'style-summary.json')['simulations']==3240
 report=dict(cards_unchanged=True,battle_and_planner_sources_match_training=True,all_15_decks_legal=True,final_pairings=120,final_unique_seeds=24000,stage_seed_sets_disjoint=True,rows_by_stage=dict(counts),unique_seeds_by_stage={k:len(v) for k,v in groups.items()},selected_before_final=True,draft_frozen_before_its_final_test=True,
  total_simulations=sum(c['counts'].values())+counts['draft']+counts['hierarchy']+counts['style']+read(OUT/'trace-audit.json')['simulation_count'])
 if (OUT/'parallel-resume-partial.zip').exists():
  import zipfile
  compared=0
  with zipfile.ZipFile(OUT/'parallel-resume-partial.zip') as z:
   for name in z.namelist():
    if not name.endswith('.json.gz'):continue
    before=json.loads(gzip.decompress(z.read(name)))
    with gzip.open(OUT/name,'rt',encoding='utf-8') as f:after=json.load(f)
    if name.endswith('shared-learning/all.json.gz'):
     before['training'].sort(key=lambda x:x['candidate']);after['training'].sort(key=lambda x:x['candidate'])
    assert before==after,('resumed candidate changed',name)
    compared+=1
  report['parallel_resume_identical_completed_jobs']=compared
 save(OUT/'integrity-audit.json',report);print(json.dumps(report),flush=True)
if __name__=='__main__':main()
