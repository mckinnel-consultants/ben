"""Modern Acol notrump and strong-club auctions (EBU sections A1.1--A1.4).

The partnership uses 12--14 notrumps and the published Baron/minor-relay
continuations. Only public auction information and the bidder's own hand are
used. Opponents' intervention is deliberately left to the competitive module.
"""
from dataclasses import dataclass

from .core import Auction, Call, Context, Decision, Meaning, SUITS, bid_rank


@dataclass
class NTFrame:
    call: Call
    low: int
    high: int
    mode: str
    actions: list
    earlier: list

    @property
    def level(self):
        return self.call.level

    @property
    def opener(self):
        return self.call.seat

    @property
    def responder(self):
        return (self.opener + 2) % 4


def _side(a, seat):
    return [c for c in a.calls if c.seat % 2 == seat % 2 and c.bid != 'PASS']


def _quiet(a, seat, since=0):
    return not any(c.bid != 'PASS' and c.seat % 2 != seat % 2
                   for c in a.calls if c.index >= since)


def _protective(a, c):
    previous = a.calls[:c.index]
    return len(previous) >= 3 and previous[-1].bid == previous[-2].bid == 'PASS'


def _rebid_range(opening, response, rebid):
    """Strength union where natural shape exceptions make a rebid ambiguous.

    A jump-shift consumes room, and a strong long minor can jump to 3NT.
    These public auctions must not falsely exclude the opener's actual hand.
    """
    if response.bid == '1N':
        return (17, 18) if rebid.bid == '2N' else (19, 22 if opening.strain in ('C', 'D') else 19)
    if response.level >= 3:
        return 15, 22
    if response.bid == '2N':
        return 14, 22
    cheapest = 1 if response.level == 1 else 2
    if rebid.level == cheapest:
        return 15, 16
    if rebid.level == 3:
        return (19 if cheapest == 1 else 17), (22 if opening.strain in ('C', 'D') else 19)
    return 17, 18


def _frame(a, seat, profile):
    """Find the initial notrump bid, never a later relay or quantitative bid."""
    ours = _side(a, seat)
    contracts = [c for c in ours if c.is_contract]
    if not contracts:
        return None
    base = None
    first = contracts[0]
    mode = 'system'
    if ours[0].bid == 'X' and len(contracts) >= 2 and contracts[1].seat == ours[0].seat and contracts[1].strain == 'N':
        base, mode = contracts[1], 'natural'
        low, high = (15, 18) if _protective(a, ours[0]) else (19, 22)
    elif first.bid in ('1N', '2N'):
        previous = [c for c in a.calls[:first.index] if c.is_contract]
        doubled = any(c.bid == 'X' and c.index < first.index for c in ours)
        if not previous:
            low, high = profile.get('nt_range', [12, 14]) if first.level == 1 else profile.get('two_nt_range', [20, 22])
        elif doubled:
            double = next(c for c in ours if c.bid == 'X')
            low, high = (15, 18) if _protective(a, double) else (19, 22)
            mode = 'natural'
        elif first.level == 1:
            low, high = (11, 14) if _protective(a, first) else (16, 18)
        elif _protective(a, first):
            low, high = 19, 21
        else:
            return None  # Unusual 2NT, handled by competitive bidding.
        base = first
    elif first.bid == '2C' and len(contracts) >= 3:
        response, rebid = contracts[1:3]
        if rebid.seat == first.seat and rebid.strain == 'N':
            base = rebid
            if response.bid == '2D':
                low, high = {2: (23, 24), 3: (25, 27), 4: (28, 30)}.get(rebid.level, (31, 37))
                mode = 'system' if rebid.level == 2 else 'natural'
            else:
                low, high, mode = 23, 37, 'positive'
    elif first.level == 1 and first.strain in tuple(SUITS) and len(contracts) >= 3:
        response, rebid = contracts[1:3]
        if response.seat != first.seat and rebid.seat == first.seat and rebid.strain == 'N':
            base, mode = rebid, 'natural'
            low, high = _rebid_range(first, response, rebid)
    if base is None or not _quiet(a, seat, base.index + 1):
        return None
    return NTFrame(base, low, high, mode,
                   [c for c in ours if c.index > base.index],
                   [c for c in ours if c.index < base.index])


def _offer(ctx, bid, text, section, alert=False):
    return ctx.choose(bid, text, 'A' + section, alert)


def _m(text, section, **kwargs):
    return Meaning(description=text, rule='A' + section, **kwargs)


def _longest(h, suits=SUITS, minimum=0):
    return next(iter(sorted((s for s in suits if h.length(s) >= minimum),
                            key=lambda s: (h.length(s), 'CDHS'.index(s)), reverse=True)), None)


def _four_card(ctx, min_level=1, excluded=()):
    options = [ctx.cheapest(s, min_level) for s in 'CDHS'
               if ctx.h.length(s) >= 4 and s not in excluded]
    return min((b for b in options if b), key=bid_rank, default=None)


def _maximum(ctx, f):
    return ctx.h.hcp >= f.high or (f.high - f.low > 2 and ctx.h.hcp >= f.high - 1)


def _game_values(f):
    # EBU permits the ordinary 2NT response with four points, but calls for
    # a couple of points after the exceptionally passable 2C–2D–2NT rebid.
    return max(2 if f.low >= 23 else 0, (25 if f.level == 1 else 24) - f.low)


def _solid(h, s):
    return h.length(s) >= 6 and all(h.has(s, r) for r in 'AKQJ')


def _baron_jump_cue(reply, call):
    return (reply.strain in tuple(SUITS) and call.strain in tuple(SUITS)
            and reply.strain != call.strain and bid_rank(call.bid) - bid_rank(reply.bid) > 5)


def _nt_shape(h, allow_singleton=False):
    return h.balanced or (allow_singleton and h.shape == (5, 4, 3, 1)
                         and all(h.has(s, 'A') or h.has(s, 'K')
                                 for s in SUITS if h.length(s) == 1))


def _opening(ctx):
    if ctx.auction.opening:
        return None
    h = ctx.h
    low, high = ctx.profile.get('nt_range', [12, 14])
    two_low, two_high = ctx.profile.get('two_nt_range', [20, 22])
    if h.hcp >= 23 or (h.hcp >= 20 and h.losers <= 3 and h.quick_tricks >= 4):
        return _offer(ctx, '2C', 'Strong artificial opening: 23+ points or game-forcing playing strength.', '1.4', True)
    if two_low <= h.hcp <= two_high and _nt_shape(h, True):
        return _offer(ctx, '2N', f'Balanced {two_low}–{two_high} points.', '1.3')
    if low <= h.hcp <= high and h.balanced:
        major = _longest(h, 'HS', 5)
        if major and any(h.has(major, r) for r in 'AKQ'):
            return None
        return _offer(ctx, '1N', f'Weak notrump, {low}–{high} points.', '1.1', True)
    return None


