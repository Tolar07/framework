"""
ID403 F2 quorum for live odds — the price check, ON in the live loop since
2026-10-03 (Architect: "switch it on", no paid APIs).

WHAT IT DOES
  Every SportyBet price on the board's day is checked against independent
  books, all free:
    bet365 (Pinnacle / market average where bet365 is missing)
                       via football-data.co.uk fixtures.csv and
                       new_league_fixtures.csv
    DraftKings         via ESPN's scoreboard (data/espn_fixtures.py)
  For each match, the 1X2 and Over/Under 2.5 prices of both books are turned
  into margin-free chances (each book's overround removed) and compared:

    VERIFIED       at least one independent book agrees on every co-quoted
                   market within PRICE_CHECK_TOLERANCE_PP points
    CONFLICT       an independent book quotes the match and none agrees — the
                   gap is shown, never averaged away (HR35)
    SINGLE-SOURCE  no independent book quotes the match

WHY CHANCES, NOT RAW PRICES
  Two honest books differ on raw prices because their margins differ. Measured
  2026-10-03 on matches both carried: bet365 vs DraftKings raw prices were a
  median 4.5% apart and 38% of markets were more than 5% apart — a raw 5%
  test would have called most agreeing books a CONFLICT. With margins removed
  the same pairs sat within ~3 points, while a wrong match or swapped sides is
  10+ points out.

SCOPE — READ THIS
  This is PROVENANCE ONLY: it labels prices (FixtureOdds.verification,
  .price_note) and the board shows the label. Nothing branches on it for
  selection, staking or deployment. Making a CONFLICT block or demote a pick
  is an Architect decision, and PRICE_CHECK_TOLERANCE_PP would have to be
  ratified as a constant first.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from pipeline.odds import FixtureOdds, MarketQuote

VERIFIED = "VERIFIED"
SINGLE_SOURCE = "SINGLE-SOURCE"
CONFLICT = "CONFLICT"

# Margin-free chance points two books may differ by and still agree.
# PROVENANCE-ONLY DEFAULT, not ratified for any gate (see SCOPE).
PRICE_CHECK_TOLERANCE_PP = 5.0

# Raw-price tolerance kept for prices_agree(); not used by the live check.
ODDS_AGREEMENT_TOLERANCE_PCT = 5.0


def prices_agree(a: Optional[float], b: Optional[float],
                 tol_pct: float = ODDS_AGREEMENT_TOLERANCE_PCT) -> Optional[bool]:
    """True/False if both prices exist; None if either is missing (can't judge).

    Agreement is |a-b| as a percentage of the mean <= tol_pct."""
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return abs(a - b) / ((a + b) / 2.0) * 100.0 <= tol_pct


def chances(fx: FixtureOdds) -> dict[str, tuple[float, ...]]:
    """Margin-free chances per market group a book quotes in full:
    '1X2' -> (home, draw, away), 'O/U 2.5' -> (over, under)."""
    out: dict[str, tuple[float, ...]] = {}
    for group, keys in (("1X2", ("home", "draw", "away")), ("O/U 2.5", ("over25", "under25"))):
        prices = [getattr(fx, k).price for k in keys]
        if all(p is not None and p > 1.0 for p in prices):
            inv = [1.0 / p for p in prices]  # type: ignore[operator]
            total = sum(inv)
            out[group] = tuple(x / total for x in inv)
    return out


_LABELS = {"1X2": ("home", "draw", "away"), "O/U 2.5": ("over 2.5", "under 2.5")}


def _who(fx: FixtureOdds) -> str:
    """'DraftKings via ESPN', 'bet365 via football-data', … for the board."""
    if fx.source.startswith("espn.com"):
        return f"{fx.home.bookmaker or 'DraftKings'} via ESPN"
    if "football-data" in fx.source:
        book = (fx.home.bookmaker or "a book").replace(" (not a single book)", "")
        return f"{'market average' if book == 'avg' else book} via football-data"
    return fx.source


def _classify(primary: FixtureOdds, secondary: FixtureOdds,
              tol_pp: float) -> tuple[str, list[str]]:
    """Compare two books' margin-free chances for one match.

    VERIFIED      at least one market group is quoted by both and every
                  co-quoted chance agrees within tol_pp points.
    CONFLICT      at least one co-quoted chance differs by more.
    SINGLE-SOURCE no co-quoted group, or both quotes from the same source
                  (not independent, so it cannot corroborate)."""
    if primary.source == secondary.source:
        return SINGLE_SOURCE, ["same source — not independent, cannot corroborate"]
    a, b = chances(primary), chances(secondary)
    shared = [g for g in a if g in b]
    if not shared:
        return SINGLE_SOURCE, ["no co-quoted market to corroborate"]
    gaps = []
    for g in shared:
        for label, pa, pb in zip(_LABELS[g], a[g], b[g], strict=True):
            if abs(pa - pb) * 100 > tol_pp:
                gaps.append(f"{label} {pa:.0%} vs {pb:.0%}")
    who = _who(secondary)
    if gaps:
        return CONFLICT, [f"differs from {who}: SportyBet " + ", ".join(gaps)
                          + f" (margin removed, more than {tol_pp:g} pts apart)"]
    return VERIFIED, [f"agrees with {who} within {tol_pp:g} pts on "
                      + " and ".join(shared)]


def cross_verify(primary: list[FixtureOdds], secondary: list[FixtureOdds],
                 tol_pp: float = PRICE_CHECK_TOLERANCE_PP
                 ) -> tuple[list[FixtureOdds], list[str]]:
    """Stamp each PRIMARY fixture's .verification against ONE secondary source
    whose team names are the same keys (exact match).

    Returns the same primary fixtures (mutated in place) plus a summary flag.
    Never drops or rewrites a price — only labels its provenance."""
    index = {(f.home_team, f.away_team): f for f in secondary}
    counts = {VERIFIED: 0, CONFLICT: 0, SINGLE_SOURCE: 0}
    for fx in primary:
        match = index.get((fx.home_team, fx.away_team))
        if match is None:
            fx.verification = SINGLE_SOURCE
            counts[SINGLE_SOURCE] += 1
            continue
        tier, notes = _classify(fx, match, tol_pp)
        fx.verification = tier
        fx.price_note = notes[0]
        fx.notes.extend(notes)
        counts[tier] += 1
    return primary, [f"cross-verify: {counts[VERIFIED]} VERIFIED, {counts[CONFLICT]} CONFLICT, "
                     f"{counts[SINGLE_SOURCE]} SINGLE-SOURCE (tolerance {tol_pp:g} pts)"]


def espn_to_odds(ev) -> FixtureOdds:
    """An ESPN event's DraftKings line as a FixtureOdds (decimal prices)."""
    book = ev.provider or "DraftKings"

    def q(key: str) -> MarketQuote:
        p = ev.prices.get(key)
        return MarketQuote(price=p, bookmaker=book if p else None)
    return FixtureOdds(league=ev.league, home_team=ev.home, away_team=ev.away,
                       kickoff_utc=ev.kickoff_utc, home=q("home"), draw=q("draw"),
                       away=q("away"), over25=q("over25"), under25=q("under25"),
                       source=f"espn.com ({book})", source_tier="T2")


def _near(a: str, b: str) -> bool:
    try:
        return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days) <= 1
    except ValueError:
        return False


