"""
RUGBY combined candidate study (framework#344, record-only SHADOW candidate).

Two earlier studies each found a fix for the home-side bias, tested ONE AT A TIME:
  backtest/rugby_inputs_study.py       per-league home edge Elo     (held-out Brier 0.1844)
  backtest/rugby_calibration_study.py  shrink toward the home rate  (on the flat +70 Elo)
This asks whether stacking them beats either alone. Same ESPN games. Per-league home edges and the shrink weight w are
chosen on 2014-2019 only (every try counted), reported on 2020+ only. Record only: nothing here changes a stake, bar,
threshold or live switch.

  python backtest/rugby_combined_study.py      writes backtest/RUGBY_COMBINED_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import rugby_calibration_study as rc  # noqa: E402
from backtest import rugby_inputs_study as ri  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_COMBINED_STUDY.md"
MIN_GAMES = 100


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    leagues = sorted({g["league"] for g in games})
    homes, tries = ri.best_home_by_league(games, False)
    p_flat = rb.replay(games, 32.0, 70.0)
    p_league = ri.replay(games, homes, False)
    tuned = {w: rc.brier(games, p_league, rb.TUNE_YEARS, base, w) for w in rc.WS}
    ok = {w: t for w, t in tuned.items() if t["n"] >= MIN_GAMES}
    best = min(ok, key=lambda w: ok[w]["brier"]) if ok else None
    tries += len(rc.WS)
    rows = [("Flat home +70, no shrink (backtest pick)", rc.brier(games, p_flat, test, base, 1.0)),
            ("Per-league home edge, no shrink", rc.brier(games, p_league, test, base, 1.0))]
    if best is not None:
        rows.append((f"Per-league home edge + shrink w={best}", rc.brier(games, p_league, test, base, best)))
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby combined candidate (per-league home edge + shrink)", "",
         f"Made {made} by `backtest/rugby_combined_study.py` (framework#344). {len(games)} games, final scores only (ESPN). "
         f"Settings tried: **{tries}**; chosen on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**. "
         f"Leagues: {', '.join(leagues)}. Home edges chosen: "
         + ", ".join(f"{lg} +{h:.0f}" for lg, h in sorted(homes.items())) + ".", "",
         "| Rule (held-out years) | Games | Brier |", "|---|---|---|"]
    for name, r in rows:
        L.append(f"| {name} | {r['n']} | {r['brier']:.4f} |" if r["n"] else f"| {name} | 0 | PENDING |")
    L += ["", "## Reading", ""]
    if best is None or not rows[2][1]["n"] or not rows[1][1]["n"]:
        L.append("- Too few tuning games to choose a shrink: PENDING.")
    else:
        alone, stacked = rows[1][1]["brier"], rows[2][1]["brier"]
        d = alone - stacked
        L.append(f"- Stacking the shrink on the per-league edge changed held-out Brier by {d:+.4f} "
                 + ("(helps; the stacked rule is the shadow candidate)." if d > 0.0005 else
                    "(no real help: per-league home edge alone is enough)."))
        if rows[0][1]["n"]:
            L.append(f"- Best of the two vs flat +70: {rows[0][1]['brier'] - min(alone, stacked):+.4f} Brier.")
    L += [f"- {tries} settings tried; the held-out line is the honest one.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = rb.load()
    if len(games) < 1000:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
