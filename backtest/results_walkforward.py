"""
Shared walk-forward Elo pieces for the multi-sport backtests (framework#352; record-only).

Used by backtest/baseball_backtest.py, snooker_backtest.py, darts_backtest.py and table_tennis_backtest.py. A game is
a dict with an ordering key "key" (a real date where the source has one, "YYYY-MM-DD..." always), the two sides
"a" / "b", "y" = 1.0 when side a won (0.0 when side b won), and optionally "home" = True when side a is at home and
"season" (a label; ratings are pulled back toward the start value between seasons when `carry` < 1).

Every game is scored BEFORE it is learned (no look-ahead); a game where either side has fewer than `min_games`
earlier games gets no chance (None) and is not scored. Nothing here reads a price, a stake or the live switch.
"""
from __future__ import annotations

import math
from collections.abc import Iterable

ELO_START = 1500.0


def replay(games: list[dict], k: float, min_games: int = 0, home_adv: float = 0.0,
           carry: float = 1.0) -> list[float | None]:
    """Elo chance that side a wins, before each game, in the order given; then learn from the result."""
    r: dict[str, float] = {}
    n: dict[str, int] = {}
    out: list[float | None] = []
    season = None
    for g in games:
        s = g.get("season")
        if carry < 1.0 and s is not None and season is not None and s != season:
            r = {t: ELO_START + carry * (v - ELO_START) for t, v in r.items()}
        season = s
        a, b = g["a"], g["b"]
        ra, rb = r.get(a, ELO_START), r.get(b, ELO_START)
        h = home_adv if g.get("home") else 0.0
        e = 1 / (1 + 10 ** ((rb - ra - h) / 400))
        out.append(e if n.get(a, 0) >= min_games and n.get(b, 0) >= min_games else None)
        d = k * (g["y"] - e)
        r[a], r[b] = ra + d, rb - d
        n[a], n[b] = n.get(a, 0) + 1, n.get(b, 0) + 1
    return out


def clip(p: float) -> float:
    return min(max(p, 1e-6), 1 - 1e-6)


def score(rows: Iterable[tuple[float, float]]) -> dict:
    """Brier, log loss and hit rate of (chance of side a, side a won 0/1) pairs."""
    n = hits = 0
    b = ll = 0.0
    for p, y in rows:
        n += 1
        b += (p - y) ** 2
        q = clip(p)
        ll -= math.log(q if y else 1 - q)
        hits += (p > 0.5) == (y == 1.0)
    return {"n": n, "brier": b / n if n else None, "ll": ll / n if n else None, "hit": hits / n if n else None}


def pick(games: list[dict], probs: list[float | None], lo: str, hi: str) -> list[tuple[float, float]]:
    """Scored (chance, result) pairs whose key falls in [lo, hi)."""
    return [(p, g["y"]) for g, p in zip(games, probs, strict=True) if p is not None and lo <= g["key"] < hi]


def fmt(x: float | None, spec: str = ".4f") -> str:
    return "PENDING" if x is None else format(x, spec)


def results_only_study(games: list[dict], tries: list[tuple[float, int]], split: str, board: tuple[float, int],
                       min_tuned: int = 200) -> dict:
    """Walk-forward results-only test: every (K, min games) try replayed over all games; the best on the games
    keyed before `split` (lowest log loss, at least `min_tuned` scored) is reported on the games from `split` on,
    next to the board's own setting and the coin flip (Brier 0.25, log loss 0.6931). Every try is counted."""
    rows: list[dict] = []
    for k, mg in tries:
        probs = replay(games, k, mg)
        rows.append({"k": k, "mg": mg, "tune": score(pick(games, probs, "", split)),
                     "test": score(pick(games, probs, split, "￿"))})
    ok = [r for r in rows if r["tune"]["n"] >= min_tuned]
    best = min(ok, key=lambda r: r["tune"]["ll"]) if ok else None
    base = next((r for r in rows if (r["k"], r["mg"]) == board), None)
    return {"rows": rows, "best": best, "board": base, "tries": len(rows)}


def results_only_lines(res: dict) -> list[str]:
    """Markdown table + verdict for results_only_study()."""
    L = ["| K | Min games each | Tuning: scored | Tuning log loss | Held-out: scored | Held-out Brier | "
         "Held-out log loss | Held-out hit rate |", "|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        tag = " (board)" if r is res["board"] else ""
        tag += " (picked)" if r is res["best"] else ""
        t, h = r["tune"], r["test"]
        L.append(f"| {r['k']:g}{tag} | {r['mg']} | {t['n']} | {fmt(t['ll'])} | {h['n']} | {fmt(h['brier'])} | "
                 f"{fmt(h['ll'])} | {fmt(h['hit'], '.1%')} |")
    b = res["best"]
    L.append("")
    if not b or not b["test"]["n"]:
        L.append("Verdict: PENDING (too few scored matches in the tuning or held-out part).")
        return L
    h = b["test"]
    beats = h["ll"] < math.log(2) and h["brier"] < 0.25
    L.append(f"Verdict: the setting picked on the tuning part (K={b['k']:g}, min games {b['mg']}) scores held-out "
             f"Brier {h['brier']:.4f} / log loss {h['ll']:.4f} / hit rate {h['hit']:.1%} on {h['n']} matches, against "
             f"the coin flip's 0.2500 / 0.6931: the Elo {'carries' if beats else 'does NOT carry'} information on "
             "unseen matches. No price in this source, so this is accuracy only, never an edge or a return.")
    return L
