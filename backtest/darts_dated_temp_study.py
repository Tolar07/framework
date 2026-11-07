"""
Darts dated temperature study (framework#341, Week A; record-only). Writes backtest/DARTS_DATED_TEMP_STUDY.md.

The dated calibration study found the board's Elo slightly over-confident. This is a SHADOW: on the dated Premier
League results (data/darts/pl_results.json), in date order, each match is scored with the raw Elo chance and with a
shrunk chance (logit divided by a temperature T), the Elo coming only from earlier matches. Walk-forward Brier of each
T is compared with T=1 (the board). The first half of the scored matches picks the best T; the second half (sealed,
never used to pick) is where it is judged. Every try is counted. Under MIN_SCORED matches reads PENDING (HR35).
No price is in this source: this is calibration only, never an edge. Nothing here changes a pick, stake, bar or the
live switch.

  python backtest/darts_dated_temp_study.py
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

OUT = ROOT / "backtest" / "DARTS_DATED_TEMP_STUDY.md"
TEMPS = [1.0, 1.1, 1.2, 1.35, 1.5, 2.0]
MIN_SCORED = 100


def temper(p: float, t: float) -> float:
    """Shrink a chance toward 0.5: logit / t. t=1 returns p."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return 1 / (1 + math.exp(-math.log(p / (1 - p)) / t))


def scored(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float]]:
    """(Elo chance of home, home won 0/1) per match, date order, Elo from earlier matches only."""
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


def brier(rows: list[tuple[float, float]], t: float) -> float | None:
    return round(sum((temper(p, t) - y) ** 2 for p, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    rows = scored(games)
    n = len(rows)
    half = n // 2
    first, second = rows[:half], rows[half:]
    table = [{"t": t, "first": brier(first, t), "second": brier(second, t)} for t in TEMPS]
    ok = n >= MIN_SCORED
    best = min(table, key=lambda r: r["first"]) if ok else None
    base = table[0]
    return {"scored": n, "table": table, "best_t": best["t"] if best else None,
            "sealed_best": best["second"] if best else None, "sealed_base": base["second"] if ok else None}


def verdict(r: dict) -> str:
    if r["best_t"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    if r["best_t"] == 1.0:
        return "T=1 (the board) was best in the first half: no shrink lead"
    d = round(r["sealed_base"] - r["sealed_best"], 4)
    return (f"T={r['best_t']} picked on the first half; sealed second half Brier {r['sealed_best']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)})")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts dated temperature study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_dated_temp_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from earlier "
          "matches only. The dated calibration study found the Elo slightly over-confident; does shrinking it toward "
          f"50% (logit / T) lower the Brier? {len(TEMPS)} temperatures tried, all shown. The first half picks T, the "
          "second half is sealed and only judges.", "",
          "| T | Brier, first half | Brier, sealed second half |", "|---|---|---|"]
    for row in r["table"]:
        tag = " (board)" if row["t"] == 1.0 else ""
        L.append(f"| {row['t']:g}{tag} | {row['first'] if row['first'] is not None else 'PENDING'} | "
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
