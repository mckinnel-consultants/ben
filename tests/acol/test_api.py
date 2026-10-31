import unittest
from unittest.mock import patch
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

    def test_bid_includes_the_public_explanation_without_private_hand_constraints(self):
        responses = [self.client.get('/bid', query_string={**self.params, 'hand': hand}).json
                     for hand in ['KJ32.A32.KJ2.432', 'QJ32.A32.KJ2.K32']]
        for response in responses:
            self.assertEqual(response['bid'], '1N')
            explained = self.client.post('/explain', json={
                'dealer': 'N', 'auction': [{'seat': 'N', 'bid': response['bid']}],
            }).json
            self.assertEqual(response['public_meaning'], {
                **explained['calls'][-1], 'system': explained['system'],
            })
        self.assertEqual(responses[0]['public_meaning'], responses[1]['public_meaning'])
        self.assertEqual((responses[0]['public_meaning']['hcp_min'],
                          responses[0]['public_meaning']['hcp_max']), (12, 14))

    def test_supplementary_meaning_failure_does_not_discard_a_legal_bid(self):
        with patch('acol_api.interpret_call', side_effect=RuntimeError('private diagnostic')):
            response = self.client.get('/bid', query_string=self.params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['bid'], '1N')
        self.assertNotIn('public_meaning', response.json)
        self.assertNotIn('private diagnostic', response.text)

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
