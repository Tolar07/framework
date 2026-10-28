"""
NBA PLAYERS AND LINE-UPS (Architect 2026-10-28: treat the NBA like football, built on how
points are actually scored — line-ups, players, minutes, each player's points).

Step 1 of 4, RECORDED ONLY: this module adds numbers to the NBA picks file and changes
no pick, stake or threshold.

Free, keyless ESPN endpoints (the same family data/nba_source.py already uses):
  summary  site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=<id>
           finished game -> box score: every player's minutes, points, starter, DNP
           coming game   -> each team's injury list (Out / Doubtful / Day-To-Day ...)

  data/nba_lineups/player_games.jsonl   one row per player per finished REGULAR-SEASON
                                        game (tracked in git: the runners start empty)
  data/nba_lineups/meta.json            which days have been scanned
  data/cache/nba/summary/<id>.json      raw finished-game summaries (re-fetchable)

Per coming game and team, `team_sheet` gives the injury list, the EXPECTED starters
(ESPN publishes no confirmed NBA line-up before tip-off: the five who started most of
the team's last five games, leaving out anyone listed Out) and each available player's
season and last-10 minutes and points.

STALE-DATA GATE: a sheet is marked stale (and step 2 must not project from it) when the
log's newest game is older than STALE_DAYS before the night, when the injury list could
not be read, or when a team has fewer than MIN_GAMES logged games. Nothing is guessed:
a missing number stays missing (HR35).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from data import nba_source as ns

DIR = Path(__file__).parent / "nba_lineups"
LOG = DIR / "player_games.jsonl"
TEAM_LOG = DIR / "team_games.jsonl"     # one row per team per game: points, possessions, tip
META = DIR / "meta.json"
CACHE = ns.CACHE / "summary"
_SUM = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={e}"

STALE_DAYS = 3          # newest logged game older than this before the night -> stale
MIN_GAMES = 2           # a team needs this many logged games to be projected from
LAST_N = 10
OUT = {"Out"}           # statuses that take a player off the sheet
DOUBT = {"Doubtful": 0.25, "Questionable": 0.5, "Day-To-Day": 0.6}   # chance he plays


def season_start(d: date) -> date:
    """1 October of the season's first year — the regular season is found by game type."""
    return date(d.year if d.month >= 8 else d.year - 1, 10, 1)


def summary(event_id: str, completed: bool, fetch=ns._get) -> dict | None:
    path = CACHE / f"{event_id}.json"
    if completed and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    blob = fetch(_SUM.format(e=event_id))
    if blob is not None and completed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(blob), encoding="utf-8")
    return blob


def _minutes(x) -> float | None:
    try:
        return float(str(x).split(":")[0]) if x not in (None, "", "--") else None
    except ValueError:
        return None


def box_rows(g: ns.Game, blob: dict) -> list[dict]:
    """One row per player who was on the box score (DNP players kept, minutes 0)."""
    rows = []
    for side in (blob.get("boxscore") or {}).get("players") or []:
        team = (side.get("team") or {}).get("abbreviation")
        if team not in (g.home, g.away):
            continue
        for st in side.get("statistics") or []:
            keys = st.get("keys") or []
            if "minutes" not in keys or "points" not in keys:
                continue
            im, ip = keys.index("minutes"), keys.index("points")
            for a in st.get("athletes") or []:
                ath, stats = a.get("athlete") or {}, a.get("stats") or []
                dnp = bool(a.get("didNotPlay")) or not stats
                mins = 0.0 if dnp else _minutes(stats[im])
                try:
                    pts = 0 if dnp else int(stats[ip])
                except (ValueError, IndexError):
                    pts = None
                if mins is None or pts is None:
                    continue
                rows.append({"g": g.id, "d": g.date, "t": team, "o": g.away if team == g.home else g.home,
                             "h": int(team == g.home), "p": str(ath.get("id")), "n": ath.get("displayName", ""),
                             "s": int(bool(a.get("starter"))), "m": mins, "pts": pts})
    return rows


def _made_att(x) -> tuple[int, int]:
    a, b = str(x).split("-")
    return int(a), int(b)