def _strong(ctx):
    a, h = ctx.auction, ctx.h
    opening = a.opening
    if not opening or opening.bid != '2C' or opening.seat % 2 != ctx.seat % 2 or not _quiet(a, ctx.seat):
        return None
    calls = _side(a, ctx.seat)
    if len(calls) == 1 and ctx.seat != opening.seat:
        good = [s for s in SUITS if h.length(s) >= 5 and h.has(s, 'A') and h.has(s, 'Q')]
        has_ace = any(h.has(s, 'A') for s in SUITS)
        has_king = any(h.has(s, 'K') for s in SUITS)
        positive = (h.hcp >= 8 and (has_ace or has_king)) or (has_ace and has_king) or bool(good)
        if not positive:
            return _offer(ctx, '2D', 'Negative waiting response to the strong club.', '1.4.1', True)
        solid = _longest(h, [s for s in SUITS if _solid(h, s)])
        if solid:
            cheapest = ctx.cheapest(solid)
            return _offer(ctx, str(int(cheapest[0]) + 1) + solid, 'Positive response with a solid six-card or longer suit.', '1.4.1')
        five = _longest(h, minimum=5)
        if h.balanced and h.hcp >= 8 and (not five or h.suit_quality(five) < 8):
            return _offer(ctx, '2N', 'Positive balanced response, at least eight points.', '1.4.1')
        if five:
            return _offer(ctx, ctx.cheapest(five), 'Positive response with a good five-card or longer suit.', '1.4.1')
        return _offer(ctx, '2N', 'Positive balanced response including an ace and a king.', '1.4.1')
    if len(calls) == 2 and ctx.seat == opening.seat:
        response = calls[1]
        if h.balanced:
            if response.bid == '2D':
                bid = '2N' if h.hcp <= 24 else '3N' if h.hcp <= 27 else '4N' if h.hcp <= 30 else '6N' if h.hcp <= 34 else '7N'
                return _offer(ctx, bid, 'Balanced strong-club rebid showing the corresponding notrump range.', '1.4.2')
            if response.bid in ('2H', '2S'):
                return _offer(ctx, '2N', 'Balanced strong-club hand; positive auction continues naturally.', '1.4.4')
            if response.bid == '2N':
                return _offer(ctx, '3N', 'Balanced hand after a positive notrump response; the auction is forcing to 4NT.', '1.4.4')
        if response.bid != '2D' and response.strain in tuple(SUITS) and h.length(response.strain) >= 3:
            return _offer(ctx, ctx.cheapest(response.strain, 3), 'Support for partner’s positive suit; game forcing.', '1.4.4')
        suit = _longest(h, minimum=5) or _longest(h)
        bid = ctx.cheapest(suit)
        if _solid(h, suit):
            bid = str(int(bid[0]) + 1) + suit
        return _offer(ctx, bid, 'Natural strong-club rebid, forcing to game' + (' with a solid suit.' if _solid(h, suit) else '.'), '1.4.2')
    # Natural development after a suit rebid is forcing to game. This also
    # prevents a weak negative responder from passing at the two level.
    if len(calls) >= 3 and calls[2].strain in tuple(SUITS):
        partner = next((c for c in reversed(calls) if c.seat == ctx.partner and c.is_contract), None)
        if not partner:
            return None
        if partner.strain in ('H', 'S') and h.length(partner.strain) >= 3:
            target = 4 if h.hcp < (8 if ctx.seat != opening.seat else 27) else max(3, partner.level + 1)
            return _offer(ctx, ctx.cheapest(partner.strain, target), 'Raise partner’s natural major in the game-forcing strong-club auction.', '1.4')
        if partner.bid == '3N' or (partner.level >= (4 if partner.strain in ('H', 'S') else 5) and partner.strain in tuple(SUITS)):
            return _offer(ctx, 'PASS', 'Game reached after the strong-club opening.', '1.4')
        own = [c.strain for c in calls if c.seat == ctx.seat and c.is_contract and c.strain in tuple(SUITS)]
        new_suit = _longest(h, [s for s in SUITS if s not in own and s != partner.strain], 5)
        if new_suit:
            return _offer(ctx, ctx.cheapest(new_suit), 'Show a natural five-card suit; the strong-club auction remains forcing.', '1.4')
        if ctx.seat == opening.seat:
            suit = calls[2].strain
            if h.length(suit) >= 6:
                return _offer(ctx, ctx.cheapest(suit, 4 if suit in 'HS' else 5), 'Place the game with the strong six-card suit.', '1.4')
        if partner.strain in ('C', 'D') and h.length(partner.strain) >= 4 and not h.balanced:
            return _offer(ctx, ctx.cheapest(partner.strain, 5), 'Raise the minor to game in the forcing strong-club auction.', '1.4')
        return _offer(ctx, ctx.cheapest('N', 3), 'Natural notrump continuation; game is compulsory.', '1.4')
    return None


def _balanced_rebid(ctx):
    a, h = ctx.auction, ctx.h
    calls = _side(a, ctx.seat)
    if len(calls) != 2 or not _quiet(a, ctx.seat) or not h.balanced or not 15 <= h.hcp <= 19:
        return None
    opening, response = calls
    if opening.seat != ctx.seat or opening.level != 1 or opening.strain not in tuple(SUITS) or not response.is_contract:
        return None
    if response.strain in ('H', 'S') and h.length(response.strain) >= 4:
        return None  # Natural bidding raises the known four-card major fit.
    if response.strain == opening.strain:
        return None
    if response.bid == '1N':
        bid = 'PASS' if h.hcp <= 16 else '2N' if h.hcp <= 18 else '3N'
    else:
        lowest = ctx.cheapest('N')
        level = int(lowest[0]) + (1 if h.hcp >= 17 else 0)
        bid = '3N' if h.hcp == 19 else str(min(3, level)) + 'N'
    return _offer(ctx, bid, 'Balanced rebid: 15–16 at the lowest level, 17–18 a jump, 19 points at 3NT.', '1.2')


