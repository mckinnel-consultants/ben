"""Public-information bridge primitives shared by the Acol rules.

These classes deliberately have no neural-model or full-deal input. Bidding
receives one hand and an auction; inference receives the auction alone.
"""
from dataclasses import dataclass, field
from typing import Optional

SUITS = 'SHDC'
STRAINS = 'CDHSN'
RANKS = 'AKQJT98765432'
SEATS = 'NESW'
HCP = dict(A=4, K=3, Q=2, J=1)
PROFILE = {
    'id': 'ebu-acol-weak-twos-0314-v1',
    'nt_range': [12, 14], 'two_nt_range': [20, 22],
    'weak_twos': ['D', 'H', 'S'], 'weak_two_range': [5, 9],
    'benji': False, 'rkcb': '0314', 'baron': True,
    'minor_relay': True, 'opponents': 'acol',
}


def normalize_bid(bid):
    bid = str(bid).upper().replace('NT', 'N').replace('*', '')
    return {'P': 'PASS', '--': 'PASS', 'DB': 'X', 'DBL': 'X',
            'RD': 'XX', 'RDBL': 'XX'}.get(bid, bid)


def bid_rank(bid):
    bid = normalize_bid(bid)
    return (int(bid[0]) - 1) * 5 + STRAINS.index(bid[1]) if len(bid) == 2 and bid[0] in '1234567' and bid[1] in STRAINS else -1


def seat_index(seat):
    if isinstance(seat, str):
        if seat.upper() not in SEATS or len(seat) != 1:
            raise ValueError('Invalid compass seat')
        return SEATS.index(seat.upper())
    if not isinstance(seat, int) or not 0 <= seat < 4:
        raise ValueError('Invalid compass seat')
    return seat


class Hand:
    def __init__(self, cards):
        if isinstance(cards, Hand):
            cards = cards.cards
        if isinstance(cards, str):
            parts = cards.upper().split('.')
            if len(parts) != 4:
                raise ValueError('Expected an SHDC PBN hand')
            cards = [s + r for s, holding in zip(SUITS, parts) for r in holding.replace('-', '')]
        self.cards = tuple(cards)
        if len(self.cards) != 13 or len(set(self.cards)) != 13 or any(len(c) != 2 or c[0] not in SUITS or c[1] not in RANKS for c in self.cards):
            raise ValueError('Expected thirteen distinct valid cards')
        self.suits = {s: ''.join(r for r in RANKS if s + r in self.cards) for s in SUITS}
        self.lengths = {s: len(self.suits[s]) for s in SUITS}
        self.hcp = sum(HCP.get(c[1], 0) for c in self.cards)
        self.shape = tuple(sorted(self.lengths.values(), reverse=True))
        self.balanced = self.shape in [(4, 3, 3, 3), (4, 4, 3, 2), (5, 3, 3, 2)]
        self.semi_balanced = self.balanced or self.shape in [(5, 4, 2, 2), (6, 3, 2, 2)]
        self.controls = sum(2 if c[1] == 'A' else 1 if c[1] == 'K' else 0 for c in self.cards)
        self.losers = sum(max(0, min(3, len(ranks)) - sum(rank in ranks for rank in 'AKQ'[:min(3, len(ranks))])) for ranks in self.suits.values())
        self.quick_tricks = sum(2 if 'A' in ranks and 'K' in ranks else 1.5 if 'A' in ranks and 'Q' in ranks else 1 if 'A' in ranks or ('K' in ranks and 'Q' in ranks) else .5 if 'K' in ranks and len(ranks) >= 2 else 0 for ranks in self.suits.values())

    @property
    def pbn(self):
        return '.'.join(self.suits[s] for s in SUITS)

    def length(self, suit):
        return self.lengths.get(suit, 0)

    def has(self, suit, rank):
        return rank in self.suits.get(suit, '')

    def stopper(self, suit):
        ranks = self.suits[suit]
        return 'A' in ranks or ('K' in ranks and len(ranks) >= 2) or ('Q' in ranks and len(ranks) >= 3) or ('J' in ranks and len(ranks) >= 4)

    def support_points(self, trump):
        return self.hcp + sum({0: 5, 1: 3, 2: 1}.get(self.lengths[s], 0) for s in SUITS if s != trump)

    def keycards(self, trump):
        return sum(self.has(s, 'A') for s in SUITS) + int(self.has(trump, 'K'))

    def suit_quality(self, suit):
        return self.length(suit) + sum(self.has(suit, r) for r in 'AKQJT')


