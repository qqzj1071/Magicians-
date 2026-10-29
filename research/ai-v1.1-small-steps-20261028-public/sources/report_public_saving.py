"""Publish two-cycle results with explicit savings and opportunity controls."""
import argparse
import json
import shutil
from pathlib import Path
import cards as C


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    out=C.ROOT/'research'/args.run;read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
    s=read('summary.json');a=read('analysis.json');audit=read('audit.json');p=lambda x:f'{x:.1%}'
    labels={'selected':'所选新AI','legacy':'旧v4修正流程','no_saving':'同参数关闭存费','initial_new':'未学习的新AI',
            'same_cards_old_combat':'新卡组＋旧战斗AI','full_reference':'完整标准卡组＋新战斗AI'}
    lines=['# growth-v5：公开播报、存费与两轮战斗优先优化','',
        '日期：2026-10-23。新规则、算法、样本、控制和原始记录均独立保存；不修改卡牌v1.0、15套标准牌组、冻结引擎或历史策略。','',
        '本次完成两轮优化与7096场正式记录。最终独立测试中新方案明显退步，强存费策略也弱于关闭存费对照，因此不提升为默认。保留旧检查点与核心构筑逻辑，公开播报作为独立兼容功能接入；本次候选及失败记录完整保留。','',
        '## 执行边界','',
        '- 普通附魔/通用6/8、稀有4/6、史诗3/4份，同类各卡名等份数；总1060。传奇、出率、保底、65%专精后附魔目标、研习收入/继承/免费/删牌价格全部不变。',
        '- 专精与路线选择/替换逐笔向四人播报；所有AI立即更新同一公开状态并重评目标。换目标后稀有、史诗与Dice都按新路线计算。当前被他人持有或尚未到回池轮次的路线不作为可得目标，全部不可得时允许无路线继续构筑。',
        '- 存费比较眼前卡组收益与最多2点继承的未来价值；已发生的上一场表现差时降低存费压力。第1轮为第2轮史诗留支付能力，第5轮为第6轮刷新加传奇留灵活度，保底前也考虑存点。存费不会提高任何出率。',
        '- 刷新估值看当前未购位置、合法卡表、自己的牌、已知概率与预算，不读取二面预生成稀有度或未来牌；构筑目标选择不读取别人私有牌组。',
        '- 评分加入抽牌、能量、检索保留数、洗牌的中性状态投影，取代仅数“2过牌2检索1洗牌”的充分性假设；投影仍是启发式，不是实际每回合吞吐量。Dice继续提供路线指引，构筑学习以90%战斗奖励和10%运转进展更新，选版不以Dice为目标。','',
        '## 两轮优化与选版','',
        '每阶段8组四人14轮训练，旧/新各4组冻结验证。每次构筑后两两对战，胜败双方更新构筑评分，并各做一次固定对手与种子的单边战斗参数试验。构筑按各轮真实卡组对固定同期旧对手的得分及小幅生命差选版，并保护早期专精率；战斗参数单独用相同卡组验证。','',
        '|阶段|固定同期对手得分：旧→新|战斗效用：旧→新|专精≤5：旧→新|同卡组战斗：旧→新|构筑/战斗采纳|',
        '|---|---:|---:|---:|---:|---|']
    for h in s['history']:
        x=h['strength'];c=h['combat']
        lines.append(f"|{h['phase']}|{p(x['score']['old'])}→{p(x['score']['new'])}|{x['utility']['old']:.3f}→{x['utility']['new']:.3f}|{p(h['before']['spec_by5'])}→{p(h['after']['spec_by5'])}|{p(c['old'])}→{p(c['new'])}|{'是' if h['draft_accepted'] else '否'} / {'是' if h['combat_accepted'] else '否'}|")
    from public_saving_draft import PRIOR
    lines+=['','|构筑评分权重|新结构初值|第一轮后采用|第二轮后采用|',
        '|---|---:|---:|---:|']
    for key,label in [('dice','Dice指引'),('progress','前期专精'),('main','标准主系覆盖'),('draw_capacity','抽牌容量'),
                      ('energy','能量容量'),('bank','存费'),('coin','消费成本'),('refresh','刷新预期收益')]:
        lines.append(f"|{label}|{PRIOR[key]:.3f}|{s['history'][0]['weights'][key]:.3f}|{s['history'][1]['weights'][key]:.3f}|")
    lines+=['','权重只应在相同特征内比较，不是卡牌数值。多项权重与在线经验同时变化，验证能衡量整个候选，不能把全部增益归因于某一行权重。']
    lines+=['','效用=胜1平0.5负0，再加0.05×截断生命差；不是Dice。构筑保护线为第5轮专精率至少75%，且不能比同阶段旧检查点下降超过10个百分点。第二轮只使用第一轮验证提出调整，具体为：'+str(s['history'][1]['changes'])+'。失败候选保留，不把训练对战的接受次数当泛化提升。','',
        '## 最终独立构筑与存费','',
        '最终每方案8组新种子、32名玩家，参数冻结。相同命名种子用于旧流程、新AI、同参数关闭存费、未学习新AI；不同决策会影响随机数消耗、胜败奖励及后续库存，配对对照衡量整个策略改变，不能解释成单张牌的独立因果。','',
        '|方案|第5轮结束专精|第6轮结束专精|D14均值|D14≥80%|平均张数|平均费用|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for key in ['legacy','selected','no_saving','initial_new']:
        x=s['final' if key=='selected' else key]
        lines.append(f"|{labels[key]}|{p(x['spec_by5'])}|{p(x['spec_by6'])}|{p(x['dice14_mean'])}|{p(x['dice14_ge80'])}|{x['mean_size14']:.2f}|{x['average_cost']:.2f}|")
    lines+=['','Dice按实际持有传奇路线对应标准牌组计算，无路线记0；此处只诊断组成，不用达标率宣布更强。','',
        '|时点|所选新AI平均存点|关闭存费平均存点|旧流程平均存点|所选新AI刷新率|关闭存费刷新率|',
        '|---|---:|---:|---:|---:|---:|']
    for r in ['1','2','5','6','7','8','12','14']:
        x=a['finance']['final-selected']['rounds'][r];y=a['finance']['final-no-saving']['rounds'][r];z=a['finance']['final-legacy']['rounds'][r]
        lines.append(f"|{r}|{x['bank']:.2f}|{y['bank']:.2f}|{z['bank']:.2f}|{p(x['refresh'])}|{p(y['refresh'])}|")
    wasted=a['finance']['final-selected']['rounds']['5']['discarded_points']
    no_wasted=a['finance']['final-no-saving']['rounds']['5']['discarded_points']
    lines+=['',f'第5轮超过继承上限而失去的点数，存费组平均{wasted:.2f}点，关闭存费组{no_wasted:.2f}点。剩点超过2并无额外未来价值；可能是拒绝无益弱牌，也可能是估值过于保守，不能把这些点数记作成功存费。']
    lines+=['','第14轮为本次有限训练期限，终点剩点价值置0；这不是实际游戏必须在第14轮结束的规则，不能直接照搬为无限轮次AI。没有强制每轮存1/2点，符合当前收益的免费牌仍可在0点购买。','',
        '|支付机会（每方案32名玩家）|所选新AI|关闭存费|旧流程|',
        '|---|---:|---:|---:|']
    for field,label in [('r2_first_affordable_income','第2轮开面有≥3点'),('r2_first_seen','第2轮首面实际见到史诗'),
        ('r2_first_seen_affordable','见到史诗且开面可支付'),('r6_first_affordable_income','第6轮开面有≥4点'),
        ('r6_can_refresh_and_pay_after_first','第6轮首面消费后仍能付刷新＋传奇'),('r6_bought','第6轮购买传奇张数')]:
        values=[a['finance'][k]['opportunities'].get(field,0) for k in ['final-selected','final-no-saving','final-legacy']]
        lines.append('|'+label+'|'+'|'.join(str(x) for x in values)+'|')
    lines+=['','能支付不等于一定刷到或应该买；第2轮史诗、第6轮传奇实际曝光样本很少，不用少量成功/失败个例推断改变了概率。第6轮基础4点，存1点就能支付刷新加传奇；存2点多出的是首面灵活消费余地，若首面先花太多仍会失去刷新后的购买能力。','',
        '## 存费的即战力代价','',
        '同一所选战斗控制器，比较存费与关闭存费所生成的实际卡组；对手固定为同种子旧流程的同期牌组，另用新战斗种子。','',
        '|轮次|存费得分|关闭存费得分|配对差95%区间|',
        '|---|---:|---:|---:|']
    for r,x in a['early_saving'].items():lines.append(f"|{r}|{p(x['score']['saving'])}|{p(x['score']['no_saving'])}|[{x['paired']['low']*100:+.2f}, {x['paired']['high']*100:+.2f}]个百分点|")
    lines+=['','这组结果应与后期收益一起解释；不能把“留住了点数”本身作为好运营的证明。','',
        '## 实际战斗与对照','',
        '第14轮每位玩家面对3个轮换标准对手及所选路线标准对手（去重），交换先后手。所有方案使用同一对手列表与种子，覆盖全部15条标准路线；不是每位玩家穷举15条，因此不与v4绝对得分直接相减。胜率和得分先算每个房间再平均；区间以8个独立四人房间聚类重采样，均为探索性结果。','',
        '|方案|场数|胜率|得分率（平局半分）|得分95%区间|',
        '|---|---:|---:|---:|---:|']
    for key in ['legacy','initial_new','no_saving','same_cards_old_combat','selected','full_reference']:
        x=a['matrix'][key];lines.append(f"|{labels[key]}|{x['n']}|{p(x['win_rate'])}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    lines+=['','|所选新AI相对对照|配对得分差|95%区间|',
        '|---|---:|---:|']
    for key in ['legacy','initial_new','no_saving','same_cards_old_combat','full_reference']:
        x=a['paired'][key];lines.append(f"|{labels[key]}|{x['mean']*100:+.2f}个百分点|[{x['low']*100:+.2f}, {x['high']*100:+.2f}]|")
    lines+=['',
        ('本批独立样本支持整体新策略强于旧流程。' if a['paired']['legacy']['low']>0 else '本批独立样本中新策略明显弱于旧流程，不推荐作为默认。' if a['paired']['legacy']['high']<0 else '本批独立样本尚不足以证明整体新策略稳定强于旧流程。'),
        ('本批独立样本支持存费带来后期收益。' if a['paired']['no_saving']['low']>0 else '本批独立样本中启用存费明显降低第14轮战力，本次存费权重不予提升。' if a['paired']['no_saving']['high']<0 else '本批独立样本尚不足以证明存费稳定提高第14轮战力；需结合早期代价与支付机会判断。'),
        ('新战斗权重在相同卡组上有可辨别提升。' if a['paired']['same_cards_old_combat']['low']>0 else '相同卡组下，新战斗权重的额外收益未获稳定证明。'),
        ('实际卡组仍明显弱于完整标准；不能称为已经比肩。' if a['paired']['full_reference']['high']<0 else '标准参照差距仍需更多独立样本，未检出差异不等于等强。'),
        '有限评分结构和少量局部参数试验不能证明已发挥卡组理论最优战斗力。','',
        '## 公开改目标与运转缺口','',
        '最终播报/改目标计数：'+str(a['broadcast_counts'])+'。所选新AI在轮末仍以他人已持路线为目标的次数为'+str(a['selected_blocked_target_rounds'])+'；全部同系路线不可得的回退情况须单独解释。播报顺序、四人接收与最终公开状态均独立重建验证，而非只检查最终牌组。','',
        '所选方案拥有的资源牌中性投影总量均值为'+str(a['selected_operation_projection'])+'；这是每张牌效果之和，不是实际每回合收益。实际战斗能量、出牌数量、费用浪费与持续时间见analysis.json中的matrix。','',
        '|缺少的对应标准牌|累计缺失次数|',
        '|---|---:|']
    for name,n in a['missing_top'].items():lines.append(f'|{name}|{n}|')
    lines+=['','禁忌知识、禁咒目录等仍只有全局2份，不能靠改份数让所有玩家照抄标准。未持有指定传奇时，其他抽牌、检索、能量和循环牌可以成为替代；是否有效以实际对战衡量，而不是仅统计卡名或提高Dice。未做逐张消融，不把缺失次数直接解释为该卡的独立战力损失。','',
        '## 审计与复核','',
        f"正式记录共{audit['public_saving']['total_games']}场：课程{audit['counts']['course_battles']}、单边战斗候选{audit['public_saving']['combat_trials']}、验证/同卡组/早期存费对照{audit['public_saving']['comparison_games']}、最终标准矩阵{audit['public_saving']['matrix_games']}。", 
        f"重建{audit['public_saving']['public_courses']}组公开信息课程、{audit['public_saving']['broadcasts']}次播报、{audit['public_saving']['retargets']}次目标变化。库存、金额、免费资格、刷新次数、同名、传奇保护、Dice、六类等份数及来源哈希通过；卡牌与冻结引擎回归通过。", 
        '四人固定完成14轮，无跨轮扣血与淘汰；混系战斗执行器仍为研究原型。存费风险只用上一场结果调节，没有模拟真实赛事残血时来不及兑现存款的危险。研究终点会影响存费激励，8组终测样本不能代替完整赛事认证。','',
        f"[原始实验目录](../../research/{args.run})保留两轮候选、接受/回退、每轮参数、播报、财务决策、两面候选、逐笔购买、最终对照与源码。模型selected-model.json标记public-saving-v1；public_saving_inference.load_model仅用于复现实验候选，不覆盖历史policies.json。",'',
        '## 保留与回退','',
        '不采用本次新构筑权重、强存费权重或新战斗权重作为默认。public_baseline_inference.load_model使用previous-model.json保留旧核心评分、刷新、删除和战斗参数，只增加逐笔公开播报、立即重评目标与路线回池等待。该兼容入口通过私有状态隔离、四人播报与14轮确定性回放检查；未额外训练，也未将上述旧流程战绩追溯归给此新入口。', '',
        '两轮阶段验证每方案只有4组房间，第二轮的验证改善没有在独立终测复现。当前不能证明人工运转特征、存费估值或局部战斗学习足以发挥牌组大部分潜力。后续应优先约束前期专精与即战力损失，再单独校准存费；本次不在终测种子上继续调权重来制造提升。','']
    (C.ROOT/'docs/deckbuilding/simulation-v5-report.md').write_text('\n'.join(lines),encoding='utf-8')
    decision=dict(promote_experimental_construction=False,promote_banking=False,promote_combat=False,
        retained_checkpoint='previous-model.json',compatibility_loader='public_baseline_inference.load_model',
        compatibility_scope='public-protocol replay verified; no additional strength claim',
        candidate_checkpoint='selected-model.json',reason='independent final regression; preserve all candidates')
    (out/'deployment-decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ['analyze_public_saving.py','audit_public_saving.py','report_public_saving.py','test_public_saving.py','public_saving_inference.py','public_baseline_inference.py','test_public_baseline.py']:
        shutil.copyfile(Path(__file__).parent/name,out/'sources'/name)
    print('Report written.')


if __name__=='__main__':main()
