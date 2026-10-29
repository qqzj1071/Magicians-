from copy import deepcopy
from unittest.mock import patch
import unittest
from .engine import Battle
from .model import PlannedCard
from .test_rules import fixture
from .policy import STYLES

class PlanningTests(unittest.TestCase):
    def test_planning_never_changes_real_players_rng_or_play_statistics(self):
        b=fixture('灵感涌现',('轻羽','穿甲','换页'),opponent='毒瓶')
        before=deepcopy(b.players);rngs=[p.rng.getstate() for p in b.players]
        sequences=b.plan_stage()
        self.assertEqual(b.players,before)
        self.assertEqual([p.rng.getstate() for p in b.players],rngs)
        self.assertFalse(b.executed)
        self.assertTrue(all(not c for c in b.executed_by_seat))
        self.assertTrue(sequences[0])

    def test_own_plan_independent_of_enemy_unrevealed_card_choices(self):
        a=fixture('风之躯',('灵感涌现','穿甲','护盾'),opponent='磐石')
        b=fixture('风之躯',('灵感涌现','穿甲','护盾'),opponent='毒瓶')
        self.assertEqual(a.plan_stage()[0],b.plan_stage()[0])

    def test_planner_sees_no_enemy_hidden_zones(self):
        from .policy import choose_play
        b=fixture('穿甲',('掠影','轻羽'))
        def spy(shadow,i):
            enemy=shadow.players[1-i]
            self.assertEqual((enemy.deck,enemy.instances),((),()))
            self.assertFalse(enemy.hand or enemy.pile or enemy.discard or enemy.removed)
            return choose_play(shadow,i)
        with patch('tools.sim_v12.policy.choose_play',side_effect=spy):b.plan_stage()

    def test_resolving_frozen_sequences_never_calls_decision_policy_again(self):
        b=fixture('命运检索',('火花','穿甲','轻羽'))
        sequence=b.plan_stage()
        b.chooser=lambda *args: self.fail('Private choices must not be remade during replay')
        with patch('tools.sim_v12.policy.choose_play',side_effect=AssertionError('No repicking')):
            b.resolve_sequences(sequence)
        self.assertTrue(b.executed)

    def test_invalid_slot_keeps_its_index_instead_of_compressing_queue(self):
        b=fixture('奔流',('风之躯',),opponent='毒瓶')
        a,e=b.players;a.hand.extend(a.pile);a.pile=[];a.energy=1
        e.hand.append(e.pile.pop(0))
        seq=((PlannedCard(a.hand[0].uid,'奔流',3),PlannedCard(a.hand[1].uid,'风之躯',1)),
             (PlannedCard(e.hand[0].uid,'毒瓶',1),PlannedCard(e.hand[1].uid,'防御强化',1)))
        b.resolve_sequences(seq)
        self.assertEqual(b.players[0].poison,0)  # poison at slot0, cleanse at slot1
        self.assertEqual(b.sequence_skips['insufficient_energy'],1)
        self.assertNotIn('奔流',b.executed)

    def test_all_style_families_can_plan_and_resolve(self):
        for style in STYLES:
            with self.subTest(style=style):
                b=fixture('穿甲',('灵感涌现','轻羽'))
                b.styles=(style,style)
                sequences=b.plan_stage();b.resolve_sequences(sequences)
                for s in b.players:s.assert_instances()

if __name__=='__main__':unittest.main()
