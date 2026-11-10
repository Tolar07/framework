"""
TENNIS workload study: does recent match load add to Pinnacle's close? (framework#345, record-only shadow)

Same walk-forward logistic as tennis_residual_study (de-vigged Pinnacle close = fixed offset, ridge-shrunk toward
'the market is right', refit each test year on EARLIER years only), with three schedule signals made only from the
results list itself (no new data): days since each side's last match (capped, log-ratio), matches each side played in
the previous 14 days (difference), and a Best-of-5 flag times the load gap. A player's first match in the data has no
rest value: that row is skipped for the model (PENDING, never invented). Tries counted: 1 model, 3 signals, one ridge
value. Nothing here changes a stake, bar, threshold or live switch.

  python backtest/tennis_workload_study.py      writes backtest/TENNIS_WORKLOAD_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402
from backtest import tennis_residual_study as rs  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_WORKLOAD_STUDY.md"
REST_CAP = 30      # days; a longer gap reads as 30 (a layoff, not a bigger number)
WINDOW = 14        # days of recent load
NAMES = ("rest gap (log days, a vs b)", "matches in last 14 days (a minus b)", "Bo5 x load gap")


def _ord(day: str) -> int:
    return datetime.strptime(day, "%Y-%m-%d").toordinal()


def features(games: list[dict]) -> list[list[float] | None]:
    """Per match, from results BEFORE it only: [rest log-ratio, load difference, Bo5 x load difference]."""
    hist: dict[tuple, list[int]] = {}
    out = []
    for g in games:
        d = _ord(g["day"])
        ka, kb = (g["tour"], g["a"]), (g["tour"], g["b"])
        ha, hb = hist.get(ka, []), hist.get(kb, [])
        if ha and hb:
            ra = max(min(d - ha[-1], REST_CAP), 1)
            rb = max(min(d - hb[-1], REST_CAP), 1)
            la = sum(1 for x in ha if d - x <= WINDOW)
            lb = sum(1 for x in hb if d - x <= WINDOW)
            out.append([math.log(ra / rb), float(la - lb), (1.0 if g.get("bo", 3) == 5 else 0.0) * (la - lb)])
        else:
            out.append(None)
        hist.setdefault(ka, []).append(d)
        hist.setdefault(kb, []).append(d)
    return out


def run(games: list[dict]) -> str:
    rows, coefs = rs.walk_forward(games, features(games))
    sc = rs.score(rows)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis workload study (shadow, record only)", "",
         f"Made {made} by `backtest/tennis_workload_study.py` (framework#345). Pinnacle's de-vigged close is a fixed "
         f"offset; signals are rest-day gap, matches in the last {WINDOW} days and a Best-of-5 interaction, from the "
         f"results list only; coefficients refit each year on earlier years only (ridge {rs.RIDGE:g}). Tries "
         f"counted: **1** model (3 signals, no search).", ""]
    if not sc["n"]:
        L.append("PENDING: not enough matches with both players' history to fit.")
        return "\n".join(L) + "\n"
    se = rs.paired_se(rows) or 0.0
    gain = sc["mkt_ll"] - sc["ll"]
    ys = [r["g"]["year"] for r in rows]
    L += ["| Held-out years | Matches | Model log loss | Pinnacle close log loss | Gain per match | Std error |",
          "|---|---|---|---|---|---|",
          f"| {min(ys)}-{max(ys)} | {sc['n']} | {sc['ll']:.5f} | {sc['mkt_ll']:.5f} | {gain:+.5f} | {se:.5f} |", "",
          "| Fit for year | " + " | ".join(NAMES) + " |", "|---|---|---|---|"]
    for y, b in sorted(coefs.items()):
        L.append(f"| {y} | " + " | ".join(f"{v:+.4f}" for v in b) + " |")
    z = gain / se if se else 0.0
    L += ["", "## Reading", "",
          f"- Gain {gain:+.5f} log loss per match ({z:+.1f} standard errors): "
          + ("a signal beyond the price, worth a closer shadow." if z >= 2 else
             "not distinguishable from zero; the price already holds workload. Keep pricing off the exchange."),
          "- Coefficients near 0 mean the close already reflects rest and recent load.",
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
