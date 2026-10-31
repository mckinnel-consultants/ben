"""Natural bidding in EBU Modern Acol, sections A2.1–2.7 and A2.10.

The partnership variation is weak 2D/2H/2S. Strength ranges are deliberately
broad where losing-trick evaluation or distribution can replace high cards.
Only the bidder's hand and the public auction are examined.
"""
from .core import Auction, Call, Context, Decision, Meaning, SUITS, STRAINS, bid_rank

_MAJOR = 'HS'
_MINOR = 'CD'
_GAME = {'C': 5, 'D': 5, 'H': 4, 'S': 4, 'N': 3}


def _game(bid):
    return bid_rank(bid) >= 0 and int(bid[0]) >= _GAME[bid[1]]


def _partnership(auction, seat):
    return auction.contract_calls([seat, (seat + 2) % 4])


def _uncontested(auction, seat):
    return not any(c.seat % 2 != seat % 2 and c.bid != 'PASS' for c in auction.calls)


def _cheapest_after(auction, suit, minimum=1):
    floor = bid_rank(auction.last_contract.bid) if auction.last_contract else -1
    return next((f'{level}{suit}' for level in range(minimum, 8)
                 if bid_rank(f'{level}{suit}') > floor), None)


def _jump(auction, bid):
    cheapest = _cheapest_after(auction, bid[1])
    return cheapest is not None and int(bid[0]) > int(cheapest[0])


def _good_suit(hand, suit):
    return sum(hand.has(suit, r) for r in 'AKQ') >= 2 or sum(hand.has(suit, r) for r in 'AKQJT') >= 3


def _strength(hand, suit):
    return sum({'A': 4, 'K': 3, 'Q': 2, 'J': 1}.get(r, 0) for r in hand.suits[suit])


def _opening_suit(hand):
    if sorted(hand.lengths.values()) == [1, 4, 4, 4]:
        singleton = next(s for s in SUITS if hand.length(s) == 1)
        return {'S': 'D', 'H': 'D', 'D': 'C', 'C': 'H'}[singleton]
    longest = max(hand.lengths.values())
    tied = [s for s in SUITS if hand.length(s) == longest]
    if longest == 4 and 'H' in tied and 'S' in tied:
        return 'H'
    return tied[0]


def _rule20(hand):
    long = sorted(SUITS, key=lambda s: (hand.length(s), _strength(hand, s)), reverse=True)[:2]
    # Unsupported short-suit queens/jacks do not contribute their full value
    # to a borderline opening (the second example in EBU A2.1).
    wasted = sum((2 if hand.has(s, 'Q') else 0) + (1 if hand.has(s, 'J') else 0)
                 for s in SUITS if hand.length(s) <= 2 and not hand.has(s, 'A') and not hand.has(s, 'K'))
    return (9 <= hand.hcp <= 11 and hand.hcp - wasted + sum(hand.length(s) for s in long) >= 20
            and sum(_strength(hand, s) for s in long) > hand.hcp / 2)


def _opening(ctx):
    h = ctx.h
    suit = _opening_suit(h)
    # A solid minor is a separate preemptive opening, not an ordinary weak three.
    for minor in _MINOR:
        if h.length(minor) >= 7 and all(h.has(minor, r) for r in 'AKQJ') and h.hcp - _strength(h, minor) <= 2:
            return ctx.choose('3N', 'Gambling 3NT: a long solid minor and little outside strength.', 'A2.10.5', True)
    if h.hcp >= 12 or _rule20(h):
        return ctx.choose('1' + suit, 'Natural opening; four-card majors and distributional Rule of 20 evaluation.', 'A2.1')
    low, high = ctx.profile.get('weak_two_range', [5, 9])
    if suit in ctx.profile.get('weak_twos', ['D', 'H', 'S']) and h.length(suit) == 6 and low <= h.hcp <= high and _good_suit(h, suit):
        if not any(h.length(s) >= 4 for s in _MAJOR if s != suit):
            return ctx.choose('2' + suit, 'Weak two: a decent six-card suit and limited strength.', 'A2.10.4')
    if h.length(suit) >= 7 and h.hcp < 10 and sum(h.has(s, 'A') for s in SUITS) < 2:
        if not any(h.length(s) >= 4 for s in _MAJOR if s != suit):
            # Conservative Rule of 500: estimate long-suit cashing tricks, then
            # add outside aces. A missing ace normally costs one trick.
            tricks = h.length(suit) - sum(not h.has(suit, r) for r in 'AKQ')
            tricks += sum(h.has(s, 'A') for s in SUITS if s != suit)
            level = min(4 if h.length(suit) >= 8 else 3, int(tricks) + (2 if ctx.vulnerable else 3) - 6)
            if level >= 3 and _good_suit(h, suit):
                return ctx.choose(str(level) + suit, 'Preempt with a long suit, allowing for vulnerability and playing tricks.', 'A2.10.1-2')
    return ctx.choose('PASS', 'Insufficient values or suit quality to open.', 'A2.1')


def _new_response_suit(ctx, opening):
    """Choose length first, but prefer an affordable major below game values."""
    h = ctx.h
    available = [s for s in SUITS if s != opening.strain and h.length(s) >= 4]
    available = [s for s in available if not (opening.bid == '1S' and s == 'H' and h.length(s) < 5)]
    if h.hcp < 13:
        majors = [s for s in _MAJOR if s in available and ctx.cheapest(s).startswith('1')]
        if majors:
            return max(majors, key=lambda s: (h.length(s), -STRAINS.index(s)))
    available = [s for s in available if h.hcp >= 9 or ctx.cheapest(s).startswith('1')]
    if not available:
        return None
    longest = max(h.length(s) for s in available)
    tied = [s for s in available if h.length(s) == longest]
    return max(tied, key=STRAINS.index) if longest >= 5 else min(tied, key=lambda s: bid_rank(ctx.cheapest(s)))


def _strong_jump_suit(ctx, opening):
    h = ctx.h
    candidates = [s for s in SUITS if s != opening.strain and h.length(s) >= 5 and _good_suit(h, s)]
    candidates = [s for s in candidates if h.length(s) >= 6 or h.length(opening.strain) >= 3 or h.balanced]
    return max(candidates, key=lambda s: (h.length(s), STRAINS.index(s)), default=None)