@dataclass(frozen=True)
class Call:
    seat: int
    bid: str
    index: int

    @property
    def is_contract(self):
        return bid_rank(self.bid) >= 0

    @property
    def level(self):
        return int(self.bid[0]) if self.is_contract else 0

    @property
    def strain(self):
        return self.bid[1] if self.is_contract else None


class Auction:
    def __init__(self, calls=(), dealer=0):
        self.dealer = seat_index(dealer)
        self.calls = []
        for index, item in enumerate(calls):
            seat = (self.dealer + index) % 4
            if isinstance(item, Call):
                if item.seat != seat:
                    raise ValueError('Auction seats must follow the dealer')
                bid = item.bid
            elif isinstance(item, dict):
                if 'seat' in item and seat_index(item['seat']) != seat:
                    raise ValueError('Auction seats must follow the dealer')
                bid = item['bid']
            else:
                bid = item
            bid = normalize_bid(bid)
            if bid not in self.legal_bids():
                raise ValueError(f'Illegal auction call at position {index}')
            self.calls.append(Call(seat, bid, index))

    @property
    def bids(self):
        return [c.bid for c in self.calls]

    @property
    def turn(self):
        return (self.dealer + len(self.calls)) % 4

    @property
    def opening(self):
        return next((c for c in self.calls if c.is_contract), None)

    @property
    def last_contract(self):
        return next((c for c in reversed(self.calls) if c.is_contract), None)

    @property
    def last_nonpass(self):
        return next((c for c in reversed(self.calls) if c.bid != 'PASS'), None)

    @property
    def ended(self):
        passes = 0
        for c in reversed(self.calls):
            if c.bid != 'PASS':
                break
            passes += 1
        return passes >= (3 if self.opening else 4)

    def contract_calls(self, seats=None):
        if isinstance(seats, int):
            seats = [seats]
        return [c for c in self.calls if c.is_contract and (seats is None or c.seat in seats)]

    def calls_by(self, seat, include_pass=False):
        return [c for c in self.calls if c.seat == seat_index(seat) and (include_pass or c.bid != 'PASS')]

    def prefix(self, index):
        return Auction(self.calls[:index], self.dealer)

    def passed_hand(self, seat):
        first = next((c for c in self.calls if c.seat == seat_index(seat)), None)
        return bool(first and first.bid == 'PASS' and (not self.opening or first.index < self.opening.index))

    def legal_bids(self):
        if self.ended:
            return []
        last = self.last_contract
        result = ['PASS']
        nonpass = self.last_nonpass
        if last and nonpass.bid not in ['X', 'XX'] and last.seat % 2 != self.turn % 2:
            result.append('X')
        if last and nonpass.bid == 'X' and last.seat % 2 == self.turn % 2:
            result.append('XX')
        floor = bid_rank(last.bid) if last else -1
        result.extend(str(level) + suit for level in range(1, 8) for suit in STRAINS if bid_rank(str(level) + suit) > floor)
        return result

    @property
    def contract(self):
        if not self.ended or not self.last_contract:
            return None
        last = self.last_contract
        declarer = next(c.seat for c in self.calls if c.is_contract and c.strain == last.strain and c.seat % 2 == last.seat % 2)
        final = self.last_nonpass.bid
        return {'level': last.level, 'strain': last.strain, 'declarer': declarer, 'doubled': 2 if final == 'XX' else 1 if final == 'X' else 0}


