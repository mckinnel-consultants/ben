"""Regressions for natural games unnecessarily raised to the five level."""
import unittest

from acol.core import Auction, Call
from acol.system import choose_bid, interpret_call


class GameSignoffTests(unittest.TestCase):
    def test_recorded_production_games_are_passed_in_every_seat(self):
        cases = [
            ("KJ98.KQ5.T52.KQ5", "PASS 1N 2D 4S PASS"),
            ("AKJ83.A95.K953.9", "1N PASS 2D PASS 2H PASS PASS 2S PASS 4S PASS"),
            ("A3.AKT873.Q6.Q86", "1C PASS 1D 2H 3C 4H PASS"),
        ]
        for hand, bids in cases:
            for dealer in range(4):
                for vulnerability in ("None", "NS", "EW", "Both"):
                    with self.subTest(bids=bids, dealer=dealer, vulnerability=vulnerability):
                        a = Auction(bids.split(), dealer)
                        result = choose_bid(hand, a, vulnerability=vulnerability)
                        self.assertEqual(result.bid, "PASS", result)

    def test_natural_games_after_intervention_are_signoffs(self):
        for prefix, bid in [("1N 2D", "4H"), ("1N 2D", "4S"),
                            ("1N 2H", "5C"), ("1N 2H", "5D"),
                            ("1D 1S", "4H")]:
            with self.subTest(prefix=prefix, bid=bid):
                a = Auction(prefix.split())
                m = interpret_call(a, Call(a.turn, bid, len(a.calls)))
                self.assertFalse(m.artificial)
                self.assertEqual(m.forcing, "signoff")

    def test_below_game_jump_responses_and_cues_stay_forcing(self):
        for prefix, bid, expected in [("1N 2D", "2S", "signoff"),
                                      ("1N 2D", "3S", "one-round"),
                                      ("1D 1S", "2H", "one-round"),
                                      ("1N 2H", "3H", "game")]:
            with self.subTest(prefix=prefix, bid=bid):
                a = Auction(prefix.split())
                self.assertEqual(interpret_call(a, Call(a.turn, bid, len(a.calls))).forcing,
                                 expected)

    def test_overcaller_accepts_major_and_minor_games(self):
        for hand, bids in [
            ("AKJ83.A95.K953.9", "1C 1S PASS 4S PASS"),
            ("A3.AKT873.Q6.Q86", "1C 1H PASS 4H PASS"),
            ("Q6.Q86.A3.AKT873", "1H 2C PASS 5C PASS"),
            ("Q6.Q86.AKT873.A3", "1H 2D PASS 5D PASS"),
        ]:
            with self.subTest(bids=bids):
                self.assertEqual(choose_bid(hand, Auction(bids.split())).bid, "PASS")

    def test_overcaller_can_accept_invitation_and_compete_after_game(self):
        hand = "A3.AKT873.Q6.Q86"
        for bids, expected in [("1C 1H PASS 3H PASS", "4H"),
                               ("1C 1H PASS 4H 5C", "5H")]:
            with self.subTest(bids=bids):
                self.assertEqual(choose_bid(hand, Auction(bids.split())).bid, expected)

    def test_overcaller_answers_forcing_cue(self):
        a = Auction("1D 1S PASS 2D PASS".split())
        self.assertEqual(choose_bid("AKJ83.A95.K953.9", a).bid, "2S")

    def test_genuine_slam_enquiries_and_replies_remain_available(self):
        a = Auction("1C 1S PASS 4S PASS".split())
        self.assertEqual(choose_bid("AKQJ8.AK5.AK9.K5", a).bid, "4N")
        a = Auction("1S PASS 3S PASS 4N PASS".split())
        self.assertEqual(choose_bid("KJ76.AQ4.J74.Q87", a).bid, "5H")
        self.assertEqual(choose_bid("KQ76.AQ4.J74.Q87", a).bid, "5S")


if __name__ == "__main__":
    unittest.main()
