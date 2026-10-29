"""Postprocess sealed training outputs without running or modifying policies."""
from collections import Counter,defaultdict
import gzip,json,math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,ROUTES,START_ONLY
from tools.sim_v12.analytics import Statistics
from tools.sim_v12.quick_test import pct,number

OUT=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def cohort(rooms):
 elements={e:Counter() for e in ELEMENTS};routes={r:Counter() for rs in ROUTES.values() for r in rs}
 cards={n:Counter() for n in CARDS};people=0;rounds=[]
 for room in rooms:
  selected=set(room['comparison']['first_seats']);people+=len(selected)
  final={p['pid']:p for p in room['placements'] if p['pid'] in selected}
  champs=sum(p['rank']==1 for p in room['placements'])
  seen=defaultdict(set);bought=defaultdict(set);ever=defaultdict(set)
  for rnd in room['rounds']:
   for row in rnd['ledger']:
    pid=row['pid']
    if pid not in selected:continue
    ever[pid].update(row['deck'])
    for event in row['exposure']:seen[pid].add(event['name']);cards[event['name']]['offer_slots']+=1
    for action in row['actions']:
     if action['kind']=='buy':bought[pid].add(action['name']);cards[action['name']]['purchases']+=1
   for b in rnd['battles']:
    for i,p in enumerate(b['participants']):
     if i==1 and b['ghost'] or p['pid'] not in selected:continue
     books=([elements[p['spec']]] if p['spec'] else [])+([routes[p['route']]] if p['route'] else [])
     for book in books:Statistics.combat(book,b['winner'],i)
     for name in set(p['deck']):
      Statistics.combat(cards[name],b['winner'],i)
      cards[name]['casts']+=b['executed_by_seat'][i].get(name,0)
  for pid,p in final.items():
   books=([elements[p['spec']]] if p['spec'] else [])+([routes[p['route']]] if p['route'] else [])
   for book in books:Statistics.ending(book,p,(1/champs if p['rank']==1 else 0))
   for name in set(p['deck']):Statistics.ending(cards[name],p,(1/champs if p['rank']==1 else 0))
   for name in seen[pid]:cards[name]['exposed']+=1
   for name in bought[pid]:cards[name]['buyers']+=1
   for name in ever[pid]:cards[name]['ever']+=1
 result=[]
 for name,b in cards.items():
  c=CARDS[name];m=Statistics.metrics(b)
  m.update(name=name,element=c.element,rarity=c.rarity,carry_rate=b['players']/max(1,people),
   exposed_players=b['exposed'],buying_players=b['buyers'],exposure_conversion=b['buyers']/b['exposed'] if b['exposed'] else None,
   ever_carry_rate=b['ever']/max(1,people),casts=b['casts'])
  result.append(m)
 return dict(games=len(rooms),players=people,elements={k:Statistics.metrics(v) for k,v in elements.items()},
  routes={k:Statistics.metrics(v) for k,v in routes.items()},cards=result)

def contrast_ci(rooms):
 values=[]
 for r in rooms:
  seats=set(r['comparison']['first_seats'])
  first=[p['score'] for p in r['placements'] if p['pid'] in seats]
  second=[p['score'] for p in r['placements'] if p['pid'] not in seats]
  values.append(sum(first)/2-sum(second)/2)
 mean=sum(values)/len(values)
 se=math.sqrt(sum((x-mean)**2 for x in values)/max(1,len(values)-1)/len(values))
 return dict(mean=mean,low=mean-1.96*se,high=mean+1.96*se,games=len(values))

