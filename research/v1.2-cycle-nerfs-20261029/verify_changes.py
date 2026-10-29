"""Verify the exact requested card-data delta against the preceding 192-card table."""
from pathlib import Path
from dataclasses import asdict
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,copies,export
from tools.sim_v12.effects import EFFECTS
from tools.sim_v12.pool import Pool

before=json.loads((ROOT/'research/v1.2-repeat-enchantment-review-20261029/cards.json').read_text(encoding='utf-8'))['cards']
removed=set(before)-set(CARDS)
assert removed=={'潮汐恩泽','大地之盾','穿空'},removed
assert not set(CARDS)-set(before)
changes={}
for name,c in CARDS.items():
    fields={k:dict(before=before[name][k],after=v) for k,v in asdict(c).items() if before[name][k]!=v}
    if fields:changes[name]=fields
assert {name:set(fields) for name,fields in changes.items()}=={
    '熔盾烈焰':{'text'},'深渊':{'cost'},'山岳壁垒':{'text'},
    '层岩结构':{'text'},'风暴':{'cost'},'缓释毒素':{'text'}}
assert set(CARDS)==set(EFFECTS)
assert len(CARDS)==189 and sum(copies(c) for c in CARDS.values())==707
assert len(Pool().tokens)==707
assert 'Ran 30 tests' in (OUT/'tests.txt').read_text(encoding='utf-8')
assert (OUT/'tests.txt').read_text(encoding='utf-8').strip().endswith('OK')
export(OUT)
static=json.loads((ROOT/'research/v1.2-simulation-readiness-20261028/static-audit.json').read_text(encoding='utf-8'))
result=dict(cards=len(CARDS),stock=sum(copies(c) for c in CARDS.values()),deleted=sorted(removed),changed_fields=changes,
    unchanged_cards=len(CARDS)-len(changes),tests_passed=30,static_budget_problems=static['budget_problems'],
    intentional_budget_deviations=static['intentional_budget_deviations'],new_tournaments=0,
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'tools/sim_v12').glob('*.py'))})
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(cards=result['cards'],stock=result['stock'],deleted=result['deleted'],changed_cards=list(changes),unchanged_cards=result['unchanged_cards'],tests_passed=30),ensure_ascii=False))
