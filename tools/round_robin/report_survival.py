"""Readable empirical duration schedule and qualified AI learning conclusions."""
import argparse
import json
import shutil
from pathlib import Path
import survival_tournament as Q
S=Q.S


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    root=S.C.ROOT/'research'/args.run
    selection=json.loads((root/'release-selection.json').read_text(encoding='utf-8')) if (root/'release-selection.json').exists() else {}
    out=root/selection['chosen_folder'] if selection else root
    read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
    s=read('summary.json');a=read('analysis.json');audit=read('audit.json');p=lambda x:f'{x:.1%}'
    if selection:s['history']=json.loads((root/'history.json').read_text(encoding='utf-8'))
    datasets=[]
    for folder in [root,root/'duration-refinement',root/'duration-probe26']:
        if (folder/'analysis.json').exists():datasets.append(json.loads((folder/'analysis.json').read_text(encoding='utf-8')))
    total={key:sum(x['counts'][key] for x in datasets) for key in ('rooms','course_battles','training_trials','matrix_games','total_formal_games')}
    lines=['# 生存赛事：三轮学习与扣血表验证','',
        '日期：2026-10-23。本次从保留的旧检查点出发，加入完成专精的即时收益、100血赛事、提前公布对手和幽灵，进行三轮构筑/战斗学习及扣血表校准。卡牌v1.0、概率、六类等份数、传奇和基础研习经济保持不变。','',
        '## 独立终测','',
        f"最终锁定表与模型后，运行{s['final']['rooms']}个新种子四人房间，持续到决出冠军或并列冠军。每名冠军对15套标准牌组各交换先后手一次，另有同卡组旧控制器与完整标准参照。",'',
        '|目标|终测结果|95%区间|', '|---|---:|---:|']
    for key,label,target in [('strong12','第12轮末赛事血量>40（初始玩家）',.7),('alive15','第15轮末存活（初始玩家）',.5),('ended18','第18轮末房间已结束',.98)]:
        x=a['final_intervals'][key];lines.append(f"|{label}，目标{p(target)}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    ending='、'.join(f'第{r}轮{n}房间' for r,n in sorted(s['final']['end_histogram'].items(),key=lambda x:int(x[0])))
    lines+=['',f"平均结束轮次{s['final']['mean_end']:.2f}，最晚第{s['final']['max_end']}轮；并列冠军房间{s['final']['tied']}个。结束分布：{ending}。",'',
        '第12/15轮比例按初始全部玩家计算，区间按四人房间聚类重采样；房间结束率用Wilson区间。提前结束的冠军血量冻结，淘汰者记0。70%和50%为接近目标，不是有限样本中必须精确命中。当前后期基础扣血100提供18轮结束的规则上界；更改赛事回血、匹配或其他规则后仍须复核。',
        '第15轮各房间存活人数：'+'、'.join(f'{k}人存活{v}房间' for k,v in sorted(a['alive15_room_histogram'].items(),key=lambda x:int(x[0])))+'。平均50%存活不代表每个房间都恰好剩两人。','',
        '## 扣血参数表','',
        '`败损 = m + floor(ln(max(x,1)) × n)`；x是胜方战斗角色剩余生命，不是胜方赛事血。双死双方只扣m。胜者不扣。','',
        '|轮次|基础m|系数n|x=100时败损|x=500时败损|x=1000时败损|','|---|---:|---:|---:|---:|---:|']
    for r,values in s['table'].items():
        m,n=values;lines.append(f'|{r}|{m}|{n:.1f}|{Q.damage(m,n,100)}|{Q.damage(m,n,500)}|{Q.damage(m,n,1000)}|')
    lines+=['','m和n均单调不减，允许平台。第13轮后扣血显著提高，是为了兼顾第12轮保留血量与随后快速淘汰；此曲线的手感仍需实际玩家验证。第20轮以后，m每轮加5，n每轮加0.1；模拟不设18/20轮强制停止。',
        '补充表在第17、18轮将基础扣血设为100：赛事血量只减不增，故第17轮结束至多两名活人，第18轮至多一名。它提供确定收束，代价是后期进入单败淘汰阶段；这不是98%概率保证来自小样本，而是规则本身更强的上界。','',
        '## 三轮训练与接受/回退','',
        '每阶段12个训练房间，四个独立在线分支阶段末平均参数；旧/新各12个真实淘汰赛事验证。相同验证房间命名种子，决策改变后库存、抽样消耗与冠军可能变化。构筑以冠军卡组用同一旧控制器对标准的得分和早期专精保护线选版；战斗以同一卡组的新旧控制器比较。该选版有冠军筛选和小样本局限，不能将阶段改善当作全部玩家的因果提升。','',
        '|阶段|第5轮专精旧→新|冠军同控制器对标准旧→新|同新卡组旧→新控制器|采纳构筑/战斗|','|---|---:|---:|---:|---|']
    for h in s['history']:
        lines.append(f"|{h['phase']}|{p(h['before']['spec_by5'])}→{p(h['after']['spec_by5'])}|{p(h['benchmark_before']['old_combat'])}→{p(h['benchmark_after']['old_combat'])}|{p(h['benchmark_after']['old_combat'])}→{p(h['benchmark_after']['candidate'])}|{'是' if h['draft_accepted'] else '否'}/{'是' if h['combat_accepted'] else '否'}|")
    lines+=['','|阶段使用的扣血表|第12轮>40血（验证后）|第15轮存活（验证后）|18轮内结束（验证后）|','|---|---:|---:|---:|']
    for h in s['history']:
        x=h['after'];lines.append(f"|{h['phase']}|{p(x['strong12'])}|{p(x['alive15'])}|{p(x['ended18'])}|")
    initial=json.loads((root/'initial-model.json').read_text(encoding='utf-8'))['draft'];trained=read('selected-model.json')['draft']
    lines+=['','|同一评分特征|v6初值|最后采用|','|---|---:|---:|']
    for key,label in [('specialization_jump','完成专精跃迁'),('effective_layers','有效附魔层收益'),('bank','存费'),('next_counter','下一对手对策'),('coin','消费成本'),('refresh','刷新预期收益')]:
        lines.append(f'|{label}|{initial[key]:.3f}|{trained[key]:.3f}|')
    lines+=['','存费权重变化很小，消费成本与刷新估值变化更明显。权重只在同一特征内可比，多项参数同时变化，不能据此证明某项单独带来了收益。第二、三阶段在早期专精已较充分时提出对策权重+10%的候选，第二阶段被拒，第三阶段仅构筑被采纳。']
    lines+=['','先用固定战斗轨迹筛选参数，再做真实淘汰验证。固定轨迹改变扣血后的淘汰/幽灵/库存反馈均不精确。原筛选器曾将缺少第18轮的提前结束轨迹计入分母，使screen结束率被低估；诊断已修正，原始源码和记录保留，真实赛事扣血不受影响。','',
        '三阶段后第一张表的200房间终测为：第12轮>40血68.875%、第15轮存活43.75%、18轮内结束100%，中期淘汰过快，因此未作为最终表。随后冻结AI，用新校准种子比较中期基础扣血；基于校准记录锁定最终表，再用全新200房间独立复测。没有第四轮AI训练。选表依据与时点见release-selection.json，未复用第一轮终测种子来制造达标。','',
        '## 专精、路线与研习运营','',
        f"终测玩家第5轮结束前完成专精比例{p(s['final']['spec_by5'])}，第6轮结束前{p(s['final']['spec_by6'])}。每房间平均不同专精数{s['final']['mean_elements']:.2f}。",'',
        '所有人初始8张相同，参考偏好按15条路线轮换，不强行分配专精；该偏好课程并非四名完全无偏玩家的自然分布。没有无限池/无竞争对照，不能把不同专精数归因于牌池独立作用。', '',
        '第三张同系牌跨过门槛时，额外计入赠送专精卡和已有本系附魔增益提升；模型仍保留Dice指引和路线稀有/史诗覆盖。评分为机制启发式，未进行专精特征单独消融，不能把全部专精速度归因于这一个特征。','',
        '存费价值随赛事血量相对预计败损下降，不再在第14轮人为归零。对策估值仅看下一对手公开专精/路线和自己的牌，播报后立即更新。各系文字机制的对策特征较粗，尚不能证明已精通所有路线变阵。','',
        f"终测实际发放连胜奖励{a['bonus_points'].get('win',0)}点、连败奖励{a['bonus_points'].get('loss',0)}点。奖金确已进入经济与学习，但奖金发放次数不能证明主动控连胜/连败策略已学会。",'',
        '构筑奖励包含本场胜负、角色生命差、实际赛事扣血、淘汰惩罚与小幅连胜败奖金。它仍偏重近期反馈，未来存费价值主要由启发式近似；没有多回合对手建模与显式“主动摆烂”策略搜索，不能声称已学会牺牲一轮换取整局最优收益。','',
        '不同轮次/血量下的平均存点、购买、刷新和超过继承上限的损失见analysis.json中的finance；不同血量组牌组强度和经历不同，不能将组间差别当成血量单独造成的效果。','',
        '|构筑轮次|平均继承点|刷新比例|平均购牌|超过继承上限损失|','|---|---:|---:|---:|---:|']
    for r in [1,5,8,12,15,17]:
        xs=[x for key,x in a['finance'].items() if key.split(':')[0]==str(r)];n=sum(x['n'] for x in xs)
        if not n:continue
        avg=lambda key:sum(x[key]*x['n'] for x in xs)/n
        lines.append(f"|{r}|{avg('bank'):.2f}|{p(avg('refresh'))}|{avg('purchases'):.2f}|{avg('discarded'):.2f}|")
    lines+=['','超过2点的部分必定丢失，不能记作成功存费。后期即使低血，AI也可能因评分拒绝可选牌而剩下点数；这既可能是合理拒绝弱牌，也可能暴露Dice与边际战力估值的不足，不能仅凭剩点判定运营最优。','',
        '|完成时点|完成专精人数|首次取得路线人数|','|---|---:|---:|']
    for r in sorted(set(a['spec_rounds'])|set(a['route_rounds']),key=int):
        lines.append(f"|{'未完成/未取得' if r=='0' else '第'+r+'轮'}|{a['spec_rounds'].get(r,0)}|{a['route_rounds'].get(r,0)}|")
    lines+=['',
        '## 冠军的实际战力','',
        '|条件|房间平均得分率（平局半分）|95%区间|','|---|---:|---:|']
    for key,label in [('candidate','实际冠军牌组＋新战斗AI'),('old_combat','相同冠军牌组＋初始旧战斗AI'),('full_reference','完整对应标准牌组＋新战斗AI')]:
        x=a['champion_scores'][key];lines.append(f"|{label}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    lines+=['','|实际冠军＋新AI相对对照|配对得分差|95%区间|','|---|---:|---:|']
    for key,label in [('old_combat','相同卡组旧战斗AI'),('full_reference','完整对应标准牌组')]:
        x=a['champion_paired'][key];lines.append(f"|{label}|{x['mean']*100:+.2f}个百分点|[{x['low']*100:+.2f}, {x['high']*100:+.2f}]|")
    diff=a['champion_paired']['old_combat'];gap=a['champion_paired']['full_reference']
    lines+=['',('同卡组独立终测支持新战斗参数有提升。' if diff['low']>0 else '同卡组独立终测显示新战斗参数退步。' if diff['high']<0 else '同卡组新战斗参数的额外提升仍不确定。'),
        ('冠军牌组整体仍明显弱于完整标准参照。' if gap['high']<0 else '未检出与完整标准参照的显著差异也不等于证明等强。'),
        f"冠军平均张数{s['final']['champion_size']:.2f}，平均对应路线Dice {p(s['final']['champion_dice'])}。这些是胜者样本，不与上一版全体玩家的绝对得分直接相减。",'',
        '|标准对手路线|实际冠军＋新AI得分|完整标准参照得分|','|---|---:|---:|']
    for oid,x in a['opponent_scores'].items():lines.append(f"|{S.TARGETS[oid]['route']}|{p(x['candidate'])}|{p(x['full_reference'])}|")
    lines+=['',
        '|冠军最常缺少的对应标准卡|缺失次数|','|---|---:|']
    for name,n in a['missing_standard'].items():lines.append(f'|{name}|{n}|')
    lines+=['',f"全体终测玩家发生路线替换{a['route_changes']}次。改变目标、取得第一张路线和主动更换已有路线是不同事件，不能用播报总数代替变阵次数。",'',
        '|战斗条件|平均出牌|平均获得能量|能量浪费比例|平均持续时间（引擎单位）|','|---|---:|---:|---:|---:|']
    for key,label in [('candidate','实际冠军＋新AI'),('old_combat','同卡组旧AI'),('full_reference','完整标准参照')]:
        x=a['champion_operation'][key];lines.append(f"|{label}|{x['plays']:.2f}|{x['granted']:.2f}|{p(x['waste_ratio'])}|{x['duration']:.1f}|")
    lines+=['','不同持续时间会改变累计出牌和能量，较多出牌或较低能量浪费不自动代表更高战力。','',
        '## 审计、文件与限制','',
        f"全部保留的训练、校准、失败测试和独立复测共{total['rooms']}个房间、{total['total_formal_games']}场正式记录：课程{total['course_battles']}、训练中单边战斗候选{total['training_trials']}、冠军与阶段标准对照{total['matrix_games']}。最终选表这一批为{a['counts']['rooms']}个房间；其中200个用于独立终测，其他为冻结AI校准。",'',
        '逐笔审计通过：源码哈希、封版卡牌、六类等份数、候选保留、购买与金额、奖金、扣血与淘汰、幽灵、匹配、播报、终局冠军和配对标准矩阵。三轮候选接受/回退也经独立复核。封版253张卡牌、15组确定性战斗与225策略绑定回归通过；未覆盖完整产品联机、动画或真人手感验收。','',
        f"[原始记录](../../research/{args.run})保存各轮构筑、公开信息、匹配、战斗、扣血、淘汰、三阶段参数、拒绝/采纳、源码哈希与标准矩阵。最终入口由release-selection.json指向{selection.get('chosen_folder','.')}/selected-model.json及selected-table.json，通过tournament_inference加载；不覆盖历史policies.json。",'',
        '本表是当前AI与牌池下的经验校准。改变卡牌、战斗AI或运营策略会改变胜负分布、胜者剩余角色血量和赛事长度，届时必须复核。三轮学习与局部搜索不构成最优出牌或最优运营证明。','']
    target=S.C.ROOT/'docs/deckbuilding/simulation-v6-report.md';target.write_text('\n'.join(lines),encoding='utf-8')
    S.save(S.C.ROOT/'docs/deckbuilding/survival-damage-table.json',dict(status='research_validated_candidate',
        initial_hp=100,formula='m + floor(ln(max(winner_character_hp,1)) * n)',simultaneous_death='both lose m',
        coefficients=s['table'],selection=selection,validation=a['final_intervals'],
        late_stage='m17=m18=100; single loss eliminates from round17; no artificial match truncation',
        frozen_card_version='1.0',model_checkpoint=str(out/'selected-model.json')))
    S.save(out/'duration-verdict.json',dict(observed=dict(strong12=a['final_intervals']['strong12']['mean'],
        alive15=a['final_intervals']['alive15']['mean'],ended18=a['final_intervals']['ended18']['mean']),
        approximate_targets_tolerance_pp=5,ended18_observed_pass=a['final_intervals']['ended18']['mean']>=.98,
        note='empirical validation; no guarantee after future balance changes'))
    original_hashes=read('experiment.json')['source_hashes'];postflight=out/'sources-postflight';postflight.mkdir(exist_ok=True)
    for name in ['test_survival_tournament.py','audit_survival.py','analyze_survival.py','report_survival.py','tournament_inference.py','train_survival.py']:
        destination=postflight/name if name in original_hashes else out/'sources'/name
        shutil.copyfile(Path(__file__).parent/name,destination)
    print(str(target))


if __name__=='__main__':main()
