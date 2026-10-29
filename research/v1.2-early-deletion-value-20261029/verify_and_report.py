from pathlib import Path
from dataclasses import asdict
import json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,copies,export
from tools.sim_v12.panel_budget import role,value,bounds

def main():
 data=json.loads((OUT/'panel-changes.json').read_text(encoding='utf-8'))
 before=json.loads((OUT/'before-catalog/cards.json').read_text(encoding='utf-8'))['cards']
 assert set(CARDS)==set(before)
 changed=[]
 for n,c in CARDS.items():
  old=before[n]
  assert all(old[k]==v for k,v in asdict(c).items() if k not in ('attack','defense')),n
  assert role(n)==old['panel_role'],n
  lo,hi=bounds(n,c.rarity);v=value(c.cost,c.attack,c.defense);assert lo<=v<=hi
  if (c.attack,c.defense)!=(old['attack'],old['defense']):
   changed.append(n);assert n in data['eligible'] and role(n)=='numeric'
   assert v>value(c.cost,old['attack'],old['defense'])
  if n in data['explicitly_protected'] or n not in data['eligible']:
   assert (c.attack,c.defense)==(old['attack'],old['defense']),n
 assert len(changed)==51 and len(CARDS)==189 and sum(copies(c) for c in CARDS.values())==707
 old=json.loads((OUT/'before/tools/sim_v12/rules/economy.json').read_text(encoding='utf-8'))
 new=json.loads((ROOT/'tools/sim_v12/rules/economy.json').read_text(encoding='utf-8'))
 old['implementation_profile']='growth-v7';old['deletions']['rounds_4_to_6']=[1,[1]]
 assert old==new
 rows=['# 纯即时战力牌面板上调','','按原数值档区间的上四分位附近取合法整数，已经更高者不下调。强/弱运转牌、战意等永久成长、专门资源与连锁蓄积牌不改。','',
  '|卡牌|原攻/防|现攻/防|原V|现V|变化|','|---|---:|---:|---:|---:|---|']
 for c in data['cards']:
  rows.append(f"|{c['name']}|{c['old_attack']}/{c['old_defense']}|{c['attack']}/{c['defense']}|{c['old_value']:.3f}|{c['value']:.3f}|{'上调' if c['changed'] else '已在高位，维持'}|")
 (OUT/'panels.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
 cn={'specialization':'专精','legendary':'传奇','epic':'史诗','rare':'稀有','common':'普通'};rn={'numeric':'数值100%','strong':'强运转70%','weak':'弱运转90%'}
 lines=['# v1.2现行189张卡牌总表','','2026-10-29。纯即时战力牌在原数值V区间内取较高值；永久成长与运转档维持。统一V规则见[功能分档](panel-budgets.md)。首次层按实例每场一次。','']
 for el,label in zip((*ELEMENTS,'generic'),('火','水','土','风','毒','通用')):
  lines+=['## '+label,'','|品质|卡牌|费|攻|防|首次层|V档|V值|效果|','|---|---|---:|---:|---:|---:|---|---:|---|']
  for c in CARDS.values():
   if c.element==el:lines.append(f'|{cn[c.rarity]}|{c.name}|{c.cost}|{c.attack}|{c.defense}|{c.layers}|{rn[role(c.name)]}|{float(value(c.cost,c.attack,c.defense)):.3f}|{c.text}|')
  lines.append('')
 (ROOT/'docs/cards-v1.2/catalogue.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 export(OUT)
 result=dict(cards=189,stock=707,reviewed_immediate_cards=55,increased_panels=51,unchanged_eligible=4,
  all_noneligible_panels_unchanged=True,all_flow_panels_unchanged=True,protected_growth_panels_unchanged=True,
  no_cost_text_layer_or_effect_changes=True,only_economy_changes=['profile growth-v7','rounds4to6 deletion 1 point'],new_tournaments=0)
 (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