def _respond_one(ctx, opening):
    h, suit = ctx.h, opening.strain
    support = h.length(suit)
    if h.hcp < 6:
        return ctx.choose('PASS', 'Too weak for an ordinary response.', 'A2.3')
    jump_suit = _strong_jump_suit(ctx, opening) if h.hcp >= 16 else None
    if jump_suit:
        bid = str(int(ctx.cheapest(jump_suit)[0]) + 1) + jump_suit
        return ctx.choose(bid, 'Strong jump shift: a good suit, with a rebid in that suit, support or no trumps.', 'A2.3.2')
    if suit in _MAJOR and support >= 4:
        if 11 <= h.hcp <= 15:
            short = [s for s in SUITS if s != suit and h.length(s) <= 1]
            if short:
                bids = [(('3S' if suit == 'H' and s == 'S' else '4' + s), s) for s in short]
                bid, short_suit = min(bids, key=lambda item: bid_rank(item[0]))
                return ctx.choose(bid, f'Splinter: game values, four-card support and shortage in {short_suit}.', 'A2.2.2', True)
        if 12 <= h.hcp <= 15 and h.balanced:
            return ctx.choose('3N', 'Pudding raise: balanced game values with four-card major support.', 'A2.2.2', True)
        # The card gives no special artificial response for a very strong
        # 4-3-3-3 raise without a jump-shift suit. Take the assured game.
        level = 4 if h.losers <= 7 or h.hcp >= 16 else 3 if h.losers == 8 else 2
        return ctx.choose(str(level) + suit, 'Raise the major using the losing-trick count and four-card support.', 'A2.2.1')
    response_suit = _new_response_suit(ctx, opening)
    if response_suit:
        return ctx.choose(ctx.cheapest(response_suit), 'Natural new-suit response; show length while preserving an affordable major.', 'A2.3.1')
    if suit in _MAJOR and support == 3 and not h.balanced and h.hcp <= 9:
        return ctx.choose('2' + suit, 'A minimum raise with three trumps and useful distribution.', 'A2.2.1')
    if suit == 'C' and 8 <= h.hcp <= 10 and h.balanced and h.length('H') < 4 and h.length('S') < 4:
        return ctx.choose('1N', 'Special balanced 8–10 response to one club, without a four-card major.', 'A2.4')
    if suit in _MINOR and support >= 4:
        if h.hcp <= 12:
            return ctx.choose(('2' if h.hcp <= 9 else '3') + suit, 'Natural minor-suit raise after checking for a major.', 'A2.2.1')
        if all(h.stopper(s) for s in SUITS if s != suit):
            return ctx.choose('3N', 'Game values with minor support and stoppers in the other suits.', 'A2.2.1')
    if 10 <= h.hcp <= 12 and h.balanced and all(h.stopper(s) for s in SUITS if s != suit):
        return ctx.choose('2N', 'Natural invitation: balanced with stoppers in the unbid suits.', 'A2.4')
    if suit == 'C' and h.hcp <= 7:
        if support >= 4:
            return ctx.choose('2C', 'Weak club support; reserve the 1NT response for 8–10 points.', 'A2.4')
        if h.length('D') >= 4:
            return ctx.choose('1D', 'Natural diamond response, too weak for the special club-opening 1NT response.', 'A2.4')
    if h.hcp <= (10 if suit == 'C' else 9):
        return ctx.choose('1N', 'Limited no-trump response; no suitable natural suit response.', 'A2.4')
    # A hand too strong for the dustbin response normally has a four-card
    # minor. The choice above only excluded four hearts over one spade.
    candidates = [s for s in _MINOR if h.length(s) >= 3 and s != suit]
    if candidates:
        pick = max(candidates, key=lambda s: h.length(s))
        return ctx.choose(ctx.cheapest(pick), 'Temporizing minor response with game interest; no available four-card response.', 'A2.4.extension')
    return ctx.choose('3N', 'Game-going no-trump response with no suitable new suit.', 'A2.4')


def _reverse(opening, response, rebid, auction):
    return (rebid.strain not in (opening.strain, response.strain, 'N')
            and not _jump(auction.prefix(rebid.index), rebid.bid)
            and bid_rank(rebid.bid) > bid_rank('2' + opening.strain))


def _support_responder(ctx, response):
    h, suit = ctx.h, response.strain
    if suit not in _MAJOR or h.length(suit) < 4:
        return None
    level = 4 if h.support_points(suit) >= 19 or h.losers <= 5 else 3 if h.support_points(suit) >= 16 or h.losers <= 6 else 2
    return ctx.choose(str(level) + suit, 'Support responder’s major, showing strength through the level of the raise.', 'A2.5.1-2')


def _after_raise(ctx, opening, response):
    h, suit = ctx.h, opening.strain
    if _game(response.bid):
        return ctx.choose('PASS', 'Partner has placed the contract in game.', 'A2.2')
    if suit in _MAJOR:
        if response.level == 3:
            return ctx.choose('4' + suit if h.losers <= 6 or h.support_points(suit) >= 15 else 'PASS', 'Accept the limit raise with a better-than-minimum opening.', 'A2.2.1')
        if h.losers <= 5 or h.support_points(suit) >= 19:
            return ctx.choose('4' + suit, 'Enough playing strength for game opposite a simple raise.', 'A2.5.2')
        if h.losers <= 6 or h.support_points(suit) >= 16:
            trial = [s for s in SUITS if s != suit and h.length(s) >= 3
                     and sum(h.has(s, r) for r in 'AKQ') <= 1
                     and bid_rank(ctx.cheapest(s)) < bid_rank('3' + suit)]
            if trial:
                pick = min(trial, key=lambda s: bid_rank(ctx.cheapest(s)))
                return ctx.choose(ctx.cheapest(pick), 'Long-suit trial bid: help in this suit would make game attractive.', 'A2.7')
            return ctx.choose('3' + suit, 'Invite game with extra strength and no useful long-suit trial bid.', 'A2.7')
        return ctx.choose('PASS', 'Minimum opening opposite a simple raise.', 'A2.2.1')
    minimum = 10 if response.level == 3 else 6
    stopped = all(h.stopper(s) for s in SUITS if s != suit)
    if h.hcp + minimum >= 25 and stopped:
        return ctx.choose('3N', 'Enough combined strength for no trump game with the side suits stopped.', 'A2.7')
    if h.hcp + minimum >= 23:
        trials = [s for s in SUITS if s != suit and h.stopper(s) and bid_rank(ctx.cheapest(s)) < bid_rank('3N')]
        if trials:
            pick = min(trials, key=lambda s: bid_rank(ctx.cheapest(s)))
            return ctx.choose(ctx.cheapest(pick), 'Minor-suit trial bid: show a stopper while investigating 3NT.', 'A2.7', True)
    return ctx.choose('PASS', 'No extra values to pursue game after the minor-suit raise.', 'A2.2.1')


