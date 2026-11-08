"""
MULTI-SPORT LIVE TRACKER — every rollout sport's picks followed in play, as football's matchday
(monitor/live_loop.py) and the NBA night (monitor/nba_live.py) are (Architect 2026-11-06: "Everything
inherits everything ... no gaps"; framework#359). Sports: ice hockey, American football, snooker,
darts, volleyball, table tennis, cricket, rugby, tennis, baseball.

ONE loop (`multisport_live.yml`) reads the picks frozen on the multi-sport boards
(output/multisport/<sport>/ms_<date>.json, ice hockey output/ice_hockey/ih_<date>.json) whose games
start within EARLIEST or are already under way, and looks every POLL seconds at free live feeds,
fetched in this session (HR59):
  * Flashscore's day feed for every sport (the same feed the boards are graded from:
    AB 1 = not started, 2 = in play, 3 = finished; BA/BB.. = each period's score);
  * ESPN's public scoreboard for the NHL, NFL, college football and MLB, used when Flashscore
    does not answer for a game.
The Architect gets ONE Telegram per round that has an event: the start, the end of each period
(set, quarter, innings, half ...; baseball every third inning), a frame/leg/set won where the feed
gives no periods (snooker, darts), and the final — each with where every pick on that game stands
(WINNING / LOSING if it ended now, or WON / LOST / VOID once final, settled by the board's own
rules: engine/multisport.settle, engine/hockey_model.settle). A quiet round says nothing. A game no
feed has found is reported as NO DATA — PENDING once, never guessed (HR35).

Snapshots go to data/study/multisport/<UTC day>/live.jsonl and are saved as the loop goes; every
PERSIST_EVERY rounds the loop also re-reads framework-data, so picks frozen by a later look are
followed too. The same single-loop and hand-off rules as monitor/live_loop.py (monitor/loop_util.py);
the Oracle VM clock only STARTS it (matchbook-agent oracle_clock/schedule.json), never a cron tick.

Nothing here bets, prices or changes a board. It records and it reports. Architect's own chat only
(order 33). No steam (order 50).

    python monitor/multisport_live.py                 follow what is in play / about to start
    python monitor/multisport_live.py --once          one look, print, no Telegram, no save
    python monitor/multisport_live.py --handoff       (internal: started by the previous run)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402
from monitor import loop_util as lu  # noqa: E402

POLL = 120
EARLIEST = timedelta(hours=3)          # follow a pick from this long before its start
GIVE_UP = timedelta(hours=10)          # a game no feed has finished this long after its start is dropped
PERSIST_EVERY = 10
WORKFLOW = "multisport_live.yml"
HOCKEY = "ice_hockey"
SPORTS = [HOCKEY, *ms.SPORTS]
FS_SPORT = {HOCKEY: 4, **{s: c["fs"] for s, c in ms.SPORTS.items()}}
ESPN = {HOCKEY: ["hockey/nhl"], "american_football": ["football/nfl", "football/college-football"],
        "baseball": ["baseball/mlb"]}
_ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d}&limit=500"
PERIOD = {HOCKEY: "period", "american_football": "Q", "baseball": "inning", "cricket": "innings",
          "rugby": "half", "tennis": "set", "volleyball": "set", "table_tennis": "game",
          "darts": "set", "snooker": "session"}
REPORT_EVERY = {"baseball": 3}         # nine innings = three messages, not nine
LABEL = {HOCKEY: "ICE HOCKEY", "american_football": "AMERICAN FOOTBALL", "table_tennis": "TABLE TENNIS"}
DATA = "data/study/multisport"


def label(sport: str) -> str:
    return LABEL.get(sport, sport.upper())


# ---------------------------------------------------------------- the boards' picks
def board_file(sport: str, day: str) -> Path:
    if sport == HOCKEY:
        return ROOT / "output" / "ice_hockey" / f"ih_{day}.json"
    return ms.path_for(sport, day)


def _dt(s: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def board_games(now: datetime, file_for=board_file) -> list[dict]:
    """[{key, sport, home, away, ko, picks}] — every board pick not yet graded whose game starts
    within EARLIEST or started less than GIVE_UP ago, one entry per game."""
    games: dict[str, dict] = {}
    days = sorted({(now + timedelta(days=k)).strftime("%Y-%m-%d") for k in (-1, 0, 1)})
    for sport in SPORTS:
        for day in days:
            try:
                doc = json.loads(file_for(sport, day).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for p in doc.get("picks") or []:
                ko = _dt(p.get("ko") or p.get("tip"))
                if ko is None or p.get("result") or not (now - GIVE_UP <= ko <= now + EARLIEST):
                    continue
                key = f"{sport}:{p.get('sb_event_id') or p.get('event_id')}"
                g = games.setdefault(key, {"key": key, "sport": sport, "home": p.get("home") or "",
                                           "away": p.get("away") or "", "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                           "comp": p.get("comp"), "paper": bool(p.get("paper")), "picks": []})
                g["picks"].append(p)
    return sorted(games.values(), key=lambda g: (g["ko"], g["key"]))


# ---------------------------------------------------------------- live feeds
def parse_flashscore_live(text: str) -> list[dict]:
    """Every game of a Flashscore day feed, started or not:
    {home, away, kickoff_utc, state pre/in/post, periods [[h, a]..], final [h, a], winner, stage}."""
    out, league = [], ""
    for block in text.split("~"):
        kv: dict[str, str] = {}
        for f in block.split("¬"):
            if "÷" in f:
                k, v = f.split("÷", 1)
                kv.setdefault(k, v)
        if "ZA" in kv:
            league = kv["ZA"]
            continue
        if "AA" not in kv:
            continue
        state = {"1": "pre", "2": "in", "3": "post"}.get(kv.get("AB", ""), "pre")
        try:
            ko = datetime.fromtimestamp(int(kv.get("AD", "0")), tz=UTC)
            fh, fa = int(kv.get("AG") or 0), int(kv.get("AH") or 0)
        except ValueError:
            continue
        periods = []
        for hk, ak in (("BA", "BB"), ("BC", "BD"), ("BE", "BF"), ("BG", "BH"), ("BI", "BJ"),
                       ("BK", "BL"), ("BM", "BN"), ("BO", "BP"), ("BQ", "BR")):
            try:
                periods.append([int(kv[hk]), int(kv[ak])])
            except (KeyError, ValueError):
                break
        win = kv.get("AS")
        out.append({"league": league, "home": kv.get("AE", ""), "away": kv.get("AF", ""),
                    "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "state": state, "stage": kv.get("AC"),
                    "periods": periods, "final": [fh, fa], "fthg": fh, "ftag": fa,
                    "winner": int(win) if win in ("1", "2") and state == "post" else None, "source": "flashscore"})
    return out


def _espn_score(c: dict) -> int:
    try:
        return int(float(c.get("score") or 0))
    except (TypeError, ValueError):
        return 0


def _espn_lines(c: dict) -> list[int]:
    try:
        return [int(float(x.get("value") or 0)) for x in c.get("linescores") or []]
    except (TypeError, ValueError):
        return []


def parse_espn(blob: dict) -> list[dict]:
    """ESPN scoreboard events in the same shape as parse_flashscore_live."""
    out = []
    for e in (blob or {}).get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        side = {x.get("homeAway"): x for x in comp.get("competitors") or []}
        if "home" not in side or "away" not in side:
            continue

        lh, la = _espn_lines(side["home"]), _espn_lines(side["away"])
        st = ((e.get("status") or {}).get("type") or {})
        state = st.get("state") or "pre"
        fh, fa = _espn_score(side["home"]), _espn_score(side["away"])
        out.append({"league": (e.get("season") or {}).get("slug") or "", "source": "espn",
                    "home": (side["home"].get("team") or {}).get("displayName") or "",
                    "away": (side["away"].get("team") or {}).get("displayName") or "",
                    "kickoff_utc": (e.get("date") or "").replace("Z", ":00Z") if len(e.get("date") or "") == 17
                    else e.get("date") or "", "state": state, "stage": st.get("name"),
                    "periods": [list(x) for x in zip(lh, la, strict=False)], "final": [fh, fa], "fthg": fh, "ftag": fa,
                    "winner": (1 if fh > fa else 2 if fa > fh else None) if state == "post" else None})
    return out


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ms._UA, "Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310 — fixed https hosts
        return json.loads(r.read().decode("utf-8"))


def fetch_live(sports: set[str], now: datetime, fs_get=None, espn_get=None) -> dict[str, dict[str, list[dict]]]:
    """{sport: {"flashscore": [...], "espn": [...]}} for yesterday and today (UTC). A feed that does not
    answer gives [] for that sport this round."""
    from data import flashscore_results as fr
    out: dict[str, dict[str, list[dict]]] = {}
    sign = None
    for sport in sports:
        feeds: dict[str, list[dict]] = {"flashscore": [], "espn": []}
        for off in (-1, 0):
            try:
                if fs_get is None:
                    sign = sign or fr.feed_sign()
                    text = fr._get(fr._FEED.replace("f_1_", f"f_{FS_SPORT[sport]}_").format(offset=off),
                                   {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})
                else:
                    text = fs_get(FS_SPORT[sport], off)
                feeds["flashscore"] += parse_flashscore_live(text)
            except Exception:  # noqa: BLE001, S110 — silent feed this round, retried next
                pass
        for path in ESPN.get(sport, []):
            for d in sorted({(now + timedelta(days=k)).strftime("%Y%m%d") for k in (-1, 0)}):
                try:
                    blob = (espn_get or _get_json)(_ESPN_SB.format(path=path, d=d))
                    feeds["espn"] += parse_espn(blob)
                except Exception:  # noqa: BLE001, S110 — ESPN silent this round
                    pass
        out[sport] = feeds
    return out


def find_live(g: dict, feeds: dict[str, list[dict]]) -> dict | None:
    """The live game for a board game: Flashscore first, then ESPN. Both names must match strongly
    and the best match be unambiguous (data/flashscore_results.find_result), never a guess.
    SportyBet names a women's side without Flashscore's ' W' (8 Nov: 'Sydney Sixers' v Flashscore's
    'Sydney Sixers W'): that form is tried last, and only for a game starting at the same time."""
    from data import flashscore_results as fr
    if is_simulated(g):
        return None
    ko = _dt(g["ko"])
    for src in ("flashscore", "espn"):
        evs = feeds.get(src) or []
        for home, away in ((g["home"], g["away"]), (ms.match_name(g["home"]), ms.match_name(g["away"]))):
            ev = fr.find_result(evs, home, away, g["ko"])
            if ev:
                return ev
    same_time = [e for e in feeds.get("flashscore") or []
                 if ko and (k := _dt(e.get("kickoff_utc"))) and abs((k - ko).total_seconds()) <= 900]
    ev = fr.find_result(same_time, f"{g['home']} W", f"{g['away']} W", g["ko"]) if same_time else None
    if ev or g["sport"] not in PLAYER_SPORTS or not ko:
        return ev
    # a player's name: SportyBet 'Julia Stusek' / 'Imai, Shintaro', Flashscore 'Stusek J.' / 'Imai S.';
    # an order of play moves start times, so within PLAYER_WINDOW, both players exact, one game only
    hits = [e for e in feeds.get("flashscore") or []
            if (k := _dt(e.get("kickoff_utc"))) and abs(k - ko) <= PLAYER_WINDOW
            and same_player(g["home"], e["home"]) and same_player(g["away"], e["away"])]
    return hits[0] if len(hits) == 1 else None


def is_simulated(g: dict) -> bool:
    """SportyBet's SRL games ('Chennai Super Kings SRL', 'Navarro, Emma (Srl)') are simulated: no live feed
    has them, and the real teams' game must never stand in for one."""
    from data import flashscore_results as fr
    return any("srl" in fr.norm(g.get(k) or "").split() for k in ("home", "away", "comp"))


