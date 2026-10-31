"""Sample concealed cards from public Acol meanings and visible cards only.

Auction promises are soft evidence: people can depart from their system. Card
ownership and demonstrated voids are hard constraints and are never relaxed.
No trained 2/1 bidding-information model participates in this path.
"""
import hashlib
import heapq
import random
from .core import Hand, SUITS, RANKS
from .system import interpret_auction
from .play import reconstruct, legal_cards, card_code

DECK = tuple(s + r for s in SUITS for r in RANKS)


def validate_visible(known, state):
    seen = set()
    for seat, hand in known.items():
        if seen.intersection(hand.cards):
            raise ValueError('Visible hands overlap')
        seen.update(hand.cards)
        if not set(state['assigned'][seat]).issubset(hand.cards):
            raise ValueError('Played cards contradict a visible hand')
        remaining = set(hand.cards) - set(state['assigned'][seat])
        if any(card[0] in state['voids'][seat] for card in remaining):
            raise ValueError('Visible hand contradicts public voids')
    for seat, cards in state['assigned'].items():
        if seat not in known and seen.intersection(cards):
            raise ValueError('Played card belongs to another visible hand')


def sample_deals(known, auction, plays=(), count=24, candidates=512, profile=None):
    if not 1 <= count <= 64 or not count <= candidates <= 8192:
        raise ValueError('Invalid sample budget')
    state = reconstruct(plays, auction.contract)
    validate_visible(known, state)
    unknown = [seat for seat in range(4) if seat not in known]
    used = set(c for h in known.values() for c in h.cards)
    used.update(c for cards in state['assigned'].values() for c in cards)
    pool = [c for c in DECK if c not in used]
    capacities = {seat: 13 - len(state['assigned'][seat]) for seat in unknown}
    if sum(capacities.values()) != len(pool):
        raise ValueError('Inconsistent public card count')
    allowed = {c: [s for s in unknown if c[0] not in state['voids'][s]] for c in pool}
    if any(not seats for seats in allowed.values()):
        raise ValueError('Public voids leave a card without an owner')
    meanings = {s: [] for s in unknown}
    for call, meaning in interpret_auction(auction, profile):
        if call.seat in meanings and meaning.confidence:
            meanings[call.seat].append(meaning)
    seed = repr((sorted((s, h.pbn) for s, h in known.items()), auction.dealer, auction.bids, list(plays), profile)).encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(seed).digest()[:8], 'big'))
    retained = []
    seen = set()
    generated = 0
    # Most-constrained cards first. Rejection retries retain hard constraints;
    # they do not distribute an impossible card just to finish a sample.
    for attempt in range(candidates * 8):
        if generated >= candidates:
            break
        left = capacities.copy()
        allocated = {s: list(state['assigned'][s]) for s in unknown}
        cards = pool.copy()
        rng.shuffle(cards)
        cards.sort(key=lambda c: len(allowed[c]))
        for card in cards:
            options = [s for s in allowed[card] if left[s] > 0]
            if not options:
                break
            seat = rng.choices(options, weights=[left[s] for s in options])[0]
            allocated[seat].append(card)
            left[seat] -= 1
        else:
            generated += 1
            deal = {**known, **{s: Hand(cards) for s, cards in allocated.items()}}
            key = tuple(deal[s].pbn for s in range(4))
            if key in seen:
                if not pool or sum(n > 0 for n in capacities.values()) <= 1:
                    break
                continue
            seen.add(key)
            penalty = sum(m.penalty(deal[s]) for s in unknown for m in meanings[s])
            item = (-penalty, attempt, deal)
            if len(retained) < count:
                heapq.heappush(retained, item)
            elif penalty < -retained[0][0]:
                heapq.heapreplace(retained, item)
    if not retained:
        raise ValueError('No deal satisfies visible cards and public voids')
    retained.sort(key=lambda x: (-x[0], x[1]))
    return [item[2] for item in retained], state, {
        'method': 'acol-public-auction-constraints',
        'samples': len(retained), 'candidates': generated,
        'best_auction_penalty': round(-retained[0][0], 3),
        'worst_auction_penalty': round(-retained[-1][0], 3),
        'auction_constraints': 'soft', 'card_constraints': 'hard',
    }


def choose_card(known, auction, plays, solver, count=24, candidates=512, profile=None):
    samples, state, diagnostics = sample_deals(known, auction, plays, count, candidates, profile)
    if state['turn'] not in known:
        raise ValueError('Acting hand must be visible to the engine')
    legal = legal_cards(known[state['turn']], state)
    if not legal:
        raise ValueError('No cards remain to play')
    if len(legal) == 1:
        return {'card': legal[0], 'source': 'forced-legal-card', 'inference': diagnostics}
    pbns = []
    for deal in samples:
        holdings = []
        for seat in range(4):
            remaining = set(deal[seat].cards) - set(state['assigned'][seat])
            holdings.append('.'.join(''.join(r for r in RANKS if s + r in remaining) for s in SUITS))
        pbns.append('N:' + ' '.join(holdings))
    contract = auction.contract
    result = solver.solve('NSHDC'.index(contract['strain']), state['leader'],
                          [card_code(c) for _, c in state['trick']], pbns, 3, purpose='acol')
    if not result or any(card_code(c) not in result or len(result[card_code(c)]) != len(samples) for c in legal):
        raise RuntimeError('DDS did not evaluate every legal card on every sample')
    expectations = {c: sum(result[card_code(c)]) / len(samples) for c in legal}
    # Equal DDS values: conserve the highest card. This is deterministic, not a
    # random substitute when the solver fails (failures preserve the turn).
    card = max(legal, key=lambda c: (expectations[c], RANKS.index(c[1]), -SUITS.index(c[0])))
    return {'card': card, 'source': 'acol-sampled-dds', 'inference': diagnostics,
            'expected_tricks': round(expectations[card], 3)}
