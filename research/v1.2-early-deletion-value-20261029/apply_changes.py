"""Apply paid early deletion and conservative immediate-combat panel buffs."""
from pathlib import Path
from fractions import Fraction as Q
import json,sys,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,export
from tools.sim_v12.panel_budget import role,bounds,value

ELIGIBLE=set('压缩爆燃 爆燃 狂暴 余烬护心 灼痛 烈焰附身 烈焰冲刺 猛火弹 引火 回响之潮 水幕 泉心 潮汐风暴 穿潮 泉眼 潮涌 万钧碎盾 不坏壁垒 山岳之躯 岩潮壁垒 镜岩之心 临时壁垒 守岩 山岳 碎岩印记 碎盾术 磐岩壁 裂岩护壁 坚岩 岩甲 磐石 裂风 风切 风幕 风蚀 风步 万毒爆 万毒蚀骨 万蚀 毒潮 疫病 毒囊 爆裂 腐溃 腐潮 蚀刻 断流封印 破甲 裂伤 利刃 攻击强化 防御强化 护盾 拆盾弹 短促'.split())
PROTECTED=set('战意 熔盾烈焰 奔流 深渊 层岩结构 风暴 缓释毒素 回震岩甲 山岳壁垒 蚀创 蚀骨之触 血刃 烈风 疾风连斩 穿云破甲 裂空穿云 岩核重压 握盾 盾脉 回岩 腐息 涌泉 细流 洪潮 洪流 血潮汹涌 血怒 静水 永恒壁垒 火花 轻羽 毒引 毒龙 毒瓶 毒针 固毒 蚀界 气旋护壁 风痕刻印 风眼 回火 燃血 高温炉心 焚心 潮声'.split())

def write(rel,text):
 p=ROOT/rel
 if p.exists():
  backup=OUT/'before'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
  if not backup.exists():shutil.copy2(p,backup)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

def main():
 assert not (OUT/'panel-changes.json').exists(),'Already applied'
 assert not ELIGIBLE&PROTECTED and ELIGIBLE|PROTECTED<=CARDS.keys()
 assert all(role(n)=='numeric' and not CARDS[n].ability for n in ELIGIBLE)
 export(OUT/'before-catalog')
 records=[];new_panels={}
 for name in sorted(ELIGIBLE):
  c=CARDS[name];lo,hi=bounds(name,c.rarity);old=value(c.cost,c.attack,c.defense)
  target=lo+(hi-lo)*Q(3,4)
  if old>=target:a,d,v=c.attack,c.defense,old
  else:
   limit=int(hi*(c.cost+1)/2)+2;options=[]
   for a in range(limit+1):
    for d in range(limit+1):
     v=value(c.cost,a,d)
     if not target<=v<=hi:continue
     zero_flip=int(c.attack==0 and a!=0)+int(c.defense==0 and d!=0)
     shape=Q(abs(a*c.defense-d*c.attack),max(1,c.attack+c.defense))
     options.append(((zero_flip,abs(v-target),shape,abs(a-c.attack)+abs(d-c.defense)),a,d,v))
   _,a,d,v=min(options)
  new_panels[name]=(a,d)
  records.append(dict(name=name,element=c.element,rarity=c.rarity,cost=c.cost,old_attack=c.attack,old_defense=c.defense,
   attack=a,defense=d,old_value=float(old),value=float(v),target=float(target),changed=(a,d)!=(c.attack,c.defense)))
 for el in ('fire','water','earth','wind','poison','generic'):
  p=ROOT/f'docs/cards-v1.2/{el}.md';lines=p.read_text(encoding='utf-8').splitlines()
  for i,line in enumerate(lines):
   cells=line.split('|')
   if len(cells)==8 and cells[1] in new_panels:
    a,d=new_panels[cells[1]];cells[3]=str(a);cells[4]=str(d);lines[i]='|'.join(cells)
  write(str(p.relative_to(ROOT)),'\n'.join(lines)+'\n')
 for rel in ('tools/sim_v12/rules/economy.json','releases/deckbuilding-v1.2/economy.json'):
  d=json.loads((ROOT/rel).read_text(encoding='utf-8'));d['implementation_profile']='growth-v7'
  d['deletions']['rounds_4_to_6']=[1,[1]]
  write(rel,json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 rel='tools/sim_v12/rules/probabilities.json';d=json.loads((ROOT/rel).read_text(encoding='utf-8'));d['economy_profile']='growth-v7'
 write(rel,json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 result=dict(eligible=sorted(ELIGIBLE),explicitly_protected=sorted(PROTECTED),changed=sum(r['changed'] for r in records),cards=records,
  rule='numeric-role, immediate/transient combat only; target upper quarter of existing rarity range; never reduce existing V',
  exclusions='All abilities, first-layer-only legendaries, flow cards and resource/stacking engines remain unchanged.')
 write('research/v1.2-early-deletion-value-20261029/panel-changes.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(eligible=len(ELIGIBLE),changed=result['changed'],protected=len(PROTECTED)),ensure_ascii=False))

if __name__=='__main__':main()
