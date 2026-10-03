"""
Results Ingestion Module — Automated post-match verification for acca legs.

This module:
1. Loads acca JSON (fixtures + markets)
2. Fetches actual match results from football-data.co.uk (T1 canonical source, same as CLV grading)
   with ESPN as fallback via multi-source fabric
   with manual verification file as last resort for new-season matches
3. Settles each leg using engine/markets settlement rules
4. Outputs verification_log.json with WIN/LOSS/PENDING per leg
5. Integrates with clv/clv_logger.py for CLV feedback loop

HR35 Compliant: NO fabrication — missing results = PENDING, never guessed.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import load_league, MatchResult as FDMatchResult
from data.espn_results import fetch_results_for_date, MatchResult as ESPNMatchResult
from engine import markets as mkt
from clv.clv_logger import CLVLog, LoggedLeg, compute_clv


@dataclass
class AccaLeg:
    """A single accumulator leg from the production JSON."""
    fixture: str
    league: str
    market_key: str
    market_name: str
    price: float
    prob: float
    ev: float
    edge: float
    verification_stamp: str
    status: str


@dataclass
class Acca:
    """An accumulator with multiple legs."""
    label: str
    combined_odds: float
    combined_prob: float
    n_legs: int
    legs: list[AccaLeg]


@dataclass
class VerifiedLeg:
    """A leg verified against actual match result."""
    fixture: str
    league: str
    market_key: str
    market_name: str
    price: float
    prob: float
    ev: float
    edge: float
    verification_stamp: str
    status: str  # original status from acca JSON
    # Verification fields
    result: Optional[str] = None  # "HOME_WIN", "DRAW", "AWAY_WIN", "PENDING"
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    settled: bool = False
    hit: Optional[bool] = None  # True=WIN, False=LOSS, None=PENDING
    clv_pct: Optional[float] = None
    closing_odds: Optional[float] = None
    closing_capture_path: Optional[str] = None
    match_date: Optional[str] = None
    event_id: Optional[str] = None
    provenance: Optional[dict] = None
    verification_time: str = ""


@dataclass
class VerifiedAcca:
    """An accumulator with verified legs."""
    label: str
    combined_odds: float
    combined_prob: float
    n_legs: int
    legs: list[VerifiedLeg]
    # Summary
    wins: int = 0
    losses: int = 0
    pending: int = 0
    acca_result: str = "PENDING"  # "WIN", "LOSS", "PENDING"


def load_acca_file(path: Path) -> tuple[list[Acca], str]:
    """Load acca JSON file and return list of Acca objects + date string."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    date_str = data.get("date", "")
    accas = []

    for acca_data in data.get("accas", []):
        legs = [
            AccaLeg(
                fixture=leg["fixture"],
                league=leg["league"],
                market_key=leg["market_key"],
                market_name=leg["market_name"],
                price=leg["price"],
                prob=leg["prob"],
                ev=leg["ev"],
                edge=leg["edge"],
                verification_stamp=leg["verification_stamp"],
                status=leg["status"],
            )
            for leg in acca_data["legs"]
        ]
        accas.append(Acca(
            label=acca_data["label"],
            combined_odds=acca_data["combined_odds"],
            combined_prob=acca_data["combined_prob"],
            n_legs=acca_data["n_legs"],
            legs=legs,
        ))

    return accas, date_str


