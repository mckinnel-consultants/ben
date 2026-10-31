"""Public-play reconstruction; no actual concealed deal is accepted."""
from .core import SUITS, RANKS


def card_code(card):
    if len(card) != 2 or card[0] not in SUITS or card[1] not in RANKS:
        raise ValueError('Invalid card')
    return SUITS.index(card[0]) * 13 + RANKS.index(card[1])


def code_card(code):
    return SUITS[code // 13] + RANKS[code % 13]


def reconstruct(plays, contract):
    if not contract:
        raise ValueError('Card play requires a completed auction')
    leader = (contract['declarer'] + 1) % 4
    turn = leader
    trick, assigned = [], {seat: [] for seat in range(4)}
    voids, won = {seat: set() for seat in range(4)}, [0, 0]
    seen = set()
    for card in plays:
        card_code(card)
        if card in seen or len(seen) >= 52:
            raise ValueError('Duplicate or excess played card')
        if card[0] in voids[turn]:
            raise ValueError('A seat played a suit after showing out of it')
        seen.add(card)
        if trick and card[0] != trick[0][1][0]:
            voids[turn].add(trick[0][1][0])
        assigned[turn].append(card)
        if len(assigned[turn]) > 13:
            raise ValueError('Too many cards played by a seat')
        trick.append((turn, card))
        turn = (turn + 1) % 4
        if len(trick) == 4:
            trump = contract['strain']
            lead_suit = trick[0][1][0]
            winner = max(trick, key=lambda item: (2 if item[1][0] == trump else 1 if item[1][0] == lead_suit else 0, 14 - RANKS.index(item[1][1])))
            leader = turn = winner[0]
            won[winner[0] % 2] += 1
            trick = []
    return {'turn': turn, 'leader': leader, 'trick': trick, 'assigned': assigned, 'voids': voids, 'won': won}


def legal_cards(hand, state):
    remaining = [card for card in hand.cards if card not in state['assigned'][state['turn']]]
    follow = [card for card in remaining if state['trick'] and card[0] == state['trick'][0][1][0]]
    return follow or remaining
