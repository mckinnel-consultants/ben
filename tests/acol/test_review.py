"""Independent regressions for cross-module forcing obligations."""
import unittest

from acol.core import Auction
from acol.system import choose_bid


class ReviewTests(unittest.TestCase):
    hand = 'A2.AQJ43.KQ32.32'

    def test_opener_game_force_survives_later_preference_and_double(self):
        for bids in [
            ['1H', 'PASS', '2C', 'PASS', '3D', 'X', '3H', 'PASS'],
            ['1H', 'PASS', '2C', 'PASS', '3D', 'PASS', '3H', 'X'],
        ]:
            with self.subTest(bids=bids):
                decision = choose_bid(self.hand, Auction(bids))
                self.assertEqual(decision.bid, '4H')
                self.assertEqual(decision.rule, 'general.game-force')

    def test_opponents_game_does_not_satisfy_our_force(self):
        bids = ['1H', 'PASS', '2C', 'PASS', '3D', 'PASS', '3H', '4S']
        decision = choose_bid(self.hand, Auction(bids))
        self.assertEqual(decision.bid, 'X')
        self.assertEqual(decision.rule, 'general.game-force-penalty')

    def test_completed_game_force_does_not_create_another_raise(self):
        bids = ['1H', 'PASS', '2C', 'PASS', '3D', 'X', '4H', 'PASS']
        decision = choose_bid(self.hand, Auction(bids))
        self.assertEqual(decision.bid, 'PASS')

    def test_unknown_nonforcing_competitive_continuation_can_pass(self):
        bids = ['1H', 'PASS', '1S', 'PASS', '2C', 'X', '2H', 'PASS']
        decision = choose_bid(self.hand, Auction(bids))
        self.assertEqual(decision.bid, 'PASS')


if __name__ == '__main__':
    unittest.main()
