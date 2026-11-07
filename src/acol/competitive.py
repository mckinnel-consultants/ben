"""Modern Acol sections B and C: intervention and defensive bidding.

Rules use public auction history and the acting hand only.  Opponent-specific
artificial methods can be declared in profile['opponents']; they are never
inferred merely from an unusually short holding in an opponent's hidden hand.
"""

from .core import Auction, Call, Context, Decision, Meaning, SUITS, bid_rank


GAME = {"C": 5, "D": 5, "H": 4, "S": 4, "N": 3}
ORDER = "CDHS"


def _m(description, rule, **kwargs):
    return Meaning(description=description, rule=rule, **kwargs)


def _actions(a, seat):
    return [c for c in a.calls if c.seat % 2 == seat % 2 and c.bid != "PASS"]


def _opponents(a, seat):
    return [c for c in a.calls if c.seat % 2 != seat % 2 and c.is_contract]


def _protective(a, first):
    o = a.opening
    return bool(o and first.index == o.index + 3 and
                all(c.bid == "PASS" for c in a.calls[o.index + 1:first.index]))


def _last(a, seat):
    calls = [c for c in a.calls if c.seat == seat and c.bid != "PASS"]
    return calls[-1] if calls else None


def _minimum(a, suit):
    bids = [b for b in a.legal_bids() if len(b) == 2 and b[0].isdigit() and b[1] == suit]
    return min(bids, key=bid_rank) if bids else None


def _jump(a, bid):
    if len(bid) != 2 or not bid[0].isdigit():
        return 0
    minimum = _minimum(a, bid[1])
    return int(bid[0]) - int(minimum[0]) if minimum else 0


def _two_suits(a, call):
    """Known suits, or [other major] when Michaels leaves the minor unknown."""
    o = a.opening
    if not o or o.strain == "N" or o.level != 1 or call.seat % 2 == o.seat % 2:
        return None
    if any(c.is_contract for c in a.calls[o.index + 1:call.index]):
        return None
    if call.bid == "2N" and not _protective(a, call):
        return [s for s in ORDER if s != o.strain][:2]
    if call.bid == f"2{o.strain}":
        return ["H", "S"] if o.strain in "CD" else ["S" if o.strain == "H" else "H"]
    return None


def _artificial(a, call, profile):
    if not call or not call.is_contract:
        return None
    methods = (profile or {}).get("opponents", {})
    methods = methods if isinstance(methods, dict) else {}
    specified = methods.get("artificial_bids", {}).get(call.bid)
    if specified:
        return specified
    known = _two_suits(a, call)
    if known:
        return {"suits": known, "kind": "two-suited"}
    o = a.opening
    if o and o.bid == "1N":
        if call.seat % 2 != o.seat % 2 and call.bid == "2C":
            return {"suits": ["H", "S"], "kind": "Landy"}
        if call.seat == (o.seat + 2) % 4:
            if call.bid in ("2D", "2H"):
                return {"suits": ["H" if call.bid == "2D" else "S"], "kind": "transfer"}
            if call.bid == "2C":
                return {"suits": [], "kind": "Stayman"}
    return None


def _shape(hand, suits, n=3):
    return all(hand.length(s) >= n for s in suits)


def _quality(hand, suit):
    return sum(hand.has(suit, rank) for rank in "AKQJT")


def _best(hand, suits=SUITS):
    return sorted(suits, key=lambda s: (hand.length(s), s in "HS", _quality(hand, s), ORDER.index(s)),
                  reverse=True)


def _stopped(hand, suits):
    return all(hand.stopper(s) for s in suits if s != "N")


def _penalty_mode(a, seat, profile):
    own = _actions(a, seat)
    if any(c.bid == "XX" for c in own):
        return True
    if a.opening and a.opening.bid == "1N":
        for c in own:
            if c.bid == "X":
                before = a.prefix(c.index)
                if before.last_contract and (before.last_contract.bid == "1N" or
                        _artificial(before, before.last_contract, profile)):
                    return True
    return False


def _scene(a, seat, profile):
    o = a.opening
    if not o:
        return None
    partner = (seat + 2) % 4
    own = _actions(a, seat)
    other = _opponents(a, seat)
    mine = [c for c in own if c.seat == seat]
    partners = [c for c in own if c.seat == partner]
    if _penalty_mode(a, seat, profile):
        return "penalty"
    # First response to intervention over our opening.
    if o.seat % 2 == seat % 2:
        after = [c for c in a.calls[o.index + 1:] if c.seat % 2 != seat % 2 and c.bid != "PASS"]
        if not after:
            return None
        if o.seat == partner and not mine:
            return "nt-intervention" if o.strain == "N" else "our-opening-intervention"
        if o.seat == seat and partners and partners[-1].bid == "X":
            return "negative-rebid"
        if o.seat == seat and other and not partners and len(mine) == 1:
            # A pass by responder may conceal a penalty hand.
            last = other[-1]
            if len(a.calls) >= last.index + 3 and all(c.bid == "PASS" for c in a.calls[last.index + 1:]):
                return "reopen"
        if o.seat == seat and partners and partners[-1].bid == "2N" and \
                any(c.bid == "X" for c in after) and len(partners) == 1:
            return "support-2nt-rebid"
        # Natural rebids remain with the natural module.
        return None
    # We are the defending/overcalling side.
    if not own:
        return "defence"
    first = own[0]
    if first.bid == "X":
        if not mine and first.seat == partner:
            return "double-advance"
        if first.seat == seat and partners and len(mine) == 1:
            return "double-rebid"
        if first.seat == partner and mine and partners[-1].is_contract and \
                len(mine) == 1 and mine[0].is_contract and mine[0].strain == o.strain:
            return "double-cue-place"
        if first.seat == partner and mine and partners[-1].bid == "X":
            return None
    if first.is_contract:
        known = _two_suits(a, first)
        landy = o.bid == "1N" and first.bid == "2C"
        if known or landy:
            if first.seat == partner and not mine:
                return "two-suit-advance"
            if first.seat == seat and partners and len(mine) == 1:
                return "two-suit-rebid"
            if first.seat == partner and len(mine) == 1 and mine[-1].bid in ("2D", "2N") and \
                    len(partners) >= 2:
                return "two-suit-place"
        elif first.strain != "N":
            if first.seat == partner and not mine:
                return "overcall-advance"
            if first.seat == seat and partners and len(mine) == 1:
                return "overcall-rebid"
    return None


