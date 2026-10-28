"""
SCORELINES — the model's whole score table, read as a direction for the match.

Every 1X2 / overs / BTTS number on the board is a sum over the Dixon-Coles
score matrix (engine.dixon_coles.score_matrix). This module shows the table
itself: the most likely scores and the shape of the match (how many goals,
which side keeps a clean sheet, which side scores twice).

A LABEL ONLY (Architect 2026-10-28). Nothing selects, stakes or books on it.
The single most likely score is usually ~10-13%, so the top score is a story,
not a forecast; the spread is what is useful. The ledger keeps the 0-5 grid of
every rated fixture and the scorecard grades it (check()), so whether the table can be
trusted is measured before anything is wired to it.
"""
from __future__ import annotations

import math

import numpy as np

GRID = 6        # 0..5 goals per side kept in the ledger; the rest is "other"


def top_scores(m: np.ndarray, n: int = 3) -> list[tuple[str, float]]:
    """[('1-0', 0.12), ...] — the n most likely scores."""
    flat = np.argsort(m, axis=None)[::-1][:n]
    return [(f"{i}-{j}", float(m[i, j])) for i, j in
            (np.unravel_index(k, m.shape) for k in flat)]


def shape(m: np.ndarray) -> dict:
    """The match's shape from the table — each a yes/no chance."""
    tot = np.add.outer(np.arange(m.shape[0]), np.arange(m.shape[1]))
    return {"goals_0_1": float(m[tot <= 1].sum()),
            "goals_2_3": float(m[(tot >= 2) & (tot <= 3)].sum()),
            "goals_4p": float(m[tot >= 4].sum()),
            "home_cs": float(m[:, 0].sum()), "away_cs": float(m[0, :].sum()),
            "home_2p": float(m[2:, :].sum()), "away_2p": float(m[:, 2:].sum())}


def board_line(probs) -> str | None:
    """One board line, or None for a fixture with no model table
    (market-implied fixtures carry no matrix — no scoreline is invented)."""
    m = getattr(probs, "matrix", None)
    if m is None:
        return None
    top = " · ".join(f"{s} {round(p*100)}%" for s, p in top_scores(m))
    sh = shape(m)
    h, a = probs.home_team, probs.away_team
    return (f"Likely scores (model, label only): {top} | goals 0-1 {round(sh['goals_0_1']*100)}%"
            f" · 2-3 {round(sh['goals_2_3']*100)}% · 4+ {round(sh['goals_4p']*100)}%"
            f" | clean sheet {h} {round(sh['home_cs']*100)}% · {a} {round(sh['away_cs']*100)}%")


def ledger_grid(probs) -> list[list[float]] | None:
    """The 0-5 x 0-5 corner of the table, 4dp, for grading after the match."""
    m = getattr(probs, "matrix", None)
    if m is None:
        return None
    return [[round(float(x), 4) for x in row[:GRID]] for row in m[:GRID]]


def grade(grid: list, ft: str) -> dict | None:
    """How the stored table did against a 'h-a' full-time score:
    the chance it gave the actual score, the score's rank, and log loss.
    A score beyond the 0-5 grid gets the grid's leftover chance."""
    try:
        hg, ag = (int(x) for x in ft.split("-"))
    except (AttributeError, ValueError):
        return None
    g = np.asarray(grid, dtype=float)
    inside = hg < GRID and ag < GRID
    p = float(g[hg, ag]) if inside else max(0.0, 1.0 - float(g.sum()))
    rank = int((g > p).sum()) + 1 if inside else None
    return {"p": p, "rank": rank, "logloss": -math.log(max(p, 1e-6))}


def check(rows: list[tuple[list, str]]) -> list[str]:
    """Scorecard lines for the scoreline table over graded fixtures."""
    graded = [(x, float(np.max(g))) for g, ft in rows if (x := grade(g, ft)) is not None]
    if len(graded) < 10:
        return []
    n = len(graded)
    top1 = sum(x["rank"] == 1 for x, _ in graded)
    top3 = sum(x["rank"] is not None and x["rank"] <= 3 for x, _ in graded)
    said = sum(t for _, t in graded) / n      # what the top scores promised
    ll = sum(x["logloss"] for x, _ in graded) / n
    return [f"Scoreline check ({n} rated fixtures): top score right {100*top1/n:.0f}% "
            f"(model said {100*said:.0f}%) · in top 3 {100*top3/n:.0f}% · log loss {ll:.2f}"]
