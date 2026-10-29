import os,unittest,random
from pathlib import Path
from fractions import Fraction as Q
os.environ['MAGICIANS_CARD_LIBRARY']=str(Path(__file__).resolve().parents[2]/'decks/trained-v1.1-poison.json')
import engine as E
class Pass5Tests(unittest.TestCase):
 def test_credit_per_draw_cap_and_reset(self):
  s=E.State('fire',spec=True,route='灰烬循环',ember=2,next_draw=1,next_energy=1)
  E.consume_ember(s,1);s.ember=5;E.consume_ember(s,5)
  p=E.Fighter('test',['攻击强化']*20,random.Random(1),random.Random(2))
  E.draw_player(p,s,100)
  self.assertEqual((len(p.pool),s.energy,s.ash_credit),(9,7,0))
  E.draw_player(p,s,200)
  self.assertEqual((len(p.pool),s.energy,s.ash_credit),(5,3,0))
 def test_only_actual_specialized_consumption_counts(self):
  s=E.State('fire',route='灰烬循环',ember=0,spec=True)
  E.consume_ember(s,5);self.assertEqual(s.ash_credit,0)
  s.spec=False;s.ember=3;E.consume_ember(s,3);self.assertEqual(s.ash_credit,0)
 def test_trace_step_applies_to_complete_detonation(self):
  s=E.State('wind',route='风痕',spec=True,shot_count=2,attack=100,layers=0)
  t=E.State('earth',defense=0,wind_marks=2)
  result=E.launch([s,t],[0],0)
  self.assertEqual(result[1].hp,850) # main100 + third20 + trace(8+10+12)
  self.assertEqual(result[1].wind_marks,0)
 def test_all_shield_bursts_lose_grip_penetration(self):
  for route,rate in [('',3),('大地之握',3),('壁垒之心',3),('反震岩核',Q(9,2))]:
   s=E.State('earth',route=route,spec=True,shield=100,layers=10,energy=10)
   t=E.State('fire',defense=40,shield=1000)
   plan=E.card_plan([s,t],0,'岩核爆破',0)
   self.assertEqual(plan.consume_coeff,Q(rate)*plan.local[0].layers/100)
   self.assertEqual(plan.consume_defense,20)
   self.assertEqual(plan.packets[0].penetration,0)
   self.assertEqual(E.shield_pen(s,'shield'),0)
 def test_heal_and_shield_tuning_preserves_triggers(self):
  s=E.State('water',hp=500,energy=10)
  self.assertEqual(E.card_plan([s,E.State('fire')],0,'生命洪流',0).local[0].hp,570)
  p=E.card_plan([E.State('earth',shield=100,energy=10),E.State('fire')],0,'不坏壁垒',0)
  self.assertEqual(p.local[0].shield,290)
if __name__=='__main__':unittest.main()