@dataclass(frozen=True)
class Decision:
    bid: str
    explanation: str
    rule: str
    alert: bool = False


@dataclass
class Meaning:
    description: str = ''
    rule: str = ''
    hcp_min: int = 0
    hcp_max: int = 37
    min_length: dict = field(default_factory=dict)
    max_length: dict = field(default_factory=dict)
    balanced: Optional[bool] = None
    forcing: str = 'none'
    artificial: bool = False
    suit: Optional[str] = None
    keycards: Optional[tuple] = None
    queen: Optional[bool] = None
    aces: Optional[tuple] = None
    kings: Optional[tuple] = None
    honours: dict = field(default_factory=dict)
    controls: dict = field(default_factory=dict)
    stoppers: tuple = ()
    min_total_length: list = field(default_factory=list)
    confidence: float = 1.0

    def penalty(self, hand):
        deviation = max(0, self.hcp_min - hand.hcp, hand.hcp - self.hcp_max) * .4
        deviation += sum(max(0, n - hand.length(s)) * 2 for s, n in self.min_length.items())
        deviation += sum(max(0, hand.length(s) - n) * 2 for s, n in self.max_length.items())
        if self.balanced is not None and self.balanced != hand.balanced:
            deviation += 2
        if self.keycards is not None and self.suit in tuple(SUITS) and hand.keycards(self.suit) not in self.keycards:
            deviation += 4
        if self.queen is not None and self.suit in tuple(SUITS) and hand.has(self.suit, 'Q') != self.queen:
            deviation += 3
        if self.aces is not None and sum(hand.has(s, 'A') for s in SUITS) not in self.aces:
            deviation += 4
        if self.kings is not None and sum(hand.has(s, 'K') for s in SUITS) not in self.kings:
            deviation += 3
        deviation += sum(3 for s, ranks in self.honours.items() for rank in ranks if not hand.has(s, rank))
        deviation += sum(3 for s, level in self.controls.items() if not (
            hand.has(s, 'A') or hand.length(s) == 0 or
            (level >= 2 and (hand.has(s, 'K') or hand.length(s) == 1))))
        deviation += sum(2 for s in self.stoppers if not hand.stopper(s))
        deviation += sum(max(0, n - sum(hand.length(s) for s in suits)) * 2 for suits, n in self.min_total_length)
        return deviation * self.confidence


class Context:
    def __init__(self, hand, auction, seat=None, vulnerability='None', profile=None):
        self.h = self.hand = hand if isinstance(hand, Hand) else Hand(hand)
        self.auction = auction if isinstance(auction, Auction) else Auction(auction)
        self.seat = self.auction.turn if seat is None else seat_index(seat)
        if self.seat != self.auction.turn or self.auction.ended:
            raise ValueError('Bidding requested out of turn or after the auction')
        self.partner = (self.seat + 2) % 4
        self.lho, self.rho = (self.seat + 1) % 4, (self.seat + 3) % 4
        if vulnerability not in ['None', 'NS', 'EW', 'Both']:
            raise ValueError('Invalid vulnerability')
        self.vulnerability = vulnerability
        our_side = 'NS' if self.seat % 2 == 0 else 'EW'
        self.vulnerable = self.me_vulnerable = vulnerability in ['Both', our_side]
        self.they_vulnerable = self.opp_vulnerable = vulnerability in ['Both', 'EW' if our_side == 'NS' else 'NS']
        self.legal = frozenset(self.auction.legal_bids())
        self.profile = {**PROFILE, **(profile or {})}

    def choose(self, bid, explanation, rule, alert=False):
        if bid is None:
            return None
        bid = normalize_bid(bid)
        return Decision(bid, explanation, rule, alert) if bid in self.legal else None

    def cheapest(self, suit, min_level=1):
        return next((str(level) + suit for level in range(min_level, 8) if str(level) + suit in self.legal), None)
