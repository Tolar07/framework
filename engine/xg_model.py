"""
xG RATING (improvement #3, Architect 2026-10-02; evidence backtest/XG_STUDY.md).

Team strength from expected goals (Understat, top-5 leagues): each team's
time-weighted (240-day half-life) xG created and allowed, scaled by the
league's home/away xG, -> Poisson scoreline grid. In both test seasons the xG
rating was more accurate than the goals model (Brier 0.5823 vs 0.5927 and
0.6001 vs 0.6040) and the goals+xG blend beat goals alone, so for these
leagues the model's scoreline grid becomes the AVERAGE of the Dixon-Coles grid
and the xG grid. Leagues without xG keep Dixon-Coles alone.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.stats import poisson

from data.flashscore_results import _sim

UNDERSTAT = {"Premier League": "EPL", "La Liga": "La_liga", "Bundesliga": "Bundesliga",
             "Serie A": "Serie_A", "Ligue 1": "Ligue_1"}
HALF_LIFE = 240.0
CACHE = Path(__file__).parent.parent / "data" / "cache" / "understat"
MAX_AGE = 12 * 3600
_G = np.arange(11)


def _fetch(code: str, year: int) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{code}_{year}.json"
    if not f.exists() or time.time() - f.stat().st_mtime > MAX_AGE:
        req = urllib.request.Request(f"https://understat.com/getLeagueData/{code}/{year}",
                                     headers={"User-Agent": "Mozilla/5.0",
                                              "X-Requested-With": "XMLHttpRequest",
                                              "Accept-Encoding": "gzip"})
        raw = urllib.request.urlopen(req, timeout=40).read()
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        f.write_bytes(raw)
    d = json.loads(f.read_text(encoding="utf-8"))
    return [{"date": m["datetime"][:10], "home": m["h"]["title"], "away": m["a"]["title"],
             "xh": float(m["xG"]["h"]), "xa": float(m["xG"]["a"])}
            for m in d.get("dates", []) if m.get("isResult")]


class XGRatings:
    def __init__(self, matches: list[dict], ref: str):
        self.att, self.dfn, self.ws = defaultdict(float), defaultdict(float), defaultdict(float)
        hx = ax = wt = 0.0
        refd = date.fromisoformat(ref)
        for m in matches:
            if m["date"] >= ref:
                continue
            w = 0.5 ** ((refd - date.fromisoformat(m["date"])).days / HALF_LIFE)
            self.att[m["home"]] += w * m["xh"]; self.dfn[m["home"]] += w * m["xa"]
            self.att[m["away"]] += w * m["xa"]; self.dfn[m["away"]] += w * m["xh"]
            self.ws[m["home"]] += w; self.ws[m["away"]] += w
            hx += w * m["xh"]; ax += w * m["xa"]; wt += w
        self.hx, self.ax, self.wt = hx, ax, wt
        self.teams = set(self.ws)

    def team(self, name: str) -> Optional[str]:
        """Our team name -> Understat's, strict (best match, >= 0.70)."""
        if not self.teams:
            return None
        best = max(self.teams, key=lambda u: _sim(name, u))
        return best if _sim(name, best) >= 0.70 else None

    def matrix(self, home: str, away: str) -> Optional[np.ndarray]:
        h, a = self.team(home), self.team(away)
        if not h or not a or self.ws[h] < 3 or self.ws[a] < 3 or not self.wt:
            return None
        avg = (self.hx + self.ax) / (2 * self.wt)
        lam_h = (self.hx / self.wt) * (self.att[h] / self.ws[h] / avg) * (self.dfn[a] / self.ws[a] / avg)
        lam_a = (self.ax / self.wt) * (self.att[a] / self.ws[a] / avg) * (self.dfn[h] / self.ws[h] / avg)
        m = np.outer(poisson.pmf(_G, lam_h), poisson.pmf(_G, lam_a))
        return m / m.sum()


def ratings_for(league: str, season_code: str, ref: Optional[str] = None) -> Optional[XGRatings]:
    """xG ratings for a league from last season + the current one
    (season_code '2627' -> Understat years 2025 and 2026)."""
    code = UNDERSTAT.get(league)
    if not code:
        return None
    year = 2000 + int(season_code[:2])
    matches = []
    for y in (year - 1, year):
        try:
            matches += _fetch(code, y)
        except Exception:  # noqa: BLE001 — a missing season just narrows the window
            continue
    if not matches:
        return None
    return XGRatings(matches, ref or date.today().isoformat())


def blend(probs, xg_matrix: np.ndarray):
    """FixtureProbabilities rebuilt from the average of its Dixon-Coles grid
    and the xG grid (every derived probability recomputed from the blend)."""
    from engine.dixon_coles import FixtureProbabilities
    if probs is None or probs.matrix is None:
        return probs
    m = (probs.matrix + xg_matrix) / 2
    m = m / m.sum()
    tot = np.add.outer(_G, _G)
    over = lambda line: float(m[tot > line].sum())
    btts_no = float(m[0, :].sum() + m[:, 0].sum() - m[0, 0])
    return FixtureProbabilities(
        home_team=probs.home_team, away_team=probs.away_team,
        lambda_home=probs.lambda_home, lambda_away=probs.lambda_away,
        p_home=float(np.tril(m, -1).sum()), p_draw=float(np.trace(m)),
        p_away=float(np.triu(m, 1).sum()),
        p_over_15=over(1), p_over_25=over(2), p_over_35=over(3),
        p_btts_yes=1 - btts_no, matrix=m)
