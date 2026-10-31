"""Behavioral cases taken from the EBU auction families and partnership choices."""
import random
import unittest

from acol.core import Auction, Call, Context, Hand, PROFILE
from acol.natural import choose, interpret


def auction(*partnership_bids):
    """Uncontested N/S sequence, with East/West passing after every bid."""
    return Auction([bid for b in partnership_bids for bid in (b, 'PASS')])


def decision(hand, *bids, vulnerability='None'):
    return choose(Context(hand, auction(*bids), vulnerability=vulnerability))


def meaning(bids, bid):
    a = auction(*bids)
    return interpret(a, Call(a.turn, bid, len(a.calls)), PROFILE)


class NaturalAcolTests(unittest.TestCase):
    def assert_bid(self, hand, expected, *bids, **kw):
        result = decision(hand, *bids, **kw)
        self.assertIsNotNone(result)
        self.assertEqual(result.bid, expected, result)
        return result

    def test_four_four_four_one_openings(self):
        for hand, expected in [('AQ32.KJ43.Q432.2', '1H'),
                               ('2.AQ43.KJ43.Q432', '1D'),
                               ('AQ43.2.KJ43.Q432', '1D'),
                               ('AQ43.KJ43.2.Q432', '1C')]:
            with self.subTest(hand=hand):
                self.assert_bid(hand, expected)

    def test_equal_four_card_majors_open_hearts(self):
        self.assert_bid('AQ32.KJ43.Q32.32', '1H')

    def test_rule20_reference_examples(self):
        self.assert_bid('AQ982.KJT43.5.96', '1S')
        self.assert_bid('Q2.AJ64.J3.K9532', 'PASS')

    def test_weak_two_is_six_cards_and_not_benji(self):
        self.assert_bid('32.32.KQJ432.432', '2D')
        self.assert_bid('32.KQJ432.32.432', '2H')
        self.assert_bid('KQJ432.32.32.432', '2S')
        self.assertEqual(meaning([], '2D').min_length, {'D': 6})
        self.assertFalse(meaning([], '2D').artificial)

    def test_weak_two_does_not_hide_side_major(self):
        self.assert_bid('KQJ432.5432.2.32', 'PASS')

    def test_preempt_respects_vulnerability(self):
        self.assert_bid('KQJ5432.32.32.32', '3S')
        self.assert_bid('KQJ5432.32.32.32', 'PASS', vulnerability='Both')

    def test_gambling_three_nt_precedes_rule20(self):
        self.assert_bid('32.32.32.AKQJ432', '3N')
        self.assert_bid('32.32.32.AKQJ432', 'PASS', '3N', '4C')
        self.assert_bid('32.32.AKQJ432.32', '4D', '3N', '4C')

    def test_losing_trick_major_raises(self):
        self.assert_bid('K432.J432.Q32.32', '2S', '1S')
        self.assert_bid('K432.Q432.Q32.32', '3S', '1S')
        self.assert_bid('K432.AQ32.Q32.32', '4S', '1S')

    def test_splinter_and_pudding_are_not_natural(self):
        self.assert_bid('K432.AQ32.K432.2', '4C', '1S')
        self.assert_bid('K432.AQ3.Q32.K32', '3N', '1S')
        self.assertEqual(meaning(['1S'], '3N').min_length, {'S': 4})
        self.assertTrue(meaning(['1S'], '3N').artificial)
        self.assertEqual(meaning(['1S'], '4C').max_length, {'C': 1})
        self.assert_bid('AQJ32.K32.A32.32', '4S', '1S', '3N')

    def test_major_preferred_to_longer_minor_below_game_values(self):
        self.assert_bid('Q2.AQ32.32.KJ432', '1H', '1D')
        self.assert_bid('Q2.AQ32.32.AK432', '2C', '1D')

    def test_four_hearts_does_not_qualify_for_two_hearts_over_spade(self):
        self.assert_bid('Q2.AQ32.K432.432', '2D', '1S')
        self.assertEqual(meaning(['1S'], '2H').min_length, {'H': 5})

    def test_strong_jump_shift(self):
        self.assert_bid('K32.AQJ32.A32.K2', '3H', '1S')
        self.assertEqual(meaning(['1S'], '3H').forcing, 'game')

    def test_club_opening_special_no_trump_response(self):
        self.assert_bid('Q32.K32.Q32.J432', '1N', '1C')
        self.assertEqual(meaning(['1C'], '1N').hcp_min, 8)
        self.assertEqual(meaning(['1C'], '1N').hcp_max, 10)

    def test_balanced_opener_supports_four_card_major(self):
        self.assert_bid('AQ32.K32.A432.Q2', '3S', '1D', '1S')

    def test_opener_reverse_requires_extra_values(self):
        self.assert_bid('A2.KQ32.AK432.32', '2H', '1D', '1S')
        self.assert_bid('Q2.KJ32.AQ432.32', '2D', '1D', '1S')
        self.assertEqual(meaning(['1D', '1S'], '2H').forcing, 'one-round')
        self.assertEqual(meaning(['1D', '2C'], '3H').forcing, 'game')

    def test_opener_jump_rebid_forcing_depends_on_response(self):
        self.assert_bid('A2.KQJ432.A32.K2', '3H', '1H', '1S')
        self.assertEqual(meaning(['1H', '1S'], '3H').forcing, 'invite')
        self.assertEqual(meaning(['1H', '2C'], '3H').forcing, 'game')

    def test_minimum_good_major_preserves_fifteen_point_nt_rebid(self):
        self.assert_bid('AQJ32.K32.K32.32', '2S', '1S', '2C')

    def test_four_four_four_one_can_rebid_four_card_suit(self):
        hand = 'Q.QJT6.AQ52.AT72'
        self.assert_bid(hand, '2D', '1D', '2C')
        self.assertEqual(meaning(['1D', '2C'], '2D').penalty(Hand(hand)), 0)

    def test_distributional_rule20_opener_can_jump_raise(self):
        hand = 'A942.T.AK7542.53'
        self.assert_bid(hand, '3S', '1D', '1S')
        self.assertEqual(meaning(['1D', '1S'], '3S').penalty(Hand(hand)), 0)

    def test_strong_long_minor_is_not_limited_to_invitational_jump(self):
        self.assert_bid('Q.AKT.AKJ8752.A2', '5D', '1D', '1S')
        self.assert_bid('K3.AQ4.AK6542.A3', '3N', '1D', '1S')

    def test_responder_reverse_is_game_forcing(self):
        self.assert_bid('A2.KQ32.32.AJ432', '2H', '1D', '2C', '2D')
        m = meaning(['1D', '2C', '2D'], '2H')
        self.assertEqual(m.forcing, 'game')
        self.assertEqual(m.min_length, {'H': 4})

    def test_false_preference_is_not_forcing(self):
        self.assert_bid('KQ432.32.432.K32', '2H', '1H', '1S', '2C')
        self.assertEqual(meaning(['1H', '1S', '2C'], '2H').forcing, 'none')
        self.assertEqual(meaning(['1H', '1S', '2C'], '2H').min_length, {'H': 2})

    def test_responder_invitational_jump_preference(self):
        self.assert_bid('KQ432.Q32.A32.32', '3H', '1H', '1S', '2C')
        self.assertEqual(meaning(['1H', '1S', '2C'], '3H').forcing, 'invite')

    def test_fourth_suit_forcing_without_stopper(self):
        self.assert_bid('AKJ32.Q2.32.KQ32', '2D', '1H', '1S', '2C')
        m = meaning(['1H', '1S', '2C'], '2D')
        self.assertTrue(m.artificial)
        self.assertEqual(m.min_length, {})
        self.assertEqual(m.forcing, 'one-round')
        self.assertEqual(meaning(['1H', '1S', '2D'], '3C').forcing, 'game')

    def test_fourth_suit_one_spade_exception(self):
        self.assert_bid('KQ32.32.AQ432.32', '1S', '1C', '1D', '1H')
        self.assertFalse(meaning(['1C', '1D', '1H'], '1S').artificial)
        self.assertTrue(meaning(['1C', '1D', '1H'], '2S').artificial)

    def test_opener_answers_fourth_suit_with_support(self):
        self.assert_bid('Q32.AK432.2.K432', '2S', '1H', '1S', '2C', '2D')
        self.assertEqual(meaning(['1H', '1S', '2C', '2D'], '2S').forcing, 'none')

    def test_continuing_after_fourth_suit_creates_game_force(self):
        self.assertEqual(meaning(['1H', '1S', '2C', '2D', '2H'], '2S').forcing, 'game')
        result = decision('Q32.AK432.2.K432', '1H', '1S', '2C', '2D', '2H', '2S')
        self.assertNotEqual(result.bid, 'PASS')

    def test_fourth_suit_on_an_existing_game_force_accepts_weaker_response(self):
        hand = 'J.Q3.J974.KQT652'
        self.assert_bid(hand, '3H', '1S', '2C', '3D')
        self.assertEqual(meaning(['1S', '2C', '3D'], '3H').penalty(Hand(hand)), 0)
        self.assertEqual(meaning(['1S', '2C', '3D'], '3H').forcing, 'game')

    def test_game_values_continue_after_minimum_fourth_suit_answer(self):
        self.assert_bid('AKJ32.Q2.32.KQ32', '3N', '1H', '1S', '2C', '2D', '2N')

    def test_raising_openers_rebid_suit_is_invitational(self):
        m = meaning(['1S', '2D', '2S'], '3S')
        self.assertEqual(m.forcing, 'invite')
        self.assertEqual((m.hcp_min, m.hcp_max), (10, 12))

    def test_long_suit_trial_and_rejection(self):
        self.assert_bid('AQJ32.K32.AK3.32', '3H', '1S', '2S')
        self.assert_bid('K432.Q32.J432.32', '3S', '1S', '2S', '3H')
        self.assert_bid('K432.A2.Q432.432', '4S', '1S', '2S', '3H')

    def test_minor_trial_promises_stopper_not_four_cards(self):
        m = meaning(['1D', '2D'], '2S')
        self.assertEqual(m.min_length, {})
        self.assertTrue(m.artificial)
        self.assertEqual(m.forcing, 'invite')

    def test_weak_two_enquiry_requires_partial_fit(self):
        self.assert_bid('AQ32.32.AK32.K32', '2N', '2H')
        self.assertEqual(meaning(['2H'], '2N').min_length, {'H': 2})
        self.assertEqual(meaning(['2H'], '2N').forcing, 'one-round')

    def test_weak_two_enquiry_minimum_feature_and_good_suit(self):
        self.assert_bid('32.KQJ432.32.432', '3H', '2H', '2N')
        self.assert_bid('K2.KQJ432.32.432', '3S', '2H', '2N')
        self.assert_bid('32.AQJ432.32.Q32', '3N', '2H', '2N')
        self.assertEqual(meaning(['2H', '2N'], '3S').min_length, {'H': 6})
        self.assertTrue(meaning(['2H', '2N'], '3S').artificial)

    def test_weak_two_new_suit_at_two_is_nonforcing_at_three_forcing(self):
        self.assertEqual(meaning(['2D'], '2H').forcing, 'none')
        self.assertEqual(meaning(['2S'], '3H').forcing, 'game')

    def test_preemptive_raise_does_not_generate_another_raise(self):
        self.assert_bid('KQJ432.32.32.432', 'PASS', '2S', '3S')
        self.assertEqual(meaning(['2S'], '3S').forcing, 'signoff')

    def test_passed_hand_new_suit_is_not_forcing(self):
        a = Auction(['PASS', 'PASS', '1C', 'PASS'])
        m = interpret(a, Call(0, '1S', 4), PROFILE)
        self.assertEqual(m.forcing, 'none')

    def test_completed_game_is_not_raised_again(self):
        self.assert_bid('AQJ32.K32.A32.32', 'PASS', '1S', '2S', '3H', '4S')
        self.assert_bid('AQJ32.K32.A32.32', 'PASS', '1S', '1N', '2H', '3N')

    def test_other_auction_families_are_left_to_their_modules(self):
        for bids in [('1N',), ('2N',), ('2C',)]:
            self.assertIsNone(decision('AQJ32.K32.A32.32', *bids))
        a = Auction(['1S', '2H'])
        self.assertIsNone(choose(Context('AQJ32.K32.A32.32', a)))

    def test_decisions_are_legal_for_varied_hands_in_natural_auctions(self):
        rng = random.Random(1234)
        deck = [s + r for s in 'SHDC' for r in 'AKQJT98765432']
        sequences = [(), ('1C',), ('1D',), ('1H',), ('1S',),
                     ('1D', '1S'), ('1H', '2C'), ('1H', '1S', '2C'),
                     ('1D', '1S', '2H'), ('1H', '1S', '2C', '2D'),
                     ('2H',), ('2H', '2N'), ('2H', '2N', '3C')]
        for bids in sequences:
            a = auction(*bids)
            for _ in range(30):
                ctx = Context(Hand(rng.sample(deck, 13)), a)
                result = choose(ctx)
                self.assertIsNotNone(result, (ctx.h.pbn, bids))
                self.assertIn(result.bid, ctx.legal)


if __name__ == '__main__':
    unittest.main()
