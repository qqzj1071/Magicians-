import json
from pathlib import Path
P=Path(__file__).resolve().parent
old=json.loads((P.parent/'v1.2-panel-balance-500-20261029/statistics.json').read_text(encoding='utf-8'))
new=json.loads((P/'statistics.json').read_text(encoding='utf-8'))
cn=dict(fire='火',water='水',earth='土',wind='风',poison='毒')
lines=['# 七条路线机制调整后的500局复测','',f"500局四人赛事，2000人次，{new['battles']}场战斗，失效跳过0；新种子303000—303499。五系/15路线全覆盖，同上一轮冻结AI与赛事分布，每系安排400人次、每座位100。输入源码、卡文、规则和策略哈希全部复核。72项回归、185张预算与跨层卡文/总表匹配、v1.1冻结通过。",'',
 '[七条机制与六张攻防改动](changes.md) · [本轮详细标注及95%区间](balance-report.md) · [全部185张卡选择数据](card-selection.csv)','',
 '表格为上一轮→本轮，括号为百分点变化。得分率=总名次分/(3×人数)。两轮独立种子，且七机制和六面板同时变化；差值含抽样波动与环境变化，不能拆成单项机制因果贡献。本轮终测后不再调参。','']
for title,key in [('元素','elements'),('路线','routes')]:
 lines+=['## '+title,'', '|'+title+'|本轮人数|得分率：旧→新|战斗胜率：旧→新|夺冠率：旧→新|','|---|---:|---:|---:|---:|']
 for k,b in sorted(new[key].items(),key=lambda kv:kv[1]['win_rate'],reverse=True):
  a=old[key][k];vals=[f"{a[m]:.1%} → {b[m]:.1%} ({(b[m]-a[m])*100:+.1f})" for m in ('score_rate','win_rate','championship_rate')]
  lines.append(f"|{cn.get(k,k)}|{b['players']}|"+'|'.join(vals)+'|')
oc={c['name']:c for c in old['cards']};nc={c['name']:c for c in new['cards']}
names=list(dict.fromkeys(['大地之握','潮汐回响','生命之泉','燃烧血统','蚀命','风痕','血潮']+[r['name'] for r in json.loads((P/'changes.json').read_text(encoding='utf-8'))['panels']]))
lines+=['','## 修改牌的选择变化','', '|卡牌|曝光人数：旧→新|展示后购买率：旧→新|最终同系携带率：旧→新|','|---|---:|---:|---:|']
for n in names:
 a,b=oc[n],nc[n]
 lines.append(f"|{n}|{a['exposed_players']} → {b['exposed_players']}|{a['exposure_conversion']:.1%} → {b['exposure_conversion']:.1%}|{a['same_element_carry_rate']:.1%} → {b['same_element_carry_rate']:.1%}|")
lines+=['','全部低选择牌清单在详细报告中，逐局完整构筑与战斗记录保存在rooms/。AI本轮冻结，尚未针对新公式重新训练，其策略适应程度也会影响表现。', '', '预检发现两处既有火系专精展示名称未同步，初次运行中断，53份已保存诊断房间另放interrupted-diagnostic-rooms/，不计入本报告。同步总表/跨层文档并全部通过检查后，以303000—303499全新种子完成上述正式500局；详见interruption.json。']
(P/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines[:37]))
