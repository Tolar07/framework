"""
Darts dated calibration study (framework#341, Week A; record-only). Writes backtest/DARTS_DATED_CALIBRATION_STUDY.md.

On the dated Premier League results (data/darts/pl_results.json) the board's Elo is run walk-forward in date order.
Each scored match gives two sides (home, away) with the Elo's chance before the match. Sides are grouped by that
chance and compared with how often they really won. A band with under 30 sides reads PENDING (HR35). No price is in
this source, so this shows calibration only, never an edge. Nothing here changes a pick, stake, bar or live switch.

  python backtest/darts_dated_calibration_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_DATED_CALIBRATION_STUDY.md"
BANDS = [(0.0, 0.40), (0.40, 0.50), (0.50, 0.60), (0.60, 1.0001)]
MIN_SIDES = 30


def sides(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, int]]:
    """(Elo chance, won 0/1) for both sides of each match, scored from earlier games only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    out: list[tuple[float, int]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1 if g["winner"] == 1 else 0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out += [(p, y), (1 - p, 1 - y)]
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return out


def bands(rows: list[tuple[float, int]]) -> list[dict]:
    res = []
    for lo, hi in BANDS:
        sel = [(p, y) for p, y in rows if lo <= p < hi]
        n = len(sel)
        ok = n >= MIN_SIDES
        res.append({"band": f"{lo:.2f}-{min(hi, 1.0):.2f}", "n": n, "won": sum(y for _, y in sel),
                    "said": round(sum(p for p, _ in sel) / n, 3) if ok else None,
                    "actual": round(sum(y for _, y in sel) / n, 3) if ok else None})
    return res


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts dated calibration study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_dated_calibration_study.py` (framework#341). Record only.", ""]
    rows = sides(games)
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    L += [f"Data: {len(games)} dated Premier League Darts matches, {len(rows)} scored sides (two per match) with the "
          "board's Elo from earlier matches only. When the Elo says a side has X, does it win about X of the time? "
          f"No price is in this source, so this is calibration only, not an edge. Bands under {MIN_SIDES} sides read PENDING.",
          "", "| Elo chance band | Sides | Won | Elo said | Actual |", "|---|---|---|---|---|"]
    for b in bands(rows):
        L.append(f"| {b['band']} | {b['n']} | {b['won']} | {b['said'] if b['said'] is not None else 'PENDING'} | "
                 f"{b['actual'] if b['actual'] is not None else 'PENDING'} |")
    L += ["", "A gap here is a lead to test on new matches, not a change to the Elo.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