PLAYER_SPORTS = ("tennis", "table_tennis", "darts", "snooker")
PLAYER_WINDOW = timedelta(hours=4)


def same_player(ours: str, theirs: str) -> bool:
    """'Julia Stusek' / 'Stusek, Julia' is Flashscore's 'Stusek J.'; 'Alejandro Moro Canas' is 'Moro Canas A.'.
    Singles only (a doubles pair has '/'); surname exact, first initial equal."""
    from data import flashscore_results as fr
    if "/" in ours or "/" in theirs:
        return False                      # a doubles pair
    t = fr.norm(theirs).split()
    initials = [x for x in t if len(x) == 1]
    sur = [x for x in t if len(x) > 1]
    if not sur or not initials:
        return False
    if ours.count(",") == 1:
        last, first = (fr.norm(x) for x in ours.split(","))
        return last.split() == sur and first[:1] == initials[0]
    o = fr.norm(ours).split()
    return len(o) > len(sur) and o[-len(sur):] == sur and o[0][:1] == initials[0]


# ---------------------------------------------------------------- where a pick stands
def done_periods(s: dict) -> int:
    """Periods finished: all of them once final, else every one before the current."""
    n = len(s.get("periods") or [])
    if s["state"] == "post":
        return n
    return max(n - 1, 0) if s["state"] == "in" else 0


