"""
xG STUDY (improvement #3, Architect 2026-10-02).

Does an expected-goals (xG) team rating add information the market, our goals
model (Dixon-Coles) and their blend don't already have?

Data: Understat per-match xG (top 5 leagues) joined to football-data results
and opening prices by date + both team names. Walk-forward: every rating uses
only matches BEFORE the match it predicts. xG rating = time-weighted
(240-day half-life) xG created/allowed per team, league home/away scale,
Poisson grid -> 1X2 + Over 2.5.

Compared, per test season:
  * accuracy (Brier, 1X2) of MARKET, DC, XG and blends;
  * the production pick rule (anchored: market + 0.25 x (model - market),
    one pick per match, band 1.20-2.00) with model = DC (today) vs
    model = avg(DC, XG) vs model = XG.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from scipy.stats import poisson

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from data.flashscore_results import _sim
from data.football_data_source import load_league
from engine.dixon_coles import predict

LEAGUES = {"Premier League": "EPL", "La Liga": "La_liga", "Bundesliga": "Bundesliga",
           "Serie A": "Serie_A", "Ligue 1": "Ligue_1"}
SEASONS = [("2324", "2425", 2023, 2024), ("2425", "2526", 2024, 2025)]
CACHE = Path(__file__).parent / "cache" / "understat"
HALF_LIFE = 240.0
BAND = (1.20, 2.00)
W = 0.25
G = np.arange(11)


def understat(code: str, year: int) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{code}_{year}.json"
    if not f.exists():
        req = urllib.request.Request(f"https://understat.com/getLeagueData/{code}/{year}",
                                     headers={"User-Agent": "Mozilla/5.0",
                                              "X-Requested-With": "XMLHttpRequest",
                                              "Accept-Encoding": "gzip"})
        raw = urllib.request.urlopen(req, timeout=40).read()
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        f.write_bytes(raw)
    d = json.loads(f.read_text(encoding="utf-8"))
    out = []
    for m in d["dates"]:
        if not m.get("isResult"):
            continue
        out.append({"date": m["datetime"][:10], "home": m["h"]["title"], "away": m["a"]["title"],
                    "xh": float(m["xG"]["h"]), "xa": float(m["xG"]["a"])})
    return out


def xg_probs(xmatches, cut, home_us, away_us):
    att, dfn, ws = defaultdict(float), defaultdict(float), defaultdict(float)
    hx = ax = wt = 0.0
    cutd = date.fromisoformat(cut)
    for m in xmatches:
        if m["date"] >= cut:
            continue
        w = 0.5 ** ((cutd - date.fromisoformat(m["date"])).days / HALF_LIFE)
        att[m["home"]] += w * m["xh"]; dfn[m["home"]] += w * m["xa"]; ws[m["home"]] += w
        att[m["away"]] += w * m["xa"]; dfn[m["away"]] += w * m["xh"]; ws[m["away"]] += w
        hx += w * m["xh"]; ax += w * m["xa"]; wt += w
    if wt == 0 or ws[home_us] < 3 or ws[away_us] < 3:
        return None
    avg = (hx + ax) / (2 * wt)
    lam_h = (hx / wt) * (att[home_us] / ws[home_us] / avg) * (dfn[away_us] / ws[away_us] / avg)
    lam_a = (ax / wt) * (att[away_us] / ws[away_us] / avg) * (dfn[home_us] / ws[home_us] / avg)
    m = np.outer(poisson.pmf(G, lam_h), poisson.pmf(G, lam_a))
    m /= m.sum()
    tot = np.add.outer(G, G)
    return (float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum()),
            float(m[tot > 2].sum()))


def _devig(ps):
    inv = [1 / p for p in ps]
    s = sum(inv)
    return [i / s for i in inv]


def map_names(fd_teams, us_teams):
    out = {}
    for t in fd_teams:
        best = max(us_teams, key=lambda u: _sim(t, u))
        if _sim(t, best) >= 0.70:
            out[t] = best
    return out


def run():
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="",
                         refit_every_days=14, max_history_matches=800, half_life_days=HALF_LIFE)
    S = defaultdict(lambda: defaultdict(float))
    for carry_s, test_s, y0, y1 in SEASONS:
        for lg, code in LEAGUES.items():
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
                xm = understat(code, y0) + understat(code, y1)
            except Exception as e:
                print(f"skip {lg} {test_s}: {e}", flush=True)
                continue
            us_teams = {m["home"] for m in xm} | {m["away"] for m in xm}
            names = map_names({r.home_team for r in carry + test} | {r.away_team for r in carry + test},
                              us_teams)
            hist = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            warm = None
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                model, _ = get_model(lg, cut, hist, cfg, warm) if block else (None, None)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                for r in block:
                    o = r.odds
                    if not o or not all((o.home.open, o.draw.open, o.away.open,
                                         o.over25.open, o.under25.open)):
                        continue
                    if r.home_team not in names or r.away_team not in names:
                        continue
                    p = predict(model, r.home_team, r.away_team)
                    x = xg_probs(xm, r.date, names[r.home_team], names[r.away_team])
                    if p is None or x is None:
                        continue
                    mk = _devig([o.home.open, o.draw.open, o.away.open])
                    mo = _devig([o.over25.open, o.under25.open])[0]
                    y = [r.fthg > r.ftag, r.fthg == r.ftag, r.ftag > r.fthg]
                    srcs = {"MARKET": mk, "DC": [p.p_home, p.p_draw, p.p_away], "XG": list(x[:3])}
                    srcs["DC+XG"] = [(a + b) / 2 for a, b in zip(srcs["DC"], srcs["XG"])]
                    for k, v in srcs.items():
                        S[(test_s, k)]["n"] += 1
                        S[(test_s, k)]["brier"] += sum((a - b) ** 2 for a, b in zip(v, y))
                    # production-style pick (1X2 + O/U 2.5 in band), anchored
                    t = r.fthg + r.ftag
                    base = {"HOME": (mk[0], o.home.open, y[0]), "DRAW": (mk[1], o.draw.open, y[1]),
                            "AWAY": (mk[2], o.away.open, y[2]), "OVER": (mo, o.over25.open, t > 2),
                            "UNDER": (1 - mo, o.under25.open, t <= 2)}
                    models = {"DC": {"HOME": p.p_home, "DRAW": p.p_draw, "AWAY": p.p_away,
                                     "OVER": p.p_over_25, "UNDER": 1 - p.p_over_25},
                              "XG": {"HOME": x[0], "DRAW": x[1], "AWAY": x[2], "OVER": x[3],
                                     "UNDER": 1 - x[3]}}
                    models["DC+XG"] = {k: (models["DC"][k] + models["XG"][k]) / 2 for k in base}
                    for name, mod in models.items():
                        cands = [(base[k][0] + W * (mod[k] - base[k][0]), k) for k in base
                                 if BAND[0] <= base[k][1] <= BAND[1]]
                        if not cands:
                            continue
                        _, k = max(cands)
                        mp, price, won = base[k]
                        s = S[(test_s, "PICK " + name)]
                        s["n"] += 1
                        s["w"] += won
                        s["pnl"] += (price - 1) if won else -1
            print(f"done {lg} {test_s}", flush=True)
    return S


def report(S) -> str:
    L = ["xG STUDY — top 5 leagues, walk-forward", ""]
    for s in sorted({k[0] for k in S}):
        L.append(f"=== test season {s}")
        for k in ("MARKET", "DC", "XG", "DC+XG"):
            v = S[(s, k)]
            L.append(f"   Brier 1X2  {k:7} {v['brier']/max(v['n'],1):.4f}  (n={int(v['n'])})")
        for k in ("PICK DC", "PICK XG", "PICK DC+XG"):
            v = S[(s, k)]
            n = max(v["n"], 1)
            L.append(f"   {k:11} n={int(v['n'])} hit={100*v['w']/n:.1f}% roi={100*v['pnl']/n:+.2f}%")
    return "\n".join(L)


if __name__ == "__main__":
    out = report(run())
    print(out)
    Path(__file__).with_name("XG_STUDY.md").write_text("```\n" + out + "\n```\n", encoding="utf-8")
