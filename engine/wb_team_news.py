"""
WORLD BASKETBALL TEAM NEWS PER PICK — twin of engine/nba_team_news.py for NCAA (framework#391).

Architect 2026-11-06: "NBA and basketball, they're the same thing ... inherit all its attributes of NBA".
The NBA says per pick whether the injury report HURTS / HELPS it. Here the same verdict is given for an NCAA
men's pick, from ESPN's college roster feed (site.api.espn.com/.../mens-college-basketball/teams/<id>/roster,
each athlete's `injuries`), weighed with the SAME rules as the NBA (engine/nba_team_news.py verdicts,
engine/nba_absence_impact.py weights: already-out = 0, rotation = share of the last 5 games played):

  * a team with nobody listed: lost share 0, no box scores fetched. Read as "ESPN lists none", NOT as
    "nobody is hurt": college injury coverage is thin (measured 2026-11-10: 0 of 327 rostered players listed
    across 20 teams on a full board), so the note says so;
  * a team with a listed player: his recent minutes come from that team's last completed games' box scores
    (past games only); fewer than MIN_GAMES logged -> PENDING (HR35);
  * EuroLeague / FIBA / other world leagues: no injury feed exists -> PENDING, never an invented absence.

RECORD-ONLY. Nothing here drops, restakes or re-prices a pick. Verdicts append to
output/world_basketball/wb_news_<day>.jsonl (saved by the edge workflow with the rest of that folder) so they can
be graded against results before they are ever allowed to matter. Raw ESPN data is cached per run only.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from data import nba_players as npl
from engine import exchange as ex
from engine import nba_absence_impact as nai
from engine import nba_team_news as ntn
from engine import ncaa_lines as nl
from engine import world_basketball as wb

_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
_ROSTER = _BASE + "/teams/{t}/roster"
_SCHED = _BASE + "/teams/{t}/schedule"
_SUMMARY = _BASE + "/summary?event={e}"
THIN = "ESPN lists none for this team; college injury coverage is thin, so this is not proof nobody is out"
NO_FEED = "PENDING (no injury feed for this league: only NCAA men's has one, framework#391)"


def is_ncaa(pick: dict) -> bool:
    return "ncaa" in (pick.get("comp") or "").lower()


def news_path(day: str, folder: Path = wb.OUT_DIR) -> Path:
    return folder / f"wb_news_{day}.jsonl"


def games(day: datetime, get=nl._get) -> list[dict]:
    """ESPN Division I games on one US date with team ids: {id, tip, home, away (name forms), ids, abbr}."""
    blob = get(nl._SB.format(d=day.strftime("%Y%m%d"))) or {}
    out = []
    for e in blob.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        t = {c.get("homeAway"): c.get("team") or {} for c in comp.get("competitors") or []}
        if "home" not in t or "away" not in t:
            continue

        def names(x: dict) -> list[str]:
            return [n for n in (x.get("displayName"), x.get("shortDisplayName"), x.get("location"), x.get("name"))
                    if n]
        out.append({"id": e["id"], "tip": ex._dt(e.get("date")), "home": names(t["home"]), "away": names(t["away"]),
                    "ids": {"home": str(t["home"].get("id")), "away": str(t["away"].get("id"))},
                    "abbr": {"home": t["home"].get("abbreviation"), "away": t["away"].get("abbreviation")}})
    return out


def roster_injuries(team_id: str, get=nl._get) -> list[dict] | None:
    """[{id, name, status}] listed on the team's roster; None when the roster could not be read."""
    blob = get(_ROSTER.format(t=team_id))
    if not blob:
        return None
    out = []
    for a in blob.get("athletes") or []:
        for i in a.get("injuries") or []:
            out.append({"id": str(a.get("id")), "name": a.get("displayName", ""), "status": i.get("status", "")})
    return out


def team_rows(team_id: str, abbr: str, before: datetime, get=nl._get, last: int = 6) -> list[dict]:
    """Box-score rows (data/nba_players format) of the team's last completed games before `before`."""
    sched = get(_SCHED.format(t=team_id)) or {}
    done = []
    for e in sched.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        when = ex._dt(e.get("date"))
        if when and when < before and ((comp.get("status") or {}).get("type") or {}).get("completed"):
            done.append((when, e["id"], comp))
    rows: list[dict] = []
    for when, eid, comp in sorted(done, key=lambda x: x[0])[-last:]:
        blob = get(_SUMMARY.format(e=eid))
        if not blob:
            continue
        sides = {c.get("homeAway"): (c.get("team") or {}).get("abbreviation") for c in comp.get("competitors") or []}
        g: Any = SimpleNamespace(id=eid, date=when.strftime("%Y-%m-%d"), home=sides.get("home"), away=sides.get("away"))
        rows += npl.box_rows(g, blob)
    return rows


