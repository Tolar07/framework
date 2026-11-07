"""
Darts night-order study (framework#341, Week A; record-only). Writes backtest/DARTS_NIGHT_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). Two ideas, both new:
  1. SLOT: does the player listed first (the "home" slot) win more often than the Elo says?
  2. FATIGUE: on a night of 6-14 matches, a player who has already thrown more matches that night may be weaker.
For each match, in date order, the Elo chance (earlier matches only) is shifted on the logit scale by
  s + f * (matches already thrown tonight by home - by away).
s = 0 and f = 0 is the board. The first half of the scored matches picks (s, f) (s is the first half's own log-odds
gap between the actual home win rate and the mean Elo chance; f from a grid, every try counted); the second half is
sealed and only judges. Under MIN_SCORED matches reads PENDING (HR35). No price in this source: calibration only,
never an edge. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_night_study.py
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

OUT = ROOT / "backtest" / "DARTS_NIGHT_STUDY.md"
FATIGUE = [0.0, 0.05, 0.1, 0.2, 0.4]
MIN_SCORED = 100


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def shifted(p: float, load_gap: float, s: float, f: float) -> float:
    return 1 / (1 + math.exp(-(_logit(p) + s + f * load_gap)))


def scored(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float, float]]:
    """(Elo chance of home, matches home has thrown tonight minus away, home won 0/1), date order, earlier only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    tonight: dict[tuple[str, str], int] = {}
    out: list[tuple[float, float, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        day = g["date"]
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((p, float(tonight.get((day, h), 0) - tonight.get((day, a), 0)), y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
        tonight[(day, h)] = tonight.get((day, h), 0) + 1
        tonight[(day, a)] = tonight.get((day, a), 0) + 1
    return out


def brier(rows: list[tuple[float, float, float]], s: float, f: float) -> float | None:
    return round(sum((shifted(p, d, s, f) - y) ** 2 for p, d, y in rows) / len(rows), 4) if rows else None


def slot_shift(rows: list[tuple[float, float, float]]) -> float:
    """Log-odds gap between the actual home win rate and the mean Elo chance (clipped to +-0.5)."""
    if not rows:
        return 0.0
    rate = sum(y for _, _, y in rows) / len(rows)
    mean_p = sum(p for p, _, _ in rows) / len(rows)
    return round(max(-0.5, min(0.5, _logit(rate) - _logit(mean_p))), 3)


def evaluate(games: list[dict]) -> dict:
    rows = scored(games)
    n = len(rows)
    first, second = rows[: n // 2], rows[n // 2:]
    s = slot_shift(first)
    tries = [(0.0, 0.0)] + [(s, f) for f in FATIGUE]
    table = [{"s": a, "f": b, "first": brier(first, a, b), "second": brier(second, a, b)} for a, b in tries]
    ok = n >= MIN_SCORED
    best = min(table, key=lambda r: r["first"]) if ok else None
    return {"scored": n, "slot": s, "table": table, "best": best,
            "sealed_base": table[0]["second"] if ok else None}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b = r["best"]
    if b["s"] == 0.0 and b["f"] == 0.0:
        return "the board was best in the first half: no slot or fatigue lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"s={b['s']}, f={b['f']} picked on the first half; sealed second half Brier {b['second']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)})")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts night-order study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_night_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from "
          "earlier matches only. Two ideas: the first-listed slot (s), and tiredness on a long night (f per extra "
          f"match already thrown tonight). First-half slot shift s = {r['slot']}. {len(FATIGUE) + 1} tries, all "
          "shown. The first half picks, the second half is sealed and only judges.", "",
          "| s (slot) | f (fatigue) | Brier, first half | Brier, sealed second half |", "|---|---|---|---|"]
    for row in r["table"]:
        tag = " (board)" if row["s"] == 0.0 and row["f"] == 0.0 else ""
        L.append(f"| {row['s']:g}{tag} | {row['f']:g} | {row['first'] if row['first'] is not None else 'PENDING'} | "
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
