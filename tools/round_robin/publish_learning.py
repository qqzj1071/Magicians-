"""Publish measured v1.0 AI knowledge without modifying the frozen card release."""
from pathlib import Path
from collections import Counter
from dataclasses import asdict
import copy,gzip,hashlib,json,statistics
from learning_core import *
AI=ROOT/'docs/ai'
LABELS=dict(core_priority='启动核心优先',startup_resource='启动资源',operation_layer='首次叠层',finish_ratio='进入斩杀投影的阈值',finish_burst='斩杀阶段伤害偏好',panic='危险时生存偏好',penetration_value='防御穿透偏好',tempo_value='缩短间隔偏好',sustain_value='有效治疗偏好',shield_engine='盾资源偏好',epic_cycle='史诗回收偏好',budget_fit='本池费用衔接',cost_power='费用折算',damage='伤害收益',health='生命收益',shield='护盾收益',defense='永久防御收益',draw='下抽牌资源',energy='下抽费用资源',search='检索收益',counterplay_value='应对窗口收益',combo='本池两步衔接',cleanse='净化净收益',reserve='为已在手核心保留费用',horizon='估值行动值窗口',lethal_candidates='精确投影候选数')
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def load_gz(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def recommendations(own,enemy):
 e=C.DECKS[enemy]['element'];r=C.DECKS[own]['route'];text=[]
 if e=='earth':text+=['优先比较穿盾减少反伤的收益与防穿减少扣防的收益；两种穿透不可混为一谈。破障法阵只强化下一发主弹，普通副弹仍独立减防。','面对大盾，过量主弹增伤可能触发碎盾反击；用实际穿盾生命伤害和完整反应投影判断是否能活着斩杀。']
 if e=='water':text+=['减治疗需覆盖对方实际吸血或治疗窗口；在抽牌前已到期的抑制不能计入随后收益。若对方能回复，分散的小伤害不等于有效压血。','比较集中主弹爆发、护盾吸血抑制与继续成长的净收益；满血空回不产生潮汐，避免为了记录潮汐机械抢打治疗。']
 if e=='poison':text+=['先让主弹触及生命的能力、挂毒后的每百行动值毒伤和减攻防都应进入生存投影；只堆生命不处理减益可能继续恶化。','净化能减毒伤和动态减益，但敌方毒爆会从实际减毒获得永久攻击；以完整事务后状态估值，不能只把减层当成单向收益。']
 if e=='fire':text+=['首发前费用分配同时比较防爆发与核心落地；防御/护盾必须在伤害前获得，下一抽才给的资源无法救当前致死。','余烬只强化一发主弹，读取实际火层与消耗层数；不能用旧版火层或余烬系数估算斩杀线。']
 if e=='wind':text+=['高风层下纯堆护盾的边际价值降低；优先比较有效生命、净化风痕、缩短自身节奏与提前斩杀。','天岚第三次真伤与风痕引爆是同发之后的独立事件，完整发射组末才判死；不能因主弹先致死忽略对方副弹。']
 if r=='灰烬循环':text+=['回火和灰烬账本检查本场计数及未兑换消耗；额外资源有上限，不能把重复洗牌都估成无限余烬。']
 if C.DECKS[own]['element']=='water':text+=['按实际缺血、吸血基数和潮汐记录一起排序；静水只给下一发主弹盾伤吸血，不能复制到所有副弹。']
 if r=='大地之握':text+=['只把普通叠盾实际衰减损失计入转伤，主动耗盾、敌方削盾不计。免衰减盾保生存，但没有本次衰减转伤。']
 return text
def policy_changes(ctx,own,enemy):
 base=base_policy(ctx,own,enemy);actual=policy(ctx,own,enemy);items=[]
 for k,label in LABELS.items():
  v=getattr(actual,k);b=getattr(base,k)
  if v!=b:items.append((abs(v-b)/max(1,abs(b)),f'{label}：{b:g} → {v:g}'))
 return [x[1] for x in sorted(items,reverse=True)[:6]]
def phase_text(m):
 counts=m['phases'];total=max(1,sum(counts.values()))
 return '、'.join(f'{label}{counts.get(k,0)/total:.1%}' for k,label in [('startup','启动'),('operation','运转'),('finish','斩杀')])
def hard_history(a,b):
 entries=[]
 for folder in sorted(OUT.glob('round_*')):
  path=folder/'hard-matchup-learning'/(a+'__'+b+'.json.gz')
  if not path.exists():continue
  d=load_gz(path)
  for role,valid in enumerate(d['validation']):
   own=a if role==0 else b
   gain=score(valid[1],role)-score(valid[0],role)
   entries.append(dict(round=int(folder.name[-2:]),own=own,gain=gain,accepted=d['accepted'][role]))
 return entries
def factorial_lifts():
 per_route=[]
 for path in sorted((OUT/'round_99/factorial-final').glob('*.json.gz')):
  r=load_gz(path);arms={}
  for d in (False,True):
   for p in (False,True):arms[d,p]=score([row for arm in r['arms'] if arm['deck_changed']==d and arm['ai_changed']==p for row in arm['rows']])
  per_route.append(dict(ai=arms[True,True]-arms[True,False],deck=arms[True,False]-arms[False,False],combined=arms[True,True]-arms[False,False]))
 rng=random.Random(44991237);result={}
 for key in ('ai','deck','combined'):
  values=[x[key] for x in per_route];boot=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(2000))
  result[key]=dict(mean=statistics.mean(values),cluster_bootstrap_ci95=[boot[49],boot[1949]],clusters=len(values))
 save(OUT/'factorial-lifts.json',result);return result

