"""Auction fixtures for EBU Modern Acol sections B and C."""
import unittest

from acol.core import Auction, Call, Context, Hand
from acol import competitive


def decision(hand, bids, **kwargs):
    return competitive.choose(Context(hand, Auction(bids.split()), **kwargs))


def meaning(bids, bid, profile=None):
    auction = Auction(bids.split())
    return competitive.interpret(auction, Call(auction.turn, bid, len(auction.calls)), profile)


class InterventionTests(unittest.TestCase):
    def test_negative_double_shows_both_majors(self):
        result = decision("KJ76.QJ54.84.876", "1C 1D")
        self.assertEqual(result.bid, "X")
        m = meaning("1C 1D", "X")
        self.assertEqual(m.min_length, {"S": 4, "H": 4})
        self.assertEqual(m.hcp_min, 6)

    def test_four_spades_double_five_spades_bid(self):
        self.assertEqual(decision("KJ76.84.Q74.J876", "1D 1H").bid, "X")
        self.assertEqual(decision("KJ765.84.Q74.J87", "1D 1H").bid, "1S")
        self.assertEqual(meaning("1D 1H", "X").max_length, {"S": 4})
        self.assertEqual(meaning("1D 1H", "1S").min_length["S"], 5)

    def test_redouble_and_artificial_limit_raise(self):
        self.assertEqual(decision("AK76.84.QJ4.K876", "1H X").bid, "XX")
        result = decision("KQ76.QJ54.84.A76", "1S X")
        self.assertEqual(result.bid, "2N")
        self.assertTrue(result.alert)
        self.assertEqual(meaning("1S X", "2N").min_length["S"], 4)

    def test_raise_after_double_is_preemptive(self):
        self.assertEqual(decision("Q876.KJ54.84.876", "1H X").bid, "3H")
        self.assertEqual(meaning("1H X", "3H").hcp_max, 9)

    def test_nt_penalty_double_switches_off_transfers(self):
        self.assertEqual(decision("J87654.84.J74.87", "1N X").bid, "2S")
        self.assertEqual(meaning("1N X", "2C").forcing, "signoff")
        self.assertFalse(meaning("1N X", "2C").artificial)

    def test_nt_intervention_takeout_and_stayman(self):
        self.assertEqual(decision("KJ76.84.QJ74.A87", "1N 2H").bid, "X")
        self.assertEqual(decision("AK76.84.KQ74.A87", "1N 2H").bid, "3H")
        self.assertEqual(meaning("1N 2H", "3H").forcing, "game")
        self.assertEqual(meaning("1N 3H", "X").rule, "B3.1.takeout")

    def test_two_suited_overcall_cue_meanings(self):
        low = meaning("1S 2N", "3C")
        high = meaning("1S 2N", "3D")
        self.assertEqual(low.min_length, {"H": 5, "S": 2})
        self.assertEqual(high.min_length, {"S": 3})
        self.assertTrue(low.artificial)

    def test_reopening_protects_a_penalty_pass(self):
        result = decision("AK765.KJ4.84.Q87", "1S 2D PASS PASS")
        self.assertEqual(result.bid, "X")
        self.assertEqual(result.rule, "B1.5.reopen")

    def test_double_after_redouble_is_penalties(self):
        m = meaning("1H X XX 1S PASS PASS", "X")
        self.assertEqual(m.rule, "B2.2.1.penalty")


