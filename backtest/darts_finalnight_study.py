"""
Darts final-night study (framework#341, Week A; record-only). Writes backtest/DARTS_FINALNIGHT_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json). Idea: the last night of each Premier League
(the play-offs, knock-out matches under pressure) may be more or less predictable than the league nights. On that
night only, the Elo chance (earlier matches only) is stretched or squeezed on the logit scale by a factor c
(c = 1 is the board; c < 1 pulls towards 50-50, c > 1 pushes towards the favourite). The first half of the scored
matches picks c from a grid (every try counted); the second half is sealed and only judges. Under MIN_SCORED
scored matches, or under MIN_FINAL final-night matches in the first half, reads PENDING (HR35). No price in this
source: calibration only, never an edge. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_finalnight_study.py
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_FINALNIGHT_STUDY.md"
FACTORS = [0.5, 0.75, 1.0, 1.25, 1.5]
MIN_SCORED = 100
MIN_FINAL = 8


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def shifted(p: float, final: bool, c: float) -> float:
    """c scales the logit on a final night only; league nights are untouched."""
    return 1 / (1 + math.exp(-_logit(p) * (c if final else 1.0)))


def last_nights(games: list[dict]) -> set[tuple[str, str]]:
    """(tournament, date) of each tournament's last night."""
    last: dict[str, str] = {}
    for g in games:
        t = g.get("tournament", "")
        last[t] = max(last.get(t, ""), g["date"])
    return set(last.items())


def scored(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, bool, float]]:
    """(Elo chance of home, is final night, home won 0/1), date order, earlier matches only."""
    finals = last_nights(games)
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    out: list[tuple[float, bool, float]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((p, (g.get("tournament", ""), g["date"]) in finals, y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return out


def brier(rows: list[tuple[float, bool, float]], c: float) -> float | None:
    return round(sum((shifted(p, f, c) - y) ** 2 for p, f, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    rows = scored(games)
    n = len(rows)
    first, second = rows[: n // 2], rows[n // 2:]
    nf1, nf2 = sum(1 for r in first if r[1]), sum(1 for r in second if r[1])
    table = [{"c": c, "first": brier(first, c), "second": brier(second, c)} for c in FACTORS]
    ok = n >= MIN_SCORED and nf1 >= MIN_FINAL
    base = next(r for r in table if r["c"] == 1.0)
    return {"scored": n, "final_first": nf1, "final_second": nf2, "table": table,
            "best": min(table, key=lambda r: r["first"]) if ok else None, "sealed_base": base["second"]}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return (f"PENDING (needs {MIN_SCORED} scored and {MIN_FINAL} final-night matches in the first half; "
                f"has {r['scored']} and {r['final_first']})")
    b = r["best"]
    if b["c"] == 1.0:
        return "the board was best in the first half: no final-night lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"c={b['c']:g} picked on the first half; sealed second half Brier {b['second']} vs board "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)}; only {r['final_second']} "
            "final-night matches are in the second half, so this is noise-level)")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts final-night study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_finalnight_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    L += [f"Data: {len(games)} dated Premier League Darts matches, {r['scored']} scored with the board's Elo from "
          f"earlier matches only; {r['final_first']} final-night matches in the first half, {r['final_second']} in "
          f"the sealed second half. On each season's last night (the play-offs) the Elo is stretched or squeezed by "
          f"c. {len(FACTORS)} tries, all shown.", "",
          "| c (1 = board) | Brier, first half | Brier, sealed second half |", "|---|---|---|"]
    for row in r["table"]:
        L.append(f"| {row['c']:g} | {row['first'] if row['first'] is not None else 'PENDING'} | "
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
