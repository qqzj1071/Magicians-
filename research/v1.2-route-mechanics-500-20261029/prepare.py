import json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,export
from tools.sim_v12.panel_budget import bounds,value
assert not (P/'changes.json').exists()
export(P/'before')
replacements={'旧盾实际衰减损失×200%':'旧盾实际衰减损失×100%',
 '返还消耗量25%':'返还消耗量20%', '飞弹防御穿透20%':'飞弹护盾穿透20%',
 '主弹基础攻击倍率为1.8':'主弹基础攻击倍率为2',
 '目标最大生命×3%×目标毒层':'目标最大生命×0.5%×自身毒附魔层数×目标毒层数',
 '(10%+(k−1)×1%)':'(8%+(k−1)×2%)', '实际支付量100%':'实际支付量150%'}
panels={'大地之握':(7,7),'生命之泉':(11,5),'山岳壁垒':(1,9),'不坏壁垒':(12,2),'万钧碎盾':(19,1),'回响之潮':(9,7)}
prior=json.loads((P.parent/'v1.2-panel-balance-500-20261029/statistics.json').read_text(encoding='utf-8'));metrics={c['name']:c for c in prior['cards']}
changes=[]
for n,(a,d) in panels.items():
 c=CARDS[n];old=value(c.cost,c.attack,c.defense);v=value(c.cost,a,d);lo,hi=bounds(n,c.rarity)
 assert lo<=v<=hi and .93<=v/old<1 and metrics[n]['win_rate']>.55
 changes.append(dict(name=n,before=[c.attack,c.defense],after=[a,d],delta=float(v/old)-1,previous_win_rate=metrics[n]['win_rate']))
for path in [*(ROOT/'docs/cards-v1.2').glob('*.md'),ROOT/'docs/cards-v1.2/snapshot-contract.json']:
 if path.name=='change-history.md':continue
 text=path.read_text(encoding='utf-8')
 for old,new in replacements.items():text=text.replace(old,new)
 out=[]
 for line in text.splitlines():
  f=line.split('|')[1:-1]
  if len(f)==6 and f[0] in panels:
   f[2:4]=map(str,panels[f[0]]);line='|'+'|'.join(f)+'|'
  elif len(f)==9 and f[1] in panels:
   a,d=panels[f[1]];f[3:5]=[str(a),str(d)];f[7]=f'{float(value(int(f[2]),a,d)):.3f}';line='|'+'|'.join(f)+'|'
  out.append(line)
 path.write_text('\n'.join(out)+'\n',encoding='utf-8')
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(P/'changes.json',dict(mechanism_replacements=replacements,panels=changes))
lines=['# 七条路线机制与高胜率牌微调','', '用户指定的七条机制完整落实，随后依据前轮500局冻结结果，对六张胜率>55%的牌降低固定攻击1点。费用、防御、首次层、库存、AI与经济不变，V降幅4.7%—6.5%，全部在原预算内。本轮不使用中途结果继续调参。','']
lines += [f'- {a} → {b}' for a,b in replacements.items()]
lines+=['','蚀命新增乘区使用施毒者自身毒附魔层数，目标毒层数沿用敌方当前毒层；仍只用于常规/额外毒伤，毒爆不加。风痕n层总伤害=攻击×[0.08n+0.01n(n−1)]，按单层k计算，前2层低于旧式，第3层持平，第4层起更高；按累计n层总伤害计算，前4层低于旧式，5层持平，6层起更高。生命之泉改为盾穿，不再提供防穿；与其他盾穿加算、上限100%。','', '|卡牌|旧攻/防|新攻/防|前轮战斗胜率|V变化|','|---|---:|---:|---:|---:|']
for c in changes:lines.append(f"|{c['name']}|{c['before'][0]}/{c['before'][1]}|{c['after'][0]}/{c['after'][1]}|{c['previous_win_rate']:.1%}|{c['delta']:+.1%}|")
(P/'changes.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (ROOT/'docs/cards-v1.2/change-history.md').open('a',encoding='utf-8') as h:h.write('\n\n## 2026-10-29 七路线机制及六张高胜率面板微调\n\n详见 research/v1.2-route-mechanics-500-20261029/changes.md；历史段落保留当时系数。\n')
old=P.parent/'v1.2-panel-balance-500-20261029'
run=(old/'run.py').read_text(encoding='utf-8').replace('301000','302000').replace('301499','302499')
(P/'run.py').write_text(run,encoding='utf-8')
an=(old/'analyze.py').read_text(encoding='utf-8').replace('301000','302000').replace('301499','302499').replace('当前测试在最新六卡机制基础上微调18张固定攻防，见panel-changes.md。','当前测试落实用户指定七条路线机制，并下调六张高胜率卡固定攻击，见changes.md。')
(P/'analyze.py').write_text(an,encoding='utf-8')
print('PREPARED')
