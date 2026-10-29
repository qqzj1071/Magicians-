from fractions import Fraction as Q
from unittest.mock import patch
import unittest
from .test_current import setup,one

class RouteBalanceTests(unittest.TestCase):
 def test_blood_tide_surge_forty_percent_boundary(self):
  for hp,expected in ((400,90),(401,60)):
   b=setup('血潮汹涌');s=b.players[0];s.hp=hp;s.layers['water']=10;s.active.add('潮汐之心')
   b.resolve_sequences(one(b));self.assertEqual(b.players[0].tide,expected)

 def test_earth_grip_uses_recorded_decay_loss(self):
  b=setup('大地之握');s=b.players[0];s.active.add('大地之握');s.fx['grip_loss']=25
  packets=[]
  with patch.object(b,'wave',side_effect=lambda ps:packets.extend(ps)):b.fire([0])
  self.assertEqual(packets[0]['raw'],125)

 def test_bastion_reflects_two_percent_per_layer(self):
  b=setup('攻击强化');s,e=b.players;s.defense=0;e.defense=0
  e.shield=1000;e.layers['earth']=10;e.active.update(('不周山','壁垒之心'))
  b.wave([b.packet(0,100,'missile')])
  self.assertEqual(s.hp,983)
  self.assertEqual(e.shield,915)

 def test_wind_layer_gap_and_activation_are_separate(self):
  b=setup('天岚');s=b.players[0];s.layers['wind']=10
  self.assertEqual(b.gap(s),45);self.assertEqual(b.missile_parameters(0)['pen'],0)
  s.specialization='wind';self.assertEqual(b.gap(s),40)
  s.active.add('天岚');self.assertEqual(b.gap(s),40)
  self.assertEqual(b.missile_parameters(0)['pen'],Q(1,4))
  s.active.add('疾风之刃');self.assertEqual(b.gap(s),35)
  s.active.add('穿云箭');p=b.missile_parameters(0)
  self.assertEqual((p['def_pen'],p['ignore'],p['shield_factor']),(Q(1,4),Q(15,100),Q(115,100)))
  s.layers['wind']=100;self.assertEqual(b.missile_parameters(0)['def_pen'],1)

 def test_poison_damage_and_dynamic_debuff(self):
  b=setup('万蚀');s,e=b.players;s.layers['poison']=10;e.poison=3
  self.assertEqual(b.poison_packets(0)[0]['raw'],60)
  s.specialization='poison';self.assertEqual(b.poison_packets(0)[0]['raw'],120)
  s.active.add('蚀命');self.assertEqual(b.poison_packets(0)[0]['raw'],270)
  s.active.add('万毒之源');self.assertEqual(b.stats(1),(83,29))
  s.active.add('蚀骨');self.assertEqual(b.stats(1),(68,20))

 def test_poison_growth_counts_actual_changes_both_directions(self):
  b=setup('毒龙');s,e=b.players;s.active.add('毒爆')
  b.change_poison(s,e,3);self.assertEqual(s.attack,106)
  b.change_poison(s,e,-10);self.assertEqual(s.attack,112)
  b.change_poison(s,e,-1);self.assertEqual(s.attack,112)

 def test_fire_bloodline_and_blood_tide_packets(self):
  b=setup('燃烧血统');s,e=b.players;s.active.update(('燃烧血统','炽焰王冠'));s.specialization='fire';s.layers['fire']=10;s.ember=2
  packets=[]
  with patch.object(b,'wave',side_effect=lambda ps:packets.extend(ps)):b.fire([0])
  self.assertEqual(packets[0]['raw'],200)
  self.assertEqual(packets[0]['final'],Q(12,10)*Q(18,10))
  b=setup('血潮');s,e=b.players;s.active.add('血潮');packets=[]
  with patch.object(b,'wave',side_effect=lambda ps:packets.extend(ps)):b.fire([0])
  self.assertEqual((s.hp,packets[0]['raw']),(950,175))

 def test_wind_marks_sum_and_true_sub_are_separate(self):
  b=setup('风痕');s,e=b.players;s.active.update(('天岚','风痕'));s.fx['shots']=2;e.wind_marks=6
  packets=[]
  with patch.object(b,'wave',side_effect=lambda ps:packets.extend(ps)):b.fire([0])
  self.assertEqual([p['raw'] for p in packets],[100,20,78])
  self.assertEqual(e.wind_marks,0)

 def test_echo_refunds_twenty_percent_of_actual_spent_tide(self):
  b=setup('潮汐回响');s=b.players[0];s.active.update(('潮汐回响','潮汐之心'));s.tide=100
  with patch.object(b,'wave'):b.fire([0])
  self.assertEqual((s.spent_tide,s.tide),(100,20))

 def test_spring_penetrates_shields_not_defense_and_stacks_with_wind(self):
  b=setup('生命之泉');s=b.players[0];s.active.add('生命之泉')
  self.assertEqual((b.missile_parameters(0)['def_pen'],b.missile_parameters(0)['pen']),(0,Q(1,5)))
  s.layers['wind']=10;s.active.add('天岚')
  self.assertEqual(b.missile_parameters(0)['pen'],Q(45,100))

 def test_erosion_max_hp_bonus_scales_with_both_layer_counts(self):
  b=setup('蚀命');s,e=b.players;s.active.add('蚀命');s.specialization='poison';e.max_hp=2000
  for own,target in ((1,3),(10,3),(10,6)):
   s.layers['poison']=own;e.poison=target
   self.assertEqual(b.poison_packets(0)[0]['raw'],100*own*target*Q(4,100)+2000*own*target*Q(5,1000))
  e.poison=0;self.assertEqual(b.poison_packets(0),[])

if __name__=='__main__':unittest.main()
