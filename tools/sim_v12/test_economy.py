"""Small deterministic checks of the live construction-income rule."""
import json
import unittest
from pathlib import Path
from .catalog import ROOT
from .tournament import ECONOMY,base_income
from tools.round_robin.draft_economy import PAID_EARLY_DELETE,study_income

class IncomeTests(unittest.TestCase):
 def test_actual_simulator_income_through_round_100(self):
  for r in range(1,101):
   expected=2 if r<=3 else 3 if r<=7 else 4
   with self.subTest(round=r):
    self.assertEqual(base_income(r),expected)
    self.assertEqual(base_income(r),study_income(r,PAID_EARLY_DELETE))
  with self.assertRaises(ValueError):base_income(0)

 def test_published_and_live_configuration_are_identical(self):
  published=json.loads((ROOT/'releases/deckbuilding-v1.2/economy.json').read_text(encoding='utf-8'))
  self.assertEqual(published,ECONOMY)
  self.assertEqual(ECONOMY['implementation_profile'],PAID_EARLY_DELETE)
  self.assertEqual(ECONOMY['carry_cap'],2)
  self.assertEqual(ECONOMY['streak_bonus_every'],3)
  self.assertEqual(ECONOMY['free_purchase'],dict(rounds_1_to_2=['common'],rounds_3_to_4=['common','rare'],scope='one_per_round_both_faces'))
  self.assertEqual(ECONOMY['deletions'],dict(rounds_1_to_3=[0,[]],rounds_4_to_6=[1,[1]],rounds_7_plus=[2,[0,1]]))
  probabilities=json.loads((Path(__file__).parent/'rules/probabilities.json').read_text(encoding='utf-8'))
  self.assertEqual(probabilities['economy_profile'],PAID_EARLY_DELETE)

if __name__=='__main__':unittest.main()
