"""Executable convention-card examples for EBU A1.1--A1.4.

Hands are complete thirteen-card fixtures. Assertions check choices and the
public-information interpretation used by hidden-hand sampling.
"""
import unittest

from acol.core import Auction, Call, Context, Hand, PROFILE
from acol.notrump import choose, interpret


def decision(hand, sequence=()):
    a = Auction(sequence)
    return choose(Context(hand, a))


def meaning(sequence, bid):
    a = Auction(sequence)
    return interpret(a, Call(a.turn, bid, len(a.calls)), PROFILE)


# Omit opponents' passes when writing an uncontested partnership auction.
def auction(*partnership):
    result = []
    for bid in partnership:
        result.extend([bid, 'PASS'])
    return result


class NotrumpOpeningTests(unittest.TestCase):
    def test_weak_notrump_range_and_five_card_major(self):
        for hand, expected in [
            ('KQ32.KJ3.Q32.J32', '1N'),  # 12, 4-3-3-3
            ('J5432.KQ3.A32.Q2', '1N'),  # weak five-card spades
            ('AKQ2.AJ3.KQ3.J32', '2N'), # 20, 4-3-3-3
            ('AKQ2.AK3.KQ3.Q32', '2C'), # 23 balanced
        ]:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand).bid, expected)
        self.assertIsNone(decision('AJ543.KQ3.432.Q2'))  # natural module opens 1S

    def test_15_19_opening_yields_to_the_natural_suit_module(self):
        self.assertIsNone(decision('AQ32.KJ3.K32.Q32'))

    def test_opening_meanings_do_not_call_two_nt_a_minor_relay(self):
        for bid, low, high in [('1N', 12, 14), ('2N', 20, 22)]:
            m = meaning([], bid)
            self.assertEqual((m.hcp_min, m.hcp_max), (low, high))
            if bid == '1N':
                self.assertTrue(m.balanced)
            else:
                # An exceptional singleton ace/king is permitted over 2NT.
                self.assertIsNone(m.balanced)
                self.assertEqual(m.min_length, dict.fromkeys('SHDC', 1))
        self.assertTrue(meaning([], '2C').artificial)


