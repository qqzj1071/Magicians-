import json
from pathlib import Path
P=Path(__file__).resolve().parent
old=json.loads((P.parent/'v1.2-balance-500-20261029/statistics.json').read_text(encoding='utf-8'))
new=json.loads((P/'statistics.json').read_text(encoding='utf-8'))
changes=json.loads((P/'panel-changes.json').read_text(encoding='utf-8'))
cn=dict(fire='火',water='水',earth='土',wind='风',poison='毒')
lines=['# 固定攻防微调后的500局复测','',f"本轮500局、2000人次、{new['battles']}场战斗，零失效跳过，全部输入哈希复核；五系与15路线均覆盖。使用相同冻结AI和赛事安排，新种子301000—301499。18张固定攻防改动；其余卡定义、机制、规则、AI均不变。69项回归与185张预算通过，v1.1冻结校验通过。",'',
 '[18张攻防改动及原因](panel-changes.md) · [本轮全部路线标注与95%区间](balance-report.md) · [本轮185张逐卡数据](card-selection.csv)','',
 '下表为旧→新，括号是百分点变化；得分率为名次分/(3×人数)。两轮为独立种子样本，不是相同牌局的机制消融，单次差值不等于确定提升；多张牌同时变化，不能拆分单卡因果效果。本轮完成后不再据终测回调，留作下一轮传奇机制调整的基线。','']
for title,section in [('元素','elements'),('路线','routes')]:
 lines += ['## '+title,'','|'+title+'|本轮人数|得分率：旧→新|战斗胜率：旧→新|夺冠率：旧→新|','|---|---:|---:|---:|---:|']
 for k,b in sorted(new[section].items(),key=lambda kv:kv[1]['win_rate'],reverse=True):
  a=old[section][k];cells=[f"{a[m]:.1%} → {b[m]:.1%} ({(b[m]-a[m])*100:+.1f})" for m in ('score_rate','win_rate','championship_rate')]
  lines.append(f"|{cn.get(k,k)}|{b['players']}|"+'|'.join(cells)+'|')
oc={c['name']:c for c in old['cards']};nc={c['name']:c for c in new['cards']}
lines+=['','## 改动牌选择率变化','', '购买率=购买过该牌人数/见过该牌人数，包含最后被删除者；最终携带率按同元素玩家（通用按全体）计算。攻防微调也可能改变AI买牌顺序与对手构筑。','', '|卡牌|攻/防|曝光人数：旧→新|展示后购买率：旧→新|同系最终携带率：旧→新|','|---|---|---:|---:|---:|']
for r in changes:
 n=r['name'];a,b=oc[n],nc[n];lines.append(f"|{n}|{r['before'][0]}/{r['before'][1]} → {r['after'][0]}/{r['after'][1]}|{a['exposed_players']} → {b['exposed_players']}|{a['exposure_conversion']:.1%} → {b['exposure_conversion']:.1%}|{a['same_element_carry_rate']:.1%} → {b['same_element_carry_rate']:.1%}|")
lines+=['','未改传奇路线机制。下一步可结合仍低胜率路线的回合进程、启动条件与资源转换，决定传奇机制调整；低选择率也可能包含AI估值偏差。完整原始账本保存在 rooms/。']
(P/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines[:40]))