def interpret(a, call, profile=None):
    scene = _scene(a, call.seat, profile)
    if not scene:
        return None
    o = a.opening
    partner = (call.seat + 2) % 4
    own = _actions(a, call.seat)
    enemy = _opponents(a, call.seat)
    last = a.last_contract
    bid = call.bid
    p = _last(a, partner)
    if bid == "PASS":
        if scene == "double-advance" and o.strain != "N":
            return _m("Convert takeout double to penalties with strong trumps", "C3.3.penalty-pass",
                      min_length={o.strain: 5})
        return _m("Pass in the competitive auction", f"{scene}.pass")
    if scene == "penalty":
        if bid == "X":
            return _m("Penalty double after redouble, penalty NT double or strength double",
                      "B2.2.1.penalty", hcp_min=6)
        return _m("Natural escape or continuation after establishing penalty doubles",
                  "C5.1.continuation", suit=call.strain if call.is_contract else None)
    if scene == "defence":
        protective = _protective(a, call)
        opp = (profile or {}).get("opponents", {})
        opp = opp if isinstance(opp, dict) else {}
        if o.bid == "1C" and opp.get("strong_club") and call.index == o.index + 1:
            if bid in ("X", "1N"):
                return _m("Major two-suiter over strong club" if bid == "X" else
                          "Minor two-suiter over strong club", "C9.1.strong-club",
                          min_length={s: 4 for s in ("HS" if bid == "X" else "CD")}, artificial=True,
                          min_total_length=[("HS" if bid == "X" else "CD", 9)])
        art = _artificial(a, last, profile)
        if art and last.seat % 2 != call.seat % 2 and last != o:
            if bid == "X":
                return _m("Lead-directing double: length and strength in the artificial suit",
                          "C8.5.lead-directing", hcp_min=10, min_length={last.strain: 5})
            if call.is_contract and call.strain in art.get("suits", []):
                return _m("Takeout of the opponents' implied suit", "C8.5.implied-takeout",
                          artificial=True, hcp_min=12)
        if bid == "X":
            if last and last.level >= 6:
                return _m("Lightner double requests an unusual lead", "C8.6.Lightner", artificial=True)
            if o.strain == "N":
                return _m("Penalty double of 1NT", "C5.1.penalty", hcp_min=15)
            return _m("Takeout double; support for unbid suits or a strong hand",
                      "C4.takeout" if protective else "C6.takeout" if o.level >= 2 else "C3.1.takeout",
                      hcp_min=9 if protective else 12)
        if o.bid == "1N" and bid == "2C":
            return _m("Landy: both majors, at least five-four", "C5.3.Landy", hcp_min=9,
                      hcp_max=15, min_length={"H": 4, "S": 4}, artificial=True, forcing="one-round",
                      min_total_length=[("HS", 9)])
        known = _two_suits(a, call)
        if known:
            return _m("Unusual NT: two lowest unbid suits" if bid == "2N" else "Michaels two-suiter",
                      "C7.1.unusual" if bid == "2N" else "C7.1.Michaels", hcp_min=8,
                      min_length={s: 5 for s in known}, artificial=True, forcing="one-round")
        if call.is_contract and call.strain == "N":
            if bid == "1N":
                return _m("Protective natural NT" if protective else "Natural NT overcall with stopper",
                          "C4.1NT" if protective else "C2.1.1NT", hcp_min=11 if protective else 16,
                          hcp_max=14 if protective else 18, balanced=True,
                          stoppers=() if protective else tuple(c.strain for c in enemy if c.strain != "N"))
            if bid == "2N" and protective:
                return _m("Protective 2NT, natural", "C4.2NT", hcp_min=19, hcp_max=21, balanced=True,
                          stoppers=(o.strain,))
            if bid == "3N" and o.level >= 2:
                return _m("Natural 3NT over a preempt with stopper or a strong running minor",
                          "C6.1.3NT", hcp_min=16, stoppers=(o.strain,))
        if call.is_contract and call.strain != "N":
            jump = _jump(a, bid)
            if jump >= 2:
                return _m("Preemptive double-jump overcall", "C1.4.preempt", hcp_min=5, hcp_max=10,
                          min_length={call.strain: 7}, suit=call.strain)
            if jump == 1:
                if o.bid == "1N":
                    return _m("Strong long suit over 1NT, about seven playing tricks", "C5.2.jump",
                              hcp_min=10, min_length={call.strain: 6}, suit=call.strain)
                return _m("Intermediate jump overcall, sound six-card suit", "C1.3.intermediate",
                          hcp_min=12, hcp_max=16, min_length={call.strain: 6}, suit=call.strain)
            low = (5 if call.level == 1 else 7) if protective else \
                  12 if o.level >= 2 else 8 if call.level == 1 else 10
            return _m("Natural suit overcall", "C4.suit" if protective else
                      "C6.1.suit" if o.level >= 2 else "C5.2.suit" if o.strain == "N" else "C1.1.suit",
                      hcp_min=low, hcp_max=18, min_length={call.strain: 5}, suit=call.strain)
    if scene in ("our-opening-intervention", "nt-intervention"):
        intervening = [c for c in a.calls[o.index + 1:] if c.seat % 2 != call.seat % 2 and c.bid != "PASS"]
        action = intervening[-1]
        if action.bid == "X":
            if bid == "XX":
                return _m("Strength redouble; subsequent doubles are penalties", "B3.2.redouble" if
                          o.strain == "N" else "B2.2.redouble", hcp_min=10, artificial=True,
                          forcing="one-round")
            if o.strain == "N" and call.is_contract and call.strain != "N":
                return _m("Natural weak escape from doubled 1NT", "B3.2.escape",
                          hcp_max=7, min_length={call.strain: 5}, suit=call.strain, forcing="signoff")
            if bid == "2N":
                return _m("Sound limit raise or better after takeout double", "B2.3.support-2NT",
                          hcp_min=8, min_length={o.strain: 4}, suit=o.strain, artificial=True,
                          forcing="one-round")
            if call.is_contract and call.strain == o.strain:
                return _m("Preemptive raise after takeout double", "B2.3.preemptive-raise",
                          hcp_min=2 if call.level == 2 else 6, hcp_max=9,
                          min_length={o.strain: 3 if call.level == 2 else 4}, suit=o.strain)
            if bid == "1N":
                return _m("Natural NT after takeout double", "B2.1.NT", hcp_min=7, hcp_max=10,
                          balanced=True)
            if call.is_contract:
                return _m("Natural forcing response after takeout double", "B2.1.suit",
                          hcp_min=6 if call.level == 1 else 9, min_length={call.strain: 4},
                          suit=call.strain, forcing="one-round")
        art = _artificial(a, action, profile)
        if action.is_contract and action.strain == "N" and bid == "X" and not art:
            return _m("Penalty double of a natural NT overcall", "B1.NT-penalty", hcp_min=10)
        if art:
            suits = art.get("suits", [])
            if bid == "X":
                return _m("General strength; interest in penalties against the artificial overcall",
                          "B3.3.strength" if o.strain == "N" else "B4.1.penalty-interest",
                          hcp_min=10, artificial=True)
            if call.is_contract and call.strain in suits:
                if o.strain == "N":
                    return _m("Takeout of the known anchor suit", "B3.3.anchor", artificial=True,
                              hcp_min=10, forcing="one-round")
                low, high = (min(suits, key=ORDER.index), max(suits, key=ORDER.index))
                if len(suits) == 2 and call.strain == low:
                    unbid = [s for s in SUITS if s not in suits and s != o.strain]
                    return _m("Unbid suit with partial support for opener", "B4.2.lower-cue",
                              min_length={**{s: 5 for s in unbid}, o.strain: 2}, hcp_min=10,
                              artificial=True, forcing="one-round")
                return _m("Sound raise to at least three of opener's suit", "B4.2.raise-cue",
                          hcp_min=10, min_length={o.strain: 3}, suit=o.strain,
                          artificial=True, forcing="one-round")
        if bid == "X":
            max_level = 3 if o.strain == "N" else 2
            if action.level > max_level:
                return _m("Penalty-oriented double above the agreed takeout range", "B1.high-double",
                          hcp_min=10)
            unbid = [s for s in SUITS if s not in (o.strain, action.strain)]
            majors = {s: 4 for s in unbid if s in "HS"}
            threshold = 2 * action.level + 4 + (2 if action.strain == "S" else 0)
            exact = {"S": 4} if action.bid == "1H" and "S" in majors else {}
            return _m("Takeout/negative double showing the unbid major suits", "B3.1.takeout" if
                      o.strain == "N" else "B1.3.negative", hcp_min=threshold,
                      min_length=majors, max_length=exact, artificial=True)
        if call.is_contract and action.is_contract and call.strain == action.strain and action.strain != o.strain:
            return _m("Stayman cue bid, game forcing" if o.strain == "N" else
                      "Forcing cue bid with support for opener", "B3.1.Stayman" if o.strain == "N"
                      else "B1.cue-raise", hcp_min=13 if o.strain == "N" else 10,
                      artificial=True, forcing="game" if o.strain == "N" else "one-round",
                      min_length={} if o.strain == "N" else {o.strain: 3})
        if call.is_contract and call.strain == o.strain and o.strain != "N":
            return _m("Natural support for opener in competition", "B1.natural-raise",
                      hcp_min=5 if art else 6, min_length={o.strain: 3}, suit=o.strain, forcing="none")
        if call.is_contract and call.strain != "N":
            # Natural game bids place the contract, including jumps after
            # interference over 1NT. Artificial cues were handled above.
            forcing = "one-round" if call.level < GAME[call.strain] and \
                (o.strain != "N" or _jump(a, bid)) else "signoff"
            return _m("Natural response in competition", "B3.1.suit" if o.strain == "N" else "B1.suit",
                      hcp_min=6 if call.level == 1 else 10 if forcing == "one-round" else 0,
                      min_length={call.strain: 5 if o.strain == "N" or
                                  (call.strain == "S" and action.bid == "1H") else 4},
                      suit=call.strain, forcing=forcing)
    if scene == "negative-rebid":
        if call.is_contract:
            return _m("Natural rebid treating partner's negative double as an unbid-suit response",
                      "B1.4.rebid", min_length={call.strain: 4} if call.strain != "N" else {},
                      suit=call.strain, forcing="invite" if _jump(a, bid) else "none")
    if scene == "support-2nt-rebid" and call.is_contract:
        return _m("Accept or decline partner's limit raise after the double", "B2.3.rebid", suit=o.strain)
    if scene == "reopen" and bid == "X":
        return _m("Reopening takeout double protects partner's possible penalty pass", "B1.5.reopen",
                  max_length={last.strain: 2}, artificial=True)
    if scene == "double-advance":
        extra = 3 if _protective(a, own[0]) else 0
        if bid == "X":
            suits = [s for s in SUITS if s != o.strain]
            majors = {s: 4 for s in suits if s in "HS"}
            return _m("Responsive double: two possible unbid suits", "C8.2.responsive", hcp_min=8,
                      min_length=majors if o.strain in "CD" else {}, artificial=True)
        if call.is_contract and call.strain == o.strain:
            return _m("Cue bid; forcing until suit agreement", "C3.3.cue", hcp_min=11,
                      artificial=True, forcing="one-round")
        if call.is_contract and call.strain == "N":
            ranges = {1: (6, 9), 2: (10, 12), 3: (13, 15)}
            low, high = ranges.get(call.level, (16, 37))
            return _m("Natural NT advance with stopper", "C3.3.NT", hcp_min=low + extra, hcp_max=high + extra,
                      balanced=True, stoppers=(o.strain,))
        if call.is_contract:
            jump = _jump(a, bid)
            if call.level >= GAME[call.strain] and jump > 0:
                return _m("Game-going natural advance", "C3.3.game", hcp_min=13 + extra,
                          min_length={call.strain: 5}, suit=call.strain)
            return _m("Jump advance showing positive values" if jump else "Minimum suit advance",
                      "C3.3.jump" if jump else "C3.3.suit", hcp_min=9 + extra if jump else 0,
                      hcp_max=12 + extra if jump else 8 + extra,
                      min_length={call.strain: 4 if jump else 3}, suit=call.strain)
    if scene == "double-rebid":
        first = own[0]
        protective = _protective(a, first)
        if call.is_contract and call.strain == "N":
            return _m("Strong natural NT after initial double", "C4.double-NT" if protective else "C2.1.double-NT",
                      hcp_min=15 if protective else 19, hcp_max=18 if protective else 22, balanced=True,
                      stoppers=tuple(c.strain for c in enemy if c.strain != "N"))
        if call.is_contract and p and p.is_contract and p.strain == call.strain:
            return _m("Raise partner's advance with extra playing values", "C3.raise", hcp_min=12,
                      min_length={call.strain: 4}, suit=call.strain)
        if call.is_contract:
            if p and p.is_contract and p.strain in {c.strain for c in enemy}:
                return _m("Show a natural suit after partner's forcing cue bid", "C3.3.cue-reply",
                          hcp_min=9 if protective else 12, min_length={call.strain: 3}, suit=call.strain)
            if p and p.bid == "X":
                return _m("Natural response to partner's responsive double", "C8.2.response",
                          min_length={call.strain: 3}, suit=call.strain)
            return _m("Strong natural suit rebid after double", "C1.3.3.strong-suit", hcp_min=17,
                      min_length={call.strain: 5}, suit=call.strain)
    if scene == "double-cue-place" and call.is_contract:
        return _m("Natural continuation of the forcing cue-bid advance", "C3.3.cue-continuation",
                  suit=call.strain, forcing="one-round" if call.strain in (o.strain,) else "none")
    if scene in ("two-suit-advance", "two-suit-rebid", "two-suit-place"):
        first = own[0]
        known = ["H", "S"] if o.bid == "1N" else _two_suits(a, first)
        if scene == "two-suit-advance" and bid == "2N" and len(known) == 1:
            return _m("Ask Michaels bidder to identify the minor", "C7.3.minor-ask", artificial=True,
                      forcing="one-round")
        if scene == "two-suit-advance" and o.bid == "1N" and bid == "2D":
            return _m("Equal major length; ask Landy bidder to choose", "C5.3.preference-ask",
                      artificial=True, forcing="one-round")
        if scene == "two-suit-rebid" and p and p.bid == "2N" and len(known) == 1:
            return _m("Identify the Michaels minor", "C7.3.minor-reply",
                      min_length={call.strain: 5}, suit=call.strain)
        if call.is_contract:
            return _m("Natural preference/continuation of the two-suiter", "C5.3.preference" if
                      o.bid == "1N" else "C7.3.preference", suit=call.strain,
                      min_length={call.strain: 6} if call.strain not in known and
                      scene == "two-suit-advance" else {})
    if scene in ("overcall-advance", "overcall-rebid"):
        overcall = own[0]
        if bid == "X":
            if enemy and enemy[-1].strain != o.strain:
                others = [s for s in SUITS if s not in (o.strain, overcall.strain, enemy[-1].strain)]
                return _m("Competitive double: remaining suit and tolerance for partner",
                          "C8.3.competitive", hcp_min=9,
                          min_length={**{s: 4 for s in others}, overcall.strain: 3}, artificial=True)
            others = [s for s in SUITS if s not in (o.strain, overcall.strain)]
            return _m("Competitive double showing the other two suits", "C8.4.competitive",
                      hcp_min=9, min_length={s: 4 for s in others}, artificial=True)
        if scene == "overcall-advance" and call.is_contract and o.strain != "N" and call.strain == o.strain:
            return _m("Unassuming cue bid: support and game interest", "C1.2.2.cue", hcp_min=10,
                      min_length={overcall.strain: 3}, suit=overcall.strain, artificial=True,
                      forcing="one-round")
        if call.is_contract and call.strain == "N":
            return _m("Natural NT advance with guard in opponents' suit", "C1.2.3.NT",
                      hcp_min={1: 9, 2: 13, 3: 15}.get(call.level, 16),
                      hcp_max={1: 12, 2: 14, 3: 18}.get(call.level, 37),
                      stoppers=(o.strain,) if o.strain != "N" else ())
        if call.is_contract and call.strain == overcall.strain:
            return _m("Support for the overcall" if scene == "overcall-advance" else
                      "Natural rebid of the overcall", "C1.2.1.raise" if scene == "overcall-advance"
                      else "C1.2.2.rebid", min_length={call.strain: 3 if scene == "overcall-advance" else 5},
                      suit=call.strain)
        if call.is_contract:
            if scene == "overcall-rebid" and p and p.is_contract and p.strain == o.strain:
                return _m("Additional four-card feature after partner's unassuming cue bid",
                          "C1.2.2.feature", hcp_min=12, min_length={call.strain: 4}, suit=call.strain)
            forcing = "one-round" if _jump(a, bid) or _jump(a.prefix(overcall.index), overcall.bid) else "none"
            return _m("Natural new suit; encouraging" + (" and forcing" if forcing != "none" else " but not forcing"),
                      "C1.3.2.new-suit" if forcing != "none" else "C1.2.4.new-suit",
                      hcp_min=8 if call.level == 1 else 10, min_length={call.strain: 5},
                      suit=call.strain, forcing=forcing)
    return None