def _initial_response(ctx, f):
    h, level = ctx.h, f.level
    invite = 25 - f.high
    game = _game_values(f)
    five = _longest(h, 'HS', 5)
    four = _longest(h, 'HS', 4)
    minor = _longest(h, 'CD', 6)
    if level == 1:
        if h.hcp >= 38 - f.low:
            return _offer(ctx, '7N', 'Sufficient combined strength for a grand slam.', '1.1')
        if h.hcp >= 34 - f.low and h.hcp < 38 - f.high and h.balanced:
            return _offer(ctx, '6N', 'Balanced small-slam values; signoff.', '1.1')
        if h.hcp >= 32 - f.low and h.balanced:
            return _offer(ctx, '2S', 'Two-way Baron: balanced slam investigation.', '1.1.5', True)
        if h.hcp >= 30 - f.low and h.shape in ((4, 4, 3, 2), (4, 4, 4, 1)):
            return _offer(ctx, '2S', 'Two-way Baron: at least eighteen points with four-card suits to investigate for slam.', '1.1.5', True)
        # Weak 5-4 majors, long diamonds with both majors, and long clubs
        # with a major can escape via Stayman. Strong 5S/4H also starts here.
        weak_escape = h.hcp < invite and ((h.length('H') >= 4 and h.length('S') >= 4 and five)
                          or (h.length('D') >= 5 and h.length('H') >= 3 and h.length('S') >= 3)
                          or (h.length('C') >= 6 and four))
        stayman = weak_escape or (four and (not five or (h.length('S') == 5 and h.length('H') >= 4)) and h.hcp >= invite)
        if stayman:
            return _offer(ctx, '2C', 'Stayman: ask for a four-card major, including the agreed weak escapes.', '1.1.2', True)
        if five:
            if h.hcp >= 18 and h.length(five) >= 6 and h.suit_quality(five) >= 9:
                return _offer(ctx, '3' + five, 'Strong six-card major with slam interest.', '1.1.7')
            return _offer(ctx, '2D' if five == 'H' else '2H', 'Transfer to a five-card or longer ' + ('heart' if five == 'H' else 'spade') + ' suit.', '1.1.3', True)
        if minor and h.hcp < invite:
            return _offer(ctx, '2N', 'Relay to clubs, to play in a long minor.', '1.1.6', True)
        if minor and h.hcp >= 16:
            return _offer(ctx, '3' + minor, 'Strong long minor with slam interest.', '1.1.7')
        if h.hcp < invite:
            return _offer(ctx, 'PASS', 'Insufficient values to invite game opposite the notrump range.', '1.1')
        if h.hcp < game:
            return _offer(ctx, '2S', 'Two-way Baron: balanced game invitation without major-suit interest.', '1.1.5', True)
        return _offer(ctx, '3N', 'Game values without a major-suit fit to investigate.', '1.1')
    # Responses to a 2NT opening, or 2C–2D–2NT with its adjusted range.
    slam_invite = 33 - f.high
    if h.hcp < game:
        return _offer(ctx, 'PASS', 'Too weak for game opposite this notrump range.', '1.3' if f.low < 23 else '1.4.3')
    if h.hcp >= 37 - f.low:
        return _offer(ctx, '7N', 'Combined values for a grand slam.', '1.3')
    if minor and h.hcp >= 33 - f.low and h.suit_quality(minor) >= 9:
        return _offer(ctx, '4' + minor, 'Natural long-minor response, forcing to slam.', '1.3.7')
    good_ten = h.hcp == slam_invite - 1 and h.controls >= 4 and h.shape in ((4, 4, 3, 2), (4, 4, 4, 1))
    if h.hcp >= slam_invite or good_ten:
        if h.hcp >= 33 - f.low and h.hcp < 37 - f.high and h.balanced and not four:
            return _offer(ctx, '6N', 'Balanced small-slam values; signoff.', '1.3')
        if not five:
            return _offer(ctx, '3S', 'Baron: investigate a slam and four-card suit fits.', '1.3.6', True)
    if five:
        return _offer(ctx, '3D' if five == 'H' else '3H', 'Transfer to a five-card or longer major.', '1.3.4', True)
    if four:
        return _offer(ctx, '3C', 'Stayman: ask for a four-card major.', '1.3.3', True)
    if minor and h.hcp >= slam_invite:
        return _offer(ctx, '4' + minor, 'Natural long-minor response, forcing to slam.', '1.3.7')
    return _offer(ctx, '3N', 'Game values without a major-suit fit.', '1.3')


def _stayman(ctx, f):
    acts, h, n = f.actions, ctx.h, f.level + 1
    rule = '1.1.2' if f.level == 1 else '1.3.3'
    if len(acts) == 1:
        strain = 'H' if h.length('H') >= 4 else 'S' if h.length('S') >= 4 else 'D'
        return _offer(ctx, str(n) + strain, 'Stayman reply: ' + ('no four-card major.' if strain == 'D' else 'four or more ' + ('hearts (spades still possible).' if strain == 'H' else 'spades, fewer than four hearts.')), rule, strain == 'D')
    reply = acts[1]
    if len(acts) == 2:
        fit = reply.strain in ('H', 'S') and h.length(reply.strain) >= 4
        invite = 25 - f.high
        game = _game_values(f)
        if f.level == 1 and h.hcp < invite:
            if fit or (reply.strain == 'D' and h.length('D') >= 5):
                return _offer(ctx, 'PASS', 'Weak Stayman escape: play in the discovered fit.', rule)
            if h.length('C') >= 6:
                return _offer(ctx, '3C', 'Weak Stayman escape with six or more clubs.', rule)
            if reply.strain == 'D':
                major = _longest(h, 'HS', 5)
                if major:
                    return _offer(ctx, '2' + major, 'Weak five-card major with four cards in the other major.', rule)
            return _offer(ctx, 'PASS', 'Weak Stayman escape: stop at the two level.', rule)
        if fit:
            if f.level == 1 and h.hcp < game:
                return _offer(ctx, '3' + reply.strain, 'Invitational raise of the four-card major fit.', rule)
            if h.hcp + f.low >= 33:
                return _offer(ctx, '6' + reply.strain, 'Small slam with the established major fit.', rule)
            return _offer(ctx, '4' + reply.strain, 'Sign off in the four-card major fit.', rule)
        if f.level == 1 and h.hcp < game:
            return _offer(ctx, '2N', 'Invitational notrump rebid after Stayman.', rule)
        if reply.strain == 'D':
            major = _longest(h, 'HS', 5)
            if major:
                return _offer(ctx, '3' + major, 'Five cards in this major and four in the other, forcing to game.', rule)
        if h.hcp + f.high >= 33 and h.hcp + f.low < 33:
            return _offer(ctx, '4N', 'Quantitative slam invitation with no major fit.', rule)
        return _offer(ctx, '3N', 'No major fit; sign off in notrump game.', rule)
    continuation = acts[2]
    if len(acts) == 3:
        if continuation.bid == '2N':
            if h.length('S') >= 4 and reply.strain == 'H':
                return _offer(ctx, '3S' if _maximum(ctx, f) else 'PASS', 'Show the second four-card major with maximum values; otherwise decline the invitation.', rule)
            return _offer(ctx, '3N' if _maximum(ctx, f) else 'PASS', 'Accept the game invitation with a maximum.', rule)
        if continuation.level == 3 and continuation.strain in ('H', 'S'):
            major = continuation.strain
            if reply.strain == 'D':
                return _offer(ctx, '4' + major if h.length(major) >= 3 else '3N', 'Choose the major game with three-card support, otherwise 3NT.', rule)
            return _offer(ctx, '4' + major if _maximum(ctx, f) else 'PASS', 'Accept the major-suit game invitation with a maximum.', rule)
        if continuation.bid == '4N':
            return _offer(ctx, '6N' if _maximum(ctx, f) else 'PASS', 'Accept the quantitative slam invitation only with a maximum.', rule)
        return _offer(ctx, 'PASS', 'Respect responder’s Stayman signoff.', rule)
    # 1NT–2C–2H–2NT–3S: responder chooses between the second major and NT.
    if len(acts) == 4 and acts[-1].bid == '3S' and acts[2].bid == '2N':
        return _offer(ctx, '4S' if h.length('S') >= 4 else '3N', 'Choose game after opener shows both four-card majors.', rule)
    return None


