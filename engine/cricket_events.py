"""
CRICKET EVENTS (framework #589, Event models #10): first-innings total runs, runs per over block, wickets. RECORD-ONLY /
SHADOW. Picks nothing, stakes nothing, moves no other number.

Idea: the batting side's expected first-innings runs (batting team's runs for, bowling team's runs against, and the
venue, each shrunk to the format average) are split over three over blocks by the SHARES the Cricsheet record shows
(T20: overs 1-6 / 7-15 / 16-20; ODI: 1-10 / 11-40 / 41-50), so the blocks always add up to the innings. Wickets are
a separate count rated the same way. Runs and wickets use a negative binomial. Re-implemented from the idea in
engine/event_model.py's distributions, not copied.

It agrees with the framework by construction: block means add up to the innings mean, and from_total() keeps the
board's own innings total (test). Missing inputs read PENDING (HR35); nothing is invented (HR59).
"""
from __future__ import annotations

from engine import event_model as em

# Cricsheet men's internationals, first innings that ran its course (re-fitted in CRICKET_EVENTS_STUDY.md).
SHARES = {"T20": (0.288, 0.425, 0.287), "ODI": (0.181, 0.565, 0.255)}
LINES_TOTAL = {"T20": (140.5, 155.5, 170.5, 185.5), "ODI": (230.5, 260.5, 290.5, 320.5)}
LINES_BLOCK = {"T20": ((39.5, 44.5, 49.5), (55.5, 62.5, 69.5), (44.5, 51.5, 58.5)),
               "ODI": ((44.5, 52.5, 60.5), (115.5, 135.5, 155.5), (60.5, 75.5, 90.5))}
LINES_WICKETS = {"T20": (5.5, 6.5, 7.5), "ODI": (6.5, 7.5, 8.5)}
DISP_TOTAL = {"T20": 40.0, "ODI": 40.0}
DISP_BLOCK = {"T20": 20.0, "ODI": 20.0}
DISP_WK = 20.0


class Ratings:
    """Runs and wickets for / against per team, and per venue, from prior first innings of ONE format."""

    def __init__(self, hist: list[dict]):
        self.f: dict[str, list] = {}      # team batting: [n, runs, wickets lost]
        self.a: dict[str, list] = {}      # team bowling: [n, runs conceded, wickets taken]
        self.v: dict[str, list] = {}      # venue: [n, runs, wickets]
        self.n = len(hist)
        tr = tw = 0.0
        for r in hist:
            runs, wk = sum(r["blocks"]), r["wk"]
            tr += runs
            tw += wk
            for d, key in ((self.f, r["bat"]), (self.a, r["bowl"]), (self.v, r["venue"])):
                v = d.setdefault(key, [0, 0.0, 0.0])
                v[0] += 1
                v[1] += runs
                v[2] += wk
        if self.n:
            self.lg_r, self.lg_w = tr / self.n, tw / self.n

    def rates(self, bat: str, bowl: str, venue: str | None, k: float = 10.0, kv: float = 10.0) -> tuple[float, float] | None:
        """Expected (first-innings runs, wickets): batting for x bowling against x venue, each a ratio to the format
        average shrunk toward 1 with k (teams) or kv (venue) pseudo-innings. None (PENDING, HR35) with no history."""
        if not self.n:
            return None

        def rel(v: list | None, lg: float, i: int, w: float) -> float:
            c, t = (v[0], v[i]) if v else (0, 0.0)
            return (t + w * lg) / ((c + w) * lg)

        out = []
        for lg, i in ((self.lg_r, 1), (self.lg_w, 2)):
            out.append(lg * rel(self.f.get(bat), lg, i, k) * rel(self.a.get(bowl), lg, i, k) * rel(self.v.get(venue), lg, i, kv))
        return out[0], out[1]


def fit_shares(rows: list[dict]) -> tuple[float, ...] | None:
    """Per-block share of first-innings runs from recorded innings. None (PENDING) with no runs."""
    tot = [sum(r["blocks"][i] for r in rows) for i in range(3)]
    return tuple(x / sum(tot) for x in tot) if sum(tot) else None


def predict(fmt: str, mean_runs: float | None, mean_wk: float | None = None, shares: tuple[float, ...] | None = None,
            d_t: float | None = None, d_b: float | None = None, d_w: float = DISP_WK) -> dict | None:
    """Event numbers for the batting side's first innings. None (PENDING) for an unknown format or a missing / non-positive
    run mean; wickets stay None without a wicket mean."""
    if fmt not in SHARES or not mean_runs or mean_runs <= 0:
        return None
    sh = shares or SHARES[fmt]
    s = sum(sh)
    sh = tuple(x / s for x in sh)
    d_t = DISP_TOTAL[fmt] if d_t is None else d_t
    d_b = DISP_BLOCK[fmt] if d_b is None else d_b
    out = {"shadow": True, "format": fmt, "runs": round(mean_runs, 2),
           "total_over": {str(ln): round(em.over(ln, mean_runs, d_t), 4) for ln in LINES_TOTAL[fmt]},
           "blocks": [{"block": i + 1, "runs": round(mean_runs * sh[i], 2),
                       "over": {str(ln): round(em.over(ln, mean_runs * sh[i], d_b), 4) for ln in LINES_BLOCK[fmt][i]}}
                      for i in range(3)],
           "wickets": None}
    if mean_wk and mean_wk > 0:
        out["wickets"] = {"mean": round(mean_wk, 2),
                          "over": {str(ln): round(em.over(ln, mean_wk, d_w), 4) for ln in LINES_WICKETS[fmt]}}
    return out


def from_total(fmt: str, total: float | None) -> dict | None:
    """Event numbers from the board's own first-innings total (the blocks add up to it). None (PENDING) without it."""
    return predict(fmt, total)
