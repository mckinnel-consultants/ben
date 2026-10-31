"""Perfect-information claim referee, isolated from live card selection.

Claims ask what the claiming partnership can force against best defence. DDS
maximises for the side on turn; invert that score when the claimant is the other
side. The current incomplete trick counts among the remaining tricks.
"""
from .core import Hand, SEATS, SUITS, RANKS


def _winner(trick, trump):
    lead = trick[0][1][0]
    return max(trick, key=lambda play: (
        2 if play[1][0] == trump else 1 if play[1][0] == lead else 0,
        14 - RANKS.index(play[1][1])))[0]


def claim_position(hands, plays, contract, claim):
    if not isinstance(hands, dict) or set(hands) != set(SEATS):
        raise ValueError('Expected four original hands')
    if any(not isinstance(cards, list) or any(not isinstance(card, str) for card in cards)
           for cards in hands.values()):
        raise ValueError('Expected card arrays')
    parsed = {seat: Hand(hands[seat]) for seat in SEATS}
    if len({card for hand in parsed.values() for card in hand.cards}) != 52:
        raise ValueError('Duplicate cards')
    if not isinstance(contract, dict) or set(contract) != {'declarer', 'strain'} or \
            contract['declarer'] not in list(SEATS) or contract['strain'] not in list(SUITS + 'N'):
        raise ValueError('Invalid contract')
    if not isinstance(claim, dict) or set(claim) != {'side', 'tricks'} or \
            claim['side'] not in ('NS', 'EW') or type(claim['tricks']) is not int or not 0 <= claim['tricks'] <= 13:
        raise ValueError('Invalid claim')
    if not isinstance(plays, list) or len(plays) > 52:
        raise ValueError('Invalid play history')
    remaining = {seat: list(parsed[seat].cards) for seat in SEATS}
    leader = turn = (SEATS.index(contract['declarer']) + 1) % 4
    trick = []
    for play in plays:
        if not isinstance(play, dict) or set(play) != {'seat', 'card'} or play['seat'] != SEATS[turn]:
            raise ValueError('Invalid play order')
        hand = remaining[SEATS[turn]]
        following = [card for card in hand if trick and card[0] == trick[0][1][0]]
        if play['card'] not in (following or hand):
            raise ValueError('Illegal card play')
        hand.remove(play['card'])
        trick.append((turn, play['card']))
        if len(trick) == 4:
            leader = turn = _winner(trick, contract['strain'])
            trick = []
        else:
            turn = (turn + 1) % 4
    remaining_tricks = 13 - len(plays) // 4
    if claim['tricks'] > remaining_tricks:
        raise ValueError('Claim exceeds remaining tricks')
    return remaining, leader, turn, trick, remaining_tricks


def adjudicate_claim(hands, plays, contract, claim, dds):
    remaining, leader, turn, trick, count = claim_position(hands, plays, contract, claim)
    if claim['tricks'] == 0:
        guaranteed = 0  # A concession needs no native search.
    else:
        pbn = 'N:' + ' '.join('.'.join(''.join(rank for rank in RANKS if suit + rank in remaining[seat])
                                       for suit in SUITS) for seat in SEATS)
        trick_suits = [SUITS.index(card[0]) for _, card in trick] + [0] * (3 - len(trick))
        trick_ranks = [14 - RANKS.index(card[1]) for _, card in trick] + [0] * (3 - len(trick))
        solved = dds.solve_board_pbn(pbn, trump=(SUITS + 'N').index(contract['strain']), first=leader,
                                     current_trick_suit=tuple(trick_suits), current_trick_rank=tuple(trick_ranks),
                                     target=-1, solutions=1, mode=1, context=dds.SolverContext())
        scores = solved.get('score')
        if type(solved.get('cards')) is not int or solved['cards'] < 1 or not isinstance(scores, (list, tuple)) or \
                not scores or type(scores[0]) is not int or not 0 <= scores[0] <= count:
            raise RuntimeError('Invalid native claim result')
        same_side = (turn % 2 == 0) == (claim['side'] == 'NS')
        guaranteed = scores[0] if same_side else count - scores[0]
    accept = guaranteed >= claim['tricks']
    return {'accept': accept, 'guaranteed': guaranteed, 'remainingTricks': count,
            'side': claim['side'], 'tricks': claim['tricks'], 'source': 'BEN DDS', 'perfectInformation': True,
            'reason': 'Concession of all remaining tricks' if claim['tricks'] == 0 else
            'The claimed tricks can be made against best defence.' if accept else
            'Best defence can prevent the claimed tricks. Play continues.'}
