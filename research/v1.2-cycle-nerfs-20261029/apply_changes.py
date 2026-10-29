"""One-time implementation of the user's 2026-10-29 cycle-card adjustments."""
from pathlib import Path
import ast
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

def edit(rel, fn):
    path = ROOT / rel
    old = path.read_text(encoding='utf-8')
    new = fn(old)
    if old != new:
        backup = OUT / 'before' / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(new, encoding='utf-8')

def remove_branch(src, marker):
    lines = src.splitlines(keepends=True)
    i = next(i for i, line in enumerate(lines) if marker in line)
    indent = len(lines[i]) - len(lines[i].lstrip())
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
        j += 1
    return ''.join(lines[:i] + lines[j:])

REMOVED = ('潮汐恩泽', '大地之盾', '穿空')
for e in ('water','earth','wind'):
    edit(f'docs/cards-v1.2/{e}.md', lambda s: '\n'.join(line for line in s.split('\n') if not any(line.startswith('|'+n+'|') for n in REMOVED) and not line.startswith('- 穿空打出')))
edit('docs/cards-v1.2/fire.md', lambda s: s.replace('伤害乘以1.2', '伤害乘以1.1'))
edit('docs/cards-v1.2/water.md', lambda s: s.replace('|深渊|2|','|深渊|3|').replace('## 稀有（13）','## 稀有（12）').replace('31张','30张').replace('1/4/8/13/5','1/4/8/12/5'))
edit('docs/cards-v1.2/earth.md', lambda s: s.replace('额外获得1层土附魔；本场每次自身主弹','本场每次自身主弹').replace('最终×1.15','最终×1.1').replace('山岳壁垒的额外土层属于每次打出效果，与首次元素层分开；其他牌不自动获得重复叠层能力。','山岳壁垒只在本场首次打出时获得表中首次土层；重复打出只增加发射前获盾固定值，不额外增加土附魔层。').replace('## 稀有（13）','## 稀有（12）').replace('32张','31张').replace('1/4/9/13/5','1/4/9/12/5'))
edit('docs/cards-v1.2/wind.md', lambda s: s.replace('|风暴|2|','|风暴|3|').replace('## 史诗（9）','## 史诗（8）').replace('32张','31张').replace('1/4/9/13/5','1/4/8/13/5'))
edit('docs/cards-v1.2/poison.md', lambda s: s.replace('间隔×1.25','间隔×1.2').replace('每次×1.25','每次×1.2'))
for p in (ROOT/'docs/cards-v1.2').glob('*.md'):
    if p.name in ('catalogue.md','snapshot-audit.md','change-history.md'):
        continue
    edit(str(p.relative_to(ROOT)),lambda s:s.replace('192张','189张').replace('718份','707份'))
edit('tools/sim_v12/catalog.py', lambda s: s.replace("RETIRED = frozenset((", "RETIRED = frozenset(('潮汐恩泽', '大地之盾', '穿空', ",1).replace(",'大地之盾'",'').replace('== 192','== 189'))
for rel in ('effects.py','policy.py','legacy_policy.py'):
    edit('tools/sim_v12/'+rel, lambda s: s.replace("'潮汐恩泽', ",'').replace("'大地之盾', ",'').replace(", '大地之盾'",'').replace("'穿空', ",''))
for marker in ("elif n == '潮汐恩泽':", "elif n == '大地之盾':", "elif n == '穿空':"):
    edit('tools/sim_v12/effects.py', lambda s,m=marker:remove_branch(s,m))