def _pick(ctx, bid, text=None, rule=None):
    if not bid or bid not in ctx.legal:
        return None
    meaning = interpret(ctx.auction, Call(ctx.seat, bid, len(ctx.auction.calls)), ctx.profile)
    return ctx.choose(bid, text or (meaning.description if meaning else "Natural competitive action"),
                      rule or (meaning.rule if meaning else "competitive.natural"),
                      alert=bool(meaning and meaning.artificial))


def _pass(ctx, text="No further constructive action", rule="competitive.pass"):
    return _pick(ctx, "PASS", text, rule)


def _defence(ctx):
    a, h, o = ctx.auction, ctx.h, ctx.auction.opening
    hypothetical = Call(ctx.seat, "PASS", len(a.calls))
    protective = _protective(a, hypothetical)
    opponent = (ctx.profile or {}).get("opponents", {})
    opponent = opponent if isinstance(opponent, dict) else {}
    last = a.last_contract
    if last.level >= 6:
        if any(h.length(s) == 0 for s in SUITS if s != last.strain) and "X" in ctx.legal:
            return _pick(ctx, "X")
        return _pass(ctx)
    if o.bid == "1C" and opponent.get("strong_club") and len(a.calls) == o.index + 1:
        floor = 8 if ctx.vulnerable else 5
        if h.hcp >= floor and min(h.length("H"), h.length("S")) >= 4 and \
                max(h.length("H"), h.length("S")) >= 5:
            return _pick(ctx, "X")
        if h.hcp >= floor and min(h.length("C"), h.length("D")) >= 4 and \
                max(h.length("C"), h.length("D")) >= 5:
            return _pick(ctx, "1N")
    artificial = _artificial(a, last, ctx.profile)
    if artificial and last != o:
        if h.hcp >= 10 and h.length(last.strain) >= 5 and _quality(h, last.strain) >= 2:
            return _pick(ctx, "X")
        implied = artificial.get("suits", [])
        if len(implied) == 1 and h.hcp >= 12 and h.length(implied[0]) <= 2 and \
                _shape(h, [s for s in SUITS if s != implied[0]]):
            return _pick(ctx, ctx.cheapest(implied[0]))
        return _pass(ctx)
    if o.bid == "1N":
        if h.hcp >= 16 or (h.hcp >= 15 and any(h.length(s) >= 6 and _quality(h, s) >= 3 for s in SUITS)):
            return _pick(ctx, "X")
        if 9 <= h.hcp <= 15 and min(h.length("H"), h.length("S")) >= 4 and \
                max(h.length("H"), h.length("S")) >= 5:
            return _pick(ctx, "2C")
        for suit in _best(h):
            if h.hcp >= 10 and h.length(suit) >= 5 and _quality(h, suit) >= 2:
                level = 3 if h.length(suit) >= 7 and _quality(h, suit) >= 3 else 2
                # 2C is Landy, so a natural club hand must bid 3C.
                if suit == "C":
                    if h.length(suit) < 6:
                        continue
                    level = 3
                return _pick(ctx, f"{level}{suit}")
        return _pass(ctx)
    if o.strain == "N":
        return _pass(ctx)
    unbid = [s for s in SUITS if s not in {c.strain for c in _opponents(a, ctx.seat)}]
    if protective and h.hcp + h.length("S") < 14:
        return _pass(ctx, "Insufficient values to protect under the transferred-king guideline", "C4.pass")
    if o.level == 1:
        if h.balanced:
            if protective and 19 <= h.hcp <= 21 and h.stopper(o.strain):
                return _pick(ctx, "2N")
            if (protective and 11 <= h.hcp <= 14) or \
                    (not protective and 16 <= h.hcp <= 18 and
                     _stopped(h, {c.strain for c in _opponents(a, ctx.seat)})):
                return _pick(ctx, "1N")
        lower = [s for s in ORDER if s != o.strain][:2]
        major = ["H", "S"] if o.strain in "CD" else ["S" if o.strain == "H" else "H"]
        other_minor = [s for s in "CD" if h.length(s) >= 5 and _quality(h, s) >= 2]
        if h.hcp >= (10 if ctx.vulnerable else 8) and len(_opponents(a, ctx.seat)) == 1:
            if _shape(h, major, 5) and all(_quality(h, s) >= 2 for s in major) and \
                    (len(major) == 2 or other_minor):
                return _pick(ctx, f"2{o.strain}")
            if not protective and _shape(h, lower, 5) and all(_quality(h, s) >= 2 for s in lower):
                return _pick(ctx, "2N")
    else:
        if h.hcp >= 16 and h.stopper(o.strain) and h.balanced and "3N" in ctx.legal:
            return _pick(ctx, "3N")
    takeout_floor = 9 if protective else 12
    shape_ok = h.length(o.strain) <= 2 and _shape(h, unbid, 3) and \
        all(h.length(s) >= 4 for s in unbid if s in "HS")
    if (h.hcp >= (15 if protective and h.balanced else 17) or
            (h.hcp >= takeout_floor and shape_ok)) and "X" in ctx.legal:
        # Above a four-heart preempt, always retain real spade tolerance.
        if not (o.bid == "4H" and h.length("S") < 3):
            return _pick(ctx, "X")
    for suit in _best(h, unbid):
        minimum = ctx.cheapest(suit)
        if not minimum:
            continue
        level = int(minimum[0])
        floor = (5 if level == 1 else 7) if protective else 12 if o.level >= 2 else 8 if level == 1 else 10
        length, quality = h.length(suit), _quality(h, suit)
        if length < 5 or quality < 2:
            continue
        strong_preempt = quality >= 3 or (not ctx.vulnerable and sum(h.has(suit, r) for r in "AKQ") >= 2)
        if h.hcp <= 10 and length >= 7 and strong_preempt and o.level == 1:
            preempt = f"{level + 2}{suit}"
            if preempt in ctx.legal and level + 2 <= GAME[suit]:
                return _pick(ctx, preempt)
        if 12 <= h.hcp <= 16 and length >= 6 and quality >= 3 and o.level == 1:
            jump = f"{level + 1}{suit}"
            if jump in ctx.legal:
                return _pick(ctx, jump)
        if h.hcp >= floor and (level == 1 or length >= 6 or quality >= 3):
            if o.level >= 2 and h.losers <= 4 and length >= 7:
                game = f"{GAME[suit]}{suit}"
                if game in ctx.legal:
                    return _pick(ctx, game)
            return _pick(ctx, minimum)
    return _pass(ctx)


