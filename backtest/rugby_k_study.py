"""
RUGBY Elo speed (K-factor) study (framework#344, record-only).

Every rugby study so far fixed K at 32. K is how fast a team's rating moves after a result. A rugby season is short
(~20 games a team), so K may matter more than in football. Here K is tried on a grid, with the per-league home edge
already chosen by backtest/rugby_inputs_study.py. K is chosen on 2014-2019 only (every try counted) and reported on
2020+ only. Record only: nothing here changes a stake, bar, threshold or live switch.

  python backtest/rugby_k_study.py      writes backtest/RUGBY_K_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import rugby_inputs_study as ri  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_K_STUDY.md"
KS = (8.0, 12.0, 16.0, 24.0, 32.0, 40.0, 56.0)


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    home, tries = ri.best_home_by_league(games, False)
    cache = {k: ri.replay(games, home, False, k) for k in KS}
    tries += len(cache)
    tuned = {k: rb.evaluate(games, p, rb.TUNE_YEARS) for k, p in cache.items()}
    ok = {k: t for k, t in tuned.items() if t["n"] >= ri.MIN_N}
    best = min(ok, key=lambda k: ok[k]["brier"]) if ok else None
    at32 = rb.evaluate(games, cache[32.0], test, base)
    held = rb.evaluate(games, cache[best], test, base) if best is not None else None
    live = rb.evaluate(games, rb.replay(games, 24.0, 0.0), test, base)
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby Elo speed (K-factor) study", "",
         f"Made {made} by `backtest/rugby_k_study.py` (framework#344). {len(games)} games, final scores only (ESPN). "
         f"Settings tried: **{tries}**; chosen on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on "
         f"**{test[0]}-{test[1]} only**.", "",
         f"| Rule (held-out years) | Games | Brier | Brier flat baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|"]
    rows = [("Live board: K24, no home edge", live), ("Per-league home edge, K32 (current shadow)", at32)]
    if held and best != 32.0:
        rows.append((f"Per-league home edge, K{best:.0f}", held))
    for nm, r in rows:
        L.append(f"| {nm} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |" if r["n"]
                 else f"| {nm} | 0 | PENDING | PENDING | PENDING |")
    L += ["", "Tuning-years Brier by K: " + ", ".join(
        f"K{k:.0f}={t['brier']:.4f}" for k, t in tuned.items() if t["n"]), "", "## Reading", ""]
    if held and at32["n"]:
        gain = at32["brier"] - held["brier"]
        L.append(f"- Best tuning-years K is {best:.0f}; on the held-out years it changed Brier by {gain:+.4f} vs K32 "
                 + ("(a shadow candidate, to be confirmed on the shadow board's record)." if gain > 0.0005 and best != 32.0
                    else "(no real help: keep K32)."))
    else:
        L.append("- PENDING: too little tuning data.")
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
