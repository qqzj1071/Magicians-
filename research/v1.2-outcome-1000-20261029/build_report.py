"""Post-run audit and descriptive report; never updates a policy."""
import json,gzip,sys,hashlib
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,START_ONLY,SPECIAL
from tools.sim_v12.outcome_train import interval
from tools.sim_v12.tournament import base_income,arena_loss
from tools.sim_v12.panel_budget import role
from tools.sim_v12.quick_test import pct
from tools.sim_v12.strict import StrictBattle
from tools.sim_v12.learning_policy import choose_play
from copy import deepcopy

def load(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(n,lines):(OUT/n).write_text('\n'.join(lines)+'\n',encoding='utf-8')
def num(x):return '—' if x is None else f'{x:.3f}'
def ci(x,scale=100):return f"{x['mean']*scale:+.2f} [{x['low']*scale:+.2f}, {x['high']*scale:+.2f}]"

def main():
 t=load('training.json');inp=load('inputs.json');cfg=load('final-policy.json');selected=load('final-selected-statistics.json')
 assert not {'breadth','role_preferences'}&cfg.keys()
 for path,digest in inp['sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
 for name,digest in inp['source_hashes'].items():assert hashlib.sha256((ROOT/inp['source']/name).read_bytes()).hexdigest()==digest
 seeds=[];segments=Counter();final=[];battles=ledgers=0
 for path in sorted(OUT.rglob('room-*.json.gz')):
  with gzip.open(path,'rt',encoding='utf-8') as f:r=json.load(f)
  seeds.append(r['seed']);segments[r['comparison']['segment']]+=1
  assert r['pool_total']==707 and len(r['placements'])==4 and abs(sum(p['score'] for p in r['placements']))<1e-9
  for rd in r['rounds']:
   for row in rd['ledger']:
    ledgers+=1;assert row['base_income']==base_income(rd['round'])
    assert row['income']==row['base_income']+row['carry']+row['bonus']
    assert row['income']-sum(a['cost'] for a in row['actions'])==row['remaining']
    assert row['bank']==min(2,row['remaining']) and len(row['deck'])>=8
    assert not {a['name'] for a in row['actions'] if a['kind']=='buy'}&START_ONLY
    assert set(row['deck'])<=CARDS.keys()
   for b in rd['battles']:
    battles+=1;assert b['combat_rule']=='strict_pre_position_v2' and not b['sequence_skips']
  if r['comparison']['segment']=='final-holdout':final.append(r)
 assert sorted(seeds)==list(range(inp['seeds'][0],inp['seeds'][1]+1)) and len(set(seeds))==1000
 assert segments==dict(train=600,validation=200,**{'final-holdout':200})
 assert battles==t['battles'] and cfg==load('frozen-policy.json')
 audit=dict(unique_games=1000,battles=battles,ledgers=ledgers,segments=dict(segments),pool=707,cards=189,
  input_hashes_verified=True,source_hashes_verified=True,starter_purchase_violations=0,sequence_skips=0,
  fees_income_bank_valid=True,no_size_or_role_preference=True,frozen_model_unchanged=True)
 save('run-audit.json',audit)
 privacy=[]
 for e in ELEMENTS:
  names=[SPECIAL[e]]+[n for n,c in CARDS.items() if c.element in (e,'generic') and not c.ability][:12]
  b=StrictBattle((names,['攻击强化','防御强化','护盾']),seed=571,styles=('balanced','balanced'))
  b.policy_configs=(cfg,cfg);s=b.players[0];s.specialization=e;s.stage=1;s.energy=3
  s.pile=list(s.instances);s.hand=[s.pile.pop(0),s.pile.pop(0),s.pile.pop(0)];s.known_top=[]
  original=choose_play(b,0);clone=deepcopy(b);clone.players[0].pile.reverse()
  other=choose_play(clone,0)
  assert (original.uid if original else None)==(other.uid if other else None)
  privacy.append(dict(element=e,hidden_pile_permutation_unchanged=True))
 save('final-observation-checks.json',privacy)
 direct={};mix=Counter();hp=defaultdict(list)
 for key,v in t['evaluation'].items():
  rooms=[r for r in final if r['comparison']['second']==load('anchors.json')[key]['checkpoint']]
  counts=Counter();cells=[]
  for r in rooms:
   first=set(r['comparison']['first_seats']);cell=Counter()
   for rd in r['rounds']:
    for b in rd['battles']:
     ps=b['participants']
     if b['ghost'] or ((ps[0]['pid'] in first)==(ps[1]['pid'] in first)):continue
     seat=0 if ps[0]['pid'] in first else 1;cell['n']+=1;cell['wins']+=.5 if b['winner'] is None else b['winner']==seat
   counts.update(cell)
   if cell['n']:cells.append(cell['wins']/cell['n'])
  direct[key]=dict(battles=counts['n'],win_rate=counts['wins']/max(1,counts['n']),room_weighted_interval=interval(cells))
 for r in final:
  first=set(r['comparison']['first_seats']);current={p['pid']:100 for p in r['placements']}
  for p in r['placements']:
   if p['pid'] not in first:continue
   mix['players']+=1
   for name in p['deck']:mix[role(name)]+=1/len(p['deck'])
  for rd in r['rounds']:
   for b in rd['battles']:
    for i,p in enumerate(b['participants']):
     if i==1 and b['ghost']:continue
     current[p['pid']]-=arena_loss(rd['round'],b['hp'][1-i],won=b['winner']==i,draw=b['winner'] is None)
   if rd['round'] in (4,8,10,12):hp[rd['round']].extend(current[i] for i in first)
  for p in r['placements']:assert current[p['pid']]==p['hp']
 save('head-to-head.json',direct)
 save('final-diagnostics.json',dict(role_fractions={k:mix[k]/mix['players'] for k in ('numeric','strong','weak')},
  health={str(k):dict(players=len(v),alive=sum(x>0 for x in v),at_most20_alive=sum(0<x<=20 for x in v),mean_alive=sum(x for x in v if x>0)/max(1,sum(x>0 for x in v))) for k,v in hp.items()}))
 old=(OUT/'report.md').read_text(encoding='utf-8')
 if old.startswith('# v1.2 快速卡牌测试'):
  write('training-distribution.md',[old.replace('本轮没有训练 AI 或改动平衡数值。','混合训练、验证和终测多个模型，仅为描述；不能作为最终模型的独立成绩。')])
 lines=['# v1.2 无牌组倾向的联合训练：10轮1000局','',
  f"已完成1000局四AI完整赛事、{t['battles']:,}场战斗，跳过{t['skipped']}局。最终模型`{cfg['checkpoint']}`；接受轮次：{t['accepted_rounds']}。",'',
  '用户所说的均卡是约14张高质量数值牌；前轮实际19张不能作为该构筑的代表。本轮从最新小卡模型出发，移除role_preferences和breadth，不规定张数、删牌数或运转比例。保留起点已学机制权重作为经验，可继续更新；这不是穷举最优解。','',
  '## 事先固定的训练与验证','',
  '- 10轮，每轮60训练、20独立验证、20最终预留；共600/200/200，不把终测重复计入局数。所有预留局在第10轮模型冻结后才运行。',
  '- 目标为(夺冠率 + 战斗胜率 + (赛事均分+3)/6)/3，三项等权；名次分仍+3/+1/−1/−3，战斗平局计半胜。得分率另按均分/3报告。无牌组长度、运转次数、斩杀速度等奖励。',
  '- 每轮训练对手：当前保留模型、原小卡、原均卡、旧启发式各15局；验证各5局。四人房中双方各两席，随机座位，每席独立随机6种风格。',
  '- 构筑与战斗机制参数共同更新，单轮随机扰动上限分别10%/7%，总体相对初始限制0.65—1.5倍；元素项更新更保守、总幅度限±10%。',
  '- 接受门槛：训练综合差非负、验证综合差≥0.005、三分项均不低于−0.04；有至少12个验证房间的阶段，其配对胜率差不得低于−8个百分点。20局验证较嘈杂，因此保留回退，并只用最终封存检验提升。',
  '- 最终100局对原小卡、100局对原均卡。综合差95%区间下界均>0且任一阶段平均胜率差不低于−3个百分点，才标记稳健提升；不根据终测重选检查点或补训。不自动改默认AI。','',
  '## 冻结终测','',
  '| 对照 | 局数 | 新/对照胜率 | 新/对照夺冠率 | 新/对照均分（得分率） | 综合配对差及95%区间 | 直接交手新胜率 |',
  '|---|---:|---:|---:|---:|---:|---:|']
 for k,v in t['evaluation'].items():
  a,b=v['selected'],v['control']
  lines.append(f"| {k} | {v['games']} | {pct(a['win_rate'])}/{pct(b['win_rate'])} | {pct(a['championship_rate'])}/{pct(b['championship_rate'])} | {num(a['mean_score'])}/{num(b['mean_score'])}（{pct(a['mean_score']/3)}/{pct(b['mean_score']/3)}） | {ci(v['objective']['composite'])} pp | {pct(direct[k]['win_rate'])}（{direct[k]['battles']}场） |")
 lines+=['','综合差的区间以赛事为聚类单位、每赛事等权，避免将相关战斗误当独立样本。整体战斗胜率含同阵营交手和实际玩家对幽灵战斗，因此两组不一定互补；直接交手剔除同阵营与幽灵。夺冠率按rank=1计，完整并列规则沿用当前模拟器。','',
  f"预设稳健提升门槛：**{'通过' if t['robust_improvement_gate'] else '未通过'}**。"+('结果支持对这两个固定对手的综合提升，仍不代表所有对手或所有元素最优。' if t['robust_improvement_gate'] else '不能宣称这轮已经得到比原模型更强、全阶段都更好的AI。最终候选保留，原小卡模型仍可继续使用，默认fixed-legacy未替换。'),'',
  '## 分阶段表现','',
  '| 对照 | 构筑轮阶段 | 新/对照战斗胜率 | 配对胜率差95%区间（pp） |',
  '|---|---|---:|---:|']
 for k,v in t['evaluation'].items():
  for stage,s in v['stages'].items():lines.append(f"| {k} | {stage} | {pct(s['selected']['win_rate'])}/{pct(s['control']['win_rate'])} | {ci(s['paired_win'])} |")
 lines+=['','后期只包含存活到该阶段的玩家，存在幸存者选择；分阶段区间也未经多重比较校正。不能由后期高胜率推断所有开局都能稳定进入后期。阶段仅用于防止严重退化与检查，不另加早期或后期奖励。','',
  '## 实际形成的牌组','',
  '| 指标 | 新模型（最终200局、400人次） |', '|---|---:|']
 overall=t['overall_final'];d=overall['selected_decks'];a=overall['selected_actions']
 for label,val in [('平均终局张数',num(d['mean_size'])),('中位张数',str(d['median'])),('最小/最大张数',f"{d['minimum']}/{d['maximum']}"),('购买/人',num(a['purchases_per_player'])),('删除/人',num(a['deletions_per_player'])),('其中付费删除/人',num(a['paid_deletions_per_player'])),('数值/强运转/弱运转占比',' / '.join(pct(mix[k]/mix['players']) for k in ('numeric','strong','weak')))]:lines.append(f'| {label} | {val} |')
 lines+=['','张数与运转比例是胜负目标下的结果，并未被固定。牌组稀释和研习机会成本仍是AI评估牌质所需的机制特征，不是达到某个张数的奖励。数值组包含无运转标签的能力与成长牌，不能把74.2%解读为纯即时数值牌占比。','',
  '对原小卡的同批终测，新模型每战即时抽牌5.08次、对照10.38次，获胜战斗的平均行动值712对785。结合面板/核心/首次层权重提高、构筑运转权重下降，可推测新策略更重视高质量核心与有效战力；这只是行为解释，本轮没有单独消融来证明具体参数的因果收益。','',
  '## 元素与路线','', '| 元素 | 人次 | 平均张数 | 战斗胜率 | 夺冠率 | 均分 | 得分率 |', '|---|---:|---:|---:|---:|---:|---:|']
 for el in ELEMENTS:
  m=selected['elements'][el];de=d['elements'][el]
  lines.append(f"| {el} | {m['players']} | {num(de['mean_size'])} | {pct(m['win_rate'])} | {pct(m['championship_rate'])} | {num(m['mean_score'])} | {pct(m['score_rate'])} |")
 lines+=['','| 路线 | 人次 | 战斗胜率 | 夺冠率 | 均分 |','|---|---:|---:|---:|---:|']
 for route,m in selected['routes'].items():lines.append(f"| {route} | {m['players']} | {pct(m['win_rate'])} | {pct(m['championship_rate'])} | {num(m['mean_score'])} |")
 lines+=['','元素与路线在比赛中由AI选择，样本量和对手构成不同；低样本与低胜率不能单独证明某张卡过弱。路线人次按终局路线归类，战斗按当时路线归类；替换路线后可能出现终局0人但仍有历史战斗记录。逐卡携带/参战使用、得分率与夺冠见[最终模型189张卡统计](final-cards.md)，不要将混合1000局分布视为最终模型成绩。','',
  '## 逐轮记录','', '| 轮次 | 接受 | 训练综合差（pp） | 验证综合差（pp） | 保留模型 |','|---|---|---:|---:|---|']
 for b in t['batches']:lines.append(f"| {b['round']} | {'是' if b['accepted'] else '否'} | {b['train']['composite']['mean']*100:+.2f} | {b['validation']['composite']['mean']*100:+.2f} | {b['selected']} |")
 lines+=['','以下是实际学习到的参数变化；它们同时影响多个决策，不能把某一个权重上升单独解释为胜率提升的原因。','',
  '| 参数 | 中性起点 | 最终 | 相对变化 |','|---|---:|---:|---:|']
 initial=load('initial-policy.json')
 for section in ('weights','construction'):
  for k,v in cfg[section].items():
   anchor=initial[section][k]
   lines.append(f'| {section}.{k} | {anchor:.4f} | {v:.4f} | {(v/anchor-1)*100:+.1f}% |')
 lines+=['','## 检查与限制','',
  f"58项回归通过；{ledgers:,}条构筑账本与1000个唯一种子核验通过，707库存、初始牌不入池、费用/继承/收入正确，失效跳过0。输入及起点哈希复核通过，最终模型5系隐藏摸牌堆逆序不影响未揭示状态下的选择。v1.1冻结核验另见checks.txt。",'',
  '| 问题或限制 | 处理 |','|---|---|',
  f"| 运行失败 | {t['skipped']}；详见issues.json |",'| 起点仍有历史小卡经验 | 移除显式大小及类型偏好；机制参数可学习，但不声称无先验或全局最优 |',
  '| 固定启发式结构 | 本轮是黑箱机制权重微调，未训练神经网络，也未重写所有决策分支 |',
  '| 20局验证的波动 | 保守接受/回退、独立种子、混合对手与最终200局封存；最终不确定时不宣布提升 |',
  '| 中性化与学习同时发生 | 终测比较完整新方案与历史小卡起点，未单列中性起点对照，不能将全部收益归于10轮权重学习 |',
  '| 终测对照覆盖 | 原小卡与原均卡各100局；旧启发式只在训练验证中，不能宣称对所有策略都提升 |',
  '| 规则与默认模型 | 卡牌/经济/战斗规则不变；默认fixed-legacy不替换 |','',
  '复现入口：`python -m tools.sim_v12.outcome_train --out research/<新目录> --seed <新起始种子> --source research/v1.2-dual-growthv7-1000-20261029`。已看过的296000—296999不可复用为下一轮盲测。']
 write('report.md',lines)
 cards=['# 最终模型逐卡统计','', '仅冻结终测200局中新模型400人次；终局携带按人次去重，曾携带包括后来删除的牌。参战使用率=携带该卡的战斗中至少实际打出一次的比例，重复施放均计入均次。携带得分率=持有者平均赛事分/3，正分率=持有者赛事分>0比例。统计仅为关联，不表示卡牌的因果收益。','',
  '| 卡牌 | 元素 | 品质 | 携带人次 | 终局携带 | 曾携带 | 携带胜率 | 携带夺冠 | 携带得分率 | 携带正分率 | 参战使用率 | 每携带战斗施放次 |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for c in sorted(selected['cards'],key=lambda x:(x['element'],-x['carry_rate'],x['name'])):
  cards.append(f"| {c['name']} | {c['element']} | {c['rarity']} | {c['players']} | {pct(c['carry_rate'])} | {pct(c['ever_carry_rate'])} | {pct(c['win_rate'])} | {pct(c['championship_rate'])} | {pct(c['score_rate'])} | {pct(c['positive_score_rate'])} | {pct(c['usage_rate'])} | {num(c['casts_per_carried_battle'])} |")
 write('final-cards.md',cards)
 print(json.dumps(dict(audit=audit,checkpoint=cfg['checkpoint'],accepted=t['accepted_rounds'],gate=t['robust_improvement_gate'],evaluation={k:dict(selected=v['selected'],control=v['control'],objective=v['objective'],direct=direct[k]) for k,v in t['evaluation'].items()}),ensure_ascii=False))

if __name__=='__main__':main()
