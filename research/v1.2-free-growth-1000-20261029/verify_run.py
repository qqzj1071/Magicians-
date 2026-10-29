"""Read-only outcome/ledger audit; no extra simulations or checkpoint changes."""
from pathlib import Path
from collections import Counter
import gzip,json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,START_ONLY
from tools.sim_v12.tournament import base_income

def main():
 seeds=[];battle_count=0;segments=Counter();ledgers=0;cycle=Counter()
 for path in sorted((OUT/'batches').glob('*/room-*.json.gz')):
  with gzip.open(path,'rt',encoding='utf-8') as h:r=json.load(h)
  seeds.append(r['seed']);segments[r['comparison']['segment']]+=1
  assert len(r['placements'])==4 and {p['pid'] for p in r['placements']}==set(range(4))
  assert abs(sum(p['score'] for p in r['placements']))<1e-9
  assert r['pool_total']==707
  for rd in r['rounds']:
   for row in rd['ledger']:
    ledgers+=1
    assert row['base_income']==base_income(rd['round'])
    assert row['income']==row['base_income']+row['carry']+row['bonus']
    assert 0<=row['bank']<=2 and row['carry']<=2
    assert row['income']-sum(a['cost'] for a in row['actions'])==row['remaining']
    assert len(row['deck'])>=8
    assert not {a['name'] for a in row['actions'] if a['kind']=='buy'}&START_ONLY
    assert set(row['deck'])<=CARDS.keys()
   for b in rd['battles']:
    battle_count+=1
    assert b['combat_rule']=='strict_pre_position_v2'
    assert not b['sequence_skips']
    for counts in b['executed_by_seat']:assert set(counts)<=CARDS.keys()
    for counts in b['cycle_decisions']:cycle.update(counts)
 assert len(seeds)==1000 and len(set(seeds))==1000 and sorted(seeds)==list(range(292000,293000))
 assert dict(segments)=={'train':480,'validation':160,'rolling-holdout':160,'final-holdout':200}
 t=json.loads((OUT/'training.json').read_text(encoding='utf-8'))
 assert battle_count==t['battles'] and t['input_hashes_verified']
 result=dict(games=1000,unique_seeds=1000,battles=battle_count,ledgers=ledgers,segments=dict(segments),
  pool_total=707,sequence_skips=0,cycle_decisions=dict(cycle),income_bank_debit_checks=True,starters_never_bought=True,
  four_players_and_zero_sum_rank_scores=True,input_hashes_verified=True)
 (OUT/'run-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
