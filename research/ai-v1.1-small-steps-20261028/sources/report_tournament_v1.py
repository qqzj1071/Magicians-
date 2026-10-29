"""Independent final analysis, uncertainty, failed updates and actual reasons."""
import copy
import gzip
import hashlib
import json
import random
import statistics as st
from collections import Counter,defaultdict
from pathlib import Path
import strategic_tournament_ai as I
import survival_tournament as Q
from analyze_survival import interval
S=Q.S


def grouped_scores(rows):
    groups=defaultdict(lambda:defaultdict(list))
    for row in rows:groups[row['condition']][row['room']].append(row['score'])
    means={k:{r:st.mean(v) for r,v in by.items()} for k,by in groups.items()}
    return means


def independent_difference(new,old):
    rng=random.Random(4731);new=list(new);old=list(old)
    draws=sorted(st.mean(rng.choices(new,k=len(new)))-st.mean(rng.choices(old,k=len(old))) for _ in range(3000))
    return dict(mean=st.mean(new)-st.mean(old),low=draws[75],high=draws[2925],new_rooms=len(new),old_rooms=len(old))


def diagnostics(eps):
    players=[];finance=defaultdict(list);routes=[];reason_count=Counter();counter_buys=0;hp_banks=defaultdict(list)
    for ep in eps:
        players+=ep['eliminated']+([] if ep['tied'] else ep['champions'])
        seen=set()
        for row in ep['rounds']:
            r=row['round']
            for p in row['players']:
                if p['route'] and p['pid'] not in seen:routes.append(r);seen.add(p['pid'])
            for ledger in row['ledger']:
                hp=row['hp_before'][str(ledger['pid'])]
                hp_banks['low<=30' if hp<=30 else 'mid31-60' if hp<=60 else 'high>60'].append(ledger['bank'])
                for d in ledger.get('decision_reasons',[]):reason_count[d['kind']]+=1
                counter_buys+=sum(d['kind']=='buy' and d.get('features',{}).get('next_counter',0)>0 for d in ledger.get('decision_reasons',[]))
                finance[str(r)].append(dict(bank=ledger['bank'],wasted=max(0,ledger['remaining']-2),
                    refresh=any(a['kind']=='refresh' for a in ledger['actions']),bonus=ledger['bonus']))
    return dict(spec_mean=st.mean(p['spec_round'] for p in players if p['spec_round']),unspecialized=sum(not p['spec_round'] for p in players),
        route_mean=st.mean(routes) if routes else None,route_observations=len(routes),
        mean_cost=st.mean(p['average_cost'] for p in players),
        mean_size=st.mean(p['size'] for p in players),
        resources={k:st.mean(p['resources'][k] for p in players) for k in ('draw','search','shuffle')},
        route_changes=sum(p['route_changes'] for p in players),
        mean_elements=st.mean(len({p['spec'] for p in e['eliminated']+e['champions'] if p['spec']}) for e in eps),
        reason_counts=dict(reason_count),positive_public_counter_buys=counter_buys,
        bank_by_hp={k:dict(n=len(v),mean=st.mean(v)) for k,v in hp_banks.items()},
        finance={r:{k:st.mean(x[k] for x in xs) for k in ('bank','wasted','refresh','bonus')} for r,xs in finance.items()})


