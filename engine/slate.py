"""
ID402 — Matchday Slate Engine.

SOFTNESS TIERING RETIRED (2026-09-30, Architect's instruction): the old A/B/C/D
"softness" ranking is gone. Every whitelisted league is now BOTH scan- and
deploy-eligible — "all fixtures eligible", the Architect's standing position.
The DEPLOY shortlist is ranked purely by model conviction (with recent form as a
tie-breaker) and capped at DEPLOY_POOL_CAP; it no longer favours any league tier.

What this module still does:
  - Holds the league whitelist (ID401 / HR34: an unratified league is never
    silently included — it scans as NO DATA, never guessed).
  - The evidence-based MARKET GATE (below), which narrows what can carry capital.
  - Builds the capped DEPLOY shortlist.

It never claims any fixture is a good bet — only logged CLV (clv/) confirms edge.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

DEPLOY_POOL_CAP = 1000  # ID402 hard cap on THE CALL

# --- DEPLOY ODDS BAND (Architect's standing rule) ---------------------------
# A single is only deployable when its price sits inside this band:
#   * DEPLOY_ODDS_MAX = 2.00 — the hard ceiling. Above 2.0 the market is roughly
#     90/10 in the bookmaker's favour; the Architect treats anything over 2.0 as
#     a loss and never deploys it.
#   * DEPLOY_ODDS_MIN = 1.20 — the floor. Below this the return doesn't justify
#     the stake; 1.20+ is where the "assured outcome" picks live.
#   * DEPLOY_ODDS_SAFE = 1.50 — the safest target inside the band, used only to
#     rank/label; it is not a gate.
# This narrows what can carry capital (like the MARKET GATE); it never widens it.
DEPLOY_ODDS_MIN = 1.20
DEPLOY_ODDS_MAX = 2.00
DEPLOY_ODDS_SAFE = 1.50
# A deploy pick must be one the model rates MORE LIKELY TO WIN THAN LOSE.
# Without this floor, a fixture whose sensible markets sit just outside the
# band (e.g. 2.02, 2.05) fell back to whatever was left in band — a 37% Under
# the model expects to lose (2026-10-02 dry run). "Winnable" means >= 50%.
DEPLOY_MIN_MODEL_PROB = 0.50

# --- PICK TIERS (selection study, backtest/SELECTION_STUDY.md, 2026-10-02) ---
# Every fixture's pick is the in-band market with the highest CONSENSUS
# probability = average of the model and the de-vigged market. Tiers:
#   BANKER  straight win (1X2 home/away), model and market agree within
#           AGREE_PP and consensus >= BANKER_MIN. Walk-forward: 82% hit, +4%
#           ROI over 290 picks in two seasons (2024/25 out-of-sample: 80%, +3%).
#   SAFE    model and market agree within AGREE_PP (any market) — ~73% hit
#           but the short prices carry the margin (≈ -6% ROI).
#   SPLIT   model and market disagree by more than AGREE_PP — shown, never
#           deployed (model-only Under 2.5 picks hit 55%, -13% ROI).
#   MARKET  no model history: market-implied only, no edge claimed.
#   BOOK    model and market disagree: follow the BOOKMAKER's strongest
#           outcome (its pick won 73.1% vs the model's 71.0% in the study), so
#           every fixture stays in production. SPLIT is then only a fixture
#           with no in-band outcome the bookmaker rates >= 50%.
AGREE_PP = 0.07
BANKER_MIN = 0.70
# MARKET ANCHOR (improvement #4, backtest/ANCHOR_STUDY.md, 2026-10-02): the
# pick's chance = market + MODEL_WEIGHT x (model - market). The more weight on
# the model, the more over-confident the stated % (model alone: 4-5 pts too
# high) and the lower the hit rate; 0.25 keeps the % honest (calibration error
# <= 1.2 pts) while the model still counts. Agreement checks are unchanged.
MODEL_WEIGHT = 0.25
# CERTAINTY (2026-10-02): HIGH when model and bookmaker agree within this;
# MEDIUM within AGREE_PP; LOW otherwise or when only one source exists.
CERTAINTY_HIGH_PP = 0.03
TIER_RANK = {"BANKER": 0, "SAFE": 1, "VALUE": 1.5, "BOOK": 2, "MARKET": 3, "SPLIT": 4}


def in_deploy_band(price: Optional[float]) -> bool:
    """True when a decimal price is inside the Architect's deploy band
    [DEPLOY_ODDS_MIN, DEPLOY_ODDS_MAX] (inclusive). A missing price is NOT in
    band — no price, no deploy (HR35: never assume one)."""
    return price is not None and DEPLOY_ODDS_MIN <= price <= DEPLOY_ODDS_MAX

# ID401 league whitelist. Membership alone decides eligibility now — no tiers.
# Every league here is scan- AND deploy-eligible; anything not here is refused
# (HR34 default-ban), never silently scanned.
WHITELIST_LEAGUES = (
    "Eredivisie",
    "Danish Superliga",
    "Belgian Pro League",
    "Scottish Premiership",
    "Ekstraklasa",
    "HNL",
    "Championship",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Europa League",
    "Primeira Liga",
    "Premier League",
    "La Liga",
    "Champions League",
    "Conference League",       # added 2026-10-05 (market-implied, order 10)
    # Second tiers — MIDWEEK coverage (football-data history + SportyBet priced).
    "La Liga 2",
    "Serie B",
    "2. Bundesliga",
    "Ligue 2",
    # English lower tiers + FA Cup — added 2026-10-02 (full English Saturday card).
    "League One",
    "League Two",
    "National League",
    "FA Cup",
    # National teams — rated on the international results dataset
    # (data/international_source.py). Added 2026-09-30 at the Architect's request.
    "UEFA Nations League",
    # More European top flights — added 2026-10-05 (Architect: full coverage).
    "Turkish Super Lig",
    "Greek Super League",
    "Austrian Bundesliga",
    "Swiss Super League",
    "Eliteserien",             # Norway — calendar-year season (2026-10-05)
    "Allsvenskan",             # Sweden — calendar-year season (2026-10-05)
)

# --- MARKET GATE (ratified 2026-08-04, evidence below) ----------------------
#
# Measured on the 2024/25 walk-forward backtest, 5 leagues, corrected engine.
# Two markets are structurally negative — for the MODEL and for random
# selection alike, which is what makes them a market property rather than a
# model failing:
#
#     1X2 Away    -1.883%  t=-4.515  (606 legs)   placebo also -1.707%
#     Over 2.5    -0.716%  t=-2.783  (442 legs)
#
# Removing them flips the whole backtest from -0.404% to +0.326%. This gate
# only ever NARROWS what can be deployed — it can never admit a market that
# was previously excluded — so it is a conservative restriction, not a new
# licence. Capital authority is unchanged and remains the Architect's.
BLOCKED_DEPLOY_MARKETS = {}   # Architect 2026-08-10: all markets open


def market_blocked(market_name: str) -> Optional[str]:
    """Reason this market cannot carry capital, or None if it may.

    Matched on the plain-language market name the board renders, so the gate
    and the thing the Architect reads are the same string."""
    key = (market_name or "").strip().lower()
    for blocked, reason in BLOCKED_DEPLOY_MARKETS.items():
        if blocked in key:
            return reason
    return None


def is_whitelisted(league: str) -> bool:
    return league in WHITELIST_LEAGUES


# Deploy-eligibility is now identical to being whitelisted — kept as a named
# function so callers read intently rather than testing the tuple inline.
def is_deploy_eligible(league: str) -> bool:
    return is_whitelisted(league)


@dataclass
class SlateDecision:
    league: str
    scan_eligible: bool
    deploy_eligible: bool


def classify(league: str) -> SlateDecision:
    ok = is_whitelisted(league)
    return SlateDecision(league=league, scan_eligible=ok, deploy_eligible=ok)


def _confidence(c) -> float:
    """Ranking key: the model's strongest market probability for this fixture.

    Deliberately NOT an edge/EV figure — that would need a market price. Ranks by
    model conviction only. Fixtures with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    return max(probs.p_home, probs.p_draw, probs.p_away,
               probs.p_over_15, 1 - probs.p_over_15,
               probs.p_btts_yes, 1 - probs.p_btts_yes)


