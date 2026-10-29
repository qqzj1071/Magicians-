"""Focused v1.1 formula checks; no full tournament is run here."""
import os
from pathlib import Path
import unittest
from fractions import Fraction as Q
os.environ["MAGICIANS_CARD_LIBRARY"]=str(Path(__file__).resolve().parents[2]/"decks/trained-v1.1-poison.json")
import engine as E

class FormulaTests(unittest.TestCase):
    def test_echo_records_actual_heal_and_water_layers(self):
        s=E.State("water",route="潮汐回响",spec=True,layers=5,hp=950)
        self.assertEqual(E.heal(s,100),50)
        self.assertEqual(s.tide,20)
        E.heal(s,100)
        self.assertEqual(s.tide,20)

    def test_bastion_absorption_reflection_coefficient(self):
        source=E.State("fire",defense=40)
        target=E.State("earth",route="壁垒之心",spec=True,layers=10)
        p=E.packet([source,target],0,100)
        self.assertEqual(p.reflect_coeff,Q(1,4))
        self.assertEqual(p.reflect_defense,20)
        self.assertTrue(p.wall)

    def test_bone_plague_both_coefficients(self):
        s=E.State("poison",route="蚀骨",spec=True,layers=5)
        t=E.State("fire",attack=100,defense=100,poison=4)
        self.assertEqual(E.stats([s,t],1),(86,90))

    def test_poison_burst_card_damage_and_consumption(self):
        for name,mult in [("万毒爆",2),("毒潮",Q(5,2)),("毒爆弹",Q(3,2))]:
            with self.subTest(card=name):
                s=E.State("poison",layers=4,attack=100,energy=10)
                t=E.State("fire",defense=40,poison=5)
                c=E.CARDS[name];p=E.card_plan([s,t],0,name,0)
                expected=Q(100+c.attack)*Q(2,100)*(4+c.layers)*5*mult-20
                self.assertEqual(p.packets[0].raw,expected)
                self.assertEqual(p.local[1].poison,0)

    def test_arrow_independent_ignore_and_shield_bonus(self):
        s=E.State("wind",route="穿云箭",spec=True,layers=2,attack=200)
        t=E.State("earth",defense=100)
        p=E.missile([s,t],0,0,main=True)
        self.assertEqual(p.raw,Q(592,5))  # 200 - 100 * (1 - 0.04) * (1 - 0.15)
        self.assertEqual(p.shield_multiplier,Q(115,100))

    def test_adjusted_support_cards_use_effective_values(self):
        fire=E.State("fire",spec=True,attack=100,energy=10,ember=2)
        enemy=E.State("earth")
        self.assertEqual(E.card_plan([fire,enemy],0,"慢燃",0).local[0].bonus,30)
        self.assertEqual(E.card_plan([fire,enemy],0,"压缩爆燃",0).local[0].bonus,45)
        water=E.State("water",spec=True,route="潮汐回响",hp=500,layers=5,energy=10)
        storm=E.card_plan([water,enemy],0,"潮汐风暴",0).local[0]
        self.assertEqual(storm.hp,585)
        self.assertEqual(storm.tide_bonus,70)
        earth=E.State("earth",spec=True,shield=100,energy=10)
        self.assertEqual(E.card_plan([earth,enemy],0,"回震岩甲",0).local[0].shield,225)

    def test_final_interval_floors_half_units(self):
        s=E.State("wind",route="疾风之刃",spec=True,layers=3)
        self.assertEqual(E.gap(s),39)
        self.assertEqual(E.param("blade_follow_percent",50),20)

if __name__=="__main__":
    unittest.main()
