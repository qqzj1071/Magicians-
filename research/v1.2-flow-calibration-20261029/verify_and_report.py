from pathlib import Path
from dataclasses import asdict
from collections import Counter
import json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,copies,export
from tools.sim_v12.panel_budget import RULES,role,bounds,value

def main():
 before=json.loads((OUT/'before-catalog/cards.json').read_text(encoding='utf-8'))['cards']
 changes=json.loads((OUT/'calibration.json').read_text(encoding='utf-8'))
 assert before.keys()==CARDS.keys()
 actual_changes=0
 for n,c in CARDS.items():
  old=before[n];now=asdict(c)
  assert all(old[k]==v for k,v in now.items() if k not in ('attack','defense')),n
  actual_changes+=(c.attack,c.defense)!=(old['attack'],old['defense'])
  lo,hi=bounds(n,c.rarity);assert lo<=value(c.cost,c.attack,c.defense)<=hi,n
 assert actual_changes==57 and len(CARDS)==189 and sum(copies(c) for c in CARDS.values())==707
 old_damage=json.loads((OUT/'before-damage.json').read_text(encoding='utf-8'))
 live_damage=json.loads((ROOT/'tools/sim_v12/rules/damage.json').read_text(encoding='utf-8'))
 for r in range(9,81):assert old_damage['table'][str(r)]==live_damage['table'][str(r)]
 # Generate a complete current catalogue without changing six machine source tables.
 cn={'specialization':'专精','legendary':'传奇','epic':'史诗','rare':'稀有','common':'普通'}
 rn={'numeric':'数值100%','strong':'强运转70%','weak':'弱运转90%'}
 lines=['# v1.2现行189张卡牌总表','','2026-10-29。运转牌按统一70%/90%分档校准；[V规则](panel-budgets.md)。首次元素层每场按实例仅一次，效果与费用不变。','']
 for e,label in zip((*ELEMENTS,'generic'),('火','水','土','风','毒','通用')):
  lines+=['## '+label,'','|品质|卡牌|费|攻|防|首次层|V档|V值|效果|','|---|---|---:|---:|---:|---:|---|---:|---|']
  for c in CARDS.values():
   if c.element==e:lines.append(f'|{cn[c.rarity]}|{c.name}|{c.cost}|{c.attack}|{c.defense}|{c.layers}|{rn[role(c.name)]}|{float(value(c.cost,c.attack,c.defense)):.3f}|{c.text}|')
  lines.append('')
 (ROOT/'docs/cards-v1.2/catalogue.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 rows=['# 65张运转牌的统一V校准','','32张强运转、33张弱运转；57张面板变化，8张因整数取值维持原面板但在新档位区间内。费用与卡牌效果均未改。',
  '弱势元素不另外开区间；本轮也未据旧胜率额外增强毒系或改机制，避免混入额外变量。','',
  '|卡牌|档位|旧攻/防|新攻/防|旧V|新V|新V区间|','|---|---|---:|---:|---:|---:|---|']
 for c in changes['cards_detail']:
  lo,hi=bounds(c['name'],c['rarity'])
  rows.append(f"|{c['name']}|{rn[c['role']]}|{c['old_attack']}/{c['old_defense']}|{c['attack']}/{c['defense']}|{c['old_value']:.3f}|{c['value']:.3f}|{float(lo):g}—{float(hi):g}|")
 (OUT/'panels.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
 export(OUT)
 result=dict(cards=189,stock=707,role_counts=dict(Counter(RULES['card_roles'].values())),changed_panels=actual_changes,
  unchanged_costs_effects_layers_and_card_identity=True,rounds_9_plus_damage_unchanged=True,new_tournaments=0)
 (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
