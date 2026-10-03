"""Match context: rest, congestion and competition stage.

ARCHITECT DIRECTIVE 2026-09-19
"Always factor the motivation into the engine decision." Asked how strongly,
the Architect chose a BOUNDED, LOGGED adjustment over an unbounded one.

WHAT THE MODEL COULD NOT SEE BEFORE THIS
The probability stack is Dixon-Coles + Elo + xG + bookmaker consensus: entirely
historical form and market data. A side resting players before a European tie,
a team on its third match in eight days, a cup round a manager does not care
about — none of it reached the model. A grep for motivation, rest days,
congestion, rotation, team news, derby and relegation returned nothing.

WHY BOUNDED
Heartbeat grading began on 2026-09-19 and has exactly one day of settled
results behind it. Layering an unvalidated context signal at full strength
onto an unvalidated goal model makes failure unattributable: when a pick is
wrong you cannot tell whether the goal model or the context weight caused it.
MAX_ADJUSTMENT caps the total swing so the goal model stays dominant while the
context effect accumulates enough logged observations to be measured.

Every adjustment records its own reasons, so `ContextAdjustment.reasons` can be
audited against outcomes later. That audit is the point of shipping it small.

NOT MODELLED — team news and injuries.
The Architect asked for these. API-Football exposes /injuries, but this key's
plan does not: probed 2026-09-19 and it returned
    "Free plans do not have access to this season, try from 2022 to 2024."
So lineups and injury lists are genuinely unavailable, not merely unbuilt.
`ContextAdjustment` leaves `injury_factor` at 1.0 and says so in `missing`,
rather than silently pretending the signal is present (HR35). Wiring a
provider in is a plan upgrade plus a source-validation pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# Hard ceiling on the TOTAL multiplicative swing from all context signals
# combined. 0.10 = a side's strength may move at most +/-10%. The goal model
# must stay the dominant term while this is unvalidated.
MAX_ADJUSTMENT = 0.10

# Rest-day thresholds. Sub-72-hour turnarounds are the best-evidenced fatigue
# effect in the literature; beyond roughly a week extra rest stops helping and
# can hurt (match sharpness), so the curve is not monotonic.
SHORT_REST_DAYS = 3        # <= this is a congested turnaround
NORMAL_REST_DAYS = 6       # the ordinary weekly cycle
LONG_LAYOFF_DAYS = 14      # beyond this, rustiness rather than freshness

# Congestion window and threshold.
CONGESTION_WINDOW_DAYS = 14
CONGESTION_HEAVY = 5       # matches in the window that count as heavy load

# Per-signal magnitudes, deliberately small. These are priors, not fitted
# values -- nothing here has been calibrated against OLP XDV outcomes yet, and
# labelling them as priors is the honest description until it has.
SHORT_REST_PENALTY = 0.04      # <=3 days since last match
LONG_LAYOFF_PENALTY = 0.02     # >14 days idle
CONGESTION_PENALTY = 0.03      # >=5 matches in 14 days
CUP_ROTATION_PENALTY = 0.03    # domestic cup: rotation risk for the bigger side


@dataclass
class ContextAdjustment:
    """A bounded, auditable context adjustment for one fixture.

    `home_factor` / `away_factor` multiply that side's attacking strength.
    1.0 = no change. Both are clamped into [1-MAX_ADJUSTMENT, 1+MAX_ADJUSTMENT].
    """
    home_factor: float = 1.0
    away_factor: float = 1.0
    home_rest_days: Optional[int] = None
    away_rest_days: Optional[int] = None
    home_matches_14d: Optional[int] = None
    away_matches_14d: Optional[int] = None
    injury_factor: float = 1.0
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def is_neutral(self) -> bool:
        return self.home_factor == 1.0 and self.away_factor == 1.0


def _clamp(v: float) -> float:
    return max(1.0 - MAX_ADJUSTMENT, min(1.0 + MAX_ADJUSTMENT, v))


def _rest_days(match_dates: list[str], kickoff: str) -> Optional[int]:
    """Days between a team's previous match and this kickoff.

    None when no prior match is known -- that is reported as missing, never
    treated as "well rested" (which would be a silent guess, HR35).
    """
    try:
        ko = date.fromisoformat(kickoff)
    except (ValueError, TypeError):
        return None
    prior = [date.fromisoformat(d) for d in match_dates
             if d and date.fromisoformat(d) < ko]
    if not prior:
        return None
    return (ko - max(prior)).days


def _matches_in_window(match_dates: list[str], kickoff: str,
                       window: int = CONGESTION_WINDOW_DAYS) -> Optional[int]:
    try:
        ko = date.fromisoformat(kickoff)
    except (ValueError, TypeError):
        return None
    start = ko - timedelta(days=window)
    return sum(1 for d in match_dates
               if d and start <= date.fromisoformat(d) < ko)


def _side_factor(rest: Optional[int], load: Optional[int],
                 reasons: list[str], side: str) -> float:
    """Combine one side's rest and congestion into a strength multiplier."""
    factor = 1.0
    if rest is not None:
        if rest <= SHORT_REST_DAYS:
            factor -= SHORT_REST_PENALTY
            reasons.append(f"{side}: {rest}d rest (short turnaround)")
        elif rest > LONG_LAYOFF_DAYS:
            factor -= LONG_LAYOFF_PENALTY
            reasons.append(f"{side}: {rest}d idle (long layoff)")
    if load is not None and load >= CONGESTION_HEAVY:
        factor -= CONGESTION_PENALTY
        reasons.append(f"{side}: {load} matches in {CONGESTION_WINDOW_DAYS}d")
    return factor


