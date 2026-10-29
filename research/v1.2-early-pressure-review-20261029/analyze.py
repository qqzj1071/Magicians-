"""Read existing sealed logs and draft balance values; no live rule edits."""
from pathlib import Path
from collections import Counter,defaultdict
from dataclasses import asdict
import gzip,json,math,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS
from tools.sim_v12.mechanics import static

def save(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def panel_pair(c,ratio):
 target=(c.attack+1.5*c.defense)*ratio
 choices=[]
 for attack in range(c.attack+1):
  for defense in range(c.defense+1):
   if attack+defense>=c.attack+c.defense:continue
   value=attack+1.5*defense
   shape=abs(attack*c.defense-defense*c.attack)/max(1,c.attack+c.defense)
   choices.append(((abs(value-target),shape,-value),attack,defense))
 _,a,d=min(choices)
 return a,d

def main():
 bands=defaultdict(Counter);health=defaultdict(list);losses=defaultdict(list);room_heads=defaultdict(list)
 source=ROOT/'research/v1.2-medium-500-20261029'
 for path in sorted((source/'batches').glob('*/room-*.json.gz')):
  r=json.loads(gzip.decompress(path.read_bytes()))
  if r['comparison']['segment']!='final-holdout':continue
  new=set(r['comparison']['first_seats']);hp={i:100 for i in range(4)};alt=dict(hp);heads=defaultdict(Counter)
  for rd in r['rounds']:
   rn=rd['round'];band='1—4' if rn<=4 else '5—8' if rn<=8 else '9—10' if rn<=10 else '11—12' if rn<=12 else '13+'
   for b in rd['battles']:
    ps=b['participants'];head=not b['ghost'] and ((ps[0]['pid'] in new)!=(ps[1]['pid'] in new))
    for side,p in enumerate(ps):
     if side==1 and b['ghost']:continue
     typ='medium' if p['pid'] in new else 'small';win=.5 if b['winner'] is None else b['winner']==side
     bands[(typ,band)]['battles']+=1;bands[(typ,band)]['win_share']+=win
     if head:
      bands[(typ,band)]['head_battles']+=1;bands[(typ,band)]['head_win_share']+=win
      if typ=='medium':heads[band]['n']+=1;heads[band]['wins']+=win
     m,n=(2,.8) if rn<=4 else (4,1.8) if rn<=8 else (7,2) if rn<=12 else (9,3.2) if rn<=14 else (10,4.5) if rn<=16 else (11,6)
     mm,nn=(3,1) if rn<=4 else (5,2) if rn<=8 else (m,n)
     draw=b['winner'] is None;won=b['winner']==side;x=max(1,b['hp'][1-side])
     old=0 if won else m if draw else m+math.floor(math.log(x)*n)
     proposed=0 if won else mm if draw else mm+math.floor(math.log(x)*nn)
     hp[p['pid']]-=old;alt[p['pid']]-=proposed
     if rn<=8 and not won:losses[(typ,band)].append((old,proposed))
   if rn in (4,8):
    for row in rd['ledger']:
     typ='medium' if row['pid'] in new else 'small'
     health[(typ,rn)].append((hp[row['pid']],alt[row['pid']]))
  for band,cell in heads.items():room_heads[band].append(cell['wins']/cell['n'])
 band_rows=[]
 for (typ,band),book in sorted(bands.items()):
  row=dict(policy=typ,rounds=band,**book,win_rate=book['win_share']/book['battles'],head_win_rate=book['head_win_share']/book['head_battles'])
  if typ=='medium':
   xs=room_heads[band];mean=sum(xs)/len(xs);se=math.sqrt(sum((x-mean)**2 for x in xs)/max(1,len(xs)-1)/len(xs))
   row.update(room_weighted_head_mean=mean,room95low=mean-1.96*se,room95high=mean+1.96*se,rooms=len(xs))
  band_rows.append(row)
 health_rows=[]
 for (typ,rn),rows in sorted(health.items()):
  health_rows.append(dict(policy=typ,round=rn,players=len(rows),actual_mean=sum(x[0] for x in rows)/len(rows),
   actual_le20=sum(x[0]<=20 for x in rows),fixed_history_draft_mean=sum(x[1] for x in rows)/len(rows),
   fixed_history_draft_le20=sum(x[1]<=20 for x in rows),fixed_history_draft_le0=sum(x[1]<=0 for x in rows)))
 draft=[]
 for name,c in CARDS.items():
  f=static(name)
  direct=any(f[k]>0 for k in ('draw','fee','search','shuffle','recover','discard'))
  future=f['future_draw']>0 or f['future_fee']>0 or name=='灰烬循环'
  if not (direct or future):continue
  tier='one_use_or_delayed' if c.ability or not direct else 'strong_immediate' if f['draw']>=2 or f['fee']>0 or f['recover']>0 else 'light_immediate'
  # These weak-element cards have conditional premium branches; their ordinary
  # behavior is not the same as unconditional draw+refund/search+recovery.
  if name in ('枯潮','循毒'):tier='light_immediate'
  ratio={'one_use_or_delayed':.85,'strong_immediate':.6,'light_immediate':.75}[tier]
  a,d=panel_pair(c,ratio);den=(c.cost+1)/2
  draft.append(dict(name=name,element=c.element,rarity=c.rarity,tier=tier,target_ratio=ratio,
   old_attack=c.attack,old_defense=c.defense,draft_attack=a,draft_defense=d,
   old_value=(c.attack+1.5*c.defense)/den,draft_value=(a+1.5*d)/den,card_text=c.text))
 save('round-analysis.json',dict(rooms=200,bands=band_rows,health=health_rows,
  loss_means=[dict(policy=k[0],rounds=k[1],losses=len(rows),old=sum(x[0] for x in rows)/len(rows),draft=sum(x[1] for x in rows)/len(rows)) for k,rows in sorted(losses.items())],
  caveat='HP alternative uses fixed historical battles. It is NOT a resimulated tournament: changed health changes later eliminations, ghosts, opponents and choices.'))
 save('draft-flow-panels.json',dict(status='proposal_only_not_applied',count=len(draft),tiers=dict(Counter(c['tier'] for c in draft)),cards=draft))
 save('draft-damage.json',dict(status='proposal_only_not_applied',formula='m+floor(n*ln(max(winner_remaining_battle_hp,1)))',
  rounds_1_to_4=dict(old=[2,.8],draft=[3,1.]),rounds_5_to_8=dict(old=[4,1.8],draft=[5,2.]),rounds_9_plus='unchanged'))
 lines=['# 运转牌攻防下调草案（未应用）','','通过当前机制标签筛选，并补充灰烬循环；需逐卡语义复核。即时强运转目标保留60%面板、轻运转75%、一次性能力或仅延迟资源85%；取不增加任一属性的最近整数对。伤害/护盾等独立效果不变。',
  '这会主动打破此前同品质全牌统一V预算，实施时需同步改为按功能分档审计。以下不是现行卡表。','',
  '|卡牌|类别|旧攻/防|草案攻/防|旧V|草案V|','|---|---|---:|---:|---:|---:|']
 for c in draft:lines.append(f"|{c['name']}|{c['tier']}|{c['old_attack']}/{c['old_defense']}|{c['draft_attack']}/{c['draft_defense']}|{c['old_value']:.2f}|{c['draft_value']:.2f}|")
 (OUT/'draft-flow-panels.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(dict(draft_cards=len(draft),tiers=dict(Counter(c['tier'] for c in draft)),health=health_rows),ensure_ascii=False))

if __name__=='__main__':main()