def check_prices(league: str, primary: list[FixtureOdds], days: set[str],
                 tol_pp: float = PRICE_CHECK_TOLERANCE_PP,
                 fetch_espn: Optional[Callable] = None,
                 fetch_fd: Optional[Callable] = None,
                 fetch_fd_extra: Optional[Callable] = None) -> list[str]:
    """The live price check for one league: every primary (SportyBet) quote
    kicking off on one of `days` is labelled against bet365 (football-data) and
    DraftKings (ESPN). Quotes on other days are left unchecked (blank label).
    Never raises for a source that is down — it is flagged and skipped."""
    from data import espn_fixtures
    from engine.fixture_match import find_match
    from pipeline.odds_footballdata import (
        EXTRA_COUNTRY,
        fetch_extra_footballdata,
        fetch_odds_footballdata,
    )
    fetch_espn = fetch_espn or espn_fixtures.fetch_day
    fetch_fd = fetch_fd or fetch_odds_footballdata
    fetch_fd_extra = fetch_fd_extra or fetch_extra_footballdata

    todo = [fx for fx in primary if fx.kickoff_utc[:10] in days]
    if not todo:
        return []
    flags: list[str] = []
    books: list[list[FixtureOdds]] = []
    try:
        fd, _ = (fetch_fd_extra if league in EXTRA_COUNTRY else fetch_fd)(league)
        books.append(fd)
    except Exception as e:  # noqa: BLE001
        flags.append(f"{league}: price check — football-data unavailable ({str(e)[:60]})")
    if league in espn_fixtures.SLUGS:
        from verification.fixture_check import _days_around
        espn_days = sorted({x for d in days for x in _days_around(d)})
        evs: list = []
        failed: list[str] = []
        for d in espn_days:
            try:
                evs += fetch_espn(league, d)
            except Exception as e:  # noqa: BLE001
                failed.append(f"{d} ({str(e)[:40]})")
        if failed:
            flags.append(f"{league}: price check — ESPN unavailable for " + ", ".join(failed))
        books.append([espn_to_odds(e) for e in evs])

    counts = {VERIFIED: 0, CONFLICT: 0, SINGLE_SOURCE: 0}
    for fx in todo:
        verdicts: list[tuple[str, list[str]]] = []
        for book in books:
            near = [b for b in book if _near(b.kickoff_utc, fx.kickoff_utc)]
            m = find_match(fx.home_team, fx.away_team, near, lambda b: (b.home_team, b.away_team))
            if m is not None:
                verdicts.append(_classify(fx, m.item, tol_pp))
        agree = [n for t, n in verdicts if t == VERIFIED]
        differ = [n for t, n in verdicts if t == CONFLICT]
        if agree:
            fx.verification, notes = VERIFIED, [x for n in agree for x in n]
        elif differ:
            fx.verification, notes = CONFLICT, [x for n in differ for x in n]
        else:
            fx.verification, notes = SINGLE_SOURCE, ["no independent book quotes this match"]
        fx.price_note = "; ".join(notes)
        fx.notes.extend(notes)
        counts[fx.verification] += 1
    flags.append(f"{league}: price check — {counts[VERIFIED]} agree with an independent "
                 f"book, {counts[CONFLICT]} differ, {counts[SINGLE_SOURCE]} unchecked "
                 f"(margin-free, {tol_pp:g} pts)")
    return flags


def fetch_odds_verified(league: str,
                        tol_pp: float = PRICE_CHECK_TOLERANCE_PP
                        ) -> tuple[list[FixtureOdds], list[str]]:
    """the-odds-api prices cross-checked against football-data (exact names).
    Kept for the metered fallback; the live loop uses check_prices()."""
    from pipeline.odds import QuotaExhausted, fetch_odds
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
        verified, vf = cross_verify(primary, secondary, tol_pp)
        return verified, flags + vf
    return (primary or secondary), flags