def _is_domestic_cup(league: str) -> bool:
    lg = (league or "").lower()
    return any(tok in lg for tok in
               ("cup", "pokal", "copa", "coppa", "taça", "taca", "trophy"))


def build_context(home_team: str, away_team: str, league: str, kickoff_date: str,
                  home_match_dates: Optional[list[str]] = None,
                  away_match_dates: Optional[list[str]] = None
                  ) -> ContextAdjustment:
    """Compute the bounded context adjustment for one fixture.

    `*_match_dates` are that team's known recent match dates (ISO). Pass None
    when unknown -- the signal is then recorded in `missing` and contributes
    nothing, rather than defaulting to a neutral value that looks measured.
    """
    adj = ContextAdjustment()

    if home_match_dates is None:
        adj.missing.append("home match history")
    if away_match_dates is None:
        adj.missing.append("away match history")
    adj.missing.append("team news / injuries (API-Football plan does not cover "
                       "this season)")

    if home_match_dates is not None:
        adj.home_rest_days = _rest_days(home_match_dates, kickoff_date)
        adj.home_matches_14d = _matches_in_window(home_match_dates, kickoff_date)
    if away_match_dates is not None:
        adj.away_rest_days = _rest_days(away_match_dates, kickoff_date)
        adj.away_matches_14d = _matches_in_window(away_match_dates, kickoff_date)

    hf = _side_factor(adj.home_rest_days, adj.home_matches_14d, adj.reasons, "home")
    af = _side_factor(adj.away_rest_days, adj.away_matches_14d, adj.reasons, "away")

    # Competition stage. A domestic cup tie carries rotation risk for BOTH
    # sides, so it is applied symmetrically: without team news we cannot tell
    # which manager is resting whom, and guessing that the favourite rotates
    # would be exactly the unfounded inference this module must avoid.
    if _is_domestic_cup(league):
        hf -= CUP_ROTATION_PENALTY
        af -= CUP_ROTATION_PENALTY
        adj.reasons.append(f"domestic cup ({league}): rotation risk both sides")

    adj.home_factor = round(_clamp(hf), 4)
    adj.away_factor = round(_clamp(af), 4)
    return adj
