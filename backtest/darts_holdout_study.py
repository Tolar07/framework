"""
Darts sealed hold-out study (framework#341, Week A; record-only). Writes backtest/DARTS_HOLDOUT_STUDY.md.

The earlier darts studies (K, margin-aware K, calibration temperature) each showed "leads" found by reading the whole
7-year sample, which flatters the best try. This one seals the last years: the setting is CHOSEN on the early years
only (lowest Brier on dev matches), then that single choice and the board setting are compared on the sealed years,
which played no part in choosing. Ratings still learn from every earlier match (walk-forward, scored before learned).
Every try is counted. No closing price exists, so this shows no edge. Nothing here changes a pick, stake, bar or the
live switch.

  python backtest/darts_holdout_study.py
"""
from __future__ import annotations

import itertools
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import darts_history_study as hist  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_HOLDOUT_STUDY.md"
MIN_SCORED = 100
MIN_GAMES = 3
SEAL_FROM = "2024"  # matches from this year on are sealed
MODES = ["plain", "margin_k"]
KS = [16.0, 24.0, 32.0, 48.0]
TEMPS = [1.0, 1.5, 2.0]
BASE = ("plain", ms.ELO_K, 1.0)
TRIES = list(itertools.product(MODES, KS, TEMPS))


def mult_of(g: dict, mode: str) -> float:
    hs, as_ = g.get("home_sets"), g.get("away_sets")
    if mode == "plain" or not isinstance(hs, int) or not isinstance(as_, int) or hs + as_ <= 0:
        return 1.0
    return math.log(abs(hs - as_) + 1) + 1.0


def walk_forward(games: list[dict], mode: str, k: float, temp: float) -> dict:
    """Walk-forward; Brier on dev (before SEAL_FROM) and sealed (from SEAL_FROM) matches reported separately."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    acc = {"dev": [0, 0.0], "sealed": [0, 0.0]}
    for g in sorted(games, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p_learn = 1 / (1 + 10 ** ((ra - rh) / 400))
        p = 1 / (1 + 10 ** ((ra - rh) / (400 * temp)))  # temp above 1 stretches the gap
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= MIN_GAMES and played.get(a, 0) >= MIN_GAMES:
            part = "sealed" if str(g["kickoff_utc"])[:4] >= SEAL_FROM else "dev"
            acc[part][0] += 1
            acc[part][1] += (p - y) ** 2
        d = k * mult_of(g, mode) * (y - p_learn)
        rating[h], rating[a] = rh + d, ra - d
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1

    def f(part: str) -> float | None:
        return round(acc[part][1] / acc[part][0], 4) if acc[part][0] else None

    return {"mode": mode, "k": k, "temp": temp, "dev_n": acc["dev"][0], "dev": f("dev"),
            "sealed_n": acc["sealed"][0], "sealed": f("sealed")}


def evaluate(games: list[dict]) -> dict:
    rows = [walk_forward(games, *t) for t in TRIES]
    base = next(r for r in rows if (r["mode"], r["k"], r["temp"]) == BASE)
    ok = [r for r in rows if r["dev"] is not None and r["dev_n"] >= MIN_SCORED]
    chosen = min(ok, key=lambda r: r["dev"]) if ok else None
    if chosen is None or base["sealed_n"] < MIN_SCORED or base["sealed"] is None or chosen["sealed"] is None:
        verdict = f"PENDING (needs {MIN_SCORED} scored matches on both dev and sealed years)"
    elif (chosen["mode"], chosen["k"], chosen["temp"]) == BASE:
        verdict = "the board setting was also the best on dev: nothing to confirm"
    elif chosen["sealed"] < base["sealed"]:
        verdict = "confirmed on sealed years (lower Brier than the board setting): a lead, still only one sample"
    else:
        verdict = "NOT confirmed on sealed years: the dev lead was selection luck"
    return {"rows": rows, "base": base, "chosen": chosen, "verdict": verdict}


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts sealed hold-out study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_holdout_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python backtest/darts_history_study.py` to fetch the results).", ""])
    ev = evaluate(games)
    b, c = ev["base"], ev["chosen"]

    def p(v: object) -> object:
        return "PENDING" if v is None else v

    L += [f"Data: {len(games)} PDC World Championship matches. Matches from {SEAL_FROM} on are sealed: the setting is chosen "
          f"on the earlier matches only (each player at least {MIN_GAMES} earlier games), then compared once on the sealed ones.",
          "", "No closing price exists for these matches: no edge is shown, only whether a dev-chosen setting holds up on unseen years.",
          "", f"## Result ({len(TRIES)} tries counted)", "",
          "| Setting | Learns from | K | Temperature | Dev matches | Dev Brier | Sealed matches | Sealed Brier |",
          "|---|---|---|---|---|---|---|---|"]
    L.append(f"| board | {b['mode']} | {b['k']:g} | {b['temp']:g} | {b['dev_n']} | {p(b['dev'])} | {b['sealed_n']} | {p(b['sealed'])} |")
    if c:
        L.append(f"| best on dev | {c['mode']} | {c['k']:g} | {c['temp']:g} | {c['dev_n']} | {p(c['dev'])} | {c['sealed_n']} | {p(c['sealed'])} |")
    L += ["", f"Verdict: {ev['verdict']}.", "", "## Every try", "",
          "| Learns from | K | Temperature | Dev Brier | Sealed Brier |", "|---|---|---|---|---|"]
    for r in ev["rows"]:
        L.append(f"| {r['mode']} | {r['k']:g} | {r['temp']:g} | {p(r['dev'])} | {p(r['sealed'])} |")
    L += ["", "The sealed Brier of tries other than the dev-chosen one is shown for the record only: choosing by it would undo the seal.",
          "", "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(hist.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
