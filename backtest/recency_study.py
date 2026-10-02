"""
RECENCY STUDY — should the model see THIS season, not just last season?

A  STATIC   (current production): fitted once on the previous completed
            season; predicts every match of the test season with it.
B  RECENT   (proposed): fitted on previous season + test-season matches
            played BEFORE each block (refit every 14 days), recent matches
            weighted more (exponential half-life).

Walk-forward, no leakage (strictly-before cut). Same matches scored for both
where both can rate them; coverage reported separately (B can rate promoted
teams once they have played; A never can).

Metrics: 1X2 Brier + log-loss, O/U 2.5 Brier, mean |model - market| on the
home-win probability (disagreement), share of matches the selection rule
would mark SPLIT, and the BANKER / SAFE picks' hit rate + ROI at opening
prices (backtest/selection_study.py candidate maths).
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from backtest.selection_study import candidates
from data.football_data_source import load_league
from engine.dixon_coles import predict

GROUPS = [
    ("2425", "2526", ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga",
                      "Ligue 1", "Eredivisie", "Primeira Liga", "Scottish Premiership",
                      "Belgian Pro League", "League One", "League Two"]),
    ("2526", "2627", ["League One", "League Two", "National League", "Championship",
                      "Premier League", "La Liga 2", "Serie B", "2. Bundesliga", "Ligue 2",
                      "Eredivisie", "Scottish Premiership", "Belgian Pro League"]),
]
HALF_LIVES = (120, 240)


def _devig(ps):
    inv = [1 / p for p in ps]
    s = sum(inv)
    return [i / s for i in inv]


def pick(rows):
    """Production selection on the study's markets: BANKER (1X2 win, agree
    <=7pp, consensus >=70%) else best agreeing market (SAFE) else SPLIT."""
    if not rows:
        return None, None
    cons = lambda r: (r[1] + r[2]) / 2
    agree = [r for r in rows if abs(r[1] - r[2]) <= 0.07 and cons(r) >= 0.5]
    bank = [r for r in agree if r[0] in ("HOME", "AWAY") and cons(r) >= 0.70]
    if bank:
        return max(bank, key=cons), "BANKER"
    if agree:
        return max(agree, key=cons), "SAFE"
    return None, "SPLIT"


def run():
    S = defaultdict(lambda: defaultdict(float))   # (group, arm) -> metric sums
    for carry_s, test_s, leagues in GROUPS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception as e:
                print(f"skip {lg} {test_s}: {e}", flush=True)
                continue
            if len(carry) < 100 or len(test) < 20:
                print(f"skip {lg} {test_s}: thin ({len(carry)}/{len(test)})", flush=True)
                continue
            test = sorted(test, key=lambda r: r.date)
            cuts = refit_cut_dates([r.date for r in test], 14)
            static_cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="",
                                        refit_every_days=14, max_history_matches=10_000)
            static, _ = get_model(lg, test[0].date, carry, static_cfg)
            arms = {"A_static": static_cfg}
            for hl in HALF_LIVES:
                arms[f"B_recent_hl{hl}"] = replace(static_cfg, half_life_days=float(hl),
                                                   max_history_matches=800)
            hist = sorted(carry + test, key=lambda r: r.date)
            warm = {k: None for k in arms}
            for cut in cuts:
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                if not block:
                    continue
                models = {"A_static": static}
                for name, cfg in arms.items():
                    if name == "A_static":
                        continue
                    m, _ = get_model(lg, cut, hist, cfg, warm[name])
                    warm[name] = getattr(m, "warm_seed", None) or warm[name]
                    models[name] = m
                for r in block:
                    o = r.odds
                    if not o or not all((o.home.open, o.draw.open, o.away.open,
                                         o.over25.open, o.under25.open)):
                        continue
                    preds = {k: (predict(m, r.home_team, r.away_team) if m else None)
                             for k, m in models.items()}
                    G = (carry_s + ">" + test_s)
                    for k, p in preds.items():
                        S[(G, k)]["matches"] += 1
                        S[(G, k)]["rated"] += p is not None
                    if any(p is None for p in preds.values()):
                        continue
                    mh, md, ma = _devig([o.home.open, o.draw.open, o.away.open])
                    mo, _ = _devig([o.over25.open, o.under25.open])
                    y = [r.fthg > r.ftag, r.fthg == r.ftag, r.ftag > r.fthg]
                    yo = (r.fthg + r.ftag) > 2
                    for k, p in preds.items():
                        s = S[(G, k)]
                        pv = [p.p_home, p.p_draw, p.p_away]
                        s["n"] += 1
                        s["brier"] += sum((a - b) ** 2 for a, b in zip(pv, y))
                        s["logloss"] += -math.log(max(pv[y.index(True)], 1e-9))
                        s["brier_ou"] += (p.p_over_25 - yo) ** 2
                        s["gap_home"] += abs(p.p_home - mh)
                        s["gap_over"] += abs(p.p_over_25 - mo)
                        c, tier = pick(candidates(r, p))
                        s[f"tier_{tier}"] += 1
                        if c is not None:
                            s[f"{tier}_n"] += 1
                            s[f"{tier}_w"] += c[4]
                            s[f"{tier}_pnl"] += (c[3] - 1) if c[4] else -1
            print(f"done {lg} {test_s}", flush=True)
    return S


def report(S) -> str:
    L = ["RECENCY STUDY — last-season-only model (A) vs last+current season, time-weighted (B)", ""]
    groups = sorted({g for g, _ in S})
    for g in groups:
        L.append(f"=== carry>test {g}")
        L.append(f"{'arm':16} {'rated%':>7} {'n':>5} {'brier1X2':>9} {'logloss':>8} {'brierOU':>8} "
                 f"{'|gap|H':>7} {'SPLIT%':>7} {'BANKER n/hit/roi':>20} {'SAFE n/hit/roi':>20}")
        for arm in sorted(a for gg, a in S if gg == g):
            s = S[(g, arm)]
            n = max(s["n"], 1)
            def tr(t):
                k = max(s[f"{t}_n"], 1)
                return f"{int(s[f'{t}_n'])}/{100*s[f'{t}_w']/k:.0f}%/{100*s[f'{t}_pnl']/k:+.1f}%"
            L.append(f"{arm:16} {100*s['rated']/max(s['matches'],1):6.1f}% {int(s['n']):5d} "
                     f"{s['brier']/n:9.4f} {s['logloss']/n:8.4f} {s['brier_ou']/n:8.4f} "
                     f"{s['gap_home']/n:7.3f} {100*s['tier_SPLIT']/n:6.1f}% {tr('BANKER'):>20} {tr('SAFE'):>20}")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    out = report(run())
    print(out)
    Path(__file__).with_name("RECENCY_STUDY.md").write_text("```\n" + out + "\n```\n", encoding="utf-8")
