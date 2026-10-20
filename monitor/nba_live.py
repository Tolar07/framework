"""
NBA LIVE TRACKER — the NBA board's games followed live, as football's matchday is
(Architect 2026-10-20: "The way we are treating football, that's how NBA should be
treated too ... the live tracker").

ONE loop (`nba_live.yml`) follows the night's NBA board games from ESPN's live
scoreboard every POLL seconds and sends the Architect one Telegram per round that has
an event: tip-off, the end of each quarter (half time included), overtime and the final
score — each with where every pick on that game stands (running points against its line,
or WON / LOST once it is settled: a 1st-half total settles at half time). A quiet round
says nothing. Snapshots go to data/study/nba/<board date>/live.jsonl and are committed as
the night goes. The same single-loop and hand-off rules as monitor/live_loop.py.

Nothing here bets, prices or changes a board. It records and it reports. Architect's own
chat only (order 33), as football's live tracker.

    python monitor/nba_live.py                    tonight's board
    python monitor/nba_live.py --board 2026-10-21
    python monitor/nba_live.py --handoff          (internal: started by the previous run)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import loop_util as lu  # noqa: E402

POLL = 120
EARLIEST = timedelta(hours=3)          # don't sit idle longer than this before the first tip-off
PERSIST_EVERY = 10
WORKFLOW = "nba_live.yml"
LEDGER_DIR = ROOT / "output" / "picks"


# ---------------------------------------------------------------- the board's games
def board_date(now: datetime) -> str:
    import run_nba
    return run_nba.night_key(run_nba.night_start(run_nba.night_of(now)))


def board_games(board: str, ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    """[{espn_id, espn_days, home, away, tip, picks}] — the games the night's NBA board picked."""
    try:
        doc = json.loads((ledger_dir / f"nba_{board}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    games: dict = {}
    for p in doc.get("picks") or []:
        if not p.get("espn_id"):
            continue
        g = games.setdefault(str(p["espn_id"]), {
            "espn_id": str(p["espn_id"]), "home": p.get("home"), "away": p.get("away"), "tip": p.get("tip"),
            "espn_days": sorted({(date.fromisoformat(p["espn_date"]) + timedelta(days=k)).strftime("%Y%m%d")
                                 for k in (-1, 0)}) if p.get("espn_date") else [], "picks": []})
        g["picks"].append(p)
    return sorted(games.values(), key=lambda g: g["tip"] or "")


# ---------------------------------------------------------------- ESPN live
def parse_event(e: dict) -> dict:
    """One ESPN scoreboard event -> {state, period, clock, detail, hs, as, q_home, q_away}."""
    st = e.get("status") or {}
    side = {x.get("homeAway"): x for x in (e.get("competitions") or [{}])[0].get("competitors") or []}

    def score(k: str) -> int:
        try:
            return int(float(side[k].get("score") or 0))
        except (KeyError, TypeError, ValueError):
            return 0

    def quarters(k: str) -> list[int]:
        try:
            return [int(float(x.get("value") or 0)) for x in side[k].get("linescores") or []]
        except (KeyError, TypeError, ValueError):
            return []
    return {"state": (st.get("type") or {}).get("state") or "pre", "period": int(st.get("period") or 0),
            "name": (st.get("type") or {}).get("name") or "",
            "clock": st.get("displayClock"), "detail": (st.get("type") or {}).get("shortDetail") or "",
            "hs": score("home"), "as": score("away"), "q_home": quarters("home"), "q_away": quarters("away")}


def fetch(days: list[str], get=None) -> dict:
    """{espn_id: parsed event} across the ESPN days asked for; {} when ESPN does not answer."""
    from data import nba_source as ns
    get = get or ns._get
    out = {}
    for d in days:
        blob = get(ns._SB.format(d=d))
        for e in (blob or {}).get("events") or []:
            out[str(e.get("id"))] = parse_event(e)
    return out


# ---------------------------------------------------------------- where a pick stands
BREAK = ("STATUS_END_PERIOD", "STATUS_HALFTIME")


def periods_done(s: dict) -> int:
    """Periods finished: all of them once final; during a break the current one; else the ones before."""
    if s["state"] == "post":
        return max(s["period"], len(s["q_home"]))
    if s["state"] != "in":
        return 0
    return s["period"] if s.get("name") in BREAK else max(s["period"] - 1, 0)


def standing(p: dict, s: dict) -> str:
    """One line: where the pick stands now, or its result once settled."""
    from engine import nba_value as nv
    mid, spec, out = str(p.get("market_id")), p.get("specifier") or "", p.get("outcome") or ""
    qh, qa = s["q_home"], s["q_away"]
    if mid in ("68", "236"):                                   # 1st half / 1st quarter total
        n = 2 if mid == "68" else 1
        done = periods_done(s) >= n and len(qh) >= n and len(qa) >= n
        if done:
            r = nv.settle(p, s["hs"], s["as"], qh, qa)
            return f"{(r or 'PENDING').upper()} — {p.get('pick')}"
        pts = sum(qh[:n]) + sum(qa[:n])
        return f"running — {p.get('pick')}: {pts} so far"
    if s["state"] == "post":
        r = nv.settle(p, s["hs"], s["as"], qh, qa)
        return f"{(r or 'PENDING').upper()} — {p.get('pick')}"
    m = re.search(r"total=(\d+(?:\.\d+)?)", spec)
    if mid == "225" and m:
        return f"running — {p.get('pick')}: {s['hs'] + s['as']} so far"
    if mid in ("227", "228") and m:
        return f"running — {p.get('pick')}: {s['hs'] if mid == '227' else s['as']} so far"
    lead = s["hs"] - s["as"]
    who = "home" if lead > 0 else "away" if lead < 0 else "level"
    return f"running — {p.get('pick')} ({out}): {who} by {abs(lead)}" if lead else f"running — {p.get('pick')}: level"


def events(g: dict, before: dict | None, now_s: dict) -> list[str]:
    """What happened since the last look: tip-off, each period that ended (once), the final."""
    before = before or {"state": "pre", "done": 0}
    head = f"{g['away']} @ {g['home']}"
    score = f"{now_s['as']}-{now_s['hs']}"
    out = []
    if before["state"] == "pre" and now_s["state"] in ("in", "post"):
        out.append(f"TIP-OFF {head}")
    done = periods_done(now_s)
    now_s["done"] = max(done, before.get("done", 0))
    if now_s["state"] == "in":
        for k in range(before.get("done", 0) + 1, done + 1):
            name = "HALF TIME" if k == 2 else f"END Q{k}" if k <= 4 else f"END OT{k - 4}"
            out.append(f"{name} {head} {score}")
    if before["state"] != "post" and now_s["state"] == "post":
        out.append(f"FINAL {head} {score}")
    if out:
        out += [f"  {standing(p, now_s)}" for p in g["picks"]]
    return out


def round_once(games: list[dict], seen: dict, out_file: Path, get=None) -> tuple[list[str], bool]:
    """One look at every game. Returns (event lines, any game not final)."""
    days = sorted({d for g in games for d in g["espn_days"]})
    live = fetch(days, get)
    lines, still = [], False
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for g in games:
        s = live.get(g["espn_id"])
        if s is None:                     # ESPN silent this round: keep waiting, report nothing
            still = still or seen.get(g["espn_id"], {}).get("state") != "post"
            continue
        lines += events(g, seen.get(g["espn_id"]), s)
        seen[g["espn_id"]] = s
        if s["state"] != "post":
            still = True
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now, "espn_id": g["espn_id"], **s}) + "\n")
    return lines, still


