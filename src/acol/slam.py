"""Modern Acol A2.8 controls, with the partnership's RKCB 0314 override.

The EBU card describes ordinary Blackwood.  The following are our explicit
partnership extensions, not quotations from that card: 0314 keycard replies;
the cheapest available non-trump suit that leaves five of trumps available
asks for the trump queen; a negative
answer returns to trumps and a positive answer shows the cheapest side king,
or six of trumps without one.  5NT after RKCB confirms all five keycards and
the trump queen and asks for a specific side king (cheapest first).
Direct 2NT--4NT remains an ace enquiry because Baron supplies the quantitative
route. Without an agreed trump, our 0314 variant counts four aces only:
5C=0/3, 5D=1/4 and 5H=2. There is no trump-queen enquiry in this context.
In this ace-only branch 5NT retains the EBU king-count enquiry, with the
ordinary 6C=0/4, 6D=1, 6H=2, 6S=3 king steps. It is never a natural signoff.
Robot callers must avoid the ace enquiry without a safe slam continuation.
"""

from .core import Auction, Call, Context, Decision, Meaning, SUITS, bid_rank


GAME = {"C": 5, "D": 5, "H": 4, "S": 4, "N": 3}


def _team(a, seat):
    return [c for c in a.calls if c.seat % 2 == seat % 2 and c.is_contract]


def agreed_trump(a, seat):
    """An explicit natural raise, not a same-player rebid or a transfer reply.

    Cue bids in an opponent's original suit are never evidence of agreement.
    For NT auctions a transfer completion becomes agreement only when the
    transferring player subsequently raises the suit.
    """
    from . import notrump
    team = _team(a, seat)
    nt_meanings = {c.index: notrump.interpret(a.prefix(c.index), c, {}) if c.strain != "N" else None
                   for c in a.contract_calls()}
    opponents = set()
    for c in a.contract_calls():
        if c.seat % 2 == seat % 2 or c.strain == "N":
            continue
        m = nt_meanings[c.index]
        if m and m.artificial:
            # A transfer shows its target, not the denomination printed on
            # the transfer card. Stayman/Baron/relay requests show no suit.
            opponents.update(s for s, n in m.min_length.items() if n >= 4)
        else:
            opponents.add(c.strain)
    promises = {seat % 2: {}, seat % 2 + 2: {}}
    fit = None
    for i, c in enumerate(team):
        m = nt_meanings[c.index]
        if m:
            support = m.min_length.get(c.strain, 0)
            partner_length = promises[(c.seat + 2) % 4].get(c.strain, 0)
            if not m.artificial and m.suit == c.strain and c.strain in SUITS and \
                    c.strain not in opponents and support >= 3 and support + partner_length >= 8 and \
                    (not fit or fit == c.strain or c.level < 4):
                # Opener can agree the transferred major without responder
                # ever printing that suit. A forced acceptance has no length
                # promise and cannot satisfy this condition prematurely.
                fit = c.strain
            for suit, length in m.min_length.items():
                promises[c.seat][suit] = max(promises[c.seat].get(suit, 0), length)
            if i and c.bid in ("4H", "4S") and support >= 6 and team[i - 1].bid == "2N" and \
                    team[i - 1].seat != c.seat and _ace_route(a, team[i - 1]):
                # A1.3.8: direct four of a major over 2NT names the trump
                # suit for a subsequent Blackwood/RKCB enquiry. The balanced
                # bidder has at least two cards opposite the promised six.
                fit = c.strain
        # A Baron jump cue agrees opener's just-shown four-card suit. The
        # NT module supplies the precise ace promise for the cue itself.
        nt_before = [p for p in team[:i] if p.strain == "N" and p.level <= 2]
        if i >= 2 and nt_before and c.strain != "N":
            nt = nt_before[-1]
            after_nt = [p for p in team[:i] if p.index > nt.index]
            previous = team[i - 1]
            baron = "2S" if nt.bid == "1N" else "3S"
            if after_nt and after_nt[0].bid == baron and c.seat != nt.seat and \
                    previous.seat == nt.seat and previous.strain in SUITS and c.strain != previous.strain:
                minimum_level = previous.level + (1 if "CDHS".index(c.strain) <= "CDHS".index(previous.strain) else 0)
                if c.level > minimum_level:
                    fit = previous.strain
                    continue
        if c.strain == "N" or c.strain in opponents:
            continue
        earlier = [p for p in team[:i] if p.strain == c.strain and p.seat != c.seat]
        if not earlier:
            continue
        # 2C strong opening/Stayman and transfer calls are not natural suits.
        prior = earlier[-1]
        prior_meaning = nt_meanings[prior.index]
        if prior_meaning and prior_meaning.artificial and prior_meaning.suit != prior.strain:
            # Stayman's denial, Baron and minor-relay steps carry no natural
            # length in the denomination printed on the bidding box.
            continue
        if prior.bid == "2C" and (prior == a.opening or
                any(p.strain == "N" and p.level <= 2 for p in team[:i])):
            continue
        if any(p.strain == "N" and p.level <= 2 for p in team[:i]):
            nt = next(p for p in reversed(team[:i]) if p.strain == "N" and p.level <= 2)
            if prior.index < nt.index and c.level <= 3:
                # A three-card preference after a natural NT rebid does not
                # establish an eight-card fit in a four-card opening suit.
                continue
            # The prior-call meaning above distinguishes actual transfers
            # from natural suits after Baron or a positive strong-2C reply.
            # The printed denomination alone cannot make that distinction.
        # A new suit above an existing fit is a control, not a new fit.
        if fit and c.level >= 4 and c.strain != fit:
            continue
        fit = c.strain
    return fit


