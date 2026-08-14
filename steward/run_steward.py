"""The Data Steward — the "always fetch the data the board needs" agent.

Architect request (2026-08-12): *"find a way to solve [NO DATA] for good,
create an agent to always fetch the data needed."*

WHY THIS EXISTS
  Every data source is only refreshed when the daily run happens to re-fetch
  on a stale cache — a stale or failed fetch silently empties a source, and
  the 07:00 board reads whatever was left. The steward is a scheduled one-shot
  pass that fetches EVERYTHING the board needs AHEAD of the daily run, so the
  board always reads fresh data. Registered at 06:00 (pre-board) and 15:00
  (afternoon refresh for evening fixtures).

DESIGN
  Best-effort per source: a source failure is a flag in steward_state.json,
  never a crash — the daily run does its own reads and is unaffected. Every
  fetch below reuses the source's OWN TTL/cache discipline, so a warm pass is
  cheap and a cold pass warms exactly what is stale (incremental).

SOURCES
  sportybet  booking.bridge.refresh_sportybet_cache(WHITELISTED_LEAGUES)
             Playwright; the builder skips caches <6h old, so this is
             incremental. The heaviest source — failures are flags.
  odds       pipeline.odds.fetch_odds(lg) per whitelisted league. Quota-
             guarded (walks ODDS_API_KEY -> backup -> tertiary, refuses below
             the floor); on full quota exhaustion it INTERNALLY serves the
             api-football free fallback — so the fallback is warmed by the
             same pull, never double-spent.
  af_odds    data.api_football_odds.fetch_odds(lg) — warmed ONLY for leagues
             the Odds API pull above failed to serve, and only while the
             api-football daily quota is above its floor. The fallback's own
             100 req/day budget is a scarce shared resource: warming it
             unconditionally for all 18 leagues would exhaust the day BEFORE
             it is needed, sabotaging the very fallback the steward exists to
             keep fresh.
  tsdb       data.thesportsdb_fixtures.fetch_upcoming(lg, fixtures_season)
             6h TTL — the steward warms them so the orchestrator's first
             fixture source is never stale.
  espn       data.espn_source.fetch_upcoming(lg) — keyless leg of the
             multi-source fixture chain.
  clubelo    data.clubelo_source.fetch_snapshot() — one keyless all-clubs CSV
             (the STRETCH rating fallback; a warm snapshot keeps it fresh).
  fdc        football-data live-season CSV — VERIFY PRESENCE only. The health
             monitor self-heals a stale one; the steward must not duplicate.

ARTEFACTS
  logs/steward_state.json   per-source {fetched_at, ok, detail, counts}
  logs/steward.log          append-only proof-of-life lines

ALERTING
  State-change only (same _should_alert discipline as monitor/health_monitor):
  a source that was fine and goes red alerts once. notify.send_alert() stays
  gated on TELEGRAM_ALERTS_ENABLED (Architect 2026-08-11 — monitor alerts
  log locally by default).

USAGE
  python steward/run_steward.py              # one full pass + state file
  python steward/run_steward.py --no-alert   # pass only, no alert evaluation
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402  (loads .env — the keys below all come from it)
from engine.leagues import WHITELISTED_LEAGUES  # noqa: E402

LOG_DIR = ROOT / "logs"
STATE_PATH = LOG_DIR / "steward_state.json"
LOG_PATH = LOG_DIR / "steward.log"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(line: str) -> None:
    """Append one proof-of-life line. Never raises — a logging failure must
    not fail the steward pass."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"[{_now_iso()}] {line}\n")
    except OSError:
        pass


def _fixtures_season(fit_season: str) -> str:
    """'2526' -> '2627' — the season being played now (mirrors
    orchestrator.next_season_code). The model is fit on the last COMPLETED
    season; fixtures come from the one now being played."""
    return f"{int(fit_season[:2]) + 1:02d}{int(fit_season[2:]) + 1:02d}"


# ---------------------------------------------------------------------------
# Per-source handlers. Each returns (ok: bool, detail: str) and never raises.
# ---------------------------------------------------------------------------

def _st_sportybet() -> tuple[bool, str]:
    """Playwright cache rebuild for every whitelisted league. The builder
    skips caches <6h old, so repeated passes are incremental."""
    from booking.bridge import refresh_sportybet_cache
    counts = refresh_sportybet_cache(leagues=list(WHITELISTED_LEAGUES))
    total = sum(counts.values()) if counts else 0
    return (total > 0,
            f"{len(counts)} league(s) cached, {total} fixture(s) — "
            f"{', '.join(sorted(counts)[:6])}" + ("…" if len(counts) > 6 else ""))


