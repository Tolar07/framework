"""
Darts dated study (framework#341, Week A; record-only). Writes backtest/DARTS_DATED_STUDY.md.

First darts results with REAL match dates (data/darts_pl_results.py: Premier League Darts nights 2023-2026). Asks
walk-forward, in true date order, whether the board's Elo beats a coin flip, season by season, with every try
(K x min games) counted. Ratings carry over between seasons. No closing price exists in this source, so this is NOT
a price backtest and shows no edge; it unblocks the date axis only. Nothing here changes a pick, stake, bar or the
live switch.

  python backtest/darts_dated_study.py
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

DATA = ROOT / "data" / "darts" / "pl_results.json"
OUT = ROOT / "backtest" / "DARTS_DATED_STUDY.md"
COIN = 0.25
MIN_SCORED = 100
TRIES = [(ms.ELO_K, ms.MIN_GAMES), (ms.ELO_K, 3), (ms.ELO_K, 1), (12.0, 1), (40.0, 1)]


def walk_forward(games: list[dict], k: float, min_games: int) -> dict:
    """Score each game (oldest date first) with the Elo from earlier games only, then learn it. Per-season Brier."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    per: dict[str, list[float]] = {}
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            per.setdefault(g["date"][:4], []).append((p - y) ** 2)
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    allb = [b for v in per.values() for b in v]
    return {"k": k, "min_games": min_games, "scored": len(allb),
            "brier": round(sum(allb) / len(allb), 4) if allb else None,
            "by_year": {y: (len(v), round(sum(v) / len(v), 4)) for y, v in sorted(per.items())}}


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
    L = ["# Darts dated study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_dated_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    days = sorted({g["date"] for g in games})
    L += [f"Data: {len(games)} Premier League Darts matches on {len(days)} real dates ({days[0]} to {days[-1]}), "
          "source Wikipedia season pages (`data/darts_pl_results.py`). A closed field of about 10 players, so ratings "
          "firm up fast; it is not the whole PDC tour.", "",
          "No closing price exists in this source, so this is not a price backtest and shows no edge. It asks only "
          f"whether the rating carries information: walk-forward Brier against the coin-flip {COIN}.", "",
          f"## Elo walk-forward in date order, every try counted ({len(TRIES)} tries)", "",
          "| K | Min games each | Scored | Brier | By season (n, Brier) | Verdict |", "|---|---|---|---|---|---|"]
    for k, mg in TRIES:
        r = walk_forward(games, k, mg)
        used = " (board setting)" if (k, mg) == (ms.ELO_K, ms.MIN_GAMES) else ""
        yrs = "; ".join(f"{y}: {n}, {b}" for y, (n, b) in r["by_year"].items()) or "PENDING"
        L.append(f"| {k:g}{used} | {mg} | {r['scored']} | {r['brier'] if r['brier'] is not None else 'PENDING'} | "
                 f"{yrs} | {verdict(r)} |")
    L += ["", "A try that looks better than the board setting is a lead to test on new matches, not a change.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None, fetch=None) -> str:
    """Reads saved results; when none are saved (data/ is not in git) fetches and saves them."""
    games = load()
    if not games:
        from data import darts_pl_results
        games = darts_pl_results.fetch_all(get=fetch)
        if games and fetch is None:
            DATA.parent.mkdir(parents=True, exist_ok=True)
            DATA.write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
    text = render(games, now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
