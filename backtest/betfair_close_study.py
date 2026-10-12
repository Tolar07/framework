"""
BETFAIR CLOSING-LINE STUDY (Architect 2026-10-12: "write the Betfair
closing-line study").

Does the model know anything the market doesn't? It is measured against the
sharpest free price there is: the Betfair Exchange CLOSING odds that
football-data.co.uk publishes (BFECH/BFECD/BFECA, BFEC>2.5/BFEC<2.5), margin
removed. Results alone are too noisy to answer this at our sample sizes;
the closing exchange price is the market's final, best-informed number.

Prices compared, all from the same football-data file:
  model      the production Dixon-Coles fit (last + current season, 240-day
             half-life, walk-forward, refit every 14 days; nothing on or after
             the cut is seen). Over 2.5 also shown calibrated as production
             does (engine/calibration.py). Goals model only: the top-5-league
             xG blend (order 19) is not in this study.
  soft       bet365 at collection time (B365*, ~Friday for the weekend,
             ~Tuesday midweek), margin removed: the stand-in for SportyBet when
             the board is built (SportyBet history is not published).
  bf_early   Betfair Exchange at the same collection time (BFE*).
  bf_close   Betfair Exchange closing (BFEC*): the yardstick.
  anchored   production's pick chance: 75% soft + 25% model (order 18).

Questions:
  A. Who forecasts results best? Log loss and Brier on 1X2 and O/U 2.5.
  B. Does the model add anything to the close? p = close + w(model - close).
  C. Does the model know where the line goes? When the model is above the
     soft price, does the close move towards it?
  D. Value against the close of bets taken at the soft price:
     EV_close = bf_close chance x soft price - 1 (positive = beat the close).
     Production-style picks vs model-edge picks vs Betfair-lag picks.

Run:  python backtest/betfair_close_study.py           (fetch + fit, slow)
      python backtest/betfair_close_study.py --reuse   (re-analyse saved records)
Writes backtest/BETFAIR_CLOSE_STUDY.md.
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from data.football_data_source import (
    DEFAULT_CACHE_DIR,
    LEAGUE_CODES,
    _clean_row,
    _parse_date,
    load_league,
)
from engine import calibration as cal
from engine.dixon_coles import predict

# Main-endpoint leagues the board covers (the Extra files carry no Betfair columns).
LEAGUES = [lg for lg, code in LEAGUE_CODES.items() if code]
# (carry-in season, test season): the model always fits on the season before too.
SEASONS = [("2324", "2425"), ("2425", "2526"), ("2526", "2627")]
BAND = (1.20, 2.00)
ANCHOR = 0.75                     # order 18: 75% market + 25% model
EDGES = (0.02, 0.05, 0.10)
BLEND_W = (0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0)
RECORDS = Path(__file__).parent / "cache" / "betfair_close_records.json"
OUT = Path(__file__).with_name("BETFAIR_CLOSE_STUDY.md")

# outcome -> (soft cols, exchange early cols, exchange close cols) per market
X12 = (("B365H", "B365D", "B365A"), ("BFEH", "BFED", "BFEA"), ("BFECH", "BFECD", "BFECA"))
OU = (("B365>2.5", "B365<2.5"), ("BFE>2.5", "BFE<2.5"), ("BFEC>2.5", "BFEC<2.5"))


def _f(row, k):
    try:
        v = float(row.get(k) or "")
        return v if v > 1 else None
    except ValueError:
        return None


def _devig(ps):
    if not ps or any(p is None for p in ps):
        return None
    inv = [1 / p for p in ps]
    s = sum(inv)
    return [i / s for i in inv]


def _raw_rows(league, season):
    """(date, home, away) -> raw CSV row, from the file load_league cached."""
    path = Path(DEFAULT_CACHE_DIR) / f"{league.replace(' ', '_')}_{season}.csv"
    out = {}
    for raw in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))):
        row = _clean_row(raw)
        try:
            out[(_parse_date(row["Date"]), row["HomeTeam"].strip(), row["AwayTeam"].strip())] = row
        except (KeyError, ValueError, AttributeError):
            continue
    return out


def collect() -> list[dict]:
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="",
                         refit_every_days=14, max_history_matches=800, half_life_days=240.0)
    recs = []
    for carry_s, test_s in SEASONS:
        for lg in LEAGUES:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
                raw = _raw_rows(lg, test_s)
            except Exception as e:
                print(f"skip {lg} {test_s}: {e}", flush=True)
                continue
            hist = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            warm, kept = None, 0
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                model, _ = get_model(lg, cut, hist, cfg, warm) if block else (None, None)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                for r in block:
                    row = raw.get((r.date, r.home_team, r.away_team))
                    p = predict(model, r.home_team, r.away_team) if row else None
                    if p is None:
                        continue
                    rec = {"season": test_s, "league": lg, "date": r.date,
                           "hg": r.fthg, "ag": r.ftag,
                           "model": [p.p_home, p.p_draw, p.p_away, p.p_over_25]}
                    for name, cols in (("x12", X12), ("ou", OU)):
                        soft, early, close = ([_f(row, k) for k in c] for c in cols)
                        rec[name] = {"soft": soft, "early": early, "close": close}
                    recs.append(rec)
                    kept += 1
            print(f"done {lg} {test_s}: {kept} matches", flush=True)
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    RECORDS.write_text(json.dumps(recs), encoding="utf-8")
    return recs


# ---------------------------------------------------------------- analysis --

def _outcomes(rec):
    """Every outcome of the match with its probabilities and soft price.
    Double chance is built from the 1X2 prices, as anchor_study does."""
    m = rec["model"]
    x, ou = rec["x12"], rec["ou"]
    fs, fe, fc = _devig(x["soft"]), _devig(x["early"]), _devig(x["close"])
    os_, oe, oc = _devig(ou["soft"]), _devig(ou["early"]), _devig(ou["close"])
    hg, ag = rec["hg"], rec["ag"]
    t = hg + ag
    out = []
    if fs and fc:
        H, D, A = x["soft"]
        won = (hg > ag, hg == ag, ag > hg)
        for i, name in enumerate(("HOME", "DRAW", "AWAY")):
            out.append((name, m[i], fs[i], fe[i] if fe else None, fc[i], x["soft"][i], won[i]))
        for name, (i, j), price, w in (("DC_1X", (0, 1), 1 / (1 / H + 1 / D), hg >= ag),
                                       ("DC_X2", (1, 2), 1 / (1 / D + 1 / A), ag >= hg),
                                       ("DC_12", (0, 2), 1 / (1 / H + 1 / A), hg != ag)):
            out.append((name, m[i] + m[j], fs[i] + fs[j], fe[i] + fe[j] if fe else None,
                        fc[i] + fc[j], price, w))
    if os_ and oc:
        po = cal.over(2.5, m[3])
        out.append(("OVER25", po, os_[0], oe[0] if oe else None, oc[0], ou["soft"][0], t > 2))
        out.append(("UNDER25", 1 - po, os_[1], oe[1] if oe else None, oc[1], ou["soft"][1], t <= 2))
    return out


def _mean_se(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    mu = sum(xs) / n
    if n < 2:
        return mu, float("nan")
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    return mu, sd / math.sqrt(n)


def _ll(p, won):
    return -math.log(max(min(p if won else 1 - p, 1 - 1e-9), 1e-9))


def forecast_table(recs) -> list[str]:
    """A: log loss / Brier of each forecaster on the same matches."""
    L = ["A. WHO FORECASTS RESULTS BEST — same matches for every row; lower is better",
         "   (1X2: multi-class log loss and Brier; O/U 2.5: binary)", ""]
    for label, key in (("1X2", "x12"), ("Over/Under 2.5", "ou")):
        rows = defaultdict(lambda: [0.0, 0.0])
        n = 0
        for r in recs:
            d = r[key]
            s, e, c = _devig(d["soft"]), _devig(d["early"]), _devig(d["close"])
            if not (s and e and c):
                continue
            if key == "x12":
                y = (r["hg"] > r["ag"], r["hg"] == r["ag"], r["ag"] > r["hg"])
                mod = r["model"][:3]
            else:
                y = (r["hg"] + r["ag"] > 2, r["hg"] + r["ag"] <= 2)
                mod = [r["model"][3], 1 - r["model"][3]]
            cands = {"model": mod, "soft (bet365 early)": s, "Betfair early": e,
                     "Betfair close": c,
                     "anchored 75/25 (production)": [ANCHOR * a + (1 - ANCHOR) * b
                                                     for a, b in zip(s, mod, strict=True)]}
            if key == "ou":
                po = cal.over(2.5, r["model"][3])
                cands["model, O/U calibrated"] = [po, 1 - po]
            n += 1
            for name, p in cands.items():
                k = y.index(True)
                rows[name][0] += -math.log(max(p[k], 1e-9))
                rows[name][1] += sum((pi - yi) ** 2 for pi, yi in zip(p, y, strict=True))
        L.append(f"  {label} — {n} matches")
        for name, (ll, br) in sorted(rows.items(), key=lambda kv: kv[1][0]):
            L.append(f"    {name:30} log loss {ll / n:.4f}   Brier {br / n:.4f}")
        L.append("")
    return L


def blend_table(recs) -> list[str]:
    """B: does mixing the model into the close improve it? Per season."""
    L = ["B. DOES THE MODEL ADD ANYTHING TO THE CLOSE? p = close + w x (model - close),",
         "   1X2 log loss on results by season. If w = 0 is best, the model carries",
         "   nothing the closing price didn't already have.", ""]
    seasons = sorted({r["season"] for r in recs})
    L.append("  " + f"{'w':>6}" + "".join(f"{s:>16}" for s in seasons))
    best = {}
    for w in BLEND_W:
        cells = []
        for s in seasons:
            tot, n = 0.0, 0
            for r in recs:
                c = _devig(r["x12"]["close"])
                if r["season"] != s or not c:
                    continue
                k = (r["hg"] > r["ag"], r["hg"] == r["ag"], r["ag"] > r["hg"]).index(True)
                p = c[k] + w * (r["model"][k] - c[k])
                tot += -math.log(max(p, 1e-9))
                n += 1
            v = tot / n if n else float("nan")
            best.setdefault(s, (v, w))
            if v < best[s][0]:
                best[s] = (v, w)
            cells.append(f"{v:.4f} (n={n})")
        L.append("  " + f"{w:>6}" + "".join(f"{c:>16}" for c in cells))
    L.append("  best w: " + ", ".join(f"{s} -> {best[s][1]}" for s in seasons))
    L.append("")
    return L


def movement_table(recs) -> list[str]:
    """C: model's disagreement with the soft price vs where the close went."""
    L = ["C. DOES THE MODEL KNOW WHERE THE LINE GOES? Every 1X2 and O/U 2.5 outcome,",
         "   bucketed by the model's chance minus the soft (bet365 early) fair chance.",
         "   move = Betfair close fair chance - soft fair chance, in points. If the",
         "   model knows something, move has the same sign as the bucket.", ""]
    buckets = [(-1, -0.10), (-0.10, -0.05), (-0.05, -0.02), (-0.02, 0.02),
               (0.02, 0.05), (0.05, 0.10), (0.10, 1)]
    agg = defaultdict(list)
    xs, ys = [], []
    for r in recs:
        for name, mp, sp, _ep, cp, _price, _w in _outcomes(r):
            if name.startswith("DC_"):
                continue
            gap, move = mp - sp, cp - sp
            xs.append(gap)
            ys.append(move)
            for lo, hi in buckets:
                if lo <= gap < hi:
                    agg[(lo, hi)].append(move)
    for lo, hi in buckets:
        mu, se = _mean_se(agg[(lo, hi)])
        lab = f"model - soft {100*lo:+.0f}..{100*hi:+.0f} pts".replace("-100", "<").replace("+100", ">")
        L.append(f"  {lab:32} n={len(agg[(lo, hi)]):6d}  move {100*mu:+.2f} ± {100*se:.2f} pts")
    if xs:
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
        var = sum((a - mx) ** 2 for a in xs)
        L.append(f"  slope: the close moves {cov / var:+.3f} pts per point of model disagreement "
                 f"({len(xs)} outcomes)")
    L.append("")
    return L


