"""Refit every Dixon-Coles league model with club names normalised across sources.

WHY: the base history (football-data.co.uk) names clubs "Ath Madrid"; the
current-season merge (football-data.org) names the same club "Club Atletico de
Madrid". The merge deduped on raw names, so nothing collided, both spellings
were appended, and fit() saw one club as two. On 2026-09-16, 67 of 84 fitted
models carried both short- and long-form names, meaning most leagues had clubs
whose match history was split across two identities -- which weakens every fit
and biases it toward overconfidence.

The merge itself is fixed in pipeline/production_stage_b, so new fits are clean.
This script rebuilds the models already on disk.

SAFETY
  - Back up brain/olp.db before running. The script does not delete anything;
    it overwrites a model only after that league's fit succeeds.
  - A league whose history will not load is SKIPPED with its existing model
    left untouched, never replaced with a thin or empty fit.
  - The football-data.org merge is best-effort. That API is rate-limited
    (10/min, 100/day), so across 80+ leagues most calls will be refused. A
    league that misses the merge is still refit from its base history, which is
    already strictly better than a split-identity model -- and the next
    pipeline run will merge current-season results with normalisation applied.

USAGE
    python scripts/refit_all_leagues.py            # refit all
    python scripts/refit_all_leagues.py --dry-run  # report only, write nothing
    python scripts/refit_all_leagues.py --league "La Liga"
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import config  # noqa: F401,E402  (loads .env)

from data.football_data_source import load_league  # noqa: E402
from engine.dixon_coles import fit  # noqa: E402
from pipeline.production_stage_b import _resolve_model_key  # noqa: E402

DB = REPO / "brain" / "olp.db"
FIT_SEASON = "2526"       # last COMPLETED season -- what the model is fit on
FIXTURES_SEASON = "2627"  # season being played -- what current results come from


def _team_count(payload: str) -> int:
    try:
        return len((json.loads(payload).get("teams") or {}))
    except Exception:
        return -1


def _merge_current_season(league: str, history: list) -> tuple[int, int]:
    """Best-effort merge of current-season results, names normalised first."""
    try:
        from data.multi_source_concrete import FootballDataOrgResultsSource
        fdo = FootballDataOrgResultsSource()
        results = (fdo.fetch(league=league, season=FIT_SEASON,
                             fixtures_season=FIXTURES_SEASON) or {}).get("results", [])
    except Exception:
        return 0, 0
    if not results:
        return 0, 0

    roster = {r.home_team for r in history} | {r.away_team for r in history}
    renamed = 0
    for r in results:
        h = _resolve_model_key(r.home_team, league, roster)
        a = _resolve_model_key(r.away_team, league, roster)
        if h != r.home_team:
            r.home_team, renamed = h, renamed + 1
        if a != r.away_team:
            r.away_team, renamed = a, renamed + 1

    existing = {(r.date, r.home_team, r.away_team) for r in history}
    added = 0
    for r in results:
        key = (r.date, r.home_team, r.away_team)
        if key not in existing:
            history.append(r)
            existing.add(key)
            added += 1
    return added, renamed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--league", default=None)
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "select model_key, n_matches, payload from model_state where kind='dc'"
    ).fetchall()

    targets = [(r["model_key"].split(":", 1)[1], r["n_matches"], _team_count(r["payload"]))
               for r in rows if ":" in r["model_key"]]
    if args.league:
        targets = [t for t in targets if t[0] == args.league]

    print(f"{'LEAGUE':34} {'teams':>11}  {'matches':>15}  status")
    print("-" * 82)

    improved = skipped = unchanged = 0
    for league, old_n, old_teams in sorted(targets):
        # ":carry" and other suffixed variants are separate artefacts; skip.
        if ":" in league:
            continue
        try:
            history, _ = load_league(league, FIT_SEASON)
        except Exception as e:
            print(f"{league[:33]:34} {'-':>11}  {'-':>15}  SKIP (history: {type(e).__name__})")
            skipped += 1
            continue

        if not history or len(history) < 20:
            print(f"{league[:33]:34} {'-':>11}  {len(history or []):>15}  SKIP (history too thin)")
            skipped += 1
            continue

        added, renamed = _merge_current_season(league, history)

        try:
            model = fit(history)
        except Exception as e:
            print(f"{league[:33]:34} {'-':>11}  {'-':>15}  SKIP (fit: {type(e).__name__})")
            skipped += 1
            continue

        new_teams = len(model.teams)
        delta = f"{old_teams}->{new_teams}"
        matches = f"{old_n}->{model.n_matches_fit}"
        note = f"+{added} cur, {renamed} renamed" if (added or renamed) else ""

        if new_teams < old_teams:
            improved += 1
            status = f"COLLAPSED {note}"
        else:
            unchanged += 1
            status = f"ok {note}"

        print(f"{league[:33]:34} {delta:>11}  {matches:>15}  {status}")

        if not args.dry_run:
            # dc_to_payload and content_hash live in brain.store, not
            # engine.dixon_coles -- same place production_stage_b imports them.
            from brain.store import Brain, content_hash, dc_to_payload
            b = Brain()
            b.save_model_state(
                f"dc:{league}", "dc", 1,
                content_hash(history, salt=f"dc:{league}:{FIT_SEASON}"),
                model.n_matches_fit, None, None, dc_to_payload(model))

    print("-" * 82)
    print(f"collapsed: {improved} | unchanged: {unchanged} | skipped: {skipped}"
          + ("   [DRY RUN — nothing written]" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
