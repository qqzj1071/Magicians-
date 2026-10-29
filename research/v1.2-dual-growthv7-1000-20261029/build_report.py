"""Audit the exact 1000-room budget and report the sealed two-family test."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,math,sys,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,START_ONLY
from tools.sim_v12.panel_budget import role,value
from tools.sim_v12.tournament import arena_loss,base_income
from tools.sim_v12.quick_test import pct,number

def load(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def save(n,d):(OUT/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(n,rows):(OUT/n).write_text('\n'.join(rows)+'\n',encoding='utf-8')
def interval(xs):
 mean=sum(xs)/max(1,len(xs));se=math.sqrt(sum((x-mean)**2 for x in xs)/max(1,len(xs)-1)/max(1,len(xs)))
 return dict(mean=mean,low=mean-1.96*se,high=mean+1.96*se,rooms=len(xs))

def main():
 t=load('training.json');inputs=load('inputs.json');e=t['evaluation'];stats={f:load(f'{f}-final-statistics.json') for f in ('medium','small')}
 initial=load('initial-policies.json')
 for family in ('medium','small'):
  source=ROOT/inputs['resumed_from']/f'{family}-final-policy.json'
  original=json.loads(source.read_text(encoding='utf-8'))
  assert {k:v for k,v in initial[family].items() if k!='checkpoint'}=={k:v for k,v in original.items() if k!='checkpoint'}
  assert hashlib.sha256(source.read_bytes()).hexdigest()==inputs['initial_model_sha256'][str(source.relative_to(ROOT))]
 old=OUT/'report.md'
 if old.exists() and old.read_text(encoding='utf-8').startswith('# v1.2 快速卡牌测试'):
  text=old.read_text(encoding='utf-8').replace('# v1.2 快速卡牌测试','# 1000局混合训练分布',1)
  text=text.replace('本轮没有训练 AI 或改动平衡数值。','本文件混合多个训练检查点和验证对手，不能当作最终候选独立成绩；未改动平衡数值。')
  (OUT/'training-distribution.md').write_text(text,encoding='utf-8')
 final=[];owners=Counter();segments=Counter();seeds=[];battle_count=0;ledgers=0
 for path in sorted(OUT.rglob('room-*.json.gz')):
  with gzip.open(path,'rt',encoding='utf-8') as h:r=json.load(h)
  seeds.append(r['seed']);owner=r['comparison']['budget_owner'];seg=r['comparison']['segment']
  owners[owner]+=1;segments[(owner,seg)]+=1
  assert len(r['placements'])==4 and abs(sum(p['score'] for p in r['placements']))<1e-9
  assert r['pool_total']==707
  for rd in r['rounds']:
   for row in rd['ledger']:
    ledgers+=1;assert row['base_income']==base_income(rd['round'])
    assert row['income']==row['base_income']+row['carry']+row['bonus']
    assert row['income']-sum(x['cost'] for x in row['actions'])==row['remaining']
    assert 0<=row['bank']<=2 and len(row['deck'])>=8
    assert not {x['name'] for x in row['actions'] if x['kind']=='buy'}&START_ONLY
    assert set(row['deck'])<=CARDS.keys()
   for b in rd['battles']:
    battle_count+=1;assert b['combat_rule']=='strict_pre_position_v2' and not b['sequence_skips']
  if seg=='final-holdout':final.append(r)
 assert sorted(seeds)==list(range(inputs['seeds'][0],inputs['seeds'][1]+1)) and len(set(seeds))==1000
 assert owners==dict(medium=500,small=500)
 for f in owners:
  for seg,n in (('train',300),('validation',100),('final-holdout',100)):assert segments[(f,seg)]==n
 assert battle_count==t['battles'] and len(final)==200 and t['input_hashes_verified']
 save('run-audit.json',dict(games=1000,battles=battle_count,ledgers=ledgers,unique_seeds=1000,budgets=dict(owners),
  segments={f'{f}/{s}':n for (f,s),n in segments.items()},sequence_skips=0,income_bank_debit_passed=True,
  starter_purchase_violations=0,pool_total=707,input_hashes_verified=True))
 head=Counter();head_cells=[];bands=defaultdict(Counter);band_rooms=defaultdict(list)
 goal_sizes=defaultdict(Counter);early_deletions=defaultdict(Counter)
 hp_check=defaultdict(list);mix=defaultdict(Counter);same=defaultdict(Counter)
 for r in final:
  first=set(r['comparison']['first_seats']);current_hp={p['pid']:100 for p in r['placements']}
  cell=Counter();perband=defaultdict(Counter)
  for p in r['placements']:
   f='medium' if p['pid'] in first else 'small';mix[f]['players']+=1
   n=len(p['deck'])
   goal_sizes[f]['players']+=1
   goal_sizes[f]['below12']+=n<12;goal_sizes[f]['within12to14']+=12<=n<=14;goal_sizes[f]['above14']+=n>14
   for name in p['deck']:
    mix[f][role(name)]+=1/n;mix[f]['mean_V_sum']+=float(value(CARDS[name].cost,CARDS[name].attack,CARDS[name].defense))/n
   for name in set(p['deck']):same[f][name]+=CARDS[name].element==p['spec']
  for rd in r['rounds']:
   rn=rd['round'];band='1—4' if rn<=4 else '5—8' if rn<=8 else '9—10' if rn<=10 else '11—12' if rn<=12 else '13+'
   if 4<=rn<=6:
    for row in rd['ledger']:
     f='medium' if row['pid'] in first else 'small'
     for action in row['actions']:
      if action['kind']=='delete':
       assert action['cost']==1
       early_deletions[f]['count']+=1;early_deletions[f]['spent']+=action['cost']
   for b in rd['battles']:
    ps=b['participants'];direct=not b['ghost'] and ((ps[0]['pid'] in first)!=(ps[1]['pid'] in first))
    if direct:
     med=0 if ps[0]['pid'] in first else 1
     win=.5 if b['winner'] is None else b['winner']==med
     cell['battles']+=1;cell['wins']+=win;cell['draws']+=b['winner'] is None
     bands[band]['battles']+=1;bands[band]['wins']+=win;perband[band]['n']+=1;perband[band]['wins']+=win
    for i,p in enumerate(ps):
     if i==1 and b['ghost']:continue
     current_hp[p['pid']]-=arena_loss(rn,b['hp'][1-i],won=b['winner']==i,draw=b['winner'] is None)
   if rn in (8,10,12):
    for p in r['placements']:
     f='medium' if p['pid'] in first else 'small'
     hp_check[(f,rn)].append(current_hp[p['pid']])
  assert all(current_hp[p['pid']]==p['hp'] for p in r['placements'])
  head.update(cell)
  if cell['battles']:head_cells.append(cell['wins']/cell['battles'])
  for band,c in perband.items():band_rooms[band].append(c['wins']/c['n'])
 head_result=dict(**head,medium_win_rate=head['wins']/head['battles'],small_win_rate=1-head['wins']/head['battles'],room_interval=interval(head_cells))
 save('head-to-head.json',head_result)
 band_result={b:dict(**c,medium_win_rate=c['wins']/c['battles'],room_interval=interval(band_rooms[b])) for b,c in bands.items()}
 hp_result=[]
 for (f,rn),xs in sorted(hp_check.items()):
  alive=[x for x in xs if x>0];low=sum(0<x<=20 for x in xs)
  hp_result.append(dict(family=f,round=rn,initial_players_in_rooms=len(xs),alive=len(alive),eliminated=sum(x<=0 for x in xs),
   alive_mean_hp=sum(alive)/max(1,len(alive)),alive_at_1_to_20=low,low_fraction_of_alive=low/max(1,len(alive))))
 save('round-analysis.json',dict(bands=band_result,health=hp_result,caveat='Only rooms reaching the checkpoint; includes earlier eliminations in that room, excludes ghosts. Later rounds have survivor bias.'))
 mix_result={f:{k:v/m['players'] for k,v in m.items() if k!='players'} for f,m in mix.items()};save('final-role-mix.json',mix_result)
 goal_result={f:dict(v,fraction12to14=v['within12to14']/v['players'],early_deletions_per_player=early_deletions[f]['count']/v['players']) for f,v in goal_sizes.items()}
 save('deck-size-goal.json',goal_result)
 a,b=e['medium'],e['small'];ad,bd=e['medium_decks'],e['small_decks'];aa,ba=e['medium_actions'],e['small_actions'];ci=e['paired_win']
 lines=['# v1.2 growth-v7／1200疲劳／成长V7：两类AI续训对照','',
  f"完成1000/1000局，{t['battles']:,}场战斗，零跳过。两类各500局预算，均完成5轮独立训练。均卡组最终{t['candidates']['medium']['checkpoint']}，小卡组最终{t['candidates']['small']['checkpoint']}。",'',
  '## 最终冻结对照','',
  f"预留的200局跨风格终测中，两类实际直接交手{head['battles']}场。均卡组胜率{pct(head_result['medium_win_rate'])}，小卡组{pct(head_result['small_win_rate'])}；均卡组按完整赛事聚类的胜率95%区间[{pct(head_result['room_interval']['low'])}, {pct(head_result['room_interval']['high'])}]。",'',
  f"预先指定的赛事内整体战斗胜率差（均卡减小卡）为{pct(ci['mean'])}，95%区间[{pct(ci['low'])}, {pct(ci['high'])}]。{'支持均卡策略胜率更高。' if ci['low']>0 else '支持小卡策略胜率更高。' if ci['high']<0 else '区间跨0，尚不足以认定一种策略更强。'}",'',
  '|指标|均卡组倾向AI|小卡组倾向AI|','|---|---:|---:|',
  f"|整体战斗胜率|{pct(a['win_rate'])}|{pct(b['win_rate'])}|",
  f"|直接交手胜率|{pct(head_result['medium_win_rate'])}|{pct(head_result['small_win_rate'])}|",
  f"|夺冠率|{pct(a['championship_rate'])}|{pct(b['championship_rate'])}|",
  f"|人均排名分|{number(a['mean_score'])}|{number(b['mean_score'])}|",
  f"|终局平均张数|{ad['mean_size']:.2f}|{bd['mean_size']:.2f}|",
  f"|终局中位数|{ad['median']}|{bd['median']}|",
  f"|终局12—14张比例|{pct(goal_result['medium']['fraction12to14'])}|{pct(goal_result['small']['fraction12to14'])}|",
  f"|人均第4—6轮付费删牌|{goal_result['medium']['early_deletions_per_player']:.2f}|{goal_result['small']['early_deletions_per_player']:.2f}|",
  f"|人均购买|{aa['purchases_per_player']:.2f}|{ba['purchases_per_player']:.2f}|",
  f"|人均删除|{aa['deletions_per_player']:.2f}|{ba['deletions_per_player']:.2f}|",
  f"|人均付费删除|{aa['paid_deletions_per_player']:.2f}|{ba['paid_deletions_per_player']:.2f}|",
  f"|数值档牌占比|{pct(mix_result['medium']['numeric'])}|{pct(mix_result['small']['numeric'])}|",
  f"|强运转档占比|{pct(mix_result['medium']['strong'])}|{pct(mix_result['small']['strong'])}|",
  f"|弱运转档占比|{pct(mix_result['medium']['weak'])}|{pct(mix_result['small']['weak'])}|",
  f"|每场平均出牌|{number(a['plays_per_battle'])}|{number(b['plays_per_battle'])}|",
  f"|每场即时抽牌|{number(a['instant_draw_per_battle'])}|{number(b['instant_draw_per_battle'])}|",
  f"|获胜平均行动值|{number(a['winner_time'])}|{number(b['winner_time'])}|",'',
  f"平局计半胜；直接交手排除同策略内战和幽灵。两类每局各2名玩家，随机座位，共享有限卡池，所以整体战斗胜率不必互补。直接交手汇总按场数加权，区间对应等权赛事平均胜率{pct(head_result['room_interval']['mean'])}；二者权重不同。区间使用赛事为单位，避免把同一局多场战斗当成互相独立样本。", '',
  '## 是否形成前期压制与后期翻盘','',
  '|赛事轮次|直接交手场数|均卡组胜率|小卡组胜率|均卡组赛事聚类95%区间|','|---|---:|---:|---:|---|']
 for band in ('1—4','5—8','9—10','11—12','13+'):
  c=band_result.get(band)
  if not c:continue
  z=c['room_interval'];lines.append(f"|{band}|{c['battles']}|{pct(c['medium_win_rate'])}|{pct(1-c['medium_win_rate'])}|[{pct(z['low'])},{pct(z['high'])}]|")
 lines+=['','第13轮及以后受存活者选择影响，不代表固定卡组在该轮必然变强/弱；分轮次结果为描述性分析，不能对多个区间反复挑显著结果。','',
  '|类型|轮次|对应房间初始人次|仍存活|已淘汰|存活平均赛事血量|存活且1—20血|占存活者比例|','|---|---:|---:|---:|---:|---:|---:|---:|']
 for row in hp_result:lines.append(f"|{'均卡组' if row['family']=='medium' else '小卡组'}|{row['round']}|{row['initial_players_in_rooms']}|{row['alive']}|{row['eliminated']}|{row['alive_mean_hp']:.2f}|{row['alive_at_1_to_20']}|{pct(row['low_fraction_of_alive'])}|")
 lines+=['','只统计实际走到第8/10/12轮的房间，较早淘汰者计入“已淘汰”；不是把已淘汰者算成低血存活。此处使用新规则的真实赛事血量，不是旧日志静态重算。20血不严格等于下一场必淘汰。','',
  '## 分元素及路线','',
  '|元素|均/小人数|均/小平均张数|均/小战斗胜率|均/小夺冠率|均/小人均分|','|---|---:|---:|---:|---:|---:|']
 labels={'fire':'火','water':'水','earth':'土','wind':'风','poison':'毒'}
 for el in ELEMENTS:
  x,y=stats['medium']['elements'][el],stats['small']['elements'][el]
  lines.append(f"|{labels[el]}|{x['players']}/{y['players']}|{ad['elements'][el]['mean_size']:.2f}/{bd['elements'][el]['mean_size']:.2f}|{pct(x['win_rate'])}/{pct(y['win_rate'])}|{pct(x['championship_rate'])}/{pct(y['championship_rate'])}|{number(x['mean_score'])}/{number(y['mean_score'])}|")
 lines+=['','|路线|均/小最终人数|均/小战斗胜率|均/小夺冠率|','|---|---:|---:|---:|']
 for name in stats['medium']['routes']:
  x,y=stats['medium']['routes'][name],stats['small']['routes'][name]
  lines.append(f"|{name}|{x['players']}/{y['players']}{'（含小样本）' if min(x['players'],y['players'])<30 else ''}|{pct(x['win_rate'])}/{pct(y['win_rate'])}|{pct(x['championship_rate'])}/{pct(y['championship_rate'])}|")
 lines+=['','最终人数按终局仍持有的路线统计，战斗按当场实际路线统计，换路线可能造成最终人数为0但有战斗记录；元素/路线结果受配对、存活和风格影响，并非各元素互为匹配的因果对照。','',
  '## 训练与防过拟合','',
  '每类5轮、每轮100局预算：60训练、20新种子验证、20预留终测。各类合计300训练、100验证、100评估配额；总计600训练、200验证、200终测，1000局唯一种子295000—295999。最后200局是两类同时参赛的交叉测试，不能重复算成400局；每类预算的100是终测房间的归属，不表示其仅参与100次终测。',
  '两类各自候选对本类当前检查点，训练与验证均不读取另一类封存表现。训练胜率差非负且验证至少+0.5个百分点才接受；目标仅战斗胜率，不奖励牌组长度、出牌数或快速斩杀。均卡与小卡构筑、战斗13项机制权重分别优化，元素微调保持初始化值，避免样本不足时逐元素追涨杀跌。',
  '构筑步长上限10%、战斗6%，新增功能倾向每次3%且围绕初始值限幅；均卡保留约15张软倾向、少付费删牌并偏好数值档，小卡保留无目标长度及循环倾向。不是强制牌组张数或运转占比。数值档包含伤害、盾和战斗成长机制，不等于纯白板。无role_preferences的旧AI路径保持原行为。',
  '当前189张、707份、强V70%/弱V90%、五张指定3费成长V7（深渊不变）、growth-v7经济、1200疲劳、前8轮扣血3/1和5/2全程冻结。第4—6轮删牌每次1点，第7起0/1；第8轮起每轮4研习点。旧版本训练只作为初始化权重，未将旧战绩当新规则对照。最终双方检查点在200局开始前冻结；没有用终测重调或改选模型。默认fixed-legacy不替换，因为本轮只比较两类新候选，不是对默认AI的部署评测。','',
  '|类型|轮|接受更新|检查点|训练胜率差|验证胜率差|','|---|---:|---|---|---:|---:|']
 for f in ('medium','small'):
  for row in t['batches'][f]:lines.append(f"|{f}|{row['round']}|{row['accepted']}|{row['selected']}|{pct(row['train']['mean'])}|{pct(row['validation']['mean'])}|")
 lines+=['','## 检查与限制','',
  '55项预检通过，覆盖全牌执行、功能V预算、新扣血边界、无目标构筑、功能倾向和初始化。全1000局预算、初始牌不入池、707库存、研习继承与收支、零失效跳过、严格结算和输入哈希检查通过。无卡牌或游戏规则改动。v1.1冻结核验另行记录。',
  '每类只有5轮、300局实际用于梯度，不足以证明全局最优。两类战斗与构筑都学习，因此胜率差不能单独归因于牌组张数；前期优势、后期优势和赛事血量必须联合观察。小样本路线不据此直接删牌或改平衡。','',
  '逐卡完整对比见[final-cards.md](final-cards.md)；两类模型分别为medium-final-policy.json、small-final-policy.json。1000局混合分布见[training-distribution.md](training-distribution.md)及[cards.md](cards.md)，不可与最终模型独立终测混用。']
 write('report.md',lines)
 cards=['# 最终冻结两类AI：189张卡牌携带与使用','',
  '各400名终测玩家。携带=终局仍持有；使用率=持有该牌参战时至少打出一次的战斗比例；平均次数=施放总数/持牌参战次数。能力牌只需激活一次，低重复次数不代表无效。初始和专精不入池。','',
  '|卡牌|功能档|均/小携带人数|均/小携带率|均/小曾携带率|均/小携带得分率|均/小携带夺冠率|均/小参战使用率|均/小平均施放次数|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
 mb={x['name']:x for x in stats['medium']['cards']};sb={x['name']:x for x in stats['small']['cards']}
 for name,c in CARDS.items():
  x,y=mb[name],sb[name]
  cards.append(f"|{name}|{role(name)}|{x['players']}/{y['players']}|{pct(x['carry_rate'])}/{pct(y['carry_rate'])}|{pct(x['ever_carry_rate'])}/{pct(y['ever_carry_rate'])}|{pct(x['score_rate'])}/{pct(y['score_rate'])}|{pct(x['championship_rate'])}/{pct(y['championship_rate'])}|{pct(x['usage_rate'])}/{pct(y['usage_rate'])}|{number(x['casts_per_carried_battle'])}/{number(y['casts_per_carried_battle'])}|")
 write('final-cards.md',cards)
 conclusions=['## 结果解读','',
  f"本轮从上次两类最终模型继续训练，使用独立新种子与当前全部规则；旧模型文件哈希和来源已记录，未把旧战绩当本次对照。最终直接交手均卡{pct(head_result['medium_win_rate'])}、小卡{pct(head_result['small_win_rate'])}，预先指定的整体胜率差区间[{pct(ci['low'])},{pct(ci['high'])}]。",
  f"终局均卡{ad['mean_size']:.2f}张、小卡{bd['mean_size']:.2f}张；付费删除{aa['paid_deletions_per_player']:.2f}/{ba['paid_deletions_per_player']:.2f}次。牌组大小是软倾向运行结果，不保证两类都处在12—14张，实际达标比例另列。",
  f"数值档占比均卡{pct(mix_result['medium']['numeric'])}、小卡{pct(mix_result['small']['numeric'])}。两类同时学习构筑和战斗，因此胜率差不能单独归因于张数或数值牌比例。",
  '本次更改了研习点、疲劳起点、前期删牌收费、即时战力面板及五张永久叠加牌面板，而且继续了AI训练；新旧报告不是逐项规则消融，不能把前后差异归功于任意单独改动。',
  '前后期胜率、低血比例与元素/路线表用于诊断；小样本或存活者偏差不能据此直接触发删牌或平衡修改。终测结果未被用于继续调参或重选检查点。','']
 text=(OUT/'report.md').read_text(encoding='utf-8').replace('## 最终冻结对照','\n'.join(conclusions)+'\n## 最终冻结对照',1)
 (OUT/'report.md').write_text(text,encoding='utf-8')
 print(json.dumps(dict(games=1000,battles=battle_count,head=head_result,health=hp_result,role_mix=mix_result),ensure_ascii=False))

if __name__=='__main__':main()