def _transfer(ctx, f):
    acts, h = f.actions, ctx.h
    target = 'H' if acts[0].strain == 'D' else 'S'
    rule = ('1.1.3' if target == 'H' else '1.1.4') if f.level == 1 else ('1.3.4' if target == 'H' else '1.3.5')
    accept_level = f.level + 1
    if len(acts) == 1:
        break_transfer = h.length(target) >= 4 and _maximum(ctx, f) and h.support_points(target) >= (15 if f.level == 1 else 23) and h.suit_quality(target) >= 6
        level = accept_level + int(break_transfer)
        return _offer(ctx, str(level) + target, 'Accept the transfer' + (' with a maximum and four-card support (transfer break).' if break_transfer else '.'), rule, not break_transfer)
    if len(acts) == 2:
        accepted = acts[1]
        game = _game_values(f)
        invite = 25 - f.high
        if accepted.level > accept_level:
            if f.level == 1:
                return _offer(ctx, '4' + target if h.support_points(target) >= 9 else 'PASS', 'Reassess game opposite the maximum four-card transfer break.', rule)
            return _offer(ctx, 'PASS' if h.hcp < 33 - f.high else '6' + target, 'Game is already reached after the transfer break.', rule)
        if f.level == 1 and h.hcp < invite:
            return _offer(ctx, 'PASS', 'Weak transfer: play in the major.', rule)
        if f.level == 1 and target == 'H' and h.length('S') >= 4 and h.length('H') == 5:
            return _offer(ctx, '2S', 'Five hearts and four spades, invitational or stronger; forcing to at least 2NT.', rule)
        if h.length(target) >= 6:
            return _offer(ctx, ('3' if f.level == 1 and h.hcp < game else '4') + target, 'Six-card major: invite game or sign off in game.', rule)
        new_suit = _longest(h, [s for s in SUITS if s != target], 4)
        if new_suit and h.hcp >= game and (f.level == 2 or h.hcp >= game + 3):
            return _offer(ctx, ctx.cheapest(new_suit, 3), 'Natural second suit after the transfer; game forcing with slam interest.', rule)
        if f.level == 2 and 33 - f.high <= h.hcp < 33 - f.low:
            return _offer(ctx, '4N', 'Quantitative slam invitation with exactly five cards in the major.', rule)
        if h.hcp + f.low >= 33:
            return _offer(ctx, '6N', 'Small-slam values with a five-card major; opener may correct to the major.', rule)
        return _offer(ctx, '2N' if f.level == 1 and h.hcp < game else '3N', 'Five-card major with invitational or game values; opener selects the strain.', rule)
    if len(acts) == 3:
        rebid = acts[2]
        fit = h.length(target) >= 3
        if rebid.bid == '2N':
            bid = ('4' if _maximum(ctx, f) else '3') + target if fit else '3N' if _maximum(ctx, f) else 'PASS'
            return _offer(ctx, bid, 'Choose the strain with three-card major support and accept game with a maximum.', rule)
        if rebid.bid in ('3N', '6N'):
            return _offer(ctx, ('4' if rebid.bid == '3N' else '6') + target if fit else 'PASS', 'Prefer the eight-card major fit to notrump.', rule)
        if rebid.bid == '3' + target:
            return _offer(ctx, '4' + target if _maximum(ctx, f) else 'PASS', 'Accept the six-card major game invitation with a maximum.', rule)
        if rebid.bid == '4N':
            if not _maximum(ctx, f):
                return _offer(ctx, 'PASS', 'Decline the quantitative slam invitation.', rule)
            return _offer(ctx, '6' + target if fit else '6N', 'Accept the quantitative invitation and select the major with three-card support.', rule)
        if rebid.bid == '2S' and target == 'H':
            if h.length('S') >= 4:
                bid = ('4' if _maximum(ctx, f) else '3') + 'S'
            elif fit:
                bid = ('4' if _maximum(ctx, f) else '3') + 'H'
            else:
                bid = '3N' if _maximum(ctx, f) else '2N'
            return _offer(ctx, bid, 'Show a major fit or notrump after responder shows five hearts and four spades.', rule)
        if rebid.strain in tuple(SUITS) and rebid.strain != target and rebid.level < 4:
            if fit:
                return _offer(ctx, ctx.cheapest(target, 3), 'Show three-card support for responder’s first major in a game-forcing auction.', rule)
            if h.length(rebid.strain) >= 4:
                return _offer(ctx, ctx.cheapest(rebid.strain, 4), 'Agree responder’s second suit; game forcing.', rule)
            return _offer(ctx, '3N', 'No fit for either of responder’s suits.', rule)
        return _offer(ctx, 'PASS', 'Respect the major-suit signoff.', rule)
    if len(acts) == 4:
        rebid, reply = acts[2:4]
        if rebid.bid == '2S' and target == 'H':
            if h.hcp >= 25 - f.low:
                return _offer(ctx, '4' + reply.strain if reply.strain in ('H', 'S') else '3N', 'Raise the fit to game with game-going values.', rule)
            return _offer(ctx, 'PASS', 'The invitational five-four major hand has reached a playable contract.', rule)
        if rebid.strain in tuple(SUITS) and rebid.strain != target:
            if reply.strain in ('H', 'S') and h.length(reply.strain) >= 3:
                return _offer(ctx, ctx.cheapest(reply.strain, 4), 'Place the game in the established major fit.', rule)
            if reply.strain in ('C', 'D') and h.length(reply.strain) >= 4:
                return _offer(ctx, ctx.cheapest(reply.strain, 5), 'Place the game in the established minor fit.', rule)
            return _offer(ctx, 'PASS' if reply.bid == '3N' else '3N', 'Complete the game-forcing transfer auction.', rule)
    return None


