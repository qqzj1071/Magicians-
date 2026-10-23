"""Capacity/probability probe, NOT the production conditional offer generator."""
import json
import random
import math
from collections import Counter, defaultdict, deque
from pathlib import Path
from construction_templates import apply_refresh_legendary_guarantee

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / 'docs/deckbuilding/construction-probabilities.json').read_text(encoding='utf-8'))
CARDS = json.loads((ROOT / 'releases/v1.0/cards.json').read_text(encoding='utf-8'))['cards']


def copies(c):
    r = c['rarity']
    if r == 'specialization':
        return 0
    if r != 'legendary':
        group = 'generic' if c['element'] == 'generic' else 'enchantment'
        return CFG.get('card_copy_overrides', {}).get(c['name'], CFG['nonlegendary_copy_counts'][r][group])
    group = 'generic' if c['element'] == 'generic' else ('route' if c['kind'] == 'route_legendary' else 'stacking')
    return CFG['legendary_copy_counts'][group]


def check_uniform():
    groups=defaultdict(set)
    for c in CARDS.values():
        if c['rarity'] in ('common','rare','epic'):
            groups[(c['rarity'],c['element']=='generic')].add(copies(c))
    assert all(len(v)==1 for v in groups.values()),'Nonuniform nonlegendary bucket'


def capacity(elements, demand, rarity, held=None, route_only=False):
    """Exact max flow: per-name copies shared, per-player same name <=1.

    Two faces combined for legends; held consumes copies and removes owner's name.
    Ignores enchant density/type targets intentionally: this is an upper bound.
    """
    held = held or [set() for _ in elements]
    remaining = {n: copies(c) for n, c in CARDS.items() if c['rarity'] == rarity and
                 (not route_only or c['kind'] == 'route_legendary')}
    for deck in held:
        for n in deck:
            if n in remaining:
                remaining[n] -= 1
                assert remaining[n] >= 0
    graph = defaultdict(dict)

    def edge(a, b, cap):
        graph[a][b] = cap
        graph[b].setdefault(a, 0)

    for n, count in remaining.items():
        edge('source', ('card', n), count)
        for p, element in enumerate(elements):
            if n not in held[p] and CARDS[n]['element'] in (element, 'generic'):
                edge(('card', n), ('player', p), 1)
    for p in range(len(elements)):
        edge(('player', p), 'sink', demand)
    flow = 0
    while True:
        parent = {'source': None}
        queue = deque(['source'])
        while queue and 'sink' not in parent:
            a = queue.popleft()
            for b, cap in graph[a].items():
                if cap > 0 and b not in parent:
                    parent[b] = a
                    queue.append(b)
        if 'sink' not in parent:
            break
        b, amount = 'sink', demand * len(elements)
        while parent[b] is not None:
            a = parent[b]
            amount = min(amount, graph[a][b])
            b = a
        b = 'sink'
        while parent[b] is not None:
            a = parent[b]
            graph[a][b] -= amount
            graph[b][a] += amount
            b = a
        flow += amount
    return flow


def wilson(hits, total):
    z, p = 1.96, hits / total
    d = 1 + z*z/total
    center = (p + z*z/(2*total))/d
    half = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/d
    return [center-half, center+half]