def _st_odds() -> tuple[bool, str, list[str]]:
    """The Odds API price pull per league. Returns (ok, detail, failed_leagues).

    QUOTA-FIRST: probe the monthly budget ONCE; below the floor the primary is
    down for the day, so per-league pulls are NOT attempted (they would each
    fall back to api-football and burn the fallback's own daily quota while
    tripping its burst breaker). A spent budget is a REAL condition — flagged
    red with the exact remaining count, and the gap list is the FULL whitelist:
    with the primary down, the api-football fallback is the source that must
    serve, so the steward warms it (its own quota/burst checks gate that)."""
    import pipeline.odds as odds_mod
    try:
        used, remaining = odds_mod.check_quota()
    except Exception as e:
        return False, f"quota probe failed ({str(e)[:50]})", []
    if remaining < odds_mod.QUOTA_FLOOR:
        return (False,
                f"Odds API quota spent ({remaining} left, floor "
                f"{odds_mod.QUOTA_FLOOR}) — primary down, fallback must serve",
                list(WHITELISTED_LEAGUES))
    priced = failed = 0
    failed_leagues: list[str] = []
    for lg in WHITELISTED_LEAGUES:
        try:
            fixtures, _ = odds_mod.fetch_odds(lg)
            if fixtures:
                priced += 1
            else:
                failed += 1
                failed_leagues.append(lg)
        except Exception as e:
            failed += 1
            failed_leagues.append(lg)
            _log(f"    odds {lg} failed: {str(e)[:70]}")
    ok = failed == 0
    detail = (f"{priced} league(s) priced, {failed} not served"
              + (f" — {', '.join(failed_leagues[:4])}" if failed_leagues else ""))
    return ok, detail, failed_leagues


_AF_WARM_CAP = 10  # leagues warmed per pass — bounds the paced burst


def _st_af_odds(failed_odds_leagues: list[str]) -> tuple[bool, str]:
    """api-football odds fallback for leagues the Odds API could NOT serve.

    Deliberately conditional (see module docstring): the fallback's 100
    req/day budget is shared and scarce, so it is only warmed where a gap
    exists, only while quota is above the floor, and capped at
    _AF_WARM_CAP leagues per pass (a safety valve on the paced burst). Every
    league warms incrementally (its own cache is reused), so a fresh warm
    costs nothing."""
    if not failed_odds_leagues:
        return True, "primary served all leagues — nothing to warm"
    from data.api_football_odds import fetch_odds, check_quota, \
        DAILY_FLOOR, QuotaExhausted
    try:
        _, remaining = check_quota()
    except Exception as e:
        return False, f"quota probe failed ({str(e)[:50]}) — not warming"
    warmable = [lg for lg in failed_odds_leagues if lg in WHITELISTED_LEAGUES]
    if remaining < DAILY_FLOOR + min(len(warmable), _AF_WARM_CAP):
        return True, f"quota low ({remaining} left, floor {DAILY_FLOOR}) — " \
                     f"fallback kept for the real need"
    priced = 0
    empty = 0
    failed: list[str] = []
    for lg in warmable[:_AF_WARM_CAP]:
        if lg not in WHITELISTED_LEAGUES:
            continue
        try:
            fixtures, _ = fetch_odds(lg, days_ahead=1)
            if fixtures:
                priced += 1
            else:
                empty += 1  # the fallback responded — nothing in window is honest
        except QuotaExhausted:
            _log("    af_odds daily quota exhausted mid-warm — stopping")
            break
        except Exception as e:
            failed.append(f"{lg} ({str(e)[:40]})")
    attempted = len(warmable[:_AF_WARM_CAP])
    if failed:
        return (False,
                f"warmed {priced} of {attempted} attempted league(s); "
                f"errors: {', '.join(failed[:4])}"
                + (f" ({empty} empty in window)" if empty else ""))
    return (True,
            f"warmed {priced} of {attempted} attempted league(s)"
            + (f" ({empty} had nothing in window)" if empty else ""))


