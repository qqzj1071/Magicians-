from copy import deepcopy
from fractions import Fraction as Q
from unittest.mock import patch
import unittest
from .catalog import CARDS
from .locked import LockedBattle
from .test_rules import fixture

def setup(name,others=(),opponent='攻击强化',rich=False):
    old=fixture(name,others,opponent,rich)
    b=LockedBattle((old.players[0].deck,old.players[1].deck),trace=True)
    b.players=old.players
    return b

def one(b,both=False):
    used=set()
    def choose(shadow,i):
        if i in used or i==1 and not both:return None
        used.add(i);return shadow.players[i].hand[0]
    with patch('tools.sim_v12.policy.choose_play',side_effect=choose):seq=b.plan_stage()
    return seq

class LockedTests(unittest.TestCase):
    def test_all_239_cards_in_both_resource_contexts(self):
        for name in CARDS:
            for rich in (False,True):
                with self.subTest(name=name,rich=rich):
                    b=setup(name,('火花','掠影','护盾','短促'),rich=rich)
                    s=b.players[0];s.discard.append(s.pile.pop())
                    seq=one(b);b.resolve_sequences(seq)
                    self.assertEqual(b.executed[name],1)
                    self.assertFalse(b.sequence_skips)
                    for p in b.players:p.assert_instances()

    def test_heal_draw_promise_survives_real_full_health(self):
        b=setup('活水',('火花',));b.players[0].hp=900
        seq=one(b);uid=seq[0][0].after['hand'][0].uid
        b.players[0].hp=1000;b.resolve_sequences(seq)
        self.assertEqual(b.players[0].hand[0].uid,uid)
        self.assertEqual(b.players[0].hp,1000)

    def test_tide_branch_locks_fee_without_fake_consumption(self):
        b=setup('疾流');s=b.players[0];s.active.add('潮汐之心');s.tide=30
        seq=one(b);s.tide=0;b.resolve_sequences(seq)
        s=b.players[0]
        self.assertEqual(s.pending['energy'],2);self.assertEqual(s.spent_tide,0)

    def test_poison_consume_and_cleanse_confirm_old_once(self):
        b=setup('万毒爆',opponent='风蚀');s,e=b.players
        s.active.add('毒爆');s.layers['poison']=10;e.poison=3;e.hp=500;e.defense=0
        seq=one(b,True);before=s.attack
        b.resolve_sequences(seq)
        self.assertEqual(b.players[1].poison,0)
        self.assertEqual(b.players[0].attack,before+CARDS['万毒爆'].attack+3)
        self.assertTrue(any(x['kind']=='damage' and x['damage_kind']=='explosion' for x in b.log))

    def test_planning_never_executes_or_changes_real_state(self):
        b=setup('碎盾术',('掠影',),rich=True);b.players[1].hp=1
        before=deepcopy(b.players);state=[p.rng.getstate() for p in b.players]
        seq=one(b)
        self.assertEqual(b.players,before);self.assertEqual(state,[p.rng.getstate() for p in b.players])
        self.assertFalse(b.executed);self.assertEqual(len(seq[0]),1)

    def test_execute_on_own_shield_gain_before_later_consumption(self):
        b=setup('碎盾术');s,e=b.players;s.active.add('不周山');s.layers['earth']=100
        e.hp=10;e.defense=0
        seq=one(b);b.resolve_sequences(seq)
        events=[x['kind'] for x in b.log]
        self.assertIn('auto_execute',events)
        self.assertEqual(b.players[0].defense,0)
        self.assertLessEqual(b.players[1].hp,0)

    def test_execute_on_opponent_payment(self):
        b=setup('攻击强化',opponent='燃血');s,e=b.players
        s.active.add('不周山');s.layers['earth']=100;s.shield=100;e.defense=0;e.hp=310
        b.pay_life(e,Q(1,10))
        self.assertLessEqual(e.hp,0);self.assertEqual(s.shield_total,0)

    def test_execute_on_opponent_heal(self):
        b=setup('攻击强化');s,e=b.players
        s.active.add('不周山');s.layers['earth']=100;s.shield=100;e.defense=0;e.hp=1
        b.heal(e,10)
        self.assertLessEqual(e.hp,0)

    def test_known_guard_does_not_waste_execute(self):
        b=setup('护盾');s,e=b.players;s.active.add('不周山');s.layers['earth']=100
        e.hp=1;e.fx['lifeguard']=1
        b.shield_gain(s,100)
        b.flush_shields(s)
        self.assertGreater(s.shield_total,0);self.assertEqual(e.hp,1)

    def test_simultaneous_auto_executes_both_commit(self):
        b=setup('护盾',opponent='护盾')
        for s in b.players:s.active.add('不周山');s.layers['earth']=100
        b.begin_atomic()
        for s in b.players:b.shield_gain(s,3000);b.flush_shields(s)
        b.end_atomic()
        self.assertTrue(all(s.hp<=0 for s in b.players))
        self.assertEqual(sum(e['kind']=='auto_execute' for e in b.log),2)

    def test_revival_cleanse_clears_new_actual_poison(self):
        b=setup('护盾');s=b.players[0]
        b._slot=deepcopy(b.players);b._old_left=[0,0]
        s.rewind=(0,Q(100),Q(40),500,0);s.poison=2;s.hp=0
        b._death()
        self.assertEqual(s.poison,0)

    def test_payment_execute_is_before_trickle_refund(self):
        b=setup('攻击强化',opponent='燃血');s,e=b.players
        s.active.add('不周山');s.layers['earth']=100;s.shield=100;e.defense=0;e.hp=310
        e.fx['trickle']=1
        b.resolve_sequences(one(b,True))
        self.assertLessEqual(b.players[1].hp,0)

    def test_revive_cuts_tail_but_keeps_reached_drawn_instance(self):
        b=setup('万毒爆',opponent='灵感涌现');s,e=b.players
        s.layers['poison']=100;e.poison=3;e.defense=0;e.hp=10
        e.rewind=(0,Q(100),Q(40),500,0)
        sequences=b.plan_stage()
        self.assertGreater(len(sequences[1]),1)
        first=sequences[1][0]
        b.resolve_sequences(sequences)
        e=b.players[1]
        self.assertTrue(e.revived);self.assertGreater(e.hp,0)
        self.assertEqual(sum(b.executed_by_seat[1].values()),1)
        self.assertEqual([x.uid for x in e.hand],[x.uid for x in first.after['hand']])
        e.assert_instances()

    def test_future_revive_cannot_save_earlier_death(self):
        b=setup('万毒爆',opponent='攻击强化');s,e=b.players
        s.layers['poison']=100;e.poison=3;e.defense=0;e.hp=10
        # Give a late, unplayed revive card in addition to the first action.
        from .model import Fighter
        e=Fighter(1,('攻击强化','时光倒流'),hp=10,defense=Q(0),poison=3,energy=100,stage=1)
        e.hand=list(e.instances);e.pile=[];b.players[1]=e
        seq=one(b,True);b.resolve_sequences(seq)
        self.assertLessEqual(b.players[1].hp,0)
        self.assertFalse(b.players[1].revived)

    def test_poison_new_same_slot_layers_survive_cleanse(self):
        b=setup('毒瓶',opponent='风之躯');b.players[1].poison=3
        b.resolve_sequences(one(b,True))
        self.assertEqual(b.players[1].poison,2)

    def test_identical_new_modifier_survives_same_slot_cleanse(self):
        b=setup('磐石',opponent='盾墙')
        b.temp(0,'atk_down',20,1);kind,target,mod=b.operations.pop()
        b.players[1].mods.append(mod);b.players[0].played=1
        b.resolve_sequences(one(b,True))
        mods=[m for m in b.players[1].mods if m.kind=='atk_down']
        self.assertEqual(len(mods),1);self.assertEqual(mods[0].stamp[3],1)

    def test_shield_consumption_and_strip_share_supply(self):
        b=setup('山岳之躯',opponent='腐骨');s,e=b.players
        s.hp=500;s.shield=100
        b.resolve_sequences(one(b,True))
        # Requests: self100 + enemy20; share of original100 is 250/3.
        self.assertEqual(b.players[0].hp,667)
        self.assertEqual(b.players[0].shield_total,0)

    def test_real_random_state_and_promised_choices_replay_exactly(self):
        b=setup('换页',('火花','轻羽','护盾','掠影'))
        s=b.players[0];s.hand.extend(s.pile[:1]);s.pile=s.pile[1:]
        seq=one(b)
        b.chooser=lambda *a:self.fail('No new formal choice')
        b.resolve_sequences(seq)
        s=b.players[0]
        self.assertEqual(s.rng.getstate(),seq[0][0].after['rng'])
        self.assertEqual([x.uid for x in s.pile],[x.uid for x in seq[0][0].after['pile']])

    def test_existing_numeric_regressions_against_locked_kernel(self):
        from . import test_rules as rules
        class Diagnostic(LockedBattle):
            def card_step(self,actions):
                used=set()
                def choice(shadow,i):
                    if i not in actions or i in used:return None
                    used.add(i)
                    return next(x for x in shadow.players[i].hand if x.uid==actions[i])
                with patch('tools.sim_v12.policy.choose_play',side_effect=choice):seq=self.plan_stage()
                return self._slot_step({i:seq[i][0] for i in actions})
        with patch.object(rules,'Battle',Diagnostic):
            suite=unittest.defaultTestLoader.loadTestsFromModule(rules)
            result=unittest.TestResult();suite.run(result)
        self.assertFalse(result.errors or result.failures,'\n'.join(str(t)+'\n'+e for t,e in result.errors+result.failures))

if __name__=='__main__':unittest.main()
