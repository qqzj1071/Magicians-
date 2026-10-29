"""Contextual offer ranking learned from construction validation, with a held-out draft test."""
from dataclasses import asdict
import argparse,copy,hashlib,json,math,random,statistics
from concurrent.futures import ProcessPoolExecutor,as_completed
from learning_core import *

def vector(n,d,needs):return card_features(n,d['element'],d['route'],needs) if n else {k:0 for k in card_features(next(iter(C.CARDS)),d['element'],d['route'],needs)}
def fit(records,keys,lam=12):
 # Small ridge model, solved by stable coordinate descent; no dependency on external ML packages.
 weights={k:0.0 for k in keys}
 for _ in range(120):
  for key in keys:
   numerator=denominator=0
   for x,y in records:
    residual=y-sum(weights[k]*x[k] for k in keys if k!=key)
    numerator+=x[key]*residual;denominator+=x[key]*x[key]
   weights[key]=numerator/(denominator+lam)
 return weights
def mse(records,w):return statistics.mean((sum(w[k]*x[k] for k in w)-y)**2 for x,y in records) if records else 0

def train_offer_model():
 initial=read(OUT/'initial-context.json');rows=[];card_rewards={}
 folders=sorted(OUT.glob('round_*/construction-learning/*.json.gz'))
 for path in folders:
  with gzip.open(path,'rt',encoding='utf-8') as f:r=json.load(f)
  best=r['training_best']
  if not best:continue
  a=r['a'];move=r['moves'][best-1];d=r['decks'][0];needs={e:.2 for e in ('fire','water','earth','wind','poison')}
  vi=vector(move['incoming'],d,needs);vo=vector(move['out'],d,needs);x={k:vi[k]-vo[k] for k in vi}
  rows.append(dict(element=d['element'],route=a,round=int(path.parents[1].name[-2:]),features=x,reward=r['gain'],accepted=r['accepted'],move=move))
  if move['incoming']:
   e=card_rewards.setdefault(move['incoming'],dict(n=0,reward=0));e['n']+=1;e['reward']+=r['gain']
 keys=list(rows[0]['features']);records=[(x['features'],x['reward']) for x in rows];cv=[]
 for element in ('fire','water','earth','wind','poison'):
  train=[(x['features'],x['reward']) for x in rows if x['element']!=element];valid=[(x['features'],x['reward']) for x in rows if x['element']==element]
  weights=fit(train,keys);cv.append(dict(held_out_element=element,n=len(valid),ridge_mse=mse(valid,weights),zero_mse=mse(valid,{k:0 for k in keys})))
 good=statistics.mean(x['ridge_mse'] for x in cv)<statistics.mean(x['zero_mse'] for x in cv)
 model=dict(schema_version=1,card_version='1.0',card_sha256=hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),training_records=len(rows),
  ridge_lambda=12,weights=fit(records,keys) if good else {k:0 for k in keys},ridge_enabled=good,leave_one_element_out=cv,card_rewards=card_rewards,
  coefficient_scale=4,uncertainty_shrinkage=8,uses_final_test=False,scope='candidate ranking and add/remove/swap of mono-element+generic 18-26 card research decks; not a finalized campaign draft flow')
 save(ROOT/'docs/ai/construction-model.json',model);save(OUT/'offer-training-records.json',rows)
 return model

def offer_score(deck,name,model,needs=None):
 needs=needs or {e:.2 for e in ('fire','water','earth','wind','poison')}
 ns=[e['name'] for e in deck['entries']];c=C.CARDS[name]
 if c.element not in (deck['element'],'generic') or name in UNSUPPORTED or name in ns or c.kind in ('specialization','route_legendary'):return None
 f=vector(name,deck,needs);rank=card_rank(name,deck,needs,model['card_rewards'])
 rank+=model['coefficient_scale']*sum(f[k]*v for k,v in model['weights'].items())
 # Diminishing returns and the actual current curve matter before a complete deck exists.
 for tag,pool,minimum in [('draw',DRAW,2),('search',SEARCH,2),('shuffle',SHUFFLE,1)]:
  count=len(set(ns)&pool)
  if name in pool:rank+=max(0,minimum-count)*2.5
 if ns:
  avg=sum(C.CARDS[n].cost for n in ns)/len(ns)
  if avg>1.7 and c.cost>=2:rank-=2*(avg-1.7)*c.cost
  if len(ns)>=20:rank-=.7
 return rank

