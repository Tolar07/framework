"""
Darts format-length underdog study (framework#341, Week A; record-only). Writes backtest/DARTS_FORMAT_UNDERDOG_STUDY.md.

Idea from a practitioner video (Action Network, https://www.youtube.com/watch?v=5laezeG01F8 @ 04:09, said only, no
numbers on screen): underdogs "bark" in short formats and less in long ones, because a longer match lets the better
player's edge show. Walk-forward test on data/darts/wc_results.json: every match is scored with the board Elo BEFORE it
is learned, then bucketed by how many sets the winner needed (first-to-N, a format-length proxy). For each bucket the
table shows the underdog's Elo-implied chance beside the underdog's actual win rate. No closing price exists: no edge is
claimed. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_format_underdog_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import darts_history_study as hist  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_FORMAT_UNDERDOG_STUDY.md"
MIN_BUCKET = 30
BUCKETS = [(1, 3), (4, 4), (5, 5), (6, 10**9)]  # winner's sets: first-to-N


def bucket_of(n: int) -> int | None:
    return next((i for i, (lo, hi) in enumerate(BUCKETS) if lo <= n <= hi), None)


def walk_forward(games: list[dict], k: float = ms.ELO_K) -> list[dict]:
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    rows = [{"n": 0, "implied": 0.0, "won": 0} for _ in BUCKETS]
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        b = bucket_of(max(int(g["home_sets"]), int(g["away_sets"])))
        # only matches the board would rate (both players known) count, so cold starts do not blur the question
        if b is not None and played.get(h, 0) >= ms.MIN_GAMES and played.get(a, 0) >= ms.MIN_GAMES and p != 0.5:
            dog_p = min(p, 1 - p)
            dog_won = (y == 1.0) if p < 0.5 else (y == 0.0)
            rows[b]["n"] += 1
            rows[b]["implied"] += dog_p
            rows[b]["won"] += bool(dog_won)
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return rows


def verdict(n: int, implied: float | None, actual: float | None) -> str:
    if n < MIN_BUCKET or implied is None or actual is None:
        return f"PENDING (needs {MIN_BUCKET}, has {n})"
    gap = actual - implied
    if abs(gap) < 0.03:
        return "underdogs win about as often as Elo says"
    return "underdogs win MORE than Elo says" if gap > 0 else "underdogs win LESS than Elo says"


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts format-length underdog study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_format_underdog_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    rows = walk_forward(games)
    L += [f"Data: {len(games)} PDC World Championship matches, board K {ms.ELO_K:g}; only matches where both players "
          f"already had {ms.MIN_GAMES}+ games count. Idea: Action Network @ 04:09 (said only).", "",
          f"## Underdog win rate by match length ({len(BUCKETS)} buckets, all shown)", "",
          "| Winner needed (sets) | Matches | Underdog Elo chance | Underdog actual | Verdict |", "|---|---|---|---|---|"]
    for (lo, hi), r in zip(BUCKETS, rows, strict=True):
        n = r["n"]
        imp = round(r["implied"] / n, 4) if n else None
        act = round(r["won"] / n, 4) if n else None
        label = f"{lo}+" if hi >= 10**9 else (str(lo) if lo == hi else f"up to {hi}")
        L.append(f"| {label} | {n} | {'PENDING' if imp is None else imp} | {'PENDING' if act is None else act} | "
                 f"{verdict(n, imp, act)} |")
    L += ["", "Read it as: if short matches show underdogs winning MORE than Elo says and long ones LESS, a length term "
          "may be worth a shadow candidate next to the price. Only a lead: confirm on new matches before proposing anything.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(hist.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
