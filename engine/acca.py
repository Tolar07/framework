"""ACCA BUILDER — the day's deploy call folded into a 4-leg accumulator set.

STANDING RULE (Architect 2026-08-09)
  The product bet draws ONLY from fixtures kicking off TODAY — nothing else.
  The wider scan (PART 2 / scan tables) stays the 3-day reference window, but
  every leg of the produced bet, THE CALL and the acca comes from today's slate.

WHAT THIS BUILDS
  Up to three 4-leg accumulators (Acca 1 / 2 / 3) from today's deploy-eligible
  shortlist, so the Architect gets a choice at the end of production. Each leg
  is priced on the live line in a CAPITAL-CLEARED market — mkt.DEPLOYABLE
  (ID405 market gate opened 2026-08-10: all five markets — 1X2 Home/Draw/Away,
  Over/Under 1.5, Over/Under 2.5, BTTS, Double Chance — are now deployable).
  If the market gate changes, the acca follows it automatically.

HONESTY (HR35 carried through)
  - A fixture with no kickoff date is NOT in the acca — a date we cannot
    confirm as today cannot be bet as today (never assumed).
  - Fewer than 4 today fixtures -> a SHORTENED acca, never padded with a
    tomorrow fixture and never a fabricated leg.
  - Combined chance is the product of the legs' chances, stated as such:
    legs are not independent, so it is information, not encouragement.
  - An acca is a product shape, NOT a demonstrated edge. The backtest is
    negative; the block carries the honest line.

PHASE 2
  This module only NAMES and PRICES the acca. It never places, never stakes.
  Booking codes are generated separately (booking/booking_codes.py) for the
  Architect's review; capital authority stays with the Architect.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional

from engine import markets as mkt

MAX_ACCAS = 3        # the Architect's "a set of 4-leg acca in 2 or 3 places"
LEGS_PER_ACCA = 4    # a 4-leg acca, per the Architect


@dataclass
class AccaLeg:
    """One leg of an accumulator: a fixture + the capital-cleared market to back."""
    fixture: str          # "Home v Away" (model keys, board fixture name)
    league: str
    market_key: str       # canonical key, e.g. mkt.DRAW
    market_name: str      # words, e.g. "Draw" (HR53 — no bare glyphs)
    price: float          # decimal odds on the live line
    prob: float           # model probability for that market
    ev: Optional[float]   # model_prob * price - 1, when computable
    softness_tier: str = "?"
    sportybet_fixture_id: Optional[str] = None  # set by the booking step


@dataclass
class Acca:
    """One 4-leg accumulator."""
    label: str            # "Acca 1"
    legs: List[AccaLeg] = field(default_factory=list)
    combined_odds: Optional[float] = None
    combined_prob: Optional[float] = None

    @property
    def n_legs(self) -> int:
        return len(self.legs)


def _league_of(fixture: str) -> str:
    """'Home v Away (League)' -> 'League'. Mirrors the board's league tag."""
    return fixture.split(" (")[-1].rstrip(")") if " (" in fixture else "—"


def _best_deployable_leg(bf, odds_index: Optional[dict]) -> Optional[AccaLeg]:
    """The best CAPITAL-CLEARED market for one fixture, priced on the live line.

    Returns None when the fixture has no model probs, no deployable market with
    a live price, or is not rated — a leg we cannot price is not a leg (HR35)."""
    if bf.probs is None or not getattr(bf, "on_deploy_shortlist", False):
        return None
    home, away = _team_pair(bf)

    best: Optional[AccaLeg] = None
    for market in mkt.DEPLOYABLE:
        prob = mkt.model_prob(market, bf.probs)
        if prob is None:
            continue
        price = None
        # SportyBet first for the markets it carries (1X2) — it is the book the
        # Architect actually bets at. The Odds API covers the rest (totals).
        if market == mkt.DRAW:
            price = getattr(bf, "sb_draw_odds", None)
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
        if best is None or (ev is not None and (best.ev is None or ev > best.ev)):
            best = AccaLeg(
                fixture=bf.fixture.split(" (")[0],
                league=_league_of(bf.fixture),
                market_key=market,
                market_name=mkt.display(market, bf.probs.home_team, bf.probs.away_team),
                price=price,
                prob=prob,
                ev=ev,
                softness_tier=bf.softness_tier,
            )
    return best


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