def team_rows(g: ns.Game, blob: dict) -> list[dict]:
    """Both teams' points and possessions (FGA - OREB + TO + 0.44 FTA); [] if a number is missing."""
    pts = {g.home: g.hs, g.away: g.as_}
    out = []
    for t in (blob.get("boxscore") or {}).get("teams") or []:
        team = str((t.get("team") or {}).get("abbreviation"))
        st = {x.get("name"): x.get("displayValue") for x in t.get("statistics") or []}
        try:
            fga, fta = _made_att(st["fieldGoalsMade-fieldGoalsAttempted"])[1], _made_att(st["freeThrowsMade-freeThrowsAttempted"])[1]
            poss = round(fga - int(st["offensiveRebounds"]) + int(st.get("totalTurnovers") or st["turnovers"]) + 0.44 * fta, 1)
        except (KeyError, TypeError, ValueError):
            return []
        if pts.get(team) is None:
            return []
        out.append({"g": g.id, "d": g.date, "tip": g.tip, "t": team, "o": g.away if team == g.home else g.home,
                    "h": int(team == g.home), "pts": pts[team], "poss": poss})
    return out if len(out) == 2 else []


def load_log(path: Path = LOG) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def update_log(today: date, fetch=ns._get, scoreboard=ns.scoreboard,
               log: Path = LOG, meta: Path = META) -> list[str]:
    """Append every finished regular-season game up to yesterday not yet logged."""
    m = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    start = season_start(today)
    done = date.fromisoformat(m["through"]) if m.get("through") and m.get("season") == start.isoformat() else None
    tlog = log.parent / TEAM_LOG.name
    if done is None:
        for f in (log, tlog):
            if f.exists():
                f.unlink()                             # a new season starts a new log
    have = {r["g"] for r in load_log(log)}
    new: list[dict] = []
    notes: list[str] = []
    tnew = backfill_teams(log, tlog, fetch)
    d, through = (done + timedelta(1)) if done else start, done
    while d < today:
        games = scoreboard(d)
        if d >= today - timedelta(1) and any(not g.completed for g in games if g.stype == 2):
            break                                      # last night not finished yet: come back to it
        for g in games:
            if g.stype != 2 or g.id in have or not g.completed:   # older unfinished = postponed
                continue
            blob = summary(g.id, True, fetch) or {}
            rows, trows = box_rows(g, blob), team_rows(g, blob)
            if not rows or not trows:
                notes.append(f"{g.away} @ {g.home} {g.date}: no box score — retried next run")
                return _save(log, meta, new, start, through, notes, tnew)
            new += rows
            tnew += trows
        through = d
        d += timedelta(1)
    return _save(log, meta, new, start, through, notes, tnew)


def backfill_teams(log: Path, tlog: Path, fetch=ns._get) -> list[dict]:
    """Team rows for logged games that have none (the team log came after the player log)."""
    have = {r["g"] for r in load_log(tlog)}
    games: dict[str, dict] = {}
    for r in load_log(log):
        games.setdefault(r["g"], {"d": r["d"]})["home" if r["h"] else "away"] = r["t"]
    out = []
    for gid, x in games.items():
        if gid in have or "home" not in x or "away" not in x:
            continue
        blob = summary(gid, True, fetch) or {}
        comp = ((blob.get("header") or {}).get("competitions") or [{}])[0]
        score = {c.get("homeAway"): c.get("score") for c in comp.get("competitors") or []}
        try:
            hs, as_ = int(score["home"]), int(score["away"])
        except (KeyError, TypeError, ValueError):
            continue
        g = ns.Game(gid, x["d"], 0, 2, x["home"], x["away"], hs, as_, True, tip=comp.get("date", ""))
        out += team_rows(g, blob)
    return out


def _append(path: Path, rows: list[dict]) -> None:
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)


