"""
TENNIS surface-form and head-to-head study over Pinnacle's close (framework#345, record-only shadow)

Same walk-forward logistic as tennis_residual_study (de-vigged Pinnacle close = fixed offset, ridge-shrunk toward
'the market is right', refit each test year on EARLIER years only). Three signals from the results list only:
  1. surface form gap: each side's win rate on THIS surface over its earlier matches, shrunk to 50% with 5 pseudo
     matches, a minus b;
  2. head-to-head: a's smoothed share of earlier meetings (any surface), minus 0.5, scaled by meetings/(meetings+3);
  3. surface switch: 1 when a's last match was on another surface, minus the same for b.
A player's first match in the data has no history: that row is skipped (PENDING, never invented). Tries counted:
1 model, 3 signals, one ridge value. Idea source: a practitioner video (recent form on the surface, head-to-head,
a surface change) https://www.youtube.com/watch?v=zUUXMhxZgZY @ 01:13, 01:30, 02:40 (transcript only; frames not
checked). Nothing here changes a stake, bar, threshold or live switch.

  python backtest/tennis_surface_h2h_study.py      writes backtest/TENNIS_SURFACE_H2H_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402
from backtest import tennis_residual_study as rs  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_SURFACE_H2H_STUDY.md"
PRIOR = 5.0   # pseudo matches at 50% for surface form
H2H_PRIOR = 3.0
NAMES = ("surface win-rate gap (a minus b)", "head-to-head share (a, shrunk)", "surface switch (a minus b)")


def _rate(rec: list[int]) -> float:
    return (rec[0] + PRIOR / 2) / (rec[1] + PRIOR)


def features(games: list[dict]) -> list[list[float] | None]:
    """Per match, from results BEFORE it only. g['y'] == 1.0 means a won."""
    surf: dict[tuple, list[int]] = {}   # (tour, player, surface) -> [wins, played]
    last: dict[tuple, str] = {}         # (tour, player) -> last surface
    h2h: dict[tuple, list[int]] = {}    # (tour, first, second) sorted -> [first wins, meetings]
    out = []
    for g in games:
        t, a, b, s = g["tour"], g["a"], g["b"], g.get("surface", "")
        key = (t,) + tuple(sorted((a, b)))
        if (t, a) in last and (t, b) in last and s:
            ra = _rate(surf.get((t, a, s), [0, 0]))
            rb = _rate(surf.get((t, b, s), [0, 0]))
            w, n = h2h.get(key, [0, 0])
            aw = w if a == key[1] else n - w
            share = ((aw + H2H_PRIOR / 2) / (n + H2H_PRIOR) - 0.5) * (n / (n + H2H_PRIOR)) if n else 0.0
            sw = (1.0 if last[(t, a)] != s else 0.0) - (1.0 if last[(t, b)] != s else 0.0)
            out.append([ra - rb, share, sw])
        else:
            out.append(None)
        if s:
            for p, won in ((a, g["y"] == 1.0), (b, g["y"] != 1.0)):
                rec = surf.setdefault((t, p, s), [0, 0])
                rec[0] += int(won)
                rec[1] += 1
                last[(t, p)] = s
            rec = h2h.setdefault(key, [0, 0])
            rec[0] += int((g["y"] == 1.0) == (a == key[1]))
            rec[1] += 1
    return out


def run(games: list[dict]) -> str:
    rows, coefs = rs.walk_forward(games, features(games))
    sc = rs.score(rows)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis surface-form and head-to-head study (shadow, record only)", "",
         f"Made {made} by `backtest/tennis_surface_h2h_study.py` (framework#345). Pinnacle's de-vigged close is a "
         f"fixed offset; signals are the win-rate gap on this surface, the head-to-head record and a surface switch, "
         f"from the results list only; coefficients refit each year on earlier years only (ridge {rs.RIDGE:g}). "
         f"Tries counted: **1** model (3 signals, no search). Idea source: "
         f"https://www.youtube.com/watch?v=zUUXMhxZgZY @ 01:13, 01:30, 02:40.", ""]
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
             "not distinguishable from zero; the price already holds surface form and head-to-head. "
             "Keep pricing off the exchange."),
          "- Coefficients near 0 mean the close already reflects these.",
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