def _opener_rebid(ctx, pair):
    opening, response = pair
    h, suit = ctx.h, opening.strain
    if opening.strain in _MAJOR and response.bid == '3N':
        return ctx.choose('4' + suit, 'Place the pudding raise in the agreed major.', 'A2.2.2')
    if response.strain == suit:
        return _after_raise(ctx, opening, response)
    if _splinter(opening, response):
        return ctx.choose('4' + suit, 'Accept the splinter raise in the agreed major.', 'A2.2.2')
    support = _support_responder(ctx, response)
    if support:
        return support
    if response.strain == 'N':
        low = 10 if response.level == 2 else 8 if suit == 'C' else 6
        if response.level == 2 and h.hcp >= 14 and all(h.stopper(s) for s in SUITS if s != suit):
            return ctx.choose('3N', 'Accept the no-trump invitation with useful extra values.', 'A2.4')
        if h.balanced:
            bid = '3N' if h.hcp + low >= 25 else '2N' if response.level == 1 and h.hcp + low >= 23 else 'PASS'
            return ctx.choose(bid, 'Evaluate the limited no-trump response using combined strength.', 'A2.4')
    candidates = [s for s in SUITS if s not in (suit, response.strain) and h.length(s) >= 4]
    candidates.sort(key=lambda s: (-h.length(s), bid_rank(ctx.cheapest(s))))
    # Strong jump shifts take precedence over economical shape description.
    jump_min = 16 if response.level == 2 and response.strain != 'N' else 19
    if h.hcp >= jump_min and candidates:
        s = candidates[0]
        jump = str(int(ctx.cheapest(s)[0]) + 1) + s
        if bid_rank(jump) < bid_rank('4N'):
            return ctx.choose(jump, 'Strong jump shift by opener, forcing to game.', 'A2.5.2')
    for s in candidates:
        bid = ctx.cheapest(s)
        reverse = bid_rank(bid) > bid_rank('2' + suit)
        if not reverse or h.hcp >= 16:
            return ctx.choose(bid, 'Reverse showing extra strength.' if reverse else 'Economical second suit with at least four cards.', 'A2.5.3' if reverse else 'A2.5.1')
    if h.length(suit) >= 6:
        if h.hcp >= 19:
            if suit in _MINOR and all(h.stopper(s) for s in SUITS if s != suit):
                return ctx.choose('3N', 'Strong long minor and outside stoppers for no trump game.', 'A2.5.2')
            return ctx.choose(str(_GAME[suit]) + suit, 'Strong long suit with playing strength for game.', 'A2.5.2')
        if h.hcp >= 16 and _good_suit(h, suit):
            bid = str(int(ctx.cheapest(suit)[0]) + 1) + suit
            return ctx.choose(bid, 'Strong six-card suit; the jump rebid shows intermediate strength.', 'A2.5.2')
    if h.balanced and response.strain != 'N':
        if h.hcp <= 14 and suit in _MAJOR and h.length(suit) >= 5:
            return ctx.choose(ctx.cheapest(suit), 'Minimum five-card major opening; retain the 15–16 range for the cheapest no-trump rebid.', 'A2.5.1')
        # Normal balanced rebids are claimed by the NT module first. This
        # branch also makes this module independently usable in unit tests.
        bid = '3N' if h.hcp >= 19 else '2N' if h.hcp >= 17 else '1N'
        return ctx.choose(bid if bid in ctx.legal else ctx.cheapest('N'), 'Balanced rebid after a natural response.', 'A1.2')
    if response.strain == 'N' and h.length(suit) < 6:
        return ctx.choose('PASS', 'A minimum hand without a useful long-suit correction.', 'A2.4')
    return ctx.choose(ctx.cheapest(suit), 'Minimum rebid of the opening suit; no suitable raise or second suit.', 'A2.5.1')


def _splinter(opening, response):
    return opening.bid in ('1H', '1S') and response.bid in ({'3S', '4C', '4D'} if opening.strain == 'H' else {'4C', '4D', '4H'})


def _fourth_suit(pair, call):
    if len(pair) < 3 or call.strain == 'N':
        return False
    first = pair[:3]
    suits = {c.strain for c in first}
    if 'N' in suits or len(suits) != 3 or call.strain in suits:
        return False
    # One spade is natural in this unique economical sequence.
    return not ([c.bid for c in first] == ['1C', '1D', '1H'] and call.bid == '1S')


