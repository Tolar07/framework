"""
Darts margin-aware Elo study (framework#341, Week A; record-only). Writes backtest/DARTS_MARGIN_ELO_STUDY.md.

Does an Elo that learns from HOW MUCH a player won by (sets share, or a K scaled by the set margin) predict later
World Championship winners better than the plain win/loss Elo the darts shadow board uses? Walk-forward on the
dated-by-order PDC World Championship results (data/darts/wc_results.json): every match is scored BEFORE it is
learned. All tries are counted and shown, none hidden. The board setting (plain Elo, K=24, min 8 games) is the
baseline and is marked. No closing price exists, so this says nothing about edge. A try that beats the baseline is a
lead to test on new matches, not a change: nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_margin_elo_study.py
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

OUT = ROOT / "backtest" / "DARTS_MARGIN_ELO_STUDY.md"
MIN_SCORED = 100
BASE = ("plain", ms.ELO_K, ms.MIN_GAMES)
TRIES = [BASE, ("plain", ms.ELO_K, 3),
         ("share", ms.ELO_K, ms.MIN_GAMES), ("share", ms.ELO_K, 3),
         ("margin_k", ms.ELO_K, ms.MIN_GAMES), ("margin_k", ms.ELO_K, 3),
         ("share", 40.0, 3), ("margin_k", 12.0, 3)]


def target(g: dict, mode: str) -> tuple[float, float]:
    """(learning target for the home player in 0..1, K multiplier) from the set score. Missing scores fall back to win/loss."""
    y = 1.0 if g["winner"] == 1 else 0.0
    hs, as_ = g.get("home_sets"), g.get("away_sets")
    if mode == "plain" or not isinstance(hs, int) or not isinstance(as_, int) or hs + as_ <= 0:
        return y, 1.0
    if mode == "share":
        return hs / (hs + as_), 1.0
    return y, math.log(abs(hs - as_) + 1) + 1.0  # margin_k: bigger wins move the rating more


def walk_forward(games: list[dict], mode: str, k: float, min_games: int) -> dict:
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    brier = ll = 0.0
    n = hits = 0
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            n += 1
            brier += (p - y) ** 2
            ll += -math.log(min(max(p if y else 1 - p, 1e-6), 1 - 1e-6))
            hits += (p >= 0.5) == (y == 1.0)
        t, mult = target(g, mode)
        rating[h], rating[a] = rh + k * mult * (t - p), ra - k * mult * (t - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return {"mode": mode, "k": k, "min_games": min_games, "scored": n,
            "brier": round(brier / n, 4) if n else None, "logloss": round(ll / n, 4) if n else None,
            "hit": round(hits / n, 4) if n else None}


def verdict(r: dict, base: dict) -> str:
    if r["scored"] < MIN_SCORED or base["brier"] is None or r["brier"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    if (r["mode"], r["k"]) == ("plain", ms.ELO_K):
        return "baseline (board K)"
    return "lead (lower Brier than plain Elo)" if r["brier"] < base["brier"] else "no better than plain Elo"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts margin-aware Elo study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_margin_elo_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    L += [f"Data: {len(games)} PDC World Championship matches (Wikipedia brackets, `data/darts_results.py`). Each match is "
          "scored from earlier matches only, then learned. `plain` = win/loss (the board); `share` = learn from the share "
          "of sets won; `margin_k` = win/loss but K scaled by 1 + ln(set margin + 1).", "",
          "No closing price exists for these matches: no edge is shown, only whether the rating predicts winners better.", "",
          f"## Every try counted ({len(TRIES)})", "",
          "| Learns from | K | Min games each | Scored | Brier | Log-loss | Favourite hit rate | Verdict |",
          "|---|---|---|---|---|---|---|---|"]
    bases = {mg: walk_forward(games, "plain", ms.ELO_K, mg) for mg in {t[2] for t in TRIES}}
    for mode, k, mg in TRIES:
        base = bases[mg]  # same min-games rule, so both score the same matches
        r = base if (mode, k, mg) == ("plain", ms.ELO_K, mg) else walk_forward(games, mode, k, mg)
        f = lambda v: "PENDING" if v is None else v  # noqa: E731
        L.append(f"| {mode} | {k:g} | {mg} | {r['scored']} | {f(r['brier'])} | {f(r['logloss'])} | {f(r['hit'])} | {verdict(r, base)} |")
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