def tell(body: str) -> None:
    """To the Architect's own chat only (order 33), as football's live tracker."""
    try:
        from output.notify import send_architect
        ok, notes = send_architect(body)
        if not ok:
            print(f"  telegram NOT SENT ({'; '.join(notes) or 'no reason given'})", flush=True)
    except Exception as e:  # noqa: BLE001 — a missed message is not a stopped night
        print(f"  telegram failed ({str(e)[:60]})", flush=True)


def first_tip(games: list[dict]) -> datetime | None:
    tips = [datetime.fromisoformat(g["tip"]) for g in games if g.get("tip")]
    return min(tips) if tips else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the NBA board's games followed live")
    ap.add_argument("--board", default=None, help="NBA board date YYYY-MM-DD (default: tonight's)")
    ap.add_argument("--handoff", action="store_true")
    a = ap.parse_args(argv)
    started = datetime.now(UTC)
    board = a.board or board_date(started)
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    if date.fromisoformat(board) < started.date() - timedelta(days=1):
        print(f"NBA board {board} is over — nothing to track")
        return 0
    if not a.handoff and repo and token and lu.other_loop_running(WORKFLOW, repo, token, run_id):
        print("an NBA live loop is already running — nothing to do")
        return 0
    games = board_games(board)
    if not games:
        print(f"no NBA board picks for {board} — nothing to track")
        return 0
    tip = first_tip(games)
    if tip and tip - started > EARLIEST:
        print(f"too early — first tip-off {tip:%H:%M}Z, more than {EARLIEST} away")
        return 0
    rel = f"data/study/nba/{board}"
    out_file = ROOT / rel / "live.jsonl"
    for g in games:
        print(f"  {g['tip'][11:16]}Z {g['away']} @ {g['home']} — " + " | ".join(p.get("pick") or "" for p in g["picks"]),
              flush=True)
    seen: dict = {}
    rounds = 0
    while True:
        lines, still = round_once(games, seen, out_file)
        rounds += 1
        for line in lines:
            print(line, flush=True)
        if lines:
            tell(f"NBA LIVE — board {board}\n\n" + "\n".join(lines))
        if not still:
            print(f"ALL NBA GAMES FINAL · {lu.save([rel], f'nba live {board} [skip ci]')}", flush=True)
            return 0
        if rounds % PERSIST_EVERY == 0:
            print(f"[{datetime.now(UTC):%H:%M}Z] {lu.save([rel], f'nba live {board} [skip ci]')}", flush=True)
        if datetime.now(UTC) - started >= lu.HANDOFF_AFTER:
            print(f"[{datetime.now(UTC):%H:%M}Z] {lu.save([rel], f'nba live {board} [skip ci]')}", flush=True)
            if repo and token:
                lu.hand_off(WORKFLOW, repo, token, {"board": board})
                print("handed off to a fresh run (job time limit)", flush=True)
            return 0
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
