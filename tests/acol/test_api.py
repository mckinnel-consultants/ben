import unittest
from acol_api import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.params = dict(hand='KJ32.A32.KJ2.432', seat='N', dealer='N', vul='None', ctx='')

    def test_bid_and_capabilities(self):
        response = self.client.get('/bid', query_string=self.params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['bid'], '1N')
        self.assertFalse(response.json['neural_fallback'])
        ready = self.client.get('/').json
        self.assertEqual(ready['system']['nt_range'], [12, 14])
        self.assertEqual(ready['system']['rkcb'], '0314')
        self.assertFalse(ready['dds_ready'])

    def test_reject_hidden_deals_invalid_turn_and_dummy_before_lead(self):
        for extra in [dict(deal='private'), dict(dummy=self.params['hand']), dict(played=''), dict(seat='E'), dict(ctx='1N1C'), dict(hand='bad')]:
            response = self.client.get('/bid', query_string={**self.params, **extra})
            self.assertEqual(response.status_code, 400, extra)
            self.assertNotIn(self.params['hand'], response.text)
        client = create_app(object()).test_client()
        response = client.get('/lead', query_string={**self.params, 'ctx': '1N--3N------', 'seat': 'E', 'dummy': self.params['hand']})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get('/lead', query_string={**self.params, 'ctx': '1N--3N------', 'seat': 'E'}).status_code, 503)

    def test_explanations_match_acol_inference(self):
        response = self.client.get('/explain', query_string={**self.params, 'ctx': '1N--2D'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['calls'][0]['hcp_max'], 14)
        transfer = response.json['calls'][2]
        self.assertTrue(transfer['artificial'])
        self.assertEqual(transfer['min_length']['H'], 5)

    def test_unknown_routes_do_not_report_engine_failure(self):
        self.assertEqual(self.client.get('/unknown').status_code, 404)
        self.assertEqual(self.client.post('/bid').status_code, 405)


if __name__ == '__main__':
    unittest.main()
