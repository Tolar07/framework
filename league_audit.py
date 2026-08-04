"""
LEAGUE COVERAGE AUDIT — can each whitelisted league actually produce a bet?

Produces a board-grade pick requires FOUR things, and a league is only
deploy-ready if it has all four:

  1. HISTORY   — enough completed matches to fit Dixon-Coles (football-data.co.uk)
  2. FIXTURES  — the upcoming matches to predict (TheSportsDB)
  3. ODDS      — a live entry price, or HR30 has no numerical MES and HR46 has
                 no CLV (The Odds API)
  4. NAMES     — the three sources must agree on who the clubs are, or the
                 model silently fails to rate a fixture it has full data for

A league missing any one of these is reported as BLOCKED with the specific
missing piece, never quietly dropped from the scan (HR35).

Quota note: odds checks cost 2 API credits per league.

    python league_audit.py            # all 15, includes live odds
    python league_audit.py --no-odds  # free, skips the odds probe
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine.softness import SOFTNESS_TIER, DEPLOY_ELIGIBLE_TIERS
from data.football_data_source import load_league, UNCOVERED_LEAGUES, LEAGUE_CODES
from data import thesportsdb_fixtures as tsdb
import pipeline.odds as odds_mod

MIN_HISTORY = 20     # orchestrator's own floor for attempting a fit


def audit(league: str, fit_season: str, fixtures_season: str,
           check_odds: bool) -> dict:
    tier = SOFTNESS_TIER.get(league, "?")
    row = {"league": league, "tier": tier,
           "deploy_eligible": tier in DEPLOY_ELIGIBLE_TIERS,
           "history": "", "fixtures": "", "odds": "", "names": "",
           "blockers": []}

    # 1. HISTORY
    if league in UNCOVERED_LEAGUES:
        row["history"] = "NOT COVERED"
        row["blockers"].append("football-data.co.uk carries no data for this competition")
        model_names: set[str] = set()
    else:
        try:
            res, _ = load_league(league, fit_season)
            model_names = {r.home_team for r in res} | {r.away_team for r in res}
            if len(res) < MIN_HISTORY:
                row["history"] = f"THIN ({len(res)})"
                row["blockers"].append(f"only {len(res)} historical matches, below the {MIN_HISTORY} floor")
            else:
                row["history"] = f"{len(res)} matches"
        except Exception as e:
            row["history"] = "FAILED"
            row["blockers"].append(f"history fetch failed: {str(e)[:60]}")
            model_names = set()

    # 2. FIXTURES — exercise the SAME fallback chain the orchestrator uses,
    # otherwise the audit reports a league as blocked that the daily run
    # actually covers.
    fixture_names: set[str] = set()
    try:
        fx, _ = tsdb.fetch_upcoming(league, fixtures_season, days_ahead=400)
        fixture_names = {f.home_team for f in fx} | {f.away_team for f in fx}
        row["fixtures"] = f"{len(fx)} (fixtures src)"
        if not fx:
            row["blockers"].append("no upcoming fixtures returned")
    except Exception as e:
        first_error = str(e)[:60]
        try:
            pairs, _dates, _f = odds_mod.fixtures_from_odds(league, days_ahead=400)
            if pairs:
                fixture_names = {t for p in pairs for t in p}
                row["fixtures"] = f"{len(pairs)} (from odds)"
            else:
                row["fixtures"] = "NONE"
                row["blockers"].append(f"fixtures: {first_error}")
        except Exception:
            row["fixtures"] = "NO SOURCE"
            row["blockers"].append(f"fixtures: {first_error}")

    # 3. ODDS
    if not check_odds:
        row["odds"] = "not checked"
    elif league not in odds_mod.SPORT_KEYS:
        row["odds"] = "NO SPORT KEY"
        row["blockers"].append("no Odds API sport key — no entry price, so no MES (HR30) and no CLV (HR46)")
    else:
        try:
            quotes, _ = odds_mod.fetch_odds(league)
            priced = sum(1 for q in quotes if q.home.available)
            ou = sum(1 for q in quotes if q.over25.available)
            row["odds"] = f"{priced} priced ({ou} with O/U)"
            if priced == 0:
                row["blockers"].append("odds source returned no priced fixtures")
        except Exception as e:
            row["odds"] = "FAILED"
            row["blockers"].append(f"odds: {str(e)[:70]}")

    # 4. NAMES — the silent killer. A club the model knows under another
    # spelling looks identical to a club it has never seen.
    if model_names and fixture_names:
        known_new = set(tsdb.KNOWN_NEW_TO_DIVISION_2627.get(league, ()))
        unresolved = sorted(fixture_names - model_names - known_new)
        matched = len(fixture_names & model_names)
        row["names"] = f"{matched}/{len(fixture_names)} matched"
        if unresolved:
            row["blockers"].append(
                f"{len(unresolved)} unmapped club name(s): {', '.join(unresolved[:4])}")
    else:
        row["names"] = "n/a"

    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-season", default="2526")
    ap.add_argument("--fixtures-season", default="2627")
    ap.add_argument("--no-odds", action="store_true")
    a = ap.parse_args()

    print(f"LEAGUE COVERAGE AUDIT — fit {a.fit_season}, fixtures {a.fixtures_season}")
    print("=" * 108)
    print(f"{'league':<22}{'Ƈ':<4}{'history':<14}{'fixtures':<14}"
          f"{'odds':<22}{'names':<14}verdict")
    print("-" * 108)

    rows = []
    for league in SOFTNESS_TIER:
        r = audit(league, a.fit_season, a.fixtures_season, not a.no_odds)
        rows.append(r)
        if not r["blockers"]:
            verdict = "READY"
        elif r["deploy_eligible"]:
            verdict = "BLOCKED (deploy league)"
        else:
            verdict = "blocked (scan-only)"
        print(f"{r['league']:<22}{r['tier']:<4}{r['history']:<14}{r['fixtures']:<14}"
              f"{r['odds']:<22}{r['names']:<14}{verdict}")

    print("-" * 108)
    print("\nBLOCKERS IN DETAIL\n")
    for r in rows:
        if r["blockers"]:
            marker = "!!" if r["deploy_eligible"] else "  "
            print(f"{marker} {r['league']} (tier {r['tier']}):")
            for b in r["blockers"]:
                print(f"     - {b}")

    ready = [r for r in rows if not r["blockers"]]
    deploy_ready = [r for r in ready if r["deploy_eligible"]]
    deploy_total = [r for r in rows if r["deploy_eligible"]]
    print(f"\nSUMMARY")
    print(f"  fully ready               : {len(ready)} of {len(rows)}")
    print(f"  DEPLOY-eligible and ready : {len(deploy_ready)} of {len(deploy_total)}")
    print(f"  (only softness A/B leagues can ever produce a capital pick — a")
    print(f"   blocked C/D league costs you reference coverage, not edge)")


if __name__ == "__main__":
    main()
