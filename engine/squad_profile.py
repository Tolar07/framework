"""
SQUAD PROFILE — every player's role in his team, and the manager's rotation habit (Architect
2026-11-04: "the framework needs to understand each player profile and the squad depth and the
manager tactics ... gather a profile on all the players").

From FotMob's free pages: the team page (squad: position, market value, season rating,
injury; coach; fixtures) and the match pages of the team's last WINDOW finished matches, all
competitions (who started, who came on and when, each player's match rating).

Per player:
    starts / sub_apps / minutes over the window (minutes: a starter plays 90 unless
    subbed off, a sub from his minute on), avg_rating over the matches he played,
    role   regular (started 70%+), rotation (30-70%), fringe (played, started < 30%),
           unused (no minutes), out (injured / unavailable now).
Per team, the manager's rotation:
    avg_changes        XI changes between one match and the next
    short_rest / long_rest   the same after <= SHORT_REST days and after more
A manager who changes 4 of the XI after a midweek game is RESTING players, not losing them;
engine/squad_depth.py reads absences against this.

Built weekly for every covered team by monitor/squad_profiles.py -> data/players/squads.json.gz.
RECORDED ONLY: it labels; nothing picks or stakes on it.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from engine import squad_depth as sd

WINDOW = 10
SHORT_REST = 3.5          # days between matches


def _minutes(p: dict, starter: bool) -> int:
    ev = (p.get("performance") or {}).get("substitutionEvents") or []
    t_in = next((e.get("time") for e in ev if e.get("type") == "subIn"), None)
    t_out = next((e.get("time") for e in ev if e.get("type") == "subOut"), None)
    if starter:
        return int(t_out if isinstance(t_out, int) else 90)
    if isinstance(t_in, int):
        return max(1, int((t_out if isinstance(t_out, int) else 90) - t_in))
    return 0


def match_lines(details: dict, team_id) -> dict | None:
    """{xi: set of ids, players: {id: {starter, minutes, rating}}} for one team in one match."""
    lu = (details.get("content") or {}).get("lineup") or {}
    for side in ("homeTeam", "awayTeam"):
        t = lu.get(side) or {}
        if str(t.get("id")) != str(team_id):
            continue
        players = {}
        for starter, group in ((True, t.get("starters") or []), (False, t.get("subs") or [])):
            for p in group:
                mins = _minutes(p, starter)
                players[p.get("id")] = {"starter": starter, "minutes": mins,
                                        "rating": (p.get("performance") or {}).get("rating") if mins else None}
        xi = {i for i, x in players.items() if x["starter"]}
        return {"xi": xi, "players": players} if xi else None
    return None


def role(starts: int, minutes: int, n: int, out: bool) -> str:
    if out:
        return "out"
    if not minutes:
        return "unused"
    share = starts / n if n else 0
    return "regular" if share >= 0.7 else "rotation" if share >= 0.3 else "fringe"


def profile(team: dict, matches: list[tuple[str | None, dict]], unavailable: set | None = None) -> dict:
    """team: FotMob team page; matches: [(utc time, match_lines())] oldest first."""
    n = len(matches)
    rows = []
    for p in sd.squad(team):
        apps = [m["players"][p["id"]] for _t, m in matches if p["id"] in m["players"]]
        starts = sum(1 for a in apps if a["starter"])
        mins = sum(a["minutes"] for a in apps)
        rated = [a["rating"] for a in apps if a.get("rating")]
        out = p["injured"] or p["id"] in (unavailable or set())
        rows.append({"id": p["id"], "name": p["name"], "group": p["group"], "value": p["value"],
                     "injured": p["injured"], "starts": starts, "sub_apps": sum(1 for a in apps if not a["starter"]
                                                                               and a["minutes"]),
                     "minutes": mins, "avg_rating": round(sum(rated) / len(rated), 2) if rated else None,
                     "role": role(starts, mins, n, out)})
    changes, short, long_ = [], [], []
    for (t0, a), (t1, b) in zip(matches, matches[1:], strict=False):
        c = len(b["xi"] - a["xi"])
        changes.append(c)
        try:
            gap = (datetime.fromisoformat(str(t1).replace("Z", "+00:00"))
                   - datetime.fromisoformat(str(t0).replace("Z", "+00:00"))).total_seconds() / 86400
        except (TypeError, ValueError):
            continue
        (short if gap <= SHORT_REST else long_).append(c)

    def avg(xs: list[int]) -> float | None:
        return round(sum(xs) / len(xs), 2) if xs else None

    coach = next((m.get("name") for b in (team.get("squad") or {}).get("squad") or []
                  if (b.get("title") or "").lower() == "coach" for m in b.get("members") or []), None)
    det = team.get("details") or {}
    return {"id": det.get("id"), "name": det.get("name"), "coach": coach, "matches": n,
            "rotation": {"avg_changes": avg(changes), "short_rest": avg(short), "long_rest": avg(long_),
                         "n_short": len(short), "n_long": len(long_)},
            "players": sorted(rows, key=lambda r: (-r["starts"], -r["minutes"], -(r["value"] or 0)))}


def build(team_id, get: Callable[[str], dict], window: int = WINDOW) -> dict | None:
    team = sd._cached(get, sd._TEAM.format(tid=team_id))
    if not team:
        return None
    fx = ((team.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures") or []
    done = [f for f in fx if (f.get("status") or {}).get("finished") and not (f.get("status") or {}).get("cancelled")]
    matches = []
    for f in done[-window:]:
        try:
            m = match_lines(sd._cached(get, sd._DETAILS.format(mid=f.get("id"))), team_id)
        except Exception:  # noqa: BLE001,S112 — a missing match page shortens the window
            continue
        if m:
            matches.append(((f.get("status") or {}).get("utcTime"), m))
    return profile(team, matches)
