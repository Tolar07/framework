"""Monitor live continental football and TRAIN THE BRAIN with real outcomes.

USAGE
  python monitor/run_monitor.py              # one pass: settle finished, report
  python monitor/run_monitor.py --watch 300  # poll every 300s until today's
                                             # events have all settled

WHY IT EXISTS
  The daily run records PREDICTIONS; until a scan-only continental match
  settles there was no path for its RESULT to reach the brain. This monitor is
  that path: it pulls the authoritative /scores feed, matches completed events
  to rated predictions (names mapped through the same aliases the engine
  uses), and records ft_result + a per-market hit. That model-vs-reality
  evidence is what the brain is trained on.

HONESTY (HR35)
  - A result is taken from the SOURCE (The Odds API /scores), never guessed.
  - A prediction with no exact fixture+date match is never settled.
  - A row already settled is never overwritten (first result wins).
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from urllib import request

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402  (loads .env -> ODDS_API_KEY)
import pipeline.odds as odds  # noqa: E402
from engine import markets as mkt  # noqa: E402
from brain.store import Brain  # noqa: E402

# Continental sports that actually carry PRICES today (verified 2026-08-05:
# UCL qualification is the only active continental key on The Odds API).
# Each maps to the framework's league label so predictions can be matched.
CONTINENTAL_SPORTS: dict[str, str] = {
    "soccer_uefa_champs_league_qualification": "Champions League",
}

# UCL/UEL qualifiers are scan-only (tier D): no capital, no paper legs. The
# monitor's job is the OUTCOME evidence, which needs no price.
SCAN_ONLY = True


def _json(url: str):
    req = request.Request(url)
    with request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _fetch_scores(sport: str) -> list[dict]:
    key = odds._get_key()
    url = (f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
           f"?apiKey={key}&daysFrom=2")
    return _json(url)


def _mapped(event: dict, league: str):
    """Odds-API names -> model keys via the same aliases the engine uses."""
    return (odds.map_team(league, event.get("home_team") or ""),
            odds.map_team(league, event.get("away_team") or ""))


def _fixture_split(fixture: str):
    parts = [s.strip() for s in fixture.split(" v ", 1)]
    return parts if len(parts) == 2 else (None, None)


def _settle_predictions(brain: Brain, league: str, event: dict) -> int:
    """Find rated predictions matching this completed event; grade and store
    their outcome. Returns prediction rows settled."""
    scores = sorted(event.get("scores") or [], key=lambda s: s.get("position", 0))
    if len(scores) < 2:
        return 0
    fthg, ftag = int(scores[0]["score"]), int(scores[1]["score"])
    ft_result = f"{fthg}-{ftag}"
    # find the prediction fixture: match event teams against stored fixtures
    home, away = _mapped(event, league)
    if not home or not away:
        return 0
    match_date = (event.get("commence_time") or "")[:10]
    rows = brain._conn.execute(
        "SELECT DISTINCT fixture, match_date FROM predictions "
        "WHERE league=? AND hit IS NULL AND match_date=?",
        (league, match_date)).fetchall()
    settled = 0
    for r in rows:
        r_home, r_away = _fixture_split(r["fixture"])
        if r_home != home or r_away != away:
            continue  # no exact match -> never settle a wrong match (HR35)
        hits = {}
        for market in mkt.ALL:
            h = mkt.settle(market, fthg, ftag)
            if h is not None:
                hits[market] = h
        settled += brain.record_outcomes(r["fixture"], match_date, ft_result, hits)
    return settled


def _status(event: dict) -> str:
    if event.get("completed"):
        return "COMPLETED"
    ct = event.get("commence_time") or ""
    try:
        kickoff = datetime.datetime.fromisoformat(ct.replace("Z", "+00:00"))
    except ValueError:
        return "?"
    now = datetime.datetime.now(datetime.timezone.utc)
    if now >= kickoff:
        return "LIVE"
    return "UPCOMING"


def _score_of(event: dict):
    """Current/final score if the source provides one, else None (never guessed)."""
    scores = sorted(event.get("scores") or [], key=lambda s: s.get("position", 0))
    if len(scores) >= 2:
        return f"{scores[0]['score']}-{scores[1]['score']}"
    return None


def _event_line(ev: dict) -> str:
    st = _status(ev)
    ct = ev.get("commence_time") or ""
    try:
        ko = datetime.datetime.fromisoformat(ct.replace("Z", "+00:00"))
    except ValueError:
        ko = None
    now = datetime.datetime.now(datetime.timezone.utc)
    home, away = ev.get("home_team") or "?", ev.get("away_team") or "?"
    if st == "UPCOMING" and ko:
        mins = int((ko - now).total_seconds() // 60)
        tail = f"kickoff in {mins} min"
    elif st == "LIVE":
        s = _score_of(ev)
        tail = f"LIVE {s}" if s else "LIVE — no in-play score from source (NO DATA)"
    else:
        s = _score_of(ev)
        tail = f"FT {s}" if s else "FT (no score)"
    return f"  {st:9s} {home:24s} v {away:24s}  {tail}"


def _live_watch(brain: Brain, interval: int) -> int:
    """Poll until every continental event for today has settled, printing a
    compact live board only when the state or score CHANGES."""
    today = datetime.date.today().isoformat()
    deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=16)
    last = None
    while datetime.datetime.now(datetime.timezone.utc) < deadline:
        lines, settled_total, pending = [], 0, False
        for sport, league in CONTINENTAL_SPORTS.items():
            try:
                events = _fetch_scores(sport)
            except Exception as e:
                lines.append(f"  {league}: fetch failed ({e})")
                continue
            todays = [e for e in events if (e.get("commence_time") or "")[:10] == today]
            lines.append(f"=== {league} — {len(todays)} event(s) today ===")
            for ev in sorted(todays, key=lambda e: e.get("commence_time", "")):
                st = _status(ev)
                if st in ("LIVE", "UPCOMING"):
                    pending = True
                lines.append(_event_line(ev))
                if st == "COMPLETED":
                    n = _settle_predictions(brain, league, ev)
                    settled_total += n
                    if n:
                        s = _score_of(ev)
                        lines.append(f"        -> settled {n} prediction row(s): {s}")
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")
        block = f"[{stamp} UTC]\n" + "\n".join(lines)
        if block != last:
            print(block, flush=True)
            last = block
        if not pending:
            print("\nAll today's continental events settled.", flush=True)
            return settled_total
        time.sleep(interval)
    print("\nWatch deadline reached.", flush=True)
    return settled_total


def run_once(brain: Brain, watch: bool = False) -> int:
    settled_total = 0
    for sport, league in CONTINENTAL_SPORTS.items():
        try:
            events = _fetch_scores(sport)
        except Exception as e:
            print(f"{league}: scores fetch failed ({e}) — NO DATA — PENDING")
            continue
        print(f"=== {league} — {sport} ({len(events)} events) ===")
        upcoming = 0
        for ev in sorted(events, key=lambda e: e.get("commence_time", "")):
            st = _status(ev)
            if st == "UPCOMING":
                upcoming += 1
            print(f"  {st:9s} {(ev.get('commence_time') or '')[:16]}  "
                  f"{ev.get('home_team') or '?':24s} v {ev.get('away_team') or '?':24s}")
            if st == "COMPLETED":
                n = _settle_predictions(brain, league, ev)
                if n:
                    scores = sorted(ev.get("scores") or [],
                                    key=lambda s: s.get("position", 0))
                    print(f"      -> settled {n} prediction row(s): "
                          f"{scores[0]['score']}-{scores[1]['score']}")
                settled_total += n
        if upcoming == 0 and all(_status(e) != "LIVE" for e in events):
            print("      (no live/upcoming events)")
    return settled_total


def main() -> int:
    ap = argparse.ArgumentParser(description="Continental outcome monitor")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="poll every N seconds until all today's events settle")
    args = ap.parse_args()

    brain = Brain()
    print(f"Monitoring at {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC")
    if not args.watch:
        n = run_once(brain)
        summary = brain.outcome_summary()
        print(f"\nBrain outcome record: {summary['n']} settled prediction(s), "
              f"hit rate {summary['hit_rate'] * 100:.0f}%"
              if summary["n"] else "\nBrain outcome record: 0 settled — "
                                   "the brain keeps accumulating until a "
                                   "match settles")
        brain.close()
        return 0

    # watch mode: a live board that polls, reports LIVE scores when the source
    # provides them, and settles each match into the brain at full time.
    settled = _live_watch(brain, args.watch)
    summary = brain.outcome_summary()
    print(f"\nWatch finished: {settled} prediction row(s) settled.")
    if summary["n"]:
        print(f"Brain outcome record: {summary['n']} settled, hit rate "
              f"{summary['hit_rate'] * 100:.0f}%")
    brain.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
