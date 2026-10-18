"""
LIVE TRACKER — a matchday minute by minute: FotMob's live numbers beside
SportyBet's live prices, and where each of our calls stands (Architect
2026-10-13: "analyzing it minute by minute, how the game is changing
according to your prediction"; "your next tracker upgrade. You can do that").

Every POLL seconds until every tracked match is over, per match:
  FotMob    score, minute, xG, shots, shots on target, box touches, big
            chances, possession, red cards, goals, last 10 minutes' momentum
  SportyBet live 1X2, Over/Under lines and BTTS prices (in-play feed), so a
            review can ask whether the live odds lagged what the xG showed
appended to data/study/<date>/live/<fotmob id>.jsonl, and a line printed on
every goal, red card, half time and full time.

Tracked: the day's Champions League matches plus every fixture on the day's
board (output/picks/picks_<date>.json) and study board, where those exist.
Nothing here bets, prices or changes a board.

NORMALLY RUN BY GITHUB ACTIONS: `live.yml` -> `monitor/live_loop.py`, which
shares `round_once` below and Telegrams the Architect on each event. The first
version of this file said an all-day Actions job would cost "about three times
the free Actions minutes" and so should be run from a session instead. That was
wrong: this repo is PUBLIC, and GitHub-hosted minutes are unmetered on public
repositories (corrected 2026-10-14). Running it by hand, as below, is for a
one-off or a backfill.

    python monitor/live_tracker.py 2026-10-14
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402
from data.flashscore_results import _sim  # noqa: E402

POLL = 120
# A match with no full time this long after kickoff is over for the tracker:
# postponed, abandoned, or a feed that never reports it. Without this, two
# 2026-10-17 matches FotMob never marked started kept the loop handing off to
# itself with --day 2026-10-17 all through the 18th, holding live.yml's queue
# so that no run for the 18th ever started (each was queued, then cancelled).
GIVE_UP = timedelta(hours=4)
GAVE_UP = (None, False, (0, 0), False, "gave up")   # seen[] marker; summary reads PENDING
LEAGUES = ("Champions League",)
STAT_KEYS = {"Expected goals (xG)": "xg", "Total shots": "shots", "Shots on target": "sot",
             "Touches in opposition box": "box", "Big chances": "big", "Ball possession": "poss"}
_LIVE = "https://www.sportybet.com/api/ng/factsCenter/liveOrPrematchEvents?sportId=sr%3Asport%3A1"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "application/json"}
LIVE_MARKETS = {"1": "1x2", "18": "ou", "29": "btts"}


def our_calls(day: str) -> list[dict]:
    """[{home, away, call}] — the day's board singles and study legs."""
    out = []
    ledger = ROOT / "output" / "picks" / f"picks_{day}.json"
    if ledger.exists():
        for p in json.loads(ledger.read_text(encoding="utf-8")).get("singles") or []:
            out.append({"home": p["home"], "away": p["away"], "call": f"board: {p['pick']} @{p['price']}"})
    study = ROOT / "data" / "study" / day / "engine_board.json"
    if study.exists():
        for leg in json.loads(study.read_text(encoding="utf-8"))["legs"]:
            if leg.get("pick"):
                h, a = leg["match"].split(" v ", 1)
                pk = leg["pick"]
                out.append({"home": h, "away": a, "call": f"study: {pk['mdesc']} {pk['pick']} @{pk['price']}"})
    return out


def tracked(day: str, calls: list[dict]) -> list[dict]:
    """FotMob fixtures of the day: the leagues above plus every fixture with a call."""
    from data import team_profiles as tp

    def same(c: dict, m: dict) -> bool:
        if tp._kind(f"{m['league']} {m['home']} {m['away']}") != "men":
            return False                             # our calls are all men's first teams
        h, a = tp._sim2(c["home"], m["home"]), tp._sim2(c["away"], m["away"])
        return min(h, a) >= 0.6 or (max(h, a) >= 0.95 and min(h, a) >= 0.2)
    keep = []
    for m in fm.matches_on(day):
        mine = [c["call"] for c in calls if same(c, m)]
        if (m["league"] in LEAGUES and tp._kind(m["league"]) == "men") or mine:
            keep.append({**m, "calls": mine})
    return keep


