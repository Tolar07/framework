"""
Darts between-year rating decay study (framework#341, Week A; record-only). Writes backtest/DARTS_YEAR_DECAY_STUDY.md.

Players change a lot between one World Championship and the next. Does pulling every rating part of the way back to
the starting rating when a new year's championship begins ("shrink") predict later winners better than the plain Elo
the darts shadow board uses (no shrink)? Walk-forward on data/darts/wc_results.json: each match is scored BEFORE it is
learned. Every try is counted and shown. The board setting (shrink 0) is the baseline. No closing price exists, so
this says nothing about edge; a lead is only a lead to confirm on new matches. Nothing here changes a pick, stake,
bar or the live switch. Idea only (standard Elo season carry-over), nothing copied.

  python backtest/darts_year_decay_study.py
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

OUT = ROOT / "backtest" / "DARTS_YEAR_DECAY_STUDY.md"
MIN_SCORED = 100
SHRINKS = [0.0, 0.1, 0.25, 0.5, 0.75]
MIN_GAMES_TRIES = [ms.MIN_GAMES, 3]


def year_of(g: dict) -> str:
    return str(g["kickoff_utc"])[:4]


def walk_forward(games: list[dict], shrink: float, min_games: int, k: float = ms.ELO_K) -> dict:
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    brier = ll = 0.0
    n = hits = 0
    cur = None
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        if cur is not None and year_of(g) != cur and shrink:
            rating = {p: ms.ELO_START + (r - ms.ELO_START) * (1 - shrink) for p, r in rating.items()}
        cur = year_of(g)
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            n += 1
            brier += (p - y) ** 2
            ll += -math.log(min(max(p if y else 1 - p, 1e-6), 1 - 1e-6))
            hits += (p >= 0.5) == (y == 1.0)
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return {"shrink": shrink, "min_games": min_games, "scored": n,
            "brier": round(brier / n, 4) if n else None, "logloss": round(ll / n, 4) if n else None,
            "hit": round(hits / n, 4) if n else None}


def verdict(r: dict, base: dict) -> str:
    if r["scored"] < MIN_SCORED or base["brier"] is None or r["brier"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    if r["shrink"] == 0:
        return "baseline (board, no shrink)"
    return "lead (lower Brier than no shrink)" if r["brier"] < base["brier"] else "no better than no shrink"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts between-year rating decay study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_year_decay_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    years = sorted({year_of(g) for g in games})
    L += [f"Data: {len(games)} PDC World Championship matches over {len(years)} years ({years[0]}-{years[-1]}). Each match is "
          "scored from earlier matches only, then learned. `Shrink` = share of each rating pulled back to the start "
          "rating when a new year's championship begins.", "",
          "No closing price exists for these matches: no edge is shown, only whether the rating predicts winners better.", "",
          f"## Every try counted ({len(SHRINKS) * len(MIN_GAMES_TRIES)})", "",
          "| Shrink | Min games each | Scored | Brier | Log-loss | Favourite hit rate | Verdict |", "|---|---|---|---|---|---|---|"]
    for mg in MIN_GAMES_TRIES:
        base = walk_forward(games, 0.0, mg)
        for s in SHRINKS:
            r = base if s == 0 else walk_forward(games, s, mg)
            f = lambda v: "PENDING" if v is None else v  # noqa: E731
            L.append(f"| {s:g} | {mg} | {r['scored']} | {f(r['brier'])} | {f(r['logloss'])} | {f(r['hit'])} | {verdict(r, base)} |")
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
