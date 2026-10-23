"""Publish the completed experiment, including failures and comparison limits."""
import argparse
import json
import shutil
from pathlib import Path
import cards as C


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    out=C.ROOT/'research'/args.run;read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
    s=read('summary.json');a=read('analysis.json');audit=read('audit.json');r=s['final'];p=lambda x:f'{x:.1%}'
    lines=['# growth-v4：统一份数与三轮构筑／战斗联合训练','',
        '日期：2026-10-23。卡牌v1.0、15套标准牌组、原战斗引擎与历史策略文件保持原样。以下全部为新统一牌池下重新模拟，未沿用v3成绩。','',
        '结论：三轮完成，只保留第一轮候选；未证明稳定的战斗学习增益，实际牌组尚不能比肩标准。专精速度达标，另修正了等待不可得路线的流程缺陷。最明显的成熟度缺口是通用运转核心，不能仅靠增加主系贴合度弥补。','',
        '## 用户约束与本轮改进','',
        '- 非传奇按普通/稀有/史诗×附魔/通用分六类；同类各卡名投入份数相同，附魔与通用两类可不同。约束写入AGENTS.md，并在建池、调参、发布与验证时检查。持有与展示占用会使剩余库存自然不同，不改变初始投入约束。',
        '- 撤下按卡名倾斜的v3候选，使用普通6/8、稀有4/6、史诗3/4份，总1060份；三轮固定供给，专精后附魔软目标65%。传奇、概率上限、保底及研习经济不改，第二次删牌仍1点。',
        '- 构筑评分强调尽早专精、主系覆盖、真实运转缺口、获得路线，以及路线稀有/史诗。Dice只是组成目标，战斗奖励来自真实已抓牌组的对战。',
        '- 未获得路线时学习轮次阶段共性；获得路线后迁移历史路线与各对局知识，再积累本次实际卡组经验。没有抓到的核心不会被当作等待启动的必要条件；出牌只投影当前可用牌与公开状态。','',
        '## 三轮训练及验证','',
        '每轮8组四人14轮训练；每次构筑后两两对战，双方分别试验一次小幅策略突变，对手策略、双方卡组与种子保持不变。额外试验不计入连胜败和牌池。策略更新后进入下一轮。构筑权重另根据战斗与组成进展更新。每轮用4组独立验证，构筑与战斗分别采纳或回退。','',
        '|轮次|构筑D14：旧→新|专精≤5：旧→新|同卡组战斗得分：旧→新|构筑采纳|战斗采纳|',
        '|---|---:|---:|---:|---|---|']
    for h in s['history']:
        b,c=h['before'],h['after'];v=h['combat_validation']
        lines.append(f"|{h['phase']}|{p(b['dice14_mean'])}→{p(c['dice14_mean'])}|{p(b['spec_by5'])}→{p(c['spec_by5'])}|{p(v['old'])}→{p(v['new'])}|{'是' if h['draft_accepted'] else '否'}|{'是' if h['combat_accepted'] else '否'}|")
    lines+=['','战斗验证把新旧出牌器放在同一批实际卡组上，固定对手，仅更换己方控制器。构筑验证两方均使用同一供给与命名种子，但行为、战斗和连胜奖励可改变后续构筑轨迹，不能把所有差异都归因于一次抓牌。验证样本较少，最终测试才用于判断泛化；最终成绩没有参与选版。','',
        '## 最终构筑流程','',
        f"最终12组独立四人局、48名玩家。第5轮结束前专精{p(r['spec_by5'])}，第6轮结束{p(r['spec_by6'])}。",'',
        '|轮次|专精率|持有路线|运转齐备率|平均张数|平均费用|',
        '|---|---:|---:|---:|---:|---:|']
    for k,x in a['flow'].items():lines.append(f"|{k}|{p(x['spec'])}|{p(x['route'])}|{p(x['operation_complete'])}|{x['size']:.2f}|{x['cost']:.2f}|")
    lines+=['','“运转齐备”采用参考构筑诊断门槛：至少2张过牌、2张检索、1张洗牌；类别可交叉，不是新增游戏硬规则。过牌等效果强度与实际卡序仍有差异。',
        '第6/7轮传奇两面仍受10%/20%上限约束，因此多数玩家不可能很早获得路线；应区分“专精早”与“在第8轮首次高供给窗口及时定路线”。首次路线获得轮次分布：'+str(a['first_route_rounds'])+'。','',
        '|时点|实际路线Dice均值|Dice≥80%|主系完整度均值|两者均≥80%|',
        '|---|---:|---:|---:|---:|']
    for n in [12,13,14]:lines.append(f"|第{n}轮|{p(r[f'dice{n}_mean'])}|{p(r[f'dice{n}_ge80'])}|{p(r[f'main_recall{n}_mean'])}|{p(r[f'joint{n}_ge80'])}|")
    lines+=['','Dice按实际持有路线对应标准套牌计算，无路线记0；不选最近套牌凑分。主系完整度包含专精与路线。剔除专精/路线后，其余标准主系卡全部到齐的玩家比例为'+p(a['main_enchantment_complete'])+'（只统计已持路线者）。',
        f"第14轮平均{r['mean_size14']:.2f}张；标准平均20.6张。每位玩家平均删除{r['mean_deletes']:.2f}次、付费删除消耗{r['mean_delete_points']:.2f}点。牌厚度与删牌倾向仍应和战力一起判断。",'',
        '## 同一实际卡组，战斗AI是否更会发挥','',
        '以下使用同一实际卡组、同一固定对手和种子比较。对手控制器为训练前的历史迁移策略；新旧均交换先后手。“旧”已含历史路线知识，不能把接入历史知识的收益误报成新学习的收益。','',
        '|构筑轮次|旧出牌器得分|新出牌器得分|旧费用浪费|新费用浪费|',
        '|---|---:|---:|---:|---:|']
    for k,x in a['stage_control'].items():lines.append(f"|{k}|{p(x['old']['score'])}|{p(x['new']['score'])}|{p(x['old']['unused'])}|{p(x['new']['unused'])}|")
    lines+=['','第14轮另面对完整15条标准路线，每个方案1440场。对手固定为完整标准卡组与历史迁移控制器；同一方案内48人的对局相关，区间按12个房间聚类自助重采样。本轮对手是全15路线，与v3只对相应路线的25.8%口径不同，不能直接相减解释成强度变化。','',
        '|己方方案|胜率|平局率|得分率|得分率95%区间|',
        '|---|---:|---:|---:|---:|']
    labels={'adaptive':'实际卡组＋所学个性策略','historical':'同卡组＋训练前历史迁移','generic':'同卡组＋所学阶段共性（移除路线个性）',
            'portfolio':'同卡组＋独立校准选出的有限策略','full_reference':'对应完整标准卡组＋所学控制器'}
    for key in ['generic','historical','adaptive','portfolio','full_reference']:
        x=a['matrix'][key];lines.append(f"|{labels[key]}|{p(x['win_rate'])}|{p(x['draw_rate'])}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    lines+=['',
        '得分=胜1、平0.5、负0。有限策略在另外3场校准对局中从贪心、共性、历史迁移、所学策略中选择；不在最终测试结果中择优，也不代表最优出牌上界。选择分布：'+str(a['portfolio_choices'])+'。','',
        '|所学策略相对对照的配对得分差|均值|95%区间|',
        '|---|---:|---:|']
    for key in ['historical','generic','portfolio','full_reference']:
        x=a['paired'][key];lines.append(f"|{labels[key]}|{x['mean']*100:+.2f}个百分点|[{x['low']*100:+.2f}, {x['high']*100:+.2f}]|")
    no_route=a['route_failures']
    if no_route:
        lines+=['',f"构筑流程发现明确缺陷：最终{len(no_route)}名无路线玩家中，{sum(x['had_affordable_offer'] for x in no_route)}名曾在牌面打开时拥有足够点数，且展示过同专精路线。不能将其失败全部归因于卡池。当前即时Dice与路线稀有/史诗贴合奖励仍可能压过换成可获得路线的价值；对他人已持有目标路线仅作有限扣分，也可能导致继续等待。逐次报价与点数见analysis.json的route_failures。", 
            '原测试由此指出应先建立路线可获得性与定路线时机的明确决策层，再在可行路线内优化Dice。原最终测试保持封存；后续推理修正及新种子回归单列在最后一节，没有追加第四轮训练。']
    learned=a['paired']['historical'];gap=a['paired']['full_reference']
    lines+=['',
        ('独立测试支持所学战斗策略相对历史迁移有所提升。' if learned['low']>0 else '独立测试尚不足以证明所学战斗策略稳定优于历史迁移；不能仅凭训练接受次数宣称AI更强。'),
        ('实际卡组与完整标准卡组仍有可辨别的强度差距，尚不能称为比肩。' if gap['high']<0 else '实际与标准卡组的强度差仍须结合区间及各路线样本判断，不能将未检出差异等同于强度相等。'),
        '本实验无法证明发挥了理论上“大部分”或全部战力；同卡组控制器对照与独立校准策略组只能提供有限、可复核的发挥参照。','',
        '## 第14轮具体差在哪里','',
        '已持路线者，对应标准卡组各稀有度覆盖：'+ '、'.join(k+' '+p(v) for k,v in a['rarity_recall'].items())+'。缺牌按类型累计：'+str(a['missing_groups'])+'。这表示缺少标准成员的次数，不等于这些牌具有同等战斗价值。','',
        '|缺少的标准牌|累计缺失玩家次数|',
        '|---|---:|']
    for n,q in a['missing_top'].items():lines.append(f'|{n}|{q}|')
    lines+=['',
        '运转瓶颈不能只按“2过牌、2检索、1洗牌”张数判断：便宜的即时资源牌不能等同于持续的抽牌/能量引擎。现有15套标准中14套使用禁忌知识、12套使用禁咒目录，而它们每名只有2份；当四人同时需要同一核心时，不可能人人照抄标准。此为共享池的真实竞争限制，不应以增加这些传奇份数绕过用户约束。',
        '下一轮应在既定份数下研究替代运转组合，按有效抽牌、可用能量和循环吞吐量评估成熟度；同时检验是否过度优先主系牌、过早删除仍能参与运转的非标准牌。当前缺失统计与配对牌组差距支持优先研究这些方向，但尚未逐张消融证明哪张缺牌造成多少损失。']
    lines+=['','|实际路线|人数|Dice均值|主系完整度|实际所学得分|标准所学得分|',
        '|---|---:|---:|---:|---:|---:|']
    for route,x in a['routes'].items():lines.append(f"|{route or '无路线'}|{x['n']}|{p(x['dice'])}|{p(x['main'])}|{p(x['scores']['adaptive'])}|{p(x['scores']['full_reference'])}|")
    lines+=['','各路线人数很少且不均衡，未出现的路线不作结论；每位玩家对15个对手测试不能代替更多独立构筑样本。逐路线缺失卡、低Dice失败样本和元素分流分布见analysis.json。',
        '元素分流房间数：'+str(a['distinct_elements'])+f"；平均{r['mean_elements']:.2f}种。没有强制异系，也没有解除卡池竞争的对照，不能据此单独量化有限池造成的分流作用。",'',
        '## 审计、复核与交付','',
        f"共{audit['joint_training']['total_games']}场：课程{audit['joint_training']['course_games']}、单边候选试验{audit['joint_training']['unilateral_trial_games']}、同卡组对照{audit['joint_training']['fixed_deck_comparison_games']}、最终矩阵{audit['joint_training']['matrix_games']}、独立策略校准{audit['joint_training']['portfolio_calibration_games']}、共性消融{audit['joint_training']['generic_probe_games']}。", 
        f"尝试{audit['joint_training']['combat_candidate_updates']}次战斗参数更新，其中局部接受{audit['joint_training']['local_acceptances']}次；独立验证可再否决候选。全{audit['joint_training']['episodes']}组课程的库存、同名、传奇保护、免费资格、点数和Dice已独立回放通过，六类等份数检查通过。", 
        '卡牌数值与原引擎回归检查通过。四人固定完成14轮，没有淘汰；混系研究执行器仍未取得全部交互的封版级认证。历史策略只是迁移起点，旧版胜率未用于本轮结论。',
        '',f"[原始实验目录](../../research/{out.name})保存每轮抓牌、两面对局、参数轨迹、阶段采纳、最终模型、同种子对照与源码快照。当前构筑机读参数为construction-probabilities.json，逐卡份数为shared-pool-counts.json。所学策略单独存为selected-model.json，不覆盖历史policies.json。",'',
        '继续优化应以已发现的主系/运转缺口和同卡组发挥差距为依据，而不是继续提高Dice权重来替代战斗验证。','']
    repair_dir=out/'route-feasibility-repair'
    if (repair_dir/'summary.json').exists():
        from collections import defaultdict
        import gzip
        import statistics as st
        from analyze_dice_optimization import interval
        repair=json.loads((repair_dir/'summary.json').read_text(encoding='utf-8'))
        mat=json.loads((repair_dir/'matrix.json').read_text(encoding='utf-8'))['rows']
        repair_audit=json.loads((repair_dir/'audit.json').read_text(encoding='utf-8'))
        assert repair_audit['status']=='passed' and repair_audit['counts']['course_battles']==336
        assert repair['training_updates']==0 and len(mat)==1440
        rooms=defaultdict(list);rates=defaultdict(list)
        for row in mat:rooms[(row['condition'],row['episode'])].append(row['score'])
        with gzip.open(repair_dir/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                ep=json.loads(line);rates[ep['condition']].extend(bool(q['route']) for q in ep['rounds'][7]['players'])
        delta=interval([st.mean(rooms[('repaired',i)])-st.mean(rooms[('control',i)]) for i in range(6)])
        lines+=['## 三轮之后的流程修正回归（不追加训练）','',
            '发现上述未定路线缺陷后，保留三轮训练和原最终测试原样，补充独立的推理规则：未持有路线时，将他人已持有的唯一路线从目标候选中排除；第8轮起有可购买同系路线时，在当前可得路线中比较适配度。已持有路线时保留现有购买/替换逻辑；所有路线均被占用时正常构筑，不凭空造牌。没有修改份数、概率、费用、战斗权重或增加研习点。',
            '另用6组新种子，对照与修正各24名玩家，参数全程冻结、额外训练更新0次。此为发现缺陷后的回归，不能冒充先前封存测试；它使用与原测试不同的样本。','',
            '|新种子回归|原流程|修正流程|',
            '|---|---:|---:|',
            f"|第8轮持有路线|{p(st.mean(rates['repair-control']))}|{p(st.mean(rates['repair-feasible']))}|",
            f"|第14轮实际路线Dice均值|{p(repair['control']['dice14_mean'])}|{p(repair['repaired']['dice14_mean'])}|",
            f"|第14轮Dice≥80%|{p(repair['control']['dice14_ge80'])}|{p(repair['repaired']['dice14_ge80'])}|",
            f"|第14轮主系完整度|{p(repair['control']['main_recall14_mean'])}|{p(repair['repaired']['main_recall14_mean'])}|",
            f"|对全部15套标准的得分率|{p(repair['score']['control'])}|{p(repair['score']['repaired'])}|",'',
            f"对标准套牌的配对得分差为{delta['mean']*100:+.2f}个百分点，按6个房间的探索性95%区间[{delta['low']*100:+.2f}, {delta['high']*100:+.2f}]。更早定路线不保证每份牌组的Dice都增加；不能仅凭这次小样本宣布普遍增强。", 
            '修正回归库存、费用、传奇与Dice独立审计通过，补充336场课程对战和1440场标准路线对照，共1776场；与三轮正式实验合计'+str(audit['joint_training']['total_games']+1776)+'场。',
            '当前推理入口为joint_draft_inference.load_model：加载原selected-model.json并安装已修正的可得路线决策，不覆盖历史policies.json。详细结果位于原实验目录下route-feasibility-repair/。','']
        profile=dict(status='post_diagnostic_inference_repair_candidate',source_experiment=args.run,
            checkpoint='selected-model.json',loader='tools/round_robin/joint_draft_inference.py:load_model',
            construction_module='route_feasible_draft.py',extra_training_updates=0,
            original_three_cycles_preserved=True,repair_paired_score_delta=delta)
        (out/'selected-inference.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (C.ROOT/'docs/deckbuilding/simulation-v4-report.md').write_text('\n'.join(lines),encoding='utf-8')
    for name in ['analyze_joint_draft.py','audit_joint_draft.py','report_joint_draft.py','joint_draft_inference.py','test_route_feasible_draft.py']:
        shutil.copyfile(Path(__file__).parent/name,out/'sources'/name)
    print('Report written.')


if __name__=='__main__':main()
