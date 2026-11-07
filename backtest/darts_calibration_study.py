"""
Darts Elo calibration (temperature) study (framework#341, Week A; record-only). Writes backtest/DARTS_CALIBRATION_STUDY.md.

Is the darts Elo too sure of itself, or not sure enough? A temperature T stretches (T>1) or squeezes (T<1) the rating
gap before it becomes a win chance: p = 1 / (1 + 10 ** (-T * gap / 400)). Walk-forward on data/darts/wc_results.json:
each match is scored BEFORE it is learned, with T fixed in advance (no fitting on the scored match). Ratings still
learn from the plain Elo chance (the board rule), so only the shown probability changes. Every try is counted and
shown; T=1 is the board baseline. No closing price exists, so this says nothing about edge; a lead is only a lead to
confirm on new matches. Nothing here changes a pick, stake, bar or the live switch. Idea only (standard temperature
scaling), nothing copied.

  python backtest/darts_calibration_study.py
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import darts_history_study as hist  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_CALIBRATION_STUDY.md"
MIN_SCORED = 100
TEMPS = [0.5, 0.75, 1.0, 1.5, 2.0]
MIN_GAMES_TRIES = [ms.MIN_GAMES, 3]


def walk_forward(games: list[dict], temp: float, min_games: int, k: float = ms.ELO_K) -> dict:
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    brier = ll = 0.0
    n = hits = 0
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p_learn = 1 / (1 + 10 ** ((ra - rh) / 400))
        p = 1 / (1 + 10 ** (-temp * (rh - ra) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            n += 1
            brier += (p - y) ** 2
            ll += -math.log(min(max(p if y else 1 - p, 1e-6), 1 - 1e-6))
            hits += (p >= 0.5) == (y == 1.0)
        rating[h], rating[a] = rh + k * (y - p_learn), ra - k * (y - p_learn)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return {"temp": temp, "min_games": min_games, "scored": n,
            "brier": round(brier / n, 4) if n else None, "logloss": round(ll / n, 4) if n else None,
            "hit": round(hits / n, 4) if n else None}


def verdict(r: dict, base: dict) -> str:
    if r["scored"] < MIN_SCORED or base["brier"] is None or r["brier"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    if r["temp"] == 1.0:
        return "baseline (board, T=1)"
    return "lead (lower Brier than T=1)" if r["brier"] < base["brier"] else "no better than T=1"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts Elo calibration (temperature) study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_calibration_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    L += [f"Data: {len(games)} PDC World Championship matches. Each match is scored from earlier matches only, then "
          "learned. `T` stretches (above 1) or squeezes (below 1) the rating gap before it becomes a win chance; "
          "ratings still learn from the plain Elo chance.", "",
          "No closing price exists for these matches: no edge is shown, only whether the stated chances are better calibrated.", "",
          f"## Every try counted ({len(TEMPS) * len(MIN_GAMES_TRIES)})", "",
          "| T | Min games each | Scored | Brier | Log-loss | Favourite hit rate | Verdict |", "|---|---|---|---|---|---|---|"]
    for mg in MIN_GAMES_TRIES:
        base = walk_forward(games, 1.0, mg)
        for t in TEMPS:
            r = base if t == 1.0 else walk_forward(games, t, mg)
            f = lambda v: "PENDING" if v is None else v  # noqa: E731
            L.append(f"| {t:g} | {mg} | {r['scored']} | {f(r['brier'])} | {f(r['logloss'])} | {f(r['hit'])} | {verdict(r, base)} |")
    L += ["", "Picking the best of several tries on the same matches flatters it; a lead needs confirming on new matches "
          "(the live shadow board) before it is even proposed to the Architect.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(hist.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
