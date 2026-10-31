import json
import pathlib
import unittest
from copy import deepcopy
from acol.claims import adjudicate_claim
from acol.core import Hand, SEATS, RANKS
from acol_api import create_app
from ddsolver.ddsolver import dds3

FIXTURE = json.loads((pathlib.Path(__file__).parent / 'fixtures/claim-endplay.json').read_text())
FIXTURE.pop('note')
FULL = {'hands': {seat: [suit + rank for rank in RANKS] for seat, suit in zip(SEATS, 'DHSC')},
        'plays': [], 'contract': {'declarer': 'S', 'strain': 'S'}}
CHALLENGE = {'hands': {seat: list(Hand(pbn).cards) for seat, pbn in zip(SEATS, [
    'QT876.QT984.3.T5', 'AK.J65.A9.Q87632', 'J952.2.JT65.KJ94', '43.AK73.KQ8742.A'])},
    'plays': [], 'contract': {'declarer': 'E', 'strain': 'N'}}


class ClaimTests(unittest.TestCase):
    def solve(self, position, side='NS', tricks=2):
        return adjudicate_claim(**position, claim={'side': side, 'tricks': tricks}, dds=dds3)

    def test_claimant_can_choose_good_play_instead_of_being_required_to_survive_blunders(self):
        result = self.solve(FIXTURE)
        self.assertTrue(result['accept'])
        self.assertEqual(result['guaranteed'], 2)
        # NS need not survive throwing away HA under partner's winning SA.
        mistake = deepcopy(FIXTURE)
        mistake['plays'] += [{'seat': 'N', 'card': 'SA'}, {'seat': 'E', 'card': 'SK'}, {'seat': 'S', 'card': 'HA'}]
        rejected = self.solve(mistake)
        self.assertFalse(rejected['accept'])
        self.assertEqual((rejected['guaranteed'], rejected['remainingTricks']), (1, 2))

    def test_native_full_hand_trump_claim_has_no_four_trick_limit(self):
        result = self.solve(FULL, tricks=13)
        self.assertTrue(result['accept'])
        self.assertEqual((result['guaranteed'], result['remainingTricks']), (13, 13))
        no_trump = {**FULL, 'contract': {'declarer': 'S', 'strain': 'N'}}
        self.assertEqual(self.solve(no_trump, tricks=1)['guaranteed'], 0)

    def test_full_hand_nontrivial_overclaim_against_best_defence(self):
        result = self.solve(CHALLENGE, 'EW', 10)
        self.assertTrue(result['accept'])
        self.assertEqual(result['guaranteed'], 10)
        rejected = self.solve(CHALLENGE, 'EW', 11)
        self.assertFalse(rejected['accept'])
        self.assertEqual(rejected['guaranteed'], 10)

    def test_partial_trick_count_and_orientation_for_each_side_on_turn(self):
        full = deepcopy(FULL)
        for count, play in enumerate([None, {'seat': 'W', 'card': 'C2'}, {'seat': 'N', 'card': 'D2'}, {'seat': 'E', 'card': 'H2'}]):
            if play:
                full['plays'].append(play)
            with self.subTest(partial_cards=count):
                result = self.solve(full, tricks=13)
                self.assertEqual((result['guaranteed'], result['remainingTricks']), (13, 13))
                defence = self.solve(full, 'EW', 1)
                self.assertFalse(defence['accept'])
                self.assertEqual(defence['guaranteed'], 0)

    def test_concession_validates_position_and_does_not_require_dds(self):
        result = adjudicate_claim(**FULL, claim={'side': 'EW', 'tricks': 0}, dds=None)
        self.assertTrue(result['accept'])
        self.assertEqual(result['guaranteed'], 0)
        with self.assertRaises(ValueError):
            adjudicate_claim(**{**FULL, 'hands': {}}, claim={'side': 'EW', 'tricks': 0}, dds=None)

    def test_illegal_history_duplicate_deal_wrong_order_revoke_and_overlarge_claim(self):
        invalid = []
        duplicate = deepcopy(FULL); duplicate['hands']['N'] = duplicate['hands']['E']; invalid.append(duplicate)
        wrong_order = deepcopy(FULL); wrong_order['plays'] = [{'seat': 'N', 'card': 'D2'}]; invalid.append(wrong_order)
        wrong_owner = deepcopy(FULL); wrong_owner['plays'] = [{'seat': 'W', 'card': 'D2'}]; invalid.append(wrong_owner)
        revoke = deepcopy(FULL)
        revoke['hands']['N'][0], revoke['hands']['W'][0] = revoke['hands']['W'][0], revoke['hands']['N'][0]
        revoke['plays'] = [{'seat': 'W', 'card': 'C2'}, {'seat': 'N', 'card': 'D2'}]
        invalid.append(revoke)
        for position in invalid:
            with self.subTest(position=invalid.index(position)), self.assertRaises(ValueError):
                self.solve(position)
        with self.assertRaises(ValueError):
            self.solve(FIXTURE, tricks=3)
        for claim in [{'side': 'S', 'tricks': 1}, {'side': 'NS', 'tricks': True}, {'side': 'NS', 'tricks': -1}]:
            with self.assertRaises(ValueError):
                adjudicate_claim(**FULL, claim=claim, dds=dds3)

    def test_dedicated_api_boundary_unavailable_native_and_response_privacy(self):
        app = create_app(object(), review_solver=dds3)
        client = app.test_client()
        body = {**FULL, 'claim': {'side': 'NS', 'tricks': 13}}
        response = client.post('/claim', json=body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['accept'])
        self.assertNotIn('hands', response.json)
        self.assertEqual(client.get('/').json['claim_api'], 1)
        for bad in [{**body, 'traveller': []}, {**body, 'claim': {**body['claim'], 'line': 'anything'}}, {**body, 'plays': [{'seat': 'S', 'card': 'SA'}]}]:
            self.assertEqual(client.post('/claim', json=bad).status_code, 400)
        self.assertEqual(client.post('/claim?hand=private', json=body).status_code, 400)
        self.assertEqual(client.get('/claim').status_code, 405)
        self.assertEqual(create_app().test_client().post('/claim', json=body).status_code, 503)
        class FailedNative:
            def SolverContext(self):
                return None
            def solve_board_pbn(self, *args, **kwargs):
                raise RuntimeError('private deal must not appear in error output')
        failed_app = create_app(object(), review_solver=FailedNative())
        failed = failed_app.test_client().post('/claim', json=body)
        self.assertEqual(failed.status_code, 500)
        self.assertNotIn('private deal', str(failed.json))
        app.extensions['acol_review_pool'].shutdown()
        failed_app.extensions['acol_review_pool'].shutdown()


if __name__ == '__main__':
    unittest.main()
