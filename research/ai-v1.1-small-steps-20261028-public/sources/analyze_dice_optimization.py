"""Room-clustered final analysis; never feeds final results back into selection."""
import argparse
import gzip
import json
import random
import statistics as st
import shutil
from collections import Counter,defaultdict
import cards as C
from shared_draft_pool import copies


def interval(values, seed=180):
    rng=random.Random(seed);n=len(values)
    estimates=sorted(st.mean(rng.choices(values,k=n)) for _ in range(5000))
    return dict(mean=st.mean(values),low=estimates[125],high=estimates[4874],rooms=n)


def publish(out,s,a,cfg):
    from shared_draft_pool import assert_uniform_counts
    assert_uniform_counts(cfg) # Historical nonuniform v3 results may be read, never republished.
    docs=C.ROOT/'docs/deckbuilding';p=lambda v:f'{v:.1%}'
    candidate=dict(cfg,status='growth_v3_research_candidate_three_phase_validation',
                   selected_experiment='research/'+out.name,
                   unresolved_policy='Research candidate, not tournament balance certification. Online learning showed no independent final benefit; see simulation-v3-report.md.')
    (docs/'construction-probabilities.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    r=s['final_selected'];lines=[
        '# growth-v3：三轮构筑、学习与供给微调报告','',
        '日期：2026-10-23。使用冻结v1.0与现有15套参考，不修改卡牌效果、标准套牌、传奇份数或稀有度基础概率。', '',
        '多数玩家在第6轮以前专精，并在12—14轮达到实际路线Dice≥80%的目标；主系平均完整度达到92.4%。供给调整有效，但本次在线学习没有证明额外收益，且对完整标准套牌仍明显处于劣势。所选参数保留为研究候选。','',
        '## 规则与评估口径','',
        '- 第1—3轮首张普通免费；第4—6轮首张普通或稀有免费，两类与两面共用一次资格。',
        '- 第1—3轮禁删；第4—6轮每轮最多删1张且免费；第7轮起最多2张，第一次免费、第二次1点。研习点、继承及刷新不变。',
        '- 8/10/12轮首面前三位传奇、尽量两路线；刷新在最低稀有度启用位置补1传奇。第14轮没有新增保底。',
        '- Dice=2×重合卡张数/(实际张数+标准张数)，按卡张数的多重集合计算。以实际持有传奇路线对应套牌评估，无路线记0，不用最近套牌代替；主系完整度为该标准套牌主系卡名的覆盖率（包括专精、路线等主系卡）。',
        '- Dice80%对应Jaccard66.7%；本轮不能与前两版Jaccard80%的目标直接等同。第14轮Jaccard均值为'+p(a['jaccard14']['mean'])+'、达到Jaccard80%的玩家为'+p(a['jaccard14']['hit'])+'。','',
        '## 三轮验证与采纳','',
        '每阶段12组训练、8组独立验证；每组4人14轮，每轮两场，双方均更新策略权重后进入下一轮。第一阶段保持原池，第二、三阶段提出小幅供给调整；未通过同阶段对照的候选回退，训练记录保留。环境份数在阶段间调整，策略权重在每场双方战后调整。','',
        '|阶段|训练后第5轮前专精|训练后D14均值|训练后D14≥80%|供给/学习目标增量|采纳|',
        '|---|---:|---:|---:|---:|---|']
    for h in s['history']:
        x=h['after'];lines.append(f"|{h['phase']}|{p(x['spec_by5'])}|{p(x['dice14_mean'])}|{p(x['dice14_ge80'])}|{h['config_delta_objective']:+.4f} / {h['learning_delta_objective']:+.4f}|{'是' if h['accepted'] else '否'}|")
    lines+=['','增量是加权综合验证目标变化，不是胜率或Dice百分点；第一阶段供给不变。前两轮未通过，因此第三轮从原始供给与初始权重出发，最终每张非传奇实际只增加或减少1份，未累计到±2份。','',
        '## 最终独立测试','',
        '验证结束后冻结所选配置，使用15组新种子（60位玩家）。最终测试不参与选择，未根据结果回选参数。','',
        '|时点|实际路线Dice均值|Dice≥80%的玩家|主系完整度均值|Dice与主系均≥80%|平均张数|',
        '|---|---:|---:|---:|---:|---:|']
    for n in [12,13,14]:lines.append(f"|第{n}轮|{p(r[f'dice{n}_mean'])}|{p(r[f'dice{n}_ge80'])}|{p(r[f'main_recall{n}_mean'])}|{p(r[f'joint{n}_ge80'])}|{r[f'mean_size{n}']:.2f}|")
    lines+=['',f"第5轮结束前专精{p(r['spec_by5'])}（53/60），第6轮结束{p(r['spec_by6'])}（59/60）。第14轮55/60位达到Dice80%，50/60位同时达到主系完整度80%；主系卡全部到齐的玩家为{p(a['main_fully_complete'])}。仍有1人未获得路线，计0分。",'',
        f"第14轮平均费用{r['average_cost']:.2f}；过牌/检索/洗牌平均{r['resource_means']['draw']:.2f}/{r['resource_means']['search']:.2f}/{r['resource_means']['shuffle']:.2f}张。平均删牌{r['mean_deletes']:.2f}次，其中付费消耗{r['mean_delete_points']:.2f}点；免费购牌平均{r['mean_free_purchases']:.2f}张。平均牌组17.95张，比参考20.6张仍偏薄，说明以Dice优化的AI倾向继续删去非目标卡。",'',
        '## 供给与学习分别带来了什么','',
        '|独立测试方案|D14均值|D14≥80%|主系完整度|',
        '|---|---:|---:|---:|']
    for key,label in [('final_selected','所选供给＋所选学习权重'),('final_baseline_pool','原供给＋相同学习权重'),('final_prior','所选供给＋初始Dice策略权重')]:
        x=s[key];lines.append(f"|{label}|{p(x['dice14_mean'])}|{p(x['dice14_ge80'])}|{p(x['main_recall14_mean'])}|")
    lines+=['',
        '固定策略权重，供给调整使Dice均值增加5.12个百分点、主系完整度增加5.70个百分点。按房间配对自助法95%区间分别约为[1.05,10.10]和[1.25,11.09]个百分点；达标率增加11.67个百分点的区间包含0，因此不能把达标率改善说成确定结论。',
        '固定所选供给，学习权重反而比初始Dice策略低1.61个Dice百分点（区间约[-5.46,0.64]）。第三阶段验证接受不等于最终证明学习有效；本次主要收益来自Dice边际评分结构与供给调整，不宜推广所学权重为更优战斗AI。','',
        '|最终牌组对战对照|场数|得分率（平局半分）|按房间95%区间|',
        '|---|---:|---:|---:|']
    for key,label in [('vs-baseline-pool','原供给，同学习权重'),('vs-prior-agent','同供给，初始策略权重'),('vs-reference','实际路线对应完整标准套牌')]:
        x=a['battles'][key];lines.append(f"|{label}|{x['n']}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    lines+=['','对完整标准套牌仅25.8%得分，说明缺少的少数运转牌、传奇与卡序仍可能明显削弱强度；高Dice只能说明组成接近，不能替代战斗成熟度。每项对照均交换先后手，研究引擎与战斗策略保持一致。','',
        '## 当前供给候选','',
        f"总流通副本{a['total_before']}→{a['total_after']}。按15套标准全局需求调整，不针对某个玩家预定路线暗送卡。非传奇109种+1、103种−1、8种不变；通用传奇每名2份、路线和叠层传奇每名1份均未变。",'',
        '|类别|不同卡名|旧总份数|新总份数|新每名份数：对应卡名数|',
        '|---|---:|---:|---:|---|']
    for rarity,rl in [('common','普通'),('rare','稀有'),('epic','史诗')]:
        for group,gl in [('enchantment','附魔'),('generic','通用')]:
            x=a['supply'][rarity][group];dist='、'.join(f'{k}份×{v}种' for k,v in x['distribution'].items())
            lines.append(f"|{rl}{gl}|{x['names']}|{x['before']}|{x['after']}|{dist}|")
    lines+=['','逐卡份数以[当前份数表](shared-pool-counts.json)为准；[当前机器参数](construction-probabilities.json)中的逐卡覆盖优先于类别基础份数。原始1060份供给另保留为construction-baseline-v2.json，便于复验。',
        '专精后主系附魔目标60%→65%，通用目标35%；这是合法库存充足时的软比例。专精前仍按2/3/4种元素=20%/60%/20%，同面同系最多1张；首面买过元素在刷新中的准入仍10%，未增加前期追同系权重。专精已达目标，因此没有必要放松这些约束。所有稀有度概率、传奇类型和保底不变。','',
        '## 元素分流、路线与传奇竞争','',
        f"15组中5组四种元素、9组三种、1组两种；{p(a['room_fraction_at_least_three_elements'])}的房间至少三种专精，平均{r['mean_elements']:.2f}种。火/土/毒/水/风人数分别为12/9/13/12/14。没有强制四人异系；无去竞争池对照，因此不能单凭此结果证明分流完全由卡池造成。",'',
        '15条路线均有实际样本，但燃烧血统、穿云箭各仅1人，不能据此声称每条路线均已稳定达标。疾风之刃11人、余烬之核8人，选择仍不均衡。','',
        '|实际路线|样本|Dice均值|Dice≥80%|主系完整度|',
        '|---|---:|---:|---:|---:|']
    for route,x in a['routes'].items():lines.append(f"|{route or '无路线'}|{x['n']}|{p(x['dice'])}|{p(x['hit'])}|{p(x['main'])}|")
    lines+=['',
        '本次所选策略累计62次“目标通用传奇已无可用副本”的检测，原供给同权重为69次、同供给初始策略为25次；这是重复检测次数，不是62张牌或62个独立受害玩家。AI会改抓其他运转牌或继续完善主系，而不会假定必定拿到指定通用传奇。此次没有解除传奇竞争的对照，不能定量分离通用传奇稀缺造成的独立战力损失。仅发生3次路线替换，也不足以证明临场变阵成熟。','',
        '## 可复核性与限制','',
        '145组四人课程、4060场轮内战斗、360场最终对战，合计4420场；尝试2016次双方学习更新，最终选中模型只继承第三阶段672次。独立审计回放8120个人轮次、101505个展示副本、11131次购买及6082次删除；库存、同名、传奇保护、点数、免费资格、保底位置与实际路线Dice均通过。',
        '概率理论上限仍为：第2轮史诗首面14.92%、两面36.02%；第6/7轮传奇两面9.55%/18.23%，均满足用户硬上限。库存约束可使实际出现率更低。',
        '95%区间按15个独立房间重采样，不能把共享牌池中的60位玩家当60个完全独立样本。四人固定完成14轮，无淘汰；混系研究战斗适配器未完成封版级全面交互验证。本次没有新增牌厚度硬下限，也没有为提高分数修改参考套牌。',
        '',f"原始记录与配置：[实验目录](../../research/{out.name})。其中summary.json、analysis.json、audit.json、optimization-history.json、selected-config.json、selected-weights.json、episodes.jsonl.gz与sources/共同保存结果、逐笔行为和执行时源码。最终配置是验证选中，最终结果未反向参与调参。",'',
        '下一步应优先验证缺失关键运转组件的战力损失，并加入足够的厚度收益或删牌机会成本；本次不继续越过三轮授权追调最终测试。','']
    (docs/'simulation-v3-report.md').write_text('\n'.join(lines),encoding='utf-8')
    for name in ['audit_dice_optimization.py','analyze_dice_optimization.py']:
        shutil.copyfile(__file__.replace('analyze_dice_optimization.py',name),out/'sources'/name)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--publish',action='store_true');args=ap.parse_args()
    out=C.ROOT/'research'/args.run
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    conditions=defaultdict(list)
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line)
            if ep['condition'].startswith('final-'):conditions[ep['condition']].append(ep)
    selected=conditions['final-selected'];routes=defaultdict(list)
    for ep in selected:
        for p in ep['players']:routes[p['route']].append(p)
    route_table={r:dict(n=len(ps),dice=st.mean(p['route_dice'] for p in ps),
                       hit=st.mean(p['route_dice']>=.8 for p in ps),
                       main=st.mean(p['route_main_recall'] for p in ps)) for r,ps in routes.items()}
    cis={}
    for metric,fn in [('dice14',lambda p:p['route_dice']),('hit14',lambda p:p['route_dice']>=.8),
                      ('main14',lambda p:p['route_main_recall']),
                      ('joint14',lambda p:p['route_dice']>=.8 and p['route_main_recall']>=.8),
                      ('spec5',lambda p:0<p['spec_round']<=5)]:
        cis[metric]=interval([st.mean(fn(p) for p in ep['players']) for ep in selected])
    paired={}
    for control in ['final-baseline-pool','final-prior-agent']:
        pairs=list(zip(selected,conditions[control]))
        paired[control]={}
        for name,fn in [('dice14',lambda p:p['route_dice']),('hit14',lambda p:p['route_dice']>=.8),
                        ('main14',lambda p:p['route_main_recall'])]:
            paired[control][name]=interval([st.mean(fn(p) for p in a['players'])-st.mean(fn(p) for p in b['players']) for a,b in pairs])
    battles={}
    for label in summary['comparisons']:
        raw=json.loads((out/(label+'-battles.json')).read_text(encoding='utf-8'))
        grouped=defaultdict(list)
        for row in raw['rows']:grouped[row['episode']].append(row['score'])
        battles[label]=dict(n=raw['n'],**interval([st.mean(v) for v in grouped.values()]))
    base=json.loads((out/'phase1-previous-config.json').read_text(encoding='utf-8'))
    cfg=json.loads((out/'selected-config.json').read_text(encoding='utf-8'))
    supply={};deltas=Counter()
    for rarity in ['common','rare','epic','legendary']:
        supply[rarity]={}
        for group in ['enchantment','generic']:
            cards=[c for c in C.CARDS.values() if c.rarity==rarity and (c.element=='generic')==(group=='generic')]
            supply[rarity][group]=dict(names=len(cards),before=sum(copies(c,base) for c in cards),
                after=sum(copies(c,cfg) for c in cards),distribution=dict(sorted(Counter(copies(c,cfg) for c in cards).items())))
    for n,c in C.CARDS.items():
        if c.rarity in ('common','rare','epic'):deltas[copies(c,cfg)-copies(c,base)]+=1
    complete=st.mean(p['route_main_recall']==1 for ep in selected for p in ep['players'])
    element_counts=Counter(ep['elements'] for ep in selected)
    ps=[p for ep in selected for p in ep['players']]
    jaccard=dict(mean=st.mean(p['actual_route_similarity']['jaccard'] if p['route'] else 0 for p in ps),
                 hit=st.mean(bool(p['route']) and p['actual_route_similarity']['jaccard']>=.8 for p in ps))
    result=dict(confidence=cis,paired=paired,battles=battles,routes=route_table,supply=supply,
                total_before=sum(copies(c,base) for c in C.CARDS.values()),
                total_after=sum(copies(c,cfg) for c in C.CARDS.values()),
                copy_delta_names=dict(deltas),main_fully_complete=complete,jaccard14=jaccard,
                distinct_elements_per_room=dict(element_counts),
                room_fraction_at_least_three_elements=st.mean(ep['elements']>=3 for ep in selected),
                interpretation='95% percentile bootstrap by room, n=15 independent rooms; exploratory, not a powered balance claim')
    (out/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.publish:publish(out,summary,result,cfg)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
