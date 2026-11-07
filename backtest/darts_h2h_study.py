"""
Darts head-to-head study (framework#341, Week A; record-only). Writes backtest/DARTS_H2H_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). The field is a closed group of about ten
players who meet again and again, so the pair's own earlier record may say something the Elo does not. For each
match, in date order, the Elo chance (from earlier matches only) is nudged on the logit scale by
b * (earlier wins of home - earlier wins of away) / (earlier meetings + SHRINK). b = 0 is the board. The first half
of the scored matches picks b, the second half is sealed and only judges. Every try is counted. Under MIN_SCORED
matches reads PENDING (HR35). No price is in this source: calibration only, never an edge. Nothing here changes a
pick, stake, bar or the live switch.

  python backtest/darts_h2h_study.py
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

OUT = ROOT / "backtest" / "DARTS_H2H_STUDY.md"
WEIGHTS = [0.0, 0.25, 0.5, 1.0, 1.5]
SHRINK = 4.0
MIN_SCORED = 100


def nudge(p: float, h2h: float, b: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return 1 / (1 + math.exp(-(math.log(p / (1 - p)) + b * h2h)))


def scored(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float, float]]:
    """(Elo chance of home, shrunk head-to-head score for home, home won 0/1), date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    meet: dict[tuple[str, str], list[int]] = {}
    out: list[tuple[float, float, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        key = tuple(sorted((h, a)))
        w = meet.setdefault(key, [0, 0])
        hw, aw = (w[0], w[1]) if key[0] == h else (w[1], w[0])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((p, (hw - aw) / (hw + aw + SHRINK), y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
        winner = h if y else a
        w[0 if key[0] == winner else 1] += 1
    return out


def brier(rows: list[tuple[float, float, float]], b: float) -> float | None:
    return round(sum((nudge(p, d, b) - y) ** 2 for p, d, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    rows = scored(games)
    n = len(rows)
    first, second = rows[: n // 2], rows[n // 2:]
    table = [{"b": b, "first": brier(first, b), "second": brier(second, b)} for b in WEIGHTS]
    ok = n >= MIN_SCORED
    best = min(table, key=lambda r: r["first"]) if ok else None
    return {"scored": n, "table": table, "best_b": best["b"] if best else None,
            "sealed_best": best["second"] if best else None, "sealed_base": table[0]["second"] if ok else None}


def verdict(r: dict) -> str:
    if r["best_b"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    if r["best_b"] == 0.0:
        return "b=0 (the board) was best in the first half: no head-to-head lead"
    d = round(r["sealed_base"] - r["sealed_best"], 4)
    return (f"b={r['best_b']} picked on the first half; sealed second half Brier {r['sealed_best']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)})")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts head-to-head study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_h2h_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo and the "
          "pair's earlier record only. Does the pair's own head-to-head add to the Elo? "
          f"{len(WEIGHTS)} weights tried, all shown. The first half picks the weight, the second half is sealed "
          "and only judges.", "",
          "| Weight b | Brier, first half | Brier, sealed second half |", "|---|---|---|"]
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
