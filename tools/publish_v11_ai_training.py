"""Audit completed training, write its report, and select the accepted checkpoint."""
import hashlib,json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN='ai-v1.1-small-steps-20261028-public'
OUT=ROOT/'research'/RUN

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 summary=read(OUT/'summary.json');history=read(OUT/'history.json');rows=read(OUT/'episodes.compact.json')
 assert summary['games']==1000 and len(rows)==1000 and len(history)==10
 assert len({(r['batch'],r['index']) for r in rows})==1000
 for b in range(1,11):assert sum(r['batch']==b for r in rows)==100
 for r in rows:
  assert len(r['placements'])==4 and r['inventory_audited']
  assert abs(sum(p['points'] for p in r['placements']))<1e-8
  assert abs(sum(p['win_share'] for p in r['placements'])-1)<1e-8
 for n,h in read(OUT/'training-source-hashes.json').items():
  assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 for n,h in read(ROOT/'releases/v1.1/freeze-manifest.json')['sha256'].items():
  assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 checkpoint=OUT/'selected-model.json';digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
 assert digest==summary['model_sha256']
 protocol=read(OUT/'protocol.json');old=protocol['initial_pointer'];save(OUT/'previous-pointer.json',old)
 sealed=[r for r in rows if r['split']=='sealed'];values=[r['candidate_points']/2 for r in sealed]
 mean=statistics.mean(values);margin=1.96*statistics.stdev(values)/math.sqrt(len(values))
 lines=['# v1.1 冻结规则下的 AI 小步长训练','',
 '2026-10-28。10批×100场四AI完整赛事，共1000局、4000个玩家结算。卡牌与战斗源码哈希全程不变。', '',
 '延续原检查点；每场两名候选AI与两名上一版AI竞争，并轮换席位。每批80局用于接受/回退，20局封存至全部训练结束。构筑权重步长约2%，战斗参数步长为允许范围的1%；新增灰烬待兑现资源估值权重每次增加0.1。按候选平均排名分为正且夺冠率不低于上一版时接受，否则回退。', '',
 '排名分为第一+3、第二+1、第三−1、第四−3；同名次按所占名次平均分，冠军并列平分夺冠份额。下表百分比为每个玩家席位的夺冠份额。', '',
 '| 批次 | 选择局数 | 候选夺冠率 | 上一版夺冠率 | 候选平均排名分 | 处理 |','|---|---:|---:|---:|---:|---|']
 for h in history:
  s=h['development'];lines.append(f"| {h['batch']} | 80 | {s['candidate_win_rate']:.2%} | {s['baseline_win_rate']:.2%} | {s['candidate_mean_points']:+.4f} | {'接受' if h['accepted'] else '回退'} |")
 s=summary['sealed_cohort']
 lines+=['',f"累计接受{summary['accepted_batches']}次更新。预留200局：候选夺冠率{s['candidate_win_rate']:.2%}，当批上一版{s['baseline_win_rate']:.2%}；候选平均排名分{mean:+.4f}，按独立赛事近似95%区间[{mean-margin:+.4f}, {mean+margin:+.4f}]。",'',
 '这200局比较的是各批候选与各批上一版，并非最终固定模型对最初模型的独立终测，不能据此证明最终AI整体更强。没有使用这些预留结果继续调参，也未额外启动终测。', '',
 '研究版原先会将对手尚未公开的目标元素带入战斗先验；已隔离为公开专精/路线，并验证改变对手私有牌组及未公开目标不会改变策略参数。此前尝试已完成300局后中止，全部标记废弃诊断数据，未用于本次训练、筛选或统计；另有中止中的未完整批次。有效训练从原检查点重启。', '',
 '当前模型：[selected-model.json](selected-model.json)。逐批变化及回退见[history.json](history.json)，训练方法及初始指针见[protocol.json](protocol.json)，全部结算见[episodes.compact.json](episodes.compact.json)，保留的逐轮审计见episodes.jsonl.gz。', '',
 f'模型SHA256：`{digest}`。客户端回归记录另存于工作区runtime/regressions/trained-ai，固定基线为Data/Regression/trained-ai-v1.1-baselines.json。']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 pointer=dict(old,status='v1.1_small_steps_selected',card_version='1.1',model=f'research/{RUN}/selected-model.json',selected_candidate=f'research/{RUN}/selected-model.json',model_sha256=digest,release=f'research/{RUN}',baseline=old['model'],training_cycles=10,training_games=1000,independent_overall_improvement_evidence='uncertain',report=f'research/{RUN}/report.md')
 save(ROOT/'docs/ai/current-tournament.json',pointer)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
 print('V11_AI_SELECTED')
if __name__=='__main__':main()
