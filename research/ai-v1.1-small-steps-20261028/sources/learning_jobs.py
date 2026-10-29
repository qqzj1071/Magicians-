"""Independent training tasks. Card inputs and chosen own deck are never opponent-specific."""
from learning_core import *

def common_job(ctx,r,index,values,opponents,n,stage):
 candidate=copy.deepcopy(ctx);candidate['common']=values;candidate['pairs']={};rows=[]
 for a,b in opponents:
  out=batch(candidate,a,b,stage,r,'shared',n,base_policy(candidate,a,b),base_policy(ctx,b,a))
  rows+=out
 return dict(candidate=index,values=values,rows=rows,score=score(rows))

def route_job(ctx,r,a):
 install(ctx);base=base_policy(ctx,a,IDS[(IDS.index(a)+1)%15]);rng=random.Random(seed('route-candidate',r,a,'all',0))
 keys=[k for k in P.RANGES if k not in COMMON_KEYS]
 defensive=replace(base,cleanse=max(.5,base.cleanse),penetration_value=min(3,base.penetration_value*1.3),counterplay_value=2)
 options=[base,mutate(base,rng,3,keys),defensive];opps=balanced_opponents(a,r,5);train=[]
 for p in options:
  rows=[]
  for b in opps:rows+=batch(ctx,a,b,'route-train',r,a,2,replace(p,opponent=b),base_policy(ctx,b,a),True)
  train.append(rows)
 best=max(range(3),key=lambda i:score(train[i]));candidates=[base,options[best]];valid=[]
 for p in candidates:
  rows=[]
  for b in IDS:
   if b!=a:rows+=batch(ctx,a,b,'route-valid',r,a,2,replace(p,opponent=b),base_policy(ctx,b,a),True)
  valid.append(rows)
 gain,se=paired_gain(valid[0],valid[1]);accepted=best!=0 and gain>=max(.015,.35*se)
 chosen=options[best] if accepted else base
 result=dict(a=a,policy=asdict(chosen),candidates=[asdict(p) for p in options],training=train,validation=valid,training_best=best,gain=gain,standard_error=se,accepted=accepted)
 log_job('route-learning',r,a,result)
 return dict(a=a,policy=asdict(chosen),accepted=accepted,gain=gain,simulations=sum(map(len,train))+sum(map(len,valid)))

def construction_job(ctx,r,a,tail,learned):
 install(ctx);decks,moves=candidate_decks(ctx,a,r,tail,learned)
 opps=balanced_opponents(a,r,5)
 for b in tail[:2]:
  if b!=a and b not in opps:opps.append(b)
 train=[];objectives=[]
 for d in decks:
  local=copy.deepcopy(ctx);local['decks'][a]=d;rows=[];vals=[]
  for b in opps:
   out=batch(local,a,b,'construction-train',r,a,2,base_policy(ctx,a,b),base_policy(ctx,b,a),True);rows+=out;vals.append(score(out))
  train.append(rows);objectives.append(robust(vals))
 best=max(range(len(decks)),key=lambda i:objectives[i]);valid=[];per_opponent=[]
 for d in (decks[0],decks[best]):
  local=copy.deepcopy(ctx);local['decks'][a]=d;rows=[];vals=[]
  for b in IDS:
   if b==a:continue
   out=batch(local,a,b,'construction-valid',r,a,4,base_policy(ctx,a,b),base_policy(ctx,b,a),True);rows+=out;vals.append(score(out))
  valid.append(rows);per_opponent.append(vals)
 gain,se=paired_gain(valid[0],valid[1]);obj_gain=robust(per_opponent[1])-robust(per_opponent[0])
 accepted=best!=0 and gain>=max(.01,.3*se) and obj_gain>0
 records=[]
 # Only out-of-training validation outcomes update card rewards. Shrinkage is in ranking.
 if best:
  m=moves[best-1]
  if m['incoming']:records.append(dict(name=m['incoming'],reward=gain))
  if m['out']:records.append(dict(name=m['out'],reward=-gain))
 result=dict(a=a,decks=decks,moves=moves,training=train,training_objectives=objectives,validation=valid,validation_opponent_scores=per_opponent,training_best=best,gain=gain,standard_error=se,robust_gain=obj_gain,accepted=accepted)
 log_job('construction-learning',r,a,result)
 return dict(a=a,deck=decks[best] if accepted else decks[0],accepted=accepted,move=moves[best-1] if best else None,gain=gain,standard_error=se,card_updates=records,simulations=sum(map(len,train))+sum(map(len,valid)))

