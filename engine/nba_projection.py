"""
NBA PLAYER-BUILT PROJECTION (Architect 2026-10-28, step 2 of 4: "built on how points are
actually scored"). RECORDED ONLY: stored in the NBA picks file beside the sharp line; no
pick, stake or threshold reads it. Wiring it into picks needs the Architect's OK after it
beats the sharp line on games it was not fitted to.

Per game, each team's points:

  lineup factor  the players actually available (data/nba_players.py sheet: Out removed,
                 Doubtful / Questionable / Day-To-Day weighted by their chance of playing),
                 expected minutes (0.6 x last-10 + 0.4 x season) scaled to 240, times each
                 player's points per minute (shrunk toward the team rate on small samples),
                 over the team's season points per game. 1.00 = the usual line-up.
  pace           possessions per game (FGA - OREB + TO + 0.44 FTA): home pace x away pace
                 / league pace, each shrunk toward the league on few games
  ratings        points per 100 possessions scored (team) and allowed (opponent), shrunk
  home / rest    +HOME_PTS for the home side, -HOME_PTS away; -B2B_PTS on the second night
                 of a back-to-back (previous tip-off within 30 hours)

  points = pace x team ORtg x lineup factor x opponent DRtg / league rating / 100 +- home - rest

Total and spread follow; the 1st half and 1st quarter take the measured shares (engine/
nba_value.py H1_SHARE / Q1_SHARE; step 3 refits them). Markets are yes/no, so every line
is recorded with BOTH sides' chances — the projection's and the sharp line's.

LINE-UP SHOCK: a top-3 scorer (season points per game) is Out and the sharp line has not
moved from its opening (total within 1.5, spread within 1.0) or SportyBet's main total is
still within 1.5 of the sharp OPENING total.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timedelta

from engine import nba_value as nv

HOME_PTS = 1.2           # each way: a 2.4-point home margin
B2B_PTS = 1.5            # points lost on the second night of a back-to-back
B2B_HOURS = 30
K_GAMES = 5              # pace / ratings shrunk toward the league by this many games
K_MIN = 60.0             # points per minute shrunk toward the team by this many minutes
LINEUP_CLIP = (0.85, 1.10)
PLAY_CHANCE = {"Doubtful": 0.25, "Questionable": 0.5, "Day-To-Day": 0.6}
SHOCK_TOTAL, SHOCK_SPREAD = 1.5, 1.0


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def team_table(trows: list[dict]) -> tuple[dict, dict]:
    """(team -> {n, ppg, pace, ortg, drtg, tips}, league {pace, rtg, ppg}) from the team log."""
    by_g: dict[str, list[dict]] = defaultdict(list)
    for r in trows:
        by_g[r["g"]].append(r)
    acc: dict[str, dict] = defaultdict(lambda: {"n": 0, "pts": 0, "poss": 0.0, "opp_pts": 0,
                                                "opp_poss": 0.0, "pace": 0.0, "tips": []})
    for rows in by_g.values():
        if len(rows) != 2:
            continue
        for me, op in (rows, rows[::-1]):
            a = acc[me["t"]]
            a["n"] += 1
            a["pts"] += me["pts"]
            a["poss"] += me["poss"]
            a["opp_pts"] += op["pts"]
            a["opp_poss"] += op["poss"]
            a["pace"] += (me["poss"] + op["poss"]) / 2
            if me.get("tip"):
                a["tips"].append(me["tip"])
    tot_pts = sum(a["pts"] for a in acc.values())
    tot_poss = sum(a["poss"] for a in acc.values())
    n = sum(a["n"] for a in acc.values())
    if not n or not tot_poss:
        return {}, {}
    lg = {"pace": sum(a["pace"] for a in acc.values()) / n, "rtg": 100 * tot_pts / tot_poss, "ppg": tot_pts / n}

    def shrink(x: float, k: int, prior: float) -> float:
        return (x + K_GAMES * prior) / (k + K_GAMES)

    out = {}
    for t, a in acc.items():
        out[t] = {"n": a["n"], "ppg": a["pts"] / a["n"],
                  "pace": shrink(a["pace"], a["n"], lg["pace"]),
                  "ortg": shrink(100 * a["pts"] / a["poss"] * a["n"], a["n"], lg["rtg"]),
                  "drtg": shrink(100 * a["opp_pts"] / a["opp_poss"] * a["n"], a["n"], lg["rtg"]),
                  "tips": sorted(a["tips"])}
    return out, lg


def lineup_factor(sheet: dict, team_ppg: float) -> float | None:
    """Points this line-up scores in the team's average game, over the team's points per game."""
    ppm_team = team_ppg / 240
    mins, pts = 0.0, 0.0
    for p in sheet.get("players") or []:
        if not p.get("gp") or p.get("min") is None:
            continue
        chance = PLAY_CHANCE.get(p.get("status", ""), 1.0)
        m = (0.6 * (p.get("min10") or p["min"]) + 0.4 * p["min"]) * chance
        ppm = (p["pts"] * p["gp"] + K_MIN * ppm_team) / (p["min"] * p["gp"] + K_MIN)
        mins += m
        pts += m * ppm
    if mins < 120 or team_ppg <= 0:          # not enough of the rotation known to say anything
        return None
    f = pts * (240 / mins) / team_ppg
    return round(min(max(f, LINEUP_CLIP[0]), LINEUP_CLIP[1]), 4)


def back_to_back(tips: list[str], tip: str) -> bool:
    t = _t(tip)
    return any(timedelta(0) < t - _t(x) <= timedelta(hours=B2B_HOURS) for x in tips)


def _over(line: float | None, mean: float, sd: float) -> dict | None:
    """Both sides of a total line: chance of Over and of Under (half lines only: no push)."""
    if line is None or float(line) == int(line):
        return None
    p = 1 - nv._phi((line - mean) / sd)
    return {"line": line, "over": round(p, 4), "under": round(1 - p, 4)}


def _home_cover(hcp: float | None, margin: float, sd: float) -> dict | None:
    """Both sides of the home handicap (hcp negative = home favoured)."""
    if hcp is None or float(hcp) == int(hcp):
        return None
    p = 1 - nv._phi((-hcp - margin) / sd)
    return {"line": hcp, "home": round(p, 4), "away": round(1 - p, 4)}


def project(game: dict, teams: dict, lg: dict, sharp: dict | None = None,
            sb_main: dict | None = None, cal: dict | None = None) -> dict:
    """One game of the players file (home_sheet / away_sheet) -> the projection record."""
    hs, as_ = game["home_sheet"], game["away_sheet"]
    why = [f"{s['team']}: {x}" for s in (hs, as_) for x in s.get("stale") or []]
    th, ta = teams.get(hs["team"]), teams.get(as_["team"])
    if th is None or ta is None or not lg:
        why.append("team not in the log")
    out: dict = {"espn_id": game["espn_id"], "home": hs["team"], "away": as_["team"]}
    shock = _shock(hs, as_, sharp, sb_main)
    out["lineup_shock"] = shock
    if why or th is None or ta is None:
        return {**out, "projection": None, "why": why}
    fh, fa = lineup_factor(hs, th["ppg"]), lineup_factor(as_, ta["ppg"])
    if fh is None or fa is None:
        return {**out, "projection": None, "why": ["rotation minutes unknown"]}
    pace = th["pace"] * ta["pace"] / lg["pace"]
    b2b_h, b2b_a = back_to_back(th["tips"], game["tip"]), back_to_back(ta["tips"], game["tip"])
    ph = pace * th["ortg"] * fh * ta["drtg"] / lg["rtg"] / 100 + HOME_PTS - B2B_PTS * b2b_h
    pa = pace * ta["ortg"] * fa * th["drtg"] / lg["rtg"] / 100 - HOME_PTS - B2B_PTS * b2b_a
    total, margin = ph + pa, ph - pa
    proj = {"home_pts": round(ph, 1), "away_pts": round(pa, 1), "total": round(total, 1),
            "spread": round(-margin, 1), "h1_total": round(total * nv.H1_SHARE, 1),
            "q1_total": round(total * nv.Q1_SHARE, 1), "pace": round(pace, 1),
            "lineup": {"home": fh, "away": fa}, "b2b": {"home": b2b_h, "away": b2b_a}}
    out["projection"] = proj
    out["sides"] = _sides(proj, sharp, sb_main, cal)
    return out


def _sides(proj: dict, sharp: dict | None, sb_main: dict | None, cal: dict | None = None) -> dict:
    """Both sides of every line we can name, by the projection and by the sharp line — and,
    given `cal` (engine/nba_recal.py's live numbers), by the sharp line with this season's
    refitted shares and widths ("sharp_recal")."""
    sharp, sb_main = sharp or {}, sb_main or {}
    st, ss = sharp.get("total"), sharp.get("spread")
    out: dict = {}
    for key, share, sd, sb_key, fam in (("total", 1.0, nv.TOTAL_SD, "225", "total"),
                                        ("h1_total", nv.H1_SHARE, nv.H1_SD, "68", "h1"),
                                        ("q1_total", nv.Q1_SHARE, nv.Q1_SD, "236", "q1")):
        lines = {"sportybet": sb_main.get(sb_key)}
        if st is not None:
            lines["sharp"] = math.floor(st * share) + 0.5          # the half line at the sharp centre
        row = {}
        for src, line in lines.items():
            if line is None:
                continue
            row[src] = {"projection": _over(line, proj[key], sd),
                        "sharp": _over(line, st * share, sd) if st is not None else None}
            if cal and st is not None:
                row[src]["sharp_recal"] = _over(line, st * cal[fam]["share"], cal[fam]["sd"])
        if row:
            out[key] = row
    if ss is not None:
        line = ss if float(ss) != int(ss) else ss + 0.5
        out["spread"] = {"sharp": {"projection": _home_cover(line, -proj["spread"], nv.MARGIN_SD),
                                   "sharp": _home_cover(line, -ss, nv.MARGIN_SD)}}
        if cal:
            out["spread"]["sharp"]["sharp_recal"] = _home_cover(line, -ss, cal["margin"]["sd"])
    return out


def _shock(hs: dict, as_: dict, sharp: dict | None, sb_main: dict | None) -> dict | None:
    out_names = (hs.get("top3_out") or []) + (as_.get("top3_out") or [])
    if not out_names:
        return None
    sharp, sb_main = sharp or {}, sb_main or {}
    ot, ct, os_, cs = sharp.get("open_total"), sharp.get("total"), sharp.get("open_spread"), sharp.get("spread")
    sharp_still = None
    if ot is not None and ct is not None and os_ is not None and cs is not None:
        sharp_still = abs(ct - ot) < SHOCK_TOTAL and abs(cs - os_) < SHOCK_SPREAD
    sb = sb_main.get("225")
    sb_still = None if sb is None or ot is None else abs(sb - ot) < SHOCK_TOTAL
    return {"out": out_names, "sharp_unmoved": sharp_still, "sportybet_unmoved": sb_still,
            "flag": bool(sharp_still or sb_still)}


def sportybet_main(event: dict) -> dict:
    """SportyBet's main line per total market (225 game, 68 1st half, 236 1st quarter): the
    half line whose Over and Under prices are closest to each other."""
    best: dict[str, tuple[float, float]] = {}
    for m in event.get("markets") or []:
        mid = str(m.get("id"))
        if mid not in ("225", "68", "236") or not nv.is_open(m):
            continue
        spec = m.get("specifier") or ""
        if mid == "236" and "quarternr=1" not in spec:
            continue
        try:
            line = float(re.search(r"total=(\d+(?:\.\d+)?)", spec).group(1))  # type: ignore[union-attr]
            prices = {o.get("desc", "").split(" ")[0]: float(o["odds"]) for o in m.get("outcomes") or []}
            gap = abs(prices["Over"] - prices["Under"])
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if line != int(line) and (mid not in best or gap < best[mid][1]):
            best[mid] = (line, gap)
    return {k: v[0] for k, v in best.items()}
