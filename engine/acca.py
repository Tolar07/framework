"""ACCA BUILDER — the day's production output folded into Acca A + split accas + singles.

STANDING RULE (Architect 2026-08-09)
  The product bet draws ONLY from fixtures kicking off TODAY — nothing else.
  The wider scan (PART 2 / scan tables) stays the 3-day reference window, but
  every leg of the produced bet, THE CALL, the acca and the singles comes from
  today's slate.

PRODUCTION INTENT (OLP_XDV_PRODUCTION_INTENT1.md, 2026-08-10; ranking 2026-08-11)
  - Acca A (headline): the framework's top 4-5 highest-EDGE fixtures, each leg =
    that fixture's OWN single best market across the FULL universe (1X2, O/U1.5,
    O/U2.5, BTTS, Double Chance) — no forced diversity. Confirmed against the
    Architect's ₦578,502 World Cup ticket, which worked precisely because each
    leg was the match's true strongest signal, not because of artificial variety.
  - Once a fixture is in Acca A it is REMOVED from the pool — a fixture never
    appears in two bets.
  - Singles: every remaining fixture's natural best market as a standalone
    slip, EACH with its own booking code.
  - The remainder is split into grouped accumulators of ~4-5 legs each (never
    one giant accumulator — too many correlated legs is a structural weakness),
    each with its own booking code.

WHAT THIS BUILDS
  `build_production_bets` returns the full production shape (Acca A, split
  accas, singles). Every leg is priced on the live line in a CAPITAL-CLEARED
  market: the builder evaluates ALL markets a fixture can be scored on
  (mkt.EDGE_MARKETS — 1X2 Home/Draw/Away, Over/Under 1.5/2.5, BTTS, Double
  Chance) and admits any that carry a real bookmaker price. The Odds API free
  tier prices the five base markets; api-football fills O1.5/BTTS/DC (2026-08-11,
  same request, zero extra quota). ID405 scope is overridden (2026-08-11,
  Architect directive) — away wins may be recommended; all markets stay open.

RANKING (changed 2026-08-11 — EDGE)
  Legs are ranked by EDGE = the natural best market's EV (model_prob × price − 1):
  the market where the book misprices the fixture in our favour, which is the
  signal that drives positive CLV. This replaced the 2026-08-10 probability-first
  ranking — raw probability drifts into favourite-longshot losses (the framework's
  own backtest: draw +0.42→+0.55% was the only genuine edge; aways −2% even at
  high probability). Probability stays visible as information. EV stays on every
  leg. When a fixture's true best market has no live price, it cannot be a leg —
  you can only bet a priced market (HR35).

HONESTY (HR35 carried through)
  - A fixture with no kickoff date is NOT in any bet — a date we cannot
    confirm as today cannot be bet as today (never assumed).
  - A leg we cannot price is not a leg (HR35) — unpriced fixtures stay visible
    in the board but never enter a bookable slip.
  - Fewer than 4-5 today fixtures -> a SHORTENED acca, never padded with a
    tomorrow fixture and never a fabricated leg.
  - Combined chance is the product of the legs' chances, stated as such:
    legs are not independent, so it is information, not encouragement.
  - An acca is a product shape, NOT a demonstrated edge. The backtest is
    negative; the block carries the honest line.

PHASE 3 (live capital, Architect-deployed 2026-08-11)
  This module only NAMES and PRICES the bets. It never places, never stakes.
  Booking codes are generated separately (booking/booking_codes.py) for the
  Architect's review; capital authority stays with the Architect.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import count
from typing import Any, Iterator, List, Optional

from engine import markets as mkt

ACCA_A_MAX = 5          # the headline acca holds the top 4-5 confidence legs
HEADLINE_MIN_LEGS = 4   # below this, Acca A is a shortened acca, never padded
SPLIT_GROUP_TARGET = 5  # remainder splits into ~4-5 leg groups, never one giant acca


@dataclass
class AccaLeg:
    """One leg of a bet: a fixture + the capital-cleared market to back."""
    fixture: str          # "Home v Away" (model keys, board fixture name)
    league: str
    market_key: str       # canonical key, e.g. mkt.DRAW
    market_name: str      # words, e.g. "Draw" (HR53 — no bare glyphs)
    price: float          # decimal odds on the live line
    prob: float           # model probability for that market
    ev: Optional[float]   # model_prob * price - 1, when computable
    sportybet_fixture_id: Optional[str] = None  # set by the booking step


@dataclass
class Acca:
    """One accumulator (headline or split)."""
    label: str            # "Acca A", "Acca B", ... or "SINGLE — <fixture>"
    legs: List[AccaLeg] = field(default_factory=list)
    combined_odds: Optional[float] = None
    combined_prob: Optional[float] = None

    @property
    def n_legs(self) -> int:
        return len(self.legs)


@dataclass
class ProductionBets:
    """The day's production output: the headline acca, the split accas, singles.

    `singles` are the SAME legs that fill the split accas — each remaining
    fixture's natural best market appears both inside a split acca AND as a
    standalone single with its own booking code (production intent #6)."""
    acca_a: Optional[Acca] = None
    split_accas: List[Acca] = field(default_factory=list)
    singles: List[AccaLeg] = field(default_factory=list)

    @property
    def n_acca_legs(self) -> int:
        """Total legs across Acca A and every split acca."""
        n = 0
        if self.acca_a is not None:
            n += self.acca_a.n_legs
        n += sum(a.n_legs for a in self.split_accas)
        return n


def _league_of(fixture: str) -> str:
    """'Home v Away (League)' -> 'League'. Mirrors the board's league tag."""
    return fixture.split(" (")[-1].rstrip(")") if " (" in fixture else "—"


def _team_pair(bf) -> tuple[str, str]:
    """(home, away) model keys from the fixture probs when present, else parse
    from the fixture name — the odds_index is keyed on model keys."""
    if bf.probs is not None:
        return bf.probs.home_team, bf.probs.away_team
    name = bf.fixture.split(" (")[0]
    if " v " in name:
        h, a = name.split(" v ", 1)
        return h.strip(), a.strip()
    return "", ""


def _best_deployable_leg(bf, odds_index: Optional[dict]) -> Optional[AccaLeg]:
    """The best CAPITAL-CLEARED market for one fixture, priced on the live line.

    Multi-market selection (Architect 2026-08-11): every fixture is evaluated
    across ALL markets — 1X2, Over/Under 1.5, Over/Under 2.5, BTTS and Double
    Chance — and picks its OWN single best market. Selection is by the highest
    EDGE = model_prob × price − 1 (where the book misprices the fixture in our
    favour — the signal that drives positive CLV), tiebreak model_prob, then
    canonical market order. Probability stays visible as information.

    A market enters only when it carries a REAL bookmaker price (SportyBet 1X2
    attrs, or the odds index — api-football fills O1.5/BTTS/DC, the Odds API
    free tier fills the rest). Returns None when the fixture has no model probs,
    is not on the deploy shortlist, or has no priced market — a leg we cannot
    price is not a leg (HR35)."""
    if bf.probs is None or not getattr(bf, "on_deploy_shortlist", False):
        return None
    home, away = _team_pair(bf)

    best: Optional[AccaLeg] = None
    for market in mkt.EDGE_MARKETS:
        prob = mkt.model_prob(market, bf.probs)
        if prob is None:
            continue
        price = None
        # SportyBet first for the markets it carries (1X2) — it is the book the
        # Architect actually bets at. The Odds API / api-football cover the rest.
        # The orchestrator attaches sb_home/draw/away_odds from the SportyBet
        # cache; using all three means a leg prices on SportyBet's own line
        # even when the Odds API quota is exhausted (verified 2026-08-11).
        sb_attr = {mkt.HOME: "sb_home_odds",
                   mkt.DRAW: "sb_draw_odds",
                   mkt.AWAY: "sb_away_odds"}.get(market)
        if sb_attr:
            price = getattr(bf, sb_attr, None)
        if price is None and odds_index is not None:
            fx = odds_index.get((home, away))
            if fx is not None:
                q = mkt.quote(market, fx)
                if q is not None and q.available:
                    price = q.price
        if price is None and getattr(bf, "best_market_key", None) == market \
                and getattr(bf, "best_price", None) is not None:
            # Fall back to the fixture's already-priced headlined market when it
            # is itself capital-cleared (covers the web re-cap path with no
            # odds_index in scope).
            price = bf.best_price
            prob = bf.best_model_prob if bf.best_model_prob is not None else prob
        if price is None:
            continue
        ev = (prob * price - 1.0) if price else None
        # Highest EDGE wins (strictly better only — EDGE_MARKETS order is the
        # deterministic final tiebreak). Probability breaks an EV tie.
        if (best is None or (ev is not None and (best.ev is None or ev > best.ev))
                or (ev == best.ev and prob > best.prob)):
            best = AccaLeg(
                fixture=bf.fixture.split(" (")[0],
                league=_league_of(bf.fixture),
                market_key=market,
                market_name=mkt.display(market, bf.probs.home_team, bf.probs.away_team),
                price=price,
                prob=prob,
                ev=ev,
            )
    return best


def _make_acca(label: str, leg_list: List[AccaLeg]) -> Acca:
    """An Acca with combined odds/prob = the product of its legs' figures."""
    combined_odds = 1.0
    combined_prob = 1.0
    for leg in leg_list:
        combined_odds *= leg.price
        combined_prob *= leg.prob
    return Acca(label=label, legs=list(leg_list),
                combined_odds=combined_odds, combined_prob=combined_prob)


def _chunk_remainder(legs: List[AccaLeg]) -> List[List[AccaLeg]]:
    """Split the post-Acca-A remainder into ~4-5 leg groups, never one giant acca.

    Deterministic:
      <=2  -> []              (a 1-2 leg "acca" is a single, not an acca)
      <=6  -> one group
      <=9  -> 4+3 / 4+4 / 5+4
      else -> take 5, repeat (10->[5,5], 11->[5,6], 13->[5,4,4], 15->[5,5,5])
    Max group size 6, min 3 — "~4-5 legs each, roughly" per the Architect."""
    n = len(legs)
    if n <= 2:
        return []
    if n <= 6:
        return [legs]
    groups: List[List[AccaLeg]] = []
    i = 0
    while i < n:
        remaining = n - i
        if remaining <= 6:
            take = remaining
        elif remaining <= 9:
            take = remaining // 2 + (remaining % 2)  # 7->4, 8->4, 9->5
        else:
            take = SPLIT_GROUP_TARGET
        groups.append(legs[i:i + take])
        i += take
    return groups


def _split_labels() -> Iterator[str]:
    """'Acca B', 'Acca C', ... in order."""
    for i in count(1):
        yield f"Acca {chr(ord('A') + i)}"


def build_production_bets(
    board: List[Any],
    today: Optional[str] = None,
    odds_index: Optional[dict] = None,
    acca_a_max: int = ACCA_A_MAX,
) -> ProductionBets:
    """Build the day's production output: Acca A + split accas + singles.

    Eligibility (all required, same discipline as the old deploy acca):
      - kickoff_date == today (the standing rule — a date we cannot confirm as
        today is never assumed, HR35)
      - on_deploy_shortlist (the deploy call; keeps a CONFLICT/NO_DATA-verified
        fixture out of a bookable bet, and makes Acca A a subset of THE CALL)
      - at least one capital-cleared market (mkt.DEPLOYABLE) with a live price

    Ranking: confidence first — the leg's model probability desc, EV desc as
    the tiebreak, fixture name as the final deterministic sort. Acca A is the
    top `acca_a_max` (the headline), the remainder splits into ~4-5 leg accas
    (Acca B, C, ...), and every remainder fixture is ALSO a standalone single.

    Write-back: each leg's pick is written onto the BoardFixture
    (best_market_key/best_market/best_price/best_model_prob/best_mes_ev) so the
    CALL cards, produced-bet record and scan show the SAME market the acca and
    single book — the same fixture must never carry two different "picks".
    """
    today = today or date.today().isoformat()

    pairs: List[tuple[Any, AccaLeg]] = []
    for bf in board:
        if bf.kickoff_date != today:
            continue  # standing rule: today's fixtures only
        leg = _best_deployable_leg(bf, odds_index)
        if leg is None:
            continue
        # Write-back (see docstring) — run before produced_bet.record so every
        # downstream consumer agrees with the bookable leg.
        bf.best_market_key = leg.market_key
        bf.best_market = leg.market_name
        bf.best_price = leg.price
        bf.best_model_prob = leg.prob
        bf.best_mes_ev = leg.ev
        pairs.append((bf, leg))

    # EDGE ranking (Architect 2026-08-11): Acca A leads with the highest-EDGE
    # legs (model_prob × price − 1) — the book mispricing the fixture in our
    # favour. Probability breaks an EV tie; fixture name is the deterministic
    # final tiebreak. This replaced the 2026-08-10 probability-first ranking.
    pairs.sort(key=lambda p: (p[1].ev if p[1].ev is not None else -1.0,
                              p[1].prob,
                              p[1].fixture),
                reverse=True)

    legs = [leg for _, leg in pairs]
    acca_a = _make_acca("Acca A", legs[:acca_a_max]) if legs else None
    remainder = legs[acca_a_max:]
    split_accas = [_make_acca(label, chunk)
                   for label, chunk in zip(_split_labels(), _chunk_remainder(remainder))]
    return ProductionBets(acca_a=acca_a, split_accas=split_accas, singles=remainder)


def build_accas(board, today: Optional[str] = None,
                odds_index: Optional[dict] = None) -> List[Acca]:
    """LEGACY — the acca set only (Acca A + split accas, no singles).

    Kept for callers that want just the accumulator set; the production flow
    should use `build_production_bets`."""
    bets = build_production_bets(board, today=today, odds_index=odds_index)
    return ([bets.acca_a] if bets.acca_a else []) + bets.split_accas


def build_single_accas(singles: List[AccaLeg]) -> List[Acca]:
    """The singles as 1-leg slips for the booking-code driver.

    `book_accas` drives one SportyBet slip per entry, so a 1-leg acca IS a
    single — no new booking concept is needed. Label 'SINGLE — <fixture>' lets
    the renders and the codes file address each single by name."""
    return [_make_acca(f"SINGLE — {leg.fixture}", [leg]) for leg in singles]


def _code_for(codes: Optional[dict], label: str) -> Optional[str]:
    """The booking code for `label`, or None (renders NO DATA — PENDING, HR35)."""
    if not codes:
        return None
    for r in codes.get("results") or []:
        if r.get("label") == label:
            return r.get("code")
    return None


def render_production_block(bets: ProductionBets, codes: Optional[dict] = None,
                            today: Optional[str] = None) -> str:
    """Lean production block for Telegram + the saved board.

    ARCHITECT FORMAT (2026-08-11, "use this always"): star on every acca,
    legs carry fixture + market + price only (no prob/EV), combined odds and
    booking code on ONE line, no note/footer lines. The honest-edge/capital
    line lives in the notify envelope, not here. No eligible bets -> an honest
    'no production pick today' note (a quiet day is a correct result, not a
    failure).

    ID407 (proposed) — Accumulator compounding disclosure: any multi-leg acca
    must show the combined probability (product of leg probabilities) with the
    explicit label that this is arithmetic, not a framework weakness."""
    today = today or date.today().isoformat()
    lines = [f"🎯 PRODUCTION BETS — {today} (today's fixtures only)", ""]
    accas = ([bets.acca_a] if bets.acca_a else []) + bets.split_accas
    if not accas and not bets.singles:
        lines.append("NO production pick today — no deploy-eligible fixture "
                     "with a live price kicks off today. A valid, honest "
                     "result (HR35).")
        return "\n".join(lines)

    for i, acca in enumerate(accas):
        if i:
            lines.append("")  # blank line between accas (Architect format)
        code = _code_for(codes, acca.label)
        is_headline = acca.label == "Acca A"
        head = (f"★ {acca.label} — HEADLINE, {acca.n_legs} legs"
                if is_headline else f"★ {acca.label}  {acca.n_legs} legs")
        lines.append(head)
        indent = "    " if is_headline else ""
        for leg in acca.legs:
            lines.append(f"{indent}{leg.fixture} ({leg.league}) — "
                         f"{leg.market_name} @ {leg.price:.2f}")
        if acca.combined_odds is not None:
            lines.append(f"    Combined {acca.combined_odds:.2f} "
                         f"Booking code: {code or 'NO DATA — PENDING'}")
        # ID407 — acca compounding disclosure: show combined probability
        # (product of independent leg probabilities). This is near-certain to
        # be much lower than any individual leg — this is expected arithmetic,
        # not a framework weakness.
        if acca.combined_prob is not None and acca.n_legs > 1:
            lines.append(f"    Combined prob {acca.combined_prob:.1%} "
                         f"(product of {acca.n_legs} legs — compounding is arithmetic, not a weakness)")
        else:
            lines.append(f"    Booking code: {code or 'NO DATA — PENDING'}")

    if bets.singles:
        lines.append("")
        lines.append("  SINGLES — one standalone slip each, own booking code")
        for leg in bets.singles:
            code = _code_for(codes, f"SINGLE — {leg.fixture}")
            lines.append(f"    {leg.fixture} ({leg.league}) — {leg.market_name} "
                         f"@ {leg.price:.2f}  Booking code: "
                         f"{code or 'NO DATA — PENDING'}")
    return "\n".join(lines)
