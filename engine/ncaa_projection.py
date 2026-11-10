"""
NCAA PLAYER-BUILT PROJECTION AND GATE (framework#396; the twin of engine/nba_projection.py + engine/nba_gate.py,
Architect 2026-11-06: basketball inherits the NBA). RECORD-ONLY: no pick, stake or threshold reads it. Wiring it
into picks needs the Architect's OK after the gate below opens.

Walk-forward, from data/ncaa_graded/player_games.jsonl (data/ncaa_players.py). For each game, each team's points:

  base     half the team's points scored per game and half the opponent's points allowed per game (prior games
           only), shrunk toward the league mean by K_GAMES games
  lineup   the players who played that night (known only afterwards, so HINDSIGHT, labelled; the NBA twin uses
           the pre-tip injury sheet): expected minutes = the player's prior average minutes, scaled to 200,
           times his prior points per minute (shrunk toward the team rate on few minutes), over the team's prior
           points per game; clipped to LINEUP_CLIP
  points   base x lineup factor; the game total is the two added

GATE (the NBA gate's test): OPEN only when, over at least MIN_GAMES graded games, the projection's chances on
the SAME yes/no total lines (the sharp line and 5 points either side, both sides) beat the sharp line's on BOTH
Brier and log loss, AND the projection's side gains against the sharp CLOSING total. ESPN gives one pre-tip
line, no close is recorded, so CLV reads PENDING (HR35) and the gate stays CLOSED. It never opens by guess.
"""
from __future__ import annotations

import math
from collections import defaultdict

from engine import ncaa_lines as nl

K_GAMES = 8
K_MIN = 60.0
MIN_PRIOR = 5
TEAM_MIN = 200.0
LINEUP_CLIP = (0.85, 1.10)
LINE_OFFSETS = (-5.0, 0.0, 5.0)
MIN_GAMES = 150


def walk(rows: list[dict]) -> list[dict]:
    """One record per game (oldest first) with a projection from prior games only; games with fewer than
    MIN_PRIOR prior games for either team are left out (PENDING), never guessed."""
    rows = sorted(rows, key=lambda r: (r["day"], r["g"]))
    team = defaultdict(lambda: {"n": 0, "for": 0.0, "agt": 0.0})
    play = defaultdict(lambda: {"m": 0.0, "pts": 0.0, "gp": 0})          # (team, player)
    lg = {"n": 0, "pts": 0.0}
    out = []
    for r in rows:
        if r.get("ot"):
            continue
        h, a = r["home"], r["away"]
        th, ta = team[h], team[a]
        if lg["n"] and th["n"] >= MIN_PRIOR and ta["n"] >= MIN_PRIOR:
            league = lg["pts"] / lg["n"]
            pts = {}
            for side, me, opp, tid in (("home", th, ta, h), ("away", ta, th, a)):
                for_ = (me["for"] + K_GAMES * league) / (me["n"] + K_GAMES)
                agt = (opp["agt"] + K_GAMES * league) / (opp["n"] + K_GAMES)
                base = 0.5 * (for_ + agt)
                ppm_team = for_ / TEAM_MIN
                mins = tot = 0.0
                for p in r["pl"][side]:
                    s = play[(tid, p["p"])]
                    if p["m"] <= 0 or s["gp"] == 0 or s["m"] <= 0:
                        continue
                    em = s["m"] / s["gp"]
                    ppm = (s["pts"] + K_MIN * ppm_team) / (s["m"] + K_MIN)
                    mins += em
                    tot += em * ppm
                f = 1.0
                if mins >= 0.6 * TEAM_MIN:
                    f = min(max(tot * (TEAM_MIN / mins) / for_, LINEUP_CLIP[0]), LINEUP_CLIP[1])
                pts[side] = base * f
            out.append({"g": r["g"], "day": r["day"], "line": r["line"], "actual": r["hs"] + r["as"],
                        "proj": pts["home"] + pts["away"]})
        for side, tid in (("home", h), ("away", a)):
            mine, theirs = (r["hs"], r["as"]) if side == "home" else (r["as"], r["hs"])
            t = team[tid]
            t["n"] += 1
            t["for"] += mine
            t["agt"] += theirs
            lg["n"] += 1
            lg["pts"] += mine
            for p in r["pl"][side]:
                if p["m"] > 0:
                    s = play[(tid, p["p"])]
                    s["m"] += p["m"]
                    s["pts"] += p["pts"]
                    s["gp"] += 1
    return out


def _score(p: float, y: int) -> tuple[float, float]:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return (p - y) ** 2, -(y * math.log(p) + (1 - y) * math.log(1 - p))


def paired(recs: list[dict]) -> dict:
    """Projection vs sharp on the SAME total lines: n lines, Brier and log loss of each, plus points error."""
    pb = pl = sb = sl = 0.0
    n = 0
    for r in recs:
        mu_s, mu_p = r["line"] + nl.TOTAL_BIAS, r["proj"]
        for off in LINE_OFFSETS:
            ln = math.floor(mu_s) + 0.5 + off
            y = int(r["actual"] > ln)
            b1, l1 = _score(1 - nl._phi((ln - mu_p) / nl.TOTAL_SD), y)
            b2, l2 = _score(1 - nl._phi((ln - mu_s) / nl.TOTAL_SD), y)
            pb, pl, sb, sl, n = pb + b1, pl + l1, sb + b2, sl + l2, n + 1
    if not n:
        return {"n": 0}
    g = len(recs)
    return {"n": n, "games": g, "projection": {"brier": pb / n, "logloss": pl / n},
            "sharp": {"brier": sb / n, "logloss": sl / n},
            "mae_projection": sum(abs(r["proj"] - r["actual"]) for r in recs) / g,
            "mae_sharp": sum(abs(r["line"] + nl.TOTAL_BIAS - r["actual"]) for r in recs) / g}


def status(recs: list[dict], clv: dict | None = None) -> dict:
    """The gate. clv None (no closing line recorded) = PENDING, which keeps it closed."""
    pr = paired(recs)
    why = []
    if len(recs) < MIN_GAMES:
        why.append(f"{len(recs)} graded games < {MIN_GAMES}")
    if pr["n"] and not (pr["projection"]["brier"] < pr["sharp"]["brier"]
                        and pr["projection"]["logloss"] < pr["sharp"]["logloss"]):
        why.append("does not beat the sharp line on both Brier and log loss")
    if not pr["n"]:
        why.append("no graded lines")
    if not clv or clv.get("mean_pts") is None:
        why.append("CLV PENDING: no sharp closing total recorded")
    elif clv["mean_pts"] <= 0:
        why.append("no positive CLV against the sharp close")
    return {"open": not why, "why": why, "games": len(recs), "lines": pr}
