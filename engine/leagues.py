"""
Unified league pool (ID401) — the whitelist, with no softness.

The softness A/B/C/D ranking (ID402) and every trace of a "softness tier" were
removed by Architect order (2026-08-10, finished 2026-08-11). There is ONE
pool: every whitelisted league is scan- AND deploy-eligible; a league off the
whitelist (HR34) is neither. No tier priority, no deploy cap, no scan-only
class.

The ID405 MARKET GATE was also opened (2026-08-10, Architect order): every
market may carry capital again. `engine/markets.py` BLOCKED is empty;
`build_deploy_shortlist` still calls `mkt.blocked()` as a structural backstop so
a future market gate would be honoured automatically, but today it never blocks.

The whitelist itself (ID401) remains the single source of truth for league
eligibility — a league on it is deploy-eligible, a league off it is not.
"""
from __future__ import annotations

# Section 7.4 — the ID401 whitelist. A single unified pool. Kept sorted; HR34:
# a league not listed here is never scan- or deploy-eligible.
# "Conference League" (UEFA Europa Conference League) was added 2026-08-10 —
# it was already in the cross-league fit pool (BRIDGE_COMPETITIONS, API-Football
# id 848) and IS modelled; the honest caveat is that its current-season FIXTURES
# source is still being wired (football-data.co.uk does NOT carry it; see
# competition_catalogue.py). The name is the framework-internal "Conference
# League", exactly like "Champions League"/"Europa League" drop the UEFA prefix.
WHITELISTED_LEAGUES: list[str] = [
    "Austrian Bundesliga",
    "Belgian Pro League",
    "Bundesliga",
    "Champions League",
    "Championship",
    "Conference League",
    "Danish Superliga",
    "EFL Cup",
    "Ekstraklasa",
    "Eredivisie",
    "Europa League",
    "HNL",
    "La Liga",
    "Ligue 1",
    "Premier League",
    "Primeira Liga",
    "Scottish Premiership",
    "Serie A",
]


def is_deploy_eligible(league: str) -> bool:
    """A whitelisted league is deploy-eligible (unified pool, no tiers). HR34
    still excludes a league that is not on the whitelist at all."""
    return league in WHITELISTED_LEAGUES


def _confidence(c) -> float:
    """Ranking key: the model's strongest market probability.

    Ranks by model conviction only — what the engine actually knows. Fixtures
    with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    # p_home / p_draw / p_away / 1-p_over_25 are the model's probabilities for
    # the deployable markets. A STRETCH 1X2-only rating (ClubElo fallback) has
    # no goals opinion — its p_over_25 is None, so the goals market is skipped
    # rather than crashing (HR35).
    over25 = probs.p_over_25
    return float(max(probs.p_home, probs.p_draw, probs.p_away,
                     1.0 - over25 if over25 is not None else 0.0))


def call_key(c) -> tuple:
    """THE CALL ranking key: PRICED picks ahead of unpriced, then expected value
    descending (best_mes_ev, set by run_daily after the odds pull) — unpriced
    rows rank by model conviction as a fallback.

    EV is the figure that actually decides a bet, so every fixture with a live
    price outranks one without (conviction is unmeasurable against a number).
    Without the priced-first separator, a 70%-confident unpriced row's key could
    beat a +20%-EV priced row and the CALL would read wrong.

    Public so the renderer sorts THE CALL into the same order it was selected
    — otherwise the right picks are chosen but shown in scan order, which reads
    as if the ranking failed.

    No tier component: the unified pool ranks every league equally."""
    ev = getattr(c, "best_mes_ev", None)
    if ev is not None:
        return (0, -ev)          # priced first
    return (1, -_confidence(c))  # unpriced after


def build_deploy_shortlist(candidates: list) -> list:
    """The deploy shortlist over the unified pool: every market-gate-cleared
    fixture, ranked by call_key, NO cap.

    The ID405 MARKET GATE is enforced at this boundary as a structural
    backstop: a fixture whose headlined market is blocked (mkt.blocked) is
    excluded even though every league is deploy-eligible. The gate is open
    today (BLOCKED is empty), so nothing is excluded — but the check stays so
    the gate cannot silently widen later without going through engine/markets.py.
    """
    from engine import markets as mkt
    eligible = [c for c in candidates
                if not (getattr(c, "best_market_key", None)
                     and mkt.blocked(c.best_market_key))]
    return sorted(eligible, key=call_key)
