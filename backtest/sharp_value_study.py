"""
SHARP-VALUE STUDY — does betting a soft book only when it beats the SHARP
book's fair price make money?

Pinnacle (PS*) is the sharpest widely quoted bookmaker: its prices, with the
margin removed, are the best available estimate of the true probability.
bet365 (B365*) stands in for a soft book like SportyBet (SportyBet history is
not published). A bet is taken only when the soft price beats Pinnacle's fair
price by at least EDGE, inside the Architect's 1.20-2.00 band, at OPENING
prices (what you can actually take when the board is built). Profit is
measured at the soft price that was actually available; flat 1-unit stakes.

Markets: 1X2 and Over/Under 2.5. No model is involved — this measures pure
price disagreement between a soft and a sharp book.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.football_data_source import DEFAULT_CACHE_DIR, _parse_date

BAND = (1.20, 2.00)
EDGES = (0.00, 0.02, 0.03, 0.05)
FILES = sorted(p for p in Path(DEFAULT_CACHE_DIR).glob("*_[0-9][0-9][0-9][0-9].csv"))


def _f(row, k):
    try:
        v = float(row.get(k) or "")
        return v if v > 1 else None
    except ValueError:
        return None


def _devig(ps):
    inv = [1 / p for p in ps]
    s = sum(inv)
    return [i / s for i in inv]


def run():
    res = defaultdict(list)       # (season, edge) -> [(date, pnl)]
    for path in FILES:
        season = path.stem[-4:]
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                try:
                    hg, ag = int(row["FTHG"]), int(row["FTAG"])
                    d = _parse_date(row["Date"])
                except (KeyError, ValueError, TypeError):
                    continue
                sharp = [_f(row, k) for k in ("PSH", "PSD", "PSA")]
                soft = [_f(row, k) for k in ("B365H", "B365D", "B365A")]
                sharp_ou = [_f(row, k) for k in ("P>2.5", "P<2.5")]
                soft_ou = [_f(row, k) for k in ("B365>2.5", "B365<2.5")]
                cands = []
                if all(sharp) and all(soft):
                    fair = _devig(sharp)
                    won = [hg > ag, hg == ag, ag > hg]
                    cands += [(fair[i], soft[i], won[i]) for i in range(3)]
                if all(sharp_ou) and all(soft_ou):
                    fair = _devig(sharp_ou)
                    won = [hg + ag > 2, hg + ag <= 2]
                    cands += [(fair[i], soft_ou[i], won[i]) for i in range(2)]
                for edge in EDGES:
                    best = None
                    for fair_p, price, won in cands:
                        if not (BAND[0] <= price <= BAND[1]):
                            continue
                        ev = fair_p * price - 1
                        if ev >= edge and (best is None or ev > best[0]):
                            best = (ev, price, won)
                    if best:
                        res[(season, edge)].append((d, (best[1] - 1) if best[2] else -1.0))
    return res


def _stats(pairs):
    pnls = [p for _, p in sorted(pairs)]
    n = len(pnls)
    if not n:
        return "n=0"
    w = sum(1 for x in pnls if x > 0)
    bank = peak = dd = 0.0
    for x in pnls:
        bank += x
        peak = max(peak, bank)
        dd = max(dd, peak - bank)
    return (f"n={n:5d} hit={100*w/n:5.1f}% roi={100*sum(pnls)/n:+6.2f}% "
            f"profit={sum(pnls):+8.2f}u maxDD={dd:6.2f}u")


def report(res) -> str:
    L = ["SHARP-VALUE STUDY — bet365 price vs Pinnacle fair price, band 1.20-2.00,",
         "opening prices, flat 1u, one bet per match (largest edge)", ""]
    for edge in EDGES:
        L.append(f"edge >= {edge:.0%}")
        allp = []
        for s in sorted({s for s, _ in res}):
            allp += res.get((s, edge), [])
            L.append(f"   {s}: {_stats(res.get((s, edge), []))}")
        L.append(f"   ALL : {_stats(allp)}")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    out = report(run())
    print(out)
    Path(__file__).with_name("SHARP_VALUE_STUDY.md").write_text("```\n" + out + "\n```\n",
                                                                encoding="utf-8")
