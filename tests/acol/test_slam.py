"""Control-bidding and the explicitly agreed 0314 partnership extensions."""
import unittest

from acol.core import Auction, Call, Context
from acol import slam


def decide(hand, bids):
    return slam.choose(Context(hand, Auction(bids.split())))


def meaning(bids, bid):
    auction = Auction(bids.split())
    return slam.interpret(auction, Call(auction.turn, bid, len(auction.calls)), {})


class KeycardTests(unittest.TestCase):
    prefix = "1S PASS 3S PASS 4N PASS"

    def test_all_0314_response_steps(self):
        cases = [
            ("QJ76.KQ4.J74.Q87", "5C", 0),
            ("QJ76.AQ4.J74.Q87", "5D", 1),
            ("KJ76.AQ4.J74.Q87", "5H", 2),
            ("KQ76.AQ4.J74.Q87", "5S", 2),
            ("KQ76.AQ4.A74.Q87", "5C", 3),
            ("KQ76.AQ4.A74.A87", "5D", 4),
        ]
        for hand, expected, keys in cases:
            with self.subTest(keys=keys, hand=hand):
                result = decide(hand, self.prefix)
                self.assertEqual(result.bid, expected)
                self.assertTrue(result.alert)
                self.assertIn(keys, meaning(self.prefix, expected).keycards)

    def test_trump_king_is_keycard_and_side_king_is_not(self):
        self.assertEqual(decide("KJ76.AQ4.J74.Q87", self.prefix).bid, "5H")
        self.assertEqual(decide("QJ76.AQ4.J74.K87", self.prefix).bid, "5D")

    def test_side_suits_must_be_controlled_before_keycard_request(self):
        safe = decide("AKJ76.KQ4.A74.K8", "1S PASS 3S PASS")
        unsafe = decide("AKQJ6.AQ4.K74.84", "1S PASS 3S PASS")
        self.assertEqual(safe.bid, "4N")
        self.assertEqual(unsafe.bid, "4H")
        self.assertIn("control", unsafe.rule)

    def test_queen_enquiry_and_positive_side_king_reply(self):
        base = self.prefix + " 5C PASS 5D PASS"
        result = decide("QJ76.KQ4.J74.Q87", base)
        self.assertEqual(result.bid, "5H")
        self.assertEqual(result.rule, "extension.rkcb.queen-reply")
        self.assertTrue(meaning(base, "5H").queen)

    def test_queen_enquiry_negative_returns_to_trumps(self):
        base = self.prefix + " 5C PASS 5D PASS"
        result = decide("J876.KQ4.J74.Q87", base)
        self.assertEqual(result.bid, "5S")
        self.assertFalse(meaning(base, "5S").queen)

    def test_specific_king_enquiry(self):
        base = self.prefix + " 5S PASS 5N PASS"
        result = decide("KQ76.AQ4.J74.K87", base)
        self.assertEqual(result.bid, "6C")
        self.assertEqual(result.rule, "extension.rkcb.king-reply")
        self.assertEqual(decide("KQ76.AQ4.J74.Q87", base).bid, "6S")

    def test_two_missing_keycards_sign_off_below_slam(self):
        # Asker has one keycard, answer 5H shows two: total three.
        result = decide("QJ765.AQ4.K74.84", self.prefix + " 5H PASS")
        self.assertEqual(result.bid, "5S")

    def test_quantitative_four_nt_is_left_to_nt_module(self):
        self.assertIsNone(meaning("1N PASS", "4N"))
        self.assertIsNone(decide("AK76.K4.QJ4.K876", "1N PASS 4N PASS"))

    def test_no_false_trump_agreement_from_transfer(self):
        a = Auction("1N PASS 2H PASS 2S PASS".split())
        self.assertIsNone(slam.agreed_trump(a, 0))
        self.assertIsNone(meaning("1N PASS 2H PASS 2S PASS", "4N"))

    def test_stayman_raise_and_transfer_raise_agree_trump(self):
        for auction in ("1N PASS 2C PASS 2H PASS 3H PASS",
                        "1N PASS 2H PASS 2S PASS 3S PASS"):
            with self.subTest(auction=auction):
                self.assertIn(slam.agreed_trump(Auction(auction.split()), 0), ("H", "S"))

    def test_stayman_diamond_denial_does_not_agree_diamonds(self):
        a = Auction("1N PASS 2C PASS 2D PASS 3D PASS".split())
        self.assertIsNone(slam.agreed_trump(a, 0))
        self.assertIsNone(meaning("1N PASS 2C PASS 2D PASS 3D PASS", "4N"))

    def test_natural_two_nt_rebid_four_nt_stays_quantitative(self):
        self.assertIsNone(meaning("1H PASS 2C PASS 2N PASS", "4N"))

    def test_baron_jump_cue_establishes_the_four_card_fit(self):
        a = Auction("1N PASS 2S PASS 3C PASS 4D PASS".split())
        self.assertEqual(slam.agreed_trump(a, 0), "C")
        self.assertEqual(meaning("1N PASS 2S PASS 3C PASS 4D PASS", "4N").suit, "C")

    def test_natural_nt_three_card_preference_does_not_establish_fit(self):
        a = Auction("1H PASS 1S PASS 1N PASS 3H PASS".split())
        self.assertIsNone(slam.agreed_trump(a, 0))

    def test_natural_baron_suit_raises_establish_a_fit(self):
        for suit in ("D", "H"):
            bids = f"1N PASS 2S PASS 2N PASS 3{suit} PASS 4{suit} PASS"
            with self.subTest(suit=suit):
                self.assertEqual(slam.agreed_trump(Auction(bids.split()), 0), suit)
                self.assertEqual(meaning(bids, "4N").rule, "extension.rkcb.ask")
                self.assertEqual(meaning(bids, "4N").suit, suit)

    def test_positive_strong_two_club_natural_major_raise_establishes_fit(self):
        bids = "2C PASS 2H PASS 2N PASS 3H PASS 4H PASS"
        self.assertEqual(slam.agreed_trump(Auction(bids.split()), 0), "H")
        self.assertEqual(meaning(bids, "4N").rule, "extension.rkcb.ask")
        self.assertEqual(meaning(bids, "4N").suit, "H")

    def test_opener_can_agree_the_transferred_suit_from_public_length_promises(self):
        auctions = (
            "1N PASS 2D PASS 2H PASS 2N PASS 3H PASS",
            "1N PASS 2D PASS 2H PASS 3N PASS 4H PASS",
            "1N PASS 2D PASS 2H PASS 2S PASS 3H PASS",
            "1N PASS 2D PASS 3H PASS",
            "2N PASS 3D PASS 3H PASS 3N PASS 4H PASS",
        )
        for bids in auctions:
            with self.subTest(bids=bids):
                self.assertEqual(slam.agreed_trump(Auction(bids.split()), 0), "H")
                self.assertEqual(meaning(bids, "4N").rule, "extension.rkcb.ask")
                self.assertEqual(meaning(bids, "4N").suit, "H")

    def test_opponents_artificial_stayman_does_not_erase_a_natural_club_fit(self):
        bids = "1N PASS 2C 3C PASS 4C PASS"
        self.assertEqual(slam.agreed_trump(Auction(bids.split()), 1), "C")
        self.assertEqual(meaning(bids, "4N").suit, "C")

    def test_direct_major_over_two_nt_names_trumps_for_keycards(self):
        for suit in ("H", "S"):
            bids = f"2N PASS 4{suit} PASS"
            with self.subTest(suit=suit):
                self.assertEqual(slam.agreed_trump(Auction(bids.split()), 0), suit)
                self.assertEqual(meaning(bids, "4N").rule, "extension.rkcb.ask")
                self.assertEqual(meaning(bids, "4N").suit, suit)
        self.assertIsNone(meaning("2N PASS 4C PASS", "4N"))


