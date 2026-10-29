"""One-time calibration of authorized 70%/90% tiers and early arena losses."""
from pathlib import Path
from dataclasses import asdict
from fractions import Fraction as Q
from collections import Counter
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,export

STRONG=set('余烬引擎 余火 火种库 燃页 导火索 回流 活水 连环潮 开岩 岩拳 风之躯 风痕回廊 狂风 疾行 穿云 追云 追风 顺风 风刃 风驰 掠影 枯潮 毒涌 循毒 禁咒目录 灵感涌现 通晓 战术 狂战 翻阅 换页 速读'.split())
WEAK=set('灰烬循环 不灭烈焰 余烬心脏 灰烬重生 余烬刻度 灰烬账本 火种翻找 深流 潮汐回廊 疾流 水之低语 壁垒之心 岩核共鸣 寻岩 寻风 寻毒 守护者壁垒 战神徽记 禁忌知识 命运检索 恐惧 盾之共鸣 坚壁 大检索 循环 护盾强化 包扎 预备 整理 检索附魔 翻找 蓄能 重洗'.split())
assert len(STRONG)==32 and len(WEAK)==33 and not STRONG&WEAK
assert STRONG|WEAK<=CARDS.keys()
BANDS=dict(common=[5,6],rare=[7.5,9],epic=[9.5,11],legendary=[11.5,13.5],specialization=[14,16])
FACTORS=dict(numeric=1,strong=.7,weak=.9)

def write(rel,content):
 p=ROOT/rel
 if p.exists():
  backup=OUT/'before'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
  if not backup.exists():shutil.copy2(p,backup)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8')

def save(rel,data):write(rel,json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def best_panel(c,factor):
 lo,hi=[Q(str(x))*factor for x in BANDS[c.rarity]]
 old=Q(2*c.attack+3*c.defense,c.cost+1);target=old*factor
 limit=int(hi*(c.cost+1)/2)+2;options=[]
 for a in range(limit+1):
  for d in range(limit+1):
   v=Q(2*a+3*d,c.cost+1)
   if not lo<=v<=hi:continue
   zero_flip=int(c.attack==0 and a!=0)+int(c.defense==0 and d!=0)
   shape=Q(abs(a*c.defense-d*c.attack),max(1,c.attack+c.defense))
   options.append(((zero_flip,abs(v-target),shape,abs(a-c.attack)+abs(d-c.defense),a+d),a,d,v))
 assert options,c.name
 _,a,d,v=min(options)
 return a,d,v

def main():
 assert not (OUT/'calibration.json').exists(),'One-time migration already applied'
 export(OUT/'before-catalog')
 roles={n:'strong' if n in STRONG else 'weak' if n in WEAK else 'numeric' for n in CARDS}
 save('tools/sim_v12/rules/panel-budgets.json',dict(version='1.2-role-v1',formula='V=(attack+1.5*defense)/((cost+1)/2)',
  base_bands=BANDS,multipliers=FACTORS,card_roles=roles,
  precedence='strong wins; conditional immediate draw/mana and same-stage discounts are strong; pure shuffle/discard/recover are weak; no elemental exceptions'))
 changes=[];panels={}
 for n,c in CARDS.items():
  a,d,v=best_panel(c,Q(str(FACTORS[roles[n]]))) if roles[n]!='numeric' else (c.attack,c.defense,Q(2*c.attack+3*c.defense,c.cost+1))
  panels[n]=(a,d)
  if roles[n]!='numeric':changes.append(dict(name=n,element=c.element,rarity=c.rarity,role=roles[n],cost=c.cost,
   old_attack=c.attack,old_defense=c.defense,attack=a,defense=d,old_value=float(Q(2*c.attack+3*c.defense,c.cost+1)),value=float(v),
   changed=(a,d)!=(c.attack,c.defense),base_equivalent_value=float(v/Q(str(FACTORS[roles[n]])))))
 for el in (*ELEMENTS,'generic'):
  p=ROOT/f'docs/cards-v1.2/{el}.md';lines=p.read_text(encoding='utf-8').splitlines()
  for i,line in enumerate(lines):
   cells=line.split('|')
   if len(cells)==8 and cells[1] in panels:
    a,d=panels[cells[1]];cells[3]=str(a);cells[4]=str(d);lines[i]='|'.join(cells)
  write(str(p.relative_to(ROOT)),'\n'.join(lines)+'\n')
 old_damage=json.loads((ROOT/'tools/sim_v12/rules/damage.json').read_text(encoding='utf-8'))
 save('research/v1.2-flow-calibration-20261029/before-damage.json',old_damage)
 damage=json.loads(json.dumps(old_damage))
 for r in range(1,9):damage['table'][str(r)]=[3,1.] if r<=4 else [5,2.]
 damage['version']='v1.2-early-pressure-v1'
 damage['formula']='loss=m for draw; 0 for win; m+floor(n*ln(max(winner_remaining_battle_hp,1))) for loss'
 save('tools/sim_v12/rules/damage.json',damage)
 save('releases/deckbuilding-v1.2/damage.json',damage)
 save('research/v1.2-flow-calibration-20261029/calibration.json',dict(cards=len(CARDS),roles=dict(Counter(roles.values())),
  calibrated=len(changes),changed=sum(c['changed'] for c in changes),cards_detail=changes,unmodified_effects=True,unmodified_costs=True))
 print(json.dumps(dict(roles=dict(Counter(roles.values())),changed=sum(c['changed'] for c in changes)),ensure_ascii=False))

if __name__=='__main__':main()