def _rkcb(a, seat):
    """Find the most recent genuine RKCB request and its partnership replies."""
    for call in reversed(_team(a, seat)):
        if call.bid != "4N":
            continue
        prefix = a.prefix(call.index)
        trump = agreed_trump(prefix, seat)
        previous = _team(prefix, seat)
        if not trump or (previous and previous[-1].strain == "N"):
            continue
        replies = [c for c in _team(a, seat) if c.index > call.index]
        return call, trump, replies
    return None


def _ace_only(a, seat):
    """Direct 4NT response to 2NT, including the strong-2C rebid route."""
    team = _team(a, seat)
    for index, call in enumerate(team):
        if call.bid != "4N" or index == 0:
            continue
        previous = team[index - 1]
        if previous.bid != "2N" or previous.seat == call.seat or not _ace_route(a, previous):
            continue
        # The first action after the 2NT bid must be this direct enquiry.
        if agreed_trump(a.prefix(call.index), seat):
            continue
        return call, team[index + 1:]
    return None


def _ace_only_ask(a, call):
    team = _team(a, call.seat)
    return bool(call.bid == "4N" and team and team[-1].bid == "2N" and
                team[-1].seat != call.seat and _ace_route(a, team[-1]) and
                not agreed_trump(a, call.seat))


def _ace_route(a, two_nt):
    before = _team(a.prefix(two_nt.index), two_nt.seat)
    # A natural 2NT rebid after a one-level suit opening is quantitative.
    return not before or (before[0].bid == "2C" and len(before) == 2 and before[1].bid == "2D")


def _queen_ask(a, response, trump):
    for level in (5, 6):
        for suit in "CDHS":
            bid = f"{level}{suit}"
            if suit != trump and bid_rank(bid) > bid_rank(response.bid) and \
                    bid_rank(bid) < bid_rank(f"5{trump}"):
                return bid
    return None


def _control(hand, suit, first=False):
    if hand.has(suit, "A") or hand.length(suit) == 0:
        return True
    return not first and (hand.has(suit, "K") or hand.length(suit) == 1)


def _response_count(bid):
    return {"5C": (0, 3), "5D": (1, 4), "5H": (2,), "5S": (2,)}.get(bid)


def _meaning(text, rule, **kw):
    return Meaning(description=text, rule=rule, **kw)


