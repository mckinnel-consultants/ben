import unittest
import threading
import time
import gevent
from acol.analysis import analyze_deal, par_contract
from acol.core import Hand, SEATS
from acol_api import create_app
from ddsolver.ddsolver import dds3

CHALLENGE = dict(zip(SEATS, ['QT876.QT984.3.T5', 'AK.J65.A9.Q87632', 'J952.2.JT65.KJ94', '43.AK73.KQ8742.A']))


class AnalysisTests(unittest.TestCase):
    def test_native_table_par_dealer_and_vulnerability(self):
        for dealer in SEATS:
            result = analyze_deal(CHALLENGE, dealer, 'None', dds3)
            self.assertEqual(result['par']['nsScore'], -430)
            self.assertEqual(result['par']['contracts'][0], {'level': 3, 'strain': 'N', 'declarers': ['E', 'W'], 'doubled': 0, 'overtricks': 1, 'undertricks': 0, 'label': '3N-EW+1'})
            self.assertEqual(result['tricks']['E'], {'C': 10, 'D': 11, 'H': 10, 'S': 6, 'N': 10})
            self.assertEqual(result['tricks']['N'], {'C': 3, 'D': 2, 'H': 3, 'S': 6, 'N': 3})
            self.assertTrue(result['perfectInformation'])
        self.assertEqual(analyze_deal(CHALLENGE, 'E', 'EW', dds3)['par']['nsScore'], -630)
        self.assertEqual(analyze_deal(CHALLENGE, 'E', 'NS', dds3)['par']['nsScore'], -430)
        rotated = {SEATS[(i + 1) % 4]: CHALLENGE[seat] for i, seat in enumerate(SEATS)}
        self.assertEqual(analyze_deal(rotated, 'E', 'None', dds3)['par']['nsScore'], 430)

    def test_par_sacrifice_is_doubled_and_not_a_makeable_contract(self):
        deal = dict(zip(SEATS, ['9.J2465.3J.5Q4TK', 'A73.T793.Q79.798', '8T5K4.8KQ.54A.32', 'Q6J2.A.8T62K.AJ6']))
        result = analyze_deal(deal, 'N', 'None', dds3)
        contract = result['par']['contracts'][0]
        self.assertEqual(result['par']['nsScore'], 100)
        self.assertEqual((contract['strain'], contract['level'], contract['doubled'], contract['undertricks']), ('D', 4, 1, 1))
        self.assertLess(result['tricks']['E']['D'], 10)
        self.assertIsNone(par_contract('pass'))
        with self.assertRaises(RuntimeError):
            par_contract('unexpected format')

    def test_review_api_is_separate_and_validates_complete_deals(self):
        client = create_app(object(), review_solver=dds3).test_client()
        good = {'hands': CHALLENGE, 'dealer': 'N', 'vulnerability': 'None'}
        response = client.post('/analyze', json=good)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['par']['nsScore'], -430)
        for bad in [{**good, 'hands': {**CHALLENGE, 'E': CHALLENGE['N']}}, {**good, 'secret': 1}, {**good, 'dealer': 'bad'}, {**good, 'vulnerability': 'invalid'}]:
            self.assertEqual(client.post('/analyze', json=bad).status_code, 400)
        self.assertEqual(client.get('/analyze').status_code, 405)
        self.assertEqual(create_app().test_client().post('/analyze', json=good).status_code, 503)

    def test_explanation_uses_public_auction_without_a_hand(self):
        client = create_app().test_client()
        auction = [{'seat': 'N', 'bid': '1N'}, {'seat': 'E', 'bid': 'PASS'}, {'seat': 'S', 'bid': '2D'}]
        response = client.post('/explain', json={'dealer': 'N', 'auction': auction})
        self.assertEqual(response.status_code, 200)
        call = response.json['calls'][-1]
        self.assertTrue(call['artificial'])
        self.assertEqual(call['min_length']['H'], 5)
        self.assertEqual(client.post('/explain', json={'dealer': 'N', 'auction': auction, 'hand': CHALLENGE['S']}).status_code, 400)
        self.assertEqual(client.post('/explain?hand=private', json={'dealer': 'N', 'auction': auction}).status_code, 400)
        self.assertEqual(client.post('/explain', json={'dealer': 'N', 'auction': [{**auction[0], 'hand': CHALLENGE['N']}]}).status_code, 400)
        self.assertEqual(client.get('/explain?dealer=N&dealer=E&ctx=1N').status_code, 400)

    def test_health_and_explanations_remain_responsive_during_native_review(self):
        entered, release = threading.Event(), threading.Event()
        class SlowNative:
            def calc_all_tables_pbn(self, *args, **kwargs):
                entered.set()
                release.wait(2)
                return {'tables': [{'res_table': [[7, 6, 7, 6] for _ in range(5)]}]}
            def dealer_par(self, *args):
                return {'score': 90, 'contracts': ['1N-NS']}
        app = create_app(object(), review_solver=SlowNative())
        started = time.monotonic()
        pending = gevent.spawn(lambda: app.test_client().post('/analyze', json={'hands': CHALLENGE, 'dealer': 'N', 'vulnerability': 'None'}))
        try:
            gevent.sleep(.05)
            self.assertTrue(entered.is_set())
            health = gevent.spawn(lambda: app.test_client().get('/'))
            explanation = gevent.spawn(lambda: app.test_client().post('/explain', json={'dealer': 'N', 'auction': ['1N']}))
            gevent.joinall([health, explanation], timeout=.5)
            self.assertTrue(health.ready())
            self.assertTrue(explanation.ready())
            self.assertFalse(pending.ready(), 'The request hub must not block until the native solve finishes')
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(health.value.status_code, 200)
        finally:
            release.set()
            pending.join(timeout=2)
            app.extensions['acol_review_pool'].shutdown()
        self.assertEqual(pending.value.status_code, 200)


if __name__ == '__main__':
    unittest.main()
