"""
Collaborative multi-source fixture gathering for OLP XDV.

THE CONFIRMED METHOD for answering "what are today's fixtures". Architect
directive 2026-09-16: every available source collaborates on one slate, so a
source that is weak or absent for a given competition is covered by the
others, and agreement between them is what produces verification.

Why this module exists
----------------------
Before this, the live path asked ONE source at a time and treated whatever it
returned as the answer. That failed in two directions at once on 2026-09-16:

  - Coverage. ESPN had no slug for 9 of the 29 whitelisted competitions -- all
    the domestic cups and second tiers -- so EFL Cup looked absent from the
    board while FlashScore was carrying all 4 of its fixtures.
  - Trust. FlashScore alone carried competitions nothing could cross-check, and
    the quorum gate had been written as "at least one source", which is true of
    every row, so everything was stamped verified unconditionally.

Asking every source and reconciling them fixes both: coverage becomes the
union, and verification becomes real agreement rather than an assertion.

Design rules
------------
1. A source that fails NEVER fails the slate. Each adapter is isolated; an
   exception or an empty return is recorded as a source-level flag (HR35:
   absence is reported, never silently filled).
2. Sources are merged by verification.fixture_matcher, which reconciles club
   names across sources ("Sheff Utd" / "Sheffield United", "NK Celje" /
   "Celje"). Without that reconciliation a corroborated fixture splits into two
   single-source records and the quorum rule can never fire.
3. Verification is NOT weakened to raise the verified count. A fixture is
   VERIFIED on agreement between two independent sources, or on one T1 source.
   Everything else is reported honestly as SINGLE-SOURCE.
4. Nothing here fabricates. The output is exactly what the sources returned,
   reconciled -- never inferred, never back-filled from a schedule.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from verification.fixture_matcher import (
    SourceFixture,
    VerificationTier,
    match_fixtures,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Sources whose single word is enough to verify a fixture on its own, per
# verification/id403.SOURCE_TRUST. Resolved there rather than restated, so this
# module never becomes a second drifting copy of the trust table.
_T1_SOURCE_KEYS = {
    "espn": "espn.com",
    "flashscore": "flashscore_fixtures",
    "api_football": "api-football.com",
    "thesportsdb": "thesportsdb.com",
    "sportybet": None,  # odds/corroboration only, never verifies alone
}


def _tier_of(source_name: str) -> str:
    try:
        from verification.id403 import SOURCE_TRUST
    except Exception:
        return "UNKNOWN"
    key = _T1_SOURCE_KEYS.get(source_name)
    return SOURCE_TRUST.get(key, "UNKNOWN") if key else "UNKNOWN"


@dataclass
class SourceReport:
    """What one source contributed, including how it failed if it did."""
    name: str
    tier: str
    fixtures: int = 0
    leagues: int = 0
    ok: bool = True
    error: Optional[str] = None


@dataclass
class Slate:
    date: str
    fixtures: list = field(default_factory=list)   # MatchedFixture
    reports: list = field(default_factory=list)    # SourceReport
    flags: list = field(default_factory=list)

    @property
    def verified(self) -> list:
        return [f for f in self.fixtures if f.tier == VerificationTier.VERIFIED]

    @property
    def single_source(self) -> list:
        return [f for f in self.fixtures if f.tier == VerificationTier.SINGLE_SOURCE]

    @property
    def conflicts(self) -> list:
        return [f for f in self.fixtures if f.tier == VerificationTier.CONFLICT]


def whitelisted_leagues() -> list:
    """Deploy-eligible competitions from the authoritative registry."""
    path = REPO_ROOT / "config" / "leagues.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [l["name"] for l in data["leagues"] if l.get("deploy_eligible")]


# --------------------------------------------------------------------------
# Source adapters. Each returns list[SourceFixture] and may raise -- gather()
# isolates them. Adding a source means adding one adapter and one entry to
# SOURCES; nothing else in the pipeline needs to know.
# --------------------------------------------------------------------------

def _kickoff_iso(date_part: str, time_part: str | None, fallback: str) -> str:
    """Build YYYY-MM-DDTHH:MM from a date plus an HH:MM, or return the date.

    Every adapter below used to pass a bare DATE as kickoff_utc, so the whole
    pipeline saw T00:00:00 for every fixture and no kickoff time existed
    anywhere -- even though FlashScore, SportyBet and TheSportsDB all carry
    one. This joins them back together.

    A missing or "TBD" time returns the DATE ALONE, never a midnight stamp.
    Downstream treats a date-only value as "kickoff not confirmed" and holds
    the fixture off the board (spec §2), which is the honest outcome; inventing
    00:00 would look like a real kickoff and be indistinguishable from one.
    """
    d = (date_part or fallback or "")[:10]
    t = (time_part or "").strip()
    if not d:
        return ""
    if not t or t.upper() == "TBD" or len(t) < 4:
        return d
    return f"{d}T{t[:5]}"


def _espn_adapter(target_date: str, leagues: list) -> list:
    from data.espn_source import fetch_upcoming
    out = []
    for lg in leagues:
        try:
            fixtures, _ = fetch_upcoming(lg, "2627", 2)
        except Exception:
            # Per-league failure (unmapped slug, transient HTTP) must not lose
            # the other leagues this source can still answer for.
            continue
        for f in fixtures:
            if f.date == target_date:
                # Prefer ESPN's full timestamp; f.date is the truncated day.
                out.append(SourceFixture(
                    home=f.home_team, away=f.away_team, league=lg,
                    kickoff_utc=getattr(f, "kickoff_utc", "") or f.date))
    return out


def _flashscore_adapter(target_date: str, leagues: list) -> list:
    from fixtures_agent import fetch_flashscore
    allowed = set(leagues)
    return [
        SourceFixture(home=r["home"], away=r["away"], league=r.get("league", ""),
                      kickoff_utc=_kickoff_iso(r.get("kickoff_date"),
                                               r.get("kickoff"), target_date))
        for r in fetch_flashscore(target_date)
        if r.get("league") in allowed
    ]


def _sportybet_adapter(target_date: str, leagues: list) -> list:
    from fixtures_agent import fetch_sportybet_cache
    allowed = set(leagues)
    return [
        SourceFixture(home=r["home"], away=r["away"], league=r.get("league", ""),
                      kickoff_utc=_kickoff_iso(r.get("kickoff_date"),
                                               r.get("kickoff"), target_date))
        for r in fetch_sportybet_cache(target_date)
        if r.get("league") in allowed
    ]


def _thesportsdb_adapter(target_date: str, leagues: list) -> list:
    # fetch_today is per-league (league, day) and uses the eventsday endpoint,
    # because the eventsseason feed lags weeks behind for continental ties.
    from data.thesportsdb_fixtures import fetch_today
    out = []
    for lg in leagues:
        try:
            fixtures = fetch_today(lg, target_date) or []
        except Exception:
            continue  # one league's gap must not lose the rest
        for f in fixtures:
            home = getattr(f, "home_team", None) or getattr(f, "home", None)
            away = getattr(f, "away_team", None) or getattr(f, "away", None)
            if home and away:
                # fetch_today already assembles "<dateEvent>T<strTime>" into
                # kickoff_utc when TheSportsDB supplies strTime. Reading .date
                # instead threw that away and kept only the day.
                out.append(SourceFixture(
                    home=home, away=away, league=lg,
                    kickoff_utc=(getattr(f, "kickoff_utc", "")
                                 or getattr(f, "date", "") or target_date)))
    return out


SOURCES: dict = {
    "espn": _espn_adapter,
    "flashscore": _flashscore_adapter,
    "sportybet": _sportybet_adapter,
    "thesportsdb": _thesportsdb_adapter,
}


def gather(target_date: str, leagues: Optional[list] = None,
           sources: Optional[dict] = None) -> Slate:
    """Collect `target_date` fixtures from every source and reconcile them.

    Returns a Slate carrying the merged fixtures, a per-source report, and
    flags. Never raises for an ordinary source failure -- that is the whole
    point of the collaboration.
    """
    leagues = leagues if leagues is not None else whitelisted_leagues()
    sources = sources if sources is not None else SOURCES

    collected: dict = {}
    reports: list = []
    flags: list = []

    for name, adapter in sources.items():
        tier = _tier_of(name)
        try:
            fixtures = adapter(target_date, leagues) or []
        except Exception as e:
            reports.append(SourceReport(name=name, tier=tier, ok=False,
                                        error=f"{type(e).__name__}: {e}"))
            flags.append(f"{name}: unavailable ({type(e).__name__}) — "
                         f"slate continues on remaining sources")
            continue

        if not fixtures:
            reports.append(SourceReport(name=name, tier=tier, fixtures=0, leagues=0))
            flags.append(f"{name}: no fixtures for {target_date} — NO DATA, not an empty slate")
            continue

        collected[name] = fixtures
        reports.append(SourceReport(name=name, tier=tier, fixtures=len(fixtures),
                                    leagues=len({f.league for f in fixtures})))

    if not collected:
        flags.append(f"NO DATA — PENDING: every source failed or was empty for {target_date}")
        return Slate(date=target_date, fixtures=[], reports=reports, flags=flags)

    matched = match_fixtures(collected)

    # Promote single-source fixtures carried by a T1 source. Two independent
    # sources already yield VERIFIED inside match_fixtures; this applies the
    # other half of the documented rule, and nothing else.
    for fx in matched:
        if fx.tier != VerificationTier.SINGLE_SOURCE:
            continue
        if any(_tier_of(s) == "T1" for s in fx.sources):
            fx.tier = VerificationTier.VERIFIED

    return Slate(date=target_date, fixtures=matched, reports=reports, flags=flags)


def _display_name(matched_fixture, side: str) -> str:
    """Longest raw name any source gave for this side.

    MatchedFixture carries the NORMALISED key ("bayer leverkusen"), which is a
    comparison artefact and must never reach output -- HR53 wants full club
    names, and the models are keyed on real names too. The longest raw form is
    the most specific one the sources offered.
    """
    names = [getattr(sf, side, "") or "" for sf in matched_fixture.sources.values()]
    return max(names, key=len) if names else getattr(matched_fixture, side, "")


def to_stage_a(slate: Slate, fixtures_season: str = "2627",
               verified_only: bool = True):
    """Convert a collaborative Slate into the Stage A artifact Stage B consumes.

    This is the link that had been missing. run_daily looks for
    data/stage_a_output/fixtures_<date>_<season>.json and, finding none, falls
    back to run_pipeline() -- which returns an empty structure, so no board is
    written. The last Stage A artifact on disk was dated 2026-08-21, which is
    when full production actually stopped: every run since then has taken the
    fallback and produced nothing.

    With the artifact present, run_stage_b() enriches the fixtures with model
    probabilities, builds the acca route and renders the four-table board --
    the full market grid plus the selected pick.
    """
    from pipeline.fixture_extraction import StageAOutput, VerifiedFixture

    source_of = lambda fx: "+".join(sorted(fx.sources))

    chosen = slate.verified if verified_only else slate.fixtures
    vfs = []
    for fx in chosen:
        vfs.append(VerifiedFixture(
            league=fx.league,
            home_team=_display_name(fx, "home"),
            away_team=_display_name(fx, "away"),
            kickoff_utc=fx.kickoff_utc.isoformat() if fx.kickoff_utc else None,
            kickoff_date=slate.date,
            verification_tier=fx.tier,
            verification_note=f"{len(fx.sources)} source(s): {source_of(fx)}",
            verification_factors={"sources": sorted(fx.sources)},
            source=source_of(fx),
            source_tier="T1" if any(_tier_of(s) == "T1" for s in fx.sources) else "T2",
            status="verified" if fx.tier == VerificationTier.VERIFIED else "pending",
        ))

    return StageAOutput(
        run_date=slate.date,
        fixtures_season=fixtures_season,
        leagues_scanned=sorted({f.league for f in slate.fixtures if f.league}),
        fixtures=vfs,
        flags=list(slate.flags),
        stats={
            "sources": {r.name: r.fixtures for r in slate.reports},
            "merged": len(slate.fixtures),
            "verified": len(slate.verified),
            "single_source": len(slate.single_source),
        },
    )
