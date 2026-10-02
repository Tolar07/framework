"""
MARKET STUDY — where is a soft bookmaker generous, and does price movement
predict results?  (Architect 2026-10-02: "find more ways to improve")

Data: football-data.co.uk files in data/cache (seasons 23/24, 24/25, 25/26),
every league we cover that carries both bet365 and Pinnacle prices, opening
AND closing, for 1X2, Over/Under 2.5 and Asian handicap.

bet365 OPENING price  = a soft bookmaker's price at the time we'd pick
                        (stand-in for SportyBet, which publishes no history)
Pinnacle CLOSING price = the sharpest estimate of the true chance (margin
                        removed proportionally)

Q1 SOFT SPOTS. For every outcome priced 1.20–2.00, its "sharp EV" = bet365
   opening price x Pinnacle closing fair chance - 1. Grouped by market, odds
   band, league and favourite/underdog. A segment is only trusted if it is
   positive on 23/24+24/25 AND again on 25/26 (out of sample) — in sharp EV
   and in real profit.
Q2 DRIFT. bet365 opening vs closing on the same outcome: when the price
   drifts out (or shortens) before kickoff, how does the outcome do vs what
   the opening price implied?
Q3 OUR RULE. Per match pick the likeliest in-band outcome (what the board
   does) vs the value-aware rule (within 4 pts, best price); sharp EV + ROI.

Run:  python backtest/market_study.py   (writes backtest/MARKET_STUDY.md)
"""
from __future__ import annotations

import csv
import glob
import math
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASONS = ("2324", "2425", "2526")
TRAIN, TEST = ("2324", "2425"), ("2526",)
LO, HI = 1.20, 2.00


def f(x):
    try:
        v = float(x)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def devig(*odds):
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [i / s for i in inv]


def ah_payoff(line: float, gd: float) -> float:
    """Return multiplier class for a HOME Asian handicap bet at `line`:
    1 = win, 0.5 = half win, 0 = push, -0.5 = half loss, -1 = loss."""
    def whole(l):
        d = gd + l
        return 1.0 if d > 0 else (0.0 if d == 0 else -1.0)
    if abs(line * 4 - round(line * 4)) < 1e-9 and abs(line * 2 - round(line * 2)) > 1e-9:
        return (whole(line - 0.25) + whole(line + 0.25)) / 2      # quarter line
    return whole(line)


def pl(price: float, outcome: float) -> float:
    """Profit at 1 unit for outcome class (1 win, 0.5 half win, 0 push, -0.5, -1)."""
    if outcome >= 1:
        return price - 1
    if outcome == 0.5:
        return (price - 1) / 2
    if outcome == 0:
        return 0.0
    if outcome == -0.5:
        return -0.5
    return -1.0


def bucket(p):
    for lo, hi in ((1.20, 1.35), (1.35, 1.50), (1.50, 1.75), (1.75, 2.01)):
        if lo <= p < hi:
            return f"{lo:.2f}-{min(hi, 2.0):.2f}"
    return None


