"""Ranking regressions: later elimination, signed HP, ties and double knockout."""
import unittest
from run_v11_balance_test import compact_episode


def player(pid, hp, round_id=None):
    p = dict(pid=pid, tournament_hp=hp, spec="wind", route="route")
    if round_id is not None:
        p["eliminated_round"] = round_id
    return p


def ranked(dead, champions):
    return compact_episode(dict(index=0, end_round=16, rounds=[], eliminated=dead, champions=champions))["placements"]


class RankingTests(unittest.TestCase):
    def test_later_elimination_ranks_higher(self):
        result = ranked([player(0,-1,10),player(1,-20,14),player(2,-80,15)], [player(3,1)])
        self.assertEqual([(p["pid"],p["points"]) for p in result], [(3,3),(2,1),(1,-1),(0,-3)])

    def test_same_round_uses_signed_remaining_hp(self):
        result = ranked([player(0,-1,10),player(1,0,14),player(2,-2,14)], [player(3,1)])
        self.assertEqual([p["pid"] for p in result], [3,1,2,0])

    def test_double_knockout_is_not_duplicated(self):
        dead=[player(0,-1,10),player(1,-2,14),player(2,-10,16),player(3,-3,16)]
        result = ranked(dead, dead[-2:])
        self.assertEqual([(p["pid"],p["points"]) for p in result], [(3,3),(2,1),(1,-1),(0,-3)])
        self.assertEqual(sum(p["win_share"] for p in result),1)

    def test_tie_averages_rank_points_and_win_share(self):
        dead=[player(0,-1,10),player(1,-2,14),player(2,-3,16),player(3,-3,16)]
        result=ranked(dead,dead[-2:])
        self.assertEqual([p["points"] for p in result],[2,2,-1,-3])
        self.assertEqual([p["win_share"] for p in result],[.5,.5,0,0])


if __name__ == "__main__":
    unittest.main()
