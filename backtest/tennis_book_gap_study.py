"""
TENNIS book-consensus study: does the market-average close know something Pinnacle's close does not? (framework#345, record-only)

Same walk-forward ridge logistic as tennis_residual_study (Pinnacle's de-vigged close = fixed offset, refit each test year on
EARLIER years only). Signals: (1) the gap between the de-vigged market-average close and the de-vigged Pinnacle close, in logit
(positive = the other books like player A more than Pinnacle does); (2) the price logit times a WTA flag (are favourites
mis-priced differently on the women's tour). A row with no average price is skipped (PENDING, never invented). Tries counted:
1 model, 2 signals, one ridge value. Nothing here changes a stake, bar, threshold or live switch.

  python backtest/tennis_book_gap_study.py      writes backtest/TENNIS_BOOK_GAP_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402
from backtest import tennis_residual_study as rs  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_BOOK_GAP_STUDY.md"
NAMES = ("book gap (avg - Pinnacle)", "WTA x price")


def features(games: list[dict]) -> list[list[float] | None]:
    """Per match: [avg-vs-Pinnacle logit gap, price logit x WTA flag]. None when there is no average price."""
    out = []
    for g in games:
        qa, qb = g.get("qa"), g.get("qb")
        if not qa or not qb or qa <= 1 or qb <= 1:
            out.append(None)
            continue
        z = tb.logit(g["mkt"])
        out.append([tb.logit(tb.devig(qa, qb)) - z, z * (1.0 if g.get("tour") == "WTA" else 0.0)])
    return out


def run(games: list[dict]) -> str:
    rows, coefs = rs.walk_forward(games, features(games))
    sc = rs.score(rows)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis book-gap study (shadow, record only)", "",
         f"Made {made} by `backtest/tennis_book_gap_study.py` (framework#345). Pinnacle's de-vigged close is a fixed offset; "
         f"signals are the average-vs-Pinnacle gap and the price times a WTA flag; coefficients "
         f"refit each year on earlier years only (ridge {rs.RIDGE:g}). Tries counted: **1** model (2 signals, no search).", ""]
    if not sc["n"]:
        L.append("PENDING: no matches with an average price to fit.")
        return "\n".join(L) + "\n"
    se = rs.paired_se(rows) or 0.0
    gain = sc["mkt_ll"] - sc["ll"]
    ys = [r["g"]["year"] for r in rows]
    L += ["| Held-out years | Matches | Model log loss | Pinnacle close log loss | Gain per match | Std error |",
          "|---|---|---|---|---|---|",
          f"| {min(ys)}-{max(ys)} | {sc['n']} | {sc['ll']:.5f} | {sc['mkt_ll']:.5f} | {gain:+.5f} | {se:.5f} |", "",
          "| Fit for year | " + " | ".join(NAMES) + " |", "|---|---|---|"]
    for y, b in sorted(coefs.items()):
        L.append(f"| {y} | " + " | ".join(f"{v:+.4f}" for v in b) + " |")
    z = gain / se if se else 0.0
    L += ["", "## Reading", "",
          f"- Gain {gain:+.5f} log loss per match ({z:+.1f} standard errors): "
          + ("a signal beyond the price, worth a closer shadow." if z >= 2 else
             "not distinguishable from zero; Pinnacle already holds what the other books know. Keep pricing off the exchange."),
          "- Book-gap coefficient above 0: the other books were right to lean away from Pinnacle; WTA coefficient above 0: favourites won more than the price said on that tour.",
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