def settle_now(sport: str, p: dict, s: dict) -> int | None:
    """1 / 0 / None for the pick on the score as it stands (the board's own settle rules)."""
    mid, spec, out = str(p.get("market_id") or ""), p.get("specifier") or "", p.get("outcome") or ""
    if sport == HOCKEY:
        from engine import hockey_model as hm
        per = s.get("periods") or []
        reg = (sum(x[0] for x in per[:3]), sum(x[1] for x in per[:3])) if per else tuple(s["final"])
        return hm.settle(mid, spec, out, reg, tuple(s["final"]))
    return ms.settle(sport, mid, spec, out, s)


def standing(sport: str, p: dict, s: dict) -> str:
    try:
        r = settle_now(sport, p, s)
    except Exception:  # noqa: BLE001 — a market this cannot read stays PENDING, never guessed
        r = None
    if s["state"] == "post":
        word = "VOID" if r is None else "WON" if r else "LOST"
        return f"{word} — {p.get('pick')}"
    word = "level / not decided" if r is None else "WINNING if it ended now" if r else "LOSING if it ended now"
    return f"running — {p.get('pick')}: {word}"


def score_text(s: dict) -> str:
    per = s.get("periods") or []
    tail = f" ({', '.join(f'{h}-{a}' for h, a in per)})" if per else ""
    return f"{s['final'][0]}-{s['final'][1]}{tail}"


