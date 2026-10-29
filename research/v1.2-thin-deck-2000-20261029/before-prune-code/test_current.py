from copy import deepcopy
from fractions import Fraction as Q
from unittest.mock import patch
import unittest
from .catalog import CARDS,copies,START_ONLY,ELEMENTS,SPECIAL
from .effects import verify_registry
from .strict import StrictBattle
from .pool import Pool
from .learning_policy import INITIAL_WEIGHTS
TEST_POLICY=dict(kind='mechanism',weights=INITIAL_WEIGHTS,checkpoint='test-mechanism')

def setup(name,others=(),opponent='攻击强化',rich=False):
 b=StrictBattle(([name,*others],[opponent,'防御强化','护盾']),seed=19,trace=True)
 b.policy_configs=(TEST_POLICY,TEST_POLICY)
 for s in b.players:
  s.pile=list(s.instances);s.hand=[s.pile.pop(0)];s.stage=1;s.energy=100
 if rich:
  s,e=b.players;s.hp=400;s.shield=250;e.shield=150;e.poison=6
  element=CARDS[name].element;s.specialization=element if element in ELEMENTS else 'fire'
  for el in ELEMENTS:s.layers[el]=5
  s.active.add(SPECIAL[s.specialization]);s.ember=3 if s.specialization=='fire' else 0
  s.active.add({'fire':'灰烬循环','water':'潮汐回响','earth':'大地之握','wind':'风痕','poison':'蚀骨'}[s.specialization])
  s.tide=75 if s.specialization=='water' else 0
 return b

def one(b,both=False):
 used=set()
 def choose(shadow,i):
  if i in used or i==1 and not both:return None
  used.add(i);return shadow.players[i].hand[0]
 with patch('tools.sim_v12.policy.choose_play',side_effect=choose):return b.plan_stage()

