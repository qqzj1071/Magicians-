import os,unittest,random,json
from pathlib import Path
os.environ['MAGICIANS_CARD_LIBRARY']=str(Path(__file__).resolve().parents[2]/'decks/trained-v1.1-poison.json')
import engine as E
class Pass6Tests(unittest.TestCase):
 def play(self,s,n):return E.card_plan([s,E.State('earth')],0,n,0).local[0]
 def test_both_startup_orders_and_gate(self):
  s=E.State('fire',energy=20,ash_cycle_owned=True)
  s=self.play(s,'灰烬循环');self.assertEqual(s.ember,0);E.assert_state([s])
  s=self.play(s,'炽焰王冠');self.assertEqual(s.ember,0)
  s=E.State('fire',energy=20,ash_cycle_owned=True)
  s=self.play(s,'炽焰王冠');self.assertEqual(s.ember,0)
  s=self.play(s,'灰烬循环');self.assertEqual(s.ember,0)
 def test_no_bonus_without_route_ownership_and_cap(self):
  s=self.play(E.State('fire',energy=20),'炽焰王冠');self.assertEqual(s.ember,0)
  s=self.play(E.State('fire',energy=20,spec=True,ember=4,ash_cycle_owned=True),'灰烬循环');self.assertEqual(s.ember,4)
 def fighter(self,pile,pool=(),removed=(),drawn=()):
  return E.Fighter('test',list(pile),random.Random(1),random.Random(2),pool=list(pool),removed=list(removed),drawn_this_window=frozenset(drawn))
 def test_link_moves_existing_counterpart_both_directions(self):
  for played,target in [('灰烬循环','炽焰王冠'),('炽焰王冠','灰烬循环')]:
   p=self.fighter(['攻击强化',target,'防御强化']);before=sorted(p.pile)
   E.ash_link_topdeck(p,played,0)
   self.assertEqual(p.pile,[target,'攻击强化','防御强化']);self.assertEqual(sorted(p.pile),before)
 def test_link_respects_drawn_and_exhausted_and_missing(self):
  for p in [self.fighter(['攻击强化','炽焰王冠'],drawn=['炽焰王冠']),self.fighter(['攻击强化'],removed=['炽焰王冠']),self.fighter(['攻击强化'],pool=['炽焰王冠']),self.fighter(['攻击强化'])]:
   before=(p.pile[:],p.pool[:],p.removed[:]);E.ash_link_topdeck(p,'灰烬循环',0)
   self.assertEqual((p.pile,p.pool,p.removed),before)
 def test_draw_membership_is_per_window(self):
  p=self.fighter(['炽焰王冠','攻击强化','防御强化','火花','火星','灰烬循环'],drawn=['灰烬循环'])
  E.draw_player(p,E.State('fire'),100)
  self.assertIn('炽焰王冠',p.drawn_this_window);self.assertNotIn('灰烬循环',p.drawn_this_window)
 def test_description_cleanup_does_not_change_first_play_layers(self):
  names=['寻毒','毒刺','毒瓶','毒甲','毒雾','腐蚀']
  data=json.loads((Path(__file__).resolve().parents[2]/'releases/v1.1/cards.json').read_text(encoding='utf-8-sig'))['cards']
  for n in names:
   self.assertNotIn('附魔层数 +1',data[n]['text'])
   s=E.State('poison',energy=20);s=self.play(s,n);self.assertEqual(s.layers,1)
   s=self.play(s,n);self.assertEqual(s.layers,1)
 def test_research_adapter_deck_identity_and_startup_integration(self):
  from shared_draft_combat import ENGINE as R
  import cards as C
  route=next(n for n,d in C.DECKS.items() if any(x['name']=='灰烬循环' for x in d['entries']))
  other=next(n for n,d in C.DECKS.items() if d['element']=='earth')
  p,s=R.make_fighter(route,1)
  self.assertEqual(s.deck_id,route)
  result=R.simulate(route,other,1,trace=True,validate=True)
  self.assertTrue(result)
if __name__=='__main__':unittest.main()
