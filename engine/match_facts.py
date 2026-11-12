"""
MATCH FACTS - every board game of every sport except football, with the numbers Flashscore shows on a match
page: the STATS tab by period (basketball field goal %, rebounds, turnovers by quarter; ice hockey shots on
goal, saves, penalties, power play by period; tennis aces, double faults, serve and return points by set; and
whatever Flashscore lists for the other sports), each side's last matches and the head-to-head.

The Architect, 2026-11-12: "aside football, all other sports don't show ... stats like this ... you can
reverse engineer it in Flashscore ... implement it in all the sports ... with all these statistics ... you're
able to inform the decision making and the processing and the prediction."

Football is not here: it has FotMob's stats (data/match_stats.py) and its own model (engine/event_model.py).

The feeds (the same host and sign as the results feed, data/flashscore_results.py; read on 2026-11-12):
  f_<sport>_<day offset>_1_en-uk_1   the day's games; AA = the game's id
  df_st_1_<id>                       STATS: SE = period ("Match", "1st Quarter", "Set 1"), SF = group ("Scoring"),
                                     SG = stat name, SH = home value, SI = away value
  df_hh_1_<id>                       H2H: KA = tab ("Overall"), KB = section ("Last matches: X", "Head-to-head
                                     matches"), then one row per past game (KC time, KJ / KK names, KL score,
                                     WIS = w / l / d for the side the section is about)

RECORD ONLY. Nothing here picks, stakes, prices or blocks anything. A game that cannot be matched to a
Flashscore game with both names (monitor/multisport_live.find_live, never a guess) has no facts and reads
PENDING in the app. Every finished game with stats is appended once to data/match_facts/<sport>/<month>.jsonl:
that archive is what a model may later be fitted on, after the usual walk-forward proof.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "match_facts"
ARCHIVE = ROOT / "data" / "match_facts"
UTC = timezone.utc
BASKETBALL = "basketball"
HOCKEY = "ice_hockey"
FS_BASKETBALL = 3
EXTRA_PER_SPORT = 8          # rated games without a pick that still get a page, per sport and day
LAST_N = 6                   # past matches kept per side, and head-to-head
MAX_DETAIL = 400             # detail feeds read in one run (a run is one polite pass, not a crawl)
PAUSE = 0.15
_FEED = "https://local-global.flashscore.ninja/2/x/feed/"


# ---------------------------------------------------------------- parsing (pure)
def _blocks(text: str):
    for block in (text or "").split("~"):
        kv: dict[str, str] = {}
        for f in block.split("¬"):
            if "÷" in f:
                k, v = f.split("÷", 1)
                kv.setdefault(k, v)
        if kv:
            yield kv


def parse_day(text: str) -> list[dict]:
    """Every game of a day feed, with its Flashscore id:
    {id, league, home, away, kickoff_utc, state pre/in/post, stage, final [h, a], periods [[h, a]..]}."""
    out, league = [], ""
    for kv in _blocks(text):
        if "ZA" in kv:
            league = kv["ZA"]
            continue
        if "AA" not in kv:
            continue
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
        out.append({"id": kv["AA"], "league": league, "home": kv.get("AE", ""), "away": kv.get("AF", ""),
                    "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "state": {"1": "pre", "2": "in", "3": "post"}.get(kv.get("AB", ""), "pre"),
                    "stage": kv.get("AC"), "final": [fh, fa], "fthg": fh, "ftag": fa, "periods": periods})
    return out


def parse_stats(text: str) -> list[dict]:
    """The STATS tab: [{period, groups: [{name, rows: [[stat, home, away], ...]}]}], in Flashscore's order.
    Values are kept as Flashscore writes them ("48.48%", "64% (36/56)", "3/6", "28")."""
    out: list[dict] = []
    for kv in _blocks(text):
        if "SE" in kv:
            out.append({"period": kv["SE"], "groups": []})
        elif "SF" in kv and out:
            out[-1]["groups"].append({"name": kv["SF"], "rows": []})
        elif "SG" in kv and out:
            if not out[-1]["groups"]:
                out[-1]["groups"].append({"name": "", "rows": []})
            out[-1]["groups"][-1]["rows"].append([kv["SG"], kv.get("SH", ""), kv.get("SI", "")])
    return [p for p in out if any(g["rows"] for g in p["groups"])]


_FRAC = re.compile(r"\((\d+)\s*/\s*(\d+)\)")
_PLAIN_FRAC = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def number(value: str) -> dict | None:
    """A stat value as numbers, for a model: {"v": 48.48, "pct": True} / {"v": 64.0, "pct": True, "made": 36,
    "of": 56} / {"made": 3, "of": 6} / {"v": 28.0}. None when it holds no number."""
    v = (value or "").strip()
    if not v:
        return None
    m = _PLAIN_FRAC.match(v)
    if m:
        return {"made": int(m.group(1)), "of": int(m.group(2))}
    out: dict = {}
    f = _FRAC.search(v)
    if f:
        out.update(made=int(f.group(1)), of=int(f.group(2)))
    head = _NUM.search(v.split("(")[0])
    if head:
        out["v"] = float(head.group(0))
        if "%" in v:
            out["pct"] = True
    return out or None


def flat_stats(stats: list[dict]) -> dict:
    """{period: {stat: [home numbers, away numbers]}}: the archive's shape (one row per finished game)."""
    out: dict[str, dict] = {}
    for p in stats:
        row = out.setdefault(p["period"], {})
        for g in p["groups"]:
            for name, h, a in g["rows"]:
                nh, na = number(h), number(a)
                if nh is not None or na is not None:
                    row[name] = [nh, na]
    return out