def events(g: dict, before: dict | None, now_s: dict) -> list[str]:
    """What happened since the last look: the start, each period that ended (once), a score change
    where the feed gives no periods, the final."""
    sport = g["sport"]
    before = before or {"state": "pre", "done": 0, "final": [0, 0]}
    head = f"{g['home']} v {g['away']}"
    out = []
    if before["state"] == "pre" and now_s["state"] in ("in", "post"):
        out.append(f"START {head}")
    done = done_periods(now_s)
    now_s["done"] = max(done, before.get("done", 0))
    every = REPORT_EVERY.get(sport, 1)
    if now_s["state"] == "in":
        ended = [k for k in range(before.get("done", 0) + 1, done + 1) if k % every == 0]
        if ended:
            out.append(f"END {PERIOD.get(sport, 'period')} {ended[-1]} {head} {score_text(now_s)}")
        elif not now_s.get("periods") and before["state"] == "in" and now_s["final"] != before.get("final"):
            out.append(f"SCORE {head} {score_text(now_s)}")
    if before["state"] != "post" and now_s["state"] == "post":
        out.append(f"FINAL {head} {score_text(now_s)}")
    if out:
        out += [f"  {standing(sport, p, now_s)}" for p in g["picks"]]
    return out


def round_once(games: list[dict], seen: dict, out_file: Path | None, feeds: dict,
               now: datetime | None = None) -> tuple[dict[str, list[str]], bool]:
    """One look at every game. Returns ({sport: event lines}, any game still to finish)."""
    now = now or datetime.now(UTC)
    lines: dict[str, list[str]] = {}
    still = False
    at = now.isoformat(timespec="seconds")
    for g in games:
        s = find_live(g, feeds.get(g["sport"]) or {})
        prev = seen.get(g["key"])
        if s is None:
            ko = _dt(g["ko"])
            if prev and prev.get("state") == "post":
                continue
            if ko and now >= ko + timedelta(minutes=30) and not (prev or {}).get("nodata"):
                why = "a simulated SRL game" if is_simulated(g) else "no live feed has this game"
                lines.setdefault(g["sport"], []).append(f"NO DATA — PENDING {g['home']} v {g['away']} ({why})")
                seen[g["key"]] = {**(prev or {"state": "pre", "done": 0, "final": [0, 0]}), "nodata": True}
            still = still or bool(ko and now < ko + GIVE_UP)
            continue
        s = {k: s[k] for k in ("state", "periods", "final", "winner", "stage", "source")}
        new = events(g, prev, s)
        if new:
            lines.setdefault(g["sport"], []).extend(new)
        seen[g["key"]] = s
        if s["state"] != "post":
            still = True
        if out_file is not None:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with out_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": at, "key": g["key"], **s}) + "\n")
    return lines, still