def _baron(ctx, f):
    acts, h = f.actions, ctx.h
    rule = '1.1.5' if f.level == 1 else '1.3.6'
    nt_reply = str(f.level + 1) + 'N'
    if len(acts) >= 3 and _baron_jump_cue(acts[1], acts[2]):
        # The jump agrees the four-card suit and shows an ace. Slam bidding
        # now owns the agreed-suit controls/keycard continuation.
        return None
    if len(acts) == 1:
        if not _maximum(ctx, f):
            return _offer(ctx, nt_reply, 'Minimum notrump hand in response to Baron.', rule, True)
        bid = _four_card(ctx, f.level + 2 if f.level == 1 else 4)
        return _offer(ctx, bid or nt_reply, 'Maximum notrump hand: show the cheapest four-card suit.', rule, True)
    if len(acts) == 2:
        response = acts[1]
        maximum = response.strain != 'N'
        if f.level == 1 and h.hcp < 25 - f.low:
            return _offer(ctx, '3N' if maximum else 'PASS', 'Complete the game invitation: game opposite a maximum, otherwise stop.', rule)
        if h.balanced and not any(h.length(s) >= 5 for s in SUITS):
            if h.hcp >= 37 - f.high:
                return _offer(ctx, '7N' if maximum else '6N', 'Baron grand-slam invitation: seven opposite a maximum, six opposite a minimum.', rule)
            if h.hcp + f.low >= (34 if f.level == 1 else 33):
                return _offer(ctx, '6N', 'Balanced small-slam strength.', rule)
            if h.hcp + f.high >= 33:
                return _offer(ctx, '6N' if maximum else '3N' if f.level == 1 else 'PASS', 'Baron slam invitation: slam only opposite a maximum.', rule)
        if response.strain in tuple(SUITS) and h.length(response.strain) >= 4:
            return _offer(ctx, ctx.cheapest(response.strain, response.level + 1), 'Agree the four-card fit found by Baron; game forcing.', rule)
        bid = _four_card(ctx, 3 if f.level == 1 else 4)
        if bid:
            return _offer(ctx, bid, 'Continue Baron by showing the cheapest four-card suit.', rule)
        return _offer(ctx, '6N' if maximum and f.level == 2 else '3N' if f.level == 1 else '4N', 'No suit fit; select the appropriate natural notrump contract.', rule)
    # Subsequent four-card suit exploration. A natural 4NT may be passed.
    last = acts[-1]
    if last.bid in ('3N', '6N', '7N'):
        return _offer(ctx, 'PASS', 'Respect the natural notrump conclusion of Baron.', rule)
    if last.bid == '4N':
        return _offer(ctx, 'PASS', 'Natural 4NT after Baron, no further suit fit to show.', rule)
    if last.strain in tuple(SUITS):
        if h.length(last.strain) >= 4:
            # A raise agrees the fit; subsequent slam decisions belong to the
            # slam module, which has priority over this module.
            if any(c.strain == last.strain for c in acts[1:-1]):
                level = 6 if h.hcp + (f.low if ctx.seat == f.responder else 18) >= 33 else 5 if last.strain in ('C', 'D') else 4
                return _offer(ctx, ctx.cheapest(last.strain, level), 'Complete the Baron auction in the agreed four-card fit.', rule)
            return _offer(ctx, ctx.cheapest(last.strain, last.level + 1), 'Agree partner’s four-card suit; game forcing.', rule)
        shown = [c.strain for c in acts[1:] if c.seat == ctx.seat]
        bid = _four_card(ctx, 3 if f.level == 1 else 4, shown)
        if bid and bid_rank(bid) < bid_rank('4N'):
            return _offer(ctx, bid, 'Continue showing four-card suits in ascending order.', rule)
        return _offer(ctx, ctx.cheapest('N', 4 if f.level == 2 else 3), 'Natural notrump conclusion when no four-card fit is available.', rule)
    return None


def _minor_relay(ctx, f):
    if len(f.actions) == 1:
        return _offer(ctx, '3C', 'Forced acceptance of the minor-suit relay.', '1.1.6', True)
    if len(f.actions) == 2:
        return _offer(ctx, '3D' if ctx.h.length('D') > ctx.h.length('C') else 'PASS', 'Play in responder’s long minor.', '1.1.6')
    return _offer(ctx, 'PASS', 'Respect the weak minor-suit signoff.', '1.1.6')


def _natural_nt(ctx, f):
    """Natural continuations after a balanced rebid (not Stayman/transfers)."""
    h, acts = ctx.h, f.actions
    rule = '1.4.4' if f.mode == 'positive' else '1.2'
    if not acts:
        if f.mode == 'positive':
            five = _longest(h, minimum=5)
            if five:
                return _offer(ctx, ctx.cheapest(five, 3), 'Natural five-card suit after the positive response; this is not a transfer.', rule)
            suit = _four_card(ctx, 3)
            if suit and h.hcp >= 10:
                return _offer(ctx, suit, 'Natural four-card suit, looking for a slam fit after the positive response.', rule)
            return _offer(ctx, ctx.cheapest('N', 4), 'Positive strong-club auction: force to at least 4NT.', rule)
        if h.hcp + f.low >= 37:
            return _offer(ctx, '7N', 'Combined values for a grand slam.', rule)
        if h.hcp + f.low >= 33:
            return _offer(ctx, '6N', 'Combined values for a small slam.', rule)
        if h.hcp + f.high >= 33:
            if f.level >= 4:
                return _offer(ctx, 'PASS', 'The strong notrump rebid already reaches 4NT; insufficient values to commit to slam.', rule)
            return _offer(ctx, '4N', 'Quantitative slam invitation after the natural notrump rebid.', rule)
        opening = next((c for c in f.earlier if c.seat == f.opener and c.is_contract and c.strain in tuple(SUITS) and c.bid != '2C'), None)
        response = next((c for c in f.earlier if c.seat == ctx.seat and c.is_contract), None)
        guaranteed_game = h.hcp + f.low >= 25
        invitational = h.hcp + f.high >= 25
        if opening and opening.strain in ('H', 'S') and h.length(opening.strain) >= 3:
            if guaranteed_game:
                return _offer(ctx, '4' + opening.strain if h.length(opening.strain) >= 4 else ctx.cheapest(opening.strain, 3), 'Support opener’s major; a three-level return is forcing.', rule)
            if f.level == 1:
                return _offer(ctx, '2' + opening.strain, 'Weak preference with three-card support for opener’s major.', rule)
        if response and response.strain in tuple(SUITS):
            suit = response.strain
            if h.length(suit) >= 6:
                level = (4 if suit in 'HS' else 5) if guaranteed_game else 3 if invitational and f.level == 1 else f.level + 1
                return _offer(ctx, ctx.cheapest(suit, level), 'Natural six-card suit: sign off, invite, or bid game according to the notrump range.', rule)
            if guaranteed_game and h.length(suit) >= 5:
                if opening and h.length(opening.strain) >= 3:
                    bid = ctx.cheapest(opening.strain, 3)
                else:
                    others = [s for s in SUITS if s != suit and (not opening or s != opening.strain)]
                    options = [ctx.cheapest(s, 3) for s in others if h.length(s) >= 3]
                    bid = min((b for b in options if b), key=bid_rank, default=None)
                if bid:
                    return _offer(ctx, bid, 'Forcing new-suit continuation asks opener for three-card support for the original five-card major.', rule)
            if not guaranteed_game and not invitational and f.level == 1:
                other = _longest(h, [s for s in SUITS if s != suit and bid_rank('2' + s) < bid_rank('2' + suit)], 4)
                if other:
                    return _offer(ctx, '2' + other, 'Natural weak second suit below a reverse.', rule)
        if guaranteed_game:
            return _offer(ctx, 'PASS' if f.level >= 3 else '3N', 'Place the notrump game.', rule)
        if invitational and f.level == 1:
            return _offer(ctx, '2N', 'Natural invitation opposite the balanced rebid.', rule)
        return _offer(ctx, 'PASS', 'Stop opposite the balanced notrump rebid.', rule)
    last = acts[-1]
    if len(acts) == 1:
        if f.mode == 'positive' and last.strain in tuple(SUITS) and last.level <= 4:
            support = 3 if last.strain in ('H', 'S') and any(c.seat == ctx.partner and c.strain == last.strain for c in f.earlier) else 4
            if h.length(last.strain) >= support:
                return _offer(ctx, ctx.cheapest(last.strain, 4 if last.strain in ('H', 'S') else 5), 'Agree the natural suit after a positive response; do not stop below game.', rule)
            return _offer(ctx, ctx.cheapest('N', 4), 'Natural notrump after the positive response, forcing to at least 4NT.', rule)
        if last.bid in ('2N', '4N'):
            target = '3N' if last.bid == '2N' else '6N'
            # 2C positive auctions commit the partnership to at least 4NT,
            # which is to play unless further values justify a slam.
            if f.mode == 'positive':
                return _offer(ctx, '6N' if h.hcp >= 25 else 'PASS', 'Evaluate the positive response and natural notrump continuation.', rule)
            return _offer(ctx, target if _maximum(ctx, f) else 'PASS', 'Accept the natural quantitative invitation with a maximum.', rule)
        if last.strain in tuple(SUITS) and last.level <= 3:
            previous_response = next((c for c in f.earlier if c.seat == ctx.partner and c.strain in ('H', 'S')), None)
            if last.level == 2:
                return _offer(ctx, 'PASS', 'Natural weak signoff after a notrump rebid.', rule)
            if previous_response and last.strain == previous_response.strain:
                return _offer(ctx, '4' + last.strain if _maximum(ctx, f) else 'PASS', 'Accept responder’s six-card major invitation with a maximum.', rule)
            if previous_response and h.length(previous_response.strain) >= 3:
                return _offer(ctx, ctx.cheapest(previous_response.strain, 3), 'Show three-card support after responder’s forcing continuation.', rule)
            if f.mode == 'positive' and h.length(last.strain) >= 4:
                return _offer(ctx, ctx.cheapest(last.strain, 4), 'Agree the four-card fit after a positive strong-club response.', rule)
            return _offer(ctx, ctx.cheapest('N', 4 if f.mode == 'positive' else 3), 'No major fit for the forcing continuation.', rule)
        return _offer(ctx, 'PASS', 'Respect the natural game or slam signoff.', rule)
    if len(acts) == 2 and f.mode == 'positive' and last.bid == '4N':
        return _offer(ctx, '6N' if h.hcp + f.low >= 33 else 'PASS',
                      'After the positive suit investigation, use the combined minimum strength to select the notrump contract.', rule)
    if len(acts) == 2 and last.strain in ('H', 'S') and last.level == 3:
        original = next((c for c in f.earlier if c.seat == f.opener and c.is_contract), None)
        support = 4 if original and original.strain == last.strain else 5
        return _offer(ctx, '4' + last.strain if h.length(last.strain) >= support else '3N',
                      'Choose the major game only with an eight-card fit; otherwise select 3NT.', rule)
    return None


