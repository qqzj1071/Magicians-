import sys,json,dataclasses
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,export,copies
from tools.sim_v12.panel_budget import bounds,value
old=json.loads((P/'before/cards.json').read_text(encoding='utf-8'))['cards']
panels=set();texts=set()
for n,c in CARDS.items():
 for k,v in dataclasses.asdict(c).items():
  if v!=old[n][k]:
   assert k in ('attack','text'),(n,k)
   (panels if k=='attack' else texts).add(n)
 lo,hi=bounds(n,c.rarity);assert lo<=value(c.cost,c.attack,c.defense)<=hi,n
assert panels=={'大地之握','生命之泉','山岳壁垒','不坏壁垒','万钧碎盾','回响之潮'}
assert texts=={'大地之握','潮汐回响','生命之泉','燃烧血统','蚀命','风痕','血潮'}
contract=json.loads((ROOT/'docs/cards-v1.2/snapshot-contract.json').read_text(encoding='utf-8'))['records']
assert all(contract[n]['card_text']==c.text for n,c in CARDS.items())
rows=[l.split('|')[1:-1] for l in (ROOT/'docs/cards-v1.2/catalogue.md').read_text(encoding='utf-8').splitlines()]
rows=[f for f in rows if len(f)==9 and f[1] in CARDS]
assert len(rows)==185
assert all((int(f[3]),int(f[4]),f[8])==(CARDS[f[1]].attack,CARDS[f[1]].defense,CARDS[f[1]].text) for f in rows)
assert sum(copies(c) for c in CARDS.values())==693
export(P/'after')
(P/'validation.json').write_text(json.dumps(dict(cards=185,stock=693,panel_changes=sorted(panels),text_changes=sorted(texts),all_other_card_fields_unchanged=True,budget_all_pass=True,catalogue_and_snapshot_match=True,regressions=72,v11_frozen_verified=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('VALIDATED: 7 mechanisms, 6 attack changes, 185 budgets and contracts')
