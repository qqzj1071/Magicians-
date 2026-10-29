"""Versioned construction prices; battle mana and rarity odds are unchanged."""

REVISED='growth-v2'
LEGACY='legacy-v1'
CURRENT='growth-v3'


def free_purchase_rarities(round_num,profile=REVISED):
    if profile==CURRENT:
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
    if profile not in (REVISED,CURRENT):raise ValueError(profile)
    return 0 if round_num<=3 else 1 if round_num<=6 else 2


def deletion_price(round_num, deleted_this_round, profile=REVISED):
    if deleted_this_round>=deletion_limit(round_num,profile):return None
    if profile==LEGACY:return 0
    return 0 if deleted_this_round==0 and (round_num>=7 or profile==CURRENT and round_num>=4) else 1
