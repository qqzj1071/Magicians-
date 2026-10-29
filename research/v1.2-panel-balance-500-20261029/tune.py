import sys,json,dataclasses
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,export
from tools.sim_v12.panel_budget import bounds,value
changes={'焚心':(16,0),'余烬心脏':(13,1),'高温炉心':(9,0),'火种库':(9,0),
 '血潮汹涌':(5,4),'血刃':(3,4),'血怒':(13,0),
 '风痕回廊':(10,1),'风痕刻印':(6,2),'裂空穿云':(15,1),'腐息':(7,4),
 '裂岩护壁':(2,4),'握盾':(10,1),'盾脉':(1,7),'山岳':(6,4),
 '水幕':(4,4),'穿潮':(6,4),'回响之潮':(10,7)}
assert all(CARDS[n].kind=='normal' for n in changes)
stats=json.loads((ROOT/'research/v1.2-balance-500-20261029/statistics.json').read_text(encoding='utf-8'))
metrics={c['name']:c for c in stats['cards']}
export(P/'before')
rows=[]
for n,(a,d) in changes.items():
 c=CARDS[n];lo,hi=bounds(n,c.rarity);v=value(c.cost,a,d);old=value(c.cost,c.attack,c.defense)
 assert lo<=v<=hi,(n,v,lo,hi)
 assert abs(float(v/old)-1)<=.126,(n,v,old)
 rows.append(dict(name=n,element=c.element,before=[c.attack,c.defense],after=[a,d],old_v=float(old),new_v=float(v),delta=float(v/old)-1,previous_conversion=metrics[n]['exposure_conversion']))
for e in ('fire','water','earth','wind','poison','generic'):
 path=ROOT/f'docs/cards-v1.2/{e}.md';lines=path.read_text(encoding='utf-8').splitlines();out=[]
 for line in lines:
  f=line.split('|')[1:-1]
  if len(f)==6 and f[0] in changes:
   a,d=changes[f[0]];f[2:4]=[str(a),str(d)];line='|'+'|'.join(f)+'|'
  elif len(f) in (7,8) and f[1] in changes:
   a,d=changes[f[1]];f[3:5]=[str(a),str(d)];line='|'+'|'.join(f)+'|'
  out.append(line)
 path.write_text('\n'.join(out)+'\n',encoding='utf-8')
path=ROOT/'docs/cards-v1.2/catalogue.md';out=[]
for line in path.read_text(encoding='utf-8').splitlines():
 f=line.split('|')[1:-1]
 if len(f)==9 and f[1] in changes:
  n=f[1];a,d=changes[n];f[3:5]=[str(a),str(d)];f[7]=f'{float(value(int(f[2]),a,d)):.3f}';line='|'+'|'.join(f)+'|'
 out.append(line)
path.write_text('\n'.join(out)+'\n',encoding='utf-8')
(P/'panel-changes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# 固定攻防微调清单','', '只改18张普通/稀有/史诗卡固定面板，全部仍在现有V预算内；V变幅−11.54%至+12.5%。费用、首次层、机制、传奇与专精面板、AI参数不变。低胜率路线优先，其次弱火系冷门牌；对高胜率土水配套牌小幅下调。风痕两牌增防减攻是V上调的重分配，非攻防同时增加。','', '|卡牌|旧攻/防|新攻/防|V变化|上轮展示购买率|','|---|---:|---:|---:|---:|']
for r in rows:lines.append(f"|{r['name']}|{r['before'][0]}/{r['before'][1]}|{r['after'][0]}/{r['after'][1]}|{r['delta']:+.1%}|{r['previous_conversion']:.1%}|")
lines+=['','缓释毒素、熔盾烈焰维持指定3费V7；灰烬重生等已近现有预算上限，不因低选择率突破预算。风痕支持牌本轮主要提高防御；其低选择率净化牌风蚀已在V上限，未直接加值。这里的路线关联来自现有AI支持映射，不是各牌的因果贡献。']
(P/'panel-changes.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('TUNED',len(rows))