def _zero(team: str) -> dict:
    return {"team": team, "lost_share": 0.0, "missing": [], "pending": None}


def assess_pick(pick: dict, game: dict, ko: datetime, get=nl._get) -> dict:
    """{verdict, level, side, note, raw/adj shares} for one NCAA pick against its ESPN game."""
    sides: dict[str, dict] = {}
    shares: dict[str, dict] = {}
    none_listed: list[str] = []
    for s in ("home", "away"):
        inj = roster_injuries(game["ids"][s], get)
        name = game[s][0] if game[s] else s
        if inj is None:
            sides[s] = {"team": name, "lost_share": None, "missing": [], "pending": "roster unreadable"}
            continue
        if not inj:
            sides[s] = _zero(name)
            none_listed.append(s)
            continue
        rows = team_rows(game["ids"][s], game["abbr"][s], ko, get)
        abbr = game["abbr"][s]
        sides[s] = {**ntn.team_loss(rows, abbr, inj), "team": name}
        shares[s] = nai.team_impact(rows, abbr, inj)
    v = ntn.assess(str(pick.get("market_id")), pick.get("outcome", ""), sides["home"], sides["away"])
    if none_listed and v["verdict"] in ("NEUTRAL", "HELPED"):
        v["note"] += f" [{THIN}]"
    v["absence"] = {s: None if shares.get(s) is None else
                    {k: shares[s][k] for k in ("raw_share", "adj_share", "level", "pending")} for s in sides}
    return v


def update(picks: list[dict], now: datetime, day: str, folder: Path = wb.OUT_DIR, get=nl._get) -> list[dict]:
    """Record one verdict per not-yet-started world basketball pick. Returns the verdicts (record-only)."""
    out = []
    last: dict[str, tuple] = {}
    if news_path(day, folder).exists():
        for line in news_path(day, folder).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            last[f"{r['event_id']}|{r['market_id']}|{r['pick']}"] = (r["verdict"], r["note"])
    for p in picks:
        ko = ex._dt(p.get("ko"))
        if ko is None or ko <= now:
            continue
        if is_ncaa(p):
            gs = games(ko, get) + games(ko - timedelta(days=1), get)
            g = nl.match(p["home"], p["away"], ko, gs)
            by_id = {x["id"]: x for x in gs}
            game = by_id.get(g["id"]) if g else None
            v = assess_pick(p, game, ko, get) if game else \
                {"verdict": "PENDING", "level": "PENDING", "side": None, "note": "game not matched on ESPN"}
        else:
            v = {"verdict": "PENDING", "level": "PENDING", "side": None, "note": NO_FEED}
        if last.get(f"{p.get('sb_event_id')}|{p.get('market_id')}|{p.get('pick')}") == (v["verdict"], v["note"]):
            continue                      # unchanged since the last look: record changes only
        out.append({"at": now.strftime("%Y-%m-%dT%H:%MZ"), "game": f"{p['away']}@{p['home']}",
                    "event_id": p.get("sb_event_id"), "pick": p.get("pick"), "market_id": p.get("market_id"), **v})
    if out:
        folder.mkdir(parents=True, exist_ok=True)
        with news_path(day, folder).open("a", encoding="utf-8", newline="\n") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


def run(now: datetime, folder: Path = wb.OUT_DIR, get=nl._get) -> list[str]:
    """Every frozen wb pick file: record verdicts; return alert lines for HURT / HELPED changes (state in file)."""
    alerts: list[str] = []
    if not folder.exists():
        return alerts
    for p in sorted(folder.glob("wb_20*.json")):
        day = p.stem[3:]
        picks = json.loads(p.read_text(encoding="utf-8")).get("picks", [])
        seen: dict = {}
        if news_path(day, folder).exists():
            for line in news_path(day, folder).read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                seen[f"{r['event_id']}|{r['market_id']}|{r['pick']}"] = r["verdict"] if r["verdict"] in (
                    "HURT", "HELPED") else "NEUTRAL"
        verdicts = update(picks, now, day, folder, get)
        alerts += ntn.changes(verdicts, seen)
    return alerts
