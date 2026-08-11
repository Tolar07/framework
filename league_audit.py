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
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: E402 — loads .env so the audit runs on the PROVISIONED
# keys (personal TheSportsDB key, Odds API), not the shared public test key.
# Without this the audit reports leagues as BLOCKED that the daily run actually
# covers — the false picture that hid a completed Ekstraklasa season feed.

from engine.leagues import WHITELISTED_LEAGUES
from data.football_data_source import load_league, UNCOVERED_LEAGUES, LEAGUE_CODES
from data import thesportsdb_fixtures as tsdb
from data.api_football_results import is_cross_league
import pipeline.odds as odds_mod

# The multi-source failover chain logs every provider that failed (WARNING) and
# every circuit breaker opening to stderr. The audit reports those failures
# itself, per league, in the blockers column — keep the shared log out of the
# table or the FAILED/Circuit lines bury the verdicts.
logging.getLogger("multi_source").setLevel(logging.ERROR)

MIN_HISTORY = 20     # orchestrator's own floor for attempting a fit

# Cross-model pool team set, shared by Champions League and Europa League. The
# daily run rates continental clubs on this pooled European graph (domestic
# anchor leagues + continental league phases — engine/cross_league.py), NOT on
# per-competition history, so the names gate must resolve against it. Built at
# most once per audit run; _CROSS_POOL_DETAIL holds a failure reason if the
# pool cannot be built (e.g. run under an interpreter without scipy).
_CROSS_POOL: set[str] | None = None
_CROSS_POOL_DETAIL = ""


def _cross_pool_teams() -> tuple[set[str] | None, str]:
    global _CROSS_POOL, _CROSS_POOL_DETAIL
    if _CROSS_POOL is not None or _CROSS_POOL_DETAIL:
        return _CROSS_POOL, _CROSS_POOL_DETAIL
    try:
        from engine import cross_league as xl
        pooled, _info, _flags = xl.build_pool("Champions League")
        _CROSS_POOL = {t for r in pooled for t in (r.home_team, r.away_team)}
        _CROSS_POOL_DETAIL = f"{len(_CROSS_POOL)} teams (cross-model pool)"
    except Exception as e:
        _CROSS_POOL_DETAIL = (f"pool unavailable ({str(e)[:55]}) — rerun with the "
                              f"project interpreter (Python 3.12, scipy)")
    return _CROSS_POOL, _CROSS_POOL_DETAIL


def audit(league: str, fit_season: str, fixtures_season: str,
           check_odds: bool) -> dict:
    whitelisted = league in WHITELISTED_LEAGUES
    row = {"league": league,
           "deploy_eligible": whitelisted,
           "history": "", "fixtures": "", "odds": "", "names": "",
           "blockers": []}

    # 1. HISTORY — football-data first; leagues it can't carry (HNL, continental
    # comps) fall back to the results multi-source (API-Football -> TheSportsDB
    # single-source T2), so the audit reports what the daily run ACTUALLY sees.
    from data.multi_source_concrete import get_historical_results
    if league in UNCOVERED_LEAGUES:
        try:
            res = get_historical_results(league, fit_season)
            src = res[0].source if res else "?"
            model_names = {r.home_team for r in res} | {r.away_team for r in res}
            if len(res) < MIN_HISTORY:
                row["history"] = f"THIN ({len(res)})"
                row["blockers"].append(
                    f"only {len(res)} historical matches ({src}), below the {MIN_HISTORY} floor")
            else:
                row["history"] = f"{len(res)} matches ({src})"
        except Exception as e:
            row["history"] = "NOT COVERED"
            row["blockers"].append("no working history source for this competition")
            model_names = set()
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
        except odds_mod.QuotaExhausted as e:
            # External, self-resetting limit (monthly) — not a coverage gap, so
            # call it out as such instead of a generic FAILED.
            row["odds"] = "QUOTA EXHAUSTED"
            row["blockers"].append(f"odds: {str(e)[:70]}")
        except Exception as e:
            row["odds"] = "FAILED"
            row["blockers"].append(f"odds: {str(e)[:70]}")

    # 4. NAMES — the silent killer. A club the model knows under another
    # spelling looks identical to a club it has never seen. For the continental
    # competitions the rating model is the cross-model pooled graph, so that is
    # the roster their fixture names must resolve against — comparing them to
    # the per-competition history would report a league blocked that the daily
    # run actually covers.
    if fixture_names:
        known_new = set(tsdb.KNOWN_NEW_TO_DIVISION_2627.get(league, ()))
        if is_cross_league(league):
            pool_teams, detail = _cross_pool_teams()
            if pool_teams is None:
                row["names"] = detail
                row["blockers"].append(f"names: {detail}")
            else:
                matched = len(fixture_names & pool_teams)
                unresolved = sorted(fixture_names - pool_teams - known_new)
                row["names"] = f"{matched}/{len(fixture_names)} matched"
                if unresolved:
                    row["blockers"].append(
                        f"{len(unresolved)} club(s) absent from the pooled "
                        f"graph: {', '.join(unresolved[:4])}")
        elif model_names:
            unresolved = sorted(fixture_names - model_names - known_new)
            matched = len(fixture_names & model_names)
            row["names"] = f"{matched}/{len(fixture_names)} matched"
            if unresolved:
                row["blockers"].append(
                    f"{len(unresolved)} unmapped club name(s): {', '.join(unresolved[:4])}")
        else:
            row["names"] = "n/a"
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
    # cp1252-safe on Windows consoles — the Ƈ glyph cannot encode there.
    print(f"{'league':<22}{'history':<14}{'fixtures':<14}"
          f"{'odds':<22}{'names':<14}verdict")
    print("-" * 108)

    rows = []
    for league in WHITELISTED_LEAGUES:
        r = audit(league, a.fit_season, a.fixtures_season, not a.no_odds)
        rows.append(r)
        if not r["blockers"]:
            verdict = "READY"
        elif r["deploy_eligible"]:
            verdict = "BLOCKED (deploy league)"
        else:
            verdict = "blocked (scan-only)"
        print(f"{r['league']:<22}{r['history']:<14}{r['fixtures']:<14}"
              f"{r['odds']:<22}{r['names']:<14}{verdict}")

    print("-" * 108)
    print("\nBLOCKERS IN DETAIL\n")
    for r in rows:
        if r["blockers"]:
            marker = "!!" if r["deploy_eligible"] else "  "
            print(f"{marker} {r['league']}:")
            for b in r["blockers"]:
                print(f"     - {b}")

    ready = [r for r in rows if not r["blockers"]]
    deploy_ready = [r for r in ready if r["deploy_eligible"]]
    deploy_total = [r for r in rows if r["deploy_eligible"]]
    print(f"\nSUMMARY")
    print(f"  fully ready               : {len(ready)} of {len(rows)}")
    print(f"  DEPLOY-eligible and ready : {len(deploy_ready)} of {len(deploy_total)}")
    print(f"  (unified pool 2026-08-10: every whitelisted league is deploy-")
    print(f"   eligible — a blocked league costs you coverage AND deployable edge)")


if __name__ == "__main__":
    main()
