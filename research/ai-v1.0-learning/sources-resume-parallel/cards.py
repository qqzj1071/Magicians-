"""v1.0 frozen cards; decks contain references, never parallel card snapshots."""
from dataclasses import dataclass
from fractions import Fraction as Q
from pathlib import Path
import json,os
ROOT=Path(__file__).resolve().parents[2]
_active=ROOT/'decks/active.json'
_default=ROOT/'decks/decks.json'
if _active.exists():
    _pointer=json.loads(_active.read_text(encoding='utf-8'))
    _default=(_active.parent/_pointer['library']).resolve()
LIBRARY_PATH=Path(os.environ.get('MAGICIANS_CARD_LIBRARY',str(_default))).resolve()
LIBRARY=json.loads(LIBRARY_PATH.read_text(encoding='utf-8'))
if LIBRARY.get('version')!='1.0':raise ValueError('Only frozen v1.0 inputs are supported; historical engines are in the archive.')
CARD_LIBRARY_PATH=(LIBRARY_PATH.parent/LIBRARY['card_library']).resolve()
CATALOG=json.loads(CARD_LIBRARY_PATH.read_text(encoding='utf-8'))
if CATALOG.get('version')!='1.0':raise ValueError('Card and deck versions differ.')
DECKS={d['id']:d for d in LIBRARY['decks']}
@dataclass(frozen=True)
class Card:
    name: str
    cost: int
    element: str
    rarity: str
    attack: int
    defense: int
    layers: int
    ability: bool
    kind: str
    text: str
PARAMS=CATALOG['mechanic_parameters']
CARDS={n:Card(**{k:v for k,v in c.items() if k!='route_support'}) for n,c in CATALOG['cards'].items()}
HEALS=CATALOG['runtime_tables']['heals']
SHIELDS=CATALOG['runtime_tables']['shields']
SUB={n:tuple(v) for n,v in CATALOG['runtime_tables']['submissiles'].items()}
SPECIAL={n for n,c in CARDS.items() if c.kind=='specialization'}
STACKING={n for n,c in CARDS.items() if c.rarity=='legendary' and c.element!='generic' and c.kind!='route_legendary'}
ROUTES={n for n,c in CARDS.items() if c.kind=='route_legendary'}