class OneNotrumpTests(unittest.TestCase):
    def test_balanced_response_ranges(self):
        cases = [
            ('J432.432.432.432', 'PASS'),
            ('KQ3.Q32.K32.J432', '2S'),  # 11
            ('KQ3.K32.K32.J432', '2S'),  # 12
            ('KQ3.K32.KJ2.J432', '3N'),  # 13
            ('AK3.AQ2.KQ2.Q432', '2S'), # 20
            ('AK3.AQ2.KQ2.K432', '2S'), # 21
            ('AK3.AQ2.KQ2.A432', '6N'), # 22
            ('AK3.AK2.AQ2.A432', '2S'), # 24
            ('AK3.AK2.AQ2.AJ32', '2S'), # 25
            ('AK3.AK2.AK2.AJ32', '7N'), # 26
        ]
        for hand, expected in cases:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('1N')).bid, expected)

    def test_stayman_weak_escape_and_invitational_four_card_major(self):
        for hand in ['KQ43.QJ32.K32.32', 'J5432.Q432.32.32', 'J43.Q432..J98765', 'J432.Q432.J5432.']:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('1N')).bid, '2C')

    def test_stayman_reply_prioritises_hearts_with_both_majors(self):
        for hand, expected in [
            ('QJ32.K432.A32.Q2', '2H'),
            ('KQ32.KJ3.Q32.J32', '2S'),
            ('KQ3.KJ3.Q32.J432', '2D'),
        ]:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('1N', '2C')).bid, expected)
        m = meaning(auction('1N', '2C'), '2S')
        self.assertEqual(m.min_length, {'S': 4})
        self.assertEqual(m.max_length, {'H': 3})
        m = meaning(auction('1N', '2C'), '2D')
        self.assertEqual(m.max_length, {'H': 3, 'S': 3})
        self.assertTrue(m.artificial)

    def test_weak_stayman_continuations(self):
        for hand, reply, expected in [
            ('J5432.Q432.32.32', '2D', '2S'),
            ('J5432.Q432.32.32', '2H', 'PASS'),
            ('J43.Q432..J98765', '2D', '3C'),
            ('J432.Q432.J5432.', '2D', 'PASS'),
        ]:
            with self.subTest(hand=hand, reply=reply):
                self.assertEqual(decision(hand, auction('1N', '2C', reply)).bid, expected)
        m = meaning(auction('1N', '2C', '2D'), '2S')
        self.assertEqual(m.min_length, {'S': 5, 'H': 4})
        self.assertEqual(m.hcp_max, 10)

    def test_stayman_invitation_fit_and_no_fit(self):
        h = 'KQ43.QJ32.K32.32'
        self.assertEqual(decision(h, auction('1N', '2C', '2H')).bid, '3H')
        self.assertEqual(decision(h, auction('1N', '2C', '2D')).bid, '2N')
        self.assertEqual(decision('QJ32.K432.A32.Q2', auction('1N', '2C', '2H', '3H')).bid, 'PASS')
        self.assertEqual(decision('QJ32.KQ32.A32.Q2', auction('1N', '2C', '2H', '3H')).bid, '4H')

    def test_stayman_game_force_five_four_majors(self):
        h = 'AQJ43.KQ32.32.Q2'
        self.assertEqual(Hand(h).hcp, 14)
        self.assertEqual(decision(h, auction('1N', '2C', '2D')).bid, '3S')
        self.assertEqual(decision('KQ3.KJ3.Q32.J432', auction('1N', '2C', '2D', '3S')).bid, '4S')
        self.assertEqual(decision('KQ.KJ3.Q432.J432', auction('1N', '2C', '2D', '3S')).bid, '3N')

    def test_stayman_shows_second_major_after_invitation(self):
        self.assertEqual(decision('QJ32.KQ32.A32.Q2', auction('1N', '2C', '2H', '2N')).bid, '3S')
        self.assertEqual(decision('KQ43.QJ32.K32.32', auction('1N', '2C', '2H', '2N', '3S')).bid, '4S')

    def test_red_transfers_and_acceptance(self):
        self.assertEqual(decision('32.KJ543.432.432', auction('1N')).bid, '2D')
        self.assertEqual(decision('KJ543.32.432.432', auction('1N')).bid, '2H')
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '2D')).bid, '2H')
        self.assertEqual(decision('32.KJ543.432.432', auction('1N', '2D', '2H')).bid, 'PASS')
        m = meaning(auction('1N'), '2D')
        self.assertEqual(m.min_length, {'H': 5})
        self.assertNotIn('D', m.min_length)
        self.assertTrue(m.artificial)
        self.assertEqual(meaning(auction('1N', '2D'), '2H').min_length, {})

    def test_transfer_break_requires_four_card_fit_and_improvement(self):
        self.assertEqual(decision('AQ32.KQ32.K32.32', auction('1N', '2D')).bid, '3H')
        m = meaning(auction('1N', '2D'), '3H')
        self.assertEqual(m.min_length, {'H': 4})
        self.assertEqual(m.hcp_min, 14)

    def test_transfer_invitation_chooses_game_and_strain(self):
        responder = 'Q32.KJ543.K32.Q2'  # 11, five hearts
        self.assertEqual(decision(responder, auction('1N', '2D', '2H')).bid, '2N')
        cases = [
            ('KQ32.KJ3.Q32.J32', '3H'), # 12 and three hearts
            ('KQ32.AJ3.K32.J32', '4H'), # 14 and three hearts
            ('KQ32.KJ.Q432.J32', 'PASS'), # 12 and two hearts
            ('KQ32.AJ.K432.J32', '3N'), # 14 and two hearts
        ]
        for hand, expected in cases:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('1N', '2D', '2H', '2N')).bid, expected)

    def test_transfer_three_nt_is_choice_of_games(self):
        self.assertEqual(decision('Q32.AJ543.K32.K2', auction('1N', '2D', '2H')).bid, '3N')
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '2D', '2H', '3N')).bid, '4H')
        self.assertEqual(decision('KQ32.KJ.Q432.J32', auction('1N', '2D', '2H', '3N')).bid, 'PASS')
        m = meaning(auction('1N', '2D', '2H'), '3N')
        self.assertEqual(m.max_length, {'H': 5})

    def test_transfer_six_card_major_invitation_and_signoff(self):
        self.assertEqual(decision('Q3.KJ5432.K32.Q2', auction('1N', '2D', '2H')).bid, '3H')
        self.assertEqual(decision('Q3.AJ5432.K32.K2', auction('1N', '2D', '2H')).bid, '4H')

    def test_transfer_heart_spade_continuation_forces_another_bid(self):
        h = 'KQ32.KJ543.Q32.2'
        self.assertEqual(decision(h, auction('1N', '2D', '2H')).bid, '2S')
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '2D', '2H', '2S')).bid, '3S')
        m = meaning(auction('1N', '2D', '2H'), '2S')
        self.assertEqual(m.min_length, {'H': 5, 'S': 4})
        self.assertEqual(m.forcing, 'one-round')

    def test_transfer_new_minor_is_natural_game_force(self):
        h = 'AQJ43.K2.32.AK32'
        self.assertEqual(decision(h, auction('1N', '2H', '2S')).bid, '3C')
        m = meaning(auction('1N', '2H', '2S'), '3C')
        self.assertEqual(m.min_length, {'S': 5, 'C': 4})
        self.assertEqual(m.forcing, 'game')

    def test_two_way_baron_minimum_and_maximum_suit_order(self):
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '2S')).bid, '2N')
        self.assertEqual(decision('KQ32.AJ3.K32.J32', auction('1N', '2S')).bid, '3S')
        self.assertEqual(decision('KQ3.AJ3.K32.J432', auction('1N', '2S')).bid, '3C')
        m = meaning(auction('1N', '2S'), '3S')
        self.assertEqual(m.min_length, {'S': 4})
        self.assertEqual(m.max_length, {'C': 3, 'D': 3, 'H': 3})
        self.assertEqual((m.hcp_min, m.hcp_max), (14, 14))

    def test_two_way_baron_game_and_slam_ranges(self):
        cases = [
            ('KQ3.Q32.K32.J432', '2N', 'PASS'),
            ('KQ3.Q32.K32.J432', '3C', '3N'),
            ('AK3.AQ2.KQ2.Q432', '2N', '3N'),
            ('AK3.AQ2.KQ2.Q432', '3C', '6N'),
            ('AK3.AQ2.KQ2.K432', '2N', '3N'),
            ('AK3.AK2.AQ2.A432', '2N', '6N'),
            ('AK3.AK2.AQ2.A432', '3C', '7N'),
        ]
        for hand, reply, expected in cases:
            with self.subTest(hand=hand, reply=reply):
                self.assertEqual(decision(hand, auction('1N', '2S', reply)).bid, expected)

    def test_baron_jump_cue_agrees_the_original_four_card_suit(self):
        m = meaning(auction('1N', '2S', '3C'), '4D')
        self.assertEqual(m.min_length, {'C': 4})
        self.assertEqual(m.honours, {'D': 'A'})
        self.assertEqual(m.suit, 'C')
        self.assertTrue(m.artificial)
        natural = meaning(auction('1N', '2S', '3C'), '3D')
        self.assertEqual(natural.min_length, {'D': 4})
        self.assertFalse(natural.artificial)

    def test_baron_can_investigate_a_four_four_fit_with_eighteen_points(self):
        hand = 'AQJ3.AK32.K432.2'
        self.assertEqual(Hand(hand).hcp, 17)
        hand = 'AQJ3.AKJ2.K432.2'
        self.assertEqual(Hand(hand).hcp, 18)
        self.assertEqual(decision(hand, auction('1N')).bid, '2S')
        self.assertEqual(decision(hand, auction('1N', '2S', '2N')).bid, '3D')

    def test_minor_relay_never_infers_opener_has_clubs(self):
        h = '32.432.QJ9876.32'
        self.assertEqual(decision(h, auction('1N')).bid, '2N')
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '2N')).bid, '3C')
        self.assertEqual(decision(h, auction('1N', '2N', '3C')).bid, '3D')
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '2N', '3C', '3D')).bid, 'PASS')
        self.assertTrue(meaning(auction('1N'), '2N').artificial)
        self.assertEqual(meaning(auction('1N', '2N'), '3C').min_length, {})
        self.assertEqual(meaning(auction('1N', '2N', '3C'), '3D').min_length, {'D': 6})

    def test_opponents_intervention_yields_to_competitive_module(self):
        h = 'KQ32.KJ3.Q32.J32'
        self.assertIsNone(decision(h, ['1N', '2H']))
        self.assertIsNone(decision(h, ['1N', 'PASS', '2C', 'X']))
        self.assertIsNone(meaning(['1N', 'PASS', '2C', 'X'], '2D'))

    def test_direct_four_nt_is_quantitative_and_unknown_calls_do_not_crash(self):
        m = meaning(auction('1N'), '4N')
        self.assertEqual(m.forcing, 'invite')
        self.assertFalse(m.artificial)
        self.assertEqual(decision('KQ32.AJ3.K32.J32', auction('1N', '4N')).bid, '6N')
        self.assertEqual(decision('KQ32.KJ3.Q32.J32', auction('1N', '4N')).bid, 'PASS')
        self.assertIsNone(meaning(auction('1N'), '5N'))
        self.assertIsNone(meaning(auction('2N'), '4N'))

    def test_systems_after_direct_and_protective_notrump_overcalls(self):
        h = 'KQ3.Q32.K32.J432' # 11, enough for game opposite 16--18
        self.assertEqual(decision(h, ['1C', '1N', 'PASS']).bid, '3N')
        # Protecting 1NT keeps the weak-notrump style of responses.
        self.assertEqual(decision(h, ['1C', 'PASS', 'PASS', '1N', 'PASS']).bid, '2S')