def parse_h2h(text: str, last_n: int = LAST_N) -> dict:
    """The first tab of the H2H feed (all venues / surfaces):
    {home_last: [...], away_last: [...], h2h: [...]}; a row = {date, comp, home, away, score, res}.
    `res` is w / l / d for the side the section is about (for h2h: for the home side of the board game),
    None when Flashscore does not say."""
    out: dict[str, list] = {"home_last": [], "away_last": [], "h2h": []}
    tab, key, seen_last = 0, None, 0
    for kv in _blocks(text):
        if "KA" in kv:
            tab += 1
            if tab > 1:
                break
            continue
        if "KB" in kv:
            title = kv["KB"].lower()
            if title.startswith("head"):
                key = "h2h"
            else:
                key = ("home_last", "away_last")[min(seen_last, 1)]
                seen_last += 1
            continue
        if "KC" not in kv or key is None or len(out[key]) >= last_n:
            continue
        try:
            when = datetime.fromtimestamp(int(kv["KC"]), tz=UTC).strftime("%Y-%m-%d")
        except ValueError:
            continue
        res = (kv.get("WIS") or "").lower()
        out[key].append({"date": when, "comp": kv.get("KF") or kv.get("KI") or "",
                         "home": (kv.get("KJ") or "").lstrip("*"), "away": (kv.get("KK") or "").lstrip("*"),
                         "score": kv.get("KL") or "", "res": res if res in ("w", "l", "d") else None})
    return out


def form_line(rows: list[dict]) -> str:
    """'WWLWD' newest first, from a side's last matches."""
    return "".join((r.get("res") or "?").upper() for r in rows)