def interpret(auction, call, profile=None):
    """Interpret slam calls using only the auction visible before the call."""
    ace_only = _ace_only(auction, call.seat)
    if _ace_only_ask(auction, call):
        return _meaning("Direct 2NT--4NT ace enquiry; 0314 steps count aces only",
                        "extension.aces.ask", artificial=True, forcing="one-round")
    if ace_only:
        ask, replies = ace_only
        if not replies and call.seat != ask.seat and call.bid in ("5C", "5D", "5H"):
            return _meaning("0314 ace-only response (no trump king)", "extension.aces.response",
                            artificial=True, forcing="one-round", aces=_response_count(call.bid))
        if call.bid == "5N" and len(replies) == 1 and call.seat == ask.seat:
            return _meaning("All four aces; ask for kings using ordinary count steps",
                            "extension.aces.kings", artificial=True, forcing="one-round")
        if len(replies) == 2 and replies[1].bid == "5N" and call.seat != ask.seat:
            return _meaning("King count: 6C zero/four, 6D one, 6H two, 6S three",
                            "extension.aces.king-reply", artificial=True, forcing="one-round",
                            kings={"6C": (0, 4), "6D": (1,), "6H": (2,), "6S": (3,)}.get(call.bid))
        return _meaning("Place the no-trump contract after ace enquiry", "extension.aces.place",
                        forcing="signoff") if call.is_contract else None
    trump = agreed_trump(auction, call.seat)
    chain = _rkcb(auction, call.seat)
    if chain:
        ask, trump, replies = chain
        if not replies and call.seat != ask.seat:
            count = _response_count(call.bid)
            if count:
                queen = None if call.bid in ("5C", "5D") else call.bid == "5S"
                return _meaning(f"RKCB 0314: {' or '.join(map(str, count))} keycards" +
                    ("; trump queen" if queen else "; no trump queen" if queen is False else ""),
                    "extension.rkcb.response", artificial=True, suit=trump,
                    keycards=count, queen=queen, forcing="one-round")
        if len(replies) == 1 and call.seat == ask.seat:
            if call.bid == "5N":
                return _meaning("All five keycards and the trump queen; asks for a side king",
                    "extension.rkcb.kings", artificial=True, suit=trump, forcing="game")
            if call.bid == _queen_ask(auction, replies[0], trump):
                return _meaning("Asks for the trump queen", "extension.rkcb.queen-ask",
                    artificial=True, suit=trump, forcing="one-round")
            if call.is_contract and call.strain == trump:
                return _meaning("Place the contract after keycard reply", "extension.rkcb.place",
                                suit=trump, forcing="signoff")
        if len(replies) == 2 and call.seat != ask.seat:
            followup = replies[1]
            if followup.bid == "5N":
                if call.is_contract and call.level >= 6:
                    return _meaning("No available side king" if call.strain == trump else
                        f"Specific king of {call.strain}", "extension.rkcb.king-reply",
                        artificial=call.strain != trump, suit=trump, forcing="one-round",
                        honours={} if call.strain == trump else {call.strain: "K"})
            if followup.bid == _queen_ask(auction, replies[0], trump):
                if call.is_contract and call.level >= 5:
                    # Six of trumps is the positive, no-side-king response; the
                    # cheapest return to trumps below six denies the queen.
                    queen = not (call.strain == trump and call.level == 5)
                    return _meaning("Trump queen" if queen else "No trump queen",
                        "extension.rkcb.queen-reply", queen=queen, suit=trump,
                        artificial=call.strain != trump, forcing="one-round",
                        honours={} if call.strain == trump else {call.strain: "K"})
        return None

    if call.bid == "4N" and trump:
        team = _team(auction, call.seat)
        if team and team[-1].strain != "N":
            return _meaning("RKCB 0314: asks for the five keycards", "extension.rkcb.ask",
                            artificial=True, suit=trump, forcing="one-round")
    team = _team(auction, call.seat)
    if trump and team:
        if team[-1].bid == "5N" and team[-1].seat != call.seat:
            if call.bid in ("6C", "6D", "6H", f"7{trump}"):
                return _meaning("Grand slam force: trump top-honour response", "A2.8.5.response",
                                artificial=call.level < 7, suit=trump, forcing="one-round")
        if call.bid == "5N":
            return _meaning("Grand slam force: asks about trump A, K and Q", "A2.8.5.ask",
                            artificial=True, suit=trump, forcing="one-round")
        if call.is_contract and call.strain not in (trump, "N") and \
                bid_rank(call.bid) > bid_rank(f"{GAME[trump] - 1}{trump}"):
            return _meaning(f"Control in {call.strain}; slam interest with {trump} agreed",
                            "A2.8.3.control", artificial=True, suit=trump,
                            forcing="one-round", controls={call.strain: 2})
    return None


def _pick(ctx, bid, text, rule, alert=False):
    return ctx.choose(bid, text, rule, alert=alert)


