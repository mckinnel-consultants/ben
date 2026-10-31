import random
import unittest
from unittest.mock import Mock, patch
from acol.core import Auction, Hand, Meaning, PROFILE
from acol.play import reconstruct, legal_cards, card_code
from acol.sampling import sample_deals, choose_card, DECK
from acol.system import choose_bid, interpret_auction


class CoreTests(unittest.TestCase):
    def test_legal_auction_and_declarer_rotate(self):
        for dealer in range(4):
            a = Auction(['1H', 'PASS', '2H', 'X', 'XX', 'PASS', 'PASS', 'PASS'], dealer)
            self.assertTrue(a.ended)
            self.assertEqual(a.contract, dict(level=2, strain='H', declarer=dealer, doubled=2))
            self.assertEqual(a.legal_bids(), [])
        for bids in [['1H', '1D'], ['1H', 'PASS', 'X'], ['1H', 'XX'], ['PASS'] * 5]:
            with self.assertRaises(ValueError):
                Auction(bids)

    def test_opening_inference_uses_acol(self):
        meaning = interpret_auction(Auction(['1N']))[0][1]
        self.assertEqual((meaning.hcp_min, meaning.hcp_max), (12, 14))
        for bid in ['2D', '2H', '2S']:
            meaning = interpret_auction(Auction([bid]))[0][1]
            self.assertEqual((meaning.hcp_min, meaning.hcp_max), (5, 9))
            self.assertGreaterEqual(meaning.min_length[bid[1]], 6)

    def test_keycard_penalty_uses_0314_sets(self):
        hand = Hand('AKQJ.432.A32.432')
        meaning = Meaning(suit='S', keycards=(0, 3))
        self.assertEqual(meaning.penalty(hand), 0)
        self.assertGreater(Meaning(suit='S', keycards=(1, 4)).penalty(hand), 0)

    def test_random_selfplay_legality_and_termination(self):
        rng = random.Random(7610)
        for board in range(160):
            deck = list(DECK)
            rng.shuffle(deck)
            hands = [Hand(deck[seat * 13:seat * 13 + 13]) for seat in range(4)]
            auction = Auction(dealer=board % 4)
            for _ in range(160):
                if auction.ended:
                    break
                decision = choose_bid(hands[auction.turn], auction, vulnerability=['None', 'NS', 'EW', 'Both'][board % 4])
                self.assertIn(decision.bid, auction.legal_bids())
                auction = Auction(auction.bids + [decision.bid], auction.dealer)
            self.assertTrue(auction.ended, auction.bids)
            self.assertLess(len(auction.calls), 80, auction.bids)
            # Interpretation must also work on every generated auction.
            self.assertEqual(len(interpret_auction(auction)), len(auction.calls))


class SamplingTests(unittest.TestCase):
    def setUp(self):
        self.auction = Auction(['1N', 'PASS', '3N', 'PASS', 'PASS', 'PASS'])
        self.known = {1: Hand('AKQJ.432.A32.432')}

    def test_samples_keep_visible_cards_and_deck_integrity(self):
        samples, state, info = sample_deals(self.known, self.auction, count=8, candidates=64)
        self.assertEqual(state['turn'], 1)
        self.assertEqual(info['method'], 'acol-public-auction-constraints')
        for deal in samples:
            self.assertEqual(deal[1].pbn, self.known[1].pbn)
            self.assertEqual(len(set(c for h in deal.values() for c in h.cards)), 52)
        again, _, _ = sample_deals(self.known, self.auction, count=8, candidates=64)
        self.assertEqual([[d[s].pbn for s in range(4)] for d in samples], [[d[s].pbn for s in range(4)] for d in again])

    def test_public_voids_are_never_relaxed(self):
        plays = ['SA', 'H5', 'S2', 'S3']
        samples, state, _ = sample_deals(self.known, self.auction, plays, count=8, candidates=64)
        self.assertIn('S', state['voids'][2])
        for deal in samples:
            self.assertEqual(deal[2].length('S'), 0)
            self.assertIn('H5', deal[2].cards)
            self.assertIn('S3', deal[0].cards)
        with self.assertRaises(ValueError):
            sample_deals({**self.known, 2: self.known[1]}, self.auction, plays)
        with self.assertRaises(ValueError):
            reconstruct(plays + ['SK', 'S4'], self.auction.contract)

    def test_dds_receives_only_synthetic_deals_and_must_return_all_cards(self):
        outer = self
        class Solver:
            def solve(self, strain, leader, trick, pbns, solutions, purpose):
                outer.assertEqual((strain, leader, trick, solutions), (0, 1, [], 3))
                outer.assertEqual(len(pbns), 8)
                outer.assertTrue(all(p.startswith('N:') for p in pbns))
                return {card_code(c): [7 if c == 'S2' else 6] * len(pbns) for c in outer.known[1].cards}
        result = choose_card(self.known, self.auction, [], Solver(), count=8, candidates=64)
        self.assertIn(result['card'], self.known[1].cards)
        self.assertEqual(result['source'], 'acol-sampled-dds')
        class FailedSolver:
            def solve(self, *args, **kwargs):
                return None
        with self.assertRaises(RuntimeError):
            choose_card(self.known, self.auction, [], FailedSolver(), count=8, candidates=64)

    def test_forced_card_skips_sampling_and_dds_but_keeps_input_validation(self):
        auction = Auction(['1N', 'PASS', 'PASS', 'PASS'])
        known = {1: Hand('.AKQJT98765432..'), 2: Hand('..AKQJT98765432.')}
        plays = [suit + rank for rank in '23456789TJQK' for suit in 'HDCS']
        solver = Mock()
        with patch('acol.sampling._sample_deals', side_effect=AssertionError('No sampling for forced cards')):
            result = choose_card(known, auction, plays, solver)
            self.assertEqual(result['card'], 'HA')
            self.assertEqual(result['source'], 'forced-legal-card')
            self.assertEqual(result['inference']['samples'], 0)
            for visible, history, options in [
                (known, plays + ['H2'], {}),  # Duplicate public card.
                ({**known, 0: known[1]}, plays, {}),  # Overlapping visible hands.
                ({1: Hand('A.KQJT98765432..'), 2: known[2]}, plays, {}),
                ({2: known[2]}, plays, {}),  # Acting hand is not visible.
                (known, plays, {'count': 0}),  # Invalid budget stays invalid.
            ]:
                with self.assertRaises(ValueError):
                    choose_card(visible, auction, history, solver, **options)
        solver.solve.assert_not_called()

    def test_forced_follow_suit_does_not_sample_concealed_cards(self):
        auction = Auction(['1N', 'PASS', 'PASS', 'PASS'])
        # South must follow the opening spade with its only spade; none of
        # the actual concealed North/West cards are needed to select it.
        known = {2: Hand('2.AKQJ.AKQJ.AKQJ')}
        with patch('acol.sampling._sample_deals', side_effect=AssertionError('Unexpected sample')):
            result = choose_card(known, auction, ['SA'], Mock())
        self.assertEqual(result['card'], 'S2')
        self.assertEqual(result['inference']['candidates'], 0)


if __name__ == '__main__':
    unittest.main()
