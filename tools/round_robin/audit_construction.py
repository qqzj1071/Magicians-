"""Read-only audit of proposed construction probabilities and frozen pool feasibility."""
import json
import random
from construction_templates import apply_refresh_legendary_guarantee
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]


def main():
    cfg = json.loads((ROOT / 'docs/deckbuilding/construction-probabilities.json').read_text(encoding='utf-8'))
    cards = json.loads((ROOT / 'releases/v1.0/cards.json').read_text(encoding='utf-8'))['cards']
    from shared_draft_pool import assert_uniform_counts
    assert_uniform_counts(cfg)
    for faces in cfg['rarities'].values():
        for probabilities in faces:
            assert len(probabilities) == 4
            assert all(0 <= p <= 1 for p in probabilities)
            assert abs(sum(probabilities) - 1) < 1e-10
    for probabilities in cfg['legendary_types'].values():
        assert all(0 <= p <= 1 for p in probabilities)
        assert abs(sum(probabilities) - 1) < 1e-10
    counts = cfg['pre_specialization_enchantment_count']
    assert abs(sum(counts.values()) - 1) < 1e-10
    assert 3 <= sum(int(k) * p for k, p in counts.items()) <= 3.35
    assert 0 < cfg['refresh_bought_element_admission'] < 1
    assert 0.6 <= cfg['post_specialization_enchantment_share'] <= 0.7
    baseline=json.loads((ROOT/'docs/deckbuilding/construction-baseline-v2.json').read_text(encoding='utf-8'))
    for n,q in cfg.get('card_copy_overrides',{}).items():
        c=cards[n];assert c['rarity'] in ('common','rare','epic')
        b=baseline['nonlegendary_copy_counts'][c['rarity']]['generic' if c['element']=='generic' else 'enchantment']
        assert isinstance(q,int) and -1<=q-b<=2
    assert cfg['legendary_types']['6_to_8'][0] >= 2 / 3
    assert cfg['legendary_types']['9_plus'][0] < cfg['legendary_types']['6_to_8'][0]
    assert cfg['legendary_types']['9_plus'][2] > cfg['legendary_types']['6_to_8'][2]
    results = {}
    for round_num, index, prefix in [(2, 2, 'round_2_epic'), (6, 3, 'round_6_legendary'), (7, 3, 'round_7_legendary')]:
        first, refresh = cfg['rarities'][str(round_num)]
        a = 1 - (1 - first[index]) ** 8
        b = 1 - (1 - first[index]) ** 8 * (1 - refresh[index]) ** 8
        assert b <= cfg['hard_caps'][prefix + '_both']
        if round_num == 2:
            assert a <= cfg['hard_caps'][prefix + '_first']
        results[prefix] = {'first': a, 'both': b}
    assert cfg['first_face_legendary_guarantees'] == {'8': 3, '10': 3, '12': 3}
    assert cfg['second_face_legendary_guarantees'] == {'8': 1, '10': 1, '12': 1}
    assert cfg['first_face_guaranteed_route_target'] == 2
    guaranteed = set(cfg['guaranteed_slot_indices_zero_based'])
    assert guaranteed == {0, 1, 2}
    assert cfg['refresh_slot_mapping'] == 'same_index_skip_purchased_no_compaction'
    # Exercise all masks and low/mixed/all-legendary templates, including empty refresh.
    rng = random.Random(42)
    for mask in range(256):
        purchased = {i for i in range(8) if mask & (1 << i)}
        active = set(range(8)) - purchased
        for template in [[0]*8, [1]*8, [2]*8, [3]*8, [3, 2, 1, 0, 3, 2, 1, 0]]:
            result, chosen = apply_refresh_legendary_guarantee(template, purchased, rng)
            if not active:
                assert chosen is None and result == template
                continue
            assert chosen in active
            assert template[chosen] == min(template[i] for i in active)
            assert result[chosen] == 3
            assert all(result[i] == template[i] for i in range(8) if i != chosen)
            assert sum(result[i] == 3 for i in active) == min(len(active), sum(template[i] == 3 for i in active) + 1)
    assert cfg['pool_scope'] == 'shared_all_rarities'
    assert set(cfg['nonlegendary_copy_counts'])=={'common','rare','epic'}
    for rarity,groups in cfg['nonlegendary_copy_counts'].items():
        assert set(groups)=={'enchantment','generic'}
        for group,q in groups.items():
            assert isinstance(q,int) and q>0
            assert abs(q-baseline['nonlegendary_copy_counts'][rarity][group])<=2
    assert cfg['legendary_copy_counts'] == {'generic': 2, 'route': 1, 'stacking': 1}
    assert cfg['legendary_seen_scope'] == 'physical_copy_all_generated_faces_all_players_current_round'
    assert abs(cfg['rarities']['5'][0][2] * 8 - 1) < 1e-10
    for r in ['1', '2', '3', '4', '5']:
        assert all(face[3] == 0 for face in cfg['rarities'][r])
    assert all(face[2] == 0 for face in cfg['rarities']['1'])
    assert all(face[0] < face[1] for face in cfg['rarities']['8_plus'])
    legends = [c for c in cards.values() if c['rarity'] == 'legendary']
    route_counts = Counter(c['element'] for c in legends if c['kind'] == 'route_legendary')
    assert len(legends) == 28 and set(route_counts.values()) == {3}
    for name in cfg['generic_engine_legendaries']:
        assert cards[name]['rarity'] == 'legendary' and cards[name]['element'] == 'generic'
    same_element_pool = [c['name'] for c in legends if c['element'] in ('fire', 'generic')]
    assert len(same_element_pool) == 12
    same_element_copies = sum(2 if cards[n]['element'] == 'generic' else 1 for n in same_element_pool)
    assert same_element_copies == 20
    print(json.dumps({'configuration_checks': 'passed', 'probability_bounds': results,
                      'legendary_count': len(legends), 'routes_per_element': dict(route_counts),
                      'unconditional_guarantee': 'still_inventory_dependent',
                      'same_element_legendary_copies': same_element_copies,
                      'two_face_four_player_guarantee_demand': 16,
                      'refresh_guarantee_template_checks': 1280}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
