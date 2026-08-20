"""
HR58 Stage A — Fixture Extraction + ID403 Verification + Multi-Source Failover + Kickoff Verification.

Produces a COMPLETE, IMMUTABLE fixture list for the run. Stage B (production) reads this
output and MUST NOT drop fixtures silently — NO DATA — PENDING rows are preserved.

Architect directive (2026-08-20): The pipeline is split:
  Stage A: fixture extraction → ID403 verify → multi-source failover → kickoff verify → immutable list
  Stage B: production reads Stage A output, NO DATA — PENDING rows preserved, no silent drops

This module is the single source of truth for the fixture universe. Every whitelisted league
is scanned; fixtures with no data show as NO DATA — PENDING with explicit reasons.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from data.multi_source_concrete import get_fixtures, initialize_multi_sources
from verification.id403 import verify, SourcedDatum, Tier
from engine.league_registry import registry

log = logging.getLogger("pipeline.fixture_extraction")

# Output path for the immutable fixture list (written once per run)
STAGE_A_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "stage_a_output"
STAGE_A_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class VerifiedFixture:
    """One fixture after Stage A processing — complete with verification and kickoff."""
    league: str
    home_team: str          # model key (aliased)
    away_team: str          # model key (aliased)
    kickoff_utc: str | None  # ISO timestamp if available
    kickoff_date: str | None  # YYYY-MM-DD if available
    verification_tier: str   # VERIFIED | SINGLE-SOURCE | CONFLICT | NO-DATA | DERIVED
    verification_note: str   # human-readable reason
    verification_factors: dict = field(default_factory=dict)
    source: str | None = None          # which source produced this fixture
    source_tier: str | None = None     # T1/T2/T3/REJECTED of the source
    status: str = "pending"            # "pending" | "verified" | "no_data"
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VerifiedFixture":
        return cls(**data)


@dataclass
class StageAOutput:
    """Complete Stage A output — the immutable fixture universe for this run."""
    run_date: str                    # YYYY-MM-DD (date the extraction ran)
    fixtures_season: str             # season code fixtures pulled for (e.g., "2627")
    leagues_scanned: list[str]       # all leagues that were scanned
    fixtures: list[VerifiedFixture]  # complete fixture list (NO silent drops)
    flags: list[str] = field(default_factory=list)  # run-level flags
    stats: dict = field(default_factory=dict)       # summary stats

    def to_json(self) -> str:
        return json.dumps({
            "run_date": self.run_date,
            "fixtures_season": self.fixtures_season,
            "leagues_scanned": self.leagues_scanned,
            "fixtures": [f.to_dict() for f in self.fixtures],
            "flags": self.flags,
            "stats": self.stats,
        }, indent=2)

    @classmethod
    def from_json(cls, data: str) -> "StageAOutput":
        obj = json.loads(data)
        obj["fixtures"] = [VerifiedFixture.from_dict(f) for f in obj["fixtures"]]
        return cls(**obj)

    def save(self, path: Path | None = None) -> Path:
        """Save to JSON file. Path defaults to dated file in STAGE_A_OUTPUT_DIR."""
        if path is None:
            path = STAGE_A_OUTPUT_DIR / f"fixtures_{self.run_date}_{self.fixtures_season}.json"
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "StageAOutput":
        return cls.from_json(path.read_text(encoding="utf-8"))


def _resolve_kickoff_date(kickoff_utc: str | None) -> str | None:
    """Extract YYYY-MM-DD from ISO kickoff timestamp."""
    if not kickoff_utc:
        return None
    try:
        # Validate it's a real date before slicing
        date_part = kickoff_utc[:10]
        datetime.strptime(date_part, "%Y-%m-%d")
        return date_part
    except (ValueError, AttributeError, TypeError):
        return None


def _verify_fixture(league: str, home: str, away: str, source: str, source_tier: str,
                    kickoff_utc: str | None) -> tuple[str, str, dict]:
    """
    Run ID403 verification on a single fixture.

    Returns (verification_tier, verification_note, verification_factors).
    """
    # Create sourced datum from the fixture source
    claim = SourcedDatum(
        domain=source,
        value=f"{home} v {away}",
        url=f"https://{source}",
        structured=True
    )
    result = verify([claim])

    # Add kickoff info to factors
    factors = dict(result.factors)
    if kickoff_utc:
        factors["kickoff_utc"] = kickoff_utc

    return result.tier.value, result.note, factors


def _determine_status(tier: str, kickoff_utc: str | None) -> str:
    """Determine fixture status from verification tier and kickoff availability."""
    if tier in ("VERIFIED", "SINGLE-SOURCE"):
        return "verified"
    elif tier == "CONFLICT":
        return "pending"  # Architect must adjudicate
    else:
        return "no_data"


def extract_fixtures_for_league(
    league: str,
    fixtures_season: str,
    days_ahead: int = 14,
    api_football_season: int | None = None
) -> tuple[list[VerifiedFixture], list[str]]:
    """
    Extract and verify fixtures for ONE league using multi-source failover.

    Returns (verified_fixtures, flags).
    """
    flags: list[str] = []
    verified: list[VerifiedFixture] = []

    try:
        # Multi-source failover with circuit breakers (data/multi_source_concrete.py)
        result = get_fixtures(
            league=league,
            fixtures_season=fixtures_season,
            days_ahead=days_ahead,
            api_football_season=api_football_season
        )

        fixtures = result.get("fixtures") or []
        dates = result.get("dates") or {}
        src = result.get("source", "unknown")
        skipped = result.get("skipped", 0)

        if skipped:
            flags.append(f"{league}: {skipped} fixture rows skipped/malformed from {src}")

        if not fixtures:
            flags.append(f"{league}: no upcoming fixtures from {src} — NO DATA — PENDING")
            return [], flags

        # Apply team alias mapping (same as orchestrator)
        from data.thesportsdb_fixtures import map_team
        mapped_fixtures = [(map_team(league, h), map_team(league, a)) for h, a in fixtures]

        # Verify each fixture with ID403
        for home, away in mapped_fixtures:
            kickoff_utc = dates.get((home, away))
            kickoff_date = _resolve_kickoff_date(kickoff_utc)

            tier, note, factors = _verify_fixture(
                league, home, away, src, "T2" if src == "thesportsdb" else "T1", kickoff_utc
            )

            status = _determine_status(tier, kickoff_utc)

            vf = VerifiedFixture(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_utc=kickoff_utc,
                kickoff_date=kickoff_date,
                verification_tier=tier,
                verification_note=note,
                verification_factors=factors,
                source=src,
                source_tier="T2" if src == "thesportsdb" else "T1",
                status=status,
            )
            verified.append(vf)

        if src != "thesportsdb":
            flags.append(f"{league}: fixtures via {src} (primary source failed)")

    except Exception as e:
        # HR35: A real gap is reported, never guessed. Return NO DATA fixtures list.
        flags.append(f"{league}: fixture extraction failed ({str(e)[:80]}) — NO DATA — PENDING")
        # Still attempt SportyBet cache merge (see orchestrator for pattern)
        try:
            from booking.bridge import load_sportybet_fixtures, sportybet_fixtures_to_pairs
            from data.thesportsdb_fixtures import map_team

            sb_pairs = sportybet_fixtures_to_pairs(league, days_ahead=45, max_age_hours=48)
            if sb_pairs:
                sb_pairs = [(map_team(league, h), map_team(league, a)) for h, a in sb_pairs]
                sb_fixtures = load_sportybet_fixtures(league, days_ahead=45, max_age_hours=48)

                sb_dates = {}
                for f in sb_fixtures:
                    if f.kickoff_utc:
                        mh = map_team(league, f.home_team)
                        ma = map_team(league, f.away_team)
                        sb_dates[(mh, ma)] = f.kickoff_utc[:10]

                for home, away in sb_pairs:
                    kickoff_utc = None
                    for (mh, ma), kd in sb_dates.items():
                        if (mh, ma) == (home, away):
                            kickoff_utc = kd + "T00:00:00Z"
                            break
                    kickoff_date = _resolve_kickoff_date(kickoff_utc)

                    tier, note, factors = _verify_fixture(
                        league, home, away, "sportybet_cache", "T2", kickoff_utc
                    )

                    status = _determine_status(tier, kickoff_utc)

                    vf = VerifiedFixture(
                        league=league,
                        home_team=home,
                        away_team=away,
                        kickoff_utc=kickoff_utc,
                        kickoff_date=kickoff_date,
                        verification_tier=tier,
                        verification_note=note + " (SportyBet cache merge)",
                        verification_factors=factors,
                        source="sportybet_cache",
                        source_tier="T2",
                        status=status,
                    )
                    verified.append(vf)

                flags.append(f"{league}: +{len(sb_pairs)} fixture(s) merged from SportyBet cache")
        except Exception:
            pass  # cache miss is not an error

    return verified, flags


def run_stage_a(
    season: str = "2526",
    fixtures_season: str | None = None,
    leagues: list[str] | None = None,
    days_ahead: int = 14,
    api_football_season: int | None = None
) -> StageAOutput:
    """
    HR58 Stage A — Run complete fixture extraction for all leagues.

    Produces an IMMUTABLE fixture list. Every whitelisted league is scanned.
    Fixtures with no data appear as NO DATA — PENDING with explicit reasons.
    NO fixture is silently dropped.

    Args:
        season: Season the model is FIT on (e.g., "2526" = 2025/26)
        fixtures_season: Season fixtures are pulled from (default: next_season_code(season))
        leagues: Subset of leagues to scan (default: ALL deploy-eligible from registry)
        days_ahead: Fixture window in days from today
        api_football_season: API-Football season year for fallback

    Returns:
        StageAOutput with complete fixture universe for Stage B consumption.
    """
    from orchestrator_DEPRECATED import next_season_code

    initialize_multi_sources()

    fixtures_season = fixtures_season or next_season_code(season)
    leagues = leagues or registry.deploy_eligible_leagues()
    run_date = date.today().isoformat()

    all_fixtures: list[VerifiedFixture] = []
    all_flags: list[str] = []
    stats = {
        "total_fixtures": 0,
        "verified": 0,
        "single_source": 0,
        "conflict": 0,
        "no_data": 0,
        "with_kickoff": 0,
        "leagues_scanned": len(leagues),
        "leagues_with_fixtures": 0,
    }

    log.info(f"Stage A: extracting fixtures for {len(leagues)} leagues (season={fixtures_season})")

    for league in leagues:
        log.info(f"  Scanning {league}...")
        fixtures, flags = extract_fixtures_for_league(
            league, fixtures_season, days_ahead, api_football_season
        )
        all_fixtures.extend(fixtures)
        all_flags.extend(flags)

        if fixtures:
            stats["leagues_with_fixtures"] += 1
            stats["total_fixtures"] += len(fixtures)
            for f in fixtures:
                if f.verification_tier == "VERIFIED":
                    stats["verified"] += 1
                elif f.verification_tier == "SINGLE-SOURCE":
                    stats["single_source"] += 1
                elif f.verification_tier == "CONFLICT":
                    stats["conflict"] += 1
                elif f.verification_tier == "NO-DATA":
                    stats["no_data"] += 1
                if f.kickoff_utc:
                    stats["with_kickoff"] += 1

    output = StageAOutput(
        run_date=run_date,
        fixtures_season=fixtures_season,
        leagues_scanned=leagues,
        fixtures=all_fixtures,
        flags=all_flags,
        stats=stats,
    )

    # Save immutable artifact
    saved_path = output.save()
    log.info(f"Stage A complete: {stats['total_fixtures']} fixtures across "
             f"{stats['leagues_with_fixtures']}/{stats['leagues_scanned']} leagues. "
             f"Saved to {saved_path}")

    return output


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ap = argparse.ArgumentParser(description="HR58 Stage A — Fixture Extraction")
    ap.add_argument("--season", default="2526", help="Season the model is FIT on (e.g., 2526)")
    ap.add_argument("--fixtures-season", default=None, help="Season fixtures are pulled from")
    ap.add_argument("--leagues", nargs="*", default=None, help="Specific leagues to scan")
    ap.add_argument("--days-ahead", type=int, default=14, help="Fixture window in days")
    ap.add_argument("--api-football-season", type=int, default=None, help="API-Football season year")
    ap.add_argument("--output", default=None, help="Output JSON path (default: data/stage_a_output/)")

    args = ap.parse_args()

    output = run_stage_a(
        season=args.season,
        fixtures_season=args.fixtures_season,
        leagues=args.leagues,
        days_ahead=args.days_ahead,
        api_football_season=args.api_football_season,
    )

    if args.output:
        output.save(Path(args.output))
    else:
        output.save()

    print(f"✓ Stage A complete: {output.stats['total_fixtures']} fixtures extracted")
    print(f"  Verified: {output.stats['verified']}, Single-Source: {output.stats['single_source']}")
    print(f"  Conflict: {output.stats['conflict']}, No-Data: {output.stats['no_data']}")
    print(f"  With kickoff: {output.stats['with_kickoff']}")
    print(f"  Leagues scanned: {output.stats['leagues_scanned']}, with fixtures: {output.stats['leagues_with_fixtures']}")