# ---------------------------------------------------------------- which games (every sport's board)
def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _iso(s: str | None) -> str | None:
    try:
        d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def board_games(day: str, root: Path = ROOT, extra: int = EXTRA_PER_SPORT) -> list[dict]:
    """Every game that gets a match page for one board date: all games with a pick, plus up to `extra` more
    rated games per sport (the ones the exchange also lists first). {key, sport, id, home, away, ko, comp}."""
    from engine import multisport as ms
    out: dict[str, dict] = {}

    def add(sport, eid, home, away, ko, comp, picked):
        ko = _iso(ko)
        if not (eid and home and away and ko):
            return
        key = f"{sport}:{eid}"
        g = out.setdefault(key, {"key": key, "sport": sport, "id": eid, "home": home, "away": away, "ko": ko,
                                 "comp": comp or "", "picked": False})
        g["picked"] = g["picked"] or picked

    files = [(HOCKEY, root / "output" / "ice_hockey" / f"ih_{day}.json")]
    files += [(s, root / "output" / "multisport" / s / f"ms_{day}.json") for s in ms.SPORTS]
    for sport, path in files:
        doc = _load(path) or {}
        for p in doc.get("picks") or []:
            add(sport, p.get("sb_event_id") or p.get("event_id"), p.get("home"), p.get("away"),
                p.get("ko") or p.get("tip"), p.get("comp"), True)
        rest = [(eid, g) for eid, g in (doc.get("games") or {}).items() if f"{sport}:{eid}" not in out]
        rest.sort(key=lambda x: (not x[1].get("matchbook"), x[1].get("ko") or ""))
        for eid, g in rest[:extra]:
            add(sport, eid, g.get("home"), g.get("away"), g.get("ko"), g.get("comp"), False)
    nba = _load(root / "output" / "picks" / f"nba_{day}.json") or {}
    for p in nba.get("picks") or []:
        add(BASKETBALL, p.get("event_id"), p.get("home"), p.get("away"), p.get("tip"), "NBA", True)
    for g in nba.get("study") or []:
        add(BASKETBALL, g.get("event_id"), g.get("home"), g.get("away"), g.get("tip"), "NBA", False)
    wb = _load(root / "output" / "world_basketball" / f"wb_{day}.json") or {}
    for p in wb.get("picks") or []:
        add(BASKETBALL, p.get("sb_event_id") or p.get("event_id"), p.get("home"), p.get("away"),
            p.get("ko") or p.get("tip"), p.get("comp"), True)
    return sorted(out.values(), key=lambda g: (g["sport"], g["ko"], g["key"]))


def fs_code(sport: str) -> int:
    from engine import multisport as ms
    if sport == BASKETBALL:
        return FS_BASKETBALL
    if sport == HOCKEY:
        return 4
    return ms.SPORTS[sport]["fs"]


# ---------------------------------------------------------------- one run
def path_for(day: str, out_dir: Path | None = None) -> Path:
    return (out_dir or OUT_DIR) / f"mf_{day}.json"


def needs(entry: dict, ev: dict) -> tuple[bool, bool]:
    """(read the form / head-to-head?, read the stats?) for one game this run. The form is read once, before
    or after the start; the stats every run while the game is on and once more when it has finished."""
    want_form = "form" not in entry
    want_stats = ev["state"] == "in" or (ev["state"] == "post" and not entry.get("final_stats"))
    return want_form, want_stats