def _responder_rebid(ctx, pair):
    opening, response, rebid = pair
    h, first = ctx.h, opening.strain
    if _game(rebid.bid):
        return ctx.choose('PASS', 'Opener has reached game.', 'A2.6')
    # Reply to a long-suit or stopper-showing trial after a direct raise.
    if response.strain == first and rebid.strain not in (first, 'N'):
        if first in _MAJOR:
            useful = h.length(rebid.strain) <= 1 or h.has(rebid.strain, 'A') or h.has(rebid.strain, 'K') or (h.has(rebid.strain, 'Q') and h.has(rebid.strain, 'J'))
            accept = h.losers <= 8 or (useful and h.hcp >= 8)
            return ctx.choose(('4' if accept else '3') + first, 'Accept the trial with useful help.' if accept else 'Decline the trial and return to the agreed major.', 'A2.7')
        other = [s for s in SUITS if s not in (first, rebid.strain)]
        if h.hcp >= (8 if response.level == 2 else 10) and all(h.stopper(s) for s in other):
            return ctx.choose('3N', 'The remaining suits are stopped for no trump game.', 'A2.7')
        for s in sorted(other, key=lambda s: bid_rank(ctx.cheapest(s))):
            if h.stopper(s) and bid_rank(ctx.cheapest(s)) < bid_rank('3N'):
                return ctx.choose(ctx.cheapest(s), 'Show another stopper in the search for 3NT.', 'A2.7', True)
        return ctx.choose(ctx.cheapest(first), 'Return to the agreed minor without the missing stoppers.', 'A2.7')
    if response.strain == first and rebid.strain == first:
        if rebid.level == 3 and first in _MAJOR:
            return ctx.choose('4' + first if h.losers <= 8 or h.hcp >= 9 else 'PASS', 'Evaluate the major-suit invitation.', 'A2.7')
        return ctx.choose('PASS', 'The supported suit is a suitable resting place.', 'A2.6')
    if rebid.strain == response.strain and response.strain != 'N':
        suit = response.strain
        if suit in _MAJOR:
            opening_min = 16 if _jump(ctx.auction.prefix(rebid.index), rebid.bid) else 12
            if h.support_points(suit) + opening_min >= 25 or h.losers <= (8 if opening_min == 16 else 7):
                return ctx.choose('4' + suit, 'Bid game in the major fit shown by opener.', 'A2.6')
            if h.hcp >= 10 and rebid.level == 2:
                return ctx.choose('3' + suit, 'Invite game in the agreed major.', 'A2.6')
            return ctx.choose('PASS', 'Minimum response; stop in the agreed major.', 'A2.6')
    if rebid.strain == 'N':
        return _continuation(ctx, pair)
    if [c.bid for c in pair] == ['1C', '1D', '1H'] and h.length('S') >= 4:
        return ctx.choose('1S', 'Natural four-card spades in the economical fourth-suit sequence.', 'A2.6.1')
    reverse = _reverse(opening, response, rebid, ctx.auction)
    strong_jump = rebid.strain != first and _jump(ctx.auction.prefix(rebid.index), rebid.bid)
    game_force = strong_jump or (_jump(ctx.auction.prefix(response.index), response.bid) and response.strain != first)
    game_force = game_force or (rebid.level >= 3 and reverse)
    if rebid.strain == first:
        opener_min = 16 if _jump(ctx.auction.prefix(rebid.index), rebid.bid) else 12
        game_force = game_force or (opener_min == 16 and response.level == 2 and response.strain != 'N')
        fit = h.length(first) >= 3
        if fit and first in _MAJOR and (game_force or h.support_points(first) + opener_min >= 25):
            return ctx.choose('4' + first, 'Game in opener’s long major.', 'A2.6')
        new_suits = [s for s in SUITS if s not in (first, response.strain) and h.length(s) >= 4]
        if h.hcp >= 13 and new_suits:
            new = min(new_suits, key=lambda s: bid_rank(ctx.cheapest(s)))
            return ctx.choose(ctx.cheapest(new), 'Responder shows a second suit with game-going strength.', 'A2.3.1')
        if h.hcp + opener_min >= 25 and all(h.stopper(s) for s in SUITS if s != first):
            return ctx.choose('3N', 'Combined values and side-suit stoppers suggest 3NT.', 'A2.6')
        if not game_force and h.hcp <= 9:
            if h.length(response.strain) >= 6:
                return ctx.choose(ctx.cheapest(response.strain), 'Rebid a six-card response suit with a minimum hand.', 'A2.6')
            return ctx.choose('PASS', 'A minimum response opposite a limited suit rebid.', 'A2.6')
        if not game_force and 10 <= h.hcp <= 12:
            if fit and rebid.level < 3:
                return ctx.choose('3' + first, 'Invite with support for opener’s long suit.', 'A2.6')
            return ctx.choose('2N' if '2N' in ctx.legal else 'PASS', 'Invite game with extra response values.', 'A2.6')
    # Natural descriptive bids precede fourth-suit forcing.
    if rebid.strain != first:
        if h.hcp <= 9 and not game_force:
            if h.length(response.strain) >= 6:
                return ctx.choose(ctx.cheapest(response.strain), 'Minimum rebid of a six-card response suit.', 'A2.6')
            if h.length(first) >= 3 or (h.length(first) >= 2 and h.length(rebid.strain) < 4):
                return ctx.choose(ctx.cheapest(first), 'Minimum preference; a doubleton can be a false preference.', 'A2.6')
            if not reverse:
                return ctx.choose('PASS', 'Minimum hand with a playable fit for opener’s second suit.', 'A2.6')
            return ctx.choose(ctx.cheapest('N'), 'Minimum no-trump rebid after opener’s reverse.', 'A2.5.3')
        if 10 <= h.hcp <= 12 and not game_force and not reverse:
            if h.length(first) >= 3:
                return ctx.choose(str(int(ctx.cheapest(first)[0]) + 1) + first, 'Jump preference invites game with three-card support.', 'A2.6')
            if h.length(rebid.strain) >= 4:
                return ctx.choose(str(rebid.level + 1) + rebid.strain, 'Invite with four-card support for opener’s second suit.', 'A2.6')
            if h.length(response.strain) >= 6:
                return ctx.choose(str(int(ctx.cheapest(response.strain)[0]) + 1) + response.strain, 'Invitational jump rebid of a six-card suit.', 'A2.6')
            fourth = next((s for s in SUITS if s not in {first, response.strain, rebid.strain}), None)
            if fourth and h.hcp >= 11 and not h.stopper(fourth) and ctx.cheapest(fourth)[0] == '2':
                return ctx.choose(ctx.cheapest(fourth), 'Fourth-suit forcing asks for more information.', 'A2.6.1', True)
            return ctx.choose('2N' if '2N' in ctx.legal else ctx.cheapest(first), 'Natural no-trump invitation.', 'A2.6')
        if h.length(first) >= 3 and first in _MAJOR:
            return ctx.choose('4' + first, 'Game in opener’s major with three-card support.', 'A2.6')
        if h.length(rebid.strain) >= 4 and rebid.strain in _MAJOR:
            return ctx.choose('4' + rebid.strain, 'Game in opener’s second major.', 'A2.6')
        fourth = next((s for s in SUITS if s not in {first, response.strain, rebid.strain}), None)
        if fourth and not h.stopper(fourth):
            bid = ctx.cheapest(fourth)
            if [c.bid for c in pair] == ['1C', '1D', '1H']:
                if h.length('S') >= 4:
                    return ctx.choose('1S', 'Natural four-card spade response in the special fourth-suit sequence.', 'A2.6.1')
                bid = '2S'
            return ctx.choose(bid, 'Fourth-suit forcing asks opener to clarify shape or show a stopper.', 'A2.6.1', True)
        if h.hcp >= 13 or game_force or reverse:
            return ctx.choose('3N', 'Game-going values with the unbid suit stopped.', 'A2.6')
    return _continuation(ctx, pair)