def _intervention(ctx, scene):
    a, h, o = ctx.auction, ctx.h, ctx.auction.opening
    intervening = [c for c in a.calls[o.index + 1:] if c.seat % 2 != ctx.seat % 2 and c.bid != "PASS"]
    action = intervening[-1]
    if action.bid == "X":
        if o.strain == "N":
            if h.hcp >= 10:
                return _pick(ctx, "XX")
            for suit in _best(h):
                if h.length(suit) >= 5 and h.hcp <= 7:
                    return _pick(ctx, ctx.cheapest(suit, 2))
            return _pass(ctx)
        support = h.length(o.strain)
        if support >= 4 and h.support_points(o.strain) >= 10 and h.hcp >= 8:
            return _pick(ctx, "2N")
        if support >= 5 and 5 <= h.hcp <= 9 and not ctx.vulnerable:
            return _pick(ctx, f"{GAME[o.strain]}{o.strain}")
        if support >= 4 and 6 <= h.hcp <= 9:
            return _pick(ctx, f"3{o.strain}")
        if support >= 3 and 2 <= h.hcp <= 7:
            return _pick(ctx, f"2{o.strain}")
        if h.hcp >= 10 and support < 4 and h.quick_tricks >= 2:
            return _pick(ctx, "XX")
        for suit in _best(h, [s for s in SUITS if s != o.strain]):
            bid = ctx.cheapest(suit)
            if bid and h.length(suit) >= (4 if bid[0] == "1" else 5) and \
                    h.hcp >= (6 if bid[0] == "1" else 9) and _quality(h, suit) >= 2:
                return _pick(ctx, bid)
        if 7 <= h.hcp <= 10 and h.balanced and _stopped(h, [s for s in SUITS if s != o.strain]):
            return _pick(ctx, "1N")
        return _pass(ctx)
    if not action.is_contract:
        return None
    artificial = _artificial(a, action, ctx.profile)
    if action.strain == "N" and not artificial:
        if h.hcp >= 10:
            return _pick(ctx, "X")
        if o.strain != "N" and h.length(o.strain) >= 4 and h.hcp >= 5:
            return _pick(ctx, ctx.cheapest(o.strain))
        return _pass(ctx)
    if artificial:
        theirs = artificial.get("suits", [])
        if o.strain != "N" and h.length(o.strain) >= 3:
            if h.hcp >= 10 and theirs:
                return _pick(ctx, ctx.cheapest(max(theirs, key=ORDER.index)))
            if h.hcp >= 5:
                return _pick(ctx, ctx.cheapest(o.strain, 2))
        if o.strain != "N" and len(theirs) == 2 and h.length(o.strain) >= 2 and h.hcp >= 10:
            unbid = [s for s in SUITS if s not in theirs and s != o.strain]
            if any(h.length(s) >= 5 for s in unbid):
                return _pick(ctx, ctx.cheapest(min(theirs, key=ORDER.index)))
        if h.hcp >= 10 and (o.strain == "N" or any(h.length(s) >= 4 and _quality(h, s) >= 2 for s in theirs)):
            return _pick(ctx, "X")
        anchor = artificial.get("anchor")
        if anchor and h.hcp >= 10 and h.length(anchor) <= 2:
            return _pick(ctx, ctx.cheapest(anchor))
        for suit in _best(h, [s for s in SUITS if s not in theirs and s != o.strain]):
            if h.hcp >= 10 and h.length(suit) >= 5:
                return _pick(ctx, ctx.cheapest(suit))
        return _pass(ctx)
    if o.strain == "N":
        if h.hcp >= 13 and any(h.length(s) >= 4 for s in "HS" if s != action.strain):
            return _pick(ctx, ctx.cheapest(action.strain))
        unbid = [s for s in SUITS if s != action.strain]
        if h.hcp >= 2 * action.level + 4 + (2 if action.strain == "S" else 0) and h.length(action.strain) <= 2 and \
                sum(h.length(s) >= 4 for s in unbid) >= 2 and action.level <= 3 and \
                all(h.length(s) >= 4 for s in unbid if s in "HS"):
            return _pick(ctx, "X")
        if h.hcp >= 13 and h.stopper(action.strain):
            return _pick(ctx, "3N")
        for suit in _best(h, unbid):
            bid = ctx.cheapest(suit)
            if h.length(suit) >= 5 and bid:
                if h.hcp >= 13:
                    jump = f"{int(bid[0]) + 1}{suit}"
                    if jump in ctx.legal:
                        return _pick(ctx, jump)
                return _pick(ctx, bid)
        return _pass(ctx)
    unbid = [s for s in SUITS if s not in (o.strain, action.strain)]
    # A natural 1S over 1H promises five; four spades use the negative double.
    if action.bid == "1H" and h.length("S") >= 5 and h.hcp >= 6:
        return _pick(ctx, "1S")
    threshold = 2 * action.level + 4 + (2 if action.strain == "S" else 0)
    if action.level <= 2 and h.hcp >= threshold and \
            all(h.length(s) >= 4 for s in unbid if s in "HS") and \
            all(h.length(s) >= 3 for s in unbid):
        return _pick(ctx, "X")
    if h.length(o.strain) >= 3:
        if h.hcp >= 10:
            return _pick(ctx, ctx.cheapest(action.strain))
        if h.hcp >= 6:
            return _pick(ctx, ctx.cheapest(o.strain))
    if h.length(action.strain) >= 5 and _quality(h, action.strain) >= 3:
        return _pass(ctx, "Pass with penalty-oriented trumps; partner can reopen", "B1.5.trap-pass")
    for suit in _best(h, unbid):
        bid = ctx.cheapest(suit)
        if bid and h.length(suit) >= (4 if bid[0] == "1" else 5) and h.hcp >= (6 if bid[0] == "1" else 10):
            return _pick(ctx, bid)
    if h.hcp >= 8 and h.stopper(action.strain):
        level = 3 if h.hcp >= 13 else 2 if h.hcp >= 11 else 1
        if f"{level}N" in ctx.legal:
            return _pick(ctx, f"{level}N")
    return _pass(ctx)


