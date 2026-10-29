from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
ELEMENTS = ('fire', 'water', 'earth', 'wind', 'poison')
START = ('攻击强化', '攻击强化', '防御强化', '防御强化', '护盾', '检索附魔', '短促', '重洗')
START_ONLY = frozenset(START)
RARITIES = {'专精': 'specialization', '传奇': 'legendary', '史诗': 'epic', '稀有': 'rare', '普通': 'common'}
RANK = {r: i for i, r in enumerate(('common', 'rare', 'epic', 'legendary', 'specialization'))}
STACKING = frozenset(('燎原', '深渊潮', '山崩', '飓风', '瘟潮'))
SHIELD_CARDS = frozenset(('护盾','圣盾','永恒壁垒','盾之共鸣','坚壁','护盾强化','盾墙',
                         '火墙','余烬护心','焰心屏障','潮涌','反震岩核','万钧碎盾','不坏壁垒',
                         '回震岩甲','山岳壁垒','岩潮壁垒','镜岩之心','临时壁垒','回岩','大地之盾',
                         '守岩','山岳','岩拳','岩核共鸣','握盾','盾脉','碎岩印记','碎盾术','磐岩壁',
                         '裂岩护壁','坚岩','岩壁','岩甲','磐石','垒石','开岩','破风','风幕','风卷','毒囊','毒甲'))

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
    # Historical-only replay: exact sealed 239-card machine snapshot.
    data=json.loads((Path(__file__).resolve().parents[2]/'v1.2-quick-500-final-20261028/cards.json').read_text(encoding='utf-8'))['cards']
    fields=Card.__dataclass_fields__
    return {n:Card(**{k:v for k,v in row.items() if k in fields}) for n,row in data.items()}

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
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = {'version': '1.2', 'scope': 'independent Python simulator', 'initial_deck': list(START),
            'cards': {n: dict(**asdict(c), starter_only=n in START_ONLY, pool_copies=copies(c)) for n, c in CARDS.items()}}
    data['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'docs/cards-v1.2').glob('*.md')) if p.name != 'change-history.md'}
    (folder / 'cards.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (folder / 'pool-counts.json').write_text(json.dumps({'version': '1.2', 'total': sum(copies(c) for c in CARDS.values()), 'cards': {n: copies(c) for n, c in CARDS.items()}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