def _pick_production(outs):
    """Production-style: in band, highest anchored chance, >= 50%."""
    c = [o for o in outs if BAND[0] <= o[5] <= BAND[1]]
    if not c:
        return None
    best = max(c, key=lambda o: ANCHOR * o[2] + (1 - ANCHOR) * o[1])
    return best if ANCHOR * best[2] + (1 - ANCHOR) * best[1] >= 0.5 else None


def _pick_edge(outs, idx, edge, need_model=None):
    """In band, chance[idx] x soft price - 1 >= edge; the largest such edge."""
    c = []
    for o in outs:
        if not (BAND[0] <= o[5] <= BAND[1]) or o[idx] is None:
            continue
        ev = o[idx] * o[5] - 1
        if ev >= edge and (need_model is None or o[1] * o[5] - 1 >= need_model):
            c.append((ev, o))
    return max(c, key=lambda t: t[0])[1] if c else None


def value_table(recs) -> list[str]:
    """D: bets at the soft price, valued against the Betfair close."""
    L = ["D. VALUE AGAINST THE BETFAIR CLOSE — one bet per match at the soft (bet365",
         "   early) price, band 1.20-2.00. EV close = Betfair close chance x price - 1:",
         "   the expected return of the bet by the best final estimate. ROI = what",
         "   the results actually paid (noisy). ± is one standard error.", ""]
    strategies = [("production: likeliest, 75/25 anchored", lambda o: _pick_production(o))]
    for e in EDGES:
        strategies.append((f"model edge >= {100*e:.0f}%", lambda o, e=e: _pick_edge(o, 1, e)))
    for e in EDGES:
        strategies.append((f"Betfair-early lag >= {100*e:.0f}% (no model)",
                           lambda o, e=e: _pick_edge(o, 3, e)))
    for e in EDGES:
        strategies.append((f"Betfair lag >= {100*e:.0f}% AND model edge >= {100*e:.0f}%",
                           lambda o, e=e: _pick_edge(o, 3, e, need_model=e)))
    seasons = sorted({r["season"] for r in recs})
    for name, fn in strategies:
        L.append(f"  {name}")
        for s in seasons + ["ALL"]:
            evs, pls, beat = [], [], 0
            for r in recs:
                if s != "ALL" and r["season"] != s:
                    continue
                o = fn(_outcomes(r))
                if o is None:
                    continue
                ev = o[4] * o[5] - 1
                evs.append(ev)
                beat += ev > 0
                pls.append(o[5] - 1 if o[6] else -1.0)
            if not evs:
                L.append(f"    {s:>4}: no bets")
                continue
            me, se = _mean_se(evs)
            mr, sr = _mean_se(pls)
            L.append(f"    {s:>4}: n={len(evs):5d}  EV close {100*me:+6.2f}% ± {100*se:4.2f}  "
                     f"beat close {100*beat/len(evs):5.1f}%  ROI {100*mr:+6.2f}% ± {100*sr:4.2f}")
        L.append("")
    return L


