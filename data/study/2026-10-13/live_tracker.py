"""
LIVE TRACKER — 13 Oct Champions League, minute by minute (Architect
2026-10-13: "start looking at the live match ... analyzing it minute by
minute, how the game is changing according to your prediction, and see what
you could have done better").

Every POLL seconds until every match is over: FotMob's live page of each
Champions League match (score, minute, xG, shots, shots on target, box
touches, big chances, possession, red cards, goals with minutes, momentum),
appended to live/<fotmob id>.jsonl. A line is printed on every goal, red
card, half time and full time, with where each of our calls stands.

Our calls (pre-match, fixed): the live board's singles
(output/picks/picks_2026-10-13.json) and the study board's legs
(engine_board.json, run STUDY-412d9663). Nothing here bets or changes a board.

    python data/study/2026-10-13/live_tracker.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402
from data.flashscore_results import _sim  # noqa: E402

LIVE = HERE / "live"
POLL = 120
STAT_KEYS = {"Expected goals (xG)": "xg", "Total shots": "shots", "Shots on target": "sot",
             "Touches in opposition box": "box", "Big chances": "big", "Ball possession": "poss"}


def ucl_matches() -> list[dict]:
    return [m for m in fm.matches_on("2026-10-13") if m["league"] == "Champions League"]


def our_calls(m: dict) -> list[str]:
    """The pre-match calls on this match, as text."""
    out = []
    singles = json.loads((ROOT / "output/picks/picks_2026-10-13.json").read_text(encoding="utf-8"))["singles"]
    for p in singles:
        if min(_sim(m["home"], p["home"]), _sim(m["away"], p["away"])) >= 0.6:
            out.append(f"board single: {p['pick']} @{p['price']}")
    for leg in json.loads((HERE / "engine_board.json").read_text(encoding="utf-8"))["legs"]:
        h, a = leg["match"].split(" v ", 1)
        if min(_sim(m["home"], h), _sim(m["away"], a)) >= 0.6:
            pk = leg["pick"]
            out.append(f"study leg: {pk['mdesc']} {pk['pick']} {pk.get('spec', '')} @{pk['price']}".rstrip())
    return out


def snap(mid) -> dict:
    d = fm.match_details(mid)
    st = (d.get("header") or {}).get("status") or {}
    c = d.get("content") or {}
    stats = {}
    for grp in ((c.get("stats") or {}).get("Periods", {}).get("All", {}).get("stats") or []):
        for s in grp.get("stats") or []:
            k = STAT_KEYS.get(s.get("title"))
            if k and k not in stats and s.get("stats") and None not in s["stats"]:
                stats[k] = [float(str(x).split()[0].rstrip("%")) for x in s["stats"]]
    evs = [{"min": e.get("time"), "type": e.get("type"), "home": e.get("isHome"),
            "player": (e.get("player") or {}).get("name"), "score": e.get("newScore"),
            "card": e.get("card")}
           for e in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []
           if e.get("type") in ("Goal", "Card", "Half")]
    mom = [(x.get("minute"), x.get("value")) for x in ((c.get("momentum") or {}).get("main") or {}).get("data") or []]
    return {"at": datetime.now(UTC).strftime("%H:%M:%SZ"), "live": (st.get("liveTime") or {}).get("short"),
            "score": st.get("scoreStr"), "finished": bool(st.get("finished")), "started": bool(st.get("started")),
            "reds": [st.get("numberOfHomeRedCards"), st.get("numberOfAwayRedCards")],
            "stats": stats, "events": evs, "momentum_last10": mom[-10:]}


def main() -> None:
    LIVE.mkdir(exist_ok=True)
    matches = ucl_matches()
    calls = {m["id"]: our_calls(m) for m in matches}
    seen: dict = {}
    for m in matches:
        print(f"{m['home']} v {m['away']}: " + " | ".join(calls[m["id"]] or ["no call"]), flush=True)
    while True:
        open_ = 0
        for m in matches:
            try:
                s = snap(m["id"])
            except Exception as e:  # noqa: BLE001 — a missed poll is just a gap
                print(f"[{datetime.now(UTC):%H:%M}Z] {m['home']} v {m['away']}: poll failed ({str(e)[:40]})", flush=True)
                open_ += 1
                continue
            with (LIVE / f"{m['id']}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(s, separators=(",", ":")) + "\n")
            key = (s["score"], s["finished"], tuple(s["reds"]), s["live"] == "HT")
            if seen.get(m["id"]) != key:
                if m["id"] in seen or s["finished"]:
                    xg = s["stats"].get("xg", ["?", "?"])
                    sot = s["stats"].get("sot", ["?", "?"])
                    what = "FULL TIME" if s["finished"] else "HALF TIME" if s["live"] == "HT" else "CHANGE"
                    print(f"[{s['at']}] {what} {m['home']} {s['score']} {m['away']} ({s['live']}) · xG {xg[0]}-{xg[1]} "
                          f"· on target {sot[0]}-{sot[1]} · reds {s['reds'][0]}-{s['reds'][1]} · "
                          + " | ".join(calls[m["id"]]), flush=True)
                seen[m["id"]] = key
            if not s["finished"]:
                open_ += 1
        if not open_:
            print("ALL MATCHES FINISHED", flush=True)
            return
        time.sleep(POLL)


if __name__ == "__main__":
    main()
