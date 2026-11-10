"""
TENNIS tournament-level study: is the Pinnacle close mis-priced by tournament level or round? (framework#345, record-only)

Same walk-forward ridge logistic as tennis_residual_study (de-vigged close = fixed offset, refit each test year on EARLIER
years only). Signals are the market logit times a context flag, so each coefficient reads "are favourites under/over-priced
in this context" (positive = favourites win more than the price says): Grand Slam, Masters 1000, late round (quarter-final
or later), indoor court. Context comes from the results file's own Series/Round/Court columns; a row with no Series is
skipped (PENDING, never invented). Tries counted: 1 model, 4 signals, one ridge value. Nothing here changes a stake, bar,
threshold or live switch.

  python backtest/tennis_level_study.py      writes backtest/TENNIS_LEVEL_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402
from backtest import tennis_residual_study as rs  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_LEVEL_STUDY.md"
LATE = ("quarterfinals", "semifinals", "the final")
NAMES = ("Grand Slam x price", "Masters 1000 x price", "QF-or-later x price", "indoor x price")


def features(games: list[dict]) -> list[list[float] | None]:
    """Per match: market logit times each context flag. None when the file gave no Series."""
    out = []
    for g in games:
        s = (g.get("series") or "").lower()
        if not s:
            out.append(None)
            continue
        z = tb.logit(g["mkt"])
        out.append([z * (1.0 if "grand slam" in s else 0.0),
                    z * (1.0 if "masters" in s else 0.0),
                    z * (1.0 if (g.get("round") or "").lower() in LATE else 0.0),
                    z * (1.0 if (g.get("court") or "").lower() == "indoor" else 0.0)])
    return out


def run(games: list[dict]) -> str:
    rows, coefs = rs.walk_forward(games, features(games))
    sc = rs.score(rows)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis tournament-level study (shadow, record only)", "",
         f"Made {made} by `backtest/tennis_level_study.py` (framework#345). Pinnacle's de-vigged close is a fixed offset; "
         f"signals are the price times Grand Slam / Masters 1000 / quarter-final-or-later / indoor flags; coefficients "
         f"refit each year on earlier years only (ridge {rs.RIDGE:g}). Tries counted: **1** model (4 signals, no search).", ""]
    if not sc["n"]:
        L.append("PENDING: no matches with a Series label to fit.")
        return "\n".join(L) + "\n"
    se = rs.paired_se(rows) or 0.0
    gain = sc["mkt_ll"] - sc["ll"]
    ys = [r["g"]["year"] for r in rows]
    L += ["| Held-out years | Matches | Model log loss | Pinnacle close log loss | Gain per match | Std error |",
          "|---|---|---|---|---|---|",
          f"| {min(ys)}-{max(ys)} | {sc['n']} | {sc['ll']:.5f} | {sc['mkt_ll']:.5f} | {gain:+.5f} | {se:.5f} |", "",
          "| Fit for year | " + " | ".join(NAMES) + " |", "|---|---|---|---|---|"]
    for y, b in sorted(coefs.items()):
        L.append(f"| {y} | " + " | ".join(f"{v:+.4f}" for v in b) + " |")
    z = gain / se if se else 0.0
    L += ["", "## Reading", "",
          f"- Gain {gain:+.5f} log loss per match ({z:+.1f} standard errors): "
          + ("a signal beyond the price, worth a closer shadow." if z >= 2 else
             "not distinguishable from zero; the price already holds tournament level. Keep pricing off the exchange."),
          "- Positive coefficient: favourites won more than the price said in that context; negative: fewer.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = tb.load()
    if len(games) < 3000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