def main():
 t=load(OUT/'training.json');allstats=load(OUT/'statistics.json');old=load(ROOT/'research/v1.2-quick-500-final-20261028/statistics.json')
 rooms=[json.loads(gzip.decompress(p.read_bytes())) for p in sorted((OUT/'batches').glob('*/room-*.json.gz'))]
 assert len(rooms)==1000 and {r['seed'] for r in rooms}==set(range(284000,285000))
 assert all(r['pool_total']==870 for r in rooms)
 held=[r for r in rooms if r['comparison']['segment']=='holdout'];assert len(held)==200
 finalrooms=[r for r in held if r['comparison']['first']==t['final_policy']['checkpoint']]
 current=cohort(held);final=cohort(finalrooms);ci=contrast_ci(held);fci=contrast_ci(finalrooms)
 save('selected-holdout-statistics.json',current);save('final-policy-holdout-statistics.json',final)
 save('paired-score-intervals.json',dict(selected_versions=ci,final_policy=fci))
 cn={'fire':'火','water':'水','earth':'土','wind':'风','poison':'毒'}
 lines=['# v1.2 · 1000局运转AI训练报告','',
  '**已完成10批×100局完整四AI赛事。** 每批60训练、20验证、20封存对照；共600局参与更新、200局用于检查点选择、200局保留评价。所有对局使用230张、870份库存及严格位次前快照；独立于v1.1客户端。',
  '',f"总计{allstats['players']}人次、{allstats['battles']}场战斗；输入源码/规则哈希复核通过，失效跳过{sum(allstats['sequence_skips'].values())}。最终检查点 `{t['final_policy']['checkpoint']}`，接受{t['accepted_steps']}次更新，其余回退保留。",
  '', '## 规则确认与删除', '',
  '- 土系达到名义致命伤害时，即使对方已有风系护命，仍耗尽护盾碎盾、使防御归零，正常触发保留1血；保1没有死亡，不截断后续序列。',
  '- 双方本位效果读取各自/对方打牌前快照，本牌固定攻防与首次层不用于本牌效果；本位新盾、护命、复活、减伤等从下一位起保护对方效果，同位治疗不能挽救本位致命伤害。卡内明确先后及运转承诺保留。',
  '- 删除圣盾、愈合之光、战术大师、治愈洪流、破军、破障法阵、盾墙、蓄势、稳固结界：9张/42份，其余数值与经济不变。当前通用40张、全卡230张、库存870份。',
  '- 230张逐卡低/高资源执行及18项当前边界/AI回归通过，v1.1冻结校验通过。旧239张及旧测试完整归档在baseline-code/。',
  '', '## 过去500局的复盘', '',
  '旧批次保存了完整赛事账本、战斗种子和逐牌施放统计，未保存全部逐事件战斗日志。本次利用冻结239张快照与归档引擎重放24场，全部胜者和结算生命与原记录一致；详细事件及实际出牌顺序见historical-replays.json，历史摘要见historical-analysis.json。',
  '', '旧AI主要按面板、固定抽牌标签和指定路线选牌，没有充分评估条件加费、费用曲线、选择目标、已知置顶、弃置后的重摸与洗牌时机。18张通用高阶牌零购买，说明携带率混入策略盲区；其中6张已按本次要求删除，剩余12张在下方复审。',
  '', '## 策略和小步训练方法', '',
  '构筑、战斗出牌及合法候选选择共享13项机制权重。新增即时抽牌/回费、后续资源、检索衔接、循环、弃置、启动、间隔与防护估值；根据手牌费用、毒层、先前出牌/耗费等判断条件收益。穿甲会考虑先凑耗费档位，顺风会等待风牌计数；即时抽取优先可继续运转的牌，弃牌/手牌置顶优先低当前价值牌。洗牌会权衡弃牌堆可重用收益及破坏已知置顶的损失。',
  '', '只使用自己的手牌/已知组成、明确揭示或主动置顶的牌和公开对手状态。没有读取未揭示牌堆顺序、未来随机数或对手私有牌组；已知置顶记录在洗牌和随机回插时失效。',
  '', '每批候选相对现检查点各权重最多变化5%。更新方向来自60训练局中实际施放/牌组特征与名次分的收缩相关，部分扣除元素与风格均值，奖励附带少量战斗胜率及胜场斩杀时间。训练均分不降低且20验证局相对均分优势≥0.2才接受；否则回退。此为机制特征策略搜索，不是已证明最优的策略或无偏因果梯度。',
  '', '验证完成后才确定并派遣20局封存对照：每局2个选定模型、2个不可变旧策略，座位随机，四名AI独立随机六类风格。对照双方均使用同样的230张和新规则，避免把删卡/规则变化当作训练提升。封存结果不参与参数更新或选择。',
  '', '|批次|训练均分差|验证均分差|接受|选定检查点|','|---|---:|---:|---|---|']
 for b in t['batches']:lines.append(f"|{b['batch']}|{b['train_score_delta']:+.3f}|{b['validation_score_delta']:+.3f}|{'是' if b['accepted'] else '否'}|{b['selected']}|")
 lines+=['','## 对旧AI的封存比较','',
  '下表为200局中的逐批选定模型对旧策略，每组400人次；选定模型版本随批次变化，不能全算作最终模型的单次终测。','',
  '|指标|逐批选定模型|不可变旧策略|','|---|---:|---:|']
 a,b=t['heldout_selected'],t['heldout_legacy']
 metrics=[('名次平均分','mean_score',False),('夺冠率','championship_rate',True),('战斗胜率','win_rate',True),
  ('胜场平均斩杀行动值','winner_time',False),('每场正式出牌','plays_per_battle',False),('每场即时抽牌','instant_draw_per_battle',False),
  ('每场即时回费','immediate_fee_per_battle',False),('每场弃牌','discard_per_battle',False),('每场洗牌','shuffle_per_battle',False),('每阶段剩余费用','unused_fee_per_stage',False)]
 for label,key,ispct in metrics:lines.append(f"|{label}|{pct(a[key]) if ispct else number(a[key])}|{pct(b[key]) if ispct else number(b[key])}|")
 lines+=['',f"按完整赛事配对的均分差为{ci['mean']:+.3f}，描述性95%区间[{ci['low']:+.3f}, {ci['high']:+.3f}]。胜场平均斩杀时间还受获胜对局组成影响，不能单独证明因果上的斩杀提速。",
  '',f"最终检查点另有{len(finalrooms)}局未参与更新的对照：均分差{fci['mean']:+.3f}，描述性95%区间[{fci['low']:+.3f}, {fci['high']:+.3f}]。样本较小时保留不确定性。",
  '', '## 元素与路线表现','',
  '以下只统计200封存局中的选定模型（400人次），不混入作为对手的旧策略。完整1000局混合策略分布另见distribution-report.md；未专精/未取得路线者不强塞入某元素或路线。','',
  '|元素|最终人数|战斗胜率|夺冠率|人均分|','|---|---:|---:|---:|---:|']
 for e,m in sorted(current['elements'].items(),key=lambda p:p[1]['mean_score'] if p[1]['mean_score'] is not None else -100,reverse=True):lines.append(f"|{cn[e]}|{m['players']}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','|路线|最终人数|战斗胜率|夺冠率|人均分|','|---|---:|---:|---:|---:|']
 for n,m in sorted(current['routes'].items(),key=lambda p:p[1]['mean_score'] if p[1]['mean_score'] is not None else -100,reverse=True):lines.append(f"|{n}|{m['players']}{'（小）' if m['players']<30 else ''}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','## 携带率与精简复审','',
  '逐卡主表按上述400名选定模型玩家最终仍持有计人，同名重复不重复计数。携带得分率=累计名次分/(3×携带人数)，范围−100%至100%。携带表现受元素/路线、曝光、费用和幸存者偏差影响。','',
  '旧AI零采用、且本次仍保留的12张通用牌：','',
  '|卡牌|携带人数|携带率|曝光人数|购买率|携带人均分|夺冠率|','|---|---:|---:|---:|---:|---:|---:|']
 previous_zero={c['name'] for c in old['cards'] if not c['casts'] and c['name'] in CARDS}
 for c in current['cards']:
  if c['name'] in previous_zero:lines.append(f"|{c['name']}|{c['players']}|{pct(c['carry_rate'])}|{c['exposed_players']}|{pct(c['exposure_conversion'])}|{number(c['mean_score'])}|{pct(c['championship_rate'])}|")
 lines+=['','不能把以上与旧500局的前后差异全部归因于AI，因为卡表与同位次规则同时发生变化；同规则旧策略对照才用于判断训练方向。低携带卡继续按同元素/同品质、曝光和样本量复审，不以相对排名靠后自动删除高携带普通牌。','',
  '完整230张的选定模型逐卡表见[cards-selected-holdout.md](cards-selected-holdout.md)，总体训练分布见[distribution-report.md](distribution-report.md)与[cards.md](cards.md)；原始机器统计、每批候选/保留检查点、训练梯度、完整逐局账本和输入哈希均在本目录。最终模型为final-policy.json，并已写入独立模拟器rules/ai-policy.json作为默认；未接入v1.1客户端。']
 report=OUT/'report.md'
 if report.exists():report.replace(OUT/'distribution-report.md')
 report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 cardlines=['# 选定模型 · 230张逐卡封存统计','',f"{len(held)}局、{current['players']}名选定模型玩家；不包含旧策略对手。",'',
  '|卡牌|携带人数|携带率|得分率|人均分|夺冠率|战斗胜率|曝光人数|购买率|','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for c in sorted(current['cards'],key=lambda c:c['carry_rate']):cardlines.append(f"|{c['name']}|{c['players']}|{pct(c['carry_rate'])}|{pct(c['score_rate'])}|{number(c['mean_score'])}|{pct(c['championship_rate'])}|{pct(c['win_rate'])}|{c['exposed_players']}|{pct(c['exposure_conversion'])}|")
 (OUT/'cards-selected-holdout.md').write_text('\n'.join(cardlines)+'\n',encoding='utf-8')
 print(json.dumps(dict(games=1000,battles=allstats['battles'],accepted=t['accepted_steps'],checkpoint=t['final_policy']['checkpoint'],pooled_ci=ci,final_ci=fci,selected=a,baseline=b),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
