"""Reproducible public-information learning helpers; never writes card values."""
from dataclasses import asdict,replace
from pathlib import Path
from collections import Counter
import copy,gzip,hashlib,json,math,random,statistics
import cards as C,engine as E,planner as P
ROOT=C.ROOT;OUT=ROOT/'research/ai-v1.0-learning'
IDS=list(C.DECKS);PAIRS=[(a,b) for i,a in enumerate(IDS) for b in IDS[i:]]
COMMON_KEYS=('core_priority','startup_resource','operation_layer','finish_ratio','finish_burst','budget_fit','cost_power')
DRAW={'禁忌知识','通晓','灵感涌现','过牌','翻阅','速读','整理','循环','余火','灰烬账本','余烬引擎','回流','毒涌','应急整备'}
SEARCH={'禁咒目录','命运检索','大检索','小检索','翻找','寻物','检索附魔','火种翻找','火种库','水之低语','寻岩','寻风','寻毒','壁垒之心'}
SHUFFLE={'洗牌','重洗','循环','回火','灰烬重生','余烬引擎'}
UNSUPPORTED={'元素熔炉','魔法阵核心'}

def save(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def seed(stage,round_number,item,opponent,sample):
 return int.from_bytes(hashlib.sha256(f'v1learn:{stage}:{round_number}:{item}:{opponent}:{sample}'.encode()).digest()[:8],'big')%(2**53)
def install(ctx):
 C.DECKS.clear();C.DECKS.update(copy.deepcopy(ctx['decks']))
def base_policy(ctx,a,b):
 p=P.initial(a,b)
 if a in ctx.get('routes',{}):p=replace(p,**{k:v for k,v in ctx['routes'][a].items() if k not in ('own','opponent')})
 if ctx.get('common'):p=replace(p,**ctx['common'])
 return replace(p,own=a,opponent=b)
def policy(ctx,a,b):
 e=ctx.get('pairs',{}).get('|'.join(sorted((a,b))))
 return P.Policy(**e[a]) if e and a in e else base_policy(ctx,a,b)
def game(a,b,s,pa,pb,flip=False,validate=False,trace=False):
 if flip and a!=b:r=E.simulate(b,a,s,pb,pa,trace=trace,validate=validate)
 else:r=E.simulate(a,b,s,pa,pb,trace=trace,validate=validate,stream_swap=flip and a==b)
 keys=(a,b) if a!=b else (a+'@A',a+'@B')
 winner=-1 if r['winner']=='draw' else keys.index(r['winner'])
 players=[]
 for key in keys:
  p=r['players'][key];activ=p['activations'];core=[C.DECKS[a if key==keys[0] else b]['specialization'],C.DECKS[a if key==keys[0] else b]['route']]
  complete=all(n in activ for n in core)
  players.append({k:p[k] for k in ('hp','shield','attack','defense','plays','activations','wasted','granted','phase_counts','phase_changes','lethal_predictions') if k in p}|dict(core_complete=complete,core_time=max(activ[n] for n in core) if complete else None))
 row=dict(seed=s,flip=flip,winner=winner,time=r['time'],players=players)
 if trace:row['log']=r['log']
 return row
def batch(ctx,a,b,stage,r,item,n,pa=None,pb=None,old_opponent=False):
 install(ctx);rows=[]
 pa=pa or policy(ctx,a,b);pb=pb or policy(ctx,b,a)
 for k in range(n):
  # A history opponent is explicitly installed before play; never borrowed as a hidden counter-deck.
  if old_opponent and a!=b and k%3==0:C.DECKS[b]=copy.deepcopy(ctx['initial_decks'][b])
  else:C.DECKS[b]=copy.deepcopy(ctx['decks'][b])
  rows.append(game(a,b,seed(stage,r,item,b,k),pa,pb,k%2==1))
 return rows
def score(rows,role=0):return sum(1 if x['winner']==role else .5 if x['winner']==-1 else 0 for x in rows)/max(1,len(rows))
def strict(rows,role=0):return sum(x['winner']==role for x in rows)/max(1,len(rows))
def log_job(stage,r,key,data):
 path=OUT/f'round_{r:02d}'/stage/(key+'.json.gz');path.parent.mkdir(parents=True,exist_ok=True)
 with gzip.open(path,'wt',encoding='utf-8',compresslevel=6) as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
def mutate(p,rng,count=3,keys=None):
 keys=rng.sample(list(keys or P.RANGES),count)
 return replace(p,**{k:rng.choice(P.RANGES[k]) for k in keys})
def metrics(rows,role):
 ps=[r['players'][role] for r in rows];times=[p['core_time'] for p in ps if p['core_complete']]
 return dict(n=len(rows),win_rate=strict(rows,role),score=score(rows,role),core_completion=sum(p['core_complete'] for p in ps)/len(ps),core_time_median=statistics.median(times) if times else None,
  unused_energy=sum(p['wasted'] for p in ps)/max(1,sum(p['granted'] for p in ps)),mean_duration=statistics.mean(r['time'] for r in rows),
  phases=dict(sum((Counter(p['phase_counts']) for p in ps),Counter())),plays=dict(sum((Counter(p['plays']) for p in ps),Counter())),conditional_lethal_flags=sum(p['lethal_predictions'] for p in ps))
def wilson(w,n):
 if not n:return (0,1)
 p=w/n;z=1.96;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return c-h,c+h
def summary(results):
 cells={a:{} for a in IDS};records={a:[] for a in IDS};severe=[]
 for r in results:
  a,b=r['a'],r['b'];rows=r['rows'];n=len(rows)
  for role,(x,y) in enumerate(((a,b),(b,a))):
   w=sum(z['winner']==role for z in rows);d=sum(z['winner']==-1 for z in rows)
   if x!=y:records[x].extend((z,role) for z in rows)
   cells[x][y]=dict(n=n,wins=w,draws=d,win_rate=w/n,score=score(rows,role),ci95=wilson(w,n))
   if a==b:break
  if a!=b:
   rate=max(cells[a][b]['win_rate'],cells[b][a]['win_rate'])
   if rate>.8:severe.append(dict(a=a,b=b,strong=a if cells[a][b]['win_rate']>cells[b][a]['win_rate'] else b,rate=rate))
 ranking=[]
 for a,rs in records.items():
  w=sum(row['winner']==role for row,role in rs);d=sum(row['winner']==-1 for row,role in rs);n=len(rs)
  ranking.append(dict(deck=a,route=C.DECKS[a]['route'],n=n,wins=w,draws=d,win_rate=w/n,ci95=wilson(w,n)))
 return dict(ranking=sorted(ranking,key=lambda x:x['win_rate'],reverse=True),matrix=cells,severe=severe,severe_count=len(severe),evaluation_games=sum(len(r['rows']) for r in results))

def deck_metrics(d):
 names=[x['name'] for x in d['entries']];counts=Counter(C.CARDS[n].rarity for n in names)
 return dict(size=len(names),average_cost=sum(C.CARDS[n].cost for n in names)/len(names),cost_curve=dict(Counter(str(C.CARDS[n].cost) for n in names)),rarities=dict(counts),resources=dict(draw=len(set(names)&DRAW),search=len(set(names)&SEARCH),shuffle=len(set(names)&SHUFFLE)))
def legal(d):
 ns=[x['name'] for x in d['entries']];m=deck_metrics(d)
 if len(ns)!=len(set(ns)) or not 18<=len(ns)<=26 or m['average_cost']>2.05:return False
 if any(C.CARDS[n].element not in (d['element'],'generic') or n in UNSUPPORTED for n in ns):return False
 if sum(C.CARDS[n].kind=='specialization' for n in ns)!=1 or d['specialization'] not in ns:return False
 if sum(C.CARDS[n].rarity=='legendary' for n in ns)!=3 or sum(C.CARDS[n].kind=='route_legendary' for n in ns)!=1 or d['route'] not in ns:return False
 return all(m['resources'][k]>=v for k,v in [('draw',2),('search',2),('shuffle',1)]) and m['rarities'].get('common',0)>=3 and m['rarities'].get('epic',0)>=4 and m['rarities'].get('rare',0)>=3
def with_names(d,names):
 d=copy.deepcopy(d);d['entries']=[dict(name=n,quantity=1,group='learned') for n in names];d['metrics']=deck_metrics(d);return d
def card_features(n,element,route,needs):
 c=C.CARDS[n];text=c.text;own=c.element==element
 return dict(value=(c.attack+1.5*c.defense)/max(1,c.cost),cost=-c.cost,own=float(own),route=float(C.CATALOG['cards'][n].get('route_support')==route),draw=float(n in DRAW),search=float(n in SEARCH),shuffle=float(n in SHUFFLE),
  penetration=float('穿透' in text),cleanse=float('移除' in text or '净化' in text or n=='风眼'),heal=float('回复' in text),shield=float(n in C.SHIELDS),
  tempo=float('间隔' in text),antiheal=float('回复量降低' in text or '治疗量降低' in text),cheap=float(c.cost<=1))
def card_rank(n,d,needs,learned):
 f=card_features(n,d['element'],d['route'],needs)
 weights=dict(value=.35,cost=.2,own=2,route=1.5,draw=1.2,search=1,shuffle=.5,penetration=needs.get('earth',0)*3,cleanse=needs.get('poison',0)*2+needs.get('wind',0),heal=needs.get('fire',0),shield=needs.get('fire',0),tempo=1,antiheal=needs.get('water',0)*3,cheap=1)
 prior=sum(f[k]*v for k,v in weights.items());item=learned.get(n,dict(reward=0,n=0));shrunk=item['reward']/(item['n']+8)
 return prior+4*shrunk
def candidate_decks(ctx,a,r,tail,learned):
 d=ctx['decks'][a];ns=[x['name'] for x in d['entries']];needs=Counter(ctx['decks'][b]['element'] for b in tail);total=max(1,len(tail));needs={k:v/total for k,v in needs.items()}
 rng=random.Random(seed('construction-proposals',r,a,'none',0));pool=[n for n,c in C.CARDS.items() if c.element in (d['element'],'generic') and n not in UNSUPPORTED and c.kind not in ('specialization','route_legendary')]
 options=[d];changes=[]
 mutable=[n for n in ns if n not in (d['specialization'],d['route'])]
 for kind in range(5):
  proposed=None;move=None
  for attempt in range(50):
   if kind in (0,1):
    old=rng.choice(sorted(mutable,key=lambda n:card_rank(n,d,needs,learned))[:max(4,len(mutable)//2)])
    candidates=[n for n in pool if n not in ns and (C.CARDS[n].rarity=='legendary')==(C.CARDS[old].rarity=='legendary')]
    candidates=sorted(candidates,key=lambda n:card_rank(n,d,needs,learned),reverse=True)
    new=rng.choice(candidates[:8] if kind==0 else candidates)
    names=[new if n==old else n for n in ns];move=dict(kind='swap',out=old,incoming=new)
   elif kind==2:
    old=rng.choice([n for n in mutable if C.CARDS[n].rarity!='legendary']);names=[n for n in ns if n!=old];move=dict(kind='remove',out=old,incoming=None)
   elif kind==3:
    choices=[n for n in pool if n not in ns and C.CARDS[n].rarity!='legendary'];new=rng.choice(sorted(choices,key=lambda n:card_rank(n,d,needs,learned),reverse=True)[:12]);names=ns+[new];move=dict(kind='add',out=None,incoming=new)
   else:
    old=rng.choice([n for n in mutable if C.CARDS[n].rarity=='legendary']);choices=[n for n in pool if n not in ns and C.CARDS[n].rarity=='legendary'];new=rng.choice(choices);names=[new if n==old else n for n in ns];move=dict(kind='legendary',out=old,incoming=new)
   test=with_names(d,names)
   if legal(test) and not any(test['entries']==x['entries'] for x in options):proposed=test;break
  if proposed:options.append(proposed);changes.append(move)
 return options,changes

def balanced_opponents(a,r,n=6):
 others=[b for b in IDS if b!=a];rng=random.Random(seed('opponents',r,a,'all',0));rng.shuffle(others)
 first=[]
 for element in ('fire','water','earth','wind','poison'):
  q=next((b for b in others if C.DECKS[b]['element']==element),None)
  if q:first.append(q)
 return (first+[b for b in others if b not in first])[:n]
def robust(scores):
 vals=sorted(scores);return statistics.mean(vals)+.2*statistics.mean(vals[:max(1,len(vals)//4)])
def paired_gain(before,after):
 deltas=[(1 if a['winner']==0 else .5 if a['winner']==-1 else 0)-(1 if b['winner']==0 else .5 if b['winner']==-1 else 0) for a,b in zip(after,before)]
 return statistics.mean(deltas),statistics.stdev(deltas)/math.sqrt(len(deltas)) if len(deltas)>1 else 1
