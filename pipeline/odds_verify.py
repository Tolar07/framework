"""
ID403 F2 quorum for live odds: stamp a price VERIFIED when two INDEPENDENT
T1 sources agree, CONFLICT when they disagree, SINGLE-SOURCE otherwise.

WHY
  id403.py already defines F2 — "two independent T1/T2 domains agree" — for
  factual claims. This applies the same idea to entry prices: the-odds-api and
  football-data.co.uk are two independent T1 domains, so when both quote the
  same fixture/market within tolerance, the price earns a VERIFIED stamp
  instead of SINGLE-SOURCE. A disagreement beyond tolerance is a CONFLICT and is
  surfaced, never averaged away (HR35).

SCOPE — READ THIS
  This is PROVENANCE ONLY. It annotates FixtureOdds.verification; nothing in the
  framework branches on that field for capital, deployment, or publishing. Wiring
  a VERIFIED requirement (or a CONFLICT block) into any capital gate is an
  ARCHITECT-ONLY change under the Protected Constants (the odds tolerance check),
  and the tolerance below would have to be ratified as a constant first. This
  module deliberately stops at the honest label.
"""
from __future__ import annotations

from typing import Optional

from pipeline.odds import FixtureOdds, MarketQuote

VERIFIED = "VERIFIED"
SINGLE_SOURCE = "SINGLE-SOURCE"
CONFLICT = "CONFLICT"

# How close two decimal prices must be to count as the same quote, as a
# percentage of their mean. PROVENANCE-ONLY DEFAULT — deliberately loose, since
# two books/feeds legitimately differ by a few percent. It is NOT ratified for
# any capital gate; the Architect must set the operative value before this
# figure influences a deployment decision (Protected Constants: odds tolerance).
ODDS_AGREEMENT_TOLERANCE_PCT = 5.0

# The five markets carried on a FixtureOdds, checked pairwise.
_MARKETS = ("home", "draw", "away", "over25", "under25")


def prices_agree(a: Optional[float], b: Optional[float],
                 tol_pct: float = ODDS_AGREEMENT_TOLERANCE_PCT) -> Optional[bool]:
    """True/False if both prices exist; None if either is missing (can't judge).

    Agreement is |a-b| as a percentage of the mean <= tol_pct."""
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return abs(a - b) / ((a + b) / 2.0) * 100.0 <= tol_pct


def _classify(primary: FixtureOdds, secondary: FixtureOdds,
              tol_pct: float) -> tuple[str, list[str]]:
    """Compare two quotes for the same fixture across their shared markets.

    VERIFIED  — at least one market is quoted by both and every co-quoted market
                agrees within tolerance.
    CONFLICT  — at least one co-quoted market disagrees beyond tolerance.
    SINGLE-SOURCE — the sources share no priced market (nothing to corroborate).
    Independence is required: two quotes from the SAME source can't corroborate."""
    notes: list[str] = []
    if primary.source == secondary.source:
        return SINGLE_SOURCE, ["same source — not independent, cannot corroborate"]

    compared = 0
    conflicts: list[str] = []
    for m in _MARKETS:
        pa = getattr(primary, m).price
        pb = getattr(secondary, m).price
        verdict = prices_agree(pa, pb, tol_pct)
        if verdict is None:
            continue
        compared += 1
        if verdict is False:
            conflicts.append(f"{m}: {pa} vs {pb}")

    if compared == 0:
        return SINGLE_SOURCE, ["no co-quoted market to corroborate"]
    if conflicts:
        notes.append("price CONFLICT beyond "
                     f"{tol_pct:.1f}% — {'; '.join(conflicts)}")
        return CONFLICT, notes
    notes.append(f"F2 quorum: {primary.source} & {secondary.source} agree on "
                 f"{compared} market(s) within {tol_pct:.1f}%")
    return VERIFIED, notes


def cross_verify(primary: list[FixtureOdds], secondary: list[FixtureOdds],
                 tol_pct: float = ODDS_AGREEMENT_TOLERANCE_PCT
                 ) -> tuple[list[FixtureOdds], list[str]]:
    """Stamp each PRIMARY fixture's .verification against the SECONDARY source.

    Returns the same primary fixtures (mutated in place) plus summary flags.
    Fixtures with no secondary counterpart stay SINGLE-SOURCE. Never drops or
    rewrites a price — only labels its provenance."""
    index = {(f.home_team, f.away_team): f for f in secondary}
    flags: list[str] = []
    counts = {VERIFIED: 0, CONFLICT: 0, SINGLE_SOURCE: 0}

    for fx in primary:
        match = index.get((fx.home_team, fx.away_team))
        if match is None:
            fx.verification = SINGLE_SOURCE
            counts[SINGLE_SOURCE] += 1
            continue
        tier, notes = _classify(fx, match, tol_pct)
        fx.verification = tier
        fx.notes.extend(notes)
        counts[tier] += 1

    flags.append(
        f"cross-verify: {counts[VERIFIED]} VERIFIED, {counts[CONFLICT]} CONFLICT, "
        f"{counts[SINGLE_SOURCE]} SINGLE-SOURCE (tolerance {tol_pct:.1f}%)")
    return primary, flags


def fetch_odds_verified(league: str,
                        tol_pct: float = ODDS_AGREEMENT_TOLERANCE_PCT
                        ) -> tuple[list[FixtureOdds], list[str]]:
    """Primary prices (the-odds-api) cross-checked against football-data.

    OPT-IN and not yet wired into run_daily: it always pulls the free
    football-data source in addition to the primary, purely to stamp provenance.
    Activate by switching run_daily's fetch_odds_chained call to this once the
    Architect has reviewed the tolerance and decided whether CONFLICT/VERIFIED
    should ever influence a decision (today they do not)."""
    from pipeline.odds import fetch_odds, QuotaExhausted
    from pipeline.odds_footballdata import fetch_odds_footballdata

    flags: list[str] = []
    primary: list[FixtureOdds] = []
    try:
        primary, pf = fetch_odds(league)
        flags += pf
    except (QuotaExhausted, ValueError, RuntimeError) as e:
        flags.append(f"{league}: primary odds unavailable for cross-verify ({e})")
    except Exception as e:  # noqa: BLE001 — degrade to whatever the fallback gives
        flags.append(f"{league}: primary odds error in cross-verify ({e})")

    try:
        secondary, sf = fetch_odds_footballdata(league)
        flags += sf
    except Exception as e:  # noqa: BLE001
        secondary = []
        flags.append(f"{league}: football-data unavailable for cross-verify ({e})")

    if primary and secondary:
        verified, vf = cross_verify(primary, secondary, tol_pct)
        return verified, flags + vf
    # Only one source produced anything — return it as SINGLE-SOURCE (default),
    # preferring the primary if present, else the fallback.
    return (primary or secondary), flags
