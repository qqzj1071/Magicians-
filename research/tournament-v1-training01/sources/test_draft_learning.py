import copy,unittest
import draft_learning as D
from learning_core import *

class Draft(unittest.TestCase):
 def model(self):return dict(card_rewards={},weights={},coefficient_scale=4)
 def test_rejects_duplicate_other_element_and_other_route(self):
  d=copy.deepcopy(C.DECKS['fire-01']);m=self.model()
  self.assertIsNone(D.offer_score(d,d['route'],m))
  self.assertIsNone(D.offer_score(d,'潮汐风暴',m))
  self.assertIsNone(D.offer_score(d,'余烬之核',m))
  self.assertIsNone(D.offer_score(d,'元素熔炉',m))
 def test_all_curricula_can_produce_legal_decks(self):
  for i,a in enumerate(IDS):
   d,log=D.generate_deck(C.DECKS[a],self.model(),123000+i)
   self.assertTrue(legal(d),a);self.assertEqual(len(log),20)
   self.assertTrue(all(x['choice'] in x['offer'] for x in log))
 def test_legendary_cap_suggests_replacement(self):
  # Use the immutable fixture: a learned deck may rely on both legends for its
  # minimum draw/search coverage, legitimately making every replacement illegal.
  reference=read(ROOT/'decks/decks.json')
  d=next(x for x in reference['decks'] if x['id']=='fire-01');names={e['name'] for e in d['entries']}
  other=next(n for n,c in C.CARDS.items() if c.rarity=='legendary' and c.element=='generic' and n not in names and n not in UNSUPPORTED)
  options=D.choose_offer(d,[other],self.model())
  self.assertTrue(options);self.assertTrue(all(x['replace'] and C.CARDS[x['replace']].rarity=='legendary' for x in options))
 def test_feature_regression_shrinks_small_samples(self):
  w=D.fit([({'x':1},.5)],['x'],12);self.assertLess(w['x'],.05)

if __name__=='__main__':unittest.main()
