"""Six chronological learning rounds followed by a sealed test, with no card edits."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from itertools import combinations
import argparse,copy,hashlib,json,random,shutil,time
from learning_core import *
from learning_jobs import common_job,route_job,construction_job,matchup_job,league_job,league_chunk_job,gauntlet_job,factorial_job

def parallel(pool,fn,tasks,label):
 jobs=[pool.submit(fn,*args) for args in tasks];found=[];start=time.time();last=start
 for f in as_completed(jobs):
  found.append(f.result())
  if time.time()-last>20 or len(found)==len(jobs):
   print(f'{label}: {len(found)}/{len(jobs)} ({time.time()-start:.0f}s)',flush=True);last=time.time()
 return found

def initialize():
 initial=copy.deepcopy(C.DECKS)
 ctx=dict(card_version='1.0',decks=initial,initial_decks=copy.deepcopy(initial),common={k:getattr(P.Policy(),k) for k in COMMON_KEYS},routes={},pairs={})
 return ctx

def league_parallel(pool,ctx,r,n,stage,label):
 # Splitting changes scheduling only. Each sample keeps its original seed and seat.
 ordered=sorted(PAIRS,key=lambda p:(p[0].startswith('earth') and p[1].startswith('earth'),p[0]==p[1]),reverse=True)
 tasks=[(ctx,r,a,b,start,min(20,n-start),stage) for a,b in ordered for start in range(0,n,20)]
 parts=parallel(pool,league_chunk_job,tasks,label);groups={}
 for part in parts:groups.setdefault((part['a'],part['b']),[]).append(part)
 results=[]
 for a,b in PAIRS:
  chunks=sorted(groups[a,b],key=lambda x:x['start']);rows=[row for chunk in chunks for row in chunk['rows']]
  assert len(rows)==n
  result=dict(a=a,b=b,rows=rows,policies=chunks[0]['policies']);log_job(stage,r,a+'__'+b,result);results.append(result)
 return results

def run(rounds=6,workers=20,feedback_games=60,final_games=200,resume=False):
 OUT.mkdir(parents=True,exist_ok=True);card_sha=hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()
 initial=initialize();ctx=copy.deepcopy(initial);learned={};history=[];counts=Counter();previous=None;chosen=0;best=-1
 config=dict(rounds=rounds,workers=workers,feedback_games=feedback_games,final_games=final_games,card_sha256=card_sha,seed_namespace='v1learn',algorithm='hierarchical priors + paired greedy selection + held-out final',
  deck_constraints='18-26 unique; mono-element+generic; 1 specialization+1 route+2 other legendary; >=3 common,>=3 rare,>=4 epic; avg cost<=2.05; draw>=2 search>=2 shuffle>=1',
  frozen_cards=True,final_test_must_not_select_checkpoint=True,unsupported_cards=sorted(UNSUPPORTED))
 if not resume:
  assert not (OUT/'experiment.json').exists(),'Use --resume to continue an existing run.'
  save(OUT/'experiment.json',config);save(OUT/'initial-context.json',initial)
  for name in ('engine.py','planner.py','cards.py','controller.py','learning_core.py','learning_jobs.py','train_v1.py'):
   p=ROOT/'tools/round_robin'/name;target=OUT/'sources'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(p,target)
 else:
  assert read(OUT/'experiment.json')['card_sha256']==card_sha
  completed=[p for p in OUT.glob('round_*/checkpoint.json')]
  if completed:
   last=max(completed,key=lambda p:p.parent.name);state=read(last);ctx=state['context'];history=state['history'];learned=state['learned_cards'];counts=Counter(state['counts']);previous=read(last.parent/'summary.json');chosen=state['chosen'];best=state['best']
  for name in ('learning_core.py','learning_jobs.py','train_v1.py','cards.py'):
   p=ROOT/'tools/round_robin'/name;target=OUT/'sources-resume-parallel'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(p,target)
 initial=read(OUT/'initial-context.json') if (OUT/'initial-context.json').exists() else initial
 start=time.time();begin=len(history)+1
 with ProcessPoolExecutor(max_workers=workers) as pool:
  if previous is None:
   baseline=league_parallel(pool,ctx,0,40,'baseline','new v1.0 baseline')
   previous=summary(baseline);save(OUT/'round_00/summary.json',previous);save(OUT/'round_00/context.json',ctx);counts['baseline']+=4800
  for r in range(begin,rounds+1):
   print(f'ROUND {r}/{rounds}: shared -> route -> construction -> hard matchups -> fresh feedback',flush=True)
   folder=OUT/f'round_{r:02d}';folder.mkdir(exist_ok=True)
   rng=random.Random(seed('shared-candidate',r,'all','all',0));vals=[ctx['common']]
   for _ in range(2):
    v=dict(ctx['common'])
    for k in rng.sample(list(COMMON_KEYS),2):v[k]=rng.choice(P.RANGES[k])
    vals.append(v)
   opponents=[(a,IDS[(i+4)%15]) for i,a in enumerate(IDS)]
   cr=parallel(pool,common_job,[(ctx,r,i,v,opponents,2,'common-train') for i,v in enumerate(vals)],f'R{r} common training')
   win=max(cr,key=lambda x:x['score'])['candidate']
   cv=parallel(pool,common_job,[(ctx,r,i,vals[i],[(a,IDS[(j+8)%15]) for j,a in enumerate(IDS)],4,'common-valid') for i in (0,win)],f'R{r} common validation')
   cv.sort(key=lambda x:0 if x['candidate']==0 else 1)
   gain,se=paired_gain(cv[0]['rows'],cv[-1]['rows']);accept=win!=0 and gain>=max(.015,.35*se)
   if accept:ctx['common']=vals[win]
   log_job('shared-learning',r,'all',dict(training=cr,validation=cv,accepted=accept,gain=gain,standard_error=se,chosen=ctx['common']));counts['common']+=sum(len(x['rows']) for x in cr+cv)
   rr=parallel(pool,route_job,[(ctx,r,a) for a in IDS],f'R{r} route learning')
   for x in rr:ctx['routes'][x['a']]=x['policy'];counts['route']+=x['simulations']
   # Worst opponents come only from the previous feedback, never the current final set.
   tails={a:sorted((b for b in IDS if b!=a),key=lambda b:previous['matrix'][a][b]['score'])[:3] for a in IDS}
   dr=parallel(pool,construction_job,[(ctx,r,a,tails[a],learned) for a in IDS],f'R{r} construction')
   for x in dr:
    ctx['decks'][x['a']]=x['deck'];assert legal(x['deck']);counts['construction']+=x['simulations']
    for u in x['card_updates']:
     e=learned.setdefault(u['name'],dict(n=0,reward=0));e['n']+=1;e['reward']+=u['reward']
   severe={'|'.join(sorted((x['a'],x['b']))) for x in previous['severe']}
   # Guard against forgetting: recently severe pairs remain eligible for extra practice.
   if history:severe|=set(history[-1]['severe_keys'])
   mr=parallel(pool,matchup_job,[(ctx,r,a,b,'|'.join(sorted((a,b))) in severe) for a,b in PAIRS],f'R{r} matchup specialization')
   for x in mr:
    ctx['pairs']['|'.join(sorted((x['a'],x['b'])))]=dict(zip((x['a'],x['b']),x['policies']));counts['hard_matchup']+=x['simulations']
   feedback=league_parallel(pool,ctx,r,feedback_games,'feedback',f'R{r} feedback league')
   s=summary(feedback);save(folder/'summary.json',s);counts['feedback']+=len(PAIRS)*feedback_games
   challenge=parallel(pool,gauntlet_job,[(ctx,r,a,8) for a in IDS],f'R{r} checkpoint validation')
   validation=statistics.mean(x['score'] for x in challenge);tail=statistics.mean(sorted(x['score'] for x in challenge)[:4]);objective=validation+.2*tail
   counts['checkpoint_validation']+=sum(len(x['rows']) for x in challenge)
   if objective>best+.005:best=objective;chosen=r
   record=dict(round=r,common_accepted=accept,route_accepts=sum(x['accepted'] for x in rr),deck_accepts=sum(x['accepted'] for x in dr),deck_moves=[{k:x[k] for k in ('a','accepted','move','gain','standard_error')} for x in dr],
    hard_pairs_trained=len(severe),hard_policy_accepts=sum(sum(x['accepted']) for x in mr),severe_keys=sorted(severe),feedback_severe=s['severe_count'],gauntlet_score=validation,gauntlet_tail=tail,selection_objective=objective,
    route_validation=[{k:x[k] for k in ('a','accepted','gain')} for x in rr])
   history.append(record);save(folder/'context.json',ctx);save(folder/'checkpoint.json',dict(context=ctx,history=history,learned_cards=learned,counts=dict(counts),chosen=chosen,best=best));save(OUT/'progress.json',dict(round=r,history=history,counts=dict(counts),chosen=chosen))
   previous=s
   print(json.dumps(dict(round=r,deck_accepts=record['deck_accepts'],route_accepts=record['route_accepts'],severe=s['severe_count'],checkpoint_score=validation,selected=chosen,total_games=sum(counts.values()),elapsed_seconds=time.time()-start)),flush=True)
  # The selection is frozen before any final test outcome is produced.
  selected=read(OUT/f'round_{chosen:02d}/context.json');save(OUT/'selection.json',dict(chosen_round=chosen,criterion='fixed baseline gauntlet validation mean + 0.2 lower quartile; no final seed access',objective=best,selected_context_sha256=digest(selected)))
  save(OUT/'selected-context.json',selected)
  final=league_parallel(pool,selected,99,final_games,'final','SEALED final test')
  s=summary(final);save(OUT/'final-summary.json',s);counts['final']+=len(PAIRS)*final_games
  factorial=parallel(pool,factorial_job,[(selected,initial,a,8) for a in IDS],'SEALED deck/AI factorial test')
  counts['factorial']+=15*14*8*4
  arms={}
  for d in (False,True):
   for p in (False,True):
    rows=[row for x in factorial for arm in x['arms'] if arm['deck_changed']==d and arm['ai_changed']==p for row in arm['rows']]
    arms[f'deck{int(d)}_ai{int(p)}']=dict(n=len(rows),score=score(rows),win_rate=strict(rows))
  save(OUT/'factorial-summary.json',arms)
  assert hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()==card_sha
  save(OUT/'completion.json',dict(completed=True,rounds=rounds,selected=chosen,counts=dict(counts),total_simulations=sum(counts.values()),card_sha256=card_sha,elapsed_seconds=time.time()-start,final_severe=s['severe_count'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'sources').glob('*.py')}))
  print('COMPLETE '+json.dumps(read(OUT/'completion.json')),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--rounds',type=int,default=6);p.add_argument('--workers',type=int,default=20);p.add_argument('--feedback-games',type=int,default=60);p.add_argument('--final-games',type=int,default=200);p.add_argument('--resume',action='store_true');a=p.parse_args()
 run(a.rounds,a.workers,a.feedback_games,a.final_games,a.resume)