def fetch_results_for_fixtures(
    fixtures: list[tuple[str, str, str]],  # (league, home, away)
    target_date: str
) -> dict[str, FDMatchResult]:
    """
    Fetch results for specific fixtures on a date using football-data.co.uk (T1) as primary,
    ESPN as fallback.

    Returns dict keyed by "league|home v away" -> FDMatchResult
    """
    results_by_key = {}

    # Determine season from target date (football-data.co.uk uses 4-digit season codes like "2526")
    # Target date is YYYY-MM-DD. Season starts in August.
    year = int(target_date[:4])
    month = int(target_date[5:7])
    if month >= 8:
        season = f"{year % 100:02d}{(year + 1) % 100:02d}"  # e.g., 2026 -> "2627"
    else:
        season = f"{(year - 1) % 100:02d}{year % 100:02d}"  # e.g., 2026-01 -> "2526"

    # Also try previous season in case the new season file isn't ready yet
    prev_season = f"{(year - 1) % 100:02d}{year % 100:02d}" if month >= 8 else f"{(year - 2) % 100:02d}{(year - 1) % 100:02d}"

    # Group fixtures by league for efficient fetching
    by_league: dict[str, list[tuple[str, str]]] = {}
    for league, home, away in fixtures:
        by_league.setdefault(league, []).append((home, away))

    # Last resort fallback: Manual verification data
    manual_results = load_manual_verification(target_date)
    if manual_results:
        print(f"[results_ingestion] Loaded {len(manual_results)} manual verification results")

    for league, pairs in by_league.items():
        # 1. Try football-data.co.uk first (T1 canonical source)
        for try_season in [season, prev_season]:
            try:
                results, skipped = load_league(league, try_season)
                for result in results:
                    # Filter to target date
                    if result.date == target_date:
                        key = f"{result.league}|{result.home_team} v {result.away_team}"
                        results_by_key[key] = result
                if skipped:
                    print(f"[results_ingestion] football-data.co.uk ({try_season}): {len(skipped)} rows skipped for {league}")
                if any(r.date == target_date for r in results):
                    break  # Found results for this league
            except ValueError as e:
                # League not covered by football-data.co.uk (e.g., continental comps)
                print(f"[results_ingestion] football-data.co.uk: {league} not covered ({e})")
                break  # Don't try other seasons for uncovered leagues
            except Exception as e:
                print(f"[results_ingestion] football-data.co.uk error for {league} ({try_season}): {e}")
                continue

        # 2. Fallback: ESPN for leagues not covered or missing results
        missing_pairs = [(h, a) for h, a in pairs
                         if f"{league}|{h} v {a}" not in results_by_key]
        if missing_pairs:
            try:
                espn_results = fetch_results_for_date(target_date, league)
                for result in espn_results:
                    key = f"{result.league}|{result.home_team} v {result.away_team}"
                    if key not in results_by_key:
                        fd_result = _espn_to_fd_result(result)
                        results_by_key[key] = fd_result
                if any(f"{league}|{h} v {a}" in results_by_key for h, a in missing_pairs):
                    print(f"[results_ingestion] ESPN: matched fixtures for {league}")
            except Exception as e:
                print(f"[results_ingestion] ESPN fallback error for {league}: {e}")

        # 2.5. Fallback: FlashScore for lower-tier leagues not covered by ESPN
        still_missing_after_espn = [(h, a) for h, a in pairs
                                     if f"{league}|{h} v {a}" not in results_by_key]
        if still_missing_after_espn:
            try:
                from data.flashscore_results import fetch_flashscore_results_sync
                flashscore_results = fetch_flashscore_results_sync(league, target_date)
                for result in flashscore_results:
                    key = f"{result.league}|{result.home_team} v {result.away_team}"
                    if key not in results_by_key:
                        fd_result = FDMatchResult(
                            league=result.league,
                            date=result.date,
                            home_team=result.home_team,
                            away_team=result.away_team,
                            fthg=result.fthg,
                            ftag=result.ftag,
                            ftr=result.ftr,
                            closing_home_odds=None,
                            closing_draw_odds=None,
                            closing_away_odds=None,
                            source=result.source,
                            source_tier=result.source_tier,
                            odds=None,
                            kickoff_time=None,
                        )
                        results_by_key[key] = fd_result
                if any(f"{league}|{h} v {a}" in results_by_key for h, a in still_missing_after_espn):
                    print(f"[results_ingestion] FlashScore: matched fixtures for {league}")
            except Exception as e:
                print(f"[results_ingestion] FlashScore fallback error for {league}: {e}")

        # 3. Last Resort: Manual verification data
        still_missing = [(h, a) for h, a in pairs
                         if f"{league}|{h} v {a}" not in results_by_key]
        if still_missing:
            for h, a in still_missing:
                key = f"{league}|{h} v {a}"
                if key in manual_results:
                    results_by_key[key] = manual_results[key]
                    print(f"[results_ingestion] Manual: matched fixture {key}")

    return results_by_key


def _espn_to_fd_result(espn: ESPNMatchResult) -> FDMatchResult:
    """Convert ESPN MatchResult to football-data.co.uk MatchResult format."""
    return FDMatchResult(
        league=espn.league,
        date=espn.match_date,
        home_team=espn.home_team,
        away_team=espn.away_team,
        fthg=espn.home_score,
        ftag=espn.away_score,
        ftr="H" if espn.home_score > espn.away_score else ("D" if espn.home_score == espn.away_score else "A"),
        closing_home_odds=espn.home_odds,
        closing_draw_odds=espn.draw_odds,
        closing_away_odds=espn.away_odds,
        source=espn.odds_source or "ESPN",
        source_tier="T2" if espn.odds_source else "T3",
        odds=None,
        kickoff_time=None,
    )


