"""
fixture_pick_integrity.py — fixes the root cause behind today's board:
fixtures and picks living in two separately-indexed lists that drifted
apart. Stuttgart showing up as the pick for a Hoffenheim v Dortmund
fixture, and M'gladbach v Elversberg silently losing its own data and
inheriting Hoffenheim v Dortmund's a second time, are both exactly what
happens when `fixtures[i]` and `picks[i]` stop being the same `i` partway
through a loop (one list gets filtered, reordered, or appended to
differently than the other).

The fix: ONE record per fixture, built by a keyed lookup (fixture_id ->
data), never by parallel list position. It is structurally impossible
for a FixtureRecord to show another fixture's pick, because the pick is
computed and attached to the SAME object as the fixture, never fetched
by a separate index into a separate list.

This also fixes the "defaults to 1X2 even when O1.5 is 89%" regression:
select_best_market() evaluates every scored market and returns the
actual highest-probability one, per the rule ratified 11 Aug — no
market gets special-cased to "try this first."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("fixture_pick_integrity")


@dataclass
class FixtureRecord:
    fixture_id: str          # e.g. "2026-09-02_Hoffenheim_Dortmund" — stable, unique
    league: str
    kickoff: str
    home: str
    away: str
    markets: dict[str, float] = field(default_factory=dict)  # {"O1.5": 0.89, "BTTS": 0.65, "Dortmund_win": 0.47, ...}
    market_ev: dict[str, float] = field(default_factory=dict)  # optional, same keys, EV% if known
    best_market: str | None = None
    best_prob: float | None = None

    def select_pick(self) -> None:
        """
        Evaluates EVERY market in self.markets and picks the single
        highest-probability one. This is what replaces whatever logic
        was defaulting to a 1X2 team-win pick regardless of what O1.5/
        O2.5/BTTS actually showed.
        """
        if not self.markets:
            logger.warning("Fixture %s has no market data — cannot select a pick.", self.fixture_id)
            return
        self.best_market, self.best_prob = max(self.markets.items(), key=lambda kv: kv[1])


def build_fixture_records(
    raw_fixtures: list[dict],
    market_data_by_fixture_id: dict[str, dict[str, float]],
) -> tuple[list[FixtureRecord], list[str]]:
    """
    raw_fixtures: [{"fixture_id": ..., "league": ..., "kickoff": ...,
                     "home": ..., "away": ...}, ...]
    market_data_by_fixture_id: {fixture_id: {"O1.5": 0.89, ...}, ...} —
    a DICT keyed by fixture_id, never a parallel list. This is the whole
    fix: there is no index to drift out of sync, because lookup is by
    the fixture's own identity, not by position.

    Returns (records, dropped_fixture_ids). A fixture with no market
    data is DROPPED (per the same hard-gate principle as
    enrichment_fix.py) rather than shipped with an empty row — this is
    the fix for the Schalke v Bayern silent-blank-row bug: it either
    ships complete, or it doesn't ship at all, and either way it's
    visible which happened.
    """
    records = []
    dropped = []

    for raw in raw_fixtures:
        fid = raw["fixture_id"]
        markets = market_data_by_fixture_id.get(fid)

        if not markets:
            logger.warning("DROPPED fixture %s v %s (%s) — no market data found for fixture_id=%s",
                            raw["home"], raw["away"], raw["league"], fid)
            dropped.append(fid)
            continue

        record = FixtureRecord(
            fixture_id=fid,
            league=raw["league"],
            kickoff=raw["kickoff"],
            home=raw["home"],
            away=raw["away"],
            markets=markets,
        )
        record.select_pick()
        records.append(record)

    return records, dropped


def validate_league_coverage(records: list[FixtureRecord], expected_leagues: set[str]) -> list[str]:
    """
    Catches the single-league lock-in bug. expected_leagues is whatever
    your active whitelist/hunting-set config says should be scanned
    today. Returns the list of leagues that were expected but produced
    ZERO fixtures — this should be surfaced in the board's DATA FLAGS
    section (per HR53), not silently absent.

    A league legitimately having no fixtures today is fine and should
    say so explicitly ("no fixtures in window") — what this catches is
    the different failure: a league that HAD fixtures available but
    none made it into records, which is what happened today if
    non-Bundesliga leagues had real matches.
    """
    leagues_present = {r.league for r in records}
    missing = sorted(expected_leagues - leagues_present)
    if missing:
        logger.warning("Leagues expected but produced NO fixtures: %s — verify whether "
                        "these genuinely had no matches today, or the scan silently "
                        "narrowed to fewer leagues than the active whitelist.", missing)
    return missing


def render_pick_line(record: FixtureRecord) -> str:
    if record.best_market is None:
        return f"{record.home} v {record.away} — NO DATA — PENDING (no market data)"
    ev = record.market_ev.get(record.best_market)
    ev_str = f" (EV: {ev:+.1f}%)" if ev is not None else ""
    return f"{record.home} v {record.away} — {record.best_market} {record.best_prob:.0%}{ev_str}"


# --- Self-test reproducing today's exact bug pattern, to confirm the fix ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    raw_fixtures = [
        {"fixture_id": "f1", "league": "Bundesliga", "kickoff": "18:30", "home": "Hoffenheim", "away": "Dortmund"},
        {"fixture_id": "f2", "league": "Bundesliga", "kickoff": "18:30", "home": "Werder Bremen", "away": "RB Leipzig"},
        {"fixture_id": "f3", "league": "Bundesliga", "kickoff": "18:30", "home": "M'gladbach", "away": "Elversberg"},
        {"fixture_id": "f4", "league": "Bundesliga", "kickoff": "18:30", "home": "Leverkusen", "away": "Union Berlin"},
        {"fixture_id": "f5", "league": "Bundesliga", "kickoff": "18:30", "home": "Schalke 04", "away": "Bayern Munich"},
    ]

    # Note: f3 (M'gladbach) has REAL market data here, and f5 (Schalke) is
    # deliberately missing — reproducing "no prediction for two teams."
    market_data = {
        "f1": {"O1.5": 0.89, "O2.5": 0.73, "O3.5": 0.45, "BTTS": 0.65, "Hoffenheim_win": 0.30, "Dortmund_win": 0.47},
        "f2": {"O1.5": 0.79, "O2.5": 0.55, "O3.5": 0.30, "BTTS": 0.55, "RBLeipzig_win": 0.56},
        "f3": {"O1.5": 0.81, "O2.5": 0.59, "O3.5": 0.35, "BTTS": 0.61},
        "f4": {"O1.5": 0.84, "O2.5": 0.64, "O3.5": 0.40, "BTTS": 0.57, "Leverkusen_win": 0.65},
        # f5 deliberately absent — reproducing the silent-drop bug
    }

    records, dropped = build_fixture_records(raw_fixtures, market_data)

    print("=== Fixed output ===")
    for r in records:
        print(f"{r.league} | {r.kickoff} | {render_pick_line(r)}")
    print(f"\nDropped (no data, correctly held back, not shown blank): {dropped}")

    missing_leagues = validate_league_coverage(records, expected_leagues={"Bundesliga", "Ligue 1", "Serie A"})
    print(f"Leagues expected but absent from output: {missing_leagues or 'none'}")