def main():
    out=S.C.ROOT/'research/tournament-v1-training01';read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
    groups=defaultdict(list);counts=Counter()
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            e=json.loads(line);groups[e['label']].append(e);counts['rooms']+=1;counts['course_battles']+=e['battles']
            if e['label'].endswith('-train'):counts['training_battles']+=e['battles']
    final=groups['sealed-final'];baseline=groups['baseline-final'];mixed=groups['mixed-final']
    stats=read('summary.json');history=read('training-history.json');audit=read('audit-v1.json')
    matrix=read('champion-matrix.json')['rows'];by=grouped_scores(matrix)
    champion_scores={k:interval(list(v.values())) for k,v in by.items()}
    paired={k:interval([by['candidate'][r]-by[k][r] for r in by['candidate']]) for k in ('old_combat','full_reference')}
    probe=read('final-combat-probe.json');pb=grouped_scores(probe['rows'])
    combat_gain=interval([pb['new'][r]-pb['old'][r] for r in pb['new']])
    operation={condition:{k:st.mean(x[k] for x in probe['rows'] if x['condition']==condition) for k in ('plays','waste')} for condition in ('new','old')}
    mixed_gain=interval([e['new_champion_share']-e['expected_new_champion_share'] for e in mixed])
    counts['training_counterfactual_games']=counts['training_battles']+2*audit['combat_learning_attempts']
    counts['external_matrix_games']=sum(read(p.name)['games'] for p in out.glob('*-matrix.json'))
    counts['same_deck_probe_games']=sum(len(read(p.name)['rows']) for p in out.glob('*combat-probe.json'))
    base_matrix=grouped_scores(read('baseline-matrix.json')['rows'])
    # Independent group scores, not a paired cause estimate.
    external_change=champion_scores['candidate']['mean']-st.mean(base_matrix['candidate'].values())
    construction_gain=independent_difference(by['old_combat'].values(),base_matrix['candidate'].values())
    newdiag=diagnostics(final);olddiag=diagnostics(baseline)
    result=dict(champion_scores=champion_scores,champion_paired=paired,combat_probe_gain=combat_gain,
        mixed_champion_excess=mixed_gain,independent_champion_score_change=external_change,
        construction_external_difference=construction_gain,
        same_deck_operation=operation,
        baseline_champion_score=st.mean(base_matrix['candidate'].values()),new_diagnostics=newdiag,old_diagnostics=olddiag,
        counts=dict(counts),draft_accepted=sum(h['draft_accepted'] for h in history),
        combat_accepted=sum(h['combat_accepted'] for h in history),audit=audit)
    S.save(out/'analysis.json',result)
    p=lambda x:f'{x:.2%}'
    pp=lambda x:f'{x*100:+.2f}个百分点'
    lines=['# 四人赛事AI：构筑v1.0下十轮学习','',
        '规则已由用户接受冻结；本轮未改卡牌、概率、份数、研习、保底、幽灵与扣血。旧规则及原始实验616文件已压缩校验并标记过时；现行规则入口releases/deckbuilding-v1.0。','',
        f"完成十轮学习，构筑参数{result['draft_accepted']}轮通过验证，战斗参数{result['combat_accepted']}轮通过，其余分别回退。完整赛事{counts['rooms']}房间，构筑后实战{counts['course_battles']}场；学习额外对照{counts['training_counterfactual_games']}场，标准牌组比较{counts['external_matrix_games']}场，同牌组阶段比较{counts['same_deck_probe_games']}场。计数不把试验战当成额外赛事扣血。",'',
        '## 独立终测','',
        '|指标|冻结前AI|训练后AI|','|---|---:|---:|']
    for key,name in [('spec_by5','第5轮前完成专精'),('spec_by6','第6轮前完成专精'),('champion_size','冠军牌数'),('champion_dice','冠军与所选路线标准牌组Dice'),('mean_end','平均结束轮次')]:
        a=stats['baseline'][key];b=stats['final'][key]
        lines.append(f'|{name}|{p(a) if key in ("spec_by5","spec_by6","champion_dice") else f"{a:.2f}"}|{p(b) if key in ("spec_by5","spec_by6","champion_dice") else f"{b:.2f}"}|')
    lines+=['',f"两组各32个独立房间；标签和种子不同，表中差值只是群体描述。新冠军对15套标准牌组双座位平均得分{p(champion_scores['candidate']['mean'])}，旧组冠军{p(result['baseline_champion_score'])}，描述差值{pp(external_change)}。得分中平局计0.5，不与严格胜率混用。",'',
        '|同一批冠军、同牌组对照|平均得分|','|---|---:|']
    for key,name in [('candidate','真实构筑牌组＋新出牌器'),('old_combat','真实构筑牌组＋旧出牌器'),('full_reference','对应完整标准牌组＋新出牌器')]:lines.append(f"|{name}|{p(champion_scores[key]['mean'])}|")
    x=paired['old_combat'];y=combat_gain;z=mixed_gain
    lines+=['',f"相同冠军牌组新旧出牌器差值{pp(x['mean'])}，房间聚类95%区间[{pp(x['low'])}, {pp(x['high'])}]。",'',
        f"旧AI实际中前后期牌组上的新旧出牌器差值{pp(y['mean'])}，95%区间[{pp(y['low'])}, {pp(y['high'])}]。各阶段样本不均，终局存活者存在选择偏差，不能只用冠军比较证明每阶段提升。",'',
        f"同牌组阶段对照每战平均出牌：旧{operation['old']['plays']:.2f}张、新{operation['new']['plays']:.2f}张；资源浪费比例：旧{p(operation['old']['waste'])}、新{p(operation['new']['waste'])}。出牌多或浪费少都只是诊断，仍以战果为准。",'',
        f"24个混合房间中，新AI按1/2/3席轮换；相对席位应有冠军份额的超额为{pp(z['mean'])}，房间聚类95%区间[{pp(z['low'])}, {pp(z['high'])}]。并列冠军平分份额。区间跨0就不能说已证明整体更强，纯自弈胜率不作进步证据。",'',
        f"固定旧出牌器比较两组各32房间冠军的真实构筑牌组，外部得分差值{pp(construction_gain['mean'])}，独立群体重采样95%区间[{pp(construction_gain['low'])}, {pp(construction_gain['high'])}]。这是群体比较，仍混有冠军选择和不同库存历程，不是逐次抓牌的因果证明。",'',
        '## 十轮接受与回退','',
        '|轮次|构筑外部对照变化|构筑更新|同牌组战斗变化|战斗更新|','|---|---:|---|---:|---|']
    for h in history:
        dg=h['benchmark_after']['old_combat']-h['benchmark_before']['old_combat'];cg=h['fixed_probe']['means']['new']-h['fixed_probe']['means']['old']
        lines.append(f"|{h['phase']}|{pp(dg)}|{'接受' if h['draft_accepted'] else '回退'}|{pp(cg)}|{'接受' if h['combat_accepted'] else '回退'}|")
    lines+=['','每轮验证只有4个新房间，更新门槛用于筛除退步，不能视为显著性证明；十次筛选也可能有选择偏差，最后独立终测没有参与继续训练或选参数。','',
        '## 运营与牌组诊断','',
        '|指标|旧AI|新AI|','|---|---:|---:|']
    for key,name in [('spec_mean','平均专精轮次'),('route_mean','首次持有路线平均轮次'),('mean_cost','所有玩家终止时平均卡费'),('mean_size','所有玩家终止时牌数'),('mean_elements','每房间不同专精数'),('route_changes','全部玩家换路线次数')]:
        lines.append(f"|{name}|{olddiag[key]:.2f}|{newdiag[key]:.2f}|")
    lines+=['',f"主系进度、运转资源、费用曲线、存费安全性和公开对手对策均进入估值；新终测中记录{newdiag['positive_public_counter_buys']}次正向公开对策边际购买。这是启发式计数，不是已证明针对有效的次数。",'',
        '|轮次|旧平均继承|新平均继承|新刷新比例|新超出继承上限的浪费|','|---|---:|---:|---:|---:|']
    for r in ('1','2','5','6','8','10','12','14','16','17'):
        if r in newdiag['finance'] and r in olddiag['finance']:
            a=olddiag['finance'][r];b=newdiag['finance'][r]
            lines.append(f"|{r}|{a['bank']:.2f}|{b['bank']:.2f}|{p(b['refresh'])}|{b['wasted']:.2f}|")
    lines+=['','存费与胜率之间不能从相关性判断因果；后期浪费仍需跟踪。连胜败节点参与收益，但尚未形成完整的长期控败规划器。路线被抢后重新选目标的能力保留，反复换路线并非默认好事。','',
        '低/中/高赛事血量的平均继承及观察次数：'+str(newdiag['bank_by_hp'])+'；分组还混有不同轮次与库存，不能直接视为存费策略效果。','',
        '## 决策可解释性与限制','',
        f"构筑记录包含{audit['decision_reasons']}条决策依据；战斗候选更新{audit['combat_learning_attempts']}次，其中胜方{audit['winner_learning']}、败方{audit['loser_learning']}、平局{audit['draw_learning']}次，双方均学习。每次接受须在两洗牌检验中平均收益为正且没有明显单种子退步。",'',
        '这仍是先验引导的启发式及有界在线学习，不是通用推理模型或最优策略证明。能给出特征、替代项与实际战斗阶段依据，不等于每个动作都是全局最优。标准套牌相似度不等于实际战力，冻结规则不等于全部时长目标达标。', '',
        '[训练方法](tournament-v1-method.md) · [关键决策及出牌示例](tournament-v1-decisions.md)。运行器tournament_inference.load_release可读取research/tournament-v1-training01的已锁定检查点；原始冻结前AI保留于releases/deckbuilding-v1.0/initial-ai.json。', '']
    docs=S.C.ROOT/'docs/ai';(docs/'tournament-v1-report.md').write_text('\n'.join(lines),encoding='utf-8')
    # Real inference records and exact deterministic battle traces, not generated stories.
    examples=[];covered=set()
    for ep in final:
        for row in ep['rounds']:
            for ledger in row['ledger']:
                for d in ledger.get('decision_reasons',[]):
                    category=None
                    if d['kind']=='buy':
                        if d.get('features',{}).get('specialization_jump',0)>0:category='specialize'
                        elif S.C.CARDS[d['name']].kind=='route_legendary':category='route'
                        elif d.get('features',{}).get('next_counter',0)>0:category='counter'
                    elif d['kind']=='bank' and d['carried']>0 and row['round'] in (1,5,7):category='bank'
                    elif d['kind']=='skip_refresh' and d['points']>=2:category='skip_refresh'
                    elif d['kind']=='refresh' and row['round'] in (6,8,10,12):category='refresh'
                    if category and category not in covered:
                        covered.add(category);examples.append(dict(category=category,room=ep['index'],pid=ledger['pid'],
                            round=row['round'],hp=row['hp_before'][str(ledger['pid'])],decision=d,
                            replaced=next((a.get('replaced') for a in ledger['actions'] if a['kind']=='buy' and a['name']==d.get('name')),None)))
    S.save(out/'decision-examples.json',examples)
    I.install();model=I.Learner(read('selected-model.json'));traces=[]
    for rr in (6,14):
        found=next((row for e in final for row in e['rounds'] if row['round']==rr and any(not b['ghost'] for b in row['battles'])),None)
        if not found:continue
        battle=next(b for b in found['battles'] if not b['ghost']);byid={p['pid']:p for p in found['players']}
        a='survivor-'+str(battle['a']);b='survivor-'+str(battle['b'])
        Q.deck(byid[battle['a']],a);Q.deck(byid[battle['b']],b)
        result=I.J.E.simulate(a,b,battle['result']['seed'],model.combat.policy(a,b,rr),model.combat.policy(b,a,rr),trace=True,validate=True)
        assert result['winner']==battle['result']['winner'] and result['players']==battle['result']['players']
        traces.append(dict(round=rr,result=result))
    with gzip.open(out/'battle-decision-traces.json.gz','wt',encoding='utf-8') as f:json.dump(traces,f,ensure_ascii=False)
    ex=['# 实际决策示例','', '以下来自冻结后无探索噪声的终测。评分是启发式边际估值，正贡献说明该特征支持选择，不是单卡固有战力。','']
    labels=dict(dice='参考路线匹配',main='主系核心完整度',core='路线确立',progress='专精进度',
        specialization_jump='立即专精与已有附魔增益',effective_layers='有效附魔层数',layer='主系附魔层数',
        draw='过牌补足',search='检索补足',shuffle='洗牌补足',next_counter='下一对手应对',
        coin='研习点支出',bank='继承价值变化',reserve_plan='下一轮购买能力',mana_fit='费用曲线',instant='即时攻防',refresh='搜索预期价值',
        route_epic='路线史诗支持',route_rare='路线稀有支持',quality='面板效率',foreign='异种负担',size='牌组厚度')
    for sample in examples:
        d=sample['decision'];terms=d.get('contributions',{k:model.w.get(k,0)*v for k,v in d.get('features',{}).items()})
        top=sorted(terms.items(),key=lambda x:abs(x[1]),reverse=True)[:5]
        if d['kind']=='buy':
            swap=f"，替换原路线{sample['replaced']}" if sample.get('replaced') else ''
            ex += [f"第{sample['round']}轮，玩家{sample['pid']}购买{d['name']}{swap}，费用{d['cost']}，此前赛事血{d['hp']}、研习点{d['points']}。",'',
                '主要评分贡献：'+'；'.join(f'{labels.get(k,k)}={v:+.3f}' for k,v in top)+'。',
                '可购买替代项：'+'；'.join(f"{x['name']}（分值{x['score']:.3f}，费用{x['cost']}）" for x in d['alternatives'])+'。','']
        elif d['kind']=='bank':
            ex += [f"第{sample['round']}轮，玩家{sample['pid']}保留{d['carried']}研习点，当前赛事血{sample['hp']}；超过继承上限而丢弃{d['discarded']}点。留费估值结合继承上限、已公布下一轮收入及当前可承受战损，不读取下一轮候选。",'']
        else:
            rationale=('主要评分贡献：'+'；'.join(f'{labels.get(k,k)}={v:+.3f}' for k,v in top)+'；判断为'+('搜索预期价值足以覆盖刷新与留费成本。' if d['kind']=='refresh' else '当前搜索收益不足，保留点数。')) if top else '扣除刷新费用后，当前预算不足以支撑目标购买，优先保留点数；没有提前读取第二面卡牌。'
            ex += [f"第{sample['round']}轮，玩家{sample['pid']}{'刷新' if d['kind']=='refresh' else '不刷新'}，现有{d['points']}研习点，赛事血{d['hp']}。",'',
                rationale,'']
    for item in traces:
        ex += [f"## 第{item['round']}轮真实战斗复现",'']
        queues=[x for x in item['result']['log'] if x.get('phase')=='queues'][:3]
        for x in queues:
            for pid,reasons in enumerate(x['reasons']):
                ex.append(f"时刻{x['t']}，战斗方{pid+1}：可用牌{'、'.join(x['pools'][pid])}；选择顺序{'→'.join(x['queues'][pid]) or '留费，不出牌'}。")
                ex.append('')
                for d in reasons:
                    phase={'startup':'启动','operation':'运转','finish':'斩杀'}.get(d.get('phase'),d.get('phase',''))
                    ex.append(f"- {d['card']}：{phase}阶段，边际分{d['score']}，斩杀预演{'命中' if d.get('conditional_lethal') else '未命中'}，{'有紧急生存压力' if d.get('emergency') else '无紧急生存标记'}。")
                ex.append('')
        ex.append('')
    ex+=['完整候选、贡献与关键替代项在原始ledger.decision_reasons；战斗逐步复现位于research/tournament-v1-training01/battle-decision-traces.json.gz，已逐项确认与正式赛事战果相同。','']
    (docs/'tournament-v1-decisions.md').write_text('\n'.join(ex),encoding='utf-8')
    print(json.dumps(dict(status='report_and_exact_traces_written',counts=dict(counts),mixed=mixed_gain,battle_traces=len(traces)),ensure_ascii=False))


if __name__=='__main__':main()