def choose_offer(deck,offer,model,needs=None,allow_replace=True):
 options=[];ns=[e['name'] for e in deck['entries']]
 for n in offer:
  rank=offer_score(deck,n,model,needs)
  if rank is None:continue
  c=C.CARDS[n];replacements=[None]
  if c.rarity=='legendary' and sum(C.CARDS[k].rarity=='legendary' for k in ns)>=3:
   replacements=[k for k in ns if C.CARDS[k].rarity=='legendary' and C.CARDS[k].kind!='route_legendary'] if allow_replace else []
  elif len(ns)>=26:
   replacements=[k for k in ns if not C.CARDS[k].ability] if allow_replace else []
  for old in replacements:
   if old:
    base=copy.deepcopy(deck);base['entries']=[e for e in deck['entries'] if e['name']!=old]
    rank_delta=rank-(offer_score(base,old,model,needs) or 0)
   else:rank_delta=rank
   proposed=with_names(deck,[k for k in ns if k!=old]+[n])
   if len(ns)>=18 and old and not legal(proposed):continue
   options.append(dict(card=n,replace=old,score=rank_delta,features=vector(n,deck,needs or {}),experience_n=model['card_rewards'].get(n,{}).get('n',0)))
 return sorted(options,key=lambda x:(x['score'],x['card']),reverse=True)

def generate_deck(template,model,draft_seed,learned=True):
 rng=random.Random(draft_seed);d=copy.deepcopy(template);ns=[d['specialization'],d['route']];d=with_names(d,ns);log=[]
 # This is a reproducible offer curriculum, not a claim about final in-game round rules.
 legend=[n for n,c in C.CARDS.items() if c.rarity=='legendary' and c.kind!='route_legendary' and n not in UNSUPPORTED and c.element in (d['element'],'generic')]
 for _ in range(2):
  pool=[n for n in legend if n not in ns];offer=rng.sample(pool,min(5,len(pool)))
  ranked=choose_offer(d,offer,model) if learned else [dict(card=n,replace=None,score=0) for n in offer]
  pick=ranked[0]['card'];ns.append(pick);d=with_names(d,ns);log.append(dict(offer=offer,choice=pick,ranking=ranked))
 pool=[n for n,c in C.CARDS.items() if c.kind not in ('specialization','route_legendary') and c.rarity!='legendary' and c.element in (d['element'],'generic')]
 for step in range(18):
  available=[n for n in pool if n not in ns];counts=Counter(C.CARDS[n].rarity for n in ns);m=deck_metrics(d)
  missing=[tier for tier,target in [('common',3),('rare',3),('epic',4)] if counts[tier]<target]
  if step>=12 and missing:available=[n for n in available if C.CARDS[n].rarity in missing]
  for tag,group,mincount in [('draw',DRAW,2),('search',SEARCH,2),('shuffle',SHUFFLE,1)]:
   if step>=15 and m['resources'][tag]<mincount:
    q=[n for n in available if n in group]
    if q:available=q;break
  if step>=12 and m['average_cost']>1.85:
   q=[n for n in available if C.CARDS[n].cost<=1]
   if q:available=q
  offer=rng.sample(available,min(5,len(available)))
  ranked=choose_offer(d,offer,model) if learned else [dict(card=n,replace=None,score=0) for n in offer]
  pick=ranked[0]['card'];ns.append(pick);d=with_names(d,ns);log.append(dict(offer=offer,choice=pick,ranking=ranked))
 return d,log

def draft_test_job(ctx,a,model):
 out=[]
 for k in range(3):
  for learned in (False,True):
   d,log=generate_deck(ctx['decks'][a],model,seed('draft-offer-final',99,a,'draft',k),learned)
   valid=legal(d);rows=[]
   if valid:
    local=copy.deepcopy(ctx);local['decks'][a]=d
    for b in balanced_opponents(a,0,6):rows+=batch(local,a,b,'draft-battle-final',99,a+':'+str(k),6,policy(ctx,a,b),policy(ctx,b,a))
   out.append(dict(learned=learned,draft=k,legal=valid,deck=d,offers=log,rows=rows))
 result=dict(a=a,tests=out);log_job('draft-final',99,a,result);return result

def final_draft_test(workers=20):
 model=train_offer_model();ctx=read(OUT/'selected-context.json');save(OUT/'draft-model-frozen.json',dict(model_sha256=digest(model),final_inputs_fixed=True))
 results=[]
 with ProcessPoolExecutor(max_workers=workers) as pool:
  fs=[pool.submit(draft_test_job,ctx,a,model) for a in IDS]
  for f in as_completed(fs):results.append(f.result())
 report={}
 for learned in (False,True):
  tests=[x for r in results for x in r['tests'] if x['learned']==learned];rows=[row for x in tests for row in x['rows']]
  report['learned' if learned else 'random']=dict(decks=len(tests),legal_decks=sum(x['legal'] for x in tests),games=len(rows),score=score(rows),strict_win_rate=strict(rows))
 save(OUT/'draft-final-summary.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':
 from concurrent.futures import ProcessPoolExecutor
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=20);args=p.parse_args();final_draft_test(args.workers)
