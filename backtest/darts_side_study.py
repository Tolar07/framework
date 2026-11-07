"""
Darts first-listed-side study (framework#341, Week A; record-only). Writes backtest/DARTS_SIDE_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). Idea: does the player listed first (home)
win more or less than the Elo says (seed order, walk-on order)? For each match, in date order, the Elo chance
(earlier matches only) is shifted on the logit scale by a constant bias b. b = 0 is the board. The first half of the
scored matches picks b from a grid (every try counted); the second half is sealed and only judges. Under MIN_SCORED
matches reads PENDING (HR35). No price in this source: calibration only, never an edge. Nothing here changes a pick,
stake, bar or the live switch.

  python backtest/darts_side_study.py
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_SIDE_STUDY.md"
BIASES = [-0.3, -0.15, 0.0, 0.15, 0.3]
MIN_SCORED = 100


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def shifted(p: float, b: float) -> float:
    return 1 / (1 + math.exp(-(_logit(p) + b)))


def scored(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float]]:
    """(Elo chance of the first-listed player, he won 0/1), date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    out: list[tuple[float, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((p, y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return out


def brier(rows: list[tuple[float, float]], b: float) -> float | None:
    return round(sum((shifted(p, b) - y) ** 2 for p, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    rows = scored(games)
    half = len(rows) // 2
    first, second = rows[:half], rows[half:]
    table = [{"b": b, "first": brier(first, b), "second": brier(second, b)} for b in BIASES]
    ok = len(rows) >= MIN_SCORED
    best = min(table, key=lambda r: r["first"]) if ok else None
    sealed_base = next(r["second"] for r in table if r["b"] == 0.0) if ok else None
    rate = round(sum(y for _, y in rows) / len(rows), 3) if rows else None
    mean_p = round(sum(p for p, _ in rows) / len(rows), 3) if rows else None
    return {"scored": len(rows), "table": table, "best": best, "sealed_base": sealed_base,
            "first_won": rate, "elo_expected": mean_p}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b = r["best"]
    if b["b"] == 0.0:
        return "the board was best in the first half: no first-listed-side lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"b={b['b']} picked on the first half; sealed second half Brier {b['second']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)})")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts first-listed-side study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_side_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from "
          "earlier matches only. The first-listed player won "
          f"{r['first_won']} of them; the Elo expected {r['elo_expected']}. Idea: a constant bias b (logit) for "
          f"the first-listed player. {len(r['table'])} tries, all shown. The first half picks, the second half is "
          "sealed and only judges.", "",
          "| b (bias) | Brier, first half | Brier, sealed second half |", "|---|---|---|"]
    for row in r["table"]:
        tag = " (board)" if row["b"] == 0.0 else ""
        L.append(f"| {row['b']:g}{tag} | {row['first'] if row['first'] is not None else 'PENDING'} | "
                 f"{row['second'] if row['second'] is not None else 'PENDING'} |")
    L += ["", f"Verdict: {verdict(r)}", "",
          "A lead to test on new matches, not a change to the Elo. A closed field of about 10 players; no price here.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
