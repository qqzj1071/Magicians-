import json,hashlib,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/round_robin'))
from report_v11_balance import render,phase_means
folder=ROOT/'research/ai-v1.1-route-pass5-20261027'
r=render(folder)
episodes=[json.loads(s) for s in (folder/'episodes.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(episodes)==1000 and {e['index'] for e in episodes}==set(range(1000))
for e in episodes:
 ps=e['placements'];assert len(ps)==4 and len({p['pid'] for p in ps})==4
 assert abs(sum(p['points'] for p in ps))<1e-9
 assert abs(sum(p['win_share'] for p in ps)-1)<1e-9
 keys=[(p['eliminated_round'] if p['eliminated_round'] is not None else float('inf'),p['tournament_hp']) for p in ps]
 assert keys==sorted(keys,reverse=True)
 for i,p in enumerate(ps):
  tied=[k for k,x in enumerate(keys) if x==keys[i]]
  assert p['points']==sum([3,1,-1,-3][k] for k in tied)/len(tied)
for field,key in [('spec','element_ranking'),('route','route_ranking')]:
 score=Counter();n=Counter();wins=Counter()
 for e in episodes:
  for p in e['placements']:
   if p[field]:score[p[field]]+=p['points'];n[p[field]]+=1;wins[p[field]]+=p['win_share']
 assert len(r[key])==(5 if field=='spec' else 15)
 for x in r[key]:
  name=x['name'];assert (x['score'],x['selections'],x['wins'])==(score[name],n[name],wins[name])
 assert [x['name'] for x in r[key]]==sorted(score,key=lambda name:(-score[name],name))
assert (ROOT/'releases/v1.1/cards.json').read_bytes()==(folder/'cards.snapshot.json').read_bytes()
check=json.loads((folder/'verification.json').read_text(encoding='utf-8'))
check['tournament_audit']={'games':1000,'settlements':4000,'unique_players_per_game':4,'placement_order_valid':True,'points_and_champion_shares_conserved':True,'all_rankings_recomputed_match':True,'snapshot_matches_current_cards':True}
(folder/'verification.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
old=json.loads((ROOT/'research/ai-v1.1-route-pass4-20261027/report.json').read_text(encoding='utf-8'))
lookup={x['name']:x for x in old['route_ranking']}
lines=['','## 本轮变更与上轮对比','','先执行用户指定机制，再微调9张固定攻防面板，并调整生命洪流回复量与不坏壁垒盾量；所有攻防为整数且符合费用归一化价值区间。完整说明见[调整记录](../v1.1-route-pass5-20261027/changes.md)。灰烬循环与灰烬重生仍须实际打出火专精后才能获得余烬。','','本轮沿用上轮1000个赛事种子、AI模型和构筑规则。多项机制和面板同时改变，变化不能单独归因于某张牌。测试结束后未继续改动数值。','','|路线|上轮积分|本轮积分|上轮夺冠率|本轮夺冠率|','|---|---:|---:|---:|---:|']
for x in r['route_ranking']:
 o=lookup[x['name']];lines.append(f"|{x['name']}|{o['score']:+.0f}|{x['score']:+.0f}|{o['win_rate']:.1%}|{x['win_rate']:.1%}|")
lines+=['','|阶段|上轮平均行动值|本轮平均行动值|','|---|---:|---:|']
for (name,a),(_,b) in zip(phase_means(old),phase_means(r)):lines.append(f'|{name}|{a:.1f}|{b:.1f}|')
with (folder/'report.md').open('a',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
p=ROOT/'releases/v1.1/manifest.json';m=json.loads(p.read_text(encoding='utf-8-sig'));m['latest_balance_tests'].update(status='complete',valid_settlements=4000,tested_cards_sha256=check['cards_sha256']);p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\r\n')
print(json.dumps({'elements':r['element_ranking'],'routes':r['route_ranking'],'tempo':phase_means(r),'audit':'passed'},ensure_ascii=False,indent=2))