class DefensiveTests(unittest.TestCase):
    def test_natural_overcalls_and_intermediate_jump(self):
        self.assertEqual(decision("KJ765.84.A74.J87", "1H").bid, "1S")
        self.assertEqual(decision("84.Q74.A7.KJ8765", "1H").bid, "2C")
        self.assertEqual(decision("84.Q74.K7.AKJ876", "1H").bid, "3C")
        self.assertEqual(meaning("1H", "3C").rule, "C1.3.intermediate")
        self.assertEqual(meaning("1C", "3S").min_length["S"], 7)

    def test_nt_overcall_strength_depends_on_position(self):
        self.assertEqual(decision("AK76.K4.QJ4.K876", "1H").bid, "1N")
        self.assertEqual(decision("KJ76.J4.Q74.A876", "1H PASS PASS").bid, "1N")
        self.assertEqual(decision("AK76.K4.AQ4.K876", "1H PASS PASS").bid, "2N")
        self.assertEqual(meaning("1H", "1N").hcp_min, 16)
        self.assertEqual(meaning("1H PASS PASS", "1N").hcp_min, 11)
        self.assertFalse(meaning("1H PASS PASS", "2N").artificial)

    def test_takeout_double_and_advances(self):
        self.assertEqual(decision("AK76.84.KJ74.Q87", "1H").bid, "X")
        self.assertEqual(decision("Q876.J765.84.J87", "1D X PASS").bid, "1S")
        self.assertEqual(decision("KQ76.KJ65.84.J87", "1D X PASS").bid, "2S")
        self.assertEqual(decision("K7.84.AKQ76.J876", "1D X PASS").bid, "PASS")
        self.assertEqual(meaning("1D X PASS", "2D").forcing, "one-round")

    def test_double_then_nt_is_stronger_than_direct_nt(self):
        self.assertEqual(meaning("1H X PASS 2C PASS", "2N").hcp_min, 19)
        self.assertEqual(meaning("1H PASS PASS X PASS 2C PASS", "2N").hcp_min, 15)

    def test_landy_and_equal_major_preference(self):
        self.assertEqual(decision("KQ765.AJ87.84.87", "1N").bid, "2C")
        self.assertEqual(decision("J76.Q54.K84.8765", "1N 2C PASS").bid, "2D")
        self.assertTrue(meaning("1N 2C PASS", "2D").artificial)

    def test_nt_double_is_penalty_and_rescue_doubles_stay_penalty(self):
        self.assertEqual(decision("AK76.K4.QJ4.K876", "1N").bid, "X")
        self.assertEqual(meaning("1N X 2D", "X").rule, "B2.2.1.penalty")

    def test_defence_to_preempt(self):
        self.assertEqual(decision("AK76.K4.QJ4.K876", "3H").bid, "3N")
        self.assertEqual(meaning("4H", "X").rule, "C6.takeout")

    def test_michaels_and_unusual_nt(self):
        self.assertEqual(decision("KQ765.AJ876.84.Q", "1D").bid, "2D")
        self.assertEqual(decision("84.7.KQ765.AJ876", "1S").bid, "2N")
        self.assertEqual(meaning("1C", "2N").min_length, {"D": 5, "H": 5})
        self.assertEqual(meaning("1S", "2S").min_length, {"H": 5})

    def test_michaels_minor_enquiry_and_reply(self):
        self.assertEqual(decision("K76.84.QJ74.J876", "1S 2S PASS").bid, "2N")
        self.assertEqual(decision("84.AJ876.KQ765.7", "1S 2S PASS 2N PASS").bid, "3D")
        self.assertEqual(meaning("1S 2S PASS 2N PASS", "3D").min_length["D"], 5)

    def test_unassuming_cue_bid(self):
        self.assertEqual(decision("K76.84.AQ74.K876", "1H 1S PASS").bid, "2H")
        m = meaning("1H 1S PASS", "2H")
        self.assertEqual(m.min_length, {"S": 3})
        self.assertEqual(m.hcp_min, 10)

    def test_responsive_and_competitive_doubles(self):
        self.assertEqual(meaning("1D X 2D", "X").min_length, {"S": 4, "H": 4})
        self.assertEqual(meaning("1D 1H 2D", "X").min_length, {"S": 4, "C": 4})

    def test_transfer_double_is_lead_directing(self):
        m = meaning("1N PASS 2H", "X")
        self.assertEqual(m.rule, "C8.5.lead-directing")
        self.assertEqual(m.min_length, {"H": 5})
        self.assertEqual(meaning("1N PASS 2H", "2S").rule, "C8.5.implied-takeout")

    def test_strong_club_defence_requires_declared_system(self):
        profile = {"opponents": {"strong_club": True}}
        self.assertEqual(meaning("1C", "X", profile).rule, "C9.1.strong-club")
        self.assertEqual(meaning("1C", "X").rule, "C3.1.takeout")

    def test_uncontested_natural_auctions_are_left_to_other_modules(self):
        self.assertIsNone(decision("AK76.K4.QJ4.K876", "1C PASS"))

    def test_forced_high_level_advance_does_not_promise_game_values(self):
        hand = Hand("9642.83.97653.98")
        m = meaning("1H PASS 4H X PASS", "4S")
        self.assertEqual(m.penalty(hand), 0)

    def test_double_of_nt_overcall_is_penalty(self):
        self.assertEqual(decision("AK76.84.QJ4.K876", "1H 1N").bid, "X")
        self.assertEqual(meaning("1H 1N", "X").rule, "B1.NT-penalty")

    def test_nt_takeout_double_does_not_hide_a_missing_major(self):
        result = decision("A98432.J.82.KQ97", "1N 2D")
        self.assertEqual(result.bid, "2S")

    def test_competitive_double_of_new_suit_shows_remaining_suit_and_tolerance(self):
        m = meaning("1C 1H 2D", "X")
        self.assertEqual(m.min_length, {"S": 4, "H": 3})


if __name__ == "__main__":
    unittest.main()
