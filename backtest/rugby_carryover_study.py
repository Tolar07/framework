"""
RUGBY off-season carry-over walk-forward study (framework#344, record-only SHADOW candidate).

Idea (standard in Elo sports models, e.g. season reversion in public NFL/NBA Elo): after a long break (a new
season) rosters change, so each rating is pulled FRAC of the way back to the 1500 mean. A side's first game after
a gap of more than GAP_DAYS days counts as a new season. Every fraction tried is counted, chosen on 2014-2019,
reported on 2020+ only, next to the per-league-home-edge Elo it builds on (backtest/rugby_inputs_study.py).

Record only: nothing here changes a stake, bar, threshold or the live switch.

  python backtest/rugby_carryover_study.py      writes backtest/RUGBY_CARRYOVER_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import rugby_inputs_study as ri  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_CARRYOVER_STUDY.md"
FRACS = (0.0, 0.1, 0.2, 0.33, 0.5)
GAP_DAYS = 100
K = ri.K


def replay(games, home_by_league, frac: float, k: float = K, gap_days: int = GAP_DAYS):
    """Elo replay; a side's rating is pulled `frac` back to ELO_START before its first game after a long break."""
    r, n, last, out = {}, {}, {}, []
    for g in games:
        h, a = g["home"], g["away"]
        d = date.fromisoformat(g["day"]) if "day" in g else None
        for t in (h, a):
            if d is not None and t in last and t in r and (d - last[t]).days > gap_days:
                r[t] = r[t] + frac * (rb.ELO_START - r[t])
        rh, ra = r.get(h, rb.ELO_START), r.get(a, rb.ELO_START)
        e = 1 / (1 + 10 ** ((ra - rh - home_by_league[g["league"]]) / 400))
        out.append(e if n.get(h, 0) >= rb.MIN_GAMES and n.get(a, 0) >= rb.MIN_GAMES else None)
        dd = k * (g["y"] - e)
        r[h], r[a] = rh + dd, ra - dd
        n[h], n[a] = n.get(h, 0) + 1, n.get(a, 0) + 1
        if d is not None:
            last[h] = last[a] = d
    return out


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    home, tries = ri.best_home_by_league(games, False)
    cache = {f: replay(games, home, f) for f in FRACS}
    tries += len(cache)
    tuned = {f: rb.evaluate(games, p, rb.TUNE_YEARS) for f, p in cache.items()}
    ok = {f: t for f, t in tuned.items() if t["n"] >= ri.MIN_N}
    best = min(ok, key=lambda f: ok[f]["brier"]) if ok else None
    plain = rb.evaluate(games, cache[0.0], test, base)
    held = rb.evaluate(games, cache[best], test, base) if best is not None else None
    live = rb.evaluate(games, rb.replay(games, 24.0, 0.0), test, base)
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby off-season carry-over study (rating pulled back to the mean after a long break)", "",
         f"Made {made} by `backtest/rugby_carryover_study.py` (framework#344). {len(games)} games, final scores "
         f"only (ESPN). Settings tried: **{tries}**; chosen on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported "
         f"on **{test[0]}-{test[1]} only**. A new season = a side's first game after more than {GAP_DAYS} days.", "",
         f"| Rule (held-out years) | Games | Brier | Brier flat baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|"]
    rows = [("Live board: K24, no home edge", live), ("Per-league home edge, full carry-over", plain)]
    if held and best > 0:
        rows.append((f"Per-league home edge + pull {best:.0%} to the mean each new season", held))
    for nm, r in rows:
        L.append(f"| {nm} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |" if r["n"]
                 else f"| {nm} | 0 | PENDING | PENDING | PENDING |")
    L += ["", "## Reading", ""]
    if held and plain["n"]:
        gain = plain["brier"] - held["brier"]
        L.append(f"- Season pull {best:.0%} changed held-out Brier by {gain:+.4f} vs full carry-over "
                 + ("(a shadow candidate, to be confirmed on the shadow board's record)." if gain > 0.0005 and best > 0
                    else "(no real help: not worth a shadow)."))
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