class CurrentTests(unittest.TestCase):
 def test_current_inventory_and_all_card_dispatch(self):
  self.assertEqual((len(CARDS),verify_registry(),len(Pool().tokens)),(230,230,870))
  retired={'圣盾','愈合之光','战术大师','治愈洪流','破军','破障法阵','盾墙','蓄势','稳固结界'}
  self.assertFalse(retired&CARDS.keys())
  self.assertTrue(all(copies(CARDS[n])==0 for n in START_ONLY))

 def test_all_cards_execute_both_resource_contexts(self):
  for name in CARDS:
   for rich in (False,True):
    with self.subTest(name=name,rich=rich):
     b=setup(name,('火花','掠影','护盾','短促'),rich=rich)
     s=b.players[0];s.discard.append(s.pile.pop())
     b.resolve_sequences(one(b))
     self.assertEqual(b.executed[name],1)
     for p in b.players:p.assert_instances()

 def test_earth_execute_spends_shield_and_consumes_existing_guard(self):
  b=setup('护盾');s,e=b.players
  s.active.add('不周山');s.layers['earth']=100;e.hp=10;e.fx['lifeguard']=1
  b.resolve_sequences(one(b))
  s,e=b.players
  self.assertEqual((s.shield_total,s.defense,e.hp,e.guard_used),(0,0,1,True))
  self.assertNotIn(1,b._cut)

 def test_new_guard_does_not_protect_current_position(self):
  b=setup('潮汐风暴',opponent='气旋护壁');s,e=b.players
  s.active.add('潮汐之心');s.tide=1000
  b.resolve_sequences(one(b,True))
  self.assertLessEqual(b.players[1].hp,0);self.assertFalse(b.players[1].guard_used)

 def test_new_shield_does_not_absorb_current_position(self):
  b=setup('潮汐风暴',opponent='护盾');s,e=b.players
  s.active.add('潮汐之心');s.tide=100
  b.resolve_sequences(one(b,True))
  self.assertEqual((b.players[1].hp,b.players[1].shield_total),(890,60))

 def test_source_panels_and_first_layers_are_not_in_own_effect(self):
  b=setup('万毒爆');s,e=b.players;s.layers['poison']=10;e.poison=3
  b.resolve_sequences(one(b))
  self.assertEqual(b.players[1].hp,900)
  self.assertEqual(b.players[0].layers['poison'],11)

 def test_own_gain_then_consume_retains_explicit_card_order(self):
  b=setup('碎盾术',opponent='护盾');s,e=b.players
  s.active.add('不周山');s.layers['earth']=10;e.defense=0
  b.resolve_sequences(one(b,True))
  self.assertEqual((b.players[1].hp,b.players[1].shield_total),(982,60))

 def test_old_shield_decay_and_new_shield_are_distinguished(self):
  b=setup('碎盾术',opponent='护盾');s,e=b.players
  s.active.add('不周山');s.layers['earth']=10;e.defense=0;e.shield=100
  b.resolve_sequences(one(b,True))
  self.assertEqual((b.players[1].hp,b.players[1].shield_total),(1000,117))

 def test_new_heal_cannot_save_same_position_lethal_damage(self):
  b=setup('潮汐风暴',opponent='水膜');s,e=b.players
  s.active.add('潮汐之心');s.tide=80;e.hp=50;e.defense=0
  b.resolve_sequences(one(b,True))
  self.assertLessEqual(b.players[1].hp,0)

 def test_new_revive_cannot_save_same_position_death(self):
  b=setup('潮汐风暴',opponent='时光倒流');s,e=b.players
  s.active.add('潮汐之心');s.tide=1000
  b.resolve_sequences(one(b,True))
  self.assertLessEqual(b.players[1].hp,0);self.assertFalse(b.players[1].revived)

 def test_existing_revive_truncates_tail_and_keeps_private_prefix(self):
  b=setup('潮汐风暴',opponent='灵感涌现');s,e=b.players
  s.active.add('潮汐之心');s.tide=1000;e.rewind=(0,Q(100),Q(40),500,0)
  seq=b.plan_stage();b.resolve_sequences(seq)
  self.assertTrue(b.players[1].revived)
  self.assertEqual(sum(b.executed_by_seat[1].values()),1)
  self.assertEqual(b.players[1].hand,seq[1][0].after['hand'])

 def test_poison_merge_keeps_new_layers(self):
  b=setup('毒瓶',opponent='风之躯');b.players[1].poison=3
  b.resolve_sequences(one(b,True));self.assertEqual(b.players[1].poison,2)

 def test_promised_draw_is_not_lost_at_full_health(self):
  b=setup('活水',('火花',));b.players[0].hp=900
  seq=one(b);b.players[0].hp=1000;b.resolve_sequences(seq)
  self.assertEqual(b.players[0].hand,seq[0][0].after['hand'])

 def test_revealed_topdeck_tracker_never_reads_future_random_order(self):
  b=setup('检索附魔',('火花','风刃','燃页'))
  s=b.players[0];b.search(s,lambda c:True,3)
  self.assertEqual(s.known_top,[s.pile[0].uid])
  b.draw(s,1);self.assertFalse(s.known_top)
  b.search(s,lambda c:True,3);b.shuffle(s);self.assertFalse(s.known_top)

 def test_policy_does_not_read_unrevealed_deck_order(self):
  from .policy import choose_play
  b=setup('风刃',('穿甲','掠影','护盾','毒瓶'))
  s=b.players[0];s.hand.extend(s.pile[:2]);s.pile=s.pile[2:]
  before=choose_play(b,0).uid;s.pile.reverse()
  self.assertEqual(choose_play(b,0).uid,before)

 def test_conditional_wind_fee_is_prepared_before_tailwind(self):
  b=setup('顺风',('风刃','轻羽','掠影'))
  s=b.players[0];s.hand.extend(s.pile);s.pile=[];s.energy=3
  seq=b.plan_stage()[0];names=[x.name for x in seq]
  self.assertGreaterEqual(names.index('顺风'),2)

 def test_discard_prefers_unaffordable_filler_to_live_engine(self):
  b=setup('通晓',('灵感涌现','短促','不坏壁垒'))
  s=b.players[0];s.hand.extend(s.pile);s.pile=[];s.energy=1
  chosen=b.choose(s,s.hand[1:],1,'discard')
  self.assertNotEqual(chosen[0].name,'灵感涌现')

 def test_new_generic_ability_has_nonzero_mechanism_utility(self):
  from .tournament import Player
  from .policy import draft_value
  p=Player(0,'fire');p.spec='fire'
  p.policy=TEST_POLICY
  self.assertGreater(draft_value(p,'禁忌知识',[]),8)

 def test_ai_can_leave_mana_positive_two_card_recycling(self):
  b=setup('穿甲',('风神之翼',));s=b.players[0]
  s.energy=5;s.spent=4;s.played=4
  seq=b.plan_stage()
  self.assertLess(len(seq[0]),20)
  self.assertGreater(len(seq[0]),1)
  self.assertTrue(b.cycle_decisions[0]['voluntary_end'])
  b.resolve_sequences(seq)
  self.assertEqual(sum(b.executed_by_seat[0].values()),len(seq[0]))

if __name__=='__main__':unittest.main()