def _direct_suit(ctx, f):
    """Natural jump responses to NT: strong suits, not weak jump bids."""
    response = f.actions[0]
    h, suit = ctx.h, response.strain
    section = ('1.1.8' if response.level == 4 and suit in 'HS' else '1.1.7') if f.level == 1 else ('1.3.8' if suit in 'HS' else '1.3.7')
    if len(f.actions) == 1:
        if f.level == 1 and response.level == 4 and suit in 'HS':
            return _offer(ctx, 'PASS', 'Natural six-card major game signoff.', section)
        major_slam = f.level == 2 and response.level == 4 and suit in 'HS'
        fit = h.length(suit) >= (2 if major_slam else 3)
        if f.level == 2 and response.level == 4 and suit in 'HS' and not _maximum(ctx, f):
            return _offer(ctx, 'PASS', 'Decline the natural major-suit slam invitation.', section)
        if major_slam:
            if not fit:
                return _offer(ctx, 'PASS', 'Decline the major-suit slam invitation without support.', section)
            controlled = all(h.has(s, 'A') or h.has(s, 'K') or h.length(s) <= 1
                             for s in SUITS if s != suit)
            if controlled and h.keycards(suit) >= 2:
                return _offer(ctx, '4N', 'Accept the major-suit slam invitation with RKCB 0314; the six-card major supplies trumps.', section, True)
        if fit:
            cue = min((ctx.cheapest(s, 4) for s in SUITS if s != suit and h.has(s, 'A')), key=lambda b: bid_rank(b) if b else 100, default=None)
            if cue and bid_rank(cue) < bid_rank('5' + suit):
                return _offer(ctx, cue, 'Ace-showing cue bid with support for responder’s strong suit.', section)
            if major_slam:
                return _offer(ctx, 'PASS', 'No safe slam enquiry or ace cue is available; accept the major game.', section)
            return _offer(ctx, ctx.cheapest(suit, 6 if f.level == 2 and suit in 'CD' else 4 if suit in 'HS' else 5), 'Support responder’s strong suit.', section)
        return _offer(ctx, '4N' if f.level == 2 else '3N', 'Natural notrump without support for responder’s strong suit.', section)
    return None


def choose(ctx):
    decision = _opening(ctx)
    if decision:
        return decision
    f = _frame(ctx.auction, ctx.seat, ctx.profile)
    if f:
        if f.mode != 'system' or f.level > 2:
            return _natural_nt(ctx, f)
        if not f.actions:
            return _initial_response(ctx, f) if ctx.seat == f.responder else None
        response = f.actions[0]
        n = f.level + 1
        if response.bid == str(n) + 'C':
            return _stayman(ctx, f)
        if response.bid in (str(n) + 'D', str(n) + 'H'):
            return _transfer(ctx, f)
        if response.bid == str(n) + 'S':
            return _baron(ctx, f)
        if f.level == 1 and response.bid == '2N':
            return _minor_relay(ctx, f)
        if response.strain in tuple(SUITS) and response.level >= n + 1:
            return _direct_suit(ctx, f)
        if response.bid in ('3N', '6N', '7N'):
            return _offer(ctx, 'PASS', 'Respect responder’s natural notrump signoff.', '1.1' if f.level == 1 else '1.3')
        if f.level == 1 and response.bid == '4N':
            return _offer(ctx, '6N' if _maximum(ctx, f) else 'PASS', 'Accept the direct quantitative slam invitation only with a maximum.', '1.1.5')
        return None
    return _strong(ctx) or _balanced_rebid(ctx)


def _opening_meaning(a, call, profile):
    if a.opening:
        return None
    if call.bid == '1N':
        low, high = profile.get('nt_range', [12, 14])
        return _m('Weak balanced notrump.', '1.1', hcp_min=low, hcp_max=high, balanced=True)
    if call.bid == '2N':
        low, high = profile.get('two_nt_range', [20, 22])
        return _m('Strong balanced notrump; an exceptional singleton ace or king is possible.', '1.3', hcp_min=low, hcp_max=high,
                  min_length={s: 1 for s in SUITS}, max_length={s: 5 for s in SUITS})
    if call.bid == '2C':
        return _m('Strong artificial club: 23+ points or game-forcing playing strength.', '1.4', hcp_min=20, artificial=True, forcing='one-round')
    return None


