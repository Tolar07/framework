"""
Darts close-last-match study (framework#341, Week A; record-only). Writes backtest/DARTS_CLOSE_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). Idea: a player whose last match was a narrow
win (the winner ahead by at most M legs) may carry confidence, a narrow loss may carry a hangover; a comfortable
result says little. For each match, in date order, the Elo chance (earlier matches only) is shifted on the logit
scale by  w * (carry of home - carry of away),  carry = +1 after a narrow win, -1 after a narrow loss, 0 after a
comfortable result, a draw or no earlier match. w = 0 is the board. The first half of the scored matches picks (M, w)
from a grid (every try counted); the second half is sealed and only judges. Under MIN_SCORED matches reads PENDING
(HR35). No price in this source: calibration only, never an edge. Nothing here changes a pick, stake, bar or the
live switch.

  python backtest/darts_close_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from backtest.darts_form_study import shifted  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_CLOSE_STUDY.md"
MARGINS = [1, 2]
WEIGHTS = [0.0, 0.1, 0.2, 0.4]
MIN_SCORED = 100


def _carry(g: dict, side: int, margin: int) -> int:
    """+1 narrow win, -1 narrow loss, 0 otherwise, for `side` (1 home, 2 away) in finished match g."""
    if g.get("winner") not in (1, 2):
        return 0
    try:
        gap = abs(int(g["home_sets"]) - int(g["away_sets"]))
    except (KeyError, TypeError, ValueError):
        return 0
    if gap > margin:
        return 0
    return 1 if g["winner"] == side else -1


def scored(games: list[dict], margin: int, k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float, float]]:
    """(Elo chance of home, home carry minus away carry, home won 0/1), date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    carry: dict[str, int] = {}
    out: list[tuple[float, float, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((p, float(carry.get(h, 0) - carry.get(a, 0)), y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
        carry[h], carry[a] = _carry(g, 1, margin), _carry(g, 2, margin)
    return out


def brier(rows: list[tuple[float, float, float]], w: float) -> float | None:
    return round(sum((shifted(p, x, w) - y) ** 2 for p, x, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    table = []
    n = len(scored(games, MARGINS[0]))
    for m in MARGINS:
        rows = scored(games, m)
        half = len(rows) // 2
        first, second = rows[:half], rows[half:]
        for w in WEIGHTS:
            table.append({"m": m, "w": w, "first": brier(first, w), "second": brier(second, w)})
    ok = n >= MIN_SCORED
    return {"scored": n, "table": table, "tries": len(table),
            "best": min(table, key=lambda r: r["first"]) if ok else None,
            "sealed_base": next(r["second"] for r in table if r["w"] == 0.0) if ok else None}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b = r["best"]
    if b["w"] == 0.0:
        return "the board was best in the first half: no close-last-match lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"M={b['m']}, w={b['w']} picked on the first half; sealed second half Brier {b['second']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)}; about {r['scored'] // 2} matches "
            "in the sealed half, so a gap under 0.005 is noise)")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts close-last-match study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_close_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from "
          "earlier matches only. Idea: a narrow last result (winner ahead by at most M legs) carries +1 for the winner "
          f"and -1 for the loser into the next match, shifted by weight w. {r['tries']} tries, all shown. The first "
          "half picks, the second half is sealed and only judges.", "",
          "| M (legs) | w | Brier, first half | Brier, sealed second half |", "|---|---|---|---|"]
    for row in r["table"]:
        tag = " (board)" if row["w"] == 0.0 else ""
        L.append(f"| {row['m']} | {row['w']:g}{tag} | {row['first'] if row['first'] is not None else 'PENDING'} | "
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
