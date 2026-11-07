"""
Darts history study (framework#341, Week A; record-only). Writes backtest/DARTS_HISTORY_STUDY.md.

Uses the dated-by-order PDC World Championship results (data/darts_results.py, Wikipedia brackets 2020-2026, about
690 matches) to ask one question walk-forward: does the Elo that the darts shadow board uses beat a coin flip on
real matches it has not seen? Every game is scored BEFORE it is learned (oldest first). All tries are counted and
shown (min-games rule x K), none hidden; the one the board uses (K=24, min 8 games) is marked. There is no closing
price for these matches, so this is NOT a price backtest: it says nothing about edge, only about whether the rating
carries information. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_history_study.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402

DATA = ROOT / "data" / "darts" / "wc_results.json"
OUT = ROOT / "backtest" / "DARTS_HISTORY_STUDY.md"
COIN = 0.25
MIN_SCORED = 100
TRIES = [(ms.ELO_K, ms.MIN_GAMES), (ms.ELO_K, 3), (ms.ELO_K, 1), (12.0, 1), (40.0, 1)]  # (K, min games)


def walk_forward(games: list[dict], k: float, min_games: int) -> dict:
    """Score each game with the Elo from earlier games only, then learn it."""
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
            q = min(max(p if y else 1 - p, 1e-6), 1 - 1e-6)
            ll += -math.log(q)
            hits += (p >= 0.5) == (y == 1.0)
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return {"k": k, "min_games": min_games, "scored": n,
            "brier": round(brier / n, 4) if n else None, "logloss": round(ll / n, 4) if n else None,
            "hit": round(hits / n, 4) if n else None}


def verdict(r: dict) -> str:
    if not r["scored"] or r["scored"] < MIN_SCORED:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    return "beats coin flip" if r["brier"] < COIN else "does NOT beat coin flip"


def load(path: Path = DATA) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts history study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_history_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_results.py`).", ""])
    years = sorted({g["tournament"] for g in games})
    L += [f"Data: {len(games)} PDC World Championship matches, {len(years)} tournaments "
          f"({years[0][:4]}-{years[-1][:4]}), source Wikipedia brackets (`data/darts_results.py`). Order within a "
          "tournament is round then bracket position; real match dates are not in the source.", "",
          "No closing price exists for these matches, so this is not a price backtest and shows no edge. It asks only "
          f"whether the rating carries information: walk-forward Brier against the coin-flip {COIN}.", "",
          f"## Elo walk-forward, every try counted ({len(TRIES)} tries)", "",
          "| K | Min games each | Scored | Brier | Log-loss | Favourite hit rate | Verdict |", "|---|---|---|---|---|---|---|"]
    for k, mg in TRIES:
        r = walk_forward(games, k, mg)
        used = " (board setting)" if (k, mg) == (ms.ELO_K, ms.MIN_GAMES) else ""
        L.append(f"| {k:g}{used} | {mg} | {r['scored']} | {r['brier'] if r['brier'] is not None else 'PENDING'} | "
                 f"{r['logloss'] if r['logloss'] is not None else 'PENDING'} | "
                 f"{r['hit'] if r['hit'] is not None else 'PENDING'} | {verdict(r)} |")
    L += ["", "A try that looks better than the board setting is a lead to test on new matches, not a change: "
          "picking the best of several tries on the same data flatters it.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None, fetch=None) -> str:
    """Reads the saved results; when none are saved (data/ is not in git) fetches and saves them. A failed
    fetch leaves the study reading NO DATA - PENDING."""
    games = load()
    if not games:
        from data import darts_results
        games = darts_results.fetch_all(get=fetch)
        if games and fetch is None:
            DATA.parent.mkdir(parents=True, exist_ok=True)
            DATA.write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
    text = render(games, now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