def _save(log: Path, meta: Path, new: list[dict], start: date, through, notes: list[str],
          tnew: list[dict]) -> list[str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    _append(log, new)
    _append(log.parent / TEAM_LOG.name, tnew)
    if through:
        meta.write_text(json.dumps({"season": start.isoformat(), "through": through.isoformat()}) + "\n",
                        encoding="utf-8", newline="\n")
    return notes + ([f"{len(new)} player-game rows added"] if new else [])


def injuries(blob: dict) -> dict[str, list[dict]]:
    """Team abbreviation -> [{id, name, status}] from a coming game's summary."""
    out: dict[str, list[dict]] = {}
    for t in blob.get("injuries") or []:
        team = (t.get("team") or {}).get("abbreviation")
        if not team:
            continue
        out[team] = [{"id": str((i.get("athlete") or {}).get("id")),
                      "name": (i.get("athlete") or {}).get("displayName", ""),
                      "status": i.get("status", "")} for i in t.get("injuries") or []]
    return out


def _avg(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 2) if xs else None


def player_lines(rows: list[dict], team: str) -> tuple[list[dict], int, list[str]]:
    """Each player whose latest game was for `team`: season and last-10 minutes and points.
    Returns (players, team games logged, ids of the last 5 games in date order)."""
    games = sorted({(r["d"], r["g"]) for r in rows if r["t"] == team})
    by_p: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["d"]):
        by_p[r["p"]].append(r)
    out = []
    for pid, rs in by_p.items():
        if rs[-1]["t"] != team:
            continue
        played = [r for r in rs if r["m"] > 0]
        last = played[-LAST_N:]
        out.append({"id": pid, "name": rs[-1]["n"], "gp": len(played),
                    "min": _avg([r["m"] for r in played]), "pts": _avg([r["pts"] for r in played]),
                    "min10": _avg([r["m"] for r in last]), "pts10": _avg([r["pts"] for r in last])})
    out.sort(key=lambda p: -(p["pts"] or 0))
    return out, len(games), [g for _d, g in games[-5:]]


def team_sheet(rows: list[dict], team: str, injured: list[dict] | None, night: date) -> dict:
    players, n_games, last5 = player_lines(rows, team)
    status = {i["id"]: i["status"] for i in injured or []}
    starts: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["t"] == team and r["g"] in last5 and r["s"]:
            starts[r["p"]] += 1
    for p in players:
        p["status"] = status.get(p["id"], "")
        p["starts5"] = starts.get(p["id"], 0)
    avail = [p for p in players if p["status"] not in OUT]
    starters = sorted(avail, key=lambda p: (-p["starts5"], -(p["min10"] or 0)))[:5]
    newest = max((r["d"] for r in rows), default=None)
    stale = []
    if injured is None:
        stale.append("injury list unreadable")
    if newest is None or date.fromisoformat(newest) < night - timedelta(STALE_DAYS):
        stale.append(f"newest box score {newest or 'none'}")
    if n_games < MIN_GAMES:
        stale.append(f"{n_games} games logged")
    top3 = [p["id"] for p in players[:3]]
    return {"team": team, "games": n_games, "stale": stale,
            "out": [i for i in injured or [] if i["status"] in OUT],
            "doubtful": [i for i in injured or [] if i["status"] in DOUBT],
            "top3_out": [p["name"] for p in players[:3] if p["status"] in OUT],
            "top3": top3,
            "starters": [p["name"] for p in starters], "starters_source": "expected",
            "players": avail}


def night_sheets(start: datetime, end: datetime, now: datetime, fetch=ns._get,
                 scoreboard=ns.scoreboard, log: Path = LOG) -> tuple[list[dict], list[str]]:
    """Every ESPN game tipping inside [start, end): both teams' sheets."""
    notes = update_log(now.date(), fetch=fetch, scoreboard=scoreboard, log=log, meta=log.parent / "meta.json")
    rows = load_log(log)
    days = sorted({start.date(), (end - timedelta(seconds=1)).date()})
    out = []
    for d in days:
        for g in scoreboard(d, use_cache=False):
            if not g.tip:
                continue
            tip = datetime.fromisoformat(g.tip.replace("Z", "+00:00"))
            if not (start <= tip < end) or g.completed:
                continue
            blob = summary(g.id, False, fetch)
            inj = injuries(blob) if blob is not None else None
            night = start.date()
            out.append({"espn_id": g.id, "tip": g.tip, "home": g.home, "away": g.away,
                        "fetched_at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "home_sheet": team_sheet(rows, g.home, None if inj is None else inj.get(g.home, []), night),
                        "away_sheet": team_sheet(rows, g.away, None if inj is None else inj.get(g.away, []), night)})
    return out, notes
