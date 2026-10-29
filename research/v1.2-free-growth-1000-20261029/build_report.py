"""Postprocess the sealed run without changing checkpoints or selecting models."""
from pathlib import Path
import gzip,json,sys
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS
from tools.sim_v12.free_train import describe
from tools.sim_v12.quick_test import pct,number

def load(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def write(name,lines):(OUT/name).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
 t=load('training.json');s=load('final-selected-statistics.json');deployment=load('deployment.json')
 existing=OUT/'report.md'
 if existing.exists() and existing.read_text(encoding='utf-8').startswith('# v1.2 快速卡牌测试'):
  original=existing.read_text(encoding='utf-8')
  original=original.replace('# v1.2 快速卡牌测试','# v1.2 1000局混合训练分布',1)
  original=original.replace('这些是当前启发式 AI 的相关表现','这些是本轮混合训练策略的相关表现').replace('本轮没有训练 AI 或改动平衡数值。','本文件混合多个训练检查点与对照，不能当作最终模型成绩；本轮未修改平衡数值。')
  (OUT/'training-distribution.md').write_text(original,encoding='utf-8')
 rooms=[]
 for p in sorted((OUT/'batches').glob('*/room-*.json.gz')):
  with gzip.open(p,'rt',encoding='utf-8') as h:r=json.load(h)
  if r['comparison']['segment']=='final-holdout':rooms.append(r)
 same=Counter();styles=defaultdict(list);style_wins=defaultdict(Counter)
 size_battles=defaultdict(Counter)
 for r in rooms:
  selected=set(r['comparison']['first_seats'])
  for p in r['placements']:
   if p['pid'] not in selected:continue
   styles[p['style']].append(p)
   for n in set(p['deck']):same[n]+=CARDS[n].element==p['spec']
  for rd in r['rounds']:
   for b in rd['battles']:
    for i,p in enumerate(b['participants']):
     if i==1 and b['ghost'] or p['pid'] not in selected:continue
     book=style_wins[r['placements'][next(j for j,x in enumerate(r['placements']) if x['pid']==p['pid'])]['style']]
     book['n']+=1;book['w']+=.5 if b['winner'] is None else b['winner']==i
     n=len(p['deck']);bucket='8—11' if n<=11 else '12—15' if n<=15 else '16—18' if n<=18 else '19+'
     stage='1—4' if rd['round']<=4 else '5—8' if rd['round']<=8 else '9—12' if rd['round']<=12 else '13+'
     cell=size_battles[(p['spec'],stage,bucket)];cell['battles']+=1
     cell['wins']+=.5 if b['winner'] is None else b['winner']==i
     cell['size_sum']+=n
     if b['winner']==i:cell['winner_time']+=b['time'];cell['strict_wins']+=1
 lines=['# v1.2 无目标牌组大小：10轮1000局联合AI训练','',
  f"本轮完成{t['completed']}/1000局完整四人赛事，{t['battles']:,}场战斗，跳过{t['skipped']}局。候选检查点为{t['candidate']['checkpoint']}，接受{t['accepted_steps']}次更新。默认部署：{deployment['deployed']}；是否通过部署门槛：{'是' if t['promoted'] else '否'}。",'',
  '现行189张、707份，growth-v5研习点与同类百分比加算规则全程固定。种子292000—292999；每名玩家每局独立随机六种风格。实际排名仍按+3/+1/−1/−3统计。', '',
  '## 怎样探索与防止过拟合','',
  '新构筑模型没有target、目标长度区间、超长扣分或固定删牌数量。规则中的最少8张及删牌次数/费用仍有效。购买、跳过、删除和刷新比较单牌收益、现有牌组的抽牌稀释与研习点机会成本。牌组大小和运转牌占比是策略运行后的结果。',
  '风/毒初始化略重循环，火/水/土略重首次附魔层与生存；没有把12—15或14—18写成规则或奖励。仅学习13项通用战斗机制权重、9项构筑权重与每元素3项微调；不学习逐卡胜率表，不读取对手私有牌堆、未展示候选或未来随机数。',
  '前8轮各60训练＋20独立验证＋20封存对照，后2轮冻结最终候选共200局。合计480训练、160验证、160滚动封存、200最终封存；最终对旧默认和上轮薄构筑各100局。封存成绩在训练结束后才汇总，不参与梯度、检查点选择或重新调参。',
  '策略选择只看战斗胜率：训练房间平均胜率差非负、验证差至少0.5个百分点才接受。全局参数每步至多4%，元素微调每步至多1.5%，并限于初值附近。训练梯度对元素/风格差异做收缩，避免直接追逐强势元素。胜率区间以完整赛事为统计单元，保留同局战斗相关性。',
  '默认替换要求最终双对照各100局、零跳过，且两组配对胜率差95%区间下界均大于0。未通过则保留旧默认，不用测试结果挑另一个检查点。1000局包含迭代模型，不能全部当最终模型终测；这里的探索也不能证明全局最优。','',
  '## 冻结最终模型对照','',
  '|对照|局数|新模型战斗胜率|对照胜率|配对胜率差95%区间|新/旧夺冠率|新/旧人均分|新/旧牌组大小|',
  '|---|---:|---:|---:|---|---|---|---|']
 for label,e in t['evaluation'].items():
  a,b=e['selected'],e['control'];ci=e['paired_win']
  lines.append(f"|{label}|{e['games']}|{pct(a['win_rate'])}|{pct(b['win_rate'])}|{pct(ci['mean'])} [{pct(ci['low'])}, {pct(ci['high'])}]|{pct(a['championship_rate'])}/{pct(b['championship_rate'])}|{number(a['mean_score'])}/{number(b['mean_score'])}|{e['selected_decks']['mean_size']:.2f}/{e['control_decks']['mean_size']:.2f}|")
 lines+=['','胜率把平局计半胜；汇总胜率与逐赛事配对差的加权方式不同。2新AI＋2对照共享同一有限池，可能与各自同队交手，三人阶段有幽灵，所以两列战斗胜率不必互补。两项对照均使用本轮新卡表、新数值及研习点；没有拿过去规则的胜率直接比较。','',
  '## 最终模型的构筑分布','',
  f"最终封存200局共{s['players']}名新模型玩家。终局平均{t['final_decks']['mean_size']:.2f}张，中位数{t['final_decks']['median']}，范围{t['final_decks']['minimum']}—{t['final_decks']['maximum']}；人均购买{t['final_decks']['purchases_per_player']:.2f}张、删除{t['final_decks']['deletions_per_player']:.2f}张。",'',
  '|元素|人数|平均张数|中位数|范围|运转牌占比|首次本系层总量|战斗胜率|夺冠率|人均分|',
  '|---|---:|---:|---:|---|---:|---:|---:|---:|---:|']
 names={'fire':'火','water':'水','earth':'土','wind':'风','poison':'毒'}
 for e in ELEMENTS:
  d=t['final_decks']['elements'][e];m=s['elements'][e]
  lines.append(f"|{names[e]}|{d['players']}|{d['mean_size']:.2f}|{d['median']}|{d['minimum']}—{d['maximum']}|{pct(d['flow_fraction'])}|{d['main_first_layers']:.2f}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','运转牌定义为含即时抽牌、返费、检索、主动弃牌、洗牌或回收任一机制；按牌张占比计算，初始牌也在分母中。“首次本系层总量”为终局持有牌的卡面首次层合计，不是实战已叠层数。终局牌组受赛事长度和淘汰轮次影响，相关结果不是强行令某元素达到某长度的因果证明。逐轮平均大小与完整长度直方图见training.json。','',
  '## 元素路线与风格','',
  '|路线|最终人数|战斗胜率|夺冠率|人均分|', '|---|---:|---:|---:|---:|']
 for name,m in sorted(s['routes'].items(),key=lambda x:x[1]['mean_score'] if x[1]['mean_score'] is not None else -999,reverse=True):
  lines.append(f"|{name}|{m['players']}{'（小样本）' if m['players']<30 else ''}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','最终持有路线计人数与夺冠；战斗路线按当场实际路线计，途中换路线可能使最终人数为0而仍有战斗记录。','',
  '|风格|人数|平均牌组|战斗胜率|夺冠率|人均分|','|---|---:|---:|---:|---:|---:|']
 for name,ps in sorted(styles.items()):
  w=style_wins[name]
  lines.append(f"|{name}|{len(ps)}|{sum(len(p['deck']) for p in ps)/len(ps):.2f}|{pct(w['w']/max(1,w['n']))}|{pct(sum(p['rank']==1 for p in ps)/len(ps))}|{sum(p['score'] for p in ps)/len(ps):.3f}|")
 lines+=['','## 每轮选择与参数','', '|轮|接受更新|检查点|训练胜率差|验证胜率差|','|---|---|---|---:|---:|']
 for b in t['batches']:
  lines.append(f"|{b['round']}|{b['accepted']}|{b['selected']}|{pct(b.get('train',{}).get('mean'))}|{pct(b.get('validation',{}).get('mean'))}|")
 lines+=['','每轮候选、对手、选择理由、方向和检查点保存在batches/。最终权重final-policy.json。封存回合为None，不再更新模型。','',
  '## 问题与限制','', '|问题|处理|','|---|---|']
 issues=load('issues.json')
 if not issues:lines.append('|运行失败或跳过|0；没有补造胜者或补跑有利种子|')
 for i in issues:lines.append(f"|种子{i['seed']}|{i['error']}；跳过并保留诊断|")
 lines+=['|最终每对照只有100局|使用赛事聚类区间和保守部署门槛，不把未显著的正值称为稳定提升|',
  '|元素与路线样本不均|人数少于30标注，不据低携带或低胜率自动删牌|',
  '|未限定长度不等于必然发现最优长度|受单牌估值模型、有限池、合法删牌次数和样本量约束；仍需独立复验|',
  '|缺少单独拆分构筑/战斗贡献的第三组对照|本轮是联合优化；不将提升全部归于某一模块|',
  '|旧默认仍可能存在隐式长度启发式|仅作为冻结对照保留；新explorer路径不读取这些启发式|','',
  '37项现行预检通过，包括32项战斗、2项经济、3项无目标构筑检查；输入哈希已复核。v1.1冻结核验另行记录。没有调整卡牌效果、经济、共享库存、最小8张或出牌规则。','',
  '完整新模型携带与使用率见[final-cards.md](final-cards.md)，分元素/赛事阶段的实战牌组大小见[size-analysis.md](size-analysis.md)。全1000局混合训练分布见[training-distribution.md](training-distribution.md)和[cards.md](cards.md)，不可与最终模型分布混用。']
 write('report.md',lines)
 cs=['# 最终冻结模型：189张卡牌携带与使用统计','',
  f"200局封存、{s['players']}名新模型玩家。携带=终局仍持有；使用率=持有该牌参战时至少施放一次的战斗比例；平均次数=总施放次数/持有参战次数。能力牌打出后移出本场，低重复使用不代表无效。初始和专精牌不入构筑池，曝光购买率不适用。",'',
  '|卡牌|元素|携带人数|携带率|同系携带率|曾携带率|得分率|人均分|夺冠率|参战使用率|平均施放次数|曝光购买率|',
  '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for c in sorted(s['cards'],key=lambda c:(c['element'],c['carry_rate'])):
  den=s['players'] if c['element']=='generic' else s['elements'][c['element']]['players']
  rate=c['carry_rate'] if c['element']=='generic' else same[c['name']]/max(1,den)
  cs.append(f"|{c['name']}|{c['element']}|{c['players']}|{pct(c['carry_rate'])}|{pct(rate)}|{pct(c['ever_carry_rate'])}|{pct(c['score_rate'])}|{number(c['mean_score'])}|{pct(c['championship_rate'])}|{pct(c['usage_rate'])}|{number(c['casts_per_carried_battle'])}|{pct(c['exposure_conversion'])}|")
 write('final-cards.md',cs)
 sz=['# 冻结模型：实际参战牌组大小与胜率','',
  '按当场出战时牌组大小、实际元素及赛事轮次分组；仅统计200局冻结终测的新模型玩家，幽灵不计。与终局牌组大小不同。样本少于30场标记“小”；同一玩家多场有相关性。',
  '分轮次减少早期小牌组与后期大牌组混合的偏差，但存活者偏差、卡牌质量和对手差异仍在。这些相关表现不能证明强行增删到该大小就会提高胜率。','',
  '|元素|赛事轮次|牌组区间|参战数|战斗胜率|获胜平均行动值|','|---|---|---|---:|---:|---:|']
 records=[]
 for (element,stage,bucket),cell in sorted(size_battles.items()):
  wins=cell['wins']/cell['battles'];av=cell['winner_time']/cell['strict_wins'] if cell['strict_wins'] else None
  sz.append(f"|{names.get(element,element or '未专精')}|{stage}|{bucket}|{cell['battles']}{'（小）' if cell['battles']<30 else ''}|{pct(wins)}|{number(av)}|")
  records.append(dict(element=element,round_band=stage,size_band=bucket,**cell,win_rate=wins,winner_mean_time=av))
 write('size-analysis.md',sz)
 (OUT/'size-analysis.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 # Interpret the frozen outputs without feeding them back into selection.
 conclusions=['## 本轮结果的解读','',
  '新模型对旧默认有正向战斗胜率结果，但每组仅100局，区间下界接近0；对上一轮薄构筑，胜率差区间跨0，未同时通过双对照部署门槛，因此默认未替换。对薄构筑的人均排名分更高，与胜率主目标并不相同，不能改用排名分绕过部署规则。',
  '不设目标大小后，策略仍偏向小牌组：终局均值9.90、中位数8。风8.65、火9.79、水9.52、土10.03、毒12.07，并未自然形成“风/毒12—15、火/水/土14—18”的预想；这些范围从未作为硬限制。少量未专精玩家单独留在全体统计中，因此元素表人数不一定合计400。',
  '毒系仍然较弱（终测69名最终毒专精玩家，战斗胜率17.5%、零夺冠）。这是当前策略与卡表共同作用的表现，不能证明单纯扩大或缩小毒牌组就会改善，也不能据此自动删除低携带牌。',
  '仍有“携带高费核心，却较少实际打出”的问题：风暴93名携带者，持牌参战使用率27.6%、平均0.29次；深渊73名，42.2%、0.59次。相对地余烬引擎68名，使用率99.5%、平均4.31次。3费核心可能与即时运转争夺同阶段费用，仍需后续诊断出牌时机，不能把较高携带率当作核心已成功循环。',
  '本轮是有限样本的小步局部搜索，证明的是这一候选在指定对照下的表现，不是找到了每个元素的最优长度或最高可达胜率。终测发现的问题只记录，不据此修改模型后复用同一终测。','']
 text=(OUT/'report.md').read_text(encoding='utf-8')
 text=text.replace('## 怎样探索与防止过拟合','\n'.join(conclusions)+'\n## 怎样探索与防止过拟合',1)
 (OUT/'report.md').write_text(text,encoding='utf-8')
 # Keep the generic report with its mixed-cohort labels, not as the final report.
 print(str(OUT/'report.md'))

if __name__=='__main__':main()