class TwoNotrumpTests(unittest.TestCase):
    def test_two_nt_balanced_response_ranges(self):
        for hand, expected in [
            ('J432.432.432.432', 'PASS'),
            ('K32.J32.432.5432', '3N'), # 4
            ('KQ3.Q32.K32.J432', '3S'), # 11
            ('KQ3.K32.KJ2.J432', '6N'), # 13, no major interest
            ('AQ3.K32.KJ2.K432', '3S'), # 16
            ('AQ3.K32.AJ2.K432', '7N'), # 17
        ]:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('2N')).bid, expected)

    def test_two_nt_stayman_and_transfer(self):
        self.assertEqual(decision('KJ43.Q432.32.432', auction('2N')).bid, '3C')
        self.assertEqual(decision('32.KJ543.432.432', auction('2N')).bid, '3D')
        self.assertEqual(decision('KJ543.32.432.432', auction('2N')).bid, '3H')
        self.assertEqual(decision('AKQ2.AJ3.KQ3.J32', auction('2N', '3C')).bid, '3S')
        self.assertEqual(decision('AKQ2.AJ3.KQ3.J32', auction('2N', '3D')).bid, '3H')

    def test_two_nt_transfer_quantitative_four_nt(self):
        h = 'Q32.KJ543.K32.Q2' # 11
        self.assertEqual(decision(h, auction('2N', '3D', '3H')).bid, '4N')
        m = meaning(auction('2N', '3D', '3H'), '4N')
        self.assertEqual(m.forcing, 'invite')
        self.assertFalse(m.artificial)
        self.assertEqual(decision('AKQ2.AJ3.KQ3.J32', auction('2N', '3D', '3H', '4N')).bid, 'PASS')
        self.assertEqual(decision('AKQ2.AK3.KQ3.J32', auction('2N', '3D', '3H', '4N')).bid, '6H')

    def test_two_nt_baron_slam_and_grand_slam_invitations(self):
        for hand, reply, expected in [
            ('KQ3.Q32.K32.J432', '3N', 'PASS'),
            ('KQ3.Q32.K32.J432', '4C', '6N'),
            ('AQ3.K32.KJ2.K432', '3N', '6N'),
            ('AQ3.K32.KJ2.K432', '4C', '7N'),
        ]:
            with self.subTest(hand=hand, reply=reply):
                self.assertEqual(decision(hand, auction('2N', '3S', reply)).bid, expected)
        self.assertEqual(decision('AKQ2.AJ3.KQ3.J32', auction('2N', '3S')).bid, '3N')
        self.assertEqual(decision('AKQ2.AK3.KQ3.J32', auction('2N', '3S')).bid, '4S')

    def test_direct_two_nt_four_nt_is_left_to_ace_asking_module(self):
        self.assertIsNone(decision('AKQ2.AJ3.KQ3.J32', auction('2N', '4N')))

    def test_four_nt_after_direct_major_is_keycard_not_natural(self):
        self.assertEqual(decision('AQ32.AK.KJ3.KQ32', auction('2N', '4H')).bid, '4N')
        self.assertIsNone(meaning(auction('2N', '4H'), '4N'))
        self.assertEqual(decision('AKQ2.AJ.KQ3.J432', auction('2N', '4H')).bid, 'PASS')
        natural = meaning(auction('2N', '4C'), '4N')
        self.assertFalse(natural.artificial)
        self.assertIn('Natural notrump', natural.description)


