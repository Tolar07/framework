"""
Darts World Championship prior study (framework#341, Week A; record-only). Writes backtest/DARTS_WCPRIOR_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json) and the World Championship results
(data/darts/wc_results.json, ordered but only year-level dated). Idea: the PL field is about 10 players who nearly
all play the Worlds, so a rating that has also learned the Worlds (about 690 matches) may know the players better
than one that learned only the 443 PL matches. Safe order: a World Championship of year Y is held Dec Y-1 / Jan Y,
before the PL of year Y (Feb-May), so PL season Y may use Worlds of year <= Y and nothing later. Each PL match is
scored BEFORE it is learned, with the board's Elo (K, start) either PL-only (w = 0, the board) or Worlds-then-PL
(Worlds steps scaled by w; 1 = full). Only PL matches the board can score (both players >= MIN_GAMES earlier PL
matches) are used, so every w is judged on the same matches. The first half picks w from a grid (every try
counted); the second half is sealed and only judges. Under MIN_SCORED scored matches reads PENDING (HR35). No
price in this source: calibration only, never an edge. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_wcprior_study.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_WCPRIOR_STUDY.md"
WC = ROOT / "data" / "darts" / "wc_results.json"
WEIGHTS = [0.0, 0.25, 0.5, 1.0]
MIN_SCORED = 100


def load_wc(path: Path = WC) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def year_of(g: dict) -> int:
    t = str(g.get("tournament", ""))[:4]
    return int(t) if t.isdigit() else 0


def events(pl: list[dict], wc: list[dict]) -> list[tuple[int, int, str, dict]]:
    """(year, phase, order, game): Worlds of year Y (phase 0) come before the PL of year Y (phase 1)."""
    ev = [(year_of(g), 0, g["kickoff_utc"], g) for g in wc if year_of(g)]
    ev += [(year_of(g), 1, g["kickoff_utc"], g) for g in pl if year_of(g)]
    return sorted(ev, key=lambda e: e[:3])


def scored(pl: list[dict], wc: list[dict], weights: list[float] = WEIGHTS, k: float = ms.ELO_K,
           min_games: int = ms.MIN_GAMES) -> list[dict]:
    """One row per PL match the board can score: {y, p: {w: chance of home}}; earlier matches only."""
    runs: dict[float, dict[str, float]] = {w: {} for w in weights}
    pl_played: dict[str, int] = {}
    out: list[dict] = []
    for _, phase, _, g in events(pl, wc):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        y = 1.0 if g["winner"] == 1 else 0.0
        probs: dict[float, float] = {}
        for w, rating in runs.items():
            rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
            probs[w] = 1 / (1 + 10 ** ((ra - rh) / 400))
            step = k * (1.0 if phase else w)
            rating[h], rating[a] = rh + step * (y - probs[w]), ra - step * (y - probs[w])
        if phase:
            if pl_played.get(h, 0) >= min_games and pl_played.get(a, 0) >= min_games:
                out.append({"y": y, "p": probs})
            pl_played[h], pl_played[a] = pl_played.get(h, 0) + 1, pl_played.get(a, 0) + 1
    return out


def brier(rows: list[dict], w: float) -> float | None:
    return round(sum((r["p"][w] - r["y"]) ** 2 for r in rows) / len(rows), 4) if rows else None


def evaluate(pl: list[dict], wc: list[dict]) -> dict:
    rows = scored(pl, wc)
    n = len(rows)
    first, second = rows[: n // 2], rows[n // 2:]
    table = [{"w": w, "first": brier(first, w), "second": brier(second, w)} for w in WEIGHTS]
    ok = n >= MIN_SCORED
    base = next(r for r in table if r["w"] == 0.0)
    return {"scored": n, "table": table, "best": min(table, key=lambda r: r["first"]) if ok else None,
            "sealed_base": base["second"]}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored matches; has {r['scored']})"
    b = r["best"]
    if b["w"] == 0.0:
        return "the PL-only board was best in the first half: no World Championship lead"
    d = round(r["sealed_base"] - b["second"], 4)
    return (f"w={b['w']:g} picked on the first half; sealed second half Brier {b['second']} vs PL-only "
            f"{r['sealed_base']} ({'better' if d > 0 else 'NOT better'} by {abs(d)}; about {r['scored'] // 2} "
            "matches in the sealed half, so a gap under 0.005 is noise)")


def render(pl: list[dict], wc: list[dict], now: datetime) -> str:
    L = ["# Darts World Championship prior study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_wcprior_study.py` (framework#341). Record only.", ""]
    if not pl or not wc:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py` and "
                              "`python data/darts_results.py`).", ""])
    r = evaluate(pl, wc)
    L += [f"Data: {len(pl)} dated Premier League matches and {len(wc)} World Championship matches (year-level "
          f"dating: the Worlds of year Y only before the PL of year Y). {r['scored']} PL matches scored from earlier "
          f"matches only. w = weight of the World Championship matches in the rating (0 = board, PL only). "
          f"{len(WEIGHTS)} tries, all shown.", "",
          "| w (0 = board) | Brier, first half | Brier, sealed second half |", "|---|---|---|"]
    for row in r["table"]:
        L.append(f"| {row['w']:g} | {row['first'] if row['first'] is not None else 'PENDING'} | "
                 f"{row['second'] if row['second'] is not None else 'PENDING'} |")
    L += ["", f"Verdict: {verdict(r)}", "",
          "A lead to test on new matches, not a change to the Elo. No price here: calibration only.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(load(), load_wc(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
