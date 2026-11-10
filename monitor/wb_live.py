"""
WORLD BASKETBALL LIVE TRACKER — the NBA live tracker (monitor/nba_live.py) for the world basketball /
NCAA picks (framework#393; Architect 2026-11-06: "NBA and basketball, they're the same thing ... inherit
all its attributes of NBA").

ONE loop (`wb_live.yml`) follows the picks frozen in output/world_basketball/wb_<day>.json whose game
starts within EARLIEST or is under way, and looks every POLL seconds at ESPN's college scoreboard
(the NCAA men's games, matched by team names and tip-off as engine/ncaa_lines.match does). The
Architect gets ONE Telegram per round that has an event: tip-off, half time, each overtime and the
final, with where every pick on that game stands (running points against its line, or WON / LOST
once settled: a 1st-half total settles at half time). A quiet round says nothing.

Leagues ESPN's college scoreboard does not carry (EuroLeague, EuroCup, FIBA ...) have no free live feed
here: such a pick is reported ONCE as "NO LIVE FEED - PENDING" and never guessed (HR35, HR59).

Snapshots go to data/study/wb/<night>/live.jsonl, committed as the night goes. Same single-loop and
hand-off rules as monitor/nba_live.py. Nothing here bets, prices or changes a board: it records and it
reports, to the Architect's own chat only (order 33).

    python monitor/wb_live.py                  tonight's picks
    python monitor/wb_live.py --night 2026-11-10
    python monitor/wb_live.py --handoff        (internal: started by the previous run)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import loop_util as lu  # noqa: E402
from monitor import nba_live as nl_live  # noqa: E402

POLL = 120
EARLIEST = timedelta(hours=3)
PERSIST_EVERY = 10
WORKFLOW = "wb_live.yml"
WB_DIR = ROOT / "output" / "world_basketball"
BREAK = ("STATUS_HALFTIME", "STATUS_END_PERIOD")
NO_FEED = "NO LIVE FEED - PENDING"


def _dt(s):
    from engine import exchange as ex
    return ex._dt(s)


def night_key(now: datetime) -> str:
    """The bots' night: tip-offs from 12:00 UTC to 12:00 UTC the next day (engine.world_basketball.night_of)."""
    from engine import world_basketball as wb
    return wb.night_of(now)


