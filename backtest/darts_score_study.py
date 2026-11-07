"""
Darts correct-score study (framework#341, Week A; record-only). Writes backtest/DARTS_SCORE_STUDY.md.

Does the darts format model (backtest/darts_format_study.py) predict the SET SCORE of a PDC World Championship match,
not just who wins? Walk-forward: the Elo from earlier matches gives a win chance, the format model solves the per-leg
edge that reproduces it and gives a chance for every set score (first to S sets, sets of first to 3 legs; the
final-set two-clear-legs rule is ignored). The score distribution is compared with a baseline that knows only the
format (equal players). Multi-class Brier over the score outcomes, lower is better. Sets-to-win S per round is the
largest winner score seen in that round (a match with another winner score is skipped, never guessed, HR35).
No closing price exists for these matches: this says nothing about edge. Nothing here changes a pick, stake, bar or
the live switch.

  python backtest/darts_score_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import darts_format_study as fmt  # noqa: E402
from backtest import darts_history_study as hist  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_SCORE_STUDY.md"
LEGS = 3
MIN_SCORED = 100
MIN_GAMES = 3


def set_scores(edge: float, sets: int, legs: int = LEGS, hold: float = fmt.HOLD) -> dict[tuple[int, int], float]:
    """Chance of each final set score (a, b) for A, first to `sets` sets; the set starter alternates, coin-toss start."""
    s_first, s_second = fmt.set_win(edge, legs, True, hold), fmt.set_win(edge, legs, False, hold)

    @lru_cache(maxsize=None)
    def go(a: int, b: int, a_th: bool) -> tuple:
        if a == sets or b == sets:
            return (((a, b), 1.0),)
        p = s_first if a_th else s_second
        out: dict[tuple[int, int], float] = {}
        for k, v in go(a + 1, b, not a_th):
            out[k] = out.get(k, 0.0) + p * v
        for k, v in go(a, b + 1, not a_th):
            out[k] = out.get(k, 0.0) + (1.0 - p) * v
        return tuple(out.items())

    tot: dict[tuple[int, int], float] = {}
    for start in (True, False):
        for k, v in go(0, 0, start):
            tot[k] = tot.get(k, 0.0) + 0.5 * v
    return tot


def sets_to_win(games: list[dict]) -> dict[str, int]:
    """Per year-round the largest winner score seen: the round's best-of format."""
    s: dict[str, int] = {}
    for g in games:
        k = g["kickoff_utc"][:7]
        s[k] = max(s.get(k, 0), max(g["home_sets"], g["away_sets"]))
    return s


def _brier(dist: dict[tuple[int, int], float], actual: tuple[int, int]) -> float:
    return sum((v - (1.0 if k == actual else 0.0)) ** 2 for k, v in dist.items())


def walk_forward(games: list[dict], k: float = ms.ELO_K, min_games: int = MIN_GAMES) -> dict:
    need = sets_to_win(games)
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    n = skipped = top_hit = 0
    b_model = b_flat = 0.0
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        s = need[g["kickoff_utc"][:7]]
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            e = None
            if max(g["home_sets"], g["away_sets"]) == s:
                e = fmt._solve(lambda x: fmt.set_match(x, LEGS, s), min(max(p, 0.02), 0.98), fmt.HOLD)
            if e is None:
                skipped += 1
            else:
                act = (g["home_sets"], g["away_sets"])
                d = set_scores(e, s)
                b_model += _brier(d, act)
                b_flat += _brier(set_scores(0.0, s), act)
                top_hit += max(d, key=d.get) == act
                n += 1
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return {"scored": n, "skipped": skipped,
            "model": round(b_model / n, 4) if n else None, "flat": round(b_flat / n, 4) if n else None,
            "top": round(top_hit / n, 4) if n else None}


def verdict(r: dict) -> str:
    if r["scored"] < MIN_SCORED:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    return "beats the format-only baseline" if r["model"] < r["flat"] else "does NOT beat the format-only baseline"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts correct-score study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_score_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_results.py`).", ""])
    r = walk_forward(games)
    pend = "PENDING"
    L += [f"Data: {len(games)} PDC World Championship matches (`data/darts_results.py`). Walk-forward Elo (K "
          f"{ms.ELO_K:g}, each player at least {MIN_GAMES} earlier games) -> win chance -> format model (first to S sets "
          f"of first-to-{LEGS} legs, assumed throw-first hold {fmt.HOLD}) -> chance of every set score. Compared with "
          "the format-only baseline (equal players). Multi-class Brier over the score outcomes, lower is better.", "",
          "| Scored | Skipped | Model Brier | Format-only Brier | Most-likely score hit rate | Verdict |",
          "|---|---|---|---|---|---|",
          f"| {r['scored']} | {r['skipped']} | {r['model'] if r['model'] is not None else pend} | "
          f"{r['flat'] if r['flat'] is not None else pend} | {r['top'] if r['top'] is not None else pend} | "
          f"{verdict(r)} |", "",
          "One try only, nothing tuned. The hold chance and the final-set rule are assumptions (PENDING a grade on the "
          "shadow board). No closing price exists for these matches, so this shows no edge.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(hist.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
