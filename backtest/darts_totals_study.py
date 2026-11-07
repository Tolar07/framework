"""
Darts total-legs study (framework#341, Week A; record-only). Writes backtest/DARTS_TOTALS_STUDY.md.

SHADOW on the dated Premier League results (data/darts/pl_results.json; every match is first to 6 legs, so total
legs run 6..11). For each match, in date order, the board's Elo (earlier matches only) gives a win chance; the
format model (backtest/darts_format_study.py price_legs) turns it into Over 7.5 / 8.5 / 9.5 / 10.5 total-legs
chances. Judged by Brier against what happened, versus an equal-players baseline (p = 0.5) and the plain base
rate of the first half. The throw-first leg chance ("hold", an assumption) is tried on a grid (every try shown):
the first half picks, the second half is sealed and only judges. Under MIN_SCORED matches reads PENDING (HR35).
No price in this source: calibration only, never an edge. Nothing here changes a pick, stake, bar or live switch.

  python backtest/darts_totals_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import darts_format_study as fmt  # noqa: E402
from backtest.darts_dated_study import load  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_TOTALS_STUDY.md"
LEGS = 6
LINES = [7.5, 8.5, 9.5, 10.5]
HOLDS = [0.50, 0.55, 0.60, 0.65]
MIN_SCORED = 100


def rows_of(games: list[dict], k: float = ms.ELO_K, min_games: int = ms.MIN_GAMES) -> list[tuple[float, int]]:
    """(Elo chance of first-listed player, total legs played), date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    out: list[tuple[float, int]] = []
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((p, int(g["home_sets"]) + int(g["away_sets"])))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return out


def over_chances(p: float, hold: float) -> dict[float, float] | None:
    r = fmt.price_legs(min(max(p, 0.01), 0.99), LEGS, hold)
    return r["over"] if r else None


def brier(rows: list[tuple[float, int]], hold: float | None, base: dict[float, float] | None = None) -> float | None:
    """Mean Brier over the lines. hold None -> `base` (flat base rates); else the format model on the Elo."""
    tot, n = 0.0, 0
    for p, total in rows:
        ov = over_chances(p, hold) if hold is not None else base
        if ov is None:
            continue
        for ln in LINES:
            tot += (ov[ln] - (1.0 if total > ln else 0.0)) ** 2
            n += 1
    return round(tot / n, 4) if n else None


def evaluate(games: list[dict]) -> dict:
    rows = rows_of(games)
    half = len(rows) // 2
    first, second = rows[:half], rows[half:]
    ok = len(rows) >= MIN_SCORED
    base = {ln: sum(1 for _, t in first if t > ln) / len(first) for ln in LINES} if first else None
    rate = {ln: round(sum(1 for _, t in rows if t > ln) / len(rows), 3) for ln in LINES} if rows else {}
    table = [{"hold": h, "first": brier(first, h), "second": brier(second, h)} for h in HOLDS] if ok else []
    flat = {"first": brier(first, None, base), "second": brier(second, None, base)} if ok else None
    even = ({"first": brier([(0.5, t) for _, t in first], fmt.HOLD),
             "second": brier([(0.5, t) for _, t in second], fmt.HOLD)} if ok else None)
    best = min(table, key=lambda r: r["first"]) if ok else None
    return {"scored": len(rows), "table": table, "best": best, "flat": flat, "even": even, "rate": rate}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b, f = r["best"], r["flat"]["second"]
    d = round(f - b["second"], 4)
    return (f"hold={b['hold']} picked on the first half; sealed second half Brier {b['second']} vs flat "
            f"first-half base rates {f} ({'better' if d > 0 else 'NOT better'} by {abs(d)})")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts total-legs study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_totals_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py`).", ""])
    r = evaluate(games)
    lines_txt = ", ".join(f"{ln:g}: {v}" for ln, v in r["rate"].items())
    L += [f"Data: {len(games)} dated Premier League Darts matches (all first to 6 legs), {r['scored']} scored with the "
          f"board's Elo from earlier matches only. Share of matches over each total-legs line: {lines_txt}.", ""]
    if r["table"]:
        names = ", ".join(f"{x:g}" for x in LINES)
        L += [f"Format model (Elo win chance -> Over {names} legs), mean Brier over the lines; "
              f"{len(r['table'])} throw-first tries, all shown. First half picks, second half is sealed.", "",
              "| Throw-first leg chance (hold) | Brier, first half | Brier, sealed second half |", "|---|---|---|"]
        for row in r["table"]:
            tag = " (board)" if row["hold"] == fmt.HOLD else ""
            L.append(f"| {row['hold']:g}{tag} | {row['first']} | {row['second']} |")
        L += ["", f"Baselines: equal players at the board's hold: first {r['even']['first']}, second "
                  f"{r['even']['second']}; flat first-half base rates: first {r['flat']['first']}, second "
                  f"{r['flat']['second']}.", ""]
    L += [f"Verdict: {verdict(r)}", "",
          "A lead to test on new matches, not a change to the model. A closed field of about 10 players; no price here.",
          "", "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
