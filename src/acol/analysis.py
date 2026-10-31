"""Perfect-information review, separate from the limited-observation bidder.

Callers must authorize completed-board access before sending a complete deal.
This module never feeds its results into live robot decisions.
"""
import re
from .core import Hand, SEATS, SUITS, seat_index

VULNERABILITY = {'None': 0, 'Both': 1, 'NS': 2, 'EW': 3}


def par_contract(text):
    if text.lower() in ('pass', 'passed out'):
        return None
    match = re.fullmatch(r'([1-7])([SHDCN])(\*)?-(NS|EW|[NESW])([+-]\d+)?', text)
    if not match:
        raise RuntimeError('Unrecognized native par contract format')
    level, strain, doubled, declarers, delta = match.groups()
    change = int(delta or 0)
    return {'level': int(level), 'strain': strain, 'declarers': list(declarers),
            'doubled': 1 if doubled or change < 0 else 0,
            'overtricks': max(0, change), 'undertricks': max(0, -change),
            'label': text}


def analyze_deal(hands, dealer, vulnerability, dds, max_threads=2):
    if not isinstance(hands, dict) or set(hands) != set(SEATS):
        raise ValueError('Expected four compass hands')
    if any(not isinstance(cards, (str, list, tuple)) or
           (not isinstance(cards, str) and any(not isinstance(card, str) for card in cards))
           for cards in hands.values()):
        raise ValueError('Invalid review hand encoding')
    parsed = {seat: Hand(hands[seat]) for seat in SEATS}
    if len({card for hand in parsed.values() for card in hand.cards}) != 52:
        raise ValueError('The complete deal contains duplicate cards')
    dealer_i = seat_index(dealer)
    if not isinstance(vulnerability, str) or vulnerability not in VULNERABILITY:
        raise ValueError('Invalid vulnerability')
    pbn = 'N:' + ' '.join(parsed[seat].pbn for seat in SEATS)
    solved = dds.calc_all_tables_pbn([pbn], mode=-1, max_threads=max_threads)
    tables = solved.get('tables', [])
    if len(tables) != 1:
        raise RuntimeError('Native solver did not return one complete table')
    values = tables[0].get('res_table')
    if not isinstance(values, list) or len(values) != 5 or any(
            not isinstance(row, list) or len(row) != 4 or
            any(type(n) is not int or not 0 <= n <= 13 for n in row) for row in values):
        raise RuntimeError('Native solver returned an invalid trick table')
    # DDS table rows are S,H,D,C,NT, and columns are N,E,S,W.
    tricks = {seat: {strain: values[(SUITS + 'N').index(strain)][i]
                     for strain in 'CDHSN'} for i, seat in enumerate(SEATS)}
    native = dds.dealer_par(tables[0], dealer_i, VULNERABILITY[vulnerability])
    if type(native.get('score')) is not int or not isinstance(native.get('contracts'), list):
        raise RuntimeError('Native solver returned an invalid par result')
    contracts = [parsed for text in native['contracts'] if (parsed := par_contract(text)) is not None]
    # DealerPar's score is signed NS; dealer chooses who first has the option
    # to bid. Tests with each dealer and rotated deals verify this orientation.
    return {'tricks': tricks, 'par': {'nsScore': native['score'], 'contracts': contracts},
            'dealer': SEATS[dealer_i], 'vulnerability': vulnerability,
            'source': 'BEN DDS', 'perfectInformation': True}
