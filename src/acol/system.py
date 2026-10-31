"""Acol rule dispatch and auction interpretation, with no neural fallback."""
from dataclasses import asdict
from .core import Auction, Context, Meaning, PROFILE, SUITS


def modules():
    from . import slam, notrump, competitive, natural
    return (slam, notrump, competitive, natural)


def interpret_call(auction, call, profile=None):
    profile = {**PROFILE, **(profile or {})}
    for module in modules():
        meaning = module.interpret(auction, call, profile)
        if meaning is not None:
            return meaning
    # An unrecognised sequence remains uninformative. Inventing a natural suit
    # or a 2/1 HCP range here would poison sampling of artificial human calls.
    return Meaning(description='No additional inference for this continuation', rule='general.unclassified', confidence=0)


def interpret_auction(auction, profile=None):
    if not isinstance(auction, Auction):
        auction = Auction(auction)
    return [(call, interpret_call(auction.prefix(call.index), call, profile)) for call in auction.calls]


def choose_bid(hand, auction, seat=None, vulnerability='None', profile=None):
    ctx = Context(hand, auction, seat, vulnerability, profile)
    for module in modules():
        decision = module.choose(ctx)
        if decision is not None:
            if decision.bid not in ctx.legal:
                raise ValueError(f'Acol rule {decision.rule} produced an illegal bid')
            return decision
    # A game force survives a later descriptive call and interference. Looking
    # only at partner's latest call would forget, for example, opener's jump
    # shift after responder subsequently gives simple preference.
    partner_calls = [c for c in ctx.auction.calls_by(ctx.partner) if c.is_contract]
    if partner_calls:
        last = partner_calls[-1]
        meaning = interpret_call(ctx.auction.prefix(last.index), last, ctx.profile)
        already_answered = any(c.seat == ctx.seat and c.index > last.index and c.bid != 'PASS' for c in ctx.auction.calls)
        promises = [(c, m) for c, m in interpret_auction(ctx.auction, ctx.profile)
                    if c.seat % 2 == ctx.seat % 2]
        game_forcing = any(m.forcing == 'game' for _, m in promises)
        current = ctx.auction.last_contract
        current_meaning = interpret_call(ctx.auction.prefix(current.index), current, ctx.profile) if current else None
        game_reached = bool(current and current.seat % 2 == ctx.seat % 2
                            and not current_meaning.artificial
                            and current.level >= (3 if current.strain == 'N' else 4 if current.strain in 'HS' else 5))
        if game_forcing and not game_reached:
            # Prefer an actual natural fit. Artificial asks and cue bids must
            # not turn their displayed strain into a trump agreement.
            partner_suit = meaning.suit or (last.strain if not meaning.artificial else None)
            supported = partner_suit in tuple(SUITS) and ctx.h.length(partner_suit) >= 3
            if supported:
                game = ('4' if partner_suit in 'HS' else '5') + partner_suit
                if game in ctx.legal:
                    return ctx.choose(game, 'Reach game in the fit after the earlier game force', 'general.game-force')
            if '3N' in ctx.legal:
                return ctx.choose('3N', 'Complete the earlier game force when no trump fit is available', 'general.game-force')
            if current.seat % 2 != ctx.seat % 2 and 'X' in ctx.legal:
                return ctx.choose('X', 'Opponents have bid beyond our game; defend doubled after the game force', 'general.game-force-penalty')
        if not already_answered and (meaning.forcing == 'one-round' or (game_forcing and not game_reached)):
            if meaning.suit in tuple(SUITS) and ctx.h.length(meaning.suit) >= 3:
                bid = ctx.cheapest(meaning.suit)
            else:
                suits = sorted(SUITS, key=lambda s: (-ctx.h.length(s), -ctx.h.suit_quality(s)))
                bid = next((ctx.cheapest(s) for s in suits if ctx.h.length(s) >= 4 and ctx.cheapest(s)), ctx.cheapest('N'))
            if bid:
                return ctx.choose(bid, 'Natural continuation preserving partner’s forcing call', 'general.forcing-continuation')
    return ctx.choose('PASS', 'No further constructive action in this auction', 'general.pass')


def decision_payload(decision):
    return {**asdict(decision), 'system': PROFILE['id'], 'bidding_engine': 'rules', 'neural_fallback': False}
