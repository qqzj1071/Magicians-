from pathlib import Path
from dataclasses import asdict
import json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,copies,export
from tools.sim_v12.panel_budget import role,budget_group,reference_rarity,bounds,value

def main():
 before=json.loads((OUT/'before-catalog/cards.json').read_text(encoding='utf-8'))['cards']
 records=json.loads((OUT/'changes.json').read_text(encoding='utf-8'))['cards']
 selected={x['name'] for x in records};changed=[]
 for name,c in CARDS.items():
  old=before[name]
  assert all(old[k]==v for k,v in asdict(c).items() if k not in ('attack','defense')),name
  if (c.attack,c.defense)!=(old['attack'],old['defense']):changed.append(name)
  lo,hi=bounds(name,c.rarity);assert lo<=value(c.cost,c.attack,c.defense)<=hi
 assert set(changed)==selected and len(changed)==5
 assert asdict(CARDS['深渊'])=={k:before['深渊'][k] for k in asdict(CARDS['深渊'])}
 assert len(CARDS)==189 and sum(copies(c) for c in CARDS.values())==707
 cn={'specialization':'专精','legendary':'传奇','epic':'史诗','rare':'稀有','common':'普通'};rn={'numeric':'数值100%','strong':'强运转70%','weak':'弱运转90%'}
 lines=['# v1.2现行189张卡牌总表','','2026-10-29。五张指定3费永久叠加牌采用稀有数值V档80%预算；水系只改奔流，深渊不变。[V规则](panel-budgets.md)。费用、效果与首次层不变。','']
 for el,label in zip((*ELEMENTS,'generic'),('火','水','土','风','毒','通用')):
  lines+=['## '+label,'','|品质|卡牌|费|攻|防|首次层|V档|V值|效果|','|---|---|---:|---:|---:|---:|---|---:|---|']
  for c in CARDS.values():
   group='永久叠加：稀有80%' if budget_group(c.name)=='three_cost_permanent' else rn[role(c.name)]
   if c.element==el:lines.append(f'|{cn[c.rarity]}|{c.name}|{c.cost}|{c.attack}|{c.defense}|{c.layers}|{group}|{float(value(c.cost,c.attack,c.defense)):.3f}|{c.text}|')
  lines.append('')
 (ROOT/'docs/cards-v1.2/catalogue.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 export(OUT)
 result=dict(cards=189,stock=707,changed_names=sorted(changed),all_other_panels_unchanged=True,abyss_unchanged=True,
  all_cost_text_layer_identity_and_effects_unchanged=True,target_band=[6,7.2],selected_value=7.,new_tournaments=0)
 (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