def resume(files: list[Path]) -> dict:
    """Each game's last saved look, so a handed-off run does not announce again what the run
    before it already said."""
    seen: dict = {}
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("key") and r.get("state"):
                seen[r["key"]] = r
    return seen


def message(lines: dict[str, list[str]], now: datetime | None = None) -> str:
    """One Telegram for the round; the look's time and the run id name the fetch (HR59)."""
    now = now or datetime.now(UTC)
    run = os.environ.get("GITHUB_RUN_ID", "local")
    parts = [f"MULTI-SPORT LIVE · looked {now:%H:%M}Z · run {run} (Flashscore / ESPN live feeds)"]
    for sport in SPORTS:
        if lines.get(sport):
            parts.append(f"\n{label(sport)}\n" + "\n".join(lines[sport]))
    return "\n".join(parts)


def tell(body: str) -> None:
    """To the Architect's own chat only (order 33), as football's and the NBA's live trackers."""
    try:
        from output.notify import send_architect
        ok, notes = send_architect(body)
        if not ok:
            print(f"  telegram NOT SENT ({'; '.join(notes) or 'no reason given'})", flush=True)
    except Exception as e:  # noqa: BLE001 — a missed message is not a stopped loop
        print(f"  telegram failed ({str(e)[:60]})", flush=True)


def _refresh() -> None:
    try:
        from monitor import fdata
        print(f"  {fdata.refresh()}", flush=True)
    except Exception as e:  # noqa: BLE001 — keep following what we have
        print(f"  framework-data refresh failed ({str(e)[:60]})", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="every rollout sport's picks followed live")
    ap.add_argument("--handoff", action="store_true")
    ap.add_argument("--once", action="store_true", help="one look, printed; no Telegram, no save")
    a = ap.parse_args(argv)
    started = datetime.now(UTC)
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    if not a.once and not a.handoff and repo and token and lu.other_loop_running(WORKFLOW, repo, token, run_id):
        print("a multi-sport live loop is already running — nothing to do")
        return 0
    rel = f"{DATA}/{started:%Y-%m-%d}"
    out_file = ROOT / rel / "live.jsonl"
    seen = resume([ROOT / DATA / f"{started - timedelta(days=1):%Y-%m-%d}" / "live.jsonl", out_file])
    rounds = 0
    while True:
        now = datetime.now(UTC)
        games = board_games(now)
        if not games:
            print(f"no multi-sport pick starts within {EARLIEST} or is in play — nothing to track")
            if rounds and not a.once:
                print(f"[{now:%H:%M}Z] {lu.save([rel], f'multisport live {started:%Y-%m-%d} [skip ci]')}", flush=True)
            return 0
        if rounds == 0:
            for g in games:
                print(f"  {g['ko'][11:16]}Z {g['sport']}: {g['home']} v {g['away']} — "
                      + " | ".join(p.get("pick") or "" for p in g["picks"]), flush=True)
        feeds = fetch_live({g["sport"] for g in games}, now)
        lines, still = round_once(games, seen, None if a.once else out_file, feeds, now)
        rounds += 1
        if lines:
            body = message(lines, now)
            print(body, flush=True)
            if not a.once:
                tell(body)
        if a.once:
            for g in games:
                s = find_live(g, feeds.get(g["sport"]) or {})
                print(f"  {g['sport']}: {g['home']} v {g['away']} -> "
                      + (f"{s['source']} {s['state']} {score_text(s)}" if s else "NO DATA — PENDING"))
            return 0
        if not still:
            print(f"ALL FOLLOWED GAMES FINAL · {lu.save([rel], f'multisport live {started:%Y-%m-%d} [skip ci]')}",
                  flush=True)
            return 0
        if rounds % PERSIST_EVERY == 0:
            print(f"[{datetime.now(UTC):%H:%M}Z] {lu.save([rel], f'multisport live {started:%Y-%m-%d} [skip ci]')}",
                  flush=True)
            _refresh()                     # picks frozen by a later look are followed too
        if datetime.now(UTC) - started >= lu.HANDOFF_AFTER:
            print(f"[{datetime.now(UTC):%H:%M}Z] {lu.save([rel], f'multisport live {started:%Y-%m-%d} [skip ci]')}",
                  flush=True)
            if repo and token:
                lu.hand_off(WORKFLOW, repo, token)
                print("handed off to a fresh run (job time limit)", flush=True)
            return 0
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
