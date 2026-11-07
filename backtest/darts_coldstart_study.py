"""
Darts cold-start study (framework#341, Week A; record-only). Writes backtest/DARTS_COLDSTART_STUDY.md.

How much history must a player have before the board's Elo is worth trusting? Walk-forward on
data/darts/wc_results.json (each match scored BEFORE it is learned, board K): matches are bucketed by the games the
LESS-experienced of the two players has already played, and Brier is compared with a coin flip (0.25). This says
whether the board's MIN_GAMES bar is about right. No closing price exists: no edge is shown. Nothing here changes a
pick, stake, bar or the live switch. Idea only (standard Elo cold-start check), nothing copied.

  python backtest/darts_coldstart_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import darts_history_study as hist  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_COLDSTART_STUDY.md"
MIN_BUCKET = 30
BUCKETS = [(0, 0), (1, 2), (3, 5), (6, 10**9)]


def bucket_of(n: int) -> int:
    return next(i for i, (lo, hi) in enumerate(BUCKETS) if lo <= n <= hi)


def walk_forward(games: list[dict], k: float = ms.ELO_K) -> list[dict]:
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    rows = [{"scored": 0, "brier": 0.0, "hits": 0} for _ in BUCKETS]
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        r = rows[bucket_of(min(played.get(h, 0), played.get(a, 0)))]
        r["scored"] += 1
        r["brier"] += (p - y) ** 2
        r["hits"] += (p >= 0.5) == (y == 1.0)
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return rows


def verdict(n: int, brier: float | None) -> str:
    if n < MIN_BUCKET or brier is None:
        return f"PENDING (needs {MIN_BUCKET}, has {n})"
    return "beats a coin flip" if brier < 0.25 else "no better than a coin flip"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts cold-start study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_coldstart_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    rows = walk_forward(games)
    L += [f"Data: {len(games)} PDC World Championship matches, board K {ms.ELO_K:g}, board MIN_GAMES {ms.MIN_GAMES}. "
          "Bucket = games already played by the less-experienced player.", "",
          f"## Accuracy by experience ({len(BUCKETS)} buckets, all shown)", "",
          "| Games played by the newer player | Matches | Brier (coin flip 0.25) | Favourite hit rate | Verdict |",
          "|---|---|---|---|---|"]
    for (lo, hi), r in zip(BUCKETS, rows):
        n = r["scored"]
        b = round(r["brier"] / n, 4) if n else None
        hit = round(r["hits"] / n, 4) if n else None
        label = f"{lo}+" if hi >= 10**9 else (str(lo) if lo == hi else f"{lo}-{hi}")
        L.append(f"| {label} | {n} | {'PENDING' if b is None else b} | {'PENDING' if hit is None else hit} | {verdict(n, b)} |")
    L += ["", "Read it as: if the low buckets are no better than a coin flip, the board's MIN_GAMES bar is right to skip them; "
          "if they already beat it, the bar may be too strict. Only a lead: confirm on new matches before proposing anything.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(hist.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