class StrongClubTests(unittest.TestCase):
    def test_negative_and_positive_responses(self):
        cases = [
            ('J432.Q32.J32.432', '2D'),
            ('KQ3.K32.432.J432', '2N'), # 9 balanced
            ('AQ543.32.432.432', '2S'), # AQ five-card suit, only 6 points
            ('AKQJ43.32.432.32', '3S'), # solid six-card suit
        ]
        for hand, expected in cases:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('2C')).bid, expected)
        self.assertTrue(meaning(auction('2C'), '2D').artificial)
        self.assertEqual(meaning(auction('2C'), '2S').min_length, {'S': 5})

    def test_negative_balanced_rebid_ranges(self):
        for hand, expected, bounds in [
            ('AKQ2.AK3.KQ3.Q32', '2N', (23, 24)),
            ('AKQ2.AK3.AQ3.K32', '3N', (25, 27)),
            ('AKQ2.AKJ.AQ3.KQ2', '4N', (28, 30)),
        ]:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('2C', '2D')).bid, expected)
                m = meaning(auction('2C', '2D'), expected)
                self.assertEqual((m.hcp_min, m.hcp_max), bounds)

    def test_negative_23_24_rebid_is_passable_only_with_very_weak_hand(self):
        self.assertEqual(decision('J432.432.432.432', auction('2C', '2D', '2N')).bid, 'PASS')
        self.assertEqual(decision('Q32.432.432.5432', auction('2C', '2D', '2N')).bid, '3N')
        self.assertEqual(decision('QJ43.432.432.432', auction('2C', '2D', '2N')).bid, '3C')

    def test_positive_major_then_two_nt_is_natural_not_transfer_system(self):
        self.assertEqual(decision('AKQ2.AK3.KQ3.Q32', auction('2C', '2H')).bid, '2N')
        self.assertEqual(decision('32.AQ543.K32.432', auction('2C', '2H', '2N')).bid, '3H')
        self.assertEqual(decision('AKQ2.AK3.KQ3.Q32', auction('2C', '2H', '2N', '3H')).bid, '4H')
        m = meaning(auction('2C', '2H', '2N'), '3H')
        self.assertFalse(m.artificial)
        self.assertEqual(m.min_length, {'H': 5})
        self.assertEqual(m.forcing, 'game')

    def test_positive_nt_auction_does_not_stop_at_three_nt(self):
        self.assertEqual(decision('AKQ2.AK3.KQ3.Q32', auction('2C', '2N')).bid, '3N')
        self.assertEqual(decision('KQ3.K32.432.J432', auction('2C', '2N', '3N')).bid, '4N')
        self.assertEqual(decision('KQ3.K32.K32.J432', auction('2C', '2N', '3N')).bid, '4C')
        self.assertEqual(decision('AKQ2.AK3.KQ3.Q32', auction('2C', '2N', '3N', '4C')).bid, '4N')
        self.assertEqual(decision('KQ3.K32.K32.J432', auction('2C', '2N', '3N', '4C', '4N')).bid, '6N')

    def test_unbalanced_strong_club_negative_cannot_pass_below_game(self):
        self.assertEqual(decision('32.432.Q32.J5432', auction('2C', '2D', '2S')).bid, '3C')
        self.assertEqual(decision('432.432.Q32.J432', auction('2C', '2D', '2S')).bid, '4S')