def _double_advance(ctx):
    a, h, o = ctx.auction, ctx.h, ctx.auction.opening
    enemy = _opponents(a, ctx.seat)
    first = _actions(a, ctx.seat)[0]
    protective = _protective(a, first)
    points = h.hcp - (3 if protective else 0)
    if o.strain == "N":
        for suit in _best(h):
            if h.length(suit) >= 6 and h.hcp <= 4:
                return _pick(ctx, ctx.cheapest(suit, 2))
        return _pass(ctx)
    unbid = [s for s in SUITS if s != o.strain]
    if len(enemy) >= 2 and enemy[-1].strain == o.strain:
        majors = [s for s in unbid if s in "HS"]
        if points >= 8 and (all(h.length(s) >= 4 for s in majors) if o.strain in "CD" else
                            sum(h.length(s) >= 4 for s in unbid) >= 2):
            return _pick(ctx, "X")
    if h.length(o.strain) >= 5 and _quality(h, o.strain) >= 3 and h.hcp >= 6:
        return _pass(ctx, "Convert partner's takeout double to penalties", "C3.3.penalty-pass")
    if o.level >= 4 and h.hcp >= 5 and max(h.length(s) for s in unbid) < 5:
        return _pass(ctx, "Defend the high-level preempt without a useful long suit", "C6.2.pass")
    best = _best(h, unbid)[0]
    major = [s for s in "HS" if s in unbid and h.length(s) >= 4]
    if major and h.length(best) <= 5:
        best = _best(h, major)[0]
    if points >= 11 and h.length(best) <= 4:
        return _pick(ctx, ctx.cheapest(o.strain))
    if h.stopper(o.strain) and h.balanced and not major:
        level = 3 if points >= 13 else 2 if points >= 10 else 1 if points >= 6 else None
        if level and f"{level}N" in ctx.legal:
            return _pick(ctx, f"{level}N")
    bid = ctx.cheapest(best)
    if not bid:
        return _pass(ctx)
    level = int(bid[0])
    if points >= 13 and h.length(best) >= 5:
        game = f"{GAME[best]}{best}"
        if game in ctx.legal:
            return _pick(ctx, game)
    if points >= 9 and level + 1 <= GAME[best]:
        jump = f"{level + 1}{best}"
        if jump in ctx.legal:
            return _pick(ctx, jump)
    return _pick(ctx, bid)