def _strong_meaning(a, call):
    opening = a.opening
    if not opening or opening.bid != '2C' or opening.seat % 2 != call.seat % 2 or not _quiet(a, call.seat):
        return None
    calls = _side(a, call.seat)
    if len(calls) == 1:
        if call.bid == '2D':
            return _m('Negative waiting response; lacks the agreed positive-response criteria.', '1.4.1', hcp_max=12, artificial=True, forcing='one-round', confidence=.8)
        if call.bid == '2N':
            return _m('Positive balanced hand.', '1.4.1', hcp_min=7, balanced=True, forcing='game')
        if call.strain in tuple(SUITS):
            jump = call.level > (2 if call.strain in ('H', 'S') else 3)
            return _m('Positive natural suit response' + (' with a solid six-card suit.' if jump else '.'), '1.4.1', hcp_min=6, min_length={call.strain: 6 if jump else 5}, suit=call.strain, forcing='game')
    if len(calls) == 2:
        if call.strain == 'N':
            if calls[1].bid == '2D':
                low, high = {2: (23, 24), 3: (25, 27), 4: (28, 30), 6: (31, 34), 7: (35, 37)}.get(call.level, (23, 37))
            else:
                low, high = 23, 37
            return _m('Balanced strong-club rebid.', '1.4.2' if calls[1].bid == '2D' else '1.4.4', hcp_min=low, hcp_max=high, balanced=True, forcing='none' if calls[1].bid == '2D' and call.bid == '2N' else 'game')
        if call.strain in tuple(SUITS):
            support = calls[1].strain == call.strain and calls[1].bid != '2D'
            return _m('Natural game-forcing strong-club rebid.', '1.4.2', min_length={call.strain: 3 if support else 5}, suit=call.strain, forcing='game')
    if len(calls) >= 3 and calls[2].strain in tuple(SUITS) and call.strain in tuple(SUITS):
        support = any(c.seat != call.seat and c.strain == call.strain and c.index > opening.index and c.bid != '2D' for c in calls)
        return _m('Natural continuation in a game-forcing strong-club auction.', '1.4', min_length={call.strain: 3 if support else 5}, suit=call.strain, forcing='game' if call.level < (4 if call.strain in ('H', 'S') else 5) else 'none')
    return None