def night_games(night: str, folder: Path = WB_DIR) -> list[dict]:
    """[{key, home, away, comp, tip (datetime), ncaa, picks}] - the night's frozen picks grouped by game."""
    from engine import world_basketball as wb
    start = datetime.fromisoformat(night).replace(tzinfo=UTC) + timedelta(hours=12)
    games: dict = {}
    for day in {night, (datetime.fromisoformat(night) + timedelta(days=1)).strftime("%Y-%m-%d")}:
        try:
            doc = json.loads(wb.path_for(day, folder).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in doc.get("picks") or []:
            tip = _dt(p.get("tip") or p.get("ko"))
            if tip is None or not (start <= tip < start + timedelta(days=1)):
                continue
            k = str(p.get("sb_event_id") or p.get("event_id") or f"{p.get('home')}|{p.get('away')}")
            g = games.setdefault(k, {"key": k, "home": p.get("home"), "away": p.get("away"), "comp": p.get("comp"),
                                     "tip": tip, "ncaa": "ncaa" in (p.get("comp") or "").lower(), "picks": []})
            g["picks"].append(p)
    return sorted(games.values(), key=lambda g: g["tip"])


# ---------------------------------------------------------------- ESPN live (college scoreboard)
def fetch(games: list[dict], get=None) -> dict:
    """{game key: parsed ESPN event} for the NCAA games found on ESPN; games it does not list are absent."""
    from engine import ncaa_lines as nl
    from engine import wb_team_news as wtn
    get = get or nl._get
    days = sorted({(g["tip"] + timedelta(days=k)).strftime("%Y%m%d") for g in games if g["ncaa"] for k in (-1, 0)})
    board, cat = {}, []
    for d in days:
        blob = get(nl._SB.format(d=d)) or {}
        for e in blob.get("events") or []:
            board[str(e.get("id"))] = e
        cat += wtn.games(datetime.strptime(d, "%Y%m%d").replace(tzinfo=UTC), get=get)
    out = {}
    for g in games:
        if not g["ncaa"]:
            continue
        m = nl.match(g["home"], g["away"], g["tip"], cat)
        if m and str(m["id"]) in board:
            out[g["key"]] = nl_live.parse_event(board[str(m["id"])])
    return out


# ---------------------------------------------------------------- where a pick stands
def periods_done(s: dict) -> int:
    """Periods finished (a college game has 2 halves, then overtimes)."""
    if s["state"] == "post":
        return max(s["period"], len(s["q_home"]))
    if s["state"] != "in":
        return 0
    return s["period"] if s.get("name") in BREAK else max(s["period"] - 1, 0)


def standing(p: dict, s: dict) -> str:
    from engine import nba_value as nv
    mid, spec = str(p.get("market_id")), p.get("specifier") or ""
    pick = p.get("pick")
    qh, qa = s["q_home"], s["q_away"]
    if mid == "68":                                              # 1st-half total: the first period of two
        if periods_done(s) >= 1 and qh and qa:
            r = nv.settle({**p, "market_id": "236", "specifier": spec}, s["hs"], s["as"], qh[:1], qa[:1])
            return f"{(r or 'PENDING').upper()} - {pick}"
        return f"running - {pick}: {s['hs'] + s['as']} so far"
    if s["state"] == "post":
        r = nv.settle(p, s["hs"], s["as"], qh, qa)
        return f"{(r or 'PENDING').upper()} - {pick}"
    if mid == "225":
        return f"running - {pick}: {s['hs'] + s['as']} so far"
    lead = s["hs"] - s["as"]
    who = f"home by {lead}" if lead > 0 else f"away by {-lead}" if lead < 0 else "level"
    return f"running - {pick}: {who}"


def events(g: dict, before: dict | None, now_s: dict) -> list[str]:
    """Tip-off, half time / each overtime (once) and the final, each with the picks' standing."""
    before = before or {"state": "pre", "done": 0}
    if before["state"] == "nofeed":
        before = {"state": "pre", "done": 0}
    head = f"{g['away']} @ {g['home']}"
    score = f"{now_s['as']}-{now_s['hs']}"
    out = []
    if before["state"] == "pre" and now_s["state"] in ("in", "post"):
        out.append(f"TIP-OFF {head}")
    done = periods_done(now_s)
    now_s["done"] = max(done, before.get("done", 0))
    if now_s["state"] == "in":
        for k in range(before.get("done", 0) + 1, done + 1):
            out.append(f"{'HALF TIME' if k == 1 else 'END 2ND HALF' if k == 2 else f'END OT{k - 2}'} {head} {score}")
    if before["state"] != "post" and now_s["state"] == "post":
        out.append(f"FINAL {head} {score}")
    if out:
        out += [f"  {standing(p, now_s)}" for p in g["picks"]]
    return out


def round_once(games: list[dict], seen: dict, out_file: Path, get=None) -> tuple[list[str], bool]:
    """One look at every game. Returns (event lines, any game not final)."""
    live = fetch(games, get)
    lines, still = [], False
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for g in games:
        k = g["key"]
        s = live.get(k)
        if s is None:
            if not g["ncaa"]:                      # no feed for this league: say so once, never guess
                if k not in seen:
                    seen[k] = {"state": "nofeed"}
                    lines.append(f"{g['away']} @ {g['home']} ({g.get('comp') or 'basketball'}): {NO_FEED}")
                    lines += [f"  {p.get('pick')}" for p in g["picks"]]
                continue
            still = still or seen.get(k, {}).get("state") != "post"   # ESPN silent: keep waiting
            continue
        lines += events(g, seen.get(k), s)
        seen[k] = s
        if s["state"] != "post":
            still = True
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now, "key": k, **s}) + "\n")
    return lines, still


def resume(out_file: Path) -> dict:
    """Each game's last saved look, so a handed-off run does not re-announce what the run before said."""
    seen: dict = {}
    if out_file.exists():
        for line in out_file.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("key") and r.get("state"):
                seen[r["key"]] = r
    return seen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="world basketball / NCAA picks followed live")
    ap.add_argument("--night", default=None, help="night YYYY-MM-DD (default: the current one)")
    ap.add_argument("--handoff", action="store_true")
    a = ap.parse_args(argv)
    started = datetime.now(UTC)
    night = a.night or night_key(started)
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    if not a.handoff and repo and token and lu.other_loop_running(WORKFLOW, repo, token, run_id):
        print("a world basketball live loop is already running - nothing to do")
        return 0
    games = night_games(night)
    if not games:
        print(f"no world basketball picks for night {night} - nothing to track")
        return 0
    if games[0]["tip"] - started > EARLIEST:
        print(f"too early - first tip-off {games[0]['tip']:%H:%M}Z, more than {EARLIEST} away")
        return 0
    rel = f"data/study/wb/{night}"
    out_file = ROOT / rel / "live.jsonl"
    seen = resume(out_file)
    rounds = 0
    while True:
        lines, still = round_once(games, seen, out_file)
        rounds += 1
        for line in lines:
            print(line, flush=True)
        if lines:
            nl_live.tell(f"BASKETBALL LIVE - night {night}\n\n" + "\n".join(lines))
        if not still:
            print(f"ALL TRACKED GAMES FINAL - {lu.save([rel], f'wb live {night} [skip ci]')}", flush=True)
            return 0
        if rounds % PERSIST_EVERY == 0:
            lu.save([rel], f"wb live {night} [skip ci]")
        if datetime.now(UTC) - started >= lu.HANDOFF_AFTER:
            lu.save([rel], f"wb live {night} [skip ci]")
            if repo and token:
                lu.hand_off(WORKFLOW, repo, token, {"night": night})
                print("handed off to a fresh run (job time limit)", flush=True)
            return 0
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