def update_day(day: str, games: list[dict], feeds: dict[str, list[dict]], fetch, now: datetime,
               doc: dict | None = None, budget: int = MAX_DETAIL) -> tuple[dict, int, list[dict]]:
    """Bring one day's file up to date. `feeds` = {sport: [parse_day events]}; `fetch(feed, id)` -> text.
    Returns (doc, detail feeds read, finished games to archive)."""
    from monitor import multisport_live as ml
    doc = doc or {"date": day, "games": {}}
    doc["note"] = ("Flashscore match facts, record only. A game with no Flashscore match reads PENDING; "
                   "nothing here picks or stakes.")
    used, archive = 0, []
    for g in games:
        entry = doc["games"].setdefault(g["key"], {})
        entry.update(sport=g["sport"], home=g["home"], away=g["away"], ko=g["ko"], comp=g["comp"])
        ev = ml.find_live(g, {"flashscore": feeds.get(g["sport"]) or []})
        if not ev:
            entry.setdefault("pending", "no Flashscore match for this game (names or time did not pair)")
            continue
        entry.pop("pending", None)
        entry.update(fs_id=ev["id"], fs_home=ev["home"], fs_away=ev["away"], league=ev["league"],
                     state=ev["state"], score=ev["final"] if ev["state"] != "pre" else None,
                     periods=ev["periods"])
        want_form, want_stats = needs(entry, ev)
        if want_form and used < budget:
            used += 1
            try:
                h = parse_h2h(fetch("df_hh_1_", ev["id"]))
                entry["form"] = {**h, "home_form": form_line(h["home_last"]), "away_form": form_line(h["away_last"])}
            except Exception as e:  # noqa: BLE001 - read again next run
                entry["form_pending"] = type(e).__name__
        if want_stats and used < budget:
            used += 1
            try:
                stats = parse_stats(fetch("df_st_1_", ev["id"]))
            except Exception as e:  # noqa: BLE001 - read again next run
                entry["stats_pending"] = type(e).__name__
                continue
            entry.pop("stats_pending", None)
            if stats:
                entry["stats"] = stats
            if ev["state"] == "post":
                entry["final_stats"] = True
                if stats and not entry.get("archived"):
                    entry["archived"] = True
                    archive.append({"sport": g["sport"], "date": day, "ko": g["ko"], "comp": g["comp"],
                                    "league": ev["league"], "home": g["home"], "away": g["away"],
                                    "fs_id": ev["id"], "score": ev["final"], "periods": ev["periods"],
                                    "stats": flat_stats(stats)})
    doc["updated"] = now.strftime("%Y-%m-%dT%H:%MZ")
    doc["counts"] = {"games": len(doc["games"]),
                     "matched": sum(1 for e in doc["games"].values() if e.get("fs_id")),
                     "with_stats": sum(1 for e in doc["games"].values() if e.get("stats")),
                     "with_form": sum(1 for e in doc["games"].values() if e.get("form"))}
    return doc, used, archive


def append_archive(rows: list[dict], folder: Path | None = None) -> int:
    for r in rows:
        p = (folder or ARCHIVE) / r["sport"] / f"{r['ko'][:7]}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def run(now: datetime | None = None, root: Path = ROOT, get=None) -> str:
    """Yesterday's, today's and tomorrow's boards (UK dates), every sport: one line saying what was read."""
    from data import flashscore_results as fr
    from engine import uktime
    now = now or datetime.now(UTC)
    sign = None

    def _get(path: str) -> str:
        nonlocal sign
        if get is not None:
            return get(path)
        sign = sign or fr.feed_sign()
        time.sleep(PAUSE)
        return fr._get(_FEED + path, {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})

    today = uktime.uk(now).date()
    days = [(today + timedelta(days=k)).isoformat() for k in (-1, 0, 1)]
    by_day = {d: board_games(d, root) for d in days}
    sports = sorted({g["sport"] for gs in by_day.values() for g in gs})
    feeds: dict[str, list[dict]] = {}
    for sport in sports:
        evs: list[dict] = []
        for off in (-2, -1, 0, 1, 2):
            try:
                evs += parse_day(_get(f"f_{fs_code(sport)}_{off}_1_en-uk_1"))
            except Exception:  # noqa: BLE001, S112 - a silent day feed: its games read PENDING this run
                continue
        feeds[sport] = list({e["id"]: e for e in evs}.values())     # a game is in two day feeds near midnight
    budget, notes = MAX_DETAIL, []
    for d in (days[1], days[0], days[2]):               # today first: it has the games in play
        path = path_for(d, root / "output" / "match_facts")
        doc, used, arch = update_day(d, by_day[d], feeds, lambda feed, eid: _get(feed + eid), now,
                                     _load(path), budget)
        budget -= used
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        append_archive(arch, root / "data" / "match_facts")
        c = doc["counts"]
        notes.append(f"{d}: {c['matched']}/{c['games']} matched, {c['with_stats']} with stats, "
                     f"{c['with_form']} with form, {len(arch)} archived")
    return "match facts: " + "; ".join(notes)