edit('tools/sim_v12/effects.py',lambda s:s.replace("    elif n == '山岳壁垒':\n        s.layers['earth'] += 1\n", "    elif n == '山岳壁垒':\n"))
edit('tools/sim_v12/engine.py',lambda s:s.replace("Q(23, 20)**s.fx['shield_structure']", "Q(11, 10)**s.fx['shield_structure']").replace("Q(5, 4)**source.fx['slow_poison']", "Q(6, 5)**source.fx['slow_poison']").replace("Q(6, 5)**s.fx['melt_shield']", "Q(11, 10)**s.fx['melt_shield']").replace("defense_pen = s.fx['penetration']",'defense_pen = 0').replace("+Q(s.fx['penetration'], 100)",''))
edit('tools/sim_v12/construction.py',lambda s:s.replace("'层岩结构':3", "'层岩结构':2").replace(",'潮汐恩泽':2,'大地之盾':2",'').replace("'山岳壁垒':2.5", "'山岳壁垒':1.5").replace("'熔盾烈焰':2,'穿空':2", "'熔盾烈焰':1"))
edit('tools/sim_v12/mechanics.py',lambda s:s.replace("'层岩结构': 1.5", "'层岩结构': 1.0").replace("'山岳壁垒': 1.5", "'山岳壁垒': 1.0").replace("'缓释毒素': 1.2", "'缓释毒素': 0.96"))
edit('tools/sim_v12/test_current.py',lambda s:s.replace('(192,192,718)','(189,189,707)').replace("    if name=='潮汐恩泽':expected['water']=1\n    elif name in ('山岳壁垒','大地之盾'):expected['earth']=1\n",''))
edit('tools/audit_v12_layers.py',lambda s:s.replace(' 风暴 穿空 ', ' 风暴 ').replace(' 潮汐恩泽 ', ' ').replace('192张','189张'))

from tools.sim_v12.catalog import CARDS,ELEMENTS,copies,export
assert len(CARDS)==189 and sum(copies(c) for c in CARDS.values())==707
export(OUT)
rarities={'specialization':'专精','legendary':'传奇','epic':'史诗','rare':'稀有','common':'普通'}
lines=['# v1.2现行189张卡牌总表','','2026-10-29。循环成长削弱已执行；首次层按实例每场一次，无额外可循环元素层。费用上调保留原攻防面板。','']
for e,label in zip((*ELEMENTS,'generic'),('火','水','土','风','毒','通用')):
    lines += ['## '+label,'','|品质|卡牌|费|攻|防|首次层|效果|','|---|---|---:|---:|---:|---:|---|']
    for c in CARDS.values():
        if c.element==e:
            lines.append(f'|{rarities[c.rarity]}|{c.name}|{c.cost}|{c.attack}|{c.defense}|{c.layers}|{c.text}|')
    lines.append('')
edit('docs/cards-v1.2/catalogue.md',lambda s:'\n'.join(lines)+'\n')
summary='2026-10-29循环成长调整已生效：删除潮汐恩泽、大地之盾、穿空；山岳壁垒取消额外土层（保留首次1层）；熔盾烈焰1.1、深渊3费、层岩结构1.1、风暴3费、缓释毒素1.2。当前189张、707份。费用上调保留原固定攻防。历史训练报告仍对应当时卡表。'
edit('tools/sim_v12/README.md',lambda s:s.replace('192张','189张').replace('718份','707份').replace('2026-10-29追加：穿甲已删除，专属抽牌/回费及AI分支已移除；循环叠附魔层候选潮汐恩泽、大地之盾、山岳壁垒尚未删除。检查报告见research/v1.2-repeat-enchantment-review-20261029/report.md。此前2000局为193张历史版本。',summary))
for rel in ('docs/cards-v1.2/README.md','docs/cards-v1.2/snapshot-contract.md'):
    edit(rel,lambda s:s.replace('潮汐恩泽、大地之盾、山岳壁垒为循环叠附魔层待删候选，尚未移出。',summary))
edit('docs/README.md',lambda s:s.replace('[192张卡牌总表]','[189张卡牌总表]').replace('718份库存','707份库存').replace('最新[循环附魔层检查](../research/v1.2-repeat-enchantment-review-20261029/report.md)：已删除穿甲；潮汐恩泽、大地之盾、山岳壁垒列为待删候选，尚未移出。下方2000局报告使用删穿甲前的193张卡表。','最新[循环成长调整验证](../research/v1.2-cycle-nerfs-20261029/report.md)：已删除潮汐恩泽、大地之盾、穿空，山岳壁垒取消额外土层，并落实五系指定削弱。下方2000局报告仍对应193张历史卡表。'))
