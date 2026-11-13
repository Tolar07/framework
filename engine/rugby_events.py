"""
RUGBY EVENTS (framework #593, Event models #14): first / second half total points, tries and penalty goals. RECORD-ONLY /
SHADOW. Picks nothing, stakes nothing, moves no other number.

Idea: each side's expected points (from team points-for / against ratings, or from the board's own total and spread) are split
two ways. By HALF: the share of a side's points scored in the first half, fitted from the record. By SCORING EVENT: points per
try, conversion, penalty goal and drop goal are fitted as rates PER POINT, so 5*tries + 2*conversions + 3*penalties +
3*drops rebuilds the side's expected points exactly (test): the event numbers agree with the board's win / total numbers by
construction. Counts use a negative binomial (a side's tries are clumpier than Poisson), one dispersion per kind of event,
chosen in backtest/rugby_events_study.py. Re-implemented from the idea using engine/event_model.py's distributions;
reuses the team-ratings shrink of engine/baseball_events.py. Missing inputs read PENDING (HR35); nothing is invented (HR59).
"""
from __future__ import annotations

from engine import event_model as em
from engine.baseball_events import Ratings  # noqa: F401  (points for / against shrink)

LINES_HALF = (17.5, 20.5, 23.5)       # both teams' points in the first half
LINES_TRIES = (4.5, 5.5, 6.5)         # both teams' tries
LINES_TEAM_TRIES = (2.5, 3.5)         # one team's tries
LINES_PENS = (1.5, 2.5, 3.5)          # both teams' penalty goals
DISP_HALF = 20.0
DISP_TRIES = 30.0
DISP_PENS = 12.0
POINTS = {"tries": 5.0, "conv": 2.0, "pens": 3.0, "drops": 3.0}


def fit(rows: list[dict]) -> dict | None:
    """Half shares (home, away: first-half share of a side's points) and per-point event rates from recorded games.
    Rows need h1, h2 and pts; tries / conv / pens / drops are used where present. None (PENDING) with no points."""
    if not rows:
        return None
    h1h = sum(r["h1"][0] for r in rows)
    h1a = sum(r["h1"][1] for r in rows)
    ph = sum(r["pts"][0] for r in rows)
    pa = sum(r["pts"][1] for r in rows)
    if not ph or not pa:
        return None
    out: dict = {"share": (h1h / ph, h1a / pa), "n": len(rows), "rate": None}
    full = [r for r in rows if r.get("tries")]
    if full:
        pts = sum(r["pts"][0] + r["pts"][1] for r in full)
        if pts:
            out["rate"] = {k: sum(r[k][0] + r[k][1] for r in full) / pts for k in POINTS}
    return out


def predict(mh: float | None, ma: float | None, f: dict | None, d_h: float = DISP_HALF, d_t: float = DISP_TRIES,
            d_p: float = DISP_PENS) -> dict | None:
    """Event numbers from each side's expected points. None (PENDING) when a mean or the fit is missing; the try / penalty
    parts are None (PENDING) when no counted games were fitted."""
    if not mh or not ma or mh <= 0 or ma <= 0 or not f:
        return None
    sh, sa = f["share"]
    h1h, h1a = mh * sh, ma * sa
    out = {"shadow": True, "home_points": round(mh, 3), "away_points": round(ma, 3),
           "first_half": {"home": round(h1h, 3), "away": round(h1a, 3),
                          "over": {str(ln): round(em.over(ln, h1h + h1a, d_h), 4) for ln in LINES_HALF}},
           "second_half": {"home": round(mh - h1h, 3), "away": round(ma - h1a, 3)},
           "tries": None, "penalty_goals": None}
    r = f.get("rate")
    if r:
        th, ta = mh * r["tries"], ma * r["tries"]
        ph, pa = mh * r["pens"], ma * r["pens"]
        out["tries"] = {"home": round(th, 3), "away": round(ta, 3),
                        "total_over": {str(ln): round(em.over(ln, th + ta, d_t), 4) for ln in LINES_TRIES},
                        "team_over": {"home": {str(ln): round(em.over(ln, th, d_t), 4) for ln in LINES_TEAM_TRIES},
                                      "away": {str(ln): round(em.over(ln, ta, d_t), 4) for ln in LINES_TEAM_TRIES}}}
        out["penalty_goals"] = {"home": round(ph, 3), "away": round(pa, 3),
                                "total_over": {str(ln): round(em.over(ln, ph + pa, d_p), 4) for ln in LINES_PENS}}
    return out


def from_total(total: float | None, spread_home: float | None, f: dict | None) -> dict | None:
    """Event numbers from the board's own total and home spread (negative = home favoured): the sides are
    (total -/+ spread) / 2, so they add up to the board's total and differ by its spread. None (PENDING) without both."""
    if not total or total <= 0 or spread_home is None:
        return None
    return predict((total - spread_home) / 2, (total + spread_home) / 2, f)
