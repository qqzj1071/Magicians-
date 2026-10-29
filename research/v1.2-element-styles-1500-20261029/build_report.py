"""Post-run audits and reports; does not select or update a model."""
import gzip,json,sys,hashlib
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,ROUTES,START_ONLY,SPECIAL
from tools.sim_v12.tournament import base_income
from tools.sim_v12.outcome_train import interval
from tools.sim_v12.quick_test import pct
from tools.sim_v12.cohort import selected_statistics
from tools.sim_v12.strict import StrictBattle
from tools.sim_v12.learning_policy import choose_play
from copy import deepcopy
LABEL=dict(fire='火',water='水',earth='土',wind='风',poison='毒')
def load(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(n,lines):(OUT/n).write_text('\n'.join(lines)+'\n',encoding='utf-8')
def num(x):return '—' if x is None else f'{x:.2f}'
def ci(x):return f"{100*x['mean']:+.1f} [{100*x['low']:+.1f}, {100*x['high']:+.1f}]"
def main():
 t=load('training.json');inp=load('inputs.json');frozen=load('frozen-policies.json')
 for name,digest in inp['sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
 assert hashlib.sha256((ROOT/inp['source']).read_bytes()).hexdigest()==inp['source_sha256']
 totals=Counter();segments=Counter();intents=defaultdict(Counter);seeds=[];battles=ledgers=0;final=[]
 for path in sorted(OUT.rglob('room-*.json.gz')):
  with gzip.open(path,'rt',encoding='utf-8') as f:r=json.load(f)
  c=r['comparison'];e=c['element'];seeds.append(r['seed']);totals[e]+=1;segments[(e,c['segment'],c['mode'])]+=1;intents[e][c['route_intent']]+=1
  assert r['pool_total']==693 and len(c['first_seats'])==1 and len(r['placements'])==4
  assert abs(sum(p['score'] for p in r['placements']))<1e-9
  for rd in r['rounds']:
   for row in rd['ledger']:
    ledgers+=1;assert row['base_income']==base_income(rd['round'])
    assert row['income']==row['base_income']+row['carry']+row['bonus']
    assert row['income']-sum(a['cost'] for a in row['actions'])==row['remaining']
    assert row['bank']==min(2,row['remaining']) and len(row['deck'])>=8
    assert not {a['name'] for a in row['actions'] if a['kind']=='buy'}&START_ONLY
   for b in rd['battles']:
    battles+=1;assert b['combat_rule']=='strict_pre_position_v2' and not b['sequence_skips']
  if c['segment']=='final-holdout':final.append(r)
 assert sorted(seeds)==list(range(inp['seeds'][0],inp['seeds'][1]+1)) and len(set(seeds))==1500
 for e in ELEMENTS:
  assert totals[e]==300 and set(intents[e].values())=={100}
  for seg,n in (('train',90),('validation',30),('final-holdout',30)):
   for mode in ('internal','external'):assert segments[(e,seg,mode)]==n
 assert battles==t['battles'] and len(final)==300
 audit=dict(games=1500,battles=battles,ledgers=ledgers,per_element=dict(totals),segments={str(k):v for k,v in segments.items()},intent_counts=dict(intents),source_hashes_verified=True,stock=693,sequence_skips=0)
 save('run-audit.json',audit)
 # Direct matches exclude ghosts and fights not involving the focal AI.
 direct={};route_rows={};size_rows={};matchups={};privacy=[]
 for e in ELEMENTS:
  rs=[r for r in final if r['comparison']['element']==e];direct[e]={};route_rows[e]={};matchups[e]={}
  for mode in ('internal','external'):
   counts=Counter();cells=[]
   for r in rs:
    if r['comparison']['mode']!=mode:continue
    pid=r['comparison']['first_seats'][0];cell=Counter()
    for rd in r['rounds']:
     for b in rd['battles']:
      if b['ghost']:continue
      seats=[i for i,p in enumerate(b['participants']) if p['pid']==pid]
      if not seats:continue
      i=seats[0];cell['n']+=1;cell['w']+=.5 if b['winner'] is None else b['winner']==i
      oe=b['participants'][1-i]['spec'] or 'unselected';m=matchups[e].setdefault(oe,dict(battles=0,wins=0))
      m['battles']+=1;m['wins']+=.5 if b['winner'] is None else b['winner']==i
    counts.update(cell)
    if cell['n']:cells.append(cell['w']/cell['n'])
   direct[e][mode]=dict(battles=counts['n'],win_rate=counts['w']/max(1,counts['n']),room_interval=interval(cells))
  sizes=defaultdict(Counter);by_intent=defaultdict(Counter)
  for r in rs:
   pid=r['comparison']['first_seats'][0];p=next(p for p in r['placements'] if p['pid']==pid)
   book=by_intent[r['comparison']['route_intent']];book['assigned']+=1;book['adopted']+=p['route']==r['comparison']['route_intent']
   n=len(p['deck']);b=sizes[n];b['players']+=1;b['score']+=p['score'];b['champions']+=p['rank']==1
  size_rows[e]=dict(sorted(sizes.items()));route_rows[e]=dict(by_intent)
  stats=load(f'{e}-final-statistics.json');route_rows[e]['actual']=stats['routes']
  cfg=load(f'{e}-final-policy.json');assert cfg==frozen[e]
  names=[SPECIAL[e]]+[n for n,c in CARDS.items() if c.element in (e,'generic') and not c.ability][:12]
  b=StrictBattle((names,['攻击强化','防御强化','护盾']),seed=19);b.policy_configs=(cfg,cfg)
  s=b.players[0];s.specialization=e;s.energy=3;s.stage=1;s.pile=list(s.instances);s.hand=[s.pile.pop(0) for _ in range(3)];s.known_top=[]
  x=choose_play(b,0);other=deepcopy(b);other.players[0].pile.reverse();y=choose_play(other,0)
  assert (x.uid if x else None)==(y.uid if y else None);privacy.append(dict(element=e,hidden_pile_permutation_unchanged=True))
 save('direct-matches.json',direct);save('route-analysis.json',route_rows);save('size-analysis.json',size_rows);save('matchups.json',matchups);save('final-observation-checks.json',privacy)
 old=(OUT/'report.md').read_text(encoding='utf-8')
 if old.startswith('# v1.2 快速卡牌测试'):
  write('training-distribution.md',[old.replace('本轮没有训练 AI 或改动平衡数值。','此表混合训练、验证和最终模型，不能视为最终模型成绩。')])
 lines=['# 五元素个性化AI：5轮1500局','',f"完成1500局四人赛事、{battles:,}场战斗，失败{t['skipped']}局。每系300局预算，分别保存独立的构筑和战斗权重。72项预检与v1.1冻结校验通过。",'',
  '## 训练方案','',
  '- 使用最新185张/693份卡表及已改风、毒、血统、血潮机制。从outcome-accepted-10出发，为火回收循环、水附魔与治疗、土护盾反伤、风运转加速、毒附魔与生存分别设置可学习的机制参数。未改卡牌或规则。',
  '- 每系5轮，每轮36训练、12验证、12最终预留。共900训练/300验证/300最终测试；每系内战150局、外战150局。所有最终预留局在五轮全部冻结后运行。',
  '- 每房只有1席是本轮被训练/评估的目标AI，另3席为对手，不重复计算房间。内战四席同系；外战目标AI对三种不同的其他元素。训练对手使用每轮开始时冻结的五系模型，更新前全系同时取快照；终测统一使用固定初始风格模型，避免对手变化混淆。',
  '- 三路线意向每系各100局，终测各20局；同系玩家轮转意向。意向只影响合法抓牌评分，不凭空送牌、不绕过路线唯一与共享库存。最终实际采用率可能不均。',
  '- 夺冠率、战斗胜率、(赛事均分+3)/6等权。构筑/战斗参数每轮扰动上限10%/7%，累计相对初始限制0.65—1.5倍。训练相关性估计仅使用该系目标AI，验证结果不用于梯度。',
  '- 大卡组探索奖金按0/1.5/3/4.5/6递增，鼓励抓取有一定质量的牌并减少删牌，不强制购买。火/风的软引导上沿14，水16，土/毒18；不是合法上限。训练评分另给最多0.02的大小探索奖励，验证、终测均为纯胜负目标。',
  '- 接受：训练综合差加探索奖励非负，验证综合差≥0.005，内/外战各自综合差≥−0.03，验证三分项均≥−0.08。失败保留上一模型。12局验证噪声大，因此必须另看封存成绩；终测不重调或重选模型。','',
  '## 最终冻结测试','', '| 元素 | 接受轮次 | 平均/中位张数 | 内战胜率/夺冠率 | 外战胜率/夺冠率 | 内战综合差95%区间(pp) | 外战综合差95%区间(pp) |','|---|---|---:|---:|---:|---:|---:|']
 for e in ELEMENTS:
  ev=t['evaluation'][e];d=ev['overall']['decks'];a,b=(ev['modes'][m] for m in ('internal','external'))
  lines.append(f"| {LABEL[e]} | {t['accepted'][e]} | {num(d['mean_size'])}/{d['median']} | {pct(a['selected']['win_rate'])}/{pct(a['selected']['championship_rate'])} | {pct(b['selected']['win_rate'])}/{pct(b['selected']['championship_rate'])} | {ci(a['objective']['composite'])} | {ci(b['objective']['composite'])} |")
 unchanged=[LABEL[e] for e in ELEMENTS if not t['accepted'][e]]
 if unchanged:lines+=['','**'+ '、'.join(unchanged)+'系没有任何候选通过验证，最终保留风格初始化参数。** 已执行五轮训练尝试，但不能称这些元素训练后优于起点；大小和机制探索样本保留，未因用户期待而强行采用落败模型。', '', '因此这些系的最终内战目标AI与其对手使用相同参数，只是座位、抓牌意向和随机风格不同；内战胜率偏离50%不能解读为训练进步。']
 lines+=['','每个内/外战终测只有30个目标AI人次；区间按赛事聚类、房间等权。综合差是目标AI与同房3席对手平均成绩之差；内战主要反映对初始同系风格的改良，外战也受元素克制影响，不能把外战强弱全部归因于训练。非同房配对seed的消融比较，未将同一赛事中的多场战斗视为独立统计样本。','',
  '| 元素 | 内战真实直接胜率 | 外战真实直接胜率 | 总体均分 | 总体得分率 |','|---|---:|---:|---:|---:|']
 for e in ELEMENTS:
  v=t['evaluation'][e]['overall']['selected'];lines.append(f"| {LABEL[e]} | {pct(direct[e]['internal']['win_rate'])} | {pct(direct[e]['external']['win_rate'])} | {num(v['mean_score'])} | {pct(v['mean_score']/3)} |")
 lines+=['','直接交手剔除幽灵及不涉及目标AI的战斗；上表整体胜率包含目标玩家对幽灵的战斗。对手采用同一初始模型并不意味着最终AI必然超过它，需看内战区间是否支持提升。','',
  '## 大小探索：实际达到的大小','', '| 元素 | 轮次 | 探索奖金 | 训练平均张数 | 验证综合差(pp) | 接受 |','|---|---:|---:|---:|---:|---|']
 for e in ELEMENTS:
  for b in t['batches'][e]:lines.append(f"| {LABEL[e]} | {b['round']} | {b['size_bonus']} | {num(b['candidate_decks']['mean_size'])} | {b['validation']['composite']['mean']*100:+.1f} | {'是' if b['accepted'] else '否'} |")
 lines+=['','这些轮次同时改变机制权重且对手会更新，不能将分数变化全部解释为张数的因果影响。这里找到的是本次候选和参数范围内通过验证的方案，不是严格证明的全局最优张数。若实际大小没有覆盖预期范围，结论只能是探索不足，不能声称已经比较过所有长度。','',
  '| 元素 | 最终大小分布（张数:人数） |','|---|---|']
 for e in ELEMENTS:lines.append(f"| {LABEL[e]} | {dict(t['evaluation'][e]['overall']['decks']['histogram'])} |")
 lines+=['','以最终保留方案的中间50%张数作为下一轮优先复核区间；它反映常用大小，不是随机指定张数后的因果最优解。','',
  '| 元素 | 本轮保留方案 | 中间50%张数 | 每战出牌 | 每战即时抽牌 | 终局本系首次层均值 |','|---|---|---|---:|---:|---:|']
 for e in ELEMENTS:
  ev=t['evaluation'][e]['overall'];d=ev['decks'];sizes=[]
  for n,count in d['histogram'].items():sizes.extend([int(n)]*count)
  sizes.sort();q1=sizes[len(sizes)//4];q3=sizes[len(sizes)*3//4];v=ev['selected']
  lines.append(f"| {LABEL[e]} | {frozen[e]['checkpoint']} | {q1}—{q3} | {num(v['plays_per_battle'])} | {num(v['instant_draw_per_battle'])} | {num(d['main_first_layers'])} |")
 lines+=['','## 路线均衡与异常','', '| 元素 | 路线 | 意向人次/实际兑现 | 最终路线人次 | 战斗胜率 | 夺冠率 | 均分 |','|---|---|---:|---:|---:|---:|---:|']
 warnings=[]
 for e in ELEMENTS:
  actual=route_rows[e]['actual']
  for route in ROUTES[e]:
   m=actual[route];intent=route_rows[e].get(route,{})
   lines.append(f"| {LABEL[e]} | {route} | {intent.get('assigned',0)}/{intent.get('adopted',0)} | {m['players']} | {pct(m['win_rate'])} | {pct(m['championship_rate'])} | {num(m['mean_score'])} |")
   if m['players']<10:warnings.append(f"{route}：终局仅{m['players']}人，路线采用不足，不能可靠判断强弱。")
   elif m['championship_rate']>=.5 or m['championship_rate']<=.1:warnings.append(f"{route}：{m['players']}人，夺冠{pct(m['championship_rate'])}、战斗胜率{pct(m['win_rate'])}，需关注{'过强' if m['championship_rate']>=.5 else '过弱'}信号；仍可能受内外战和对手分布影响。")
 lines+=['','路线战斗按当时持有路线统计，终局人次和夺冠按结束时路线统计；更换路线会使两者分母不同。路线意向是均衡实验分配，实际采用由展示、竞争、支付与AI选择共同决定。']
 lines+=['']+['- '+w for w in warnings]
 route_modes={}
 lines+=['','路线内外战另行拆分如下；每条路线每种模式的人次更少，不能把零夺冠直接判为卡牌无效。','',
  '| 元素 | 模式 | 路线 | 终局人次 | 战斗胜率 | 夺冠率 | 均分 |','|---|---|---|---:|---:|---:|---:|']
 for e in ELEMENTS:
  route_modes[e]={}
  for mode in ('internal','external'):
   ss=selected_statistics([r for r in final if r['comparison']['element']==e and r['comparison']['mode']==mode])['routes']
   route_modes[e][mode]={route:ss[route] for route in ROUTES[e]}
   for route in ROUTES[e]:
    m=ss[route];lines.append(f"| {LABEL[e]} | {mode} | {route} | {m['players']} | {pct(m['win_rate'])} | {pct(m['championship_rate'])} | {num(m['mean_score'])} |")
 save('route-modes.json',route_modes)
 lines+=['','## 分阶段与克制','', '| 元素 | 模式 | 阶段 | 目标/对手胜率 |','|---|---|---|---:|']
 for e in ELEMENTS:
  for mode,v in t['evaluation'][e]['modes'].items():
   for stage,s in v['stages'].items():lines.append(f"| {LABEL[e]} | {mode} | {stage} | {pct(s['selected']['win_rate'])}/{pct(s['control']['win_rate'])} |")
 lines+=['','后期只包括存活者，不能将其胜率视为从开局无条件取得的胜率。实际对各元素直接交手见matchups.json。','',
  '## 复核与保留问题','',f'1500唯一种子、{ledgers:,}条构筑账本、693库存、收入/付费/继承/初始牌规则和零失效跳过复核通过；输入与起点哈希复核通过，最终五模型隐藏摸牌堆逆序不改变未揭示选择。', '',
  '| 问题 | 处理与限制 |','|---|---|',f"| 运行失败 | {t['skipped']}，见issues.json；不补造胜者 |",'| 路线不可能保证四人都拿到预定路线 | 均衡意向并报告实际兑现率，未改路线库存 |',
  '| 每种模式终测30局 | 样本有限，不宣布所有模型或路线均已最优 |','| 张数与机制同步学习 | 最优长度仅为候选探索范围内结论，大小关联不当作因果 |',
  '| 外战接受门槛受元素强弱影响 | 外战综合差比较同房不同系；弱系可能更难通过，不能把未接受解释为没有进步。严格分离需追加同元素新旧模型对同一外敌的镜像对照，本轮不追加或超预算 |',
  '| 训练评价和玩法范围 | 完整四人赛事，参数化启发式训练，不是穷举或神经网络训练 |',
  '| 模型发布 | 五个独立*-final-policy.json可复用，默认fixed-legacy不替换；新意向与大小字段缺省不影响旧模型 |','',
  '完整185张卡携带/曾携带/使用率见[最终卡牌统计](final-cards.md)。历史训练分布另存training-distribution.md，不代表最终五模型独立战绩。']
 write('report.md',lines)
 cards=['# 五系最终AI逐卡统计','', '仅最终300局中对应元素AI，每系60目标玩家；同系卡以该系60人次为携带率分母。通用牌按五系分别展示。参战使用率按携带该牌战斗至少实际打出一次计。','',
  '| AI | 卡牌 | 品质 | 终局携带 | 曾携带 | 持有者胜率 | 持有者夺冠 | 持有者得分率 | 参战使用率 | 每携带战斗施放次数 |','|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
 for e in ELEMENTS:
  for c in load(f'{e}-final-statistics.json')['cards']:
   if c['element'] not in (e,'generic'):continue
   cards.append(f"| {LABEL[e]} | {c['name']} | {c['rarity']} | {pct(c['carry_rate'])} | {pct(c['ever_carry_rate'])} | {pct(c['win_rate'])} | {pct(c['championship_rate'])} | {pct(c['score_rate'])} | {pct(c['usage_rate'])} | {num(c['casts_per_carried_battle'])} |")
 write('final-cards.md',cards)
 save('route-warnings.json',warnings)
 print(json.dumps(dict(audit=audit,accepted=t['accepted'],evaluation={e:dict(size=t['evaluation'][e]['overall']['decks']['mean_size'],internal=t['evaluation'][e]['modes']['internal']['selected'],external=t['evaluation'][e]['modes']['external']['selected']) for e in ELEMENTS},warnings=warnings),ensure_ascii=False))

if __name__=='__main__':main()
