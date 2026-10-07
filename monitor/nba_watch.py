"""
NBA LINE WATCH — every 15 minutes before tip-off, the sharp line against
SportyBet (order 41 NBA board; Architect 2026-10-07: "build A and B
together and C").

The biggest edge on a soft book is team news it hasn't priced yet: a star
ruled out moves the sharp total/spread 3-8 points within minutes while
SportyBet can lag. The evening board looks once; this looks every 15 minutes
while any SportyBet NBA game tips off in the next AHEAD hours:

  1. every matched game's sharp line (ESPN) is compared with the FIRST line
     the watch saw that night; a move of MOVE_SPREAD / MOVE_TOTAL points or
     more is a line move;
  2. SportyBet's prices are re-checked against the CURRENT sharp line with
     the board's own rule (engine/nba_value.candidates): a new value pick on
     a game the board and the watch haven't picked yet is alerted — one pick
     per game, like the board — and saved to output/picks/nba_watch_<date>.json,
     where run_nba.py grades it (closing value included);
  3. a line move after which SportyBet's winner price still disagrees with
     the sharp line by more than nba_value.MAX_ML_GAP is reported as a LAG
     (no pick: a gap that size can also be a wrong match — check by hand);
  4. every ladder is saved for the ladder study (engine/nba_ladder.py).

Alerts go to the Architect's own chat only (like the NBA board). A LIVE TEST
since 2026-10-07: the Architect places a pick by hand from its SportyBet code
(orders 26, 41); the framework never stakes.

GitHub drops crons, so the watch is ONE job that loops (as monitor/news_loop.py):
nba_watch.yml's cron ticks and daily.yml's evening run start it; a run that
finds an older one going exits; it hands off before the 6-hour job limit.
Git sync and saving happen only inside GitHub Actions.

    python monitor/nba_watch.py --once --no-send     one round, print only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import run_nba  # noqa: E402
from data import nba_source as ns  # noqa: E402
from engine import nba_ladder as nl  # noqa: E402
from engine import nba_teams as nt  # noqa: E402
from engine import nba_value as nv  # noqa: E402

AHEAD = timedelta(hours=6)          # watch games tipping within this
EVERY_MIN = 15
MOVE_SPREAD, MOVE_TOTAL = 1.5, 3.0  # points the sharp line must move to count
HANDOFF_AFTER = timedelta(hours=5, minutes=30)
WATCH_DIR = ROOT / "output" / "nba_watch"
LEDGER_DIR = run_nba.LEDGER_DIR
API = "https://api.github.com/repos/{repo}/actions/workflows/nba_watch.yml"


def lagos_date(tip: datetime) -> str:
    return tip.astimezone(run_nba.LAGOS).date().isoformat()


def _load(path: Path, empty: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty


def matched_games(now: datetime, events: list, espn: list) -> list[tuple]:
    """[(stage, event, tip, home Team, away Team, ESPN game)] tipping in (now, now + AHEAD]."""
    out = []
    for stage, e in events:
        if not e.get("estimateStartTime"):
            continue
        tip = run_nba._tip_utc(e["estimateStartTime"])
        if not now < tip <= now + AHEAD:
            continue
        ht, _ = nt.sportybet(e.get("homeTeamName"), e.get("homeTeamId"))
        at, _ = nt.sportybet(e.get("awayTeamName"), e.get("awayTeamId"))
        if ht is None or at is None:
            continue                     # the board flags mapping problems
        g = next((g for g in espn if nt.by_espn(g.home) == ht and nt.by_espn(g.away) == at
                  and abs((datetime.fromisoformat(g.tip.replace("Z", "+00:00")) - tip).total_seconds())
                  < 6 * 3600), None)
        if g is not None:
            out.append((stage, e, tip, ht, at, g))
    return out


def check(now: datetime, games: list[tuple], state: dict, taken: set) -> tuple[list[dict], list[str], list[dict]]:
    """One round on already-fetched games (each ESPN game with its CURRENT line).
    Returns (new watch picks, LAG notes, ladder snapshot rows). Updates `state`
    ({event_id: first sharp line, lags reported}) and `taken` (event ids that
    already have a board or watch pick)."""
    picks, lags, snaps = [], [], []
    for stage, e, tip, ht, at, g in games:
        eid = e.get("eventId")
        snaps.append(nl.snapshot_row(now, stage, e, ht.key, at.key, g))
        if not (g.ml_home and g.ml_away):
            continue
        first = state.setdefault("first", {}).setdefault(eid, {
            "at": now.strftime("%H:%MZ"), "spread": g.spread, "total": g.total,
            "ml_home": g.ml_home, "ml_away": g.ml_away})
        moves = []
        if g.spread is not None and first["spread"] is not None and abs(g.spread - first["spread"]) >= MOVE_SPREAD:
            moves.append(f"spread {first['spread']:+g} → {g.spread:+g}")
        if g.total is not None and first["total"] is not None and abs(g.total - first["total"]) >= MOVE_TOTAL:
            moves.append(f"total {first['total']:g} → {g.total:g}")
        label = f"{e.get('homeTeamName')} v {e.get('awayTeamName')}"
        sb_p, sharp_p = nv.sportybet_winner_chance(e), nv.devig(g.ml_home, g.ml_away)
        if sb_p is not None and abs(sb_p - sharp_p) > nv.MAX_ML_GAP:
            if moves and eid not in state.setdefault("lags", []):
                state["lags"].append(eid)
                lags.append(f"{label}: sharp line moved since {first['at']} ({'; '.join(moves)}) but "
                            f"SportyBet's winner price still says {sb_p:.0%} vs the sharp {sharp_p:.0%} — "
                            f"SportyBet hasn't caught up, or the match is wrong: check by hand")
            continue
        if eid in taken:
            continue
        found, _suspect = nv.candidates(e, g)
        if not found:
            continue
        best = max(found, key=lambda r: (r["ev"], r["chance"]))
        min_ev = nv.MIN_EV_WINNER if best["market_id"] == "219" else nv.MIN_EV_LINE
        reason = (f"sharp line moved since {first['at']}: {'; '.join(moves)}" if moves
                  else "new value since the evening board")
        picks.append({**best, "source": "watch", "reason": reason, "found_at": now.isoformat(),
                      "stage": stage, "event_id": eid, "home_key": ht.key, "away_key": at.key,
                      "bet365": {"pick": nt.bet365_pick(best, ht, at),
                                 "take_at": nt.bet365_take_at(best, min_ev, nv.BAND[0])},
                      "espn_id": g.id, "espn_date": g.tip[:10], "tip": tip.isoformat(),
                      "home": e.get("homeTeamName"), "away": e.get("awayTeamName"),
                      "pick": nv.display(best, e.get("homeTeamName"), e.get("awayTeamName")),
                      "sharp": {"ml_home": g.ml_home, "ml_away": g.ml_away,
                                "spread": g.spread, "total": g.total},
                      "code": None, "result": None, "score": None, "close_value": None})
        taken.add(eid)
    return picks, lags, snaps


def render(now: datetime, run_id: str, picks: list[dict], lags: list[str]) -> str:
    L = ["🏀 OLP XDV · NBA LINE WATCH — LIVE TEST: load the code, place it by hand (orders 26, 41)",
         f"Run ID: {run_id}", f"Checked {now.astimezone(run_nba.LAGOS):%H:%M} Lagos (WAT)", ""]
    for p in picks:
        tip = datetime.fromisoformat(p["tip"]).astimezone(run_nba.LAGOS)
        tag = " · PRESEASON (test only)" if p["stage"] == "preseason" else ""
        L += [f"{tip:%H:%M}  {p['home']} v {p['away']}{tag}",
              f"   {p['pick']} @{p['price']:.2f} · chance {p['chance']:.0%} · fair {p['fair_price']:.2f} "
              f"· value {p['ev']:+.1%}",
              f"   why: {p['reason']}",
              f"   code {p['code'] or 'PENDING'}"]
        if (p.get("bet365") or {}).get("pick"):
            L.append(f"   bet365: {p['bet365']['pick']} · take at {p['bet365']['take_at']:.2f}+")
        L.append("")
    if lags:
        L += ["LAG — check by hand (no pick):"] + [f" • {n}" for n in lags] + [""]
    L.append("Prices move fast near tip-off: check the price is still there before acting.")
    return "\n".join(L)


# ── one round with fetching, sending and saving ──────────────────────────────
def run_round(now: datetime, send: bool = True) -> str:
    try:
        events = run_nba.sportybet_events()
    except Exception as e:  # noqa: BLE001
        return f"SportyBet NBA feed unavailable ({str(e)[:80]})"
    soon = [(s, e) for s, e in events if e.get("estimateStartTime")
            and now < run_nba._tip_utc(e["estimateStartTime"]) <= now + AHEAD]
    if not soon:
        return "no NBA game in the next 6 hours"
    days = sorted({(run_nba._tip_utc(e["estimateStartTime"]) + d).date()
                   for _s, e in soon for d in (timedelta(hours=-6), timedelta(0))})
    espn = [g for d in days for g in ns.scoreboard(d, use_cache=False)]
    games = matched_games(now, soon, espn)
    for *_rest, g in games:
        ns.attach_odds(g, use_cache=False)
    by_date: dict[str, list[tuple]] = {}
    for item in games:
        by_date.setdefault(lagos_date(item[2]), []).append(item)
    all_picks, all_lags, snaps = [], [], []
    for day, items in by_date.items():
        state_path, ledger = WATCH_DIR / f"{day}.json", LEDGER_DIR / f"nba_watch_{day}.json"
        state = _load(state_path, {"date": day})
        doc = _load(ledger, {"date": day, "picks": []})
        board = _load(LEDGER_DIR / f"nba_{day}.json", {"picks": []})
        taken = {p["event_id"] for p in board.get("picks", []) + doc["picks"]}
        picks, lags, rows = check(now, items, state, taken)
        snaps += rows
        if picks:
            try:
                run_nba.book(picks)
            except Exception as e:  # noqa: BLE001 — a booking failure never loses the alert
                print(f"  booking failed: {e}")
            doc["picks"] += picks
            LEDGER_DIR.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        WATCH_DIR.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
        all_picks += picks
        all_lags += lags
    nl.save(snaps, now)
    summary = f"{len(games)} games watched · {len(all_picks)} new picks · {len(all_lags)} lags"
    if all_picks or all_lags:
        text = render(now, run_nba._run_id(now), all_picks, all_lags)
        print(text)
        owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
                 or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
        if send and owner:
            from output import notify
            ok, notes = notify.send_telegram(text, chat_id=owner)      # the Architect only
            summary += f" · sent {'OK' if ok else 'FAILED'} {notes}"
    return summary


# ── the loop (GitHub Actions) ────────────────────────────────────────────────
def next_round(now: datetime) -> datetime:
    nxt = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while nxt.minute % EVERY_MIN:
        nxt += timedelta(minutes=1)
    return nxt


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def other_loop_running(repo: str, token: str, my_run_id: int) -> bool:
    url = API.format(repo=repo) + "/runs?status=in_progress&per_page=20"
    req = urllib.request.Request(url, headers=_headers(token))  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        runs = json.load(r).get("workflow_runs", [])
    return any(int(r["id"]) < my_run_id for r in runs)


def hand_off(repo: str, token: str) -> None:
    body = json.dumps({"ref": "main", "inputs": {"handoff": "true"}}).encode()
    req = urllib.request.Request(API.format(repo=repo) + "/dispatches", data=body,  # noqa: S310
                                 method="POST", headers=_headers(token))
    with urllib.request.urlopen(req, timeout=30):  # noqa: S310 (fixed https URL)
        pass


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)  # noqa: S603,S607 (fixed git args)


def in_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def sync() -> None:
    if in_actions():                 # never reset a desktop checkout
        _git("fetch", "-q", "origin", "main")
        _git("reset", "-q", "--hard", "origin/main")


def persist(now: datetime) -> str:
    if not in_actions():
        return "not saved (outside GitHub Actions)"
    _git("add", "output/picks", "output/nba_watch", "output/nba_ladders")
    if _git("diff", "--staged", "--quiet").returncode == 0:
        return "nothing to save"
    _git("commit", "-q", "-m", f"nba watch {now:%H:%M} [skip ci]")
    for _ in range(3):
        if _git("push", "-q", "origin", "HEAD:main").returncode == 0:
            return "saved"
        if _git("pull", "-q", "--rebase", "origin", "main").returncode != 0:
            _git("rebase", "--abort")
            break
    return "NOT SAVED — main moved and a file conflicted; the next round re-checks"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV NBA line watch")
    ap.add_argument("--once", action="store_true", help="one round, then stop")
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--handoff", action="store_true", help="started by the previous loop run")
    a = ap.parse_args(argv)
    if a.once:
        print(run_round(datetime.now(UTC), send=not a.no_send))
        return 0
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    if not a.handoff and repo and token and other_loop_running(repo, token, run_id):
        print("an NBA watch loop is already running — nothing to do")
        return 0
    started = datetime.now(UTC)
    if a.handoff:
        time.sleep(max(0.0, (next_round(started) - datetime.now(UTC)).total_seconds()))
    while True:
        now = datetime.now(UTC)
        sync()
        try:
            summary = run_round(now, send=not a.no_send)
        except Exception as e:  # noqa: BLE001 — one bad round never ends the loop
            summary = f"round failed: {e}"
        print(f"[{now:%H:%M}Z] {summary}")
        print(f"[{now:%H:%M}Z] {persist(now)}")
        if summary.startswith("no NBA game"):
            print("no game ahead — watch done for now")
            return 0
        wake = next_round(datetime.now(UTC))
        if wake - started >= HANDOFF_AFTER:
            if repo and token:
                hand_off(repo, token)
                print("handed off to a fresh run (job time limit)")
            return 0
        time.sleep(max(0.0, (wake - datetime.now(UTC)).total_seconds()))


if __name__ == "__main__":
    raise SystemExit(main())
