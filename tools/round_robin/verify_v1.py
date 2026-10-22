"""Check frozen release, numeric budgets, all card transactions and deterministic battles."""
from pathlib import Path
from dataclasses import asdict
import sys,json,hashlib
import cards as C,engine as E,planner as P,controller
from numeric_standards import validate
ROOT=C.ROOT
def canon(x):
 if isinstance(x,dict):return {k:canon(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [canon(v) for v in x]
 if isinstance(x,(set,frozenset)):return sorted(canon(v) for v in x)
 if isinstance(x,E.Q):return str(x)
 return x
def digest(x):return hashlib.sha256(json.dumps(canon(x),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 assert E.RULE_VERSION==C.CATALOG['version']=='1.0'
 assert len(C.CARDS)==253 and '净化药剂' not in C.CARDS
 validate(C.PARAMS)
 budgets=dict(common=(4,4.5),rare=(8,9.5),epic=(12,14),legendary=(18,21),specialization=(20,24));groups={}
 for c in C.CARDS.values():
  v=c.attack+1.5*c.defense;lo,hi=budgets[c.rarity];assert lo<=v<=hi,c.name;groups.setdefault(c.rarity,[]).append(v)
 for vs in groups.values():assert max(vs)/min(vs)<=1.2
 migration=json.loads((ROOT/'releases/v1.0/migration.json').read_text(encoding='utf-8'))
 fingerprint={n:{k:v for k,v in asdict(c).items() if k!='text'} for n,c in C.CARDS.items()}
 assert hashlib.sha256(json.dumps(fingerprint,ensure_ascii=False,sort_keys=True).encode()).hexdigest()==migration['previous_numeric_fingerprint']
 evidence=json.loads((ROOT/'releases/v1.0/parity.json').read_text(encoding='utf-8'))
 for n,c in C.CARDS.items():
  s=E.State(c.element if c.element!='generic' else 'water',hp=600,energy=30,layers=5,spec=True,shield=E.Q(100),ember=3,tide=E.Q(100),poison=3)
  s.route=next((d['route'] for d in C.DECKS.values() if d['element']==s.element),'')
  e=E.State('poison',hp=600,layers=5,spec=True,shield=E.Q(100),poison=5)
  assert digest(asdict(E.card_plan([s,e],0,n,200)))==evidence['card_plans'][n],n
 # The release's reference lists are immutable; active research lists may evolve.
 active_decks=dict(C.DECKS)
 reference=json.loads((ROOT/'decks/decks.json').read_text(encoding='utf-8'))
 C.DECKS.clear();C.DECKS.update({d['id']:d for d in reference['decks']})
 try:
  for b in evidence['battles']:
   r=E.simulate(b['a'],b['b'],b['seed'],P.initial(b['a'],b['b']),P.initial(b['b'],b['a']))
   assert digest(r)==b['result_sha256'],(b['a'],b['b'])
 finally:
  C.DECKS.clear();C.DECKS.update(active_decks)
 for a in C.DECKS:
  for b in C.DECKS:controller.policy_for(a,b)
 manifest=ROOT/'releases/v1.0/manifest.json'
 if manifest.exists():
  # The distributed package remains immutable, while AI/deck documentation is live.
  import zipfile
  with zipfile.ZipFile(ROOT/'releases/Magicians-cards-v1.0.zip') as z:
   for path,h in json.loads(manifest.read_text(encoding='utf-8'))['files'].items():
    assert hashlib.sha256(z.read(path)).hexdigest()==h,path
    if path.startswith(('docs/cards/','docs/combat/')) or path=='releases/v1.0/cards.json':
     assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
 result=dict(version='1.0',cards=253,card_numeric_identity=True,transaction_parity_checks=253,deterministic_battle_parity_checks=15,policy_bindings=225,numeric_grid_and_budgets=True)
 print(json.dumps(result,ensure_ascii=False));return result
if __name__=='__main__':main()
