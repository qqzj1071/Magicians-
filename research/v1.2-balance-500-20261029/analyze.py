import sys,json,gzip,random,csv
from pathlib import Path
from collections import Counter
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parents[1]))
from tools.sim_v12.catalog import CARDS,ELEMENTS,ROUTES
from tools.sim_v12.quick_test import save
CN=dict(zip(ELEMENTS,'火水土风毒'))

def main():
 s=json.loads((P/'statistics.json').read_text(encoding='utf-8'))
 rooms=[];assigned=Counter();intents=Counter();seats=Counter();unassigned=Counter()
 for path in sorted((P/'rooms').glob('*.gz')):
  with gzip.open(path,'rt',encoding='utf-8') as h:r=json.load(h)
  x={k:[0.,0.,0.,0.,0.] for k in [*ELEMENTS,*s['routes']]}
  for a in r['evaluation_assignment']:
   assigned[a['element']]+=1;intents[a['route']]+=1;seats[a['element'],a['seat']]+=1
  for p in r['placements']:
   if not p['spec']:unassigned['no_element']+=1;unassigned['no_element_score']+=p['score']
   if not p['route']:unassigned['no_route']+=1;unassigned['no_route_score']+=p['score']
   for k in (p['spec'],p['route']):
    if k in x:
     x[k][0]+=1;x[k][1]+=p['score'];x[k][2]+=p['rank']==1
  for rnd in r['rounds']:
   for b in rnd['battles']:
    for i,p in enumerate(b['participants']):
     if i==1 and b['ghost']:continue
     for k in (p['spec'],p['route']):
      if k in x:x[k][3]+=.5 if b['winner'] is None else int(b['winner']==i);x[k][4]+=1
  rooms.append(x)
 assert len(rooms)==500 and set(assigned.values())=={400} and set(seats.values())=={100}
 rng=random.Random(98123);samples={k:[[],[],[]] for k in x}
 for _ in range(1500):
  totals={k:[0.]*5 for k in x}
  for i in rng.choices(range(500),k=500):
   for k,v in rooms[i].items():
    t=totals[k]
    for j in range(5):t[j]+=v[j]
  for k,t in totals.items():
   for arr,value in zip(samples[k],(t[1]/(3*t[0]),t[3]/t[4],t[2]/t[0])):arr.append(value)
 lines=['# v1.2 冻结 AI 500 局平衡测试','',f"500局完整四人赛事，2000人次，{s['battles']}场战斗；种子300000—300499，185张卡/693份库存，失效跳过0。输入哈希全部复核。69项模拟器回归及v1.1冻结校验通过。",'',
 '使用上一轮五元素 final-policy（构筑与战斗均冻结）。它们继承 outcome-accepted-10 并保留元素风格；上一轮25个训练候选均未获接受，因此最终仍是各系 style-initial，不能称为最优AI。当前测试使用最新六卡调整。每局四种不同元素，五种缺席组合各100局，每系400个安排人次、每座位100次；路线意向均衡，但不赠牌、不绕过共享池或路线唯一限制。全部15路线实际覆盖如下。', '',
 '排名分+3/+1/−1/−3，并列均分；得分率=总分/(3×人数)，公平基线0%；战斗胜率=(胜+0.5平)/玩家参战，基线50%；夺冠率为最终玩家第一名比例，基线25%。本次并列冠军房间数：'+str(s['tied_championship_rooms'])+'。', '',
 '预设实用异常线：得分率>10%/<−10%，战斗胜率>55%/<45%，夺冠率>30%/<20%。表中依次标注偏高/偏低/正常；括号为按整局重采样1500次所得95%区间。标注为幅度筛选，不是因果结论或多重比较显著性检验。路线在构筑中途取得，胜率包含取得之后的实战；排名按最终路线归类，存在选择与存活偏差。', '']
 lines+=['胜率的50%是参考线：幽灵对战只统计存活玩家一侧，且元素/路线仅从选定后计入，因此各组加权均值不保证恰好50%。这也是应同时查看名次分与夺冠率的原因。','', '未最终选定元素/路线（不强行归类）：'+json.dumps(dict(unassigned),ensure_ascii=False)+'。各表人数因此可能小于2000；无路线者仍计入其已选元素统计。','']
 flags={}
 for title,group in [('元素',s['elements']),('路线',s['routes'])]:
  lines += ['## '+title,'','|'+title+'|实际人数|总分|人均分|得分率[95%区间]|战斗胜率[95%区间]|夺冠率[95%区间]|得分/胜率/夺冠标注|','|---|---:|---:|---:|---|---|---|---|']
  for k,m in sorted(group.items(),key=lambda kv:kv[1]['mean_score'],reverse=True):
   vals=[m['score_rate'],m['win_rate'],m['championship_rate']];labels=[];cells=[]
   for v,arr,(lo,hi) in zip(vals,samples[k],[(-.1,.1),(.45,.55),(.2,.3)]):
    a=sorted(arr);cells.append(f'{v:.1%} [{a[37]:.1%}, {a[1462]:.1%}]');labels.append('偏高' if v>hi else '偏低' if v<lo else '正常')
   flags[k]=labels
   lines.append(f"|{CN.get(k,k)}|{m['players']}|{m['score']:g}|{m['mean_score']:+.3f}|"+'|'.join(cells)+'|'+'/'.join(labels)+'|')
 low=[c for c in s['cards'] if not c['starter_only'] and c['rarity']!='specialization' and c['exposed_players']>=30 and c['exposure_conversion']<.1]
 low.sort(key=lambda c:(c['exposure_conversion'],c['same_element_carry_rate']))
 lines+=['','## 展示后选择率低于10%的卡牌','', '至少30名玩家看见过才标记；购买率=购买过人数/看见过人数。传奇也纳入，专精与初始牌不纳入。低携带同品质后25%名单另见 cards.md/statistics.json；全185张完整选择指标见 card-selection.csv。','', '|卡牌|元素|曝光人数|购买人数|展示后购买率|最终同系携带率|','|---|---|---:|---:|---:|---:|']
 for c in low:lines.append(f"|{c['name']}|{CN.get(c['element'],'通用')}|{c['exposed_players']}|{c['purchasing_players']}|{c['exposure_conversion']:.1%}|{c['same_element_carry_rate']:.1%}|")
 lines+=['','低选择率可能来自AI计价、路线依赖、费用或展示时机，不能直接解释为卡弱。路线强弱同样受本轮AI偏好影响；本轮只测量与标注，不据相关性自动改数值。','','## 覆盖及复现','', '路线安排意向：'+json.dumps(dict(intents),ensure_ascii=False),'','[逐卡携带与表现](cards.md) · [机器统计](statistics.json) · [输入与策略哈希](inputs.json) · [冻结策略](frozen-policies.json) · rooms/保留全部逐局账本。']
 aliases=[]
 for line in (P.parents[1]/'docs/cards-v1.2/fire.md').read_text(encoding='utf-8').splitlines():
  f=line.split('|')[1:-1]
  if len(f) in (7,8) and f[1] in CARDS and f[0]!=f[1]:aliases.append((f[1],f[0]))
 lines+=['','## 火系名称对照','', '火系MD为选名展示稿，运行规则与AI继续按原名匹配。数值未因名称兼容而改变。','', '|报告与运行原名|火系MD展示名|','|---|---|']+[f'|{old}|{new}|' for old,new in aliases]
 (P/'balance-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 save(P/'balance-flags.json',dict(flags=flags,low_selection=[c['name'] for c in low],assigned=dict(assigned),route_intents=dict(intents),bootstrap='room-cluster1500,seed98123'))
 with (P/'card-selection.csv').open('w',encoding='utf-8-sig',newline='') as h:
  keys=['name','element','rarity','exposed_players','purchasing_players','exposure_conversion','players','carry_rate','same_element_carry_rate','purchase_count','deleted_players','score_rate','win_rate','championship_rate']
  w=csv.DictWriter(h,keys,extrasaction='ignore');w.writeheader();w.writerows(s['cards'])
 print(json.dumps(dict(elements=s['elements'],flags=flags,low_selection=[c['name'] for c in low]),ensure_ascii=False))
if __name__=='__main__':main()
