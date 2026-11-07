"""
Darts rest-days study (framework#341, Week A; record-only). Writes backtest/DARTS_REST_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). Idea: does the gap since a player's last
Premier League match (a player coming off a long break may be rusty, or fresh) say anything the Elo has not absorbed?
For each match, in date order, the Elo chance (earlier matches only) is shifted on the logit scale by
  w * (rest of home - rest of away) / 7,   rest = days since that player's last match, capped at CAP days
(a player's first match counts as the cap). w = 0 is the board. The first half of the scored matches picks (CAP, w)
from a grid (every try counted); the second half is sealed and only judges. Under MIN_SCORED matches reads PENDING
(HR35). No price in this source: calibration only, never an edge. Nothing here changes a pick, stake, bar or the
live switch.

  python backtest/darts_rest_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from backtest.darts_form_study import shifted  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_REST_STUDY.md"
CAPS = [14, 28]
WEIGHTS = [0.0, 0.05, 0.1, 0.2]
MIN_SCORED = 100


def _day(g: dict) -> date | None:
    try:
        return date.fromisoformat(str(g.get("date", ""))[:10])
    except ValueError:
        return None


def scored(games: list[dict], cap: int, k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, float, float]]:
    """(Elo chance of home, (home rest - away rest) in weeks, home won 0/1), date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    last: dict[str, date] = {}
    out: list[tuple[float, float, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        d = _day(g)
        if d is None:
            continue
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            resth = min((d - last[h]).days, cap) if h in last else cap
            resta = min((d - last[a]).days, cap) if a in last else cap
            out.append((p, (resth - resta) / 7, y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
        last[h], last[a] = d, d
    return out


def brier(rows: list[tuple[float, float, float]], w: float) -> float | None:
    return round(sum((shifted(p, x, w) - y) ** 2 for p, x, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    table = []
    n = len(scored(games, CAPS[0]))
    for cap in CAPS:
        rows = scored(games, cap)
        half = len(rows) // 2
        first, second = rows[:half], rows[half:]
        for w in WEIGHTS:
            table.append({"cap": cap, "w": w, "first": brier(first, w), "second": brier(second, w)})
    ok = n >= MIN_SCORED
    return {"scored": n, "table": table, "best": min(table, key=lambda r: r["first"]) if ok else None,
            "sealed_base": next(r["second"] for r in table if r["w"] == 0.0) if ok else None}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b = r["best"]
    if b["w"] == 0.0:
        return "the board was best in the first half: no rest-days lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"cap={b['cap']}d, w={b['w']} picked on the first half; sealed second half Brier {b['second']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)}; about {r['scored'] // 2} matches "
            "in the sealed half, so a gap under 0.005 is noise)")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts rest-days study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_rest_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from "
          "earlier matches only. Idea: days since each player's last match (capped at CAP days; a first match counts "
          f"as the cap) shift the chance by weight w per week of difference. {len(r['table'])} tries, all shown. The "
          "first half picks, the second half is sealed and only judges.", "",
          "| CAP (days) | w (per week) | Brier, first half | Brier, sealed second half |", "|---|---|---|---|"]
    for row in r["table"]:
        tag = " (board)" if row["w"] == 0.0 else ""
        L.append(f"| {row['cap']} | {row['w']:g}{tag} | {row['first'] if row['first'] is not None else 'PENDING'} | "
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