class ControlsAndGrandSlamTests(unittest.TestCase):
    def test_minimum_declines_control_invitation(self):
        result = decide("QJ76.KQ4.J74.Q87", "1S PASS 3S PASS 4C PASS")
        self.assertEqual(result.bid, "4S")

    def test_return_to_trump_ends_slam_exploration(self):
        for auction in ("1S PASS 3S PASS 4C PASS 4S PASS",
                        "1S PASS 3S PASS 4C PASS 4D PASS 5C PASS 5S PASS"):
            with self.subTest(auction=auction):
                result = decide("AKJ76.KQ4.A74.K8", auction)
                self.assertEqual(result.bid, "PASS")

    def test_direct_weak_game_raise_does_not_invite_slam(self):
        self.assertIsNone(decide("AKJ76.KQ4.A74.K8", "1S PASS 4S PASS"))

    def test_grand_slam_force_counts_top_trump_honours(self):
        base = "1S PASS 3S PASS 5N PASS"
        cases = [("J876.AQ4.J74.Q87", "6C"),
                 ("Q876.AQ4.J74.Q87", "6D"),
                 ("KQ76.AQ4.J74.Q87", "6H"),
                 ("AKQ6.J74.J74.Q87", "7S")]
        for hand, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(decide(hand, base).bid, expected)


class AceOnlyTests(unittest.TestCase):
    def test_direct_two_nt_four_nt_counts_aces_without_trump_king(self):
        base = "2N PASS 4N PASS"
        self.assertEqual(decide("AK76.AQ4.J74.K87", base).bid, "5H")
        self.assertEqual(meaning("2N PASS", "4N").rule, "extension.aces.ask")

    def test_strong_two_club_two_nt_route_has_same_ace_enquiry(self):
        self.assertEqual(meaning("2C PASS 2D PASS 2N PASS", "4N").rule, "extension.aces.ask")

    def test_ace_only_five_nt_asks_for_ordinary_king_count(self):
        base = "2N PASS 4N PASS 5H PASS 5N PASS"
        self.assertEqual(decide("AK76.AQ4.J74.K87", base).bid, "6H")
        self.assertEqual(meaning(base, "6H").rule, "extension.aces.king-reply")

    def test_inference_respects_ace_king_and_control_promises(self):
        from acol.core import Hand
        hand = Hand("AK76.AQ4.J74.K87")
        self.assertEqual(meaning("2N PASS 4N PASS", "5H").penalty(hand), 0)
        self.assertEqual(meaning("2N PASS 4N PASS 5H PASS 5N PASS", "6H").penalty(hand), 0)
        self.assertGreater(meaning("1S PASS 3S PASS", "4D").penalty(hand), 0)

    def test_queen_ask_never_obscures_the_negative_trump_return(self):
        # After a club-keycard reply there is no five-level club signoff left;
        # do not invent an ambiguous queen enquiry requiring a 6C negative.
        base = Auction("1C PASS 3C PASS 4N PASS 5D PASS".split())
        self.assertIsNone(slam._queen_ask(base, base.calls[-2], "C"))


if __name__ == "__main__":
    unittest.main()
