"""Native DDS integration on a public BEN challenge deal (Python 3.12)."""
import unittest
from acol.core import Auction, Hand
from acol.system import choose_bid
from acol.play import reconstruct, legal_cards
from acol.sampling import choose_card
from ddsolver.ddsolver import DDSolver


class NativeBoardTests(unittest.TestCase):
    def test_complete_auction_and_52_cards_through_sampled_dds(self):
        hands = [Hand(pbn) for pbn in [
            'QT876.QT984.3.T5', 'AK.J65.A9.Q87632',
            'J952.2.JT65.KJ94', '43.AK73.KQ8742.A',
        ]]
        auction = Auction()
        while not auction.ended:
            self.assertLess(len(auction.calls), 80)
            bid = choose_bid(hands[auction.turn], auction)
            auction = Auction(auction.bids + [bid.bid])
        self.assertIsNotNone(auction.contract, 'This challenge must exercise card play')
        solver = DDSolver(max_threads=2)
        plays = []
        declarer = auction.contract['declarer']
        dummy = (declarer + 2) % 4
        for _ in range(52):
            state = reconstruct(plays, auction.contract)
            seat = state['turn']
            # Only one player's original hand and the exposed dummy enter
            # sampling. Actual concealed hands remain in this test harness.
            known = {declarer if seat == dummy else seat: hands[declarer if seat == dummy else seat]}
            if plays:
                known[dummy] = hands[dummy]
            result = choose_card(known, auction, plays, solver)
            self.assertIn(result['card'], legal_cards(hands[seat], state))
            plays.append(result['card'])
        self.assertEqual(len(set(plays)), 52)
        state = reconstruct(plays, auction.contract)
        self.assertEqual(sum(state['won']), 13)
        self.assertTrue(all(len(cards) == 13 for cards in state['assigned'].values()))


if __name__ == '__main__':
    unittest.main()