def _force_state(auction, seat, profile):
    game_forcing = False
    last_meaning = None
    for c in _partnership(auction, seat):
        m = interpret(auction.prefix(c.index), c, profile)
        if m and m.forcing == 'game':
            game_forcing = True
        if _game(c.bid):
            game_forcing = False
        if c.seat != seat:
            last_meaning = m
        else:
            last_meaning = None
    return game_forcing, bool(last_meaning and last_meaning.forcing in ('one-round', 'game'))


def _known_fit(auction, seat, profile):
    lengths = {seat: {}, (seat + 2) % 4: {}}
    for c in _partnership(auction, seat):
        m = interpret(auction.prefix(c.index), c, profile)
        if not m:
            continue
        for s, n in m.min_length.items():
            lengths[c.seat][s] = max(lengths[c.seat].get(s, 0), n)
    fits = [s for s in SUITS if sum(lengths[p].get(s, 0) for p in lengths) >= 8]
    return max(fits, key=lambda s: (s in _MAJOR, sum(lengths[p].get(s, 0) for p in lengths), STRAINS.index(s)), default=None)


def _fourth_suit_reply(ctx, pair):
    opening, response, rebid, fourth = pair[:4]
    h = ctx.h
    if h.length(response.strain) >= 3:
        return ctx.choose(ctx.cheapest(response.strain), 'Show support for responder after fourth-suit forcing.', 'A2.6.1')
    if h.stopper(fourth.strain):
        return ctx.choose(ctx.cheapest('N', 3 if h.hcp >= 16 else 1), 'Show a stopper in the artificial fourth suit.', 'A2.6.1')
    if h.length(opening.strain) >= 6:
        return ctx.choose(ctx.cheapest(opening.strain), 'Show extra length without a fourth-suit stopper.', 'A2.6.1')
    if h.length(rebid.strain) >= 5:
        return ctx.choose(ctx.cheapest(rebid.strain), 'Show extra length in opener’s second suit.', 'A2.6.1')
    if h.length(response.strain) >= 2:
        return ctx.choose(ctx.cheapest(response.strain), 'Minimum preference may show only two-card support after fourth-suit forcing.', 'A2.6.1')
    return ctx.choose(ctx.cheapest(opening.strain), 'Complete the compulsory response by rebidding the first suit.', 'A2.6.1')


def _continuation(ctx, pair):
    h = ctx.h
    if len(pair) == 4 and _fourth_suit(pair[:3], pair[3]):
        return _fourth_suit_reply(ctx, pair)
    gf, compulsory = _force_state(ctx.auction, ctx.seat, ctx.profile)
    if len(pair) >= 5 and _fourth_suit(pair[:3], pair[3]) and ctx.seat == pair[1].seat and h.hcp >= 13:
        gf = True
    partner_calls = [c for c in pair if c.seat == ctx.partner]
    partner = partner_calls[-1] if partner_calls else None
    if not partner:
        return ctx.choose('PASS', 'No further constructive action.', 'A2.6')
    if _game(partner.bid) and not compulsory:
        return ctx.choose('PASS', 'The partnership has reached game.', 'A2.6')
    m = interpret(ctx.auction.prefix(partner.index), partner, ctx.profile)
    lower = m.hcp_min if m else 6
    # A later call does not erase an earlier strength promise.
    for call in partner_calls:
        meaning = interpret(ctx.auction.prefix(call.index), call, ctx.profile)
        if meaning:
            lower = max(lower, meaning.hcp_min)
    fit = _known_fit(ctx.auction, ctx.seat, ctx.profile)
    invite = bool(m and m.forcing == 'invite')
    if fit:
        game = str(_GAME[fit]) + fit
        if game in ctx.legal and (gf or (invite and (h.support_points(fit) >= 15 if ctx.seat == pair[0].seat else h.hcp >= 9)) or h.hcp + lower >= (25 if fit in _MAJOR else 29)):
            return ctx.choose(game, 'Complete the auction in the agreed fit.', 'A2.6')
        if not gf and not compulsory:
            return ctx.choose('PASS', 'No undisclosed values to continue beyond the agreed partscore.', 'A2.6')
    stopped = all(h.stopper(s) for s in SUITS if s not in {c.strain for c in partner_calls})
    if '3N' in ctx.legal and (gf or h.hcp + lower >= 25) and stopped:
        return ctx.choose('3N', 'Enough strength for no trump game with the unbid suits stopped.', 'A2.6')
    if not gf and not compulsory:
        if partner.bid == '2N' and h.hcp >= 14 and '3N' in ctx.legal:
            return ctx.choose('3N', 'Accept the no-trump invitation with extra values.', 'A2.6')
        return ctx.choose('PASS', 'The previous limited bid is a suitable contract.', 'A2.6')
    if gf:
        if fit and str(_GAME[fit]) + fit in ctx.legal:
            return ctx.choose(str(_GAME[fit]) + fit, 'Honour the game force in the agreed suit.', 'A2.6')
        if partner.strain in _MAJOR and h.length(partner.strain) >= 3 and '4' + partner.strain in ctx.legal:
            return ctx.choose('4' + partner.strain, 'Reach game with support for partner’s major.', 'A2.6')
        own = [c for c in pair if c.seat == ctx.seat and c.strain in SUITS]
        long = max((c.strain for c in own), key=h.length, default=None)
        if long and h.length(long) >= 6 and str(_GAME[long]) + long in ctx.legal:
            return ctx.choose(str(_GAME[long]) + long, 'Reach game in the long suit after the forcing auction.', 'A2.6')
        if '3N' in ctx.legal:
            return ctx.choose('3N', 'Complete the game force when no suitable trump fit has emerged.', 'A2.6')
    if partner.strain in SUITS and h.length(partner.strain) >= 3:
        return ctx.choose(ctx.cheapest(partner.strain), 'Give preference while answering a forcing bid.', 'A2.6')
    own = [c for c in pair if c.seat == ctx.seat and c.strain in SUITS]
    if own:
        long = max((c.strain for c in own), key=h.length)
        return ctx.choose(ctx.cheapest(long), 'Rebid a natural suit to answer partner’s forcing call.', 'A2.6')
    return ctx.choose(ctx.cheapest('N'), 'Complete the compulsory response in no trumps.', 'A2.6')


