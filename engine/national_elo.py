"""
NATIONAL-TEAM ELO (Architect 2026-10-04: "the national team model").

World-Football-Elo style ratings on every men's international since 1990
(martj42/international_results, free, keyless — data/cache/international_results.csv):

  expected   We = 1 / (10^(-dr/400) + 1),  dr = home - away (+HOME_ADV unless neutral)
  update     R += K x G x (W - We)
  K          by competition: World Cup 60, continental finals 50, qualifiers and
             the Nations League 40, other tournaments 30, friendlies 20
  G          goal margin: 1 (by 0-1), 1.5 (by 2), (11 + margin) / 8 (by 3+)

Ratings become a full scoreline grid: expected goals for each side are a
log-linear function of the rating gap, fitted on the same history, and the
grid is Poisson with a Dixon-Coles low-score correction — so every market
(1X2, double chance, handicaps, goals lines) can be priced from it, exactly
like the club model. backtest/NATIONAL_STUDY.md compares it with the old
UEFA-only Dixon-Coles fit on matches neither has seen.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

CSV = Path(__file__).parent.parent / "data" / "cache" / "international_results.csv"
SINCE = "1990-01-01"
START = 1500.0
HOME_ADV = 100.0
RHO = -0.05
MAX_GOALS = 10

_CONTINENTAL = ("UEFA Euro", "Copa América", "African Cup of Nations", "AFC Asian Cup",
                "Gold Cup", "CONCACAF Championship", "Oceania Nations Cup")


def k_factor(tournament: str) -> float:
    t = tournament or ""
    if "qualification" in t or "Nations League" in t:
        return 40.0
    if t == "FIFA World Cup":
        return 60.0
    if any(t == c for c in _CONTINENTAL):
        return 50.0
    if t == "Friendly":
        return 20.0
    return 30.0


def margin_mult(gd: int) -> float:
    gd = abs(gd)
    return 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)


@dataclass
class Match:
    date: str
    home: str
    away: str
    hg: int
    ag: int
    tournament: str
    neutral: bool


def load(path: Path = CSV, since: str = SINCE) -> list[Match]:
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if r["date"] < since:
                continue
            try:
                out.append(Match(r["date"], r["home_team"], r["away_team"], int(r["home_score"]),
                                 int(r["away_score"]), r.get("tournament", ""),
                                 (r.get("neutral") or "").strip().upper() == "TRUE"))
            except (TypeError, ValueError):
                continue                                  # unplayed: never guessed
    return sorted(out, key=lambda m: m.date)


class NationalElo:
    def __init__(self):
        self.r: dict[str, float] = defaultdict(lambda: START)
        self.n: dict[str, int] = defaultdict(int)
        # goals model: log(lambda) = a + b * dr/400, home and away side
        self.ga, self.gb, self.aa, self.ab = math.log(1.4), 0.55, math.log(1.1), -0.55

    def gap(self, home: str, away: str, neutral: bool = False) -> float:
        return self.r[home] - self.r[away] + (0.0 if neutral else HOME_ADV)

    def update(self, m: Match) -> None:
        dr = self.gap(m.home, m.away, m.neutral)
        we = 1 / (10 ** (-dr / 400) + 1)
        w = 1.0 if m.hg > m.ag else (0.5 if m.hg == m.ag else 0.0)
        delta = k_factor(m.tournament) * margin_mult(m.hg - m.ag) * (w - we)
        self.r[m.home] += delta
        self.r[m.away] -= delta
        self.n[m.home] += 1
        self.n[m.away] += 1

    def fit_goals(self, samples: list[tuple[float, int, int]]) -> None:
        """Least-squares fit of log goals on the rating gap (bucketed means)."""
        def fit(pairs):
            xs = np.array([p[0] for p in pairs]) / 400
            ys = np.array([p[1] for p in pairs], dtype=float)
            bins = np.clip(np.round(xs * 4) / 4, -2, 2)
            bx, by = [], []
            for b in np.unique(bins):
                m = bins == b
                if m.sum() >= 30 and ys[m].mean() > 0:
                    bx.append(b)
                    by.append(math.log(ys[m].mean()))
            slope, inter = np.polyfit(bx, by, 1)
            return inter, slope
        self.ga, self.gb = fit([(dr, hg) for dr, hg, ag in samples])
        self.aa, self.ab = fit([(dr, ag) for dr, hg, ag in samples])

    def lambdas(self, home: str, away: str, neutral: bool = False) -> tuple[float, float]:
        x = self.gap(home, away, neutral) / 400
        return math.exp(self.ga + self.gb * x), math.exp(self.aa + self.ab * x)

    def known(self, team: str, min_games: int = 10) -> bool:
        return self.n.get(team, 0) >= min_games


def score_matrix(lh: float, la: float, rho: float = RHO) -> np.ndarray:
    i = np.arange(MAX_GOALS + 1)
    ph = np.exp(-lh) * lh ** i / np.array([math.factorial(k) for k in i])
    pa = np.exp(-la) * la ** i / np.array([math.factorial(k) for k in i])
    m = np.outer(ph, pa)
    m[0, 0] *= 1 - lh * la * rho
    m[0, 1] *= 1 + lh * rho
    m[1, 0] *= 1 + la * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def build(through: Optional[str] = None, path: Path = CSV) -> NationalElo:
    """Ratings through `through` (exclusive), goals model fitted on the same span."""
    model, samples = NationalElo(), []
    for m in load(path):
        if through and m.date >= through:
            break
        dr = model.gap(m.home, m.away, m.neutral)
        if m.date >= "2005-01-01":
            samples.append((dr, m.hg, m.ag))
        model.update(m)
    if len(samples) > 1000:
        model.fit_goals(samples)
    return model


def predict(model: NationalElo, home: str, away: str, neutral: bool = False):
    """FixtureProbabilities from the ratings, or None if a side has < 10 games."""
    from engine.dixon_coles import FixtureProbabilities
    if not (model.known(home) and model.known(away)):
        return None
    lh, la = model.lambdas(home, away, neutral)
    m = score_matrix(lh, la)
    tot = np.add.outer(np.arange(MAX_GOALS + 1), np.arange(MAX_GOALS + 1))
    return FixtureProbabilities(
        home_team=home, away_team=away, lambda_home=round(lh, 3), lambda_away=round(la, 3),
        p_home=float(np.tril(m, -1).sum()), p_draw=float(np.trace(m)),
        p_away=float(np.triu(m, 1).sum()),
        p_over_15=float(m[tot > 1.5].sum()), p_over_25=float(m[tot > 2.5].sum()),
        p_over_35=float(m[tot > 3.5].sum()),
        p_btts_yes=float(1 - (m[0, :].sum() + m[:, 0].sum() - m[0, 0])), matrix=m)