def _st_tsdb(fixtures_season: str) -> tuple[bool, str]:
    """TheSportsDB fixtures for every whitelisted league (6h TTL — the
    orchestrator's first fixture source must never be stale).

    A SourceNoData (league NOT carried by the source) is a COVERAGE GAP, not an
    outage — the orchestrator's multi-source chain falls through for those
    leagues. Only a genuine exception (source unreachable) is a red flag."""
    from data import thesportsdb_fixtures as tsdb
    from data.multi_source import SourceNoData
    ok_count = gaps = failed = 0
    gap_leagues: list[str] = []
    failed_leagues: list[str] = []
    for lg in WHITELISTED_LEAGUES:
        try:
            fixtures, _ = tsdb.fetch_upcoming(lg, fixtures_season, days_ahead=14)
            if fixtures:
                ok_count += 1
        except SourceNoData as e:
            gaps += 1
            gap_leagues.append(lg)
        except Exception as e:
            failed += 1
            failed_leagues.append(f"{lg} ({str(e)[:40]})")
    detail = f"{ok_count} league(s) with upcoming fixtures, {gaps} not carried" \
             + (f" ({', '.join(gap_leagues[:4])})" if gap_leagues else "")
    if failed:
        detail += f"; {failed} FAILED: {', '.join(failed_leagues[:4])}"
    return failed == 0, detail


def _st_espn() -> tuple[bool, str]:
    """ESPN fixtures (keyless). A league with no verified ESPN slug raises
    ValueError — a COVERAGE GAP (the orchestrator's chain has other fixture
    sources), not an outage. An empty window is honest (source responded)."""
    from data import espn_source
    covered = no_slug = failed = 0
    no_slug_leagues: list[str] = []
    failed_leagues: list[str] = []
    for lg in WHITELISTED_LEAGUES:
        try:
            fixtures, _ = espn_source.fetch_upcoming(lg, "", days_ahead=14)
            covered += 1
        except ValueError:
            no_slug += 1
            no_slug_leagues.append(lg)
        except Exception as e:
            failed += 1
            failed_leagues.append(f"{lg} ({str(e)[:40]})")
    detail = f"{covered} league(s) covered"
    if no_slug:
        detail += f", {no_slug} no ESPN slug ({', '.join(no_slug_leagues[:4])})"
    if failed:
        detail += f"; {failed} FAILED: {', '.join(failed_leagues[:4])}"
    return failed == 0, detail


def _st_clubelo() -> tuple[bool, str]:
    """One keyless all-clubs ClubElo CSV snapshot (the STRETCH rating source).
    A warm snapshot keeps current-season ratings fresh for the fallback."""
    from data import clubelo_source
    try:
        payload = clubelo_source.fetch_snapshot()
        clubs = len(payload.get("clubs", []))
        return clubs > 0, f"{clubs} club(s) in the {payload.get('date')} snapshot"
    except Exception as e:
        return False, f"snapshot fetch failed ({str(e)[:50]})"


def _st_fdc() -> tuple[bool, str]:
    """football-data live-season CSV — verify presence only. The health
    monitor self-heals a stale one; the steward only checks it exists so a
    missing file surfaces as a flag, not a silent gap.

    The CSVs live flat in data/cache (a nested football_data/ dir may not
    exist) — mirror the health monitor's fallback."""
    cache_dir = ROOT / "data" / "cache"
    results = cache_dir / "football_data" if (cache_dir / "football_data").exists() \
        else cache_dir
    live = [p.name for p in sorted(results.glob("*_all.csv"))]
    if not live:
        return False, "no live-season (_all.csv) files present in data/cache"
    return True, f"{len(live)} live-season file(s): {', '.join(live[:4])}" \
                 + ("…" if len(live) > 4 else "")


# ---------------------------------------------------------------------------
# State + alerting
# ---------------------------------------------------------------------------

def _load_prev_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _should_alert(name: str, ok: bool, prev: dict, now: float) -> bool:
    """Alert ONLY on a state CHANGE to red: a source that was fine last pass
    and went red now. A source that was already red does not re-alert (same
    discipline as monitor/health_monitor — no daily spam for an open issue).

    `prev` is the full previous state dict (sources nested under "sources").
    A missing entry (no prior pass) counts as "was not red" so the first red
    pass alerts."""
    prev_ok = prev.get("sources", {}).get(name, {}).get("ok")
    return ok is False and prev_ok is not False