def _preempt(ctx, pair):
    h, opening = ctx.h, pair[0]
    suit = opening.strain
    if opening.bid == '3N':
        if len(pair) == 1:
            if all(h.stopper(s) for s in _MAJOR) and h.hcp >= 8:
                return ctx.choose('PASS', 'Leave the gambling 3NT with useful outside stoppers.', 'A2.10.5')
            return ctx.choose('4C', 'Pass with clubs or correct to diamonds.', 'A2.10.5', True)
        if len(pair) == 2 and pair[1].bid == '4C':
            return ctx.choose('PASS' if h.length('C') > h.length('D') else '4D', 'Pass or correct to the long solid minor.', 'A2.10.5')
        return ctx.choose('PASS', 'The gambling-minor correction is complete.', 'A2.10.5')
    weak = opening.level == 2
    if len(pair) == 1:
        if weak and h.hcp >= 16 and h.length(suit) >= 2:
            return ctx.choose('2N', 'Game enquiry with 16+ points and a partial fit.', 'A2.10.4', True)
        own = [s for s in SUITS if s != suit and h.length(s) >= 6 and _good_suit(h, s)]
        if own:
            s = max(own, key=lambda s: (h.length(s), STRAINS.index(s)))
            bid = ctx.cheapest(s)
            if h.hcp >= (11 if weak and bid[0] == '2' else 16):
                return ctx.choose(bid, 'Natural strong response suit; forcing to game at the three level after a weak two.', 'A2.10.4' if weak else 'A2.10.3')
        if h.hcp >= 16 and h.length(suit) >= 2 and all(h.stopper(s) for s in SUITS if s != suit):
            return ctx.choose('3N', 'No trump game with a fit for the preempt and outside stoppers.', 'A2.10.3')
        if suit in _MAJOR and (h.support_points(suit) >= 17 and h.length(suit) >= 3 or h.length(suit) >= 5):
            return ctx.choose('4' + suit, 'Raise the long major to game for playing strength or further obstruction.', 'A2.10.3-4')
        if h.length(suit) >= (3 if weak else 4) and not _game(opening.bid):
            return ctx.choose(str(opening.level + 1) + suit, 'Further preemptive raise; this is not a game invitation.', 'A2.10.3-4')
        return ctx.choose('PASS', 'No constructive or obstructive response to the preempt.', 'A2.10.3-4')
    response = pair[1]
    if len(pair) == 2:
        if weak and response.bid == '2N':
            low, high = ctx.profile.get('weak_two_range', [5, 9])
            if h.hcp <= (low + high) // 2:
                return ctx.choose('3' + suit, 'Minimum weak two: return to the opening suit.', 'A2.10.4', True)
            if h.has(suit, 'A') and h.has(suit, 'Q') and h.has(suit, 'J'):
                return ctx.choose('3N', 'Maximum weak two with a particularly good suit, at least AQJxxx.', 'A2.10.4', True)
            features = [s for s in SUITS if s != suit and (h.has(s, 'A') or h.has(s, 'K'))]
            if features:
                feature = min(features, key=lambda s: bid_rank('3' + s))
                return ctx.choose('3' + feature, 'Maximum weak two with a high-card feature in this suit.', 'A2.10.4', True)
            return ctx.choose('3' + suit, 'No side high-card feature to show; return to the long suit.', 'A2.10.4', True)
        if response.strain == suit or response.strain == 'N' or _game(response.bid):
            return ctx.choose('PASS', 'Respect partner’s placement after the preempt.', 'A2.10.3-4')
        if weak and response.level == 2:
            if h.length(response.strain) >= 3 and h.hcp >= 8:
                return ctx.choose('3' + response.strain, 'Encouraging support for the nonforcing two-level response.', 'A2.10.4')
            return ctx.choose('PASS' if h.length(response.strain) >= 2 else '3' + suit, 'Choose the better partscore after a nonforcing response.', 'A2.10.4')
        if h.length(response.strain) >= 2:
            return ctx.choose(str(_GAME[response.strain]) + response.strain, 'Support the strong six-card response suit.', 'A2.10.3-4')
        return ctx.choose(ctx.cheapest(suit), 'Rebid the preemptive suit in response to the forcing new suit.', 'A2.10.3-4')
    if weak and response.bid == '2N' and len(pair) == 3:
        answer = pair[2]
        if answer.bid == '3N':
            return ctx.choose('PASS' if all(h.stopper(s) for s in SUITS if s != suit) else str(_GAME[suit]) + suit, 'Choose no trumps or the long suit after the good-suit response.', 'A2.10.4')
        if answer.strain != suit:
            if all(h.stopper(s) for s in SUITS if s not in (suit, answer.strain)):
                return ctx.choose('3N', 'The feature supplies the remaining stopper for no trump game.', 'A2.10.4')
            if suit in _MAJOR and h.length(suit) >= 2:
                return ctx.choose('4' + suit, 'Accept the maximum weak two in the long major.', 'A2.10.4')
        if h.hcp >= 19 and suit in _MAJOR and h.length(suit) >= 3:
            return ctx.choose('4' + suit, 'Enough extra strength for game opposite a minimum weak two.', 'A2.10.4')
        return ctx.choose('PASS' if answer.strain == suit else ctx.cheapest(suit), 'Stop in the long suit after the enquiry.', 'A2.10.4')
    return _continuation(ctx, pair)


def choose(ctx):
    """Return a natural Acol decision, or defer a different auction family."""
    if not ctx.auction.opening:
        return _opening(ctx)
    if not _uncontested(ctx.auction, ctx.seat):
        return None
    pair = _partnership(ctx.auction, ctx.seat)
    if not pair or pair[0] != ctx.auction.opening:
        return None
    opening = pair[0]
    if opening.bid == '3N' or opening.level >= 2 and opening.strain in SUITS and opening.bid != '2C':
        return _preempt(ctx, pair)
    if opening.level != 1 or opening.strain == 'N':
        return None
    if len(pair) == 1:
        return _respond_one(ctx, opening) if ctx.seat != opening.seat else ctx.choose('PASS', 'Partner declined to respond.', 'A2.3')
    if len(pair) == 2 and ctx.seat == opening.seat:
        return _opener_rebid(ctx, pair)
    if len(pair) == 3 and ctx.seat != opening.seat:
        return _responder_rebid(ctx, pair)
    return _continuation(ctx, pair)


