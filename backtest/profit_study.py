"""
PROFIT STUDY — which selection rules make money AND protect capital?

Architect 2026-10-02: "we need to make profits ... so we don't lose capital".
Picking the most likely outcome wins ~73% but loses ~6% (the margin is in the
short prices). This study tests deeper signals, walk-forward (every number
uses only matches played BEFORE kickoff), one pick per match, band 1.20-2.00,
at OPENING prices, flat 1-unit stakes:

  Signals
    DC     Dixon-Coles goals model, last + current season, 240-day half-life
           (production fit, engine.dixon_coles)
    ELO    Elo ratings (engine.elo), 1X2 only
    SHOTS  shots-on-target strength: each team's recent SOT created/allowed
           (time-weighted) x the league's goals-per-SOT -> Poisson grid
    MKT    de-vigged opening prices

  Rules
    BANKER70/65/60  straight win, DC and MKT within 7pp, consensus >= x
    TRI65           straight win, DC + ELO + MKT all within 7pp, consensus >= 65%
    SHOTS65         straight win, DC + SHOTS + MKT all within 7pp, consensus >= 65%
    VALUE5          any band market where the DC+SHOTS view beats the price by
                    >= 5% EV while staying within 7pp of MKT

Capital protection: max drawdown (units) and longest losing run, per rule.
Results per test season, so a rule that only worked once is visible.
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from scipy.stats import poisson

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from data.football_data_source import load_league, DEFAULT_CACHE_DIR, _parse_date
from engine import elo as elo_engine
from engine.dixon_coles import predict

GROUPS = [
    ("2324", "2425", ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga",
                      "Ligue 1", "Eredivisie", "Primeira Liga", "Scottish Premiership",
                      "Belgian Pro League"]),
    ("2425", "2526", ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga",
                      "Ligue 1", "Eredivisie", "Primeira Liga", "Scottish Premiership",
                      "Belgian Pro League", "League One", "League Two"]),
    ("2526", "2627", ["League One", "League Two", "National League", "Championship",
                      "Premier League", "La Liga 2", "Serie B", "2. Bundesliga", "Ligue 2"]),
]
BAND = (1.20, 2.00)
AGREE = 0.07
HALF_LIFE = 240.0
RULES = ("BANKER70", "BANKER65", "BANKER60", "TRI65", "SHOTS65", "VALUE5")
G = np.arange(11)


def _devig(ps):
    inv = [1 / p for p in ps]
    s = sum(inv)
    return [i / s for i in inv]


def load_shots(league: str, season: str) -> dict:
    """{(date, home, away): (HST, AST)} from the cached football-data CSV."""
    stem = league.replace(" ", "_")
    path = Path(DEFAULT_CACHE_DIR) / f"{stem}_{season}.csv"
    out = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            try:
                out[(_parse_date(row["Date"]), row["HomeTeam"], row["AwayTeam"])] = (
                    int(row["HST"]), int(row["AST"]))
            except (KeyError, ValueError, TypeError):
                continue
    return out


def shots_probs(hist: list, shots: dict, cut: str, home: str, away: str):
    """1X2 + O2.5 from a time-weighted shots-on-target strength model, using
    only matches before `cut`. None if either team has < 5 matches."""
    att, dfn, wsum = defaultdict(float), defaultdict(float), defaultdict(float)
    hg = ag = hsot = asot = wtot = 0.0
    cutd = date.fromisoformat(cut)
    for r in hist:
        if r.date >= cut:
            continue
        s = shots.get((r.date, r.home_team, r.away_team))
        if not s:
            continue
        w = 0.5 ** ((cutd - date.fromisoformat(r.date)).days / HALF_LIFE)
        h_sot, a_sot = s
        att[r.home_team] += w * h_sot; dfn[r.home_team] += w * a_sot; wsum[r.home_team] += w
        att[r.away_team] += w * a_sot; dfn[r.away_team] += w * h_sot; wsum[r.away_team] += w
        hg += w * r.fthg; ag += w * r.ftag; hsot += w * h_sot; asot += w * a_sot; wtot += w
    if wtot == 0 or wsum[home] < 2.5 or wsum[away] < 2.5 or hsot == 0 or asot == 0:
        return None
    avg = (hsot + asot) / (2 * wtot)
    a_h, d_h = att[home] / wsum[home] / avg, dfn[home] / wsum[home] / avg
    a_a, d_a = att[away] / wsum[away] / avg, dfn[away] / wsum[away] / avg
    lam_h = (hg / hsot) * (hsot / wtot) * a_h * d_a
    lam_a = (ag / asot) * (asot / wtot) * a_a * d_h
    m = np.outer(poisson.pmf(G, lam_h), poisson.pmf(G, lam_a))
    m /= m.sum()
    tot = np.add.outer(G, G)
    return (float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum()),
            float(m[tot > 2].sum()))


def run():
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="",
                         refit_every_days=14, max_history_matches=800,
                         half_life_days=HALF_LIFE)
    seq = defaultdict(list)    # (season, rule) -> [pnl per bet in date order]
    for carry_s, test_s, leagues in GROUPS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception as e:
                print(f"skip {lg} {test_s}: {e}", flush=True)
                continue
            if len(carry) < 100 or len(test) < 20:
                print(f"skip {lg} {test_s}: thin", flush=True)
                continue
            shots = {**load_shots(lg, carry_s), **load_shots(lg, test_s)}
            hist = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            warm = None
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                if not block:
                    continue
                model, _ = get_model(lg, cut, hist, cfg, warm)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                try:
                    elo = elo_engine.rate_through([r for r in hist if r.date < cut], burn_in=3)
                except Exception:
                    elo = None
                for r in block:
                    o = r.odds
                    if not o or not all((o.home.open, o.draw.open, o.away.open,
                                         o.over25.open, o.under25.open)):
                        continue
                    p = predict(model, r.home_team, r.away_team)
                    if p is None:
                        continue
                    sp = shots_probs(hist, shots, cut, r.home_team, r.away_team)
                    ep = elo.probabilities(r.home_team, r.away_team) if elo else None
                    mh, md, ma = _devig([o.home.open, o.draw.open, o.away.open])
                    mo, mu = _devig([o.over25.open, o.under25.open])
                    t = r.fthg + r.ftag
                    # (market, dc, mkt, shots, elo, price, won)
                    rows = [
                        ("HOME", p.p_home, mh, sp and sp[0], ep and ep[0], o.home.open, r.fthg > r.ftag),
                        ("AWAY", p.p_away, ma, sp and sp[2], ep and ep[2], o.away.open, r.ftag > r.fthg),
                        ("DRAW", p.p_draw, md, sp and sp[1], ep and ep[1], o.draw.open, r.fthg == r.ftag),
                        ("OVER25", p.p_over_25, mo, sp and sp[3], None, o.over25.open, t > 2),
                        ("UNDER25", 1 - p.p_over_25, mu, sp and 1 - sp[3], None, o.under25.open, t <= 2),
                    ]
                    rows = [x for x in rows if BAND[0] <= x[5] <= BAND[1]]
                    for rule in RULES:
                        c = choose(rule, rows)
                        if c is not None:
                            seq[(test_s, rule)].append((c[5] - 1) if c[6] else -1.0)
            print(f"done {lg} {test_s}", flush=True)
    return seq


def choose(rule, rows):
    wins = [x for x in rows if x[0] in ("HOME", "AWAY")]
    if rule.startswith("BANKER"):
        thr = int(rule[-2:]) / 100
        ok = [x for x in wins if abs(x[1] - x[2]) <= AGREE and (x[1] + x[2]) / 2 >= thr]
        return max(ok, key=lambda x: x[1] + x[2]) if ok else None
    if rule == "TRI65":
        ok = [x for x in wins if x[4] is not None
              and max(x[1], x[2], x[4]) - min(x[1], x[2], x[4]) <= AGREE
              and (x[1] + x[2] + x[4]) / 3 >= 0.65]
        return max(ok, key=lambda x: x[1] + x[2] + x[4]) if ok else None
    if rule == "SHOTS65":
        ok = [x for x in wins if x[3] is not None
              and max(x[1], x[2], x[3]) - min(x[1], x[2], x[3]) <= AGREE
              and (x[1] + x[2] + x[3]) / 3 >= 0.65]
        return max(ok, key=lambda x: x[1] + x[2] + x[3]) if ok else None
    if rule == "VALUE5":
        ok = []
        for x in rows:
            if x[3] is None or abs(x[1] - x[2]) > AGREE:
                continue
            view = (x[1] + x[3]) / 2
            ev = view * x[5] - 1
            if ev >= 0.05:
                ok.append((ev, x))
        return max(ok)[1] if ok else None
    return None


def _stats(pnls):
    n = len(pnls)
    if not n:
        return "n=0"
    w = sum(1 for x in pnls if x > 0)
    bank = peak = dd = 0.0
    run_l = max_l = 0
    for x in pnls:
        bank += x
        peak = max(peak, bank)
        dd = max(dd, peak - bank)
        run_l = run_l + 1 if x < 0 else 0
        max_l = max(max_l, run_l)
    return (f"n={n:4d} hit={100*w/n:5.1f}% roi={100*sum(pnls)/n:+6.2f}% "
            f"profit={sum(pnls):+7.2f}u maxDD={dd:5.2f}u worst-run={max_l}")


def report(seq) -> str:
    L = ["PROFIT STUDY — one pick per match, band 1.20-2.00, opening prices, flat 1u", ""]
    seasons = sorted({s for s, _ in seq})
    for rule in RULES:
        L.append(f"{rule}")
        allp = []
        for s in seasons:
            allp += seq.get((s, rule), [])
            L.append(f"   {s}: {_stats(seq.get((s, rule), []))}")
        L.append(f"   ALL : {_stats(allp)}")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    out = report(run())
    print(out)
    Path(__file__).with_name("PROFIT_STUDY.md").write_text("```\n" + out + "\n```\n",
                                                           encoding="utf-8")
