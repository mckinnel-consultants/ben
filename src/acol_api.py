"""Standalone Acol endpoint for BEN. Does not load the upstream neural models."""
if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()

import argparse
import logging
from dataclasses import asdict
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from acol.core import Auction, Hand, PROFILE, seat_index
from acol.system import choose_bid, decision_payload, interpret_auction, interpret_call
from acol.play import reconstruct
from acol.sampling import choose_card
from acol.analysis import analyze_deal


def _review_result(hands, dealer, vulnerability, native):
    # gevent reports unhandled thread-pool exceptions. Keep private review
    # arguments and native exception strings out of those diagnostics.
    try:
        return analyze_deal(hands, dealer, vulnerability, native), None
    except ValueError:
        return None, 'invalid'
    except Exception:
        return None, 'failed'


def create_app(solver=None, samples=24, candidates=512, review_solver=None):
    from gevent.threadpool import ThreadPoolExecutor
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 65536
    # A native full-deal solve must not occupy the gevent request hub. One
    # review at a time, with at most two DDS workers, leaves readiness and bid
    # explanation requests responsive while review work is running.
    review_pool = ThreadPoolExecutor(max_workers=1)
    app.extensions['acol_review_pool'] = review_pool
    # GET requests contain private cards. Neither access logs nor exception
    # diagnostics should print request URLs or query parameters.
    logging.getLogger('werkzeug').disabled = True

    def parse():
        allowed = {'hand', 'seat', 'dealer', 'vul', 'ctx', 'dummy', 'played', 'matchtype', 'details'}
        if set(request.args) - allowed or any(len(v) != 1 for _, v in request.args.lists()):
            raise ValueError('Unknown or duplicate request field')
        ctx = request.args.get('ctx', '')
        if len(ctx) % 2 or len(ctx) > 640:
            raise ValueError('Invalid compact auction')
        auction = Auction([ctx[i:i + 2] for i in range(0, len(ctx), 2)], seat_index(request.args.get('dealer', 'N')))
        seat = seat_index(request.args['seat'])
        hand = Hand(request.args['hand'])
        vul = request.args.get('vul', 'None')
        if vul not in ['None', 'NS', 'EW', 'Both']:
            raise ValueError('Invalid vulnerability')
        if request.args.get('matchtype', 'MP') != 'MP':
            raise ValueError('This profile is configured for matchpoints')
        return auction, seat, hand, vul

    @app.get('/')
    def ready():
        return jsonify(name='BEN EBU Acol rules + public-auction sampling + DDS',
                       system=PROFILE, bidding_engine='rules', neural_fallback=False,
                       inference='acol-public-auction-constraints', dds_ready=solver is not None,
                       review_api=1)

    @app.get('/bid')
    def bid():
        auction, seat, hand, vul = parse()
        if 'dummy' in request.args or 'played' in request.args:
            raise ValueError('Bidding accepts only one hand and the public auction')
        decision = choose_bid(hand, auction, seat, vul)
        payload = decision_payload(decision)
        # Interpret the public call separately from the private hand that chose
        # it. Including this result avoids a second request before publishing
        # the bid, while keeping exactly the /explain meaning for that auction.
        try:
            public = Auction(auction.bids + [decision.bid], auction.dealer)
            call = public.calls[-1]
            payload['public_meaning'] = {'seat': call.seat, 'bid': call.bid,
                                        'system': PROFILE['id'],
                                        **asdict(interpret_call(auction, call))}
        except Exception:
            # Supplementary metadata must never discard an otherwise legal bid.
            app.logger.warning('Public bid meaning unavailable')
        return jsonify(payload)

    @app.get('/explain')
    @app.post('/explain')
    def explain():
        if request.method == 'GET':
            # Keep the old adapter format available, but new callers send only
            # the public auction. No private hand participates in interpretation.
            if 'hand' in request.args:
                auction, _, _, _ = parse()
            else:
                allowed = {'dealer', 'ctx'}
                if set(request.args) - allowed or any(len(v) != 1 for _, v in request.args.lists()):
                    raise ValueError('Unknown public explanation field')
                ctx = request.args.get('ctx', '')
                if len(ctx) % 2 or len(ctx) > 640:
                    raise ValueError('Invalid compact auction')
                auction = Auction([ctx[i:i + 2] for i in range(0, len(ctx), 2)], request.args.get('dealer', 'N'))
        else:
            body = request.get_json()
            if request.args or not isinstance(body, dict) or set(body) != {'auction', 'dealer'} or not isinstance(body['auction'], list) or len(body['auction']) > 160:
                raise ValueError('Expected public auction and dealer only')
            if any(not isinstance(call, (str, dict)) or
                   (isinstance(call, dict) and set(call) != {'seat', 'bid'}) for call in body['auction']):
                raise ValueError('Public calls contain seat and bid only')
            auction = Auction(body['auction'], body['dealer'])
        return jsonify(system=PROFILE['id'], calls=[{'seat': c.seat, 'bid': c.bid, **asdict(m)} for c, m in interpret_auction(auction)])

    @app.post('/analyze')
    def analyze():
        if solver is None:
            return jsonify(error='DDS is not ready'), 503
        body = request.get_json()
        if request.args or not isinstance(body, dict) or set(body) != {'hands', 'dealer', 'vulnerability'}:
            raise ValueError('Expected a complete review deal, dealer and vulnerability')
        native = review_solver
        if native is None:
            from ddsolver.ddsolver import dds3
            native = dds3
        result, failure = review_pool.submit(_review_result, body['hands'], body['dealer'], body['vulnerability'], native).result()
        if failure == 'invalid':
            raise ValueError('Invalid review input')
        if failure:
            raise RuntimeError('Native review failed')
        return jsonify(result)

    @app.get('/lead')
    @app.get('/play')
    def play():
        auction, seat, hand, _ = parse()
        if solver is None:
            return jsonify(error='DDS is not ready'), 503
        encoded = request.args.get('played', '')
        if len(encoded) % 2 or len(encoded) > 104:
            raise ValueError('Invalid public play history')
        plays = [encoded[i:i + 2] for i in range(0, len(encoded), 2)]
        state = reconstruct(plays, auction.contract)
        declarer = auction.contract['declarer']
        dummy = (declarer + 2) % 4
        if len(plays) == 52:
            raise ValueError('The board has ended')
        known = {seat: hand}
        if request.path == '/lead':
            if plays or 'dummy' in request.args or seat != state['turn']:
                raise ValueError('Opening lead accepts only leader’s hand; dummy is concealed')
        else:
            if not plays or 'dummy' not in request.args or seat == dummy:
                raise ValueError('Play requires exposed dummy and the player’s hand')
            if seat != state['turn'] and not (state['turn'] == dummy and seat == declarer):
                raise ValueError('Card play requested out of turn')
            known[dummy] = Hand(request.args['dummy'])
        return jsonify(**choose_card(known, auction, plays, solver, samples, candidates), system=PROFILE['id'])

    @app.errorhandler(ValueError)
    @app.errorhandler(KeyError)
    def invalid(error):
        return jsonify(error='Invalid Acol request'), 400

    @app.errorhandler(Exception)
    def failed(error):
        if isinstance(error, HTTPException):
            return jsonify(error='Unknown endpoint or unsupported method'), error.code
        # No private request data in logs or error responses.
        app.logger.error('Acol request failed: %s', type(error).__name__)
        return jsonify(error='Acol decision failed; retain the current turn'), 500

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8085)
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--candidates', type=int, default=512)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    from ddsolver.ddsolver import DDSolver
    from gevent.pywsgi import WSGIServer
    solver = DDSolver(max_threads=args.threads)
    WSGIServer((args.host, args.port), create_app(solver, args.samples, args.candidates), log=None).serve_forever()
