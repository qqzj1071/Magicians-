from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
ELEMENTS = ('fire', 'water', 'earth', 'wind', 'poison')
START = ('攻击强化', '攻击强化', '防御强化', '防御强化', '护盾', '检索附魔', '短促', '重洗')
START_ONLY = frozenset(START)
RETIRED = frozenset(('灼痛', '镜岩之心', '风幕', '蚀界', '潮汐恩泽', '大地之盾', '穿空', '穿甲', '不动如山', '余震', '元素熔炉', '压实火药', '厚土', '回潮', '圣盾', '垒石', '岩壁', '巨岩', '应急整备', '愈合之光', '慢燃', '战术大师', '毒牙', '毒甲', '水膜', '治愈洪流', '润泽', '渗骨毒素', '濒死回响', '火墙', '火舌', '焰心屏障', '爆裂弹头', '生命洪流', '疾影', '疾风', '盾墙', '破军', '破障法阵', '破风', '碎岳之心', '稳固结界', '腐化之躯', '腐骨', '蓄势', '血之回响', '血偿', '裂空', '速腐', '风卷', '风神之翼', '高压弹仓', '魔力契约', '魔法阵核心'))
RARITIES = {'专精': 'specialization', '传奇': 'legendary', '史诗': 'epic', '稀有': 'rare', '普通': 'common'}
RANK = {r: i for i, r in enumerate(('common', 'rare', 'epic', 'legendary', 'specialization'))}
STACKING = frozenset(('燎原', '深渊潮', '山崩', '飓风', '瘟潮'))
SHIELD_CARDS = frozenset(('护盾','永恒壁垒','盾之共鸣','坚壁','护盾强化',
                         '余烬护心','潮涌','反震岩核','万钧碎盾','不坏壁垒',
                         '回震岩甲','山岳壁垒','岩潮壁垒','临时壁垒','回岩',
                         '守岩','山岳','岩拳','岩核共鸣','握盾','盾脉','碎岩印记','碎盾术','磐岩壁',
                         '裂岩护壁','坚岩','岩甲','磐石','开岩','毒囊'))

@dataclass(frozen=True)
class Card:
    name: str
    cost: int
    attack: int
    defense: int
    layers: int
    element: str
    rarity: str
    text: str
    kind: str
    ability: bool

    @property
    def enchantment(self):
        return self.element != 'generic' and not self.ability

def load():
    result = {}
    for element in (*ELEMENTS, 'generic'):
        rarity = None
        for line in (ROOT / f'docs/cards-v1.2/{element}.md').read_text(encoding='utf-8').splitlines():
            match = re.match(r'## (专精|传奇|史诗|稀有|普通)', line)
            if match:
                rarity = RARITIES[match[1]]
            if not re.match(r'^\|[^|]+\|(?:[^|]+\|)?\d+\|', line):
                continue
            fields = line.split('|')[1:-1]
            if len(fields) in (7, 8):
                # Editorial names remain aliases until runtime identities migrate.
                display_name, name, cost, attack, defense, layers, text = fields[:7]
            else:
                name, cost, attack, defense, layers, text = fields
            kind = 'specialization' if rarity == 'specialization' else 'route_legendary' if rarity == 'legendary' and element != 'generic' and name not in STACKING else 'normal'
            ability = rarity == 'specialization' or rarity == 'legendary' and name not in STACKING
            assert name not in result, name
            result[name] = Card(name, *map(int, (cost, attack, defense, layers)), element, rarity, text, kind, ability)
    assert len(result) == 185
    assert START_ONLY <= result.keys()
    return result

CARDS = load()
SPECIAL = {c.element: n for n, c in CARDS.items() if c.kind == 'specialization'}
ROUTES = {e: tuple(n for n, c in CARDS.items() if c.element == e and c.kind == 'route_legendary') for e in ELEMENTS}

def copies(card):
    if card.name in START_ONLY or card.kind == 'specialization':
        return 0
    if card.rarity == 'legendary':
        return 2 if card.element == 'generic' else 1
    return {'common': (6, 8), 'rare': (4, 6), 'epic': (3, 4)}[card.rarity][card.element == 'generic']

def export(folder):
    from .panel_budget import role, value, multiplier, budget_group, reference_rarity
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = {'version': '1.2', 'scope': 'independent Python simulator', 'initial_deck': list(START),
            'cards': {n: dict(**asdict(c), starter_only=n in START_ONLY, pool_copies=copies(c),
                             panel_role=role(n),panel_value=float(value(c.cost,c.attack,c.defense)),
                             panel_budget_group=budget_group(n),panel_reference_rarity=reference_rarity(n,c.rarity),
                             numeric_equivalent_value=float(value(c.cost,c.attack,c.defense)/multiplier(n))) for n, c in CARDS.items()}}
    data['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'docs/cards-v1.2').glob('*.md')) if p.name != 'change-history.md'}
    (folder / 'cards.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (folder / 'pool-counts.json').write_text(json.dumps({'version': '1.2', 'total': sum(copies(c) for c in CARDS.values()), 'cards': {n: copies(c) for n, c in CARDS.items()}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