def main():
    check_uniform()
    rng = random.Random('shared-pool-probability-audit-v1')
    trials = 100000
    probability = {}
    for r, index in [(2, 2), (6, 3), (7, 3)]:
        a, b = (face[index] for face in CFG['rarities'][str(r)])
        first_hits = both_hits = 0
        for _ in range(trials):
            first = [rng.random() < a for _ in range(8)]
            second = [rng.random() < b for _ in range(8)]
            first_hits += any(first)
            both_hits += any(first) or any(second)
        probability[str(r)] = {
            'trials': trials, 'first_exact': 1-(1-a)**8,
            'both_exact': 1-(1-a)**8*(1-b)**8,
            'first_observed': first_hits/trials, 'both_observed': both_hits/trials,
            'both_wilson_95': wilson(both_hits, trials)}
    card_counts = Counter(c['rarity'] for c in CARDS.values())
    pool_counts = Counter()
    for c in CARDS.values():
        pool_counts[c['rarity']] += copies(c)
    assert pool_counts['legendary']==36 and pool_counts['specialization']==0
    baseline=json.loads((ROOT/'docs/deckbuilding/construction-baseline-v2.json').read_text(encoding='utf-8'))
    for n,c in CARDS.items():
        if c['rarity'] in ('common','rare','epic'):
            group='generic' if c['element']=='generic' else 'enchantment'
            b=baseline['nonlegendary_copy_counts'][c['rarity']][group]
            assert isinstance(copies(c),int) and -1<=copies(c)-b<=2
    category_counts = Counter()
    for c in CARDS.values():
        group = 'generic' if c['element'] == 'generic' else 'enchantment'
        category_counts[(c['rarity'], group)] += copies(c)
    assert all(CFG['nonlegendary_copy_counts'][r]['generic'] >= 4 for r in ['common', 'rare', 'epic'])
    scenarios = {}
    for label, elements in [('four_distinct', ['fire', 'water', 'earth', 'wind']),
                            ('four_same', ['fire']*4),
                            ('two_pairs', ['fire', 'fire', 'water', 'water'])]:
        scenarios[label] = {
            'legendary_first_face_max_of_12': capacity(elements, 3, 'legendary'),
            'legendary_two_faces_max_of_16': capacity(elements, 4, 'legendary'),
            'first_face_route_target_max_of_8': capacity(elements, 2, 'legendary', route_only=True),
            'common_one_face_max_of_32': capacity(elements, 8, 'common'),
            'rare_one_face_max_of_32': capacity(elements, 8, 'rare'),
            'epic_one_face_max_of_32': capacity(elements, 8, 'epic')}
    assert scenarios['four_distinct']['legendary_two_faces_max_of_16'] == 16
    assert scenarios['four_same']['legendary_two_faces_max_of_16'] == 16
    assert scenarios['four_same']['legendary_first_face_max_of_12'] == 12
    epic_counts = [sum(rng.random() < CFG['rarities']['5'][0][2] for _ in range(8)) for _ in range(trials)]
    probability['5_epic_mean'] = {'trials': trials, 'exact': 1.0, 'observed': sum(epic_counts)/trials}
    refresh_trials = {}
    weights = CFG['rarities']['8_plus'][1]
    for n in [1, 4, 8]:
        total = 0
        purchased = set(range(n, 8))
        for _ in range(trials):
            template = rng.choices(range(4), weights=weights, k=8)
            adjusted, chosen = apply_refresh_legendary_guarantee(template, purchased, rng)
            assert chosen not in purchased
            total += sum(adjusted[i] == 3 for i in range(n))
        refresh_trials[str(n)] = {'active_slots': n, 'trials': trials,
                                 'exact_legendary_mean': n*weights[3] + 1 - weights[3]**n,
                                 'observed_legendary_mean': total/trials}
    probability['guarantee_refresh'] = refresh_trials
    # One same-element route and two generic legends already owned per player.
    generic = [n for n, c in CARDS.items() if c['rarity'] == 'legendary' and c['element'] == 'generic']
    held = [{generic[2*p], generic[2*p+1]} for p in range(4)]
    for p, element in enumerate(['fire', 'water', 'earth', 'wind']):
        held[p].add(next(n for n, c in CARDS.items() if c['element'] == element and c['kind'] == 'route_legendary'))
    scenarios['distinct_already_own_3_legends_each'] = {
        'legendary_first_face_max_of_12': capacity(['fire','water','earth','wind'], 3, 'legendary', held),
        'legendary_two_faces_max_of_16': capacity(['fire','water','earth','wind'], 4, 'legendary', held),
        'first_face_route_target_max_of_8': capacity(['fire','water','earth','wind'], 2, 'legendary', held, route_only=True)}
    report = {'scope': 'rarity-ticket Monte Carlo and exact inventory upper bounds; not full offer/battle simulation',
              'seed': 'shared-pool-probability-audit-v1', 'names_by_rarity': dict(card_counts),
              'copies_by_rarity': dict(pool_counts), 'total_market_copies': sum(pool_counts.values()),
              'copies_by_rarity_and_category': {r: {g: category_counts[(r,g)] for g in ['enchantment','generic']}
                                                for r in ['common','rare','epic']},
              'probability_audit': probability, 'capacity_upper_bounds': scenarios,
              'notes': ['Owned cards, element quotas, type targets, serial refresh and actual purchases can reduce these upper bounds.',
                        'Per-player legendary name is unique across both faces; generic copies may go to different players.',
                        'Initial cards are generated outside the market pool; their final name mapping is not tested here.']}
    manifest = {'status': CFG['status'], 'card_version': '1.0',
                'starter_cards_consume_pool': False,
                'cards': {n: {'copies': copies(c), 'rarity': c['rarity'], 'element': c['element']}
                          for n, c in CARDS.items() if copies(c) > 0}}
    (ROOT / 'docs/deckbuilding/shared-pool-counts.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    out = ROOT / 'docs/deckbuilding/pool-validation.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