def live_prices() -> list[dict]:
    """SportyBet's in-play football list: [{home, away, score, clock, prices}]."""
    req = urllib.request.Request(_LIVE, headers=_UA)  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        data = json.loads(r.read()).get("data") or []
    out = []
    for t in data:
        for e in t.get("events") or []:
            prices: dict[str, dict] = {}
            for mk in e.get("markets") or []:
                name = LIVE_MARKETS.get(str(mk.get("id")))
                if not name or mk.get("status") not in (None, 0, "0"):
                    continue
                key = f"{name}{('|' + mk['specifier']) if mk.get('specifier') else ''}"
                prices[key] = {o.get("desc"): float(o["odds"]) for o in mk.get("outcomes") or []
                               if o.get("odds") and o.get("isActive", 1)}
            out.append({"home": e.get("homeTeamName", ""), "away": e.get("awayTeamName", ""),
                        "score": e.get("setScore"), "clock": e.get("playedSeconds"), "prices": prices})
    return out


def sportybet_live(live: list[dict], m: dict) -> dict | None:
    best = max(live, key=lambda e: min(_sim(m["home"], e["home"]), _sim(m["away"], e["away"])), default=None)
    if best and min(_sim(m["home"], best["home"]), _sim(m["away"], best["away"])) >= 0.6:
        return best
    return None


def snap(mid) -> dict:
    d = fm.match_details(mid)
    st = (d.get("header") or {}).get("status") or {}
    c = d.get("content") or {}
    stats: dict[str, list[float]] = {}
    # Every step is `or {}`, not `.get(k, {})`: FotMob sends "Periods": null and
    # "All": null in the minutes around kickoff, before a match has any stats,
    # and a default only applies to a MISSING key, not a null one. The bare
    # defaults here crashed every poll of Feyenoord v Como from 16:46 on
    # 2026-10-14 ('NoneType' object has no attribute 'get') — that match went
    # unrecorded while the others logged normally.
    _periods = (c.get("stats") or {}).get("Periods") or {}
    for grp in ((_periods.get("All") or {}).get("stats") or []):
        for s in grp.get("stats") or []:
            k = STAT_KEYS.get(s.get("title"))
            if k and k not in stats and s.get("stats") and None not in s["stats"]:
                stats[k] = [float(str(x).split()[0].rstrip("%")) for x in s["stats"]]
    evs = [{"min": e.get("time"), "type": e.get("type"), "home": e.get("isHome"),
            "player": (e.get("player") or {}).get("name"), "score": e.get("newScore")}
           for e in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []
           if e.get("type") in ("Goal", "Card", "Half")]
    mom = [(x.get("minute"), x.get("value")) for x in ((c.get("momentum") or {}).get("main") or {}).get("data") or []]
    return {"at": datetime.now(UTC).strftime("%H:%M:%SZ"), "live": (st.get("liveTime") or {}).get("short"),
            "score": st.get("scoreStr"), "finished": bool(st.get("finished")), "started": bool(st.get("started")),
            "reds": [st.get("numberOfHomeRedCards"), st.get("numberOfAwayRedCards")],
            "stats": stats, "events": evs, "momentum_last10": mom[-10:]}