def load_manual_verification(target_date: str) -> dict[str, FDMatchResult]:
    """
    Load manually verified results from JSON file.

    Used as last-resort fallback for new-season matches where automated
    sources don't have data yet.
    """
    repo_root = Path(__file__).parent.parent
    manual_path = repo_root / "data" / f"manual_verification_{target_date}.json"

    if not manual_path.exists():
        return {}

    with open(manual_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results_by_key = {}
    for item in data.get("results", []):
        if item.get("status") != "completed":
            continue
        key = f"{item['league']}|{item['fixture']}"
        results_by_key[key] = FDMatchResult(
            league=item["league"],
            date=target_date,
            home_team=item["fixture"].split(" v ")[0].strip(),
            away_team=item["fixture"].split(" v ")[1].strip(),
            fthg=item["home_score"],
            ftag=item["away_score"],
            ftr="H" if item["home_score"] > item["away_score"] else ("D" if item["home_score"] == item["away_score"] else "A"),
            closing_home_odds=None,
            closing_draw_odds=None,
            closing_away_odds=None,
            source="manual_verification",
            source_tier="T3",
            odds=None,
            kickoff_time=None,
        )

    return results_by_key


def settle_leg(leg: AccaLeg, result: FDMatchResult) -> tuple[bool, Optional[str], Optional[float], Optional[str]]:
    """
    Settle a leg against a match result using engine/markets rules.

    Returns: (hit, ft_result_str, closing_odds, closing_capture_path)
    """
    # Settle using the market module
    hit = mkt.settle(leg.market_key, result.fthg, result.ftag)

    if hit is None:
        # Market not supported by settlement rules
        return False, f"{result.fthg}-{result.ftag}", None, None

    ft_result = f"{result.fthg}-{result.ftag}"

    # Extract closing odds for this market from the result
    closing_odds = None
    closing_capture_path = "CL-ARCHIVE"

    # Use the rich odds object if available (from football-data.co.uk)
    if result.odds:
        quote = mkt.quote(leg.market_key, result.odds)
        if quote and quote.close:
            closing_odds = quote.close
        elif quote and quote.available:
            closing_odds = quote.price
    elif result.closing_home_odds and result.closing_draw_odds and result.closing_away_odds:
        # Fallback to simple 1X2 closing odds
        odds_dict = {
            "home_odds": result.closing_home_odds,
            "draw_odds": result.closing_draw_odds,
            "away_odds": result.closing_away_odds,
        }
        quote = mkt.quote(leg.market_key, odds_dict)
        if quote and quote.close:
            closing_odds = quote.close
        elif quote and quote.available:
            closing_odds = quote.price
        else:
            closing_odds = _infer_closing_odds(leg.market_key, result)

    return hit, ft_result, closing_odds, closing_capture_path


def _infer_closing_odds(market_key: str, result: FDMatchResult) -> Optional[float]:
    """Infer closing odds for a market from 1X2 odds when direct quote unavailable."""
    h, d, a = result.closing_home_odds, result.closing_draw_odds, result.closing_away_odds
    if not all([h, d, a]):
        return None

    try:
        if market_key == "1X2_HOME":
            return h
        elif market_key == "1X2_AWAY":
            return a
        elif market_key == "DC_1X":
            # Home or Draw
            return 1.0 / (1.0/h + 1.0/d)
        elif market_key == "DC_X2":
            # Draw or Away
            return 1.0 / (1.0/d + 1.0/a)
        elif market_key == "DC_12":
            # Home or Away
            return 1.0 / (1.0/h + 1.0/a)
        elif market_key in ("OVER_1_5", "OVER_2_5", "UNDER_2_5", "BTTS_YES", "BTTS_NO"):
            # Can't reliably infer totals/BTTS from 1X2 alone
            return None
    except ZeroDivisionError:
        return None

    return None


def verify_acca(acca: Acca, results_by_key: dict[str, FDMatchResult], target_date: str) -> VerifiedAcca:
    """Verify all legs in an acca against fetched results."""
    verified_legs = []
    wins = losses = pending = 0

    for leg in acca.legs:
        key = f"{leg.league}|{leg.fixture}"
        result = results_by_key.get(key)

        verified = VerifiedLeg(
            fixture=leg.fixture,
            league=leg.league,
            market_key=leg.market_key,
            market_name=leg.market_name,
            price=leg.price,
            prob=leg.prob,
            ev=leg.ev,
            edge=leg.edge,
            verification_stamp=leg.verification_stamp,
            status=leg.status,
            verification_time=datetime.now(timezone.utc).isoformat(),
        )

        if result:
            hit, ft_result, closing_odds, closing_path = settle_leg(leg, result)

            verified.result = "HOME_WIN" if result.fthg > result.ftag else ("DRAW" if result.fthg == result.ftag else "AWAY_WIN")
            verified.home_score = result.fthg
            verified.away_score = result.ftag
            verified.settled = True
            verified.hit = hit
            verified.match_date = result.date
            verified.provenance = {
                "source": result.source,
                "source_tier": result.source_tier,
                "fetched_at": datetime.now(timezone.utc).isoformat() + "Z",
            }
            verified.closing_odds = closing_odds
            verified.closing_capture_path = closing_path

            if closing_odds and leg.price:
                verified.clv_pct = compute_clv(leg.price, closing_odds)

            if hit:
                wins += 1
            else:
                losses += 1
        else:
            # No result available — PENDING per HR35
            verified.result = "PENDING"
            verified.settled = False
            verified.hit = None
            pending += 1

        verified_legs.append(verified)

    # Determine acca result
    if pending > 0:
        acca_result = "PENDING"
    elif losses == 0:
        acca_result = "WIN"
    else:
        acca_result = "LOSS"

    return VerifiedAcca(
        label=acca.label,
        combined_odds=acca.combined_odds,
        combined_prob=acca.combined_prob,
        n_legs=acca.n_legs,
        legs=verified_legs,
        wins=wins,
        losses=losses,
        pending=pending,
        acca_result=acca_result,
    )


def integrate_with_clv_log(verified_acca: VerifiedAcca, clv_log: CLVLog) -> tuple[int, int]:
    """
    Integrate verified results into CLV log.

    Returns: (graded_count, clv_captured_count)
    """
    graded = 0
    clv_captured = 0

    for leg in verified_acca.legs:
        if not leg.settled or leg.hit is None:
            continue

        # Try to find existing leg in CLV log
        existing = None
        for logged in clv_log.legs:
            if logged.fixture == leg.fixture and logged.market == leg.market_key:
                existing = logged
                break

        if existing and existing.hit is None:
            # Grade the existing leg
            clv_log.log_result(existing.leg_id, ft_result=f"{leg.home_score}-{leg.away_score}", hit=leg.hit)
            graded += 1

            if leg.closing_odds:
                clv_log.log_close(existing.leg_id, closing_odds=leg.closing_odds, closing_capture_path=leg.closing_capture_path or "CL-ARCHIVE")
                clv_captured += 1

    return graded, clv_captured


def write_verification_log(verified_accas: list[VerifiedAcca], output_path: Path) -> None:
    """Write verification results to JSON file."""
    output_data = {
        "verification_date": datetime.now(timezone.utc).isoformat(),
        "accas": [
            {
                "label": acca.label,
                "combined_odds": acca.combined_odds,
                "combined_prob": acca.combined_prob,
                "n_legs": acca.n_legs,
                "wins": acca.wins,
                "losses": acca.losses,
                "pending": acca.pending,
                "acca_result": acca.acca_result,
                "legs": [asdict(leg) for leg in acca.legs],
            }
            for acca in verified_accas
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"[results_ingestion] Verification log written to {output_path}")


def write_summary_report(verified_accas: list[VerifiedAcca], output_path: Path) -> None:
    """Write human-readable summary report."""
    total_legs = sum(a.n_legs for a in verified_accas)
    total_wins = sum(a.wins for a in verified_accas)
    total_losses = sum(a.losses for a in verified_accas)
    total_pending = sum(a.pending for a in verified_accas)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 2026-08-22 Production Pipeline — Automated Verification Report\n\n")
        f.write(f"**Verification Time:** {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"**Total Accas:** {len(verified_accas)}\n")
        f.write(f"**Total Legs:** {total_legs}  |  **Wins:** {total_wins}  |  **Losses:** {total_losses}  |  **Pending:** {total_pending}\n\n")

        for acca in verified_accas:
            f.write(f"## {acca.label} — {acca.acca_result} ({acca.wins}/{acca.n_legs} legs won)\n\n")
            f.write(f"- Combined Odds: {acca.combined_odds:.2f}\n")
            f.write(f"- Combined Prob: {acca.combined_prob:.4f}\n\n")

            f.write("| Leg | Fixture | Market | Result | Score | Outcome | CLV% |\n")
            f.write("|-----|---------|--------|--------|-------|---------|------|\n")

            for leg in acca.legs:
                score = f"{leg.home_score}-{leg.away_score}" if leg.home_score is not None else "—"
                outcome = "✅ WIN" if leg.hit is True else ("❌ LOSS" if leg.hit is False else "⏳ PENDING")
                clv = f"{leg.clv_pct:+.2f}%" if leg.clv_pct is not None else "—"
                f.write(f"| {leg.fixture} | {leg.market_name} | {leg.result or '—'} | {score} | {outcome} | {clv} |\n")

            f.write("\n---\n\n")

    print(f"[results_ingestion] Summary report written to {output_path}")


def run_verification(
    acca_file: str = "acca_2026-08-22.json",
    target_date: Optional[str] = None,
    output_dir: Optional[str] = None,
    integrate_clv: bool = True,
) -> tuple[list[VerifiedAcca], dict]:
    """
    Main entry point for automated verification.

    Args:
        acca_file: Path to acca JSON file (relative to repo root)
        target_date: Match date (YYYY-MM-DD), defaults to date in acca file
        output_dir: Output directory for verification logs
        integrate_clv: Whether to update CLV log with results

    Returns:
        (list of VerifiedAcca, summary dict)
    """
    repo_root = Path(__file__).parent.parent
    acca_path = repo_root / acca_file

    if not acca_path.exists():
        raise FileNotFoundError(f"Acca file not found: {acca_path}")

    print(f"[results_ingestion] Loading accas from {acca_path}")
    accas, date_str = load_acca_file(acca_path)

    if target_date is None:
        target_date = date_str

    print(f"[results_ingestion] Target date: {target_date}")
    print(f"[results_ingestion] Loaded {len(accas)} accas with {sum(a.n_legs for a in accas)} total legs")

    # Collect all unique fixtures
    fixtures = []
    for acca in accas:
        for leg in acca.legs:
            fixtures.append((leg.league, leg.fixture.split(" v ")[0].strip(), leg.fixture.split(" v ")[1].strip()))

    # Fetch results
    print(f"[results_ingestion] Fetching results for {len(fixtures)} fixtures...")
    results_by_key = fetch_results_for_fixtures(fixtures, target_date)
    print(f"[results_ingestion] Got results for {len(results_by_key)} fixtures")

    # Verify each acca
    verified_accas = []
    for acca in accas:
        verified = verify_acca(acca, results_by_key, target_date)
        verified_accas.append(verified)
        print(f"  {verified.label}: {verified.acca_result} ({verified.wins}W/{verified.losses}L/{verified.pending}P)")

    # Integrate with CLV log
    if integrate_clv:
        clv_log = CLVLog()
        total_graded = 0
        total_clv = 0
        for acca in verified_accas:
            graded, clv = integrate_with_clv_log(acca, clv_log)
            total_graded += graded
            total_clv += clv
        print(f"[results_ingestion] CLV integration: {total_graded} legs graded, {total_clv} closing lines captured")

    # Write outputs
    out_dir = Path(output_dir) if output_dir else (repo_root / "data" / "verification_logs")
    out_dir.mkdir(parents=True, exist_ok=True)

    date_safe = target_date.replace("-", "")
    json_path = out_dir / f"verification_{date_safe}.json"
    md_path = out_dir / f"verification_{date_safe}.md"

    write_verification_log(verified_accas, json_path)
    write_summary_report(verified_accas, md_path)

    # Compute summary stats
    total_legs = sum(a.n_legs for a in verified_accas)
    total_wins = sum(a.wins for a in verified_accas)
    total_losses = sum(a.losses for a in verified_accas)
    total_pending = sum(a.pending for a in verified_accas)

    # Summary
    summary = {
        "date": target_date,
        "total_accas": len(verified_accas),
        "total_legs": total_legs,
        "wins": total_wins,
        "losses": total_losses,
        "pending": total_pending,
        "win_rate": round(total_wins / (total_wins + total_losses), 4) if (total_wins + total_losses) > 0 else None,
        "verification_log": str(json_path),
        "summary_report": str(md_path),
    }

    return verified_accas, summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Automated results ingestion for acca verification")
    parser.add_argument("--file", default="acca_2026-08-22.json", help="Acca JSON file")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to date in file")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--no-clv", action="store_true", help="Skip CLV log integration")

    args = parser.parse_args()

    verified_accas, summary = run_verification(
        acca_file=args.file,
        target_date=args.date,
        output_dir=args.output,
        integrate_clv=not args.no_clv,
    )

    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    print(f"Date: {summary['date']}")
    print(f"Accas: {summary['total_accas']}")
    print(f"Total Legs: {summary['total_legs']}")
    print(f"Wins: {summary['wins']}")
    print(f"Losses: {summary['losses']}")
    print(f"Pending: {summary['pending']}")
    if summary['win_rate'] is not None:
        print(f"Win Rate (settled): {summary['win_rate']:.1%}")
    print(f"Log: {summary['verification_log']}")
    print(f"Report: {summary['summary_report']}")