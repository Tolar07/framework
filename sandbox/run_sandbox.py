"""Friendlies sandbox runner: source -> rate -> log -> settle -> board -> send.

USAGE
  python sandbox/run_sandbox.py              # rate + log upcoming friendlies
  python sandbox/run_sandbox.py --settle     # settle finished legs first
  python sandbox/run_sandbox.py --send       # also deliver the board to Telegram
  python sandbox/run_sandbox.py --league-filter Premier_League

WHAT IT TESTS (the wait-period machinery)
  The main pipeline idles in pre-season; this runs the same shapes on real
  live Club Friendlies: cross-league model fit/reuse through the brain,
  fixture sourcing from TheSportsDB, rating, paper-leg logging, settlement
  from the source, and brain persistence.

QUARANTINE
  Legs live in sandbox/sandbox_log.json with phase="sandbox" and are mirrored
  into the brain under that phase. The Phase-3 gate, calibration and CLV
  reports all filter by the PAPER phase, so friendlies can never satisfy the
  gate or move the engine. No friendly odds exist in the framework's sources,
  so sandbox CLV is always NO DATA — PENDING (this tests machinery, not edge).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.football_data_source import load_league, UNCOVERED_LEAGUES
from data import thesportsdb_fixtures as tsdb
from engine import cross_league as xleague
from engine.dixon_coles import predict, FIT_VERSION
from engine import markets as mkt
from brain.store import Brain, content_hash, dc_to_payload, dc_from_payload
from clv.clv_logger import CLVLog
from output import notify
from sandbox import friendlies
from sandbox import live as friendly_live

SANDBOX_LOG = ROOT / "sandbox" / "sandbox_log.json"
SANDBOX_PHASE = "sandbox"

# The 18-league whitelist minus continental-only sources: every league the
# main pipeline fits that football-data.co.uk carries.
def _pooled_teams(leagues: list[str]) -> tuple[list, list[str]]:
    """(pooled MatchResults, team_keys) from each league's COMPLETED (2526)
    season — the same fit data the main pipeline uses, cached by load_league."""
    pooled, team_keys, seen = [], [], set()
    for lg in leagues:
        try:
            res, _ = load_league(lg, "2526")
        except Exception:
            continue  # that season simply isn't published for this league yet
        pooled.extend(res)
        for r in res:
            for t in (r.home_team, r.away_team):
                if t not in seen:
                    seen.add(t)
                    team_keys.append(t)
    return pooled, team_keys


def _cross_model(brain: Brain, pooled: list, fit_config: str, flags: list):
    """Fit or reuse the 'cross:Club Friendlies' model, keyed by content_hash —
    the same provenance rule as the continental pipeline: identical pool +
    config => identical fit, reused verbatim."""
    h = content_hash(pooled, salt=f"cross:Club Friendlies:{fit_config}")
    row = brain.load_model_state("cross:Club Friendlies")
    if row is not None and row["content_hash"] == h:
        flags.append("Sandbox model: reused (identical pool — no refit)")
        return dc_from_payload(row["payload"]), True
    model, _info, mflags = xleague.fit_cross_league(
        "Club Friendlies", pool=(pooled, {"weakly_anchored": []}))
    if model is not None and brain:
        brain.save_model_state(
            "cross:Club Friendlies", "cross", FIT_VERSION,
            h, model.n_matches_fit, None, None, dc_to_payload(model))
    flags += mflags
    flags.append("Sandbox model: freshly fitted")
    return model, False


def _inverted_aliases() -> dict[str, str]:
    """tsdb_name.lower() -> model_key across all leagues."""
    inv = {}
    for aliases in tsdb.TEAM_ALIASES.values():
        for tsdb_name, model_key in aliases.items():
            inv.setdefault((tsdb_name or "").lower(), model_key)
    return inv


def _fuzzy(model_teams: set[str], name: str) -> Optional[str]:
    """Single unambiguous normalized substring match, else None (NO DATA)."""
    n = name.lower().strip()
    if not n:
        return None
    hits = [t for t in model_teams
            if n in t.lower() or t.lower() in n]
    return hits[0] if len(hits) == 1 else None


def _map_fixture(model_teams: set[str], inv: dict,
                 home: str, away: str):
    hk = inv.get(home.lower()) or _fuzzy(model_teams, home)
    ak = inv.get(away.lower()) or _fuzzy(model_teams, away)
    if hk in model_teams and ak in model_teams:
        return hk, ak
    return None, None


def _pick_market(p) -> tuple[str, float]:
    """The strongest DEPLOYABLE market per the model — the sandbox leg market."""
    best, best_p = None, -1.0
    for market in mkt.DEPLOYABLE:
        mp = mkt.model_prob(market, p)
        if mp is not None and mp > best_p:
            best, best_p = market, mp
    return best, best_p


def main() -> int:
    ap = argparse.ArgumentParser(description="Friendlies sandbox runner")
    ap.add_argument("--days-ahead", type=int, default=14)
    ap.add_argument("--send", action="store_true",
                    help="deliver the board via Telegram")
    ap.add_argument("--settle", action="store_true",
                    help="settle finished sandbox legs before rating")
    ap.add_argument("--league-filter", default=None,
                    help="only pool these leagues (comma list of keys)")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="after rating, live-watch today's friendlies, polling "
                         "every N seconds, settling each at full time")
    args = ap.parse_args()

    brain = Brain()
    log = CLVLog(path=SANDBOX_LOG)
    flags: list[str] = []
    lines: list[str] = []

    from run_daily import SCAN_LEAGUES
    leagues = [l for l in SCAN_LEAGUES if l not in UNCOVERED_LEAGUES]
    if args.league_filter:
        keep = {s.strip().replace("_", " ") for s in args.league_filter.split(",")}
        leagues = [l for l in leagues if l in keep]

    t0 = time.time()

    # --- settle first (finished friendlies) ----------------------------------
    settled = 0
    if args.settle:
        for leg in [l for l in log.legs if l.phase == SANDBOX_PHASE and l.hit is None]:
            # the TheSportsDB event id was pinned into the capture path at log time
            cap = (leg.entry_capture_path or "")
            eid = cap[len("EVENT:"):] if cap.startswith("EVENT:") else ""
            if not eid:
                continue
            ev = friendlies.lookup_event(eid)
            if ev is None:
                continue
            hit = mkt.settle(leg.market, ev["fthg"], ev["ftag"])
            if hit is None:
                continue
            log.log_result(leg.leg_id, ft_result=f"{ev['fthg']}-{ev['ftag']}", hit=hit)
            settled += 1
    if settled:
        flags.append(f"Sandbox settled {settled} leg(s) from TheSportsDB")

    # --- model (fit or reuse through the brain) -------------------------------
    pooled, team_keys = _pooled_teams(leagues)
    model, reused = _cross_model(brain, pooled, f"{leagues}", flags)
    if model is None:
        flags.append("Sandbox: no model — NO DATA — PENDING")
    else:
        model_teams = set(model.teams)

    # --- source friendlies ----------------------------------------------------
    team_ids = friendlies.resolve_team_ids(team_keys)
    fixtures = friendlies.upcoming_friendlies(team_ids, days_ahead=args.days_ahead)
    flags.append(f"Sandbox: {len(fixtures)} friendly fixture(s) in the next "
                 f"{args.days_ahead} days from {len(team_ids)} resolvable clubs")
    if not fixtures:
        lines.append("SANDBOX BOARD — Club Friendlies")
        lines.append("NO FIXTURES in the window (or no clubs resolvable) — "
                     "NO DATA — PENDING")
        lines.append("")
        lines.append("The sandbox only rates friendlies between clubs the "
                     "model knows; nothing is guessed.")
        _finish(lines, flags, args.send, reused, t0, brain, log)
        return 0

    inv = _inverted_aliases()
    n_rated = 0
    for fx in fixtures:
        hk, ak = _map_fixture(model_teams, inv, fx.home_team, fx.away_team)
        if hk is None or ak is None:
            lines.append(f"NO DATA — PENDING  {fx.home_team} v {fx.away_team} "
                         f"({fx.date}) — a club isn't known to the model")
            continue
        p = predict(model, hk, ak)
        if p is None:
            lines.append(f"NO DATA — PENDING  {fx.home_team} v {fx.away_team} "
                         f"({fx.date}) — unratable pairing")
            continue
        n_rated += 1
        market, mp = _pick_market(p)
        lines.append(
            f"{fx.date}  {fx.home_team} v {fx.away_team}\n"
            f"    model {p.p_home:.0%} / {p.p_draw:.0%} / {p.p_away:.0%}"
            + (f"  — leg logged: {mkt.display(market, hk, ak)} at p={mp:.0%}"
               if market else "  — no deployable market"))
        if market:
            # Never re-log a fixture already logged in this sandbox (re-runs
            # must not inflate the ledger).
            dup = [l for l in log.legs if l.phase == SANDBOX_PHASE
                   and l.fixture == f"{fx.home_team} v {fx.away_team}"
                   and l.match_date == fx.date]
            if dup:
                continue
            # entry_capture_path pins the TheSportsDB event id so settlement
            # fetches the EXACT match (never a same-pairing meeting).
            log.log_entry(
                league="Club Friendlies",
                fixture=f"{fx.home_team} v {fx.away_team}",
                market=market, model_prob=mp, entry_odds=None,
                entry_capture_path=f"EVENT:{fx.id_event}",
                phase=SANDBOX_PHASE, match_date=fx.date)

    # --- close out -------------------------------------------------------------
    lines.insert(0, f"SANDBOX BOARD — Club Friendlies ({len(fixtures)} "
                    f"in window, {n_rated} rated)")
    lines.append("")
    lines.append("Sandbox CLV: NO DATA — PENDING (no friendly odds source — "
                 "this tests machinery, not edge)")
    if args.watch:
        def _settle_live(eid: str, score: str, state: str) -> int:
            ev = friendlies.lookup_event(eid)  # None unless the source says FT
            if ev is None:
                return 0
            n = 0
            for leg in [l for l in log.legs
                        if (l.entry_capture_path or "") == f"EVENT:{eid}"
                        and l.hit is None]:
                hit = mkt.settle(leg.market, ev["fthg"], ev["ftag"])
                if hit is None:
                    continue
                log.log_result(leg.leg_id, ft_result=f"{ev['fthg']}-{ev['ftag']}",
                               hit=hit)
                n += 1
            return n
        print("\n".join(lines))
        print("\n--- live watch ---")
        friendly_live.live_watch(args.watch, _settle_live)
        _finish(lines, flags, args.send, reused, t0, brain, log)
        return 0
    _finish(lines, flags, args.send, reused, t0, brain, log)
    return 0


def _finish(lines: list[str], flags: list[str], send: bool, reused: bool,
            t0: float, brain: Brain, log: CLVLog) -> None:
    body = "\n".join(lines)
    flags.append(f"Sandbox ran in {time.time() - t0:.0f}s")
    if send:
        ok, deliver_flags = notify.deliver(body)
        flags += deliver_flags
        print("delivered" if ok else "delivery skipped")
    else:
        print(body)
    brain.sync_legs([Path(__file__).parent / "sandbox_log.json"])
    print("\n".join("  " + f for f in flags))
    brain.close()


if __name__ == "__main__":
    sys.exit(main())