def _two_suit(ctx, scene):
    a, h, o = ctx.auction, ctx.h, ctx.auction.opening
    own = _actions(a, ctx.seat)
    first = own[0]
    known = ["H", "S"] if o.bid == "1N" else _two_suits(a, first)
    p = _last(a, ctx.partner)
    if scene == "two-suit-advance":
        if o.bid == "1N" and h.length("H") == h.length("S") and h.hcp < 10:
            return _pick(ctx, "2D")
        best = _best(h, known)[0]
        if len(known) == 1 and h.length(best) < 3 and min(h.length("C"), h.length("D")) >= 2:
            return _pick(ctx, "2N")
        if h.length(best) >= 4 and h.support_points(best) >= 13:
            return _pick(ctx, f"{GAME[best]}{best}")
        if h.length(best) >= 4 and h.hcp >= 8:
            return _pick(ctx, f"3{best}")
        if h.length(best) <= 2:
            for suit in _best(h, [s for s in SUITS if s not in known]):
                if h.length(suit) >= 7 and _quality(h, suit) >= 3:
                    return _pick(ctx, ctx.cheapest(suit))
        return _pick(ctx, ctx.cheapest(best))
    if scene == "two-suit-place":
        if p and p.is_contract and h.length(p.strain) >= 4 and h.support_points(p.strain) >= 13:
            return _pick(ctx, f"{GAME[p.strain]}{p.strain}")
        return _pass(ctx)
    if not p or not p.is_contract:
        return _pass(ctx)
    if o.bid == "1N" and p.bid == "2D":
        return _pick(ctx, ctx.cheapest(_best(h, "HS")[0]))
    if len(known) == 1 and p.bid == "2N":
        return _pick(ctx, ctx.cheapest(_best(h, "CD")[0], 3))
    if p.strain not in known:
        return _pass(ctx, "Partner's very long new suit is natural and non-forcing", "C7.3.pass")
    if h.hcp >= 17 or h.losers <= 4:
        return _pick(ctx, f"{GAME[p.strain]}{p.strain}") or _pass(ctx)
    if h.hcp >= 13 or h.losers <= 5:
        return _pick(ctx, f"{p.level + 1}{p.strain}") or _pass(ctx)
    return _pass(ctx)


