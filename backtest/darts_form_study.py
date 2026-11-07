"""
Darts recent-form study (framework#341, Week A; record-only). Writes backtest/DARTS_FORM_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). Idea: does a player's recent surprise
(wins minus what the Elo expected, over his last N matches) say anything the Elo has not yet absorbed? For each match,
in date order, the Elo chance (earlier matches only) is shifted on the logit scale by
  w * (surprise of home over his last N - surprise of away over his last N).
w = 0 is the board. The first half of the scored matches picks (N, w) from a grid (every try counted); the second half
is sealed and only judges. Under MIN_SCORED matches reads PENDING (HR35). No price in this source: calibration only,
never an edge. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_form_study.py
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

OUT = ROOT / "backtest" / "DARTS_FORM_STUDY.md"
WINDOWS = [3, 5, 8]
WEIGHTS = [0.0, 0.1, 0.25, 0.5]
MIN_SCORED = 100


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def shifted(p: float, gap: float, w: float) -> float:
    return 1 / (1 + math.exp(-(_logit(p) + w * gap)))


def scored(games: list[dict], n: int, k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float, float]]:
    """(Elo chance of home, home recent surprise minus away's, home won 0/1), date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    surprise: dict[str, list[float]] = {}
    out: list[tuple[float, float, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            fh = sum(surprise.get(h, [])[-n:])
            fa = sum(surprise.get(a, [])[-n:])
            out.append((p, fh - fa, y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
        surprise.setdefault(h, []).append(y - p)
        surprise.setdefault(a, []).append((1 - y) - (1 - p))
    return out


def brier(rows: list[tuple[float, float, float]], w: float) -> float | None:
    return round(sum((shifted(p, d, w) - y) ** 2 for p, d, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    table = []
    base_n = len(scored(games, WINDOWS[0]))
    for n in WINDOWS:
        rows = scored(games, n)
        half = len(rows) // 2
        first, second = rows[:half], rows[half:]
        for w in WEIGHTS:
            table.append({"n": n, "w": w, "first": brier(first, w), "second": brier(second, w)})
    ok = base_n >= MIN_SCORED
    best = min(table, key=lambda r: r["first"]) if ok else None
    sealed_base = next(r["second"] for r in table if r["w"] == 0.0) if ok else None
    return {"scored": base_n, "table": table, "best": best, "sealed_base": sealed_base}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b = r["best"]
    if b["w"] == 0.0:
        return "the board was best in the first half: no recent-form lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"N={b['n']}, w={b['w']} picked on the first half; sealed second half Brier {b['second']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)})")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts recent-form study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_form_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from "
          "earlier matches only. Idea: a player's wins minus what the Elo expected over his last N matches (N) moves "
          f"the chance by weight w. {len(r['table'])} tries, all shown. The first half picks, the second half is "
          "sealed and only judges.", "",
          "| N (matches) | w (weight) | Brier, first half | Brier, sealed second half |", "|---|---|---|---|"]
    for row in r["table"]:
        tag = " (board)" if row["w"] == 0.0 else ""
        L.append(f"| {row['n']} | {row['w']:g}{tag} | {row['first'] if row['first'] is not None else 'PENDING'} | "
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
