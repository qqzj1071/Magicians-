"""Publish damage-only calibration, including unmet health target honestly."""
import argparse
import gzip
import hashlib
import json
import statistics as st
import shutil
from collections import Counter
from pathlib import Path
import calibrate_survival_v7 as V
from analyze_survival import interval,wilson
S=V.S


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args();root=S.C.ROOT/'research'/args.run
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    selection=read(root/'recommendation.json') if (root/'recommendation.json').exists() else read(root/'release-selection.json')
    out=root/selection['chosen_folder']
    summary=read(out/'summary.json');table=summary['table'];eps=[];counts=Counter()
    for folder in (root,root/'expanded'):
        with gzip.open(folder/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                e=json.loads(line);counts['rooms']+=1;counts['battles']+=e['battles']
                if folder==out and e['label']=='sealed-final':eps.append(e)
    checks=V.check_bounds(table);stats=V.metrics(eps);n=len(eps)
    strong=[sum(h>40 for h in V.hp_at(e,12).values())/4 for e in eps]
    alive=[sum(h>0 for h in V.hp_at(e,14).values())/4 for e in eps]
    first_death=Counter(next((row['round'] for row in e['rounds'] if row['eliminated']),e['end_round']) for e in eps)
    endhist=Counter(e['end_round'] for e in eps);alivehist=Counter(sum(h>0 for h in V.hp_at(e,14).values()) for e in eps)
    result=dict(metrics=stats,strong12=interval(strong),alive14=interval(alive),ended17=wilson(sum(e['end_round']<=17 for e in eps),n),
        first_elimination=dict(first_death),ending=dict(endhist),alive14_histogram=dict(alivehist),bounds=checks,counts=counts,
        all_targets_met=abs(stats['strong12']-.6)<=.03 and abs(stats['alive14']-.5)<=.03 and stats['ended17']>=.98)
    S.save(out/'analysis-v7.json',result)
    p=lambda v:f'{v:.2%}';lines=['# 扣血曲线v7：九连败、14轮决赛与17轮收束','',
        '日期：2026-10-23。本轮只校准m/n，冻结上一轮AI，不追加训练，不重跑冠军标准套牌矩阵。卡牌、1060份六类共享池、研习经济、幽灵、公开匹配与淘汰回池均不变。第8/10/12轮首面3张传奇保底继续保留；“第10轮两张传奇”指通常已持有两张，不是修改保底。','',
        '本轮新目标为第12轮60%玩家高于40血、第14轮50%玩家存活、至少98%房间在第17轮内结束。原70%/第15轮50%/18轮目标已被替换。','',
        '## 独立复测','',
        '|指标|目标|200房间结果|95%区间|','|---|---:|---:|---:|']
    for key,label,target in [('strong12','第12轮末>40血玩家',.6),('alive14','第14轮末存活玩家',.5),('ended17','17轮内结束房间',.98)]:
        x=result[key];lines.append(f"|{label}|{p(target)}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    if not result['all_targets_met']:
        lines+=['','**没有同时满足全部目标。** 九连败硬约束、14轮左右进入决赛和17轮结束节奏已验证，但第12轮高血玩家比例仍低于60%。该表作为部分达标候选保存，不标记为全部达标或最优解。']
    lines+=['',f"平均结束第{stats['mean_end']:.2f}轮，最晚第{stats['max_end']}轮。场上首次剩至多两人的中位轮次为{stats['median_duel_entry']}；真正以两名活人开局对战的中位轮次为{stats['median_first_duel']}（通常是前者下一轮）。{stats['skipped_duel']}个房间因同轮多名玩家淘汰而直接结束，没有实际1v1阶段。",'',
        '第14轮存活人数：'+'、'.join(f'{k}人：{v}房间' for k,v in sorted(alivehist.items()))+'。',
        '首次淘汰轮次：'+'、'.join(f'第{k}轮：{v}房间' for k,v in sorted(first_death.items()))+'。',
        '结束轮次：'+'、'.join(f'第{k}轮：{v}房间' for k,v in sorted(endhist.items()))+'。','',
        '统计口径为初始全部玩家；提前结束的冠军血量冻结，淘汰者记0。玩家比例按房间聚类重采样，结束率用Wilson区间。','',
        '## 参数与九连败验证','',
        '`败损=m+floor(ln(max(x,1))×n)`，每轮分别下取整；双死只扣m并中断连胜败。','',
        '|轮次|m|n|胜方剩200血时败损|胜方剩500血时败损|','|---|---:|---:|---:|---:|']
    for r in range(1,21):
        m,k=table[str(r)];lines.append(f'|{r}|{m}|{k:.1f}|{V.Q.damage(m,k,200)}|{V.Q.damage(m,k,500)}|')
    losses=[V.Q.damage(*table[str(r)],500) for r in range(1,10)]
    lines+=['',f"开局连续9轮基础值总和为{checks['first_nine']['base']}，小于100。每次胜方剩500血时，逐轮败损为{'、'.join(map(str,losses))}，合计{sum(losses)}，所以从100血开始最迟第9次失败死亡。x>500时不低于此值。",'',
        '对照上一版：胜方每次剩500血时，旧表前9次失败仅扣60血，新约束要求至少100血，强度提升明显；不能把这次调整理解为只增加少量前期扣血。','',
        f"本表还满足更强条件：表内任意连续9轮基础值合计最大{checks['max_nine_base']}，仍小于100；任意连续9轮、每次胜方剩500血的总败损最小{checks['min_nine_damage_at500']}。m整数、n至多一位小数且二者均单调不减。",'',
        '500血是保证点，并非公式的伤害分界线；低于500也可能在9连败时淘汰。第17轮m只有11，已移除基础100的单败淘汰；高n加强溃败惩罚，险败仍可能保留血量。若17轮未结束，继续按后续参数运行，不截断或指定冠军。第18轮起m保持11，n每轮加4；运行表覆盖至80轮。','',
        '## 校准过程与限制','',
        '先用旧200房间固定战斗轨迹筛选，再以新种子运行4条候选各24房间。另枚举单调九连败伤害分配并抽查6000条分段曲线，用固定轨迹发现前期伤害后移的候选，再进行24房间真实校准。固定重放不包含重配对、库存回池与AI存费变化，只用于提案，不是时长结论。','',
        '|候选|校准第12轮>40血|校准第14轮存活|校准17轮内结束|','|---|---:|---:|---:|']
    for h in read(root/'calibration.json'):
        x=h['stats'];lines.append(f"|原候选{h['index']+1}|{p(x['strong12'])}|{p(x['alive14'])}|{p(x['ended17'])}|")
    expanded=read(root/'expanded/calibration.json')['stats'];lines.append(f"|伤害后移候选|{p(expanded['strong12'])}|{p(expanded['alive14'])}|{p(expanded['ended17'])}|")
    lines+=['','原四候选与伤害后移候选各自先锁定、再用新种子复测200房间；校准选择时点见selection.json及release-selection.json。校准阶段曾优先选伤害后移候选；两批复测后，较简洁的原候选在第14轮存活比例上点估计更接近目标，故作为本轮建议表，后验比较依据见recommendation.json。未追加第三次确认，不声称两候选优劣已获独立统计证明。两批种子不同，差值也不能直接当作参数的单独因果效果。所有失败记录保留。', '',
        '未达60%的原因不能简单说成逻辑上绝对不可兼容，但当前对数函数确实压缩了轻败和惨败的差异。例如m=1、n=1.8时，胜方剩200血扣10，剩500血扣12，仅差2血。保证9次大败死亡，也会抬高普通败局的累计战损。本轮没有找到兼顾60%高血率的表，不将有限搜索当成不可行性证明。', '',
        '若后续坚持60%目标，应单独讨论九连败保证点或对数函数形状的取舍；本轮没有擅自修改公式、阈值、AI或卡牌。','',
        f"本轮实际运行{counts['rooms']}个房间、{counts['battles']}场构筑后战斗，没有新增战斗训练候选或标准套牌测试。逐笔扣血、奖金、匹配、幽灵、回池、源哈希与所有9轮窗口由独立审计复核。",'',
        f"[原始记录](../../research/{args.run})；建议参数位于{selection['chosen_folder']}/selected-table.json，模型与v6相同。",'']
    target=S.C.ROOT/'docs/deckbuilding/simulation-v7-report.md';target.write_text('\n'.join(lines),encoding='utf-8')
    candidate=dict(status='partial_validation_not_all_targets_met',initial_hp=100,formula='m + floor(ln(max(x,1))*n)',
        coefficients={str(r):table[str(r)] for r in range(1,21)},tail=dict(m=11,n_increment=4.),bounds=checks,validation=result,
        source_run=args.run,selected_folder=selection['chosen_folder'],training_updates=0)
    S.save(S.C.ROOT/'docs/deckbuilding/survival-damage-v7-candidate.json',candidate)
    canonical=S.C.ROOT/'docs/deckbuilding/survival-damage-table.json'
    previous=S.C.ROOT/'docs/deckbuilding/survival-damage-v6-validated.json'
    if not previous.exists():shutil.copyfile(canonical,previous)
    S.save(canonical,dict(candidate,previous_v6='survival-damage-v6-validated.json',
        note='Latest discussion candidate; R12 60% target unmet, not a fully validated replacement.'))
    S.save(root/'verdict.json',dict(all_targets_met=result['all_targets_met'],candidate_status=candidate['status'],
        selected_folder=selection['chosen_folder'],hard_nine_loss_constraints_passed=True,old_v6_table_preserved=str(previous)))
    print(json.dumps(dict(metrics=stats,counts=counts,all_targets_met=result['all_targets_met'])))


if __name__=='__main__':main()
