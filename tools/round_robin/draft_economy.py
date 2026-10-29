"""Versioned construction prices; battle mana and rarity odds are unchanged."""

REVISED='growth-v2'
LEGACY='legacy-v1'
PREVIOUS='growth-v3'
CURRENT='growth-v4'
GUARANTEE_ROUNDS='growth-v5'
LATE_FOUR_ROUNDS='growth-v6'
PAID_EARLY_DELETE='growth-v7'


def free_purchase_rarities(round_num,profile=REVISED):
    if profile in (CURRENT,GUARANTEE_ROUNDS,LATE_FOUR_ROUNDS,PAID_EARLY_DELETE):
        return ('common',) if 1<=round_num<=2 else ('common','rare') if 3<=round_num<=4 else ()
    if profile==PREVIOUS:
        return ('common',) if 1<=round_num<=3 else ('common','rare') if 4<=round_num<=6 else ()
    rarity=free_purchase_rarity(round_num,profile)
    return (rarity,) if rarity else ()


def is_free_purchase(rarity,round_num,free_used,profile=REVISED):
    return not free_used and rarity in free_purchase_rarities(round_num,profile)


def free_purchase_rarity(round_num, profile=REVISED):
    if profile==LEGACY:return None
    if profile!=REVISED:raise ValueError(profile)
    if 1<=round_num<=3:return 'common'
    if 4<=round_num<=6:return 'rare'
    return None


def purchase_price(base_price, rarity, round_num, free_used, profile=REVISED):
    return 0 if is_free_purchase(rarity,round_num,free_used,profile) else base_price


def deletion_limit(round_num, profile=REVISED):
    if profile==LEGACY:return 1 if round_num<=5 else 2
    if profile not in (REVISED,PREVIOUS,CURRENT,GUARANTEE_ROUNDS,LATE_FOUR_ROUNDS,PAID_EARLY_DELETE):raise ValueError(profile)
    return 0 if round_num<=3 else 1 if round_num<=6 else 2


def deletion_price(round_num, deleted_this_round, profile=REVISED):
    if deleted_this_round>=deletion_limit(round_num,profile):return None
    if profile==LEGACY:return 0
    if profile==PAID_EARLY_DELETE and 4<=round_num<=6:return 1
    return 0 if deleted_this_round==0 and (round_num>=7 or profile in (PREVIOUS,CURRENT,GUARANTEE_ROUNDS,LATE_FOUR_ROUNDS,PAID_EARLY_DELETE) and round_num>=4) else 1


def study_income(round_num, profile=CURRENT):
    if round_num < 1: raise ValueError(round_num)
    if profile in (LATE_FOUR_ROUNDS,PAID_EARLY_DELETE):
        return 2 if round_num<=3 else 3 if round_num<=7 else 4
    if profile==GUARANTEE_ROUNDS:
        return 2 if round_num<=3 else 4 if round_num in (8,10,12) else 3
    return (2 if round_num<=3 else 3 if round_num<=7 else 4) if profile==CURRENT else (2 if round_num<=2 else 3 if round_num<=5 else 4)
