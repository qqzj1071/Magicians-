"""Requested pass4 mechanics, gate/rounding and card-value invariants."""
import os,json,unittest
from pathlib import Path
from fractions import Fraction as Q
os.environ['MAGICIANS_CARD_LIBRARY']=str(Path(__file__).resolve().parents[2]/'decks/trained-v1.1-poison.json')
import engine as E
class Pass4Tests(unittest.TestCase):
 def test_cycle_gate_gain_and_cap(self):
  s=E.State('fire',route='灰烬循环',spec=False)
  E.shuffled(s);self.assertEqual(s.ember,0)
  s.spec=True
  for n in (2,4,5):E.shuffled(s);self.assertEqual(s.ember,n)
 def test_echo_bonuses_and_refund(self):
  s=E.State('water',route='潮汐回响',spec=True,hp=500,layers=5,energy=10)
  s=E.card_plan([s,E.State('earth')],0,'回响之潮',0).local[0]
  self.assertEqual((s.tide_bonus,s.tide_record_bonus),(40,50))
  s.hp=500;s.tide=0
  E.heal(s,100,record_bonus=s.tide_record_bonus)
  self.assertEqual(s.tide,100*Q(8,100)*s.layers*Q(3,2))
  s=E.State('water',route='潮汐回响',spec=True,tide=100,layers=0,attack=100)
  s=E.launch([s,E.State('fire',defense=0)], [0],0)[0]
  self.assertEqual(s.tide,25)
  self.assertEqual((s.tide_bonus,s.tide_record_bonus),(0,0))
 def test_life_poison_nonburst_only(self):
  s=E.State('poison',route='蚀命',spec=False,layers=0,attack=0)
  t=E.State('fire',defense=20,poison=3)
  self.assertEqual(E.poison_packet([s,t],0).raw,20)
  self.assertEqual(E.poison_packet([s,t],0,explode=True).raw,-10)
 def test_rock_defense_and_return(self):
  s=E.State('fire',attack=200,defense=100)
  t=E.State('earth',route='反震岩核',spec=True,layers=20,shield=100)
  p=E.packet([s,t],0,200);self.assertEqual(p.reflect_defense,50)
  reactions=[];E.apply_wave([s,t],[p],0,reactions=reactions)
  self.assertEqual((reactions[0].retaliation,reactions[0].return_shield),(40,40))
  t=E.State('earth',route='反震岩核',spec=True,layers=20,shield=100,energy=10)
  plan=E.card_plan([t,s],0,'岩核爆破',0)
  self.assertEqual(plan.consume_defense,50)
 def test_arrow_base_shield_penetration_only(self):
  for spec,expected in [(False,Q(15,100)),(True,Q(30,100))]:
   self.assertEqual(E.shield_pen(E.State('wind',route='穿云箭',specialization_selected=spec,layers=10)),expected)
 def test_interval_floor_and_compensation(self):
  self.assertEqual(E.gap(E.State('wind',spec=True,layers=3)),43)
  self.assertEqual(E.gap(E.State('water',route='生命之泉',layers=3)),44)
  before=json.loads((Path(__file__).resolve().parents[2]/'research/v1.1-route-pass4-20261027/before.cards.json').read_text(encoding='utf-8-sig'))['cards']
  for name in ('气旋护壁','疾风连斩','裂空','风神之翼'):
   s=E.card_plan([E.State('wind',energy=10),E.State('earth')],0,name,0).local[0]
   self.assertEqual(s.permanent_delay,-1)
   self.assertEqual(E.CARDS[name].attack,before[name]['attack']+1)
 def test_all_integer_values_within_bands(self):
  bands={'common':(5,6),'rare':(7.5,9),'epic':(9.5,11),'legendary':(11.5,13.5),'specialization':(14,16)}
  for n,c in E.CARDS.items():
   if n=='守势':continue
   self.assertIsInstance(c.attack,int);self.assertIsInstance(c.defense,int)
   v=(c.attack+1.5*c.defense)/((c.cost+1)/2);lo,hi=bands[c.rarity]
   self.assertTrue(lo<=v<=hi,(n,v))
if __name__=='__main__':unittest.main()