def _m(description, rule, **kw):
    return Meaning(description=description, rule=rule, **kw)


def interpret(auction, call, profile):
    """Interpret one public call without consulting any player's cards."""
    if not call.is_contract:
        return None
    suit, level = call.strain, call.level
    if not auction.opening:
        if level == 1 and suit in SUITS:
            return _m('Natural opening, possibly a distributional Rule of 20 hand.', 'A2.1', hcp_min=9, min_length={suit: 4}, suit=suit)
        if level == 2 and suit in profile.get('weak_twos', ['D', 'H', 'S']):
            low, high = profile.get('weak_two_range', [5, 9])
            return _m('Weak two with a decent six-card suit.', 'A2.10.4', hcp_min=low, hcp_max=high, min_length={suit: 6}, max_length={suit: 6}, suit=suit)
        if level in (3, 4) and suit in SUITS:
            return _m('Long-suit preempt.', 'A2.10.1-2', hcp_max=9, min_length={suit: 7 if level == 3 else 8}, suit=suit)
        if call.bid == '3N':
            return _m('Gambling 3NT: a solid long minor and little outside.', 'A2.10.5', hcp_min=10, hcp_max=12, artificial=True)
        return None
    if not _uncontested(auction, call.seat):
        return None
    pair = _partnership(auction, call.seat)
    if not pair or pair[0] != auction.opening:
        return None
    opening = pair[0]
    first = opening.strain
    if opening.bid == '3N':
        if len(pair) == 1 and call.bid == '4C':
            return _m('Pass with clubs or correct to diamonds.', 'A2.10.5', artificial=True, forcing='none')
        if len(pair) == 2 and call.bid == '4D':
            return _m('Correction to the solid diamond suit.', 'A2.10.5', min_length={'D': 7}, suit='D')
        return None
    if opening.level >= 2 and opening.strain in SUITS and opening.bid != '2C':
        weak = opening.level == 2
        if len(pair) == 1:
            if weak and call.bid == '2N':
                return _m('Game enquiry with a partial fit.', 'A2.10.4', hcp_min=16, min_length={first: 2}, artificial=True, forcing='one-round')
            if suit == first:
                return _m('Preemptive raise or placement in game, never a game try.', 'A2.10.3-4', min_length={first: 3} if level < _GAME[first] else {}, suit=first, forcing='signoff')
            if suit == 'N':
                return _m('Natural game choice with outside stoppers.', 'A2.10.3', hcp_min=16, forcing='signoff')
            return _m('Natural response in a strong six-card suit.', 'A2.10.3-4', hcp_min=11 if weak and level == 2 else 16, min_length={suit: 6}, suit=suit, forcing='none' if weak and level == 2 else 'game' if weak else 'one-round')
        if len(pair) == 2 and weak and pair[1].bid == '2N':
            low, high = profile.get('weak_two_range', [5, 9])
            if suit == first:
                return _m('Minimum weak two, or no showable feature.', 'A2.10.4', hcp_min=low, hcp_max=high, min_length={first: 6}, suit=first, artificial=True)
            return _m('Maximum weak two: good long suit in 3NT, otherwise a side high-card feature.', 'A2.10.4', hcp_min=(low + high) // 2 + 1, hcp_max=high, min_length={first: 6}, artificial=True)
        return _m('Natural continuation after a preempt.', 'A2.10.3-4', suit=suit if suit in SUITS else None, forcing='signoff' if _game(call.bid) else 'none')
    if opening.level != 1 or first == 'N':
        return None
    if len(pair) == 1 and call.seat != opening.seat:
        if _splinter(opening, call):
            return _m('Splinter raise with four trumps and shortage.', 'A2.2.2', hcp_min=11, hcp_max=15, min_length={first: 4}, max_length={suit: 1}, forcing='game', artificial=True, suit=first)
        if first in _MAJOR and call.bid == '3N':
            return _m('Balanced pudding raise with four-card major support.', 'A2.2.2', hcp_min=12, hcp_max=15, min_length={first: 4}, balanced=True, forcing='game', artificial=True, suit=first)
        if suit == first:
            if first in _MINOR:
                return _m('Limited minor-suit raise.', 'A2.2.1', hcp_min=6 if level == 2 else 10, hcp_max=9 if level == 2 else 12, min_length={first: 4}, suit=first, forcing='invite' if level == 3 else 'none')
            return _m('Major raise evaluated by losing tricks.', 'A2.2.1', hcp_min=6, hcp_max=19 if level >= 4 else 15, min_length={first: 3 if level == 2 else 4}, suit=first, forcing='invite' if level == 3 else 'signoff' if level >= 4 else 'none')
        if suit == 'N':
            if level == 1:
                return _m('Limited no-trump response.', 'A2.4', hcp_min=8 if first == 'C' else 6, hcp_max=10 if first == 'C' else 9, balanced=True if first == 'C' else None, max_length={'H': 3, 'S': 3} if first in _MINOR else {})
            return _m('Natural no-trump invitation.' if level == 2 else 'Natural no-trump game response.', 'A2.4', hcp_min=10 if level == 2 else 13, hcp_max=12 if level == 2 else 37, balanced=True if level == 2 else None, forcing='invite' if level == 2 else 'signoff')
        if _jump(auction, call.bid):
            return _m('Strong natural jump shift.', 'A2.3.2', hcp_min=16, min_length={suit: 5}, suit=suit, forcing='game')
        # A documented practical exception permits a three-card minor when
        # the hand is too strong for a limited NT response and has no legal
        # four-card new suit. Public inference cannot distinguish that case.
        minimum_length = 3 if suit in _MINOR and level == 2 else 5 if first == 'S' and suit == 'H' else 4
        return _m('Natural new-suit response.', 'A2.3.1', hcp_min=6 if level == 1 else 9, min_length={suit: minimum_length}, suit=suit, forcing='none' if auction.passed_hand(call.seat) else 'one-round')
    if len(pair) == 2 and call.seat == opening.seat:
        response = pair[1]
        if response.strain == first:
            if suit != first and suit != 'N':
                return _m('Long-suit game try.' if first in _MAJOR else 'Stopper-showing minor-suit game try.', 'A2.7', min_length={suit: 3} if first in _MAJOR else {}, forcing='invite', artificial=first in _MINOR, suit=first)
            if suit == first:
                return _m('Game invitation in the agreed major.' if level == 3 and first in _MAJOR else 'Natural contract placement.', 'A2.7', suit=first, forcing='invite' if level == 3 and first in _MAJOR else 'signoff')
        if _splinter(opening, response) or first in _MAJOR and response.bid == '3N':
            return _m('Return to the agreed major.', 'A2.2.2', suit=first, forcing='signoff' if _game(call.bid) else 'game')
        if suit == response.strain and suit in SUITS:
            jump = _jump(auction, call.bid)
            return _m('Support for responder’s suit; distribution can replace high cards.', 'A2.5.1-2', hcp_min=9, min_length={suit: 4}, suit=suit, forcing='signoff' if _game(call.bid) else 'invite' if jump else 'none')
        if suit == first:
            jump = _jump(auction, call.bid)
            return _m('Strong long-suit rebid.' if jump else 'Minimum rebid; may be four cards with 4-4-4-1 shape.', 'A2.5.1-2', hcp_min=16 if jump else 9, hcp_max=18 if jump and not _game(call.bid) else 37 if _game(call.bid) else 18, min_length={first: 6 if jump else 4}, suit=first, forcing='game' if jump and response.level == 2 and response.strain != 'N' else 'invite' if jump and not _game(call.bid) else 'none')
        if suit == 'N':
            if response.strain == 'N':
                return _m('Natural no-trump continuation after a limited response.', 'A2.4', forcing='signoff' if _game(call.bid) else 'invite')
            minimum = 19 if level == 3 else 17 if level == 2 else 15
            return _m('Balanced no-trump rebid.', 'A1.2', hcp_min=minimum, hcp_max=minimum if level == 3 else minimum + 1, balanced=True)
        jump = _jump(auction, call.bid)
        reverse = bid_rank(call.bid) > bid_rank('2' + first)
        return _m('Strong jump shift.' if jump else 'Reverse.' if reverse else 'Natural second suit.', 'A2.5.2' if jump else 'A2.5.3' if reverse else 'A2.5.1', hcp_min=(16 if response.level == 2 else 19) if jump else 16 if reverse else 9, min_length={first: 4, suit: 4}, suit=suit, forcing='game' if jump or reverse and level >= 3 else 'one-round' if reverse else 'none')
    if len(pair) == 3 and call.seat != opening.seat:
        response, rebid = pair[1:]
        if _fourth_suit(pair, call):
            already_forced = (_jump(auction.prefix(rebid.index), rebid.bid) and rebid.strain != first
                              or _jump(auction.prefix(response.index), response.bid))
            return _m('Artificial fourth-suit forcing.', 'A2.6.1', hcp_min=9 if already_forced and response.level == 2 else 6 if already_forced else 11 if level == 2 else 12, forcing='game' if level >= 3 or already_forced else 'one-round', artificial=True)
        if [c.bid for c in pair] == ['1C', '1D', '1H'] and call.bid == '1S':
            return _m('Natural spades in the special economical fourth-suit auction.', 'A2.6.1', hcp_min=6, min_length={'S': 4}, suit='S', forcing='one-round')
        if suit in SUITS and suit not in (first, response.strain, rebid.strain):
            return _m('Game-going second suit by responder, including a responder reverse.', 'A2.3.1', hcp_min=13, min_length={suit: 4}, suit=suit, forcing='game')
        if response.strain == first:
            return _m('Answer to a game trial.', 'A2.7', suit=first, artificial=suit not in (first, 'N'), forcing='signoff' if _game(call.bid) or suit == first else 'invite')
        if _game(call.bid):
            return _m('Natural game choice.', 'A2.6', suit=suit if suit in SUITS else None, forcing='signoff')
        reverse = _reverse(opening, response, rebid, auction)
        minimum_rebid = call.bid == _cheapest_after(auction, suit)
        if reverse:
            nonforcing = minimum_rebid and suit in (first, response.strain, 'N')
            return _m('Continuation after opener’s reverse.', 'A2.5.3', hcp_min=6 if nonforcing else 10, min_length={suit: 6} if suit == response.strain else {}, suit=suit if suit in SUITS else None, forcing='none' if nonforcing else 'game')
        if suit == first:
            jump = _jump(auction, call.bid) or rebid.strain == first and level == 3
            return _m('Invitational jump preference.' if jump else 'Simple or false preference.', 'A2.6', hcp_min=10 if jump else 6, hcp_max=12 if jump else 9, min_length={first: 3 if jump else 2}, suit=first, forcing='invite' if jump else 'none')
        if suit == rebid.strain:
            return _m('Invitational support for opener’s second suit.', 'A2.6', hcp_min=10, hcp_max=12, min_length={suit: 4}, suit=suit, forcing='invite')
        if suit == response.strain and suit in SUITS:
            jump = _jump(auction, call.bid)
            return _m('Six-card response suit.', 'A2.6', hcp_min=10 if jump else 6, hcp_max=12 if jump else 9, min_length={suit: 6}, suit=suit, forcing='invite' if jump else 'none')
        if suit == 'N':
            return _m('Natural no-trump invitation.' if level == 2 else 'Limited no-trump rebid.', 'A2.6', hcp_min=10 if level == 2 else 6, hcp_max=12 if level == 2 else 9, forcing='invite' if level == 2 else 'none')
    if len(pair) == 4 and _fourth_suit(pair[:3], pair[3]):
        response = pair[1]
        minimum = call.bid == _cheapest_after(auction, suit)
        limited = minimum and suit in (first, response.strain, 'N')
        return _m('Answer to fourth-suit forcing.', 'A2.6.1', min_length={suit: 2} if suit == response.strain else {}, suit=suit if suit in SUITS else None, forcing='none' if limited else 'game')
    if len(pair) == 5 and _fourth_suit(pair[:3], pair[3]) and not _game(call.bid):
        return _m('Responder continues after fourth-suit clarification; game is now forced.', 'A2.6.1', forcing='game', suit=suit if suit in SUITS else None)
    return _m('Natural continuation; previous strength and shape promises still apply.', 'A2.6', suit=suit if suit in SUITS else None, forcing='signoff' if _game(call.bid) else 'none')