def round_once(matches: list[dict], seen: dict, out_dir: Path,
               live: list[dict] | None = None) -> tuple[list[str], int]:
    """One poll of every tracked match. Appends a snapshot per match to
    data/study/<day>/live/<fotmob id>.jsonl and returns (the lines worth saying
    out loud — a goal, a red card, half time, full time, or a feed that failed
    — and how many matches are still to finish).

    Shared by the session script below and the GitHub Actions loop
    (monitor/live_loop.py), so a matchday watched from either place records and
    reports exactly the same events.
    """
    lines: list[str] = []
    if live is None:
        try:
            live = live_prices()
        except Exception as e:  # noqa: BLE001 — SportyBet down: FotMob numbers still logged
            live = []
            lines.append(f"[{datetime.now(UTC):%H:%M}Z] SportyBet live feed failed ({str(e)[:40]})")
    still = 0
    for m in matches:
        ko = datetime.fromisoformat(m["kickoff_utc"].replace("Z", "+00:00"))
        now = datetime.now(UTC)
        if ko > now:
            still += 1
            continue                                 # not started: no poll yet
        if seen.get(m["id"]) == GAVE_UP:
            continue
        # Past GIVE_UP the match is still polled once, so a run that starts late
        # (or after a hand-off) records a real full time instead of giving up.
        overdue = now - ko >= GIVE_UP
        try:
            s = snap(m["id"])
        except Exception as e:  # noqa: BLE001 — a missed poll is a gap, not a stop
            lines.append(f"[{datetime.now(UTC):%H:%M}Z] {m['home']} v {m['away']}: "
                         f"poll failed ({str(e)[:40]})")
            if overdue:
                give_up(m, seen, lines, now)
            else:
                still += 1
            continue
        sb = sportybet_live(live, m)
        s["sportybet"] = {"score": sb["score"], "clock": sb["clock"], "prices": sb["prices"]} if sb else None
        with (out_dir / f"{m['id']}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(s, separators=(",", ":")) + "\n")
        key = (s["score"], s["finished"], tuple(s["reds"]), s["live"] == "HT")
        if seen.get(m["id"]) != key and (m["id"] in seen or s["finished"]):
            xg, sot = s["stats"].get("xg", ["?", "?"]), s["stats"].get("sot", ["?", "?"])
            what = "FULL TIME" if s["finished"] else "HALF TIME" if s["live"] == "HT" else "CHANGE"
            one = (sb or {}).get("prices", {}).get("1x2") or {}
            px = f" · SportyBet 1X2 {one.get('Home')}/{one.get('Draw')}/{one.get('Away')}" if one else ""
            lines.append(f"[{s['at']}] {what} {m['home']} {s['score']} {m['away']} ({s['live']}) · "
                         f"xG {xg[0]}-{xg[1]} · on target {sot[0]}-{sot[1]} · "
                         f"reds {s['reds'][0]}-{s['reds'][1]}{px} · "
                         + (" | ".join(m["calls"]) or "no call"))
        seen[m["id"]] = key
        if s["finished"]:
            continue
        if overdue:
            give_up(m, seen, lines, now)
        else:
            still += 1
    return lines, still


def give_up(m: dict, seen: dict, lines: list[str], now: datetime) -> None:
    """Stop following a match with no full time GIVE_UP after kickoff, saying so once."""
    seen[m["id"]] = GAVE_UP
    lines.append(f"[{now:%H:%M}Z] NO FULL TIME {m['home']} v {m['away']} — "
                 f"{GIVE_UP.seconds // 3600} h after kickoff, stopped following "
                 "(postponed or abandoned?)")


def main(argv: list[str]) -> int:
    day = argv[0] if argv else datetime.now(UTC).strftime("%Y-%m-%d")
    out_dir = ROOT / "data" / "study" / day / "live"
    out_dir.mkdir(parents=True, exist_ok=True)
    matches = tracked(day, our_calls(day))
    print(f"tracking {len(matches)} matches on {day}", flush=True)
    for m in matches:
        print(f"  {m['kickoff_utc'][11:16]}Z {m['home']} v {m['away']} — "
              + (" | ".join(m["calls"]) or "no call"), flush=True)
    seen: dict = {}
    while True:
        lines, still = round_once(matches, seen, out_dir)
        for line in lines:
            print(line, flush=True)
        if not still:
            print("ALL MATCHES FINISHED", flush=True)
            return 0
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
