"""Apply the explicitly requested v1.2 穿甲 retirement; leave layer candidates live."""
from pathlib import Path
import ast
import json
import re

ROOT = Path(__file__).resolve().parents[1]

def edit(rel, fn):
    p = ROOT / rel
    old = p.read_text(encoding='utf-8')
    new = fn(old)
    if new != old:
        p.write_text(new, encoding='utf-8')

def remove_branch(src, marker):
    lines = src.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if marker in line:
            indent = len(line) - len(line.lstrip())
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
                j += 1
            return ''.join(lines[:i] + lines[j:])
    raise AssertionError(marker)

edit('tools/sim_v12/catalog.py', lambda s: s.replace("'不动如山',", "'穿甲', '不动如山',", 1).replace('== 193', '== 192'))
for rel in ('effects.py', 'policy.py', 'legacy_policy.py'):
    edit('tools/sim_v12/' + rel, lambda s: s.replace("'穿甲', ", ''))
edit('tools/sim_v12/effects.py', lambda s: remove_branch(s, "elif n == '穿甲':"))
edit('tools/sim_v12/learning_policy.py', lambda s: remove_branch(s, "if x.name == '穿甲' and"))
edit('tools/sim_v12/mechanics.py', lambda s: remove_branch(s.replace("'穿甲': 2, ", '').replace("'穿甲': 0.8, ", ''), "elif name == '穿甲':"))
edit('tools/audit_v12_cards.py', lambda s: s.replace('== 193', '== 192'))

def layers(src):
    src = src.replace('顺风 穿甲 疾行', '顺风 疾行').replace('193张', '192张')
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SPECIAL' for t in n.targets))
    data = ast.literal_eval(node.value)
    data.pop('穿甲')
    start, end = node.lineno - 1, node.end_lineno
    lines = src.splitlines(keepends=True)
    lines[start:end] = ['SPECIAL = ' + repr(data) + '\n']
    return ''.join(lines)
edit('tools/audit_v12_layers.py', layers)

def tests(src):
    src = src.replace('(193,193,722)', '(192,192,718)').replace("('穿甲','掠影','护盾','毒瓶')", "('疾行','掠影','护盾','毒瓶')")
    start = src.index(' def test_ai_can_leave_mana_positive_two_card_recycling')
    end = src.index(' def test_retained_cards_and_storm_numeric_change', start)
    replacement = ''' def test_pierce_is_retired_from_effects_and_ai(self):
  from .catalog import RETIRED
  from .effects import EFFECTS
  from . import policy,legacy_policy,mechanics
  self.assertIn('穿甲',RETIRED)
  self.assertNotIn('穿甲',CARDS)
  self.assertNotIn('穿甲',EFFECTS)
  for module in (policy,legacy_policy):
   self.assertNotIn('穿甲',module.DRAW)
   self.assertTrue(all('穿甲' not in names for names in module.SUPPORT.values()))
  self.assertNotIn('穿甲',mechanics.DRAW_N)
  self.assertNotIn('穿甲',mechanics.FEE_N)

'''
    return src[:start] + replacement + src[end:]
edit('tools/sim_v12/test_current.py', tests)
edit('tools/sim_v12/quick_test.py', lambda s: s.replace("'# 全193张卡牌携带与表现'", "f'# 全{len(CARDS)}张卡牌携带与表现'"))
# Future run metadata must follow the live pool, historical outputs remain intact.
edit('tools/sim_v12/thin_train.py', lambda s: s.replace('stock=722', "stock=sum(__import__('tools.sim_v12.catalog',fromlist=['copies']).copies(c) for c in CARDS.values())"))

edit('docs/cards-v1.2/wind.md', lambda s: '\n'.join(line for line in s.split('\n') if not line.startswith('|穿甲|') and not line.startswith('- 穿甲在')).replace('## 稀有（14）', '## 稀有（13）').replace('33张', '32张').replace('1/4/9/14/5', '1/4/9/13/5'))
for p in (ROOT / 'docs/cards-v1.2').glob('*.md'):
    if p.name in ('change-history.md', 'catalogue.md', 'snapshot-audit.md'):
        continue
    edit(str(p.relative_to(ROOT)), lambda s: s.replace('193张', '192张').replace('722份', '718份'))
for rel in ('tools/sim_v12/README.md',):
    edit(rel, lambda s: s.replace('193张', '192张').replace('722份', '718份'))
edit('docs/README.md', lambda s: s.replace('[193张卡牌总表]', '[192张卡牌总表]').replace('722份库存', '718份库存'))

from tools.sim_v12.catalog import CARDS, ELEMENTS, copies, export
out = ROOT / 'research/v1.2-repeat-enchantment-review-20261029'
out.mkdir(exist_ok=True)
export(out)
table = ['# v1.2现行192张卡牌总表', '', '2026-10-29。穿甲已退役；循环附魔层候选待调整，尚未删除。首次层按实例每场一次。', '']
rarities = {'specialization':'专精','legendary':'传奇','epic':'史诗','rare':'稀有','common':'普通'}
for element, label in zip((*ELEMENTS, 'generic'), ('火','水','土','风','毒','通用')):
    table.extend(['## ' + label, '', '|品质|卡牌|费|攻|防|首次层|效果|','|---|---|---:|---:|---:|---:|---|'])
    for c in CARDS.values():
        if c.element == element:
            table.append(f'|{rarities[c.rarity]}|{c.name}|{c.cost}|{c.attack}|{c.defense}|{c.layers}|{c.text}|')
    table.append('')
(ROOT / 'docs/cards-v1.2/catalogue.md').write_text('\n'.join(table)+'\n', encoding='utf-8')
(out/'changes.json').write_text(json.dumps(dict(deleted=['穿甲'],pending_layer_candidates=['潮汐恩泽','大地之盾','山岳壁垒'],cards=len(CARDS),stock=sum(copies(c) for c in CARDS.values())),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
