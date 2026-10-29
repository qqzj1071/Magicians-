"""Report the frozen 200-room construction comparison; never retune on it."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,sys
import math
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,ELEMENTS,START_ONLY
from tools.sim_v12.tournament import base_income
from tools.sim_v12.thin_train import deck_metrics
from tools.sim_v12.quick_test import pct,number
from tools.sim_v12.cohort import selected_statistics

def load(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def write(n,lines):(OUT/n).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
 t=load('training.json');s=load('final-selected-statistics.json');e=t['evaluation'];a=e['selected'];b=e['control'];ci=e['paired_win']
 existing=OUT/'report.md'
 if existing.exists() and existing.read_text(encoding='utf-8').startswith('# v1.2 快速卡牌测试'):
  (OUT/'training-distribution.md').write_text(existing.read_text(encoding='utf-8').replace('# v1.2 快速卡牌测试','# 500局混合训练分布',1).replace('本轮没有训练 AI 或改动平衡数值。','本文件混合训练策略与对照，不能当作冻结最终模型成绩；规则与数值未改。'),encoding='utf-8')
 final=[];counts=Counter();seeds=[];battles=0;ledgers=0
 for path in sorted((OUT/'batches').glob('*/room-*.json.gz')):
  with gzip.open(path,'rt',encoding='utf-8') as h:r=json.load(h)
  seeds.append(r['seed']);counts[r['comparison']['segment']]+=1
  assert len(r['placements'])==4 and {p['pid'] for p in r['placements']}==set(range(4))
  assert abs(sum(p['score'] for p in r['placements']))<1e-9 and r['pool_total']==707
  for rd in r['rounds']:
   for row in rd['ledger']:
    ledgers+=1
    assert row['base_income']==base_income(rd['round'])
    assert row['income']==row['base_income']+row['carry']+row['bonus']
    assert row['income']-sum(x['cost'] for x in row['actions'])==row['remaining']
    assert 0<=row['bank']<=2 and len(row['deck'])>=8
    assert not {x['name'] for x in row['actions'] if x['kind']=='buy'}&START_ONLY
    assert set(row['deck'])<=CARDS.keys()
   for battle in rd['battles']:
    battles+=1;assert battle['combat_rule']=='strict_pre_position_v2' and not battle['sequence_skips']
  if r['comparison']['segment']=='final-holdout':final.append(r)
 assert len(seeds)==500 and sorted(seeds)==list(range(293000,293500))
 assert dict(counts)==dict(train=180,validation=60,**{'rolling-holdout':60,'final-holdout':200})
 assert battles==t['battles'] and t['input_hashes_verified'] and t['battle_weights_identical']
 ds,dc=deck_metrics(final),deck_metrics(final,False)
 control_rooms=[];head=Counter();head_rooms=[]
 for r in final:
  first=set(r['comparison']['first_seats'])
  control_rooms.append(dict(r,comparison=dict(r['comparison'],first_seats=sorted(set(range(4))-first))))
  cell=Counter()
  for rd in r['rounds']:
   for battle in rd['battles']:
    if battle['ghost']:continue
    actors=battle['participants']
    if (actors[0]['pid'] in first)==(actors[1]['pid'] in first):continue
    new_side=0 if actors[0]['pid'] in first else 1
    cell['battles']+=1;cell['new_win_share']+=.5 if battle['winner'] is None else battle['winner']==new_side
    cell['draws']+=battle['winner'] is None
  head.update(cell)
  if cell['battles']:head_rooms.append(cell['new_win_share']/cell['battles'])
 cstats=selected_statistics(control_rooms)
 (OUT/'control-final-statistics.json').write_text(json.dumps(cstats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 hm=sum(head_rooms)/len(head_rooms);hse=math.sqrt(sum((v-hm)**2 for v in head_rooms)/(len(head_rooms)-1)/len(head_rooms))
 head_result=dict(**head,new_win_rate=head['new_win_share']/head['battles'],control_win_rate=1-head['new_win_share']/head['battles'],room_mean=hm,room95low=hm-1.96*hse,room95high=hm+1.96*hse)
 (OUT/'head-to-head.json').write_text(json.dumps(head_result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (OUT/'run-audit.json').write_text(json.dumps(dict(games=500,battles=battles,ledgers=ledgers,unique_seeds=500,segments=dict(counts),
  sequence_skips=0,bank_income_debit_passed=True,battle_weights_identical=True,selected_deletion_detail=ds,control_deletion_detail=dc),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 labels={'fire':'火','water':'水','earth':'土','wind':'风','poison':'毒'}
 lines=['# v1.2 约15张牌组：5轮500局构筑训练与小牌组对照','',
  f"完成{t['completed']}/500局完整四AI赛事，{t['battles']:,}场战斗，跳过{t['skipped']}局。最终候选{t['candidate']['checkpoint']}，接受{t['accepted_steps']}次更新。",'',
  '## 冻结终测的结论','',
  f"最终200局，新策略战斗胜率{pct(a['win_rate'])}，上一轮小牌组AI为{pct(b['win_rate'])}；逐赛事配对胜率差{pct(ci['mean'])}，95%区间[{pct(ci['low'])}, {pct(ci['high'])}]。{'区间完全大于0，本轮对照支持提高胜率。' if ci['low']>0 else '区间完全小于0，本轮对照显示胜率下降。' if ci['high']<0 else '区间跨0，证据不足以确认哪种构筑更强。'}",'',
  '|指标|较大牌组新策略|原小牌组策略|','|---|---:|---:|',
  f"|终局平均张数|{e['selected_decks']['mean_size']:.2f}|{e['control_decks']['mean_size']:.2f}|",
  f"|终局中位数|{e['selected_decks']['median']}|{e['control_decks']['median']}|",
  f"|终局张数范围|{e['selected_decks']['minimum']}—{e['selected_decks']['maximum']}|{e['control_decks']['minimum']}—{e['control_decks']['maximum']}|",
  f"|人均购买|{ds['purchases_per_player']:.2f}|{dc['purchases_per_player']:.2f}|",
  f"|人均删除|{ds['deletions_per_player']:.2f}|{dc['deletions_per_player']:.2f}|",
  f"|人均付费删除|{ds['paid_deletions_per_player']:.2f}|{dc['paid_deletions_per_player']:.2f}|",
  f"|运转牌占比|{pct(e['selected_decks']['flow_fraction'])}|{pct(e['control_decks']['flow_fraction'])}|",
  f"|夺冠率|{pct(a['championship_rate'])}|{pct(b['championship_rate'])}|",
  f"|人均排名分|{number(a['mean_score'])}|{number(b['mean_score'])}|",
  f"|获胜平均行动值|{number(a['winner_time'])}|{number(b['winner_time'])}|",
  f"|每场平均出牌|{number(a['plays_per_battle'])}|{number(b['plays_per_battle'])}|",
  f"|每场即时抽牌|{number(a['instant_draw_per_battle'])}|{number(b['instant_draw_per_battle'])}|",'',
  '这次重启确实改变了构筑行为：牌组变大、付费删除减少，未停留在原来的小牌组附近。但新策略每场出牌更多，获胜时反而更晚，胜率也下降，说明更多抓牌和节省删牌点数在本轮没有转化为更强战力。可能涉及抽到关键牌的频率与原战斗AI的排序适配，当前对照不能把这些原因完全拆开。',
  '双方战斗AI、元素微调和六种随机战斗风格完全相同且冻结，均沿用上一轮explore-accepted-07；改变的是构筑抓牌、跳过、刷新和删牌决策。因此比同时改战斗AI更能区分本轮构筑改变的贡献，但不能把收益拆解成纯张数、牌质与删牌费用各自的贡献。',
  f"补充直接交手统计：去除同策略内战及幽灵后，两策略实际直接交手{head['battles']}场，新策略胜率{pct(head_result['new_win_rate'])}，小牌组{pct(head_result['control_win_rate'])}（平局各计半）。按赛事聚类的新策略胜率区间[{pct(head_result['room95low'])}, {pct(head_result['room95high'])}]。该项为终测后的描述性补充，不用于调参或改写预先指定的评价指标。",
  '胜率平局计半胜。两种策略每房各2名AI，随机分配座位、共享有限卡池；可能同策略交手，三人阶段使用幽灵，所以两列胜率并非互补。置信区间按完整赛事聚类；汇总胜率与逐赛事差的权重不同。','',
  '## 五轮安排与大幅重启','',
  '不是继续在小牌组附近做4%微调。新起点将稀释权重降为0.84、抓牌门槛降为0.2、删牌门槛提高到2.4，并新增约15张的软目标：低于目标时，只给达到当前牌质门槛的新牌抓取加分；达到目标附近鼓励保留有用牌；付费删除额外扣6评价分。允许不足15或超过15，也允许在收益足够高时付费删除，不改变最低8张和游戏原有删牌次数/费用。',
  '目标15固定为用户指定的软倾向，其余构筑参数在重启点附近以最高15%步长探索，新增软倾向系数最高12%。前三轮每轮60训练＋20新种子验证＋20封存对照；后两轮冻结候选共200局独立终测。共180训练、60验证、60滚动封存、200最终封存。只以战斗胜率选择更新；未把“达到15张”作为胜率或胜利奖励。',
  '训练比较候选与当前较大牌组检查点，训练胜率差非负且验证差至少0.5个百分点才接受；最终200局始终与冻结的上一轮小牌组模型比较。封存结果不参与调参或检查点重选，报告不会据终测重新调整模型再复用这些种子。','',
  '|轮|接受更新|检查点|训练胜率差|验证胜率差|','|---|---|---|---:|---:|']
 for row in t['batches']:
  lines.append(f"|{row['round']}|{row['accepted']}|{row['selected']}|{pct(row.get('train',{}).get('mean'))}|{pct(row.get('validation',{}).get('mean'))}|")
 lines+=['','## 分元素的终局构筑与成绩','',
  '|元素|新/旧平均张数|新/旧运转牌占比|新模型人数|新/旧战斗胜率|新模型夺冠率|新模型人均分|',
  '|---|---:|---:|---:|---:|---:|---:|']
 for el in ELEMENTS:
  x=e['selected_decks']['elements'][el];y=e['control_decks']['elements'][el];m=s['elements'][el]
  lines.append(f"|{labels[el]}|{x['mean_size']:.2f}/{y['mean_size']:.2f}|{pct(x['flow_fraction'])}/{pct(y['flow_fraction'])}|{m['players']}|{pct(m['win_rate'])}/{pct(cstats['elements'][el]['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','终局牌组大小还受淘汰轮次影响。运转牌指即时抽牌、回费、检索、主动弃置、洗牌或回收任一种机制，初始牌在分母内；首次本系层总量、逐轮平均大小和完整长度分布见training.json。','',
  '|路线|最终人数|战斗胜率|夺冠率|人均分|','|---|---:|---:|---:|---:|']
 for n,m in sorted(s['routes'].items(),key=lambda row:row[1]['mean_score'] if row[1]['mean_score'] is not None else -999,reverse=True):
  lines.append(f"|{n}|{m['players']}{'（小样本）' if m['players']<30 else ''}|{pct(m['win_rate'])}|{pct(m['championship_rate'])}|{number(m['mean_score'])}|")
 lines+=['','## 问题与限制','', '|问题|处理|','|---|---|',
  f"|运行异常或跳过|{t['skipped']}；详见issues.json，未补造结果|",
  '|仅一种较大牌组策略族与一个冻结对照|不能证明15张是全局最优，结果也不能直接推广到所有真人构筑|',
  '|纯构筑对照|有助于判断构筑改变的整体收益，但没有单独消融软目标、强牌门槛、少删牌三项|',
  '|小样本元素和路线|少于30名标注，不自动据低携带率删牌|',
  '|固定战斗AI未针对新牌组重新训练|本轮优先隔离构筑改变；如果表现不佳，仍需区分是构筑本身还是原战斗策略不适配|',
  '|软目标15，实测均值17.03|本轮检验的是约17张的较大牌组策略，不能据此断言严格15张一定更弱；未看完终测再调低目标补测|',
  '|默认AI|本轮只比较构筑假设，保留候选与旧模型，未自动替换默认fixed-legacy|','',
  '39项现行预检通过，含新增抓强牌与减少付费删除的定向测试。全500局账本、研习收入/继承、初始牌不入池、排名零和、707份库存、严格结算及零失效跳过检查通过，输入哈希通过；v1.1冻结校验单独记录。无卡牌、经济或战斗规则修改。','',
  '逐卡最终携带/使用见[final-cards.md](final-cards.md)；500局混合训练分布见[training-distribution.md](training-distribution.md)及[cards.md](cards.md)，不能当作最终候选独立成绩。']
 write('report.md',lines)
 cards=['# 冻结最终较大牌组AI：189张卡牌携带与使用','',
  f"200局终测，{s['players']}名新策略玩家。携带率按终局持有；参战使用率为持有该牌的战斗中至少施放一次的比例；平均次数为持牌参战每场的施放次数。初始牌和专精不入池；低使用率不能直接证明牌弱。",'',
  '|卡牌|元素|携带人数|携带率|曾携带率|得分率|人均分|夺冠率|参战使用率|平均施放次数|曝光购买率|',
  '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for c in sorted(s['cards'],key=lambda c:(c['element'],c['carry_rate'])):
  cards.append(f"|{c['name']}|{c['element']}|{c['players']}|{pct(c['carry_rate'])}|{pct(c['ever_carry_rate'])}|{pct(c['score_rate'])}|{number(c['mean_score'])}|{pct(c['championship_rate'])}|{pct(c['usage_rate'])}|{number(c['casts_per_carried_battle'])}|{pct(c['exposure_conversion'])}|")
 write('final-cards.md',cards)
 print(json.dumps(dict(completed=t['completed'],battles=battles,evaluation=e),ensure_ascii=False))

if __name__=='__main__':main()