def _overcall_advance(ctx):
    a, h, o = ctx.auction, ctx.h, ctx.auction.opening
    first = _actions(a, ctx.seat)[0]
    enemy = _opponents(a, ctx.seat)
    support = h.length(first.strain)
    points = h.hcp - (3 if _protective(a, first) else 0)
    if len(enemy) >= 2 and enemy[-1].strain == o.strain:
        unbid = [s for s in SUITS if s not in (o.strain, first.strain)]
        if points >= 9 and _shape(h, unbid, 4):
            return _pick(ctx, "X")
    elif len(enemy) >= 2:
        unbid = [s for s in SUITS if s not in (o.strain, first.strain, enemy[-1].strain)]
        if points >= 9 and h.length(first.strain) >= 3 and unbid and _shape(h, unbid, 4):
            return _pick(ctx, "X")
    if support >= 3:
        if points >= 10:
            if o.strain == "N":
                return _pick(ctx, f"{GAME[first.strain] if points >= 13 else min(first.level + 1, GAME[first.strain])}{first.strain}")
            return _pick(ctx, ctx.cheapest(o.strain))
        if support >= 5 and points >= 5 and not ctx.vulnerable:
            return _pick(ctx, f"{GAME[first.strain]}{first.strain}") or _pass(ctx)
        if support >= 4 and points >= 5:
            return _pick(ctx, f"{min(first.level + 2, GAME[first.strain])}{first.strain}") or _pass(ctx)
        if points >= 6:
            return _pick(ctx, ctx.cheapest(first.strain))
    if o.strain != "N" and h.stopper(o.strain) and h.balanced and points >= 9:
        level = 1 if points <= 12 else 2 if points <= 14 else 3
        if f"{level}N" in ctx.legal:
            return _pick(ctx, f"{level}N")
    for suit in _best(h, [s for s in SUITS if s not in (o.strain, first.strain)]):
        bid = ctx.cheapest(suit)
        if bid and (h.length(suit) >= 6 or (h.length(suit) >= 5 and _quality(h, suit) >= 3)) and \
                points >= (8 if bid[0] == "1" else 10):
            if points >= 16 and int(bid[0]) < GAME[suit] - 1:
                jump = f"{int(bid[0]) + 1}{suit}"
                if jump in ctx.legal:
                    return _pick(ctx, jump)
            return _pick(ctx, bid)
    return _pass(ctx)


