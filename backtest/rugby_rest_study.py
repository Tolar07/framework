"""
RUGBY rest-days walk-forward study (framework#344, record-only SHADOW candidate).

Idea (public, widely used in team-sport models): a side that played fewer days ago is more tired. Here: the
home-minus-away gap in days since each side's last game (capped at 14; first game / unknown = 7) shifts the Elo
difference by COEF Elo points per day. Every coefficient tried is counted, chosen on 2014-2019, reported on 2020+
only, next to the plain per-league-home-edge Elo it builds on (backtest/rugby_inputs_study.py).

Record only: nothing here changes a stake, bar, threshold or the live switch.

  python backtest/rugby_rest_study.py      writes backtest/RUGBY_REST_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import rugby_inputs_study as ri  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_REST_STUDY.md"
COEFS = (0.0, 2.0, 4.0, 6.0, 8.0, 12.0)
CAP, DEFAULT_REST = 14, 7
K = ri.K


def rest_gap(games: list[dict]) -> list[int]:
    """Home-minus-away days since last game BEFORE each game (games in date order); no look-ahead."""
    last, out = {}, []
    for g in games:
        d = date.fromisoformat(g["day"]) if "day" in g else None

        def rest(t, d=d):
            if d is None or t not in last:
                return DEFAULT_REST
            return min((d - last[t]).days, CAP)

        out.append(rest(g["home"]) - rest(g["away"]))
        if d is not None:
            last[g["home"]] = last[g["away"]] = d
    return out


def replay(games, home_by_league, coef: float, gaps: list[int], k: float = K):
    r, n, out = {}, {}, []
    for g, gap in zip(games, gaps, strict=True):
        h, a = g["home"], g["away"]
        rh, ra = r.get(h, rb.ELO_START), r.get(a, rb.ELO_START)
        e = 1 / (1 + 10 ** ((ra - rh - home_by_league[g["league"]] - coef * gap) / 400))
        out.append(e if n.get(h, 0) >= rb.MIN_GAMES and n.get(a, 0) >= rb.MIN_GAMES else None)
        d = k * (g["y"] - e)
        r[h], r[a] = rh + d, ra - d
        n[h], n[a] = n.get(h, 0) + 1, n.get(a, 0) + 1
    return out


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    gaps = rest_gap(games)
    home, tries = ri.best_home_by_league(games, False)
    cache = {c: replay(games, home, c, gaps) for c in COEFS}
    tries += len(cache)
    tuned = {c: rb.evaluate(games, p, rb.TUNE_YEARS) for c, p in cache.items()}
    ok = {c: t for c, t in tuned.items() if t["n"] >= ri.MIN_N}
    best = min(ok, key=lambda c: ok[c]["brier"]) if ok else None
    plain = rb.evaluate(games, cache[0.0], test, base)
    held = rb.evaluate(games, cache[best], test, base) if best is not None else None
    live = rb.evaluate(games, rb.replay(games, 24.0, 0.0), test, base)
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby rest-days study (days since last game)", "",
         f"Made {made} by `backtest/rugby_rest_study.py` (framework#344). {len(games)} games, final scores only "
         f"(ESPN). Settings tried: **{tries}**; chosen on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on "
         f"**{test[0]}-{test[1]} only**.", "",
         f"| Rule (held-out years) | Games | Brier | Brier flat baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|"]
    rows = [("Live board: K24, no home edge", live), ("Per-league home edge, no rest term", plain)]
    if held and best > 0:
        rows.append((f"Per-league home edge + rest term {best:.0f} Elo/day", held))
    for nm, r in rows:
        L.append(f"| {nm} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |" if r["n"]
                 else f"| {nm} | 0 | PENDING | PENDING | PENDING |")
    L += ["", "## Reading", ""]
    if held and plain["n"]:
        gain = plain["brier"] - held["brier"]
        L.append(f"- Rest term {best:.0f} Elo/day changed held-out Brier by {gain:+.4f} vs no rest term "
                 + ("(a shadow candidate, to be confirmed on the shadow board's record)." if gain > 0.0005 and best > 0
                    else "(no real help: rest days are not worth a shadow)."))
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