def choose(ctx):
    a, h = ctx.auction, ctx.h
    ace_only = _ace_only(a, ctx.seat)
    if ace_only:
        ask, replies = ace_only
        aces = sum(h.has(s, "A") for s in SUITS)
        if not replies and ctx.seat != ask.seat:
            response = "5C" if aces in (0, 3) else "5D" if aces in (1, 4) else "5H"
            return _pick(ctx, response, f"0314 ace enquiry: {aces} aces; no trump king",
                         "extension.aces.response", True)
        if len(replies) == 1 and ctx.seat == ask.seat:
            counts = _response_count(replies[0].bid)
            if not counts:
                return None
            possible = [n for n in counts if n + aces <= 4]
            total = aces + min(possible or [0])
            if total == 4 and h.hcp >= 15:
                return _pick(ctx, "5N", "All four aces; ask for kings before considering a grand slam",
                             "extension.aces.kings", True)
            return _pick(ctx, "6N", "Place the small slam after the ace enquiry", "extension.aces.place")
        if len(replies) == 2 and replies[1].bid == "5N" and ctx.seat != ask.seat:
            kings = sum(h.has(s, "K") for s in SUITS)
            bid = ("6C", "6D", "6H", "6S", "6C")[kings]
            return _pick(ctx, bid, f"Ordinary king-count response: {kings} kings",
                         "extension.aces.king-reply", True)
        if len(replies) == 3 and ctx.seat == ask.seat:
            return _pick(ctx, "7N" if h.hcp >= 17 else "6N",
                         "Place the no-trump slam after the king enquiry", "extension.aces.place")
        if len(replies) >= 2:
            return _pick(ctx, "PASS", "Accept partner's no-trump placement", "extension.aces.place")
        return None
    trump = agreed_trump(a, ctx.seat)
    chain = _rkcb(a, ctx.seat)
    if chain:
        ask, trump, replies = chain
        # Interference consumes steps; do not invent an unagreed DOPI/ROPI.
        if any(c.seat % 2 != ctx.seat % 2 and c.bid != "PASS"
               for c in a.calls[ask.index + 1:]):
            return None
        if not replies and ctx.seat != ask.seat:
            keys = h.keycards(trump)
            response = "5C" if keys in (0, 3) else "5D" if keys in (1, 4) else \
                       "5S" if h.has(trump, "Q") else "5H"
            return _pick(ctx, response, f"RKCB 0314: {keys} keycards" +
                (" with the trump queen" if keys == 2 and h.has(trump, "Q") else
                 " without the trump queen" if keys == 2 else ""),
                "extension.rkcb.response", True)
        if len(replies) == 1 and ctx.seat == ask.seat:
            counts = _response_count(replies[0].bid)
            if not counts:
                return None
            possible = [n for n in counts if n + h.keycards(trump) <= 5]
            # Choose the lower feasible interpretation: do not guess three
            # keycards from an ambiguous zero/three response.
            total = h.keycards(trump) + min(possible or [0])
            queen = h.has(trump, "Q") or replies[0].bid == "5S"
            if total < 4:
                bid = ctx.cheapest(trump, 5)
                return _pick(ctx, bid, "Two or more keycards may be missing; stop in trumps",
                             "extension.rkcb.signoff") if bid else None
            if not queen and replies[0].bid in ("5C", "5D"):
                query = _queen_ask(a, replies[0], trump)
                if query:
                    return _pick(ctx, query, "Ask for the trump queen before placing the slam",
                                 "extension.rkcb.queen-ask", True)
            if total == 5 and queen and h.hcp >= 22 and "5N" in ctx.legal:
                return _pick(ctx, "5N", "All keycards and trump queen; ask for specific kings",
                             "extension.rkcb.kings", True)
            return _pick(ctx, f"6{trump}", "Place the small slam with sufficient keycards",
                         "extension.rkcb.place")
        if len(replies) == 2 and ctx.seat != ask.seat:
            question = replies[1]
            if question.bid == "5N":
                candidates = [f"6{s}" for s in "CDHS" if s != trump and h.has(s, "K")
                              and bid_rank(f"6{s}") < bid_rank(f"6{trump}")]
                return _pick(ctx, candidates[0] if candidates else f"6{trump}",
                             "Show the cheapest available side king, or return to trumps",
                             "extension.rkcb.king-reply", True)
            if question.bid == _queen_ask(a, replies[0], trump):
                if not h.has(trump, "Q"):
                    bid = ctx.cheapest(trump, 5)
                    return _pick(ctx, bid, "Deny the trump queen", "extension.rkcb.queen-reply",
                                 True) if bid else None
                candidates = [f"{level}{s}" for level in (5, 6) for s in "CDHS"
                              if s != trump and h.has(s, "K") and
                              bid_rank(f"{level}{s}") > bid_rank(question.bid) and
                              bid_rank(f"{level}{s}") < bid_rank(f"6{trump}")]
                return _pick(ctx, candidates[0] if candidates else f"6{trump}",
                             "Trump queen; show a side king if available",
                             "extension.rkcb.queen-reply", True)
        if len(replies) >= 3 and ctx.seat == ask.seat:
            last = replies[-1]
            if last.strain == trump and last.level >= 6:
                return _pick(ctx, "PASS", "Partner has placed the slam", "extension.rkcb.finish")
            level = 5 if last.strain == trump and last.level == 5 else 6
            if replies[1].bid == "5N" and last.strain != trump and h.hcp >= 25:
                level = 7
            bid = f"{level}{trump}"
            return _pick(ctx, bid, "Place the contract after the slam enquiry",
                         "extension.rkcb.finish") or _pick(ctx, "PASS", "Accept the contract",
                         "extension.rkcb.finish")
        return None

    if not trump:
        return None
    team = _team(a, ctx.seat)
    if not team or team[-1].seat == ctx.seat:
        return None
    last = team[-1]
    if last.bid == "5N":
        count = sum(h.has(trump, r) for r in "AKQ")
        bid = f"7{trump}" if count == 3 else ("6C", "6D", "6H")[count]
        return _pick(ctx, bid, f"Grand slam force: {count} of the three top trump honours",
                     "A2.8.5.response", count < 3)
    if len(team) >= 2 and team[-2].bid == "5N" and team[-2].seat == ctx.seat:
        count = {"6C": 0, "6D": 1, "6H": 2}.get(last.bid, 3 if last.level == 7 else 0)
        ours = sum(h.has(trump, r) for r in "AKQ")
        return _pick(ctx, f"{7 if count + ours >= 3 else 6}{trump}",
                     "Place the contract after the grand slam force", "A2.8.5.place") or \
               _pick(ctx, "PASS", "Accept partner's grand slam", "A2.8.5.place")
    if last.strain == trump and last.level > GAME[trump]:
        return _pick(ctx, "PASS", "Accept partner's return to trumps", "A2.8.4.accept-signoff")
    if last.strain == trump and last.level == GAME[trump] and len(team) >= 2 and \
            team[-2].strain not in (trump, "N") and team[-2].level >= 4:
        return _pick(ctx, "PASS", "Partner declined the control-bidding invitation",
                     "A2.8.4.accept-signoff")
    if last.level >= 6 or last.strain == "N":
        return None
    partner_control = last.strain not in (trump, "N") and last.level >= 4
    # A limit raise needs roughly 19 support points before opener seeks slam;
    # a game-forcing raise or a partner control justifies lower requirements.
    invitation = last.strain == trump and last.level >= 3
    # A direct game raise may be weak and distributional; it is not a limit
    # raise. A prior natural two-level response supplies additional values.
    responder_calls = [c for c in team if c.seat == ctx.partner]
    threshold = 24 if last.strain == trump and last.level == GAME[trump] and \
        len(responder_calls) == 1 else 19
    if not partner_control and not (invitation and h.support_points(trump) >= threshold):
        return None
    if partner_control and h.support_points(trump) < 15:
        bid = ctx.cheapest(trump, GAME[trump])
        return _pick(ctx, bid, "Minimum hand; decline further slam exploration",
                     "A2.8.4.signoff") if bid else None
    # Ask for keycards only after every side suit is controlled.  In particular
    # an unguarded small doubleton is a reason to cue rather than ask.
    shown = {c.strain for c in team if c.level >= 4 and c.strain not in (trump, "N")}
    safe = all(_control(h, s) or s in shown for s in SUITS if s != trump)
    if safe and h.keycards(trump) >= 2 and "4N" in ctx.legal:
        return _pick(ctx, "4N", "Side suits controlled; ask for keycards with agreed trumps",
                     "extension.rkcb.ask", True)
    partner_suits = {c.strain for c in team if c.seat == ctx.partner and c.level < 4}
    for first in (True, False):
        for bid in sorted(ctx.legal, key=lambda b: bid_rank(b) if b[0].isdigit() else 1000):
            if len(bid) != 2 or not bid[0].isdigit() or bid[1] not in SUITS:
                continue
            suit = bid[1]
            if suit == trump or suit in shown or int(bid[0]) > 5 or \
                    bid_rank(bid) <= bid_rank(f"{GAME[trump] - 1}{trump}") or \
                    bid_rank(bid) >= bid_rank(f"{GAME[trump] + 1}{trump}"):
                continue
            if suit in partner_suits and h.length(suit) <= 1 and not partner_control:
                continue
            if _control(h, suit, first):
                return _pick(ctx, bid, f"Show a {'first' if first else 'second'} round {suit} control",
                             "A2.8.4.control", True)
    bid = ctx.cheapest(trump, GAME[trump])
    return _pick(ctx, bid, "No further safe control to show; sign off in trumps",
                 "A2.8.4.signoff") if bid else None
