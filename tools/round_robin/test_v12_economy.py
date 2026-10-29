"""New economy boundaries and compatibility of unchanged operations."""
import unittest
from draft_economy import (CURRENT, PREVIOUS, GUARANTEE_ROUNDS, LATE_FOUR_ROUNDS, study_income, purchase_price,
                           deletion_limit, deletion_price)

class EconomyTests(unittest.TestCase):
    def test_restored_late_income_keeps_v5_history_and_other_rules(self):
        for r in range(1,101):
            self.assertEqual(study_income(r,LATE_FOUR_ROUNDS),2 if r<=3 else 3 if r<=7 else 4)
            self.assertEqual(study_income(r,GUARANTEE_ROUNDS),2 if r<=3 else 4 if r in (8,10,12) else 3)
            self.assertEqual(deletion_limit(r,LATE_FOUR_ROUNDS),deletion_limit(r,GUARANTEE_ROUNDS))
            for used in range(3):self.assertEqual(deletion_price(r,used,LATE_FOUR_ROUNDS),deletion_price(r,used,GUARANTEE_ROUNDS))
            for rarity,price in (('common',1),('rare',2),('epic',3),('legendary',4)):
                for used in (False,True):self.assertEqual(purchase_price(price,rarity,r,used,LATE_FOUR_ROUNDS),purchase_price(price,rarity,r,used,GUARANTEE_ROUNDS))

    def test_guarantee_round_income_and_old_profile_compatibility(self):
        for r in range(1, 101):
            expected=2 if r<=3 else 4 if r in (8,10,12) else 3
            self.assertEqual(study_income(r,GUARANTEE_ROUNDS),expected)
            self.assertEqual(study_income(r,CURRENT),2 if r<=3 else 3 if r<=7 else 4)

    def test_guarantee_profile_preserves_purchase_and_deletion_rules(self):
        for r in range(1, 31):
            for rarity,price in [('common',1),('rare',2),('epic',3),('legendary',4)]:
                for used in (False,True):
                    self.assertEqual(purchase_price(price,rarity,r,used,GUARANTEE_ROUNDS),purchase_price(price,rarity,r,used,CURRENT))
            self.assertEqual(deletion_limit(r,GUARANTEE_ROUNDS),deletion_limit(r,CURRENT))
            for used in range(4):
                self.assertEqual(deletion_price(r,used,GUARANTEE_ROUNDS),deletion_price(r,used,CURRENT))

    def test_income_boundaries(self):
        self.assertEqual([study_income(r) for r in range(1, 10)],
                         [2, 2, 2, 3, 3, 3, 3, 4, 4])
        self.assertEqual([study_income(r, PREVIOUS) for r in range(1, 10)],
                         [2, 2, 3, 3, 3, 4, 4, 4, 4])

    def test_free_purchase_both_faces(self):
        for r in range(1, 21):
            for rarity, price in [('common', 1), ('rare', 2), ('epic', 3), ('legendary', 4)]:
                free = (r <= 2 and rarity == 'common') or (3 <= r <= 4 and rarity in ('common', 'rare'))
                self.assertEqual(purchase_price(price, rarity, r, False, CURRENT), 0 if free else price)
                self.assertEqual(purchase_price(price, rarity, r, True, CURRENT), price)

    def test_deletion_unchanged(self):
        for r in range(1, 21):
            self.assertEqual(deletion_limit(r, CURRENT), deletion_limit(r, PREVIOUS))
            for used in range(4):
                self.assertEqual(deletion_price(r, used, CURRENT), deletion_price(r, used, PREVIOUS))

if __name__ == '__main__':
    unittest.main()