def _rebid(ctx, scene):
    a, h, o = ctx.auction, ctx.h, ctx.auction.opening
    own = _actions(a, ctx.seat)
    p = _last(a, ctx.partner)
    if scene == "reopen":
        enemy = _opponents(a, ctx.seat)[-1]
        if h.length(enemy.strain) <= 2 and "X" in ctx.legal:
            return _pick(ctx, "X")
        return _pass(ctx)
    if scene == "support-2nt-rebid":
        level = GAME[o.strain] if h.support_points(o.strain) >= 15 else 3
        return _pick(ctx, f"{level}{o.strain}") or _pass(ctx)
    if not p:
        return None
    enemy_suits = {c.strain for c in _opponents(a, ctx.seat) if c.strain != "N"}
    if scene == "negative-rebid":
        choices = [s for s in SUITS if s not in enemy_suits and s != o.strain]
        majors = [s for s in choices if s in "HS" and h.length(s) >= 4]
        best = _best(h, majors or choices)[0]
        if h.length(best) >= 4:
            bid = ctx.cheapest(best)
            if bid and int(bid[0]) > GAME[best]:
                if h.hcp < 16 or h.length(best) < 5:
                    return _pass(ctx, "Opponents removed the bidding space; insufficient values to force the five level",
                                 "B1.4.high-level-pass")
                return _pick(ctx, bid)
            if bid and h.support_points(best) >= 19:
                return _pick(ctx, f"{GAME[best]}{best}")
            if bid and h.support_points(best) >= 16:
                jump = f"{int(bid[0]) + 1}{best}"
                if jump in ctx.legal and int(jump[0]) <= GAME[best]:
                    return _pick(ctx, jump)
            return _pick(ctx, bid)
        if h.balanced and _stopped(h, enemy_suits):
            bid = ctx.cheapest("N")
            return _pick(ctx, bid)
        return _pick(ctx, ctx.cheapest(o.strain))
    if scene == "double-rebid":
        first = own[0]
        protective = _protective(a, first)
        if p.bid == "X":
            suits = [s for s in SUITS if s not in enemy_suits]
            best = _best(h, suits)[0]
            majors = [s for s in suits if s in "HS" and h.length(s) >= 4]
            if majors and h.length(best) <= 5:
                best = _best(h, majors)[0]
            return _pick(ctx, ctx.cheapest(best))
        if h.balanced and h.hcp >= (15 if protective else 19) and _stopped(h, enemy_suits):
            return _pick(ctx, ctx.cheapest("N"))
        if p.is_contract and p.strain not in enemy_suits and p.strain != "N" and h.length(p.strain) >= 4:
            if h.support_points(p.strain) >= 19 or (p.level >= 2 and h.support_points(p.strain) >= 16):
                return _pick(ctx, f"{GAME[p.strain]}{p.strain}") or _pass(ctx)
            if h.support_points(p.strain) >= 16:
                return _pick(ctx, ctx.cheapest(p.strain))
        if h.hcp >= 17:
            for suit in _best(h, [s for s in SUITS if s not in enemy_suits]):
                if h.length(suit) >= 5:
                    return _pick(ctx, ctx.cheapest(suit))
        if p.is_contract and p.strain in enemy_suits:
            best = _best(h, [s for s in SUITS if s not in enemy_suits])[0]
            return _pick(ctx, ctx.cheapest(best), "Show a suit after partner's forcing cue bid", "C3.3.cue-reply")
        return _pass(ctx)
    if scene == "double-cue-place":
        if p.is_contract and p.strain != "N" and h.length(p.strain) >= 4:
            level = GAME[p.strain] if h.support_points(p.strain) >= 13 else min(p.level + 1, GAME[p.strain])
            return _pick(ctx, f"{level}{p.strain}") or _pass(ctx)
        if h.stopper(o.strain) and h.hcp >= 13:
            return _pick(ctx, "3N") or _pass(ctx)
        best = _best(h, [s for s in SUITS if s not in enemy_suits and s != p.strain])[0]
        return _pick(ctx, ctx.cheapest(best))
    if scene == "overcall-rebid":
        first = own[0]
        # The slam module has already considered genuine slam interest.
        # Do not turn a natural game raise into another automatic raise;
        # opponents bidding over game still require competitive evaluation.
        if p.is_contract and p.strain == first.strain and \
                p.level >= GAME[first.strain] and a.last_contract == p:
            return _pass(ctx, "Partner has placed the contract in game", "C1.2.2.accept-game")
        if p.is_contract and o.strain != "N" and p.strain == o.strain:
            if h.hcp <= 11:
                return _pick(ctx, ctx.cheapest(first.strain))
            if h.hcp >= 15 and h.length(first.strain) >= 6:
                return _pick(ctx, f"{GAME[first.strain]}{first.strain}") or _pass(ctx)
            if h.stopper(o.strain) and h.hcp >= 14 and h.balanced:
                return _pick(ctx, "3N")
            for suit in _best(h, [s for s in SUITS if s not in (o.strain, first.strain)]):
                if h.length(suit) >= 4:
                    return _pick(ctx, ctx.cheapest(suit))
            return _pick(ctx, ctx.cheapest(first.strain))
        if p.is_contract and p.strain != "N" and h.length(p.strain) >= 3 and h.hcp >= 13:
            return _pick(ctx, ctx.cheapest(p.strain))
        if p.is_contract and p.strain == "N" and h.hcp >= 14:
            return _pick(ctx, "3N") or _pass(ctx)
        return _pass(ctx)
    return None


def choose(ctx):
    scene = _scene(ctx.auction, ctx.seat, ctx.profile)
    if scene == "defence":
        return _defence(ctx)
    if scene in ("our-opening-intervention", "nt-intervention"):
        return _intervention(ctx, scene)
    if scene == "double-advance":
        return _double_advance(ctx)
    if scene in ("two-suit-advance", "two-suit-rebid", "two-suit-place"):
        return _two_suit(ctx, scene)
    if scene == "overcall-advance":
        return _overcall_advance(ctx)
    if scene in ("negative-rebid", "support-2nt-rebid", "reopen", "double-rebid", "double-cue-place", "overcall-rebid"):
        return _rebid(ctx, scene)
    if scene == "penalty":
        a, h = ctx.auction, ctx.h
        last = a.last_contract
        if last and last.seat % 2 != ctx.seat % 2 and "X" in ctx.legal:
            if last.strain == "N" and h.hcp >= 10 or last.strain != "N" and \
                    h.hcp >= 6 and h.length(last.strain) >= 4 and _quality(h, last.strain) >= 1:
                return _pick(ctx, "X")
        # A penalty double of NT is left in except for a weak, very long suit.
        if last and last.strain == "N" and last.seat % 2 != ctx.seat % 2:
            for suit in _best(h):
                if h.hcp <= 4 and h.length(suit) >= 6:
                    return _pick(ctx, ctx.cheapest(suit, 2), "Weak shapely escape from partner's penalty double",
                                 "C5.1.escape")
        return _pass(ctx, "Cooperate with the partnership's penalty action", "penalty.cooperate")
    return None
