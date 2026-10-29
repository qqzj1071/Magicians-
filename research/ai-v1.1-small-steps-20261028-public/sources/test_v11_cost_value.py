import os
from pathlib import Path
import unittest
from unittest.mock import patch
from fractions import Fraction as Q
os.environ["MAGICIANS_CARD_LIBRARY"]=str(Path(__file__).resolve().parents[2]/"decks/trained-v1.1-poison.json")
import engine as E

class CostValueMechanicTests(unittest.TestCase):
    def test_ash_rebirth_requires_played_specialization_then_repeats(self):
        s=E.State("fire",energy=30,spec=False,specialization_selected=True,route="灰烬循环")
        for _ in range(2):
            s=E.card_plan([s,E.State("earth")],0,"灰烬重生",0).local[0]
            self.assertEqual(s.ember,0)
            E.assert_state([s])
        s=E.card_plan([s,E.State("earth")],0,"炽焰王冠",0).local[0]
        self.assertTrue(s.spec)
        s.route="";s.ember=0
        for expected in (1,2,3):
            s=E.card_plan([s,E.State("earth")],0,"灰烬重生",0).local[0]
            self.assertEqual(s.ember,expected)
            E.assert_state([s])
        s.route="灰烬循环";s.ember=0
        s=E.card_plan([s,E.State("earth")],0,"灰烬重生",0).local[0]
        self.assertEqual(s.ember,3) # shuffle passive plus the card, after specialization

    def test_pre_specialization_ember_is_still_invalid(self):
        with self.assertRaises(AssertionError):
            E.assert_state([E.State("fire",spec=False,ember=1,seen=frozenset({"灰烬重生"}))])
        with self.assertRaises(AssertionError):
            E.assert_state([E.State("fire",spec=True,ember=6)])

    def test_bloodline_ember_bonus_requires_specialization(self):
        s=E.State("fire",route="燃烧血统",layers=4,spec=False)
        self.assertEqual(E.ember_factor(s,2),1)
        s.spec=True
        self.assertEqual(E.ember_factor(s,2),Q(124,100))
        s.route="余烬之核"
        self.assertEqual(E.ember_factor(s,2),Q(120,100))

    def test_chase_window_expires_at_fifty(self):
        for elapsed,expected in [(0,40),(25,20),(50,0),(75,0)]:
            s=E.State("wind",route="疾风之刃",last_main=200,last_time=0)
            with patch.object(E,"missile",wraps=E.missile) as missile:
                E.launch([s,E.State("earth")],[0],elapsed)
                self.assertEqual(missile.call_args.args[4],expected)

    def test_grip_only_records_real_old_shield_decay(self):
        s=E.State("earth",route="大地之握",shield=100)
        E.ordinary_shield(s,50)
        self.assertEqual(s.shield_loss,25)
        with patch.object(E,"missile",wraps=E.missile) as missile:
            E.launch([s,E.State("fire")],[0],0)
            self.assertEqual(missile.call_args.args[4],75)

    def test_bloodline_base_ratio_applies_to_main_shot(self):
        with patch.object(E,"missile",wraps=E.missile) as missile:
            E.launch([E.State("fire",route="燃烧血统"),E.State("earth")],[0],0)
            self.assertEqual(missile.call_args.args[3],Q(18,10))

if __name__=="__main__":unittest.main()
