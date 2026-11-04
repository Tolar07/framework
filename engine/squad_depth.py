"""
SQUAD DEPTH — does an absence really weaken the team? (Architect 2026-11-04, on the 16:42
LINEUP RISK alerts for Real Madrid and Liverpool: "Rodrygo has been out for a long time.
Tchouameni and Arda Guler are being rotated. You need to understand the squad depth ... the
player that is being rotated out is either being rested and the squad strength is not dropping.")

The raw missing share (data/fotmob._side) counts every unavailable player as a starter at full
market value. Here each one is weighed by what his absence actually changes:

  ALREADY OUT   he started none of the team's last RECENT matches (all competitions): the
                team's recent results AND the price already carry his absence -> weight 0.
  ROTATION      he started k of the last RECENT: weight k / RECENT (a regular starter = 1).
  DEPTH         the best cover in the squad (not unavailable, not in this match's XI, one cover
                per absence): his own position group first (full-backs and centre-backs apart);
                failing that a neighbouring group's player at MAKESHIFT of his value; worth
                v_cover against his v: weight x max(0, 1 - v_cover / v). Cover as good as
                him -> 0; no cover -> full value.

    effective value = value x start share x (1 - cover ratio)
    adjusted share  = sum(effective) / (XI value + sum(effective))

The raw share is kept beside it, and every player gets a plain reason, so the alert can say
why. Read from FotMob's free team page (squad: positions, market values, injuries; fixtures)
and the match pages of the last RECENT finished matches (who started).
"""
from __future__ import annotations

from collections.abc import Callable

RECENT = 5
_TEAM = "https://www.fotmob.com/api/data/teams?id={tid}"
_DETAILS = "https://www.fotmob.com/api/data/matchDetails?matchId={mid}"
GROUPS = {"GK": "GK", "CB": "CB", "LB": "FB", "RB": "FB", "LWB": "FB", "RWB": "FB",
          "DM": "MID", "CDM": "MID", "CM": "MID", "LM": "MID", "RM": "MID", "AM": "AM",
          "CAM": "AM", "LW": "ATT", "RW": "ATT", "ST": "ATT", "CF": "ATT"}
# cover from the player's own group first; a NEIGHBOUR group's cover is a makeshift fit and
# counts at MAKESHIFT of its value (Pinnacle FC ep. 121 @ 12:05: a makeshift left-back against a
# winger in form is the real worry; Mourinho, presser @ 22:39: structural change worries, a
# like-for-like swap "is not dramatic")
NEAR = {"CB": ("FB",), "FB": ("CB", "MID"), "MID": ("AM",), "AM": ("MID", "ATT"), "ATT": ("AM",)}
MAKESHIFT = 0.5


def group(desc: str | None) -> str | None:
    """FotMob's positionIdsDesc ("CM,DM") -> its first position's group."""
    first = (desc or "").split(",")[0].strip().upper()
    return GROUPS.get(first)


def squad(team: dict) -> list[dict]:
    out = []
    for block in ((team.get("squad") or {}).get("squad") or []):
        if (block.get("title") or "").lower() == "coach":
            continue
        for m in block.get("members") or []:
            out.append({"id": m.get("id"), "name": m.get("name"), "value": m.get("transferValue") or 0,
                        "group": group(m.get("positionIdsDesc")), "injured": bool(m.get("injury"))})
    return out


def recent_match_ids(team: dict, n: int = RECENT) -> list:
    fx = ((team.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures") or []
    done = [f for f in fx if (f.get("status") or {}).get("finished") and not (f.get("status") or {}).get("cancelled")]
    return [f.get("id") for f in done[-n:]]


def starters_of(details: dict, team_id) -> set:
    lu = (details.get("content") or {}).get("lineup") or {}
    for side in ("homeTeam", "awayTeam"):
        t = lu.get(side) or {}
        if str(t.get("id")) == str(team_id):
            return {p.get("id") for p in t.get("starters") or []}
    return set()


def assess(missing: list[dict], xi_value: float, players: list[dict], recent_xis: list[set],
           xi_ids: set | None = None) -> dict:
    """missing: [{id, name, value}]; players: squad(); recent_xis: starter-id sets, newest last;
    xi_ids: this match's (predicted or confirmed) starters, who can't also be the cover.
    -> {adjusted_share, players: [{name, value, starts, cover, weight, effective, reason}]}"""
    out_ids = {m.get("id") for m in missing} | set(xi_ids or ())
    used: set = set()                                  # one cover per absence
    n = len(recent_xis)
    rows, eff_total = [], 0.0
    for m in missing:
        v = float(m.get("value") or 0)
        me = next((p for p in players if p["id"] == m.get("id")), None)
        starts = sum(1 for xi in recent_xis if m.get("id") in xi) if n else None
        if starts == 0:
            rows.append({"name": m.get("name"), "value": v, "starts": f"0/{n}", "cover": None,
                         "weight": 0.0, "effective": 0.0,
                         "reason": f"already out: no start in the last {n}, priced in"})
            continue
        share = starts / n if n else 1.0
        g = me["group"] if me else None
        free = [p for p in players if p["id"] not in out_ids and p["id"] not in used and not p["injured"]
                and p["id"] != m.get("id")]
        own = [p for p in free if g and p["group"] == g]
        near = [p for p in free if g and p["group"] in NEAR.get(g, ())]
        cover = max(own, key=lambda p: p["value"], default=None)
        fit = 1.0
        if cover is None:
            cover, fit = max(near, key=lambda p: p["value"], default=None), MAKESHIFT
        if cover:
            used.add(cover["id"])
        ratio = min(1.0, fit * cover["value"] / v) if cover and v else 0.0
        weight = share * (1 - ratio)
        eff = v * weight
        eff_total += eff
        why = (f"{'regular' if share >= 0.8 else 'rotation'} ({starts}/{n} starts)" if n else "starts unknown")
        why += (f", {'makeshift ' if fit < 1 else ''}cover {cover['name']} ({ratio:.0%} of his value)"
                if cover else ", no fit cover")
        rows.append({"name": m.get("name"), "value": v, "starts": f"{starts}/{n}" if n else None,
                     "cover": cover["name"] if cover else None, "weight": round(weight, 3),
                     "effective": round(eff), "reason": why})
    pool_v = xi_value + eff_total
    return {"adjusted_share": (eff_total / pool_v) if pool_v else None, "recent": n,
            "players": sorted(rows, key=lambda r: -r["value"])}


_CACHE: dict[str, dict] = {}       # one read per page per process (a board run asks for many teams)


def _cached(get: Callable[[str], dict], url: str) -> dict:
    if url not in _CACHE:
        _CACHE[url] = get(url)
    return _CACHE[url]


def for_team(team_id, missing: list[dict], xi_value: float, get: Callable[[str], dict],
             xi_ids: set | None = None) -> dict | None:
    """Fetch the squad and the last RECENT line-ups, then assess(); None when FotMob has no team page."""
    if not team_id or not missing:
        return None
    team = _cached(get, _TEAM.format(tid=team_id))
    if not team:
        return None
    xis = []
    for mid in recent_match_ids(team):
        try:
            xi = starters_of(_cached(get, _DETAILS.format(mid=mid)), team_id)
        except Exception:  # noqa: BLE001,S112 — one missing match page shortens the window, never fails
            continue
        if xi:
            xis.append(xi)
    return assess(missing, xi_value, squad(team), xis, xi_ids)
