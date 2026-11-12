"""
MARKET RATES STUDY - the league + team side-rate model (engine/market_rates.py) on every side of every market in
every sport we cover, walk-forward (Architect 2026-11-12: "run this model for all the markets ... in all the sports").

For every graded game, in kick-off order, BEFORE it is added to the counts:
  - every priced side is a baseline bet (what betting everything returns at SportyBet's price);
  - every side whose two teams are known gets the model's chance p; it is a 'value' bet when p x price - 1 > 0;
  - the game's single best value side (engine/market_rates.best_side) is graded as a paper pick;
  - where the market is a clean two-way one, p is scored against the market's own de-margined chance (Brier).
Reported per sport, and per market for the biggest ones. A side or band counts only if its whole 90% range is
above zero AND the model's Brier beats the market's; every slice tried is counted.
Output: backtest/MARKET_RATES_STUDY.md.  Usage: python backtest/market_rates_study.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

from league_profile_study import fmt, roi  # noqa: E402

from engine import market_rates as mr  # noqa: E402

REPORT = ROOT / "backtest" / "MARKET_RATES_STUDY.md"
BANDS = (("under 5%", 0.0, 0.05), ("5-10%", 0.05, 0.10), ("10-20%", 0.10, 0.20), ("over 20%", 0.20, 99.0))


def band(v: float) -> str:
    return next(n for n, lo, hi in BANDS if lo <= v < hi)


def walk(games: list[dict]) -> dict:
    rates = mr.Rates()
    st: dict = defaultdict(lambda: {"games": 0, "base": [], "value": defaultdict(list), "best": defaultdict(list),
                                    "brier": [0, 0.0, 0.0], "fam": defaultdict(list)})
    for g in games:
        s = st[g["sport"]]
        s["games"] += 1
        priced = [(k, p) for k, _w, p, _f in g["sides"]]
        won = {k: w for k, w, _p, _f in g["sides"]}
        for key, w, price, fair in g["sides"]:
            if not price or not (mr.PRICE_MIN <= price <= mr.PRICE_MAX):
                continue
            s["base"].append((bool(w), price))
            m = rates.predict(g["sport"], g["league"], g["home"], g["away"], key)
            if not m or not m["teams"]:
                continue
            if fair:
                b = s["brier"]
                b[0] += 1
                b[1] += (m["p"] - w) ** 2
                b[2] += (fair - w) ** 2
            ev = m["p"] * price - 1
            if ev > 0:
                s["value"][band(ev)].append((bool(w), price))
                s["fam"][mr.family(g["sport"], key)].append((bool(w), price))
        best = mr.best_side(rates, g, priced)
        if best:
            s["best"][band(best["value"])].append((bool(won[best["key"]]), best["price"]))
        rates.add(g)
    return st


def main(argv: list[str] | None = None) -> int:
    games = mr.all_games()
    st = walk(games)
    now = datetime.now(UTC)
    slices = 0
    md = ["# Market rates study: every market, every sport", "",
          f"Generated {now:%Y-%m-%d %H:%M} UTC by `backtest/market_rates_study.py`. RECORD / PAPER ONLY. "
          "The model: each side's rate so far in the league, moved by the home team's home record and the away "
          f"team's away record of that same side (shrink {mr.SHRINK:g}, league {mr.MIN_LEAGUE}+ games, each team "
          f"{mr.MIN_TEAM}+), walk-forward. Prices are SportyBet's last before kick-off, {mr.PRICE_MIN}-{mr.PRICE_MAX}.", "",
          "| Sport | Games | Baseline: every side | Model value sides | Best side per game | Brier model / market (n) |",
          "|---|---|---|---|---|---|"]
    for sport in sorted(st, key=lambda k: -st[k]["games"]):
        s = st[sport]
        allv = [x for v in s["value"].values() for x in v]
        allb = [x for v in s["best"].values() for x in v]
        b = s["brier"]
        br = f"{b[1] / b[0]:.4f} / {b[2] / b[0]:.4f} ({b[0]:,})" if b[0] else "PENDING"
        r0, r1, r2 = roi(s["base"]), roi(allv), roi(allb)
        cell = lambda r: (f"{r['n']:,} bets, {r['roi']:+.1%} ({r['lo']:+.1%} to {r['hi']:+.1%})"  # noqa: E731
                          if r.get("n") else "0 bets")
        md.append(f"| {sport} | {s['games']:,} | {cell(r0)} | {cell(r1)} | {cell(r2)} | {br} |")
    md += ["", "## Best side per game, by the size of the claimed gap", "",
           "| Sport | Gap | Bets | Hit | ROI | 90% range |", "|---|---|---|---|---|---|"]
    for sport in sorted(st, key=lambda k: -st[k]["games"]):
        for name, *_ in BANDS:
            bets = st[sport]["best"].get(name) or []
            if bets:
                slices += 1
                md.append(f"| {sport} | {name} | {fmt(roi(bets))} |")
    md += ["", "## The biggest markets: every side the model calls value", "",
           "| Sport | Market | Bets | Hit | ROI | 90% range |", "|---|---|---|---|---|---|"]
    fams = [(sport, f, bets) for sport, s in st.items() for f, bets in s["fam"].items() if len(bets) >= 150]
    fams.sort(key=lambda x: -len(x[2]))
    for sport, f, bets in fams[:40]:
        slices += 1
        md.append(f"| {sport} | `{f}` | {fmt(roi(bets))} |")
    winners = [(sport, f) for sport, f, bets in fams[:40] if roi(bets).get("lo", -1) > 0]
    md += ["", f"**Slices tried: {slices}.** About {0.05 * slices:.1f} would show a range wholly above zero by luck "
           f"alone. Markets whose whole range is above zero: {', '.join(f'{s} {f}' for s, f in winners) or 'none'}.", "",
           "## Reading",
           "- The Brier column is the real test: if the model's chance is not closer to what happened than the "
           "market's own de-margined chance, its 'value' is the model's error, and the value bets lose about what "
           "the baseline loses (the margin).",
           "- The football and basketball record starts 2026-10-08; the other ten sports' boards started "
           "2026-11-06, so their rows are thin and read as a start, not an answer. The paper board keeps grading "
           "every sport; a sport or market goes to the Architect only with 100+ graded paper picks whose 90% range "
           "is above zero.", ""]
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}: {len(games)} games, {len(st)} sports")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