class BalancedRebidTests(unittest.TestCase):
    def test_15_19_rebid_ranges(self):
        for hand, bid in [
            ('AQ3.KJ3.K32.Q432', '1N'),
            ('AQJ.KJ3.K32.Q432', '1N'),
            ('AQJ.KQ3.K32.Q432', '2N'),
            ('AQJ.KQJ.K32.Q432', '2N'),
            ('AKJ.KQJ.K32.Q432', '3N'),
        ]:
            with self.subTest(hand=hand):
                self.assertEqual(decision(hand, auction('1C', '1S')).bid, bid)
        self.assertEqual((meaning(auction('1C', '1S'), '1N').hcp_min, meaning(auction('1C', '1S'), '1N').hcp_max), (15, 16))
        self.assertEqual((meaning(auction('1C', '1S'), '2N').hcp_min, meaning(auction('1C', '1S'), '2N').hcp_max), (17, 18))
        self.assertEqual((meaning(auction('1C', '1S'), '3N').hcp_min, meaning(auction('1C', '1S'), '3N').hcp_max), (19, 22))
        self.assertIsNone(meaning(auction('1C', '1S'), '3N').balanced)

    def test_known_four_card_major_fit_yields_to_natural_raise(self):
        self.assertIsNone(decision('AQ32.KJ3.K32.Q32', auction('1C', '1S')))

    def test_ebu_five_card_major_forcing_continuation_examples(self):
        h = 'AJ743.43.Q32.K93'
        self.assertEqual(decision(h, auction('1D', '1S', '1N')).bid, '3D')
        self.assertEqual(decision(h, auction('1H', '1S', '1N')).bid, '3C')
        self.assertEqual(decision(h, auction('1H', '1S', '2N')).bid, '3C')

    def test_six_card_major_weak_and_invitational_rebids(self):
        self.assertEqual(decision('KJ5432.32.Q32.32', auction('1C', '1S', '1N')).bid, '2S')
        self.assertEqual(decision('KJ5432.Q2.K32.32', auction('1C', '1S', '1N')).bid, '3S')

    def test_notrump_rebid_does_not_switch_on_stayman(self):
        m = meaning(auction('1C', '1S', '1N'), '2C')
        self.assertFalse(m.artificial)
        self.assertEqual(m.suit, 'C')

    def test_one_nt_response_followed_by_two_nt_is_17_18(self):
        m = meaning(auction('1S', '1N'), '2N')
        self.assertEqual((m.hcp_min, m.hcp_max), (17, 18))

    def test_double_then_nt_continuations_are_natural(self):
        sequence = ['1H', 'X', 'PASS', '1S', 'PASS', '1N', 'PASS']
        self.assertEqual(decision('KJ5432.32.Q32.32', sequence).bid, '4S')
        self.assertFalse(meaning(sequence, '2C').artificial)

    def test_strong_club_late_signoff_keeps_previously_agreed_fit(self):
        m = meaning(auction('2C', '2D', '2S', '4S', '5D'), '5S')
        self.assertEqual(m.min_length, {'S': 3})

    def test_three_card_preference_does_not_create_a_false_eight_card_fit(self):
        hand = 'J962.Q93.KJ85.KJ'
        self.assertEqual(decision(hand, auction('1H', '1S', '1N', '3H', '3S')).bid, '3N')


if __name__ == '__main__':
    unittest.main()
