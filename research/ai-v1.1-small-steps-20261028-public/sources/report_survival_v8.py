"""Record quick staged calibration without claiming population guarantees."""
import gzip
import hashlib
import json
from collections import Counter
import calibrate_survival_v7 as V
from analyze_survival import interval,wilson
S=V.S


def main():
    out=S.C.ROOT/'research/shared-draft-v8-stages01'
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    summary=read(out/'summary.json');stats=summary['final'];table=summary['table']
    eps=[];counts=Counter()
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line);counts['rooms']+=1;counts['battles']+=ep['battles']
            if ep['label']=='sealed-final':eps.append(ep)
    analysis=dict(metrics=stats,bounds=V.check_bounds(table),counts=dict(counts),
        strong12=interval([sum(h>40 for h in V.hp_at(e,12).values())/4 for e in eps]),
        alive14=interval([sum(h>0 for h in V.hp_at(e,14).values())/4 for e in eps]),
        ended17=wilson(sum(e['end_round']<=17 for e in eps),len(eps)),all_targets_met=False)
    S.save(out/'analysis.json',analysis)
    candidate=dict(status='small_sample_candidate_not_all_targets_met',initial_hp=100,
        formula='m + floor(ln(max(x,1))*n)',coefficients={str(r):table[str(r)] for r in range(1,21)},
        tail=dict(from_round=17,m=11,n=6.0,mode='constant'),validation=analysis,
        source_run=out.name,training_updates=0,note='40 independent rooms only; not proof of 98% population completion rate')
    S.save(S.C.ROOT/'docs/deckbuilding/survival-damage-v8-candidate.json',candidate)
    S.save(S.C.ROOT/'docs/deckbuilding/survival-damage-table.json',candidate)
    S.save(out/'release-selection.json',dict(chosen_folder='.',
        model_sha256=hashlib.sha256((out/'selected-model.json').read_bytes()).hexdigest(),
        table_sha256=hashlib.sha256((out/'selected-table.json').read_bytes()).hexdigest()))
    p=lambda x:f'{x:.2%}'
    lines=['# 扣血曲线v8：六阶段快速复测','',
        '日期：2026-10-23。按用户指定分为1—4、5—8、9—12、13—14、15—16、17以后六档；m、n单调不减，n限0.8—6.0，17以后固定不再增长。九连败规则、100赛事血与对数公式保持。','',
        '本轮只调整扣血表。冻结上一轮构筑和战斗AI，共享池、六类份数、研习经济、公开播报、幽灵、淘汰回池、8/10/12首面3传奇保底均不变；不追加AI学习或冠军标准套牌矩阵。','',
        '## 参数','',
        '|轮次|m|n|胜方剩200血时败损|胜方剩500血时败损|','|---|---:|---:|---:|---:|']
    for label,r in [('1—4',1),('5—8',5),('9—12',9),('13—14',13),('15—16',15),('17以后',17)]:
        m,n=table[str(r)];lines.append(f'|{label}|{m}|{n:.1f}|{V.Q.damage(m,n,200)}|{V.Q.damage(m,n,500)}|')
    b=analysis['bounds'];lines+=['',f"开局9轮基础合计{b['first_nine']['base']}<100；胜方每次剩500血时，9次累计败损{b['first_nine']['damage_at500']}≥100。表内任意连续9轮基础合计最大{b['max_nine_base']}，500血败损最小{b['min_nine_damage_at500']}；17轮以后参数恒定，故该约束也延续到表外。双死仍只扣m。",'',
        '## 独立复测','',
        '|指标|目标|40房间结果|95%区间|','|---|---:|---:|---:|']
    for key,name,target in [('strong12','第12轮末>40血玩家',.6),('alive14','第14轮末存活玩家',.5),('ended17','17轮内结束房间',.98)]:
        x=analysis[key];lines.append(f"|{name}|{p(target)}|{p(x['mean'])}|{p(x['low'])}—{p(x['high'])}|")
    lines+=['',f"平均第{stats['mean_end']:.2f}轮结束，最晚第{stats['max_end']}轮；首次剩至多两人的中位轮次为{stats['median_duel_entry']}，实际两名活人开局对战中位轮次为{stats['median_first_duel']}。",'',
        '结束分布：'+'、'.join(f'第{k}轮{v}房间' for k,v in sorted(stats['end_histogram'].items(),key=lambda x:int(x[0])))+'。','',
        '**未全部达标。** 样本较少，本轮用于快速检查阶段节奏，不能据此证明总体98%的房间17轮内结束。第12轮高血率不足仍保留为未解决问题，不因采用分档表而修改目标。','',
        '## 选择过程','',
        '3条候选各8房间校准，使用相同命名种子；按与12轮60%、14轮50%的偏差及17轮结束不足选定一条，然后用独立新种子复测40房间。只做这一轮筛选，不根据终测结果再换表。','',
        '|候选|1—4轮m/n|5—8轮m/n|9—12轮m/n|校准高血率|校准14轮存活|校准17轮结束|','|---|---|---|---|---:|---:|---:|']
    for c in read(out/'calibration.json'):
        t=c['table'];x=c['stats'];lines.append(f"|{c['index']+1}|{t['1']}|{t['5']}|{t['9']}|{p(x['strong12'])}|{p(x['alive14'])}|{p(x['ended17'])}|")
    chosen=read(out/'selection.json')['chosen']+1
    lines+=['',f"选中候选{chosen}。本轮合计{counts['rooms']}房间、{counts['battles']}场构筑后实战，训练更新0次。完整逐轮记录在research/{out.name}；扣血、奖金、配对、库存及公开信息由audit_survival.py独立回放。",'',
        '相比v7，主要变化为阶段交界更明确、晚期n从24及继续增长降至最高6；前中期也重新分配扣血。两次终测种子和样本量不同，不将百分比差值当作单独因果效果。旧v7完整记录保留。','']
    (S.C.ROOT/'docs/deckbuilding/simulation-v8-report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(selected=chosen,stats=stats,counts=dict(counts)),ensure_ascii=False))


if __name__=='__main__':main()