def build_deploy_shortlist(candidates: list) -> list:
    """The DEPLOY shortlist: highest model conviction first, capped at
    DEPLOY_POOL_CAP. No league tiering — every candidate competes on conviction
    alone, with recent form (engine.form, bounded [-1,1]) as the tie-breaker.

    Candidates are expected to be deploy-eligible already (their league is
    whitelisted); this ranks and caps them. Form can only reorder near-equal
    picks, never manufacture conviction."""
    # Rank on the DEPLOY PICK's own probability (the in-band market actually
    # booked), not the fixture's strongest market overall — otherwise a fixture
    # whose best market is out of band outranks a stronger in-band pick (the
    # 2026-10-02 Latvia drop). Model-backed picks rank ahead of market-implied
    # ones (engine.market_implied): the latter carry no model edge by design.
    def _pick_conf(c) -> float:
        bp = getattr(c, "best_model_prob", None)
        return bp if bp is not None else _confidence(c)

    ranked = sorted(
        candidates,
        key=lambda c: (TIER_RANK.get(getattr(c, "tier", None) or "", 1),
                       getattr(c, "prob_source", "model") == "market",
                       -_pick_conf(c),
                       -(getattr(c, "form_support", None) or 0.0)))
    return ranked[:DEPLOY_POOL_CAP]
