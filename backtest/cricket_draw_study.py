"""
CRICKET Test-match DRAW study (framework#343; record-only).

Cricket market "1" (3-way) on a Test has a Draw outcome, but the board's Elo only gives a win chance. This replays
every men's Test Cricsheet lists (results only), one Elo pool, in date order, and grades three 3-way rules:

  - NODRAW  : draw chance 0, Elo splits the rest (what the 2-way Elo implies);
  - FLAT    : one draw rate d (from the tuning years) takes its share, Elo splits the rest;
  - GAP     : draw rate by Elo-gap bucket (from the tuning years), Elo splits the rest.

Every rule tried is counted; draw rates come from 2010-2018 only and are reported on 2019 onward (no peeking).
The Elo learns from decided Tests only (a draw is not a win). Record only: nothing here changes a stake, a bar,
a threshold or the live switch.

  python backtest/cricket_draw_study.py      writes backtest/CRICKET_DRAW_STUDY.md
"""
from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.cricket_backtest import ELO_START, MIN_GAMES, TUNE_YEARS, fetch_zip  # noqa: E402

OUT = ROOT / "backtest" / "CRICKET_DRAW_STUDY.md"
K = 24.0                       # the live board's ELO_K
BUCKETS = (50.0, 150.0)        # |Elo gap| edges: close / medium / wide


def parse_test(d: dict) -> dict | None:
    """One finished Test -> {day, a, b, res} with res 'A' / 'B' / 'D' (draw or tie); else None."""
    try:
        info = d["info"]
        teams = info["teams"]
        out = info.get("outcome") or {}
        if len(teams) != 2:
            return None
        win = out.get("winner")
        if win in teams:
            res = "A" if win == teams[0] else "B"
        elif out.get("result") in ("draw", "tie"):
            res = "D"
        else:
            return None
        return {"day": info["dates"][0], "a": teams[0], "b": teams[1], "res": res}
    except (KeyError, TypeError, IndexError):
        return None


def load(fetch=fetch_zip) -> list[dict]:
    try:
        z = zipfile.ZipFile(BytesIO(fetch("tests_male")))
    except Exception as ex:  # PENDING, never invented
        print(f"Tests not loaded ({type(ex).__name__})")
        return []
    games = []
    for name in z.namelist():
        if name.endswith(".json"):
            try:
                g = parse_test(json.loads(z.read(name)))
            except ValueError:
                continue
            if g:
                games.append(g)
    games.sort(key=lambda g: (g["day"], g["a"], g["b"]))
    for g in games:
        g["year"] = int(g["day"][:4])
    return games


def replay(games: list[dict]) -> None:
    """Add g['e'] (Elo chance A beats B, given a decision) and g['gap'] BEFORE each Test; None until rated."""
    r, n = {}, {}
    for g in games:
        ra, rb = r.get(g["a"], ELO_START), r.get(g["b"], ELO_START)
        e = 1 / (1 + 10 ** ((rb - ra) / 400))
        rated = n.get(g["a"], 0) >= MIN_GAMES and n.get(g["b"], 0) >= MIN_GAMES
        g["e"], g["gap"] = (e, abs(ra - rb)) if rated else (None, None)
        if g["res"] != "D":
            y = 1.0 if g["res"] == "A" else 0.0
            r[g["a"]], r[g["b"]] = ra + K * (y - e), rb - K * (y - e)
        n[g["a"]], n[g["b"]] = n.get(g["a"], 0) + 1, n.get(g["b"], 0) + 1


def bucket(gap: float) -> int:
    return sum(gap >= b for b in BUCKETS)


def probs(g: dict, d: float) -> tuple[float, float, float]:
    return (1 - d) * g["e"], d, (1 - d) * (1 - g["e"])


def brier3(g: dict, p: tuple[float, float, float]) -> float:
    o = {"A": (1, 0, 0), "D": (0, 1, 0), "B": (0, 0, 1)}[g["res"]]
    return sum((pi - oi) ** 2 for pi, oi in zip(p, o))


def run(games: list[dict]) -> str:
    replay(games)
    last = max(g["year"] for g in games)
    test = (TUNE_YEARS[1] + 1, last)
    rated = [g for g in games if g["e"] is not None]
    tune = [g for g in rated if TUNE_YEARS[0] <= g["year"] <= TUNE_YEARS[1]]
    held = [g for g in rated if test[0] <= g["year"] <= test[1]]
    if len(tune) < 50 or len(held) < 50:
        return "# Cricket Test draw study\n\nPENDING: too few rated Tests.\n"
    flat = sum(g["res"] == "D" for g in tune) / len(tune)
    by_b = {}
    for b in range(len(BUCKETS) + 1):
        rows = [g for g in tune if bucket(g["gap"]) == b]
        by_b[b] = (sum(g["res"] == "D" for g in rows) / len(rows) if len(rows) >= 20 else flat, len(rows))
    rules = {"NODRAW (draw 0)": lambda g: probs(g, 0.0),
             f"FLAT (draw {flat:.1%})": lambda g: probs(g, flat),
             "GAP (draw by Elo-gap bucket)": lambda g: probs(g, by_b[bucket(g["gap"])][0])}
    names = ["close", "medium", "wide"]
    held_draw = sum(g["res"] == "D" for g in held) / len(held)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Cricket Test draw study", "",
         f"Made {made} by `backtest/cricket_draw_study.py` (framework#343). {len(games)} men's Tests with a result "
         f"(Cricsheet), {len(rated)} rated. Rules tried: **{len(rules)}**; draw rates fitted on "
         f"{TUNE_YEARS[0]}-{TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only** ({len(held)} Tests, "
         f"draws {held_draw:.1%}).", "",
         "| Rule (held-out years) | 3-way Brier (lower is better) |", "|---|---|"]
    res = {}
    for name, f in rules.items():
        res[name] = sum(brier3(g, f(g)) for g in held) / len(held)
        L.append(f"| {name} | {res[name]:.4f} |")
    L += ["", "Draw rate by Elo gap (tuning years):", "", "| Gap | Tests | Draw rate |", "|---|---|---|"]
    for b, (rate, n) in by_b.items():
        L.append(f"| {names[b]} | {n} | {rate:.1%} |")
    nod, best = res["NODRAW (draw 0)"], min(res, key=res.get)
    L += ["", "## Reading", "",
          f"- Best held-out rule: {best} ({res[best]:.4f}) vs no-draw {nod:.4f}. "
          + ("A draw chance matters: a Test 3-way price built from the 2-way Elo alone is wrong by that margin."
             if best != "NODRAW (draw 0)" else "A draw chance did not help here."),
          f"- {len(rules)} rules tried; the held-out line is the honest one.",
          "- No free historical closing odds: no return figure; return and CLV come from the shadow record.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 300:
        print(f"only {len(games)} Tests read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