def coverage(recs) -> list[str]:
    n = len(recs)
    has_close = sum(1 for r in recs if _devig(r["x12"]["close"]))
    has_soft = sum(1 for r in recs if _devig(r["x12"]["soft"]))
    by = defaultdict(int)
    for r in recs:
        if _devig(r["x12"]["close"]):
            by[r["season"]] += 1
    return [f"Matches rated by the model: {n}; with Betfair close 1X2: {has_close}; "
            f"with bet365 1X2: {has_soft}",
            "By season (with Betfair close): " + ", ".join(f"{s} {by[s]}" for s in sorted(by)),
            f"Leagues: {', '.join(sorted({r['league'] for r in recs}))}", ""]


def analyse(recs) -> str:
    L = ["BETFAIR CLOSING-LINE STUDY — does the model know anything the market doesn't?",
         "Source: football-data.co.uk (Betfair Exchange closing odds BFEC*, bet365 B365*,",
         "Betfair Exchange early BFE*). Walk-forward production Dixon-Coles fit.", ""]
    L += coverage(recs) + forecast_table(recs) + blend_table(recs) + movement_table(recs)
    L += value_table(recs)
    return "\n".join(L)


if __name__ == "__main__":
    recs = (json.loads(RECORDS.read_text()) if RECORDS.exists() and "--reuse" in sys.argv
            else collect())
    out = analyse(recs)
    print(out)
    OUT.write_text("```\n" + out + "\n```\n", encoding="utf-8")