def publish():
 assert read(OUT/'completion.json')['completed']
 completion=read(OUT/'completion.json');ctx=read(OUT/'selected-context.json');install(ctx);final=read(OUT/'final-summary.json');baseline=read(OUT/'round_00/summary.json');progress=read(OUT/'progress.json')
 hierarchy=read(OUT/'hierarchy-summary.json');draft=read(OUT/'draft-final-summary.json');audit=read(OUT/'trace-audit.json');factorial=read(OUT/'factorial-summary.json');model=read(AI/'construction-model.json');lifts=factorial_lifts();styles=read(OUT/'style-summary.json')
 assert sha(C.CARD_LIBRARY_PATH)==completion['card_sha256']
 # Reference lists and the published v1.0 zip are unchanged. Research lists have a separate pointer.
 decks=[]
 for a,d in ctx['decks'].items():
  d=copy.deepcopy(d);d['metrics']=deck_metrics(d);assert legal(d);decks.append(d)
 trained=ROOT/'decks/trained-v1.0.json'
 save(trained,dict(version='1.0',rule_version='1.0',card_library='../releases/v1.0/cards.json',status='learned_fixed_lists',selected_round=completion['selected'],decks=decks))
 save(ROOT/'decks/active.json',dict(library='trained-v1.0.json',card_version='1.0',experiment='research/ai-v1.0-learning'))
 reg=dict(schema_version=3,rule_version='1.0',planner_version=P.PLANNER_VERSION,source_experiment='ai-v1.0-learning',fixed_deck_across_opponents=True,deck_library_sha256=sha(trained),card_library_sha256=sha(C.CARD_LIBRARY_PATH),engine_sha256=sha(Path(E.__file__)),planner_sha256=sha(Path(P.__file__)),
  common=ctx['common'],routes=ctx['routes'],validation_scope='all 120 pairings on independent final seeds, 200 games each',matchups={})
 diagnostics={};index=['# 战斗AI与构筑AI · 卡牌v1.0','', '[总报告](training-v1/report.md) · [共性战斗逻辑](training-v1/common.md) · [构筑方法](training-v1/construction.md) · [120组对战索引](training-v1/matchups.md)','', '卡牌数据未修改；实际采用的固定牌表见[训练牌组](../../decks/trained-v1.0.json)。参数按共性→路线→具体对手分层，运行器默认读取该训练版列表。历史15套封版参考列表仍独立保留。','', '严格胜率中同时击败不计胜；训练评分中同时击败计0.5，两个口径不混用。最终测试只用于报告，不用来继续选牌或调参。仍严重克制的组合保留失败记录，不宣称全部破解。']
 pair_index=['# 120组实战档案','', '15×14/2异路线与15镜像。每组最终200场；左右座位各100场。个性策略只能变更出牌，不能按对手换牌。','', '|路线组合|左／右胜率|同时击败|','|---|---:|---:|']
 pair_results=[]
 for path in sorted((OUT/'round_99/final').glob('*.json.gz')):
  r=load_gz(path);a,b=r['a'],r['b'];rows=r['rows'];assert len(rows)==200
  assert all(p==asdict(policy(ctx,own,enemy)) for p,(own,enemy) in zip(r['policies'],((a,b),(b,a))))
  wins=Counter(x['winner'] for x in rows);key='|'.join(sorted((a,b)));file=a+'__'+b+'.md'
  reg['matchups'][key]=dict(policies={a:r['policies'][0],b:r['policies'][1]},current_validation=True,status='independent_final_test',evaluation_simulations=200,file='docs/ai/training-v1/matchups/'+file)
  lines=[f'# {C.DECKS[a]["route"]} ↔ {C.DECKS[b]["route"]}','', f'卡牌v1.0；采用第{completion["selected"]}轮冻结构筑与策略。最终独立200场：左胜{wins[0]}、右胜{wins[1]}、同时击败{wins[-1]}。该最终结果没有反过来用于调参。','']
  for role,(own,enemy) in enumerate(((a,b),(b,a))):
   m=metrics(rows,role);lo,hi=wilson(wins[role],len(rows));changes=policy_changes(ctx,own,enemy)
   diagnostics[own+'|'+enemy]=dict(**m,ci95=[lo,hi],policy=r['policies'][role],raw_result=str(path.relative_to(ROOT)))
   lines += [f'## {C.DECKS[own]["route"]} 对 {C.DECKS[enemy]["route"]}','',f'严格胜率{m["win_rate"]:.1%}，95%区间{lo:.1%}—{hi:.1%}；双核心完成率{m["core_completion"]:.1%}，完成者行动值中位数{m["core_time_median"]}；记录到的未用费用比例{m["unused_energy"]:.1%}（末个致死阶段可能截断）。计划出牌阶段分布：{phase_text(m)}；包括因事务提前结束而未执行的队列项。','']
   lines+=['- '+t for t in recommendations(own,enemy)]
   lines+=['','专项参数相对当前共性/路线先验的变化（评分权重，不是卡牌数值）：','']+(['- '+x for x in changes] if changes else ['- 本组合采用收缩后的共性/路线策略，没有保留独立偏移。'])
   phaseplays=m['plays'];top=sorted(phaseplays,key=phaseplays.get,reverse=True)[:6]
   lines+=['','本组实测执行高频牌：'+ '、'.join(f'{n}（{phaseplays[n]}次）' for n in top)+'。频率受到抽取、费用和存活时长影响，不代表因果强度排序。',f'计划队列中的斩杀条件投影标记累计{m["conditional_lethal_flags"]}次，部分计划可能未执行；投影假设双方不再出新牌，因此不是无条件保证，也不以最终获胜率冒充逐次预测准确率。','']
   if m['win_rate']<.2:lines+=['该方向仍未破解：当前牌组和有限搜索下低于20%。保留全部失败候选；下一步应增加候选与对手策略覆盖，不自动削弱或增强卡牌。','']
   if a==b:break
  h=hard_history(a,b)
  if h:
   lines+=['## 六轮专项探索记录','','下表是独立局部验证的得分差，单次仅12场，有抽样噪声；未采用轮次不构成当前策略。最终部署仍固定使用选中的整轮检查点。','','|轮次|方向|候选验证得分差|是否接受|','|---|---|---:|---|']
   lines += [f'|{x["round"]}|{C.DECKS[x["own"]]["route"]}|{x["gain"]:+.1%}|{"是" if x["accepted"] else "否"}|' for x in h]
  write(AI/'training-v1/matchups'/file,'\n'.join(lines)+'\n')
  pair_index.append(f'|[{C.DECKS[a]["route"]} ↔ {C.DECKS[b]["route"]}](matchups/{file})|{wins[0]/200:.1%}／{wins[1]/200:.1%}|{wins[-1]}|')
  pair_results.append(r)
 save(ROOT/'tools/round_robin/policies.json',reg);save(AI/'training-v1/diagnostics.json',diagnostics);write(AI/'training-v1/matchups.md','\n'.join(pair_index)+'\n');write(AI/'README.md','\n'.join(index)+'\n')
 common=['# 共性战斗逻辑与学习范围','', '卡牌和执行器规则始终为v1.0。三阶段是连续状态上的决策倾向，不是固定张数的脚本：','', '- 启动：未同时激活专精与路线时，提高核心、检索和下抽资源的边际价值；若当前生命不足以承受下一发，仍要比较立即防御和治疗。','- 运转：双核心齐备后，提高首次元素叠层、永久成长、有效治疗/叠盾和费用衔接的价值；重复牌不再加首次层，但仍计入其他收益。','- 斩杀：快速伤害估值达到对方有效生命的比例阈值后，进入精确条件投影；在完整主弹、副弹、引爆、反伤、毒和复活事务后判定，并且逐牌重算。','- 投影不读取未来牌序，不假设敌方下一抽停止出牌；跨抽牌边界的预测明确为“没有后续新牌”的条件结论。','- 可学习的共性参数由跨元素代表对局训练，再在不同对局和不同种子验证；路线偏好在14异路线验证；严重克制组合额外训练并向路线先验收缩，避免小样本极端权重。','- 本池两步衔接、净化净收益、核心费用保留和精确投影候选数提供新的候选维度；零默认值保留封版参考出牌器行为。某个维度是否有用取决于验证结果，不因代码存在就宣称提升。','', '|共性参数|采用值|','|---|---:|']
 common += [f'|{LABELS[k]}|{v}|' for k,v in ctx['common'].items()]
 common += ['','阶段判定先检查斩杀投影触发条件，因此有合法斩杀机会时可以在双核心齐备前进入收尾；提高核心优先级不等于必须先专精再传奇。未打专精仍严格禁止预存余烬、潮汐或风痕专属效果。']
 common+=['', '不可学习的固定规则包括完整事务末判死、余烬/风痕激活门槛、伤害乘区和抽牌时序。本轮不改变它们。风险触发阈值等部分决策结构仍是人工启发式，不能声称所有逻辑都由数据学出。','', '本轮层级消融（预先固定每第四个非镜像组合；同种子与同一对手，样本只作诊断）：','', '|自身策略层级|场数|训练评分口径|','|---|---:|---:|']
 common.insert(common.index('本轮层级消融（预先固定每第四个非镜像组合；同种子与同一对手，样本只作诊断）：'),'起手调度仍沿用执行器保留能力牌的固定规则，本轮未训练调度或完整局内构筑轮序。')
 common += [f'|{k}|{v["n"]}|{v["score"]:.2%}|' for k,v in hierarchy['arms'].items()]
 common+=['', '各层级效果来自该有限固定样本；个性化不保证每组必然胜过共性策略。最终联赛、消融和构筑测试均在冻结选版后运行，不再反向改参数。']
 write(AI/'training-v1/common.md','\n'.join(common)+'\n')
 construction=['# 构筑AI：抓牌、换牌和删牌','', '本轮学习对象是给定牌组和候选时的边际选择，不替代尚未确定的完整局内构筑规则。训练环境允许18—26张单主系+通用卡，保持1专精、1路线传奇和2张其他传奇；资源覆盖和费用曲线受约束，史诗/稀有/普通数量不再照搬旧固定配额。该约束属于可复现实验环境。','', '每轮提出定向换牌、探索换牌、删牌、加牌和传奇替换；训练含各元素与最差对手，验证覆盖14条异路线并混入历史对手。目标兼顾平均得分与最差四分位，而非只对一个敌人组牌；所有对手始终面对同一固定牌组。','', '抓牌评分结合费用、固定面板效率、本系首次层、路线支持、过牌/检索/洗牌缺口、穿透、净化、治疗、护盾、节奏与减治疗。卡牌经验按样本数收缩；线性修正采用岭回归，并留出整个元素交叉验证。若留出误差不优于零修正，则禁用该回归层，保留规则先验和收缩后的卡牌经验。','',f'实际训练样本{model["training_records"]}条；回归层{"启用" if model["ridge_enabled"] else "未启用（留出验证不足）"}。这些是完整牌组增删换的验证收益，存在上下文和候选选择偏差，不能解释成卡牌固有强度。','', '最终独立候选池测试：每路线3次、每次逐步从当前核心开始选牌；候选池种子在模型冻结后使用。该过程是抓牌训练课程，不冒充正式游戏轮序。','', '|方法|生成牌组|合法牌组|对战数|合法牌组对战得分|','|---|---:|---:|---:|---:|']
 construction += [f'|{k}|{v["decks"]}|{v["legal_decks"]}|{v["games"]}|{v["score"]:.2%}|' for k,v in draft.items()]
 if 'prior' in draft:
  delta=draft['learned']['score']-draft['prior']['score']
  construction+=['',f'学习排序相对纯启发式的点估计差为{delta:+.2%}。本次没有验证出逐张抓牌学习层优于纯先验；完整牌组改善主要来自候选构筑的全对手仿真筛选。抓牌模型保留为实验性工具，未来需要新候选池和新种子验证，不能把优于随机选择当作学习层有效的证据。']
 construction+=['', '不合法牌组未参加对战；因此“合法牌组对战得分”不能单独用于公平比较两种方法，须同时看合法率。random是随机选择，不代表有经验的人类牌手；prior使用完全相同的费用、资源和协同先验，但禁用训练得到的卡牌奖励及回归修正，用来区分学习收益与人工启发式收益。prior对照只作归因，没有用于重新选择模型。','', '可调用接口：tools/round_robin/draft_learning.py中的choose_offer(deck, offer, model)，输出候选排序与传奇替换建议；模型为docs/ai/construction-model.json。未来增加完整构筑流程后，必须用相同接口重新验证前期抓牌、删除、候选过滤与刷新决策。']
 write(AI/'training-v1/construction.md','\n'.join(construction)+'\n')
 for a,d in ctx['decks'].items():
  m=deck_metrics(d);lines=[f'# {d["route"]} · 学习后固定构筑','',f'采用第{completion["selected"]}轮。共{m["size"]}张，均费{m["average_cost"]:.2f}；资源覆盖{m["resources"]}。此套应对所有路线，不按配对换牌。','', '|卡牌|费|类型|','|---|---:|---|']
  lines += [f'|{e["name"]}|{C.CARDS[e["name"]].cost}|{C.CARDS[e["name"]].rarity}|' for e in d['entries']]
  lines+=['','本轮构筑路径（后续未采用轮次也列出，避免混淆最终构筑）：','']
  for h in progress['history']:
   move=next(x for x in h['deck_moves'] if x['a']==a)
   lines.append(f'- 第{h["round"]}轮：'+('接受' if move['accepted'] else '保留')+f'；候选{move["move"]}；独立验证得分差{move["gain"]:+.1%}。')
  write(ROOT/f'decks/learned-v1/{a}.md','\n'.join(lines)+'\n')
 ranking=['# 最终独立胜率与克制情况','', '120组×200场，包含15镜像；总体每路线对14个不同对手各200场，分母2800，不含镜像。同时击败计入分母但不计胜。区间是二项近似，不能消除牌组与对手策略覆盖的局限。','', '|路线|胜率|95%区间|最难对手及胜率|','|---|---:|---|---|']
 for row in final['ranking']:
  a=row['deck'];b=min((b for b in IDS if b!=a),key=lambda b:final['matrix'][a][b]['win_rate']);lo,hi=row['ci95']
  ranking.append(f'|{row["route"]}|{row["win_rate"]:.2%}|{lo:.1%}—{hi:.1%}|{ctx["decks"][b]["route"]}：{final["matrix"][a][b]["win_rate"]:.1%}|')
 ranking+=['','## 单边超过80%的组合','', '|优势方|劣势方|优势方胜率|95%区间下界|','|---|---|---:|---:|']
 for x in sorted(final['severe'],key=lambda x:x['rate'],reverse=True):
  a=x['strong'];b=x['b'] if a==x['a'] else x['a'];lo=final['matrix'][a][b]['ci95'][0]
  ranking.append(f'|{ctx["decks"][a]["route"]}|{ctx["decks"][b]["route"]}|{x["rate"]:.1%}|{lo:.1%}|')
 write(AI/'training-v1/win-rates.md','\n'.join(ranking)+'\n')
 old_severe={'|'.join(sorted((x['a'],x['b']))) for x in baseline['severe']};new_severe={'|'.join(sorted((x['a'],x['b']))) for x in final['severe']}
 breakthroughs=['# 严重克制的缓解候选与未解问题','','基线每组40场，最终每组200场；牌组和双方策略都改变。下表是点估计变化，不是单卡或单项策略的因果效应；退出80%不等于已稳定达到30%反制胜率。','','|初步劣势方|对手|初步胜率|最终胜率|最终95%区间|','|---|---|---:|---:|---|']
 for x in baseline['severe']:
  key='|'.join(sorted((x['a'],x['b'])))
  if key in new_severe:continue
  strong=x['strong'];weak=x['b'] if strong==x['a'] else x['a'];v=final['matrix'][weak][strong];lo,hi=v['ci95']
  breakthroughs.append(f'|{ctx["decks"][weak]["route"]}|{ctx["decks"][strong]["route"]}|{baseline["matrix"][weak][strong]["win_rate"]:.1%}|{v["win_rate"]:.1%}|{lo:.1%}—{hi:.1%}|')
 breakthroughs+=['','机制解释与下一步候选：穿云箭可以用更顺畅的核心启动和主弹穿盾/防穿协同压缩敌方治疗窗口；水系面对土系要区分打盾吸血、穿盾和反伤触发；蚀命面对大盾需要先建立有效挂毒与额外毒伤。以上是基于规则和最终构筑的解释，没有做单卡消融，不能声称某张牌单独造成这些变化。','',f'最终仍有{final["severe_count"]}组单边超过80%，其中{len(new_severe-old_severe)}组不在初步基线名单内。它们的失败训练、局部验证与最终数据全部保留，下一轮应对这些方向增加更广候选和对手策略覆盖；本轮不再根据最终结果修改模型。','','[所有严重克制组合](win-rates.md) · [120组专项记录](matchups.md)']
 write(AI/'training-v1/breakthroughs.md','\n'.join(breakthroughs)+'\n')
 report=['# v1.0战斗与构筑AI：六轮学习报告','',f'卡牌253张、费用、攻防和机制参数全程未变，SHA-256：{completion["card_sha256"]}。完成6轮，最终采用第{completion["selected"]}轮验证选出的牌组和策略；最终测试没有参与选版。','', f'训练与评估有效存档{completion["total_simulations"]:,}场，另有层级消融、独立抓牌测试与回放校验。第四轮曾为并行分批恢复，同种子重算不作为新增独立样本。最终联赛120组×200=24,000场，两席各100场，包含15镜像。','', '|轮次|接受构筑变化|接受路线策略|专项学习组数|反馈中>80%组合|固定基线挑战得分|','|---|---:|---:|---:|---:|---:|']
 for h in progress['history']:report.append(f'|{h["round"]}|{h["deck_accepts"]}|{h["route_accepts"]}|{h["hard_pairs_trained"]}|{h["feedback_severe"]}|{h["gauntlet_score"]:.2%}|')
 report+=['', f'新建初步基线每组40场、共{baseline["severe_count"]}组单边超过80%；最终每组200场、共{final["severe_count"]}组。初步24组中有{len(old_severe-new_severe)}组在最终不再超过80%，另有{len(new_severe-old_severe)}组新进入该区间。样本规模、牌组与策略均改变，这个差值不能解释为纯AI因果提升。','', '## 独立拆分检验','', '固定初始牌组和初始出牌先验作为对手，用相同种子交叉比较自身旧/新牌组与旧/新AI；每方向对14个对手各8场。该测试与最终联赛不同，不能替代联赛胜率。','', '|自身构筑/AI|场数|严格胜率|平局计半的得分|','|---|---:|---:|---:|']
 for k,v in factorial.items():report.append(f'|{k}|{v["n"]}|{v["win_rate"]:.2%}|{v["score"]:.2%}|')
 report+=['','配对收益按15条路线聚类重抽样估算区间；只对应固定初始对手池，不代表对所有人类策略的泛化保证：','', '|比较|得分变化|95%路线聚类区间|','|---|---:|---|']
 for key,label in [('deck','只换构筑（旧AI）'),('ai','只换AI（新构筑）'),('combined','构筑与AI同时更新')]:
  v=lifts[key];lo,hi=v['cluster_bootstrap_ci95'];report.append(f'|{label}|{v["mean"]:+.2%}|{lo:+.2%}—{hi:+.2%}|')
 report+=['','## 未参加训练的对手参数组合','','在冻结策略后，用新构造的节奏、续航、应对三套对手参数组合做迁移测试，共3240场；同一牌组分别使用初始先验、当前路线策略和当前个性策略。每格360场、同种子配对。这些结果不用于重新选版。','','|对手倾向|初始先验得分|路线策略得分|个性策略得分|','|---|---:|---:|---:|']
 for label,study in styles['studies'].items():report.append(f'|{label}|{study["initial"]["score"]:.2%}|{study["route"]["score"]:.2%}|{study["personal"]["score"]:.2%}|')
 if 'prior' in draft:report+=['','抓牌层的独立对照：学习排序得分'+f'{draft["learned"]["score"]:.2%}，纯启发式{draft["prior"]["score"]:.2%}。未验证出学习排序层的额外优势，仍应采用先验加仿真验证；不将随机对照的较大差距当作学习贡献。']
 report+=['', '## 防过拟合措施','', '- 共性、路线、具体对局三层策略；个性参数向路线先验收缩，不允许每次失败就堆极端权重。','- 训练、局部验证、跨轮验证、正式测试与抓牌测试使用不同种子命名空间；对候选使用相同种子作配对比较，以减少噪声。','- 每路线固定一套牌，验证覆盖14个异路线；训练混入初始历史对手，减少只适应当前自博弈对手。','- 六轮按预先固定的基线挑战目标选择一次；最终测试、消融与抓牌测试全部在模型冻结后执行，失败不会触发再选版。','- 最终仍有克制和不确定性。有限贪心候选、单主系环境、固定对手池和有限样本均限制泛化；不宣称达到全局最优或已经解决所有克制。','', f'回放检查{audit["replay_passes"]}/120通过，异路线交换座位检查{audit["seat_checks"]}/105通过。已保存所有候选、失败验证、原始对局、种子、构筑快照和代码来源；历史版本压缩包未读取。','', '[完整胜率与严重克制](win-rates.md) · [缓解候选与未解问题](breakthroughs.md) · [共性逻辑](common.md) · [120组个性档案](matchups.md) · [构筑与抓牌](construction.md) · [原始实验](../../../research/ai-v1.0-learning/completion.json)']
 write(AI/'training-v1/report.md','\n'.join(report)+'\n')
 write(ROOT/'decks/README.md','# 牌组入口\n\n[学习后15套固定构筑](trained-v1.0.json)为当前AI运行输入，逐路线说明在learned-v1/；每套应对所有对手，不按配对换牌。\n\n[封版时参考列表](decks.json)保留用于回归，未覆盖；其构筑配额不是正式局内流程。\n\n[本轮构筑学习](../docs/ai/training-v1/construction.md) · [完整结果](../docs/ai/training-v1/report.md)\n')
 # Keep the card release archive immutable; these are live research/documentation pointers.
 p=ROOT/'docs/README.md';s=p.read_text(encoding='utf-8')
 if '最新AI学习：' not in s:s=s.replace('当前唯一有效版本为', '> 最新AI学习：[六轮报告](ai/training-v1/report.md)、[共性逻辑](ai/training-v1/common.md)、[构筑与抓牌](ai/training-v1/construction.md)。卡牌v1.0不变。\n\n当前唯一有效版本为',1)
 write(p,s)
 save(OUT/'publication.json',dict(card_sha256=sha(C.CARD_LIBRARY_PATH),active_library=str(trained.relative_to(ROOT)),matchups=120,diagnostic_directions=len(diagnostics),selected_round=completion['selected'],severe_final=final['severe_count'],old_severe_no_longer_severe=len(old_severe-new_severe)))
 print(json.dumps(read(OUT/'publication.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':publish()