def load():
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "cache", "*.csv"))):
        name = os.path.basename(path)[:-4]
        season = name[-4:]
        if season not in SEASONS:
            continue
        league = name[:-5].replace("_", " ")
        with open(path, encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                try:
                    hg, ag = int(r["FTHG"]), int(r["FTAG"])
                except (KeyError, TypeError, ValueError):
                    continue
                rows.append((season, league, hg, ag, r))
    return rows


def outcomes(season, league, hg, ag, r):
    """Yield dicts for each priced outcome of one match."""
    gd, tg = hg - ag, hg + ag
    psc = [f(r.get(k)) for k in ("PSCH", "PSCD", "PSCA")]
    bo = [f(r.get(k)) for k in ("B365H", "B365D", "B365A")]
    bc = [f(r.get(k)) for k in ("B365CH", "B365CD", "B365CA")]
    if all(psc) and all(bo):
        fair = devig(*psc)
        opn = devig(*bo)
        res = [gd > 0, gd == 0, gd < 0]
        fav = max(range(3), key=lambda i: opn[i])
        for i, mk in enumerate(("Home win", "Draw", "Away win")):
            yield {"market": mk, "price": bo[i], "close": bc[i] if all(bc) else None,
                   "sharp": fair[i], "soft": opn[i], "out": 1.0 if res[i] else -1.0,
                   "fav": i == fav, "season": season, "league": league}
    pco = [f(r.get("PC>2.5")), f(r.get("PC<2.5"))]
    bou = [f(r.get("B365>2.5")), f(r.get("B365<2.5"))]
    bcu = [f(r.get("B365C>2.5")), f(r.get("B365C<2.5"))]
    if all(pco) and all(bou):
        fair = devig(*pco)
        opn = devig(*bou)
        for i, mk in enumerate(("Over 2.5", "Under 2.5")):
            hit = tg > 2.5 if i == 0 else tg < 2.5
            yield {"market": mk, "price": bou[i], "close": bcu[i] if all(bcu) else None,
                   "sharp": fair[i], "soft": opn[i], "out": 1.0 if hit else -1.0,
                   "fav": opn[i] > 0.5, "season": season, "league": league}
    # Asian handicap: only when the opening and closing lines are the same,
    # so Pinnacle's closing price is for the very bet bet365 offered.
    try:
        lo_, lc_ = float(r.get("AHh")), float(r.get("AHCh"))
    except (TypeError, ValueError):
        lo_ = lc_ = None
    bah = [f(r.get("B365AHH")), f(r.get("B365AHA"))]
    pah = [f(r.get("PCAHH")), f(r.get("PCAHA"))]
    bahc = [f(r.get("B365CAHH")), f(r.get("B365CAHA"))]
    if lo_ is not None and lo_ == lc_ and all(bah) and all(pah):
        fair = devig(*pah)
        opn = devig(*bah)
        home = ah_payoff(lo_, gd)
        for i, mk in enumerate(("AH home", "AH away")):
            o = home if i == 0 else -home
            yield {"market": mk, "price": bah[i], "close": bahc[i] if all(bahc) else None,
                   "sharp": fair[i], "soft": opn[i], "out": o, "fav": opn[i] > 0.5,
                   "season": season, "league": league}


def summarise(items):
    n = len(items)
    if not n:
        return None
    ev = sum(x["price"] * x["sharp"] - 1 for x in items) / n
    roi = sum(pl(x["price"], x["out"]) for x in items) / n
    wins = sum(x["out"] > 0 for x in items)
    return {"n": n, "ev": ev, "roi": roi, "hit": wins / n}


def fmt(s):
    if not s:
        return "n=0"
    return (f"n={s['n']:5d}  sharpEV {s['ev']*100:+5.1f}%  ROI {s['roi']*100:+6.1f}%  "
            f"hit {s['hit']*100:4.1f}%")


def main():
    rows = load()
    all_o = [o for row in rows for o in outcomes(*row)]
    band = [o for o in all_o if LO <= o["price"] <= HI]
    L = ["# MARKET STUDY — soft bookmaker vs sharp close, price drift, our pick rule", "",
         f"Matches: {len(rows)} · priced outcomes: {len(all_o)} · in the 1.20–2.00 band: {len(band)}",
         "bet365 opening = soft price we'd take; Pinnacle closing (margin removed) = truth.",
         "sharpEV = soft price x sharp fair chance - 1. ROI = real profit at 1 unit.", ""]

    # --- calibration benchmark (1X2) ---
    def brier(key):
        tot = n = 0
        for o in all_o:
            if o["market"] in ("Home win", "Draw", "Away win"):
                tot += (o[key] - (1 if o["out"] > 0 else 0)) ** 2
                n += 1
        return tot / n
    L += ["## Benchmark: how good is each price as a probability (1X2 Brier, lower = better)",
          f"- bet365 opening (margin removed): {brier('soft'):.4f}",
          f"- Pinnacle closing (margin removed): {brier('sharp'):.4f}", ""]

    # --- Q1 soft spots: market x odds band, train vs test ---
    L += ["## Q1 · Where is the soft price generous? (market x odds band, 1.20–2.00)",
          "| Segment | 23/24+24/25 (learn) | 25/26 (test) |", "|---|---|---|"]
    seg = defaultdict(list)
    for o in band:
        seg[(o["market"], bucket(o["price"]))].append(o)
    keep = []
    for k in sorted(seg):
        tr = summarise([o for o in seg[k] if o["season"] in TRAIN])
        te = summarise([o for o in seg[k] if o["season"] in TEST])
        L.append(f"| {k[0]} @{k[1]} | {fmt(tr)} | {fmt(te)} |")
        if tr and te and tr["n"] >= 100 and te["n"] >= 50 and tr["ev"] > 0 and te["ev"] > 0:
            keep.append((k, tr, te))
    L += ["", "Segments positive in sharp EV in BOTH periods (n>=100 learn, >=50 test): "
          + (", ".join(f"{k[0]} @{k[1]} (test ROI {te['roi']*100:+.1f}%)" for k, tr, te in keep)
             if keep else "**none**"), ""]

    # favourites vs underdogs, leagues
    L += ["## Q1b · Favourite vs underdog, by league (1X2 + O/U + AH in band)",
          "| League | learn | test |", "|---|---|---|"]
    lg = defaultdict(list)
    for o in band:
        lg[o["league"]].append(o)
    good_lg = []
    for k in sorted(lg):
        tr = summarise([o for o in lg[k] if o["season"] in TRAIN])
        te = summarise([o for o in lg[k] if o["season"] in TEST])
        L.append(f"| {k} | {fmt(tr)} | {fmt(te)} |")
        if tr and te and tr["ev"] > -0.01 and te["ev"] > -0.01 and te["n"] >= 50:
            good_lg.append(k)
    L += ["", "Leagues where the soft price is near or above the sharp close in both periods: "
          + (", ".join(good_lg) or "none"), ""]

    # --- Q2 drift ---
    L += ["## Q2 · Price movement before kickoff (bet365 open -> close, in band)",
          "| Move | n | won | opening implied | ROI at opening price |", "|---|---|---|---|---|"]
    mv = defaultdict(list)
    for o in band:
        if not o["close"]:
            continue
        d = o["close"] / o["price"] - 1
        k = ("shortened 5%+" if d <= -0.05 else "shortened 2-5%" if d <= -0.02 else
             "steady (±2%)" if d < 0.02 else "drifted 2-5%" if d < 0.05 else "drifted 5%+")
        mv[k].append(o)
    for k in ("shortened 5%+", "shortened 2-5%", "steady (±2%)", "drifted 2-5%", "drifted 5%+"):
        xs = mv.get(k, [])
        if not xs:
            continue
        won = sum(o["out"] > 0 for o in xs) / len(xs)
        imp = sum(o["soft"] for o in xs) / len(xs)
        roi = sum(pl(o["price"], o["out"]) for o in xs) / len(xs)
        L.append(f"| {k} | {len(xs)} | {won*100:.1f}% | {imp*100:.1f}% | {roi*100:+.1f}% |")
    L.append("")

    # --- Q3 our rule ---
    L += ["## Q3 · Our pick rule on these markets (one pick per match)",
          "| Rule | learn | test |", "|---|---|---|"]
    picks_top, picks_val = [], []
    for row in rows:
        os_ = [o for o in outcomes(*row) if LO <= o["price"] <= HI and o["soft"] >= 0.5]
        if not os_:
            continue
        top = max(os_, key=lambda o: o["soft"])
        near = [o for o in os_ if o["soft"] >= top["soft"] - 0.04]
        val = max(near, key=lambda o: (o["soft"] * o["price"], o["soft"]))
        picks_top.append(top)
        picks_val.append(val)
    for name, ps in (("Likeliest in-band outcome", picks_top),
                     ("Value-aware (within 4 pts, best price)", picks_val)):
        L.append(f"| {name} | {fmt(summarise([o for o in ps if o['season'] in TRAIN]))} | "
                 f"{fmt(summarise([o for o in ps if o['season'] in TEST]))} |")
    L.append("")
    open(os.path.join(ROOT, "backtest", "MARKET_STUDY.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
