"""HALF-TIME STUDY (2026-10-05): can the model price first-half markets?
First-half goals are modelled as Poisson with the full-match rates times the
league's first-half share of goals (learned from earlier matches only), with
the Dixon-Coles low-score correction left off. Walk-forward like production;
scored on first-half 1X2, Over 0.5 and Over 1.5 against football-data's
half-time scores. Results: backtest/HALF_STUDY.md.
Run: python backtest/half_study.py
"""
import csv
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from scipy.stats import poisson

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import refit_cut_dates  # noqa: E402
from backtest.sot_study import PAIRS  # noqa: E402
from backtest.selection_study import GROUPS  # noqa: E402
from data.football_data_source import load_league  # noqa: E402
from engine.dixon_coles import fit, predict  # noqa: E402
from orchestrator import RECENCY_HALF_LIFE_DAYS, RIDGE  # noqa: E402

CACHE = Path(__file__).parent.parent / "data" / "cache"
G = np.arange(8)


def ht_scores(lg, seasons):
    out = {}
    for s in seasons:
        p = CACHE / f"{lg.replace(' ', '_')}_{s}.csv"
        if not p.exists():
            continue
        with open(p, encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                try:
                    out[(r["HomeTeam"].strip(), r["AwayTeam"].strip(), r["Date"].strip())] = (
                        int(r["HTHG"]), int(r["HTAG"]))
                except (KeyError, ValueError):
                    continue
    return out


def fh_probs(lh, la):
    m = np.outer(poisson.pmf(G, lh), poisson.pmf(G, la))
    m /= m.sum()
    tot = np.add.outer(G, G)
    return (float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum()),
            float(m[tot > 0].sum()), float(m[tot > 1].sum()))


def main():
    pairs = {}
    for carry_s, test_s, leagues in GROUPS + PAIRS:
        for lg in leagues:
            pairs[(lg, carry_s, test_s)] = True
    res = defaultdict(list)    # metric -> [(pred, actual)]
    for (lg, carry_s, test_s) in pairs:
        try:
            carry, _ = load_league(lg, carry_s)
            test, _ = load_league(lg, test_s)
        except Exception:
            continue
        ht = ht_scores(lg, (carry_s, test_s))
        if not ht:
            continue
        test = sorted(test, key=lambda r: r.date)
        for cut in refit_cut_dates([r.date for r in test], 14):
            end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
            block = [r for r in test if cut <= r.date < end]
            window = carry + [r for r in test if r.date < cut]
            if not block or len(window) < 50:
                continue
            # league first-half share of goals, from earlier matches only
            fh = ft = 0
            past = [(r, ht.get(_key(r))) for r in window]
            past = [(r, v) for r, v in past if v]
            fh = sum(v[0] + v[1] for _r, v in past)
            ft = sum(r.fthg + r.ftag for r, _v in past)
            if ft == 0:
                continue
            share = fh / ft
            try:
                model = fit(window, half_life_days=RECENCY_HALF_LIFE_DAYS, ref_date=cut,
                            ridge=RIDGE)
            except Exception:
                continue
            for m in block:
                v = ht.get(_key(m))
                p = predict(model, m.home_team, m.away_team)
                if p is None or v is None:
                    continue
                ph, pd, pa, o05, o15 = fh_probs(p.lambda_home * share, p.lambda_away * share)
                hh, aa = v
                y = 0 if hh > aa else 1 if hh == aa else 2
                res["1x2"].append(((ph, pd, pa), y))
                res["o05"].append((o05, hh + aa > 0))
                res["o15"].append((o15, hh + aa > 1))
        print("done", lg, test_s, flush=True)
    n = len(res["1x2"])
    ll = -np.mean([math.log(max(q[y], 1e-9)) for q, y in res["1x2"]])
    base = np.mean([[y == 0, y == 1, y == 2] for _q, y in res["1x2"]], axis=0)
    ll0 = -np.mean([math.log(base[y]) for _q, y in res["1x2"]])
    print(f"\nfirst-half 1X2: n={n} log loss model {ll:.4f} vs base rates {ll0:.4f}; "
          f"draw said {np.mean([q[1] for q, _ in res['1x2']]):.3f} landed {base[1]:.3f}")
    for k in ("o05", "o15"):
        p = np.array([a for a, _ in res[k]])
        y = np.array([b for _, b in res[k]], float)
        print(f"first-half {k}: said {p.mean():.3f} landed {y.mean():.3f} "
              f"Brier {np.mean((p - y) ** 2):.4f} "
              f"vs base {np.mean((y.mean() - y) ** 2):.4f}")
        for lo, hi in ((0, .3), (.3, .45), (.45, .6), (.6, .75), (.75, 1)):
            mk = (p >= lo) & (p < hi)
            if mk.sum():
                print(f"   said {lo:.0%}-{hi:.0%}: n={mk.sum()} landed {y[mk].mean():.1%}")


def _key(r):
    d = r.date
    return (r.home_team, r.away_team, f"{d[8:10]}/{d[5:7]}/{d[0:4]}")


if __name__ == "__main__":
    main()