def shrink(personal,base,weight=.5):
 d={}
 for k,v in asdict(personal).items():
  b=getattr(base,k)
  if isinstance(v,(int,float)) and k not in ('lethal_candidates','basic_order'):
   d[k]=v*weight+b*(1-weight)
  else:d[k]=v
 return replace(personal,**d)

def matchup_job(ctx,r,a,b,severe):
 install(ctx);base=[base_policy(ctx,a,b),base_policy(ctx,b,a)]
 old=[policy(ctx,a,b),policy(ctx,b,a)]
 # Regularize an old specialization toward current common/route priors after every deck change.
 ps=[shrink(old[i],base[i],.5) for i in range(2)]
 if a==b:ps[1]=ps[0]
 if not severe:return dict(a=a,b=b,policies=[asdict(p) for p in ps],simulations=0,accepted=[False,False])
 rng=random.Random(seed('hard-candidate',r,a,b,0));trials=[];training=[];validations=[];accepted=[];count=0
 # Both directions learn; the losing direction receives extra candidates without changing its deck.
 for role in range(2 if a!=b else 1):
  p=ps[role];element=ctx['decks'][b if role==0 else a]['element']
  focused=replace(p,penetration_value=3,tempo_value=2.8) if element=='earth' else replace(p,cleanse=2,panic=2.5,sustain_value=1.8) if element=='poison' else replace(p,panic=2.5,counterplay_value=3) if element=='fire' else replace(p,finish_burst=2,damage=1.7,counterplay_value=3)
  opts=[p,base[role],shrink(mutate(p,rng,3),base[role],.75),shrink(focused,base[role],.75)];rs=[]
  for candidate in opts:
   out=batch(ctx,a,b,'hard-train',r,a+'|'+b,6,candidate if role==0 else ps[0],candidate if role==1 else ps[1]);rs.append(out)
  best=max(range(len(opts)),key=lambda k:score(rs[k],role))
  vals=[]
  for candidate in (p,opts[best]):vals.append(batch(ctx,a,b,'hard-valid',r,a+'|'+b,12,candidate if role==0 else ps[0],candidate if role==1 else ps[1]))
  # Difference estimate in the proper orientation, with an explicit complexity penalty.
  delta=score(vals[1],role)-score(vals[0],role)
  ok=best!=0 and delta>=.05
  if ok:ps[role]=opts[best]
  trials.append([asdict(x) for x in opts]);training.append(rs);validations.append(vals);accepted.append(ok);count+=48
 if a==b:ps[1]=ps[0]
 data=dict(a=a,b=b,candidates=trials,training=training,validation=validations,accepted=accepted,policies=[asdict(p) for p in ps],shrinkage=.75)
 log_job('hard-matchup-learning',r,a+'__'+b,data)
 return dict(a=a,b=b,policies=data['policies'],simulations=count,accepted=accepted)

def league_job(ctx,r,a,b,n,stage='feedback'):
 rows=batch(ctx,a,b,stage,r,a+'|'+b,n)
 result=dict(a=a,b=b,rows=rows,policies=[asdict(policy(ctx,a,b)),asdict(policy(ctx,b,a))])
 log_job(stage,r,a+'__'+b,result)
 return result

def league_chunk_job(ctx,r,a,b,start,n,stage='feedback'):
 rows=batch(ctx,a,b,stage,r,a+'|'+b,n,sample_start=start)
 return dict(a=a,b=b,start=start,rows=rows,policies=[asdict(policy(ctx,a,b)),asdict(policy(ctx,b,a))])

def gauntlet_job(ctx,r,a,n,stage='checkpoint-valid'):
 opps=balanced_opponents(a,0,6);rows=[]
 for b in opps:
  local=copy.deepcopy(ctx);local['decks'][b]=ctx['initial_decks'][b]
  out=batch(local,a,b,stage,r,a,n,policy(ctx,a,b),P.initial(b,a));rows+=out
 result=dict(a=a,rows=rows,score=score(rows));log_job(stage,r,a,result);return result

def factorial_job(ctx,initial,a,n=8):
 records=[]
 for b in IDS:
  if a==b:continue
  # Same opponent, seeds and seats across all four arms; cannot choose a final arm here.
  local=copy.deepcopy(ctx);local['decks'][b]=initial['decks'][b]
  for deck_changed in (False,True):
   local['decks'][a]=ctx['decks'][a] if deck_changed else initial['decks'][a]
   for ai_changed in (False,True):
    p=policy(ctx,a,b) if ai_changed else P.initial(a,b)
    rows=batch(local,a,b,'factorial-final',99,a,n,p,P.initial(b,a))
    records.append(dict(opponent=b,deck_changed=deck_changed,ai_changed=ai_changed,rows=rows))
 result=dict(a=a,arms=records);log_job('factorial-final',99,a,result);return result
