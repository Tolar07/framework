"""
Table tennis events study (framework #594, Event models #15; RECORD ONLY). Writes backtest/TABLE_TENNIS_EVENTS_STUDY.md.

Question: does the game ladder + points model in engine/table_tennis_events.py (board Elo win chance -> best-of-5 score
ladder with game momentum; total points = ladder chance of 3/4/5 games mixed with earlier point totals for that many
games) beat the plain frequency of earlier matches at (a) the exact game score, (b) games over 3.5 / 4.5 and -1.5
games, (c) total points over five lines taken from the earlier totals' percentiles?

Data: data/table_tennis_games.py (Setka Cup, 10 June - 8 July 2022, ~7,800 matches: one closed league, one month, a
league the board leaves out for integrity). No prices, so this measures accuracy, not edge. The walk-forward (one
matchday purged, Elo + frequencies from matches before D-1 only; momentum counted and picked on the first half of the
days, reported on the second half) is the volleyball study's `run`, reused: same best-of-5 shape.

  python backtest/table_tennis_events_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import volleyball_events_study as vstudy  # noqa: E402
from data import table_tennis_games as tt  # noqa: E402

OUT = ROOT / "backtest" / "TABLE_TENNIS_EVENTS_STUDY.md"
MOMENTA = vstudy.MOMENTA


def render(rows: list[dict], now: datetime, min_hist: int = 300, min_rows: int = 500) -> str:
    L = ["# Table tennis events study (game score, game totals, total points)", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/table_tennis_events_study.py` (framework #594). Record only, a "
         "shadow; one month of one closed league (Setka Cup, left out of the board for integrity); no price in the "
         "source, so accuracy not edge.", ""]
    if len(rows) < min_rows:
        return "\n".join(L + [f"NO DATA - PENDING ({len(rows)} usable matches).", ""])
    days = sorted({r["day"] for r in rows})
    split = days[len(days) // 2]
    res = vstudy.run(rows, MOMENTA, min_hist)
    tune = {m: [r for r in v if r["day"] < split] for m, v in res.items()}
    if not any(tune.values()):
        return "\n".join(L + ["No tuning-period match with enough history - PENDING.", ""])
    best = min(MOMENTA, key=lambda m: vstudy.summarise(tune[m], "sc_m", "sc_b")[0] if tune[m] else 9e9)
    held = [r for r in res[best] if r["day"] >= split]
    if not held:
        return "\n".join(L + ["No held-out match with enough history - PENDING.", ""])
    L += [f"Data: {len(rows)} matches, {days[0]} to {days[-1]} ({len(days)} days). Settings tried: **{len(MOMENTA)}** "
          f"(game momentum {', '.join(str(m) for m in MOMENTA)}); chosen on days before {split}: **{best}**. "
          f"Held-out matches from {split}: **{len(held)}**.", "",
          "| Event | Model log loss | Earlier-frequency log loss | Gain (base - model) | s.e. |", "|---|---|---|---|---|"]
    for name, a, b in (("Exact game score", "sc_m", "sc_b"),
                       ("Game markets (over 3.5/4.5, -1.5 home/away)", "set_m", "set_b"),
                       ("Total points over, 5 lines", "pt_m", "pt_b")):
        mu, bs, sem, _ = vstudy.summarise(held, a, b)
        L.append(f"| {name} | {mu:.4f} | {bs:.4f} | {bs - mu:+.4f} | {sem:.4f} |")
    L += ["", "Calibration of the total-points over chance (held-out, chosen momentum):", "",
          "| Predicted | Cases | Happened |", "|---|---|---|"]
    cal = [c for r in held for c in r.get("cal", [])]
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        c = [y for pm, y in cal if lo <= pm < lo + 0.2 or (lo == 0.8 and pm >= 1.0)]
        if c:
            L.append(f"| {lo:.1f}-{lo + 0.2:.1f} | {len(c)} | {sum(c) / len(c):.3f} |")
    L += ["", "## Reading", "",
          "- A positive gain means the model beats repeating how earlier matches finished; within about 2 s.e. of zero is no proof.",
          "- Only best-of-5 is modelled (every Setka Cup match is); best-of-7 (WTT finals) is PENDING, no data.",
          "- Points are mixed by game count only; a pair that plays long deuce games is not told apart.",
          "- Setka Cup stays out of the board (order 50); this tests the model shape, not the board's competitions.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def main(now: datetime | None = None) -> str:
    text = render(tt.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(main())