def _nt_meaning(f, call):
    acts, bid = f.actions, call.bid
    level = f.level
    if f.mode != 'system' or level > 2:
        rule = '1.4.4' if f.mode == 'positive' else '1.2'
        if not acts:
            if bid in ('2N', '4N'):
                threshold = 25 if bid == '2N' else 33
                return _m('Natural quantitative notrump continuation.', rule, hcp_min=max(0, threshold - f.high), hcp_max=max(0, threshold - f.low - 1), forcing='invite')
            if bid == '3N':
                return _m('Natural notrump game.', rule, hcp_min=max(0, 25 - f.high), forcing='signoff')
            if call.strain in tuple(SUITS):
                prior = next((c for c in reversed(f.earlier) if c.seat == call.seat and c.is_contract), None)
                own_suit = prior and prior.strain == call.strain
                opener_suit = next((c.strain for c in f.earlier if c.seat == f.opener and c.is_contract), None)
                support = call.strain == opener_suit
                return _m('Natural suit continuation after a balanced rebid.', rule,
                          min_length={call.strain: 5 if f.mode == 'positive' and own_suit else 3 if support else 6 if own_suit else 3 if call.level >= 3 else 4},
                          forcing='game' if f.mode == 'positive' else 'none' if call.level == 2 else 'invite' if own_suit else 'game', suit=call.strain)
        if call.strain in tuple(SUITS):
            return _m('Natural fit or suit continuation after notrump.', rule, min_length={call.strain: 3}, suit=call.strain)
        if bid == 'PASS':
            return _m('Decline the invitation or respect the natural signoff.', rule)
        return _m('Natural notrump continuation.', rule) if call.strain == 'N' else None
    n = level + 1
    if not acts:
        if bid == str(n) + 'C':
            return _m('Stayman; weak escapes are possible over 1NT.', '1.1.2' if level == 1 else '1.3.3', hcp_min=0 if level == 1 else max(0, 24 - f.low), artificial=True, forcing='one-round')
        if bid in (str(n) + 'D', str(n) + 'H'):
            target = 'H' if call.strain == 'D' else 'S'
            return _m('Transfer to the next major.', '1.1.3' if level == 1 else '1.3.4', min_length={target: 5}, hcp_min=0 if level == 1 else max(0, 24 - f.low), artificial=True, forcing='one-round', suit=target)
        if bid == str(n) + 'S':
            return _m('Two-way Baron game invitation or slam search.' if level == 1 else 'Baron slam search (a good ten points may suffice).', '1.1.5' if level == 1 else '1.3.6', hcp_min=max(0, (25 if level == 1 else 32) - f.high), artificial=True, forcing='one-round')
        if level == 1 and bid == '2N':
            return _m('Weak minor-suit relay; no notrump invitation.', '1.1.6', hcp_max=max(0, 24 - f.high), artificial=True, forcing='one-round')
        if bid in ('3N', '6N', '7N'):
            minimum = {3: 25 if level == 1 else 24, 6: 33, 7: 37}[call.level] - f.low
            return _m('Natural notrump signoff.', '1.1' if level == 1 else '1.3', hcp_min=max(0, minimum), forcing='signoff')
        if call.strain in tuple(SUITS) and call.level >= n + 1:
            signoff = level == 1 and call.level == 4 and call.strain in ('H', 'S')
            return _m('Natural long suit, ' + ('game signoff.' if signoff else 'slam interest.'), ('1.1.8' if signoff else '1.1.7') if level == 1 else ('1.3.8' if call.strain in ('H', 'S') else '1.3.7'), min_length={call.strain: 6}, suit=call.strain, forcing='signoff' if signoff else 'game' if call.strain in ('C', 'D') or level == 1 else 'invite')
        if bid == 'PASS':
            return _m('Insufficient game-invitational values.', '1.1' if level == 1 else '1.3', hcp_max=max(0, (24 - f.high) if level == 1 else (23 - f.low)))
        if level == 1 and bid == '4N':
            return _m('Direct quantitative slam invitation; Baron is the preferred route in this partnership.', '1.1.5',
                      hcp_min=max(0, 32 - f.low), hcp_max=max(0, 33 - f.low), forcing='invite')
        # Direct 2NT–4NT belongs to the ace-asking module. Unknown initial
        # responses remain uninformative rather than indexing an empty list.
        return None
    first = acts[0]
    if first.bid == str(n) + 'C':
        rule = '1.1.2' if level == 1 else '1.3.3'
        if len(acts) == 1:
            if call.strain == 'D':
                return _m('Stayman denies four cards in either major.', rule, max_length={'H': 3, 'S': 3}, artificial=True)
            if call.strain in ('H', 'S'):
                return _m('Stayman shows a four-card major.', rule, min_length={call.strain: 4}, max_length={'H': 3} if call.strain == 'S' else {}, suit=call.strain)
        if len(acts) == 2:
            response = acts[1]
            if level == 1 and bid == '3C':
                return _m('Weak long clubs after Stayman.', rule, hcp_max=max(0, 24 - f.high), min_length={'C': 6}, suit='C')
            if response.strain == 'D' and call.strain in ('H', 'S'):
                return _m('Five-card major plus four cards in the other major.', rule, min_length={call.strain: 5, 'H' if call.strain == 'S' else 'S': 4}, hcp_max=max(0, 24 - f.high) if call.level == 2 else 37, hcp_min=max(0, 25 - f.low) if call.level >= 3 else 0, forcing='game' if call.level >= 3 else 'none', suit=call.strain)
            if call.strain == response.strain and call.strain in ('H', 'S'):
                return _m('Raise the four-card major fit.', rule, min_length={call.strain: 4}, hcp_min=max(0, 25 - f.high) if call.level == 3 else max(0, (25 if level == 1 else 24) - f.low), forcing='invite' if call.level == 3 else 'signoff', suit=call.strain)
            if bid in ('2N', '3N', '4N'):
                threshold = 33 if bid == '4N' else 25
                return _m('Natural notrump continuation after Stayman; 4NT is quantitative.', rule, hcp_min=max(0, threshold - (f.low if bid == '3N' else f.high)), forcing='invite' if bid != '3N' else 'signoff')
        if len(acts) == 3 and call.strain in ('H', 'S'):
            return _m('Major fit located by Stayman.', rule, min_length={call.strain: 3 if acts[1].strain == 'D' else 4}, suit=call.strain)
        return _m('Natural continuation of the Stayman auction.', rule)
    if first.bid in (str(n) + 'D', str(n) + 'H'):
        target = 'H' if first.strain == 'D' else 'S'
        rule = ('1.1.3' if target == 'H' else '1.1.4') if level == 1 else ('1.3.4' if target == 'H' else '1.3.5')
        if len(acts) == 1 and call.strain == target:
            broken = call.level > n
            return _m('Transfer break with four-card support and a maximum.' if broken else 'Forced transfer acceptance.', rule, min_length={target: 4} if broken else {}, hcp_min=f.high if broken else 0, artificial=not broken, suit=target)
        if len(acts) == 2:
            if bid == 'PASS':
                return _m('Weak transfer signoff.', rule, hcp_max=max(0, 24 - f.high), min_length={target: 5}, suit=target)
            if bid == '2S' and target == 'H':
                return _m('Five hearts and four spades, invitational or stronger.', rule, hcp_min=max(0, 25 - f.high), min_length={'H': 5, 'S': 4}, forcing='one-round', suit='S')
            if call.strain == target:
                return _m('Six-card major invitation or game signoff.', rule, min_length={target: 6}, hcp_min=max(0, 25 - f.high), forcing='invite' if call.level == 3 else 'signoff', suit=target)
            if bid in ('2N', '3N', '4N', '6N'):
                threshold = 33 if bid in ('4N', '6N') else 25
                low = threshold - (f.low if bid in ('3N', '6N') else f.high)
                return _m('Natural notrump rebid with exactly five cards in the transferred major; 4NT is quantitative.', rule, hcp_min=max(0, low), min_length={target: 5}, max_length={target: 5}, forcing='invite' if bid in ('2N', '4N') else 'signoff')
            if call.strain in tuple(SUITS):
                return _m('Natural second suit after the transfer, forcing to game.', rule, hcp_min=max(0, 25 - f.low), min_length={target: 5, call.strain: 4}, forcing='game', suit=call.strain)
        if len(acts) == 3:
            if call.strain == target:
                minimum = 2 if acts[2].bid == '3' + target else 3
                return _m('Support for the transferred major; two cards suffice opposite a six-card invitation.', rule, min_length={target: minimum}, suit=target)
            if bid in ('PASS', '3N') and acts[2].bid in ('2N', '3N'):
                return _m('Natural notrump without three-card major support.', rule, max_length={target: 2})
        return _m('Natural continuation after the transfer.', rule)
    if first.bid == str(n) + 'S':
        rule = '1.1.5' if level == 1 else '1.3.6'
        if len(acts) == 1:
            if call.strain == 'N':
                return _m('Minimum notrump hand in response to Baron.', rule, hcp_min=f.low, hcp_max=f.high - 1, artificial=True)
            if call.strain in tuple(SUITS):
                earlier_suits = [s for s in 'CDHS' if 'CDHS'.index(s) < 'CDHS'.index(call.strain)]
                return _m('Maximum notrump hand showing the cheapest four-card suit.', rule, hcp_min=f.high, hcp_max=f.high, min_length={call.strain: 4}, max_length={s: 3 for s in earlier_suits}, suit=call.strain)
        if len(acts) == 2 and _baron_jump_cue(acts[1], call):
            trump = acts[1].strain
            return _m('Jump cue bid: agree opener’s four-card suit and show an ace.', rule,
                      min_length={trump: 4}, honours={call.strain: 'A'},
                      suit=trump, artificial=True, forcing='game')
        if call.strain in tuple(SUITS):
            return _m('Four-card suit or fit in the Baron investigation.', rule, min_length={call.strain: 4}, suit=call.strain, forcing='game')
        if bid == '4N':
            return _m('Natural 4NT after Baron, may be passed.', rule)
        return _m('Natural notrump conclusion or signoff after Baron.', rule)
    if level == 1 and first.bid == '2N':
        if len(acts) == 1:
            return _m('Forced club relay, no club holding promised.', '1.1.6', artificial=True)
        if len(acts) == 2:
            suit = 'D' if bid == '3D' else 'C'
            return _m('Weak signoff in the long minor.', '1.1.6', hcp_max=max(0, 24 - f.high), min_length={suit: 6}, suit=suit)
        return _m('Respect the weak minor signoff.', '1.1.6')
    if first.strain in tuple(SUITS) and first.level >= n + 1:
        section = ('1.1.8' if first.level == 4 and first.strain in ('H', 'S') else '1.1.7') if level == 1 else ('1.3.8' if first.strain in ('H', 'S') else '1.3.7')
        if call.strain in tuple(SUITS) and call.strain != first.strain:
            support = 2 if level == 2 and first.strain in ('H', 'S') else 3
            return _m('Ace-showing cue bid with support for the strong suit.', section, min_length={first.strain: support}, honours={call.strain: 'A'}, suit=first.strain, artificial=True, forcing='game')
        if call.strain == 'N':
            if level == 2 and first.strain in ('H', 'S') and bid == '4N':
                return None  # A1.3.8: ace/keycard enquiry, owned by slam.
            return _m('Natural notrump, denying support for the long suit.', section, max_length={first.strain: 2})
        return _m('Natural continuation after the strong suit response.', section)
    return None


def interpret(auction, call, profile):
    """Describe a call using its auction prefix; never inspect a hidden hand."""
    result = _opening_meaning(auction, call, profile)
    if result:
        return result
    f = _frame(auction, call.seat, profile)
    if f:
        return _nt_meaning(f, call)
    result = _strong_meaning(auction, call)
    if result:
        return result
    # A one-suit opener's first balanced rebid establishes a new natural frame.
    ours = _side(auction, call.seat)
    if len(ours) == 2 and _quiet(auction, call.seat) and ours[0].seat == call.seat and ours[0].level == 1 and ours[0].strain in tuple(SUITS) and call.strain == 'N':
        low, high = _rebid_range(ours[0], ours[1], call)
        shape = None if call.bid == '3N' and ours[0].strain in ('C', 'D') else True
        return _m('Natural Acol rebid; the range allows a stronger long-minor jump to 3NT.', '1.2', hcp_min=low, hcp_max=high, balanced=shape)
    return None