def build_accas(
    board: List[Any],
    today: Optional[str] = None,
    odds_index: Optional[dict] = None,
    max_accas: int = MAX_ACCAS,
    legs_per: int = LEGS_PER_ACCA,
) -> List[Acca]:
    """Build up to `max_accas` four-leg accas from TODAY's deploy shortlist.

    Eligibility (all required):
      - kickoff_date == today (the standing rule — a fixture without a date is
        never assumed to be today, HR35)
      - on_deploy_shortlist (the deploy call)
      - at least one capital-cleared market (mkt.DEPLOYABLE) with a live price

    Ranking: strongest EV first (model probability is the tiebreak), so Acca 1
    is the best-conviction set. Accas draw from disjoint slices of the ranked
    pool, so Acca 1 / 2 / 3 are genuinely different combinations. Fewer than
    `legs_per` fixtures -> a shortened acca, honestly labelled."""
    today = today or date.today().isoformat()

    legs: List[AccaLeg] = []
    for bf in board:
        if bf.kickoff_date != today:
            continue  # standing rule: today's fixtures only
        leg = _best_deployable_leg(bf, odds_index)
        if leg is not None:
            legs.append(leg)

    # Rank by EV desc, probability desc as the tiebreak (a higher-probability
    # leg at equal EV is the stronger pick).
    def _key(leg: AccaLeg) -> tuple[float, float]:
        return (leg.ev if leg.ev is not None else -1.0, leg.prob)
    legs.sort(key=_key, reverse=True)

    accas: List[Acca] = []
    for i in range(max_accas):
        pool = legs[i * legs_per:(i + 1) * legs_per]
        if not pool:
            break
        combined_odds = 1.0
        combined_prob = 1.0
        for leg in pool:
            combined_odds *= leg.price
            combined_prob *= leg.prob
        accas.append(Acca(
            label=f"Acca {i + 1}",
            legs=pool,
            combined_odds=combined_odds,
            combined_prob=combined_prob,
        ))
    return accas


def render_acca_block(accas: List[Acca], today: Optional[str] = None) -> str:
    """Human-readable acca block for the end of production.

    Renders every acca with its legs (fixture — market @ odds (prob)), combined
    odds and combined chance, and the honest lines. No accas -> an honest
    'no eligible today' note (a quiet day is a correct result, not a failure)."""
    today = today or date.today().isoformat()
    lines = [f"🎯 TODAY'S 4-LEG ACCA — {today} (today's fixtures only)"]
    if not accas:
        lines.append("NO ACCA today — no deploy-eligible fixture with a live "
                     "price kicks off today. A valid, honest result (HR35).")
        return "\n".join(lines)

    for acca in accas:
        lines.append(f"  {acca.label} — {acca.n_legs} legs")
        for leg in acca.legs:
            ev_txt = f", EV {leg.ev:+.1%}" if leg.ev is not None else ""
            lines.append(
                f"    {leg.fixture} ({leg.league}) — {leg.market_name} "
                f"@ {leg.price:.2f} ({round(leg.prob*100)}%){ev_txt}")
        if acca.combined_odds is not None:
            lines.append(f"    Combined {acca.combined_odds:.2f} "
                         f"(≈{round((acca.combined_prob or 0)*100)}% all four win — "
                         f"legs are not independent)")
        if acca.n_legs < LEGS_PER_ACCA:
            lines.append(f"    NOTE: only {acca.n_legs} eligible today — acca "
                         f"shortened, not padded (HR35)")

    lines.append("  Capital gate (ID405): all five markets are deployable (gate opened "
                 "2026-08-10 — no market blocked).")
    lines.append("  PAPER — Phase 2, zero capital. Booking codes are generated "
                 "for your review; YOU approve and paste.")
    lines.append("  HONEST EDGE LINE: excellent informed process, NOT a "
                 "demonstrated profitable edge. An acca multiplies variance.")
    return "\n".join(lines)