def _write_state(state: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        _log("WARN state write failed")


def run(alert: bool = True, fit_season: str = "2526") -> dict:
    """One full steward pass. Returns the state dict (also written to disk)."""
    started = time.time()
    now_iso = _now_iso()
    fixtures_season = _fixtures_season(fit_season)
    _log(f"steward pass START (fixtures season {fixtures_season})")

    # 1. SportyBet cache (Playwright — heaviest, run first while fresh).
    try:
        sb_ok, sb_detail = _st_sportybet()
    except Exception as e:  # belt-and-braces: a handler must never crash the pass
        sb_ok, sb_detail = False, f"unhandled ({str(e)[:80]})"

    # 2. Odds API primary (quota-guarded; internally falls back to api-football).
    try:
        odds_ok, odds_detail, odds_gap = _st_odds()
    except Exception as e:
        odds_ok, odds_detail, odds_gap = False, f"unhandled ({str(e)[:80]})", []

    # 3. api-football odds fallback — warmed ONLY for the exact leagues the
    #    primary missed, and only while its own daily quota is above the floor
    #    (the fallback's 100 req/day is scarce — never warmed unconditionally).
    try:
        af_ok, af_detail = _st_af_odds(odds_gap)
    except Exception as e:
        af_ok, af_detail = False, f"unhandled ({str(e)[:80]})"

    # 4. TheSportsDB fixtures.
    try:
        tsdb_ok, tsdb_detail = _st_tsdb(fixtures_season)
    except Exception as e:
        tsdb_ok, tsdb_detail = False, f"unhandled ({str(e)[:80]})"

    # 5. ESPN fixtures.
    try:
        espn_ok, espn_detail = _st_espn()
    except Exception as e:
        espn_ok, espn_detail = False, f"unhandled ({str(e)[:80]})"

    # 6. ClubElo snapshot.
    try:
        clubelo_ok, clubelo_detail = _st_clubelo()
    except Exception as e:
        clubelo_ok, clubelo_detail = False, f"unhandled ({str(e)[:80]})"

    # 7. football-data live-season CSV presence.
    try:
        fdc_ok, fdc_detail = _st_fdc()
    except Exception as e:
        fdc_ok, fdc_detail = False, f"unhandled ({str(e)[:80]})"

    now = time.time()
    prev = _load_prev_state()
    sources = {
        "sportybet": {"fetched_at": now_iso, "ok": sb_ok, "detail": sb_detail},
        "odds":      {"fetched_at": now_iso, "ok": odds_ok, "detail": odds_detail},
        "af_odds":   {"fetched_at": now_iso, "ok": af_ok, "detail": af_detail},
        "tsdb":      {"fetched_at": now_iso, "ok": tsdb_ok, "detail": tsdb_detail},
        "espn":      {"fetched_at": now_iso, "ok": espn_ok, "detail": espn_detail},
        "clubelo":   {"fetched_at": now_iso, "ok": clubelo_ok, "detail": clubelo_detail},
        "fdc":       {"fetched_at": now_iso, "ok": fdc_ok, "detail": fdc_detail},
    }
    state = {
        "pass": _now_iso(),
        "duration_s": round(now - started, 1),
        "fixtures_season": fixtures_season,
        "sources": sources,
    }
    _write_state(state)

    for name, s in sources.items():
        _log(f"  {name}: {'OK' if s['ok'] else 'FAIL'} — {s['detail']}")

    # State-change alert: only sources that WERE fine and went red.
    if alert:
        red = [name for name, s in sources.items()
               if _should_alert(name, s["ok"], prev, now)]
        if red:
            body = ("⚠ OLP XDV STEWARD — source(s) went red:\n"
                    + "\n".join(f"  {name}: {sources[name]['detail']}"
                                for name in red)
                    + "\n\nFull state: logs/steward_state.json")
            try:
                from monitor import alert_dispatcher
                results_disp = alert_dispatcher.dispatch_alert(
                    "warn",
                    f"OLP XDV STEWARD — {len(red)} source(s) went red",
                    body,
                    tags=red,
                )
                ok_sent = any(ok for ok, _ in results_disp.values())
                _log(f"alert dispatched={ok_sent} channels={list(results_disp.keys())}")
            except Exception as e:
                _log(f"WARN alert dispatch failed ({str(e)[:60]}), falling back to notify")
                try:
                    from output import notify
                    ok_sent, notes = notify.send_alert(body)
                    _log(f"alert sent (fallback) =={ok_sent} notes={'; '.join(notes)[:100]}")
                except Exception as e2:
                    _log(f"WARN alert failed ({str(e2)[:60]})")

    _log(f"steward pass DONE ({state['duration_s']}s, "
         f"{sum(1 for s in sources.values() if s['ok'])}/7 sources OK)")
    return state


def main() -> None:
    ap = argparse.ArgumentParser(description="OLP XDV Data Steward — fetch "
                                             "everything the board needs.")
    ap.add_argument("--no-alert", action="store_true",
                    help="skip state-change alert evaluation (still logs + writes state)")
    ap.add_argument("--season", default="2526",
                    help="season the model is FIT on (fixtures come from the next one)")
    args = ap.parse_args()
    state = run(alert=not args.no_alert, fit_season=args.season)
    bad = [n for n, s in state["sources"].items() if not s["ok"]]
    print(json.dumps(state, indent=2))
    if bad:
        print(f"steward: {len(bad)} source(s) not OK: {', '.join(bad)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
