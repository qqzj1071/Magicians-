"""Read sealed outputs only; no additional games or parameter selection."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS
from tools.sim_v12.quick_test import pct,number
from tools.sim_v12.construction import REPEAT
OUT=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
 t=load(OUT/'training.json');stats=load(OUT/'statistics.json');final=load(OUT/'final-selected-statistics.json');issues=load(OUT/'issues.json')
 rooms=[];repeats=defaultdict(lambda:Counter());cycles=Counter();held=[];mainholders=Counter();elementplayers=Counter()
 for p in sorted((OUT/'batches').glob('*/room-*.json.gz')):
  r=json.loads(gzip.decompress(p.read_bytes()));rooms.append(r)
  if r['comparison']['segment']!='final-holdout':continue
  held.append(r);selected=set(r['comparison']['first_seats']);control=r['comparison']['second']
  for player in r['placements']:
   if player['pid'] in selected:
    elementplayers[player['spec']]+=1
    for name in set(player['deck']):
     if CARDS[name].element in ('generic',player['spec']):mainholders[name]+=1
  for rd in r['rounds']:
   for b in rd['battles']:
    for i,p in enumerate(b['participants']):
     if i==1 and b['ghost']:continue
     key='selected' if p['pid'] in selected else control
     repeats[key]['battles']+=1
     repeats[key]['repeat_core_casts']+=sum(max(0,n-1) for name,n in b['executed_by_seat'][i].items() if name in REPEAT)
     if p['pid'] in selected:
      repeats['selected_vs_'+control]['battles']+=1
      repeats['selected_vs_'+control]['repeat_core_casts']+=sum(max(0,n-1) for name,n in b['executed_by_seat'][i].items() if name in REPEAT)
     cycles.update(b['cycle_decisions'][i])
 assert len(rooms)==t['completed'] and len({r['seed'] for r in rooms})==len(rooms)
 assert all(r['pool_total']==722 for r in rooms)
 for c in final['cards']:
  denominator=final['players'] if c['element']=='generic' else elementplayers[c['element']]
  c['same_element_carry_rate']=mainholders[c['name']]/denominator if denominator else None
  c['small_sample']=c['players']<30
 save('final-card-statistics.json',final);save('repeat-diagnostics.json',dict(repeats=repeats,cycles=cycles))
 cn={'fire':'火','water':'水','earth':'土','wind':'风','poison':'毒'}
 lines=['# v1.2 · 薄牌组构筑AI：20轮2000局','',
  '**结论：高质量薄牌组方向获得支持，但暂不替换默认。** 对相同战斗AI＋原构筑，配对均分差区间高于0；对旧默认点估计更好，但区间仍跨0，未同时通过两个部署门槛。候选保留，默认仍为旧启发式。','',
  f"计划2000次赛事尝试，实际完成{t['completed']}局，跳过{t['skipped']}局，共{stats['battles']}场战斗。24项当前回归通过，193张完成双资源环境和重复施放校验。训练期间输入哈希复核通过；v1.1客户端未改动。",'',
  '## 卡牌与状态清理','',
  '按确认清单删除33张元素牌与4张通用牌，共37张/148份；保留坚岩与风蚀，改删垒石。现193张、722份库存，通用36张。风暴永久加成副弹改为固定80＋发射时有效攻击30%，重复打出仍分别增加副弹。完整卡表见[现行总表](../../docs/cards-v1.2/catalogue.md)，删除前记录在retired-cards.json。',
  '', '清除已删传奇的额外费用/少抽牌、混系计数和额外元素层组件；同时清除余震待触发抽牌、渗骨毒素下阶段检查、速腐衰减伤害、毒牙挂毒、焰心屏障发射前盾、爆裂弹头返烬、腐化之躯减伤、发射前到期减伤等无来源状态。共享护命、复活、天岚真伤、破盾返盾、永恒壁垒和潮声延迟回复保留。静态来源/引用审计无残留，见cleanup-audit.json。',
  '', '风蚀、毒潮、万毒爆的描述补充为按同位快照确认的净化/消耗量，避免将同步去重误读为取消其中一方效果。首次元素层只在本场第一次打出获得；重复施放只重复固定面板和明确可重复的机制，不凭空重复首次层。',
  '', '## 构筑改动与防过拟合','',
  '新构筑按边际牌质决定购买：免费牌也会占抽牌位，不再因免费就自动抓取；低收益牌会降低核心重摸概率。对能反复叠加永久收益的牌单独估值，兼顾费用与过牌配比。删除不再只盯初始牌，也可清理非初始低价值牌；每轮合法次数、费用、最少8张和至少3张主系附魔等约束保持不变。',
  '', '牌组目标大小是软阈值，不是硬上限或强制删到固定数量。战斗出牌、置顶、弃牌等运转参数固定为上一轮候选accepted-08，本轮只更新构筑参数，用来检验高质量循环假说。',
  '', '第1–16轮每轮60训练、20验证、20封存滚动对照；第17–20轮完全冻结最终检查点，共400局盲测。合计2000次尝试，其中960训练、320验证、720封存评价。每步最多3%，参数有界；验证和封存数据不进入更新梯度，所有种子与上一轮不重叠。',
  '', '终测分成两个同规则对照，各计划200局：①固定旧启发式；②完全相同的战斗AI＋原较宽松构筑逻辑。第②组直接隔离构筑变化。只有最终检查点同时通过两个对照的配对均分区间门槛，且样本和错误率合格，才替换默认AI。不能把删卡、风暴改动、训练自弈或单批验证上升当作泛化提升。',
  '',f"接受{t['accepted_steps']}次更新，最终候选 `{t['candidate']['checkpoint']}`；默认采用 `{t['deployed']}`，部署门槛{'通过' if t['promoted'] else '未通过，保留原策略'}。",'',
  '|轮次|用途|训练均分差|验证均分差|接受|检查点|','|---|---|---:|---:|---|---|']
 for b in t['batches']:
  lines.append(f"|{b['round']}|{'冻结终测' if b.get('frozen_final_test') else '训练/验证/封存'}|{number(b.get('train_delta'))}|{number(b.get('validation_delta'))}|{'—' if b['accepted'] is None else '是' if b['accepted'] else '否'}|{b['selected']}|")
 lines+=['','## 400局冻结终测','']
 labels={'legacy':'固定旧启发式','heavy':'同战斗AI＋原构筑'}
 for key,e in t['evaluation'].items():
  a,b=e['selected'],e['control'];da,db=e['selected_decks'],e['control_decks'];ci=e['paired']
  lines+=['','### 对照：'+labels[key], '',f"完成{e['games']}局。配对赛事均分差{number(ci['mean'])}，描述性95%区间[{number(ci['low'])}, {number(ci['high'])}]。",'',
   '|指标|最终选定模型|对照|','|---|---:|---:|']
  for label,k,ispct in [('名次平均分','mean_score',False),('夺冠率','championship_rate',True),('战斗胜率','win_rate',True),('胜场斩杀行动值','winner_time',False),('每场正式出牌','plays_per_battle',False),('每场即时抽牌','instant_draw_per_battle',False),('每场即时回费','immediate_fee_per_battle',False),('每场弃牌','discard_per_battle',False),('每场洗牌','shuffle_per_battle',False)]:
   fmt=pct if ispct else number;lines.append(f'|{label}|{fmt(a[k])}|{fmt(b[k])}|')
  for label,k in [('最终牌组大小','deck_size'),('可循环牌数量','repeatable_size'),('每名玩家购买数','purchases_per_player'),('每名玩家删牌数','deletions_per_player'),('其中付费删牌数','paid_deletions_per_player')]:lines.append(f'|{label}|{number(da[k])}|{number(db[k])}|')
 lines+=['','斩杀时间只在胜场中统计，受获胜对局组成影响；更多删除或更小牌组不是胜利本身。重复永久收益牌的实际额外施放次数见repeat-diagnostics.json。','',
  '## 最终模型的元素/路线与逐卡表现','',
  f"以下只计最终400局中选定模型的{final['players']}人次，不混入对照对手。整体2000局同时含训练候选与不同对照，不视为最终模型独立平衡测试。",'',
  '|元素|人数|战斗胜率|夺冠率|人均分|','|---|---:|---:|---:|---:|']
 for e,m in sorted(final['elements'].items(),key=lambda p:p[1]['mean_score'] if p[1]['mean_score'] is not None else -100,reverse=True):lines.append(f"|{cn[e]}|{m['players']}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','|路线|人数|战斗胜率|夺冠率|人均分|','|---|---:|---:|---:|---:|']
 for name,m in sorted(final['routes'].items(),key=lambda p:p[1]['mean_score'] if p[1]['mean_score'] is not None else -100,reverse=True):lines.append(f"|{name}|{m['players']}{'（小）' if m['players']<30 else ''}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','完整193张携带率、同系携带率、携带得分率、夺冠率、携带参战施放率和平均施放次数见[final-cards.md](final-cards.md)及final-card-statistics.json。使用率=携带参战场次中至少正式打出一次的比例，并非“抽到后打出率”；当前逐局日志不提供后者的完整分母。携带表现为相关统计，路线/风格/对手结构和幸存者偏差仍会影响结果。','',
  '## 问题与跳过记录','', '|问题|处理|状态|','|---|---|---|',
  '|风神之翼删除后，穿甲＋风驰在间隔≤30时仍可形成不损费互抽|保留合法卡效，AI识别经济循环后改选/必要时主动结束；不截断已锁卡牌|已隔离；人类无限运转规则留待单独讨论|',
  '|首次层与额外永久层容易混淆|逐张重复施放验证，只有明确额外层会重复增加|检查通过|']
 lines+=['|最终牌组收敛至约8.2张，接近规则下限|保留小牌组候选，未因终测点估计更好就上线；防止把极端瘦身当成通用答案|待更多对手分布验证|',
  '|燃烧血统最终0人、血潮3人、大地之握7人等路线覆盖不足|完整列出人数，小样本不作强弱排名；不因该模型不选就继续删除卡牌|待专项构筑场景验证|']
 if not issues:lines.append('|训练对局异常|无跳过对局，不补造胜者|0项|')
 for i in issues:lines.append(f"|种子{i['seed']}：{i['error'].replace('|','/')}|跳过该局，保留error文件，不分配胜者|已记录|")
 lines+=['','## 携带与复用的讨论','',
  '相同战斗AI对照中，平均购买由25.65张降至10.36张，删除由9.15张增至11.15张，其中付费删除由0.89张增至3.18张；最终牌组由25.50张降至8.16张。实际每场出牌由28.32降至23.32，但即时回费由1.27升至1.98、洗牌由2.36升至4.61，胜场斩杀行动值由868.3降至748.1。收益来自选择和复用，而不是单纯打出更多牌。胜场组成差异仍限制因果解释。',
  '', '同战斗对照的胜率为56.2%对47.1%，配对赛事均分差+0.67，95%区间[+0.325,+1.015]，支持构筑瘦身发挥作用。对旧默认则为54.4%对49.2%，夺冠30.25%对19.75%，均分差+0.33、区间[−0.027,+0.687]；这个参照尚不足以支持默认替换。没有使用终测重新调参或追加比赛挑选结果。',
  '', '最终模型风系战斗胜率81.2%、夺冠78.9%，火56.4%/37.1%；灰烬循环112人、战斗胜率65.8%，风痕134人、80.7%。毒系仍仅24.1%战斗胜率、1.2%夺冠，蚀命85人、11.9%战斗胜率，说明削减低效牌不能替代毒系机制兑现和针对性AI的改进。这些数值属于当前双模型对照环境，不是全新AI四人平衡赛。',
  '', '同系携带方面，余烬引擎97.0%、深渊97.5%、层岩结构86.2%、山岳壁垒89.0%、风暴97.9%；相应携带参战平均施放分别5.13、2.10、1.85、2.01、0.80次。风暴作为永久效果，低于1的平均施放次数不等于没有后续收益；需要结合发射与激活时点，而非只看施放次数。',
  '', '部分牌最终零携带并不等于零购买或零使用：初始攻防牌可能前期用过、随后被删除。坚岩和风蚀按用户要求保留；薄模型最终不选它们，不能证明其在低费用过渡、对毒反制等场景无价值。路线专属牌也不能简单按全体携带率删除。',
  '', '后续宜固定本候选做针对路线、对手元素及较温和牌组大小的独立验证，不继续依当前终测压小牌组。特别需要保留毒系对策、检验零/小样本路线，区分“核心循环更集中”与“丧失反制和构筑多样性”。',
  '', '每轮候选、选定检查点、完整账本与种子均在batches/；失败单列issues.json。最终模型final-policy.json；训练期间源码/规则哈希在inputs.json，默认配置更新属于训练后输出。没有因训练结果改变卡牌数值或经济。']
 if (OUT/'report.md').read_text(encoding='utf-8').startswith('# v1.2 快速卡牌测试'):
  (OUT/'report.md').replace(OUT/'training-distribution.md')
 (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 cards=['# 最终冻结模型 · 193张逐卡统计','',f"{len(held)}局、{final['players']}名选定模型玩家，排除对照玩家。携带率按最终持有计；得分率=名次分/(3×携带人数)。",'',
  '|卡牌|人数|携带率|同系携带率|得分率|夺冠率|参战施放率|每携带参战施放次数|曝光购买率|',
  '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for c in sorted(final['cards'],key=lambda c:c['carry_rate']):cards.append(f"|{c['name']}|{c['players']}|{pct(c['carry_rate'])}|{pct(c['same_element_carry_rate'])}|{pct(c['score_rate'])}|{pct(c['championship_rate'])}|{pct(c['usage_rate'])}|{number(c['casts_per_carried_battle'])}|{pct(c['exposure_conversion'])}|")
 (OUT/'final-cards.md').write_text('\n'.join(cards)+'\n',encoding='utf-8')
 print(json.dumps(dict(attempted=t['attempted'],completed=t['completed'],skipped=t['skipped'],battles=stats['battles'],accepted=t['accepted_steps'],candidate=t['candidate']['checkpoint'],promoted=t['promoted'],evaluation=t['evaluation']),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
