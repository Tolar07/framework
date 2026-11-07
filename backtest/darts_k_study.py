"""
Darts Elo K-factor (learning speed) study (framework#341, Week A; record-only). Writes backtest/DARTS_K_STUDY.md.

Does the darts Elo learn at the right speed? K is how far a rating moves after one match. Walk-forward on
data/darts/wc_results.json: each match is scored BEFORE it is learned, with K fixed in advance (no fitting on the
scored match). Every try is counted and shown; the board's K (engine.multisport.ELO_K) is the baseline. No closing price exists, so this says nothing about edge; a lead is only a lead to
confirm on new matches. Nothing here changes a pick, stake, bar or the live switch. Idea only (standard Elo K tuning),
nothing copied.

  python backtest/darts_k_study.py
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

OUT = ROOT / "backtest" / "DARTS_K_STUDY.md"
MIN_SCORED = 100
KS = [8.0, 16.0, ms.ELO_K, 32.0, 48.0]
MIN_GAMES_TRIES = [ms.MIN_GAMES, 3]


def walk_forward(games: list[dict], k: float, min_games: int) -> dict:
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    brier = ll = 0.0
    n = hits = 0
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p_learn = 1 / (1 + 10 ** ((ra - rh) / 400))
        p = p_learn
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            n += 1
            brier += (p - y) ** 2
            ll += -math.log(min(max(p if y else 1 - p, 1e-6), 1 - 1e-6))
            hits += (p >= 0.5) == (y == 1.0)
        rating[h], rating[a] = rh + k * (y - p_learn), ra - k * (y - p_learn)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return {"k": k, "min_games": min_games, "scored": n,
            "brier": round(brier / n, 4) if n else None, "logloss": round(ll / n, 4) if n else None,
            "hit": round(hits / n, 4) if n else None}


def verdict(r: dict, base: dict) -> str:
    if r["scored"] < MIN_SCORED or base["brier"] is None or r["brier"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    if r["k"] == ms.ELO_K:
        return "baseline (board K)"
    return "lead (lower Brier than board K)" if r["brier"] < base["brier"] else "no better than board K"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts Elo K-factor (learning speed) study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_k_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    L += [f"Data: {len(games)} PDC World Championship matches. Each match is scored from earlier matches only, then "
          "learned. `K` is how far a rating moves after one match.", "",
          "No closing price exists for these matches: no edge is shown, only whether a different learning speed predicts winners better.", "",
          f"## Every try counted ({len(KS) * len(MIN_GAMES_TRIES)})", "",
          "| K | Min games each | Scored | Brier | Log-loss | Favourite hit rate | Verdict |", "|---|---|---|---|---|---|---|"]
    for mg in MIN_GAMES_TRIES:
        base = walk_forward(games, ms.ELO_K, mg)
        for k in KS:
            r = base if k == ms.ELO_K else walk_forward(games, k, mg)
            f = lambda v: "PENDING" if v is None else v  # noqa: E731
            L.append(f"| {k:g} | {mg} | {r['scored']} | {f(r['brier'])} | {f(r['logloss'])} | {f(r['hit'])} | {verdict(r, base)} |")
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
