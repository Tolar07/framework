"""
SELECTION STUDY — which per-match selection rule wins most often?

Walk-forward (model fitted only on matches BEFORE each block), one pick per
match, inside the Architect's deploy band 1.20-2.00, at the OPENING price (the
price available when the board is built). Markets: 1X2, Over/Under 2.5 (real
prices) and Double Chance 1X/X2/12 (price derived from the same book's 1X2 as
1/(1/a+1/b) — the standard sportsbook construction, margin included).

Rules compared:
  MODEL      highest Dixon-Coles probability            (current framework)
  MARKET     highest de-vigged market probability       (the bookmaker's view)
  CONSENSUS  highest average of model + market
  AGREE      CONSENSUS, only where model and market agree within 7pp
  AGREE70    AGREE, and consensus probability >= 70%
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from data.football_data_source import load_league
from engine.dixon_coles import predict

BAND = (1.20, 2.00)
GROUPS = [
    ("2425", "2526", ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga",
                      "Ligue 1", "Eredivisie", "Primeira Liga", "Scottish Premiership",
                      "Belgian Pro League"]),
    ("2526", "2627", ["League One", "League Two", "National League", "Championship"]),
]
RULES = ("MODEL", "MARKET", "CONSENSUS", "AGREE", "AGREE70")


def _devig(prices):
    inv = [1 / p for p in prices]
    s = sum(inv)
    return [i / s for i in inv]


def candidates(m, probs):
    o = m.odds
    if not o:
        return []
    H, D, A = o.home.open, o.draw.open, o.away.open
    OV, UN = o.over25.open, o.under25.open
    if not all((H, D, A, OV, UN)):
        return []
    ph, pd, pa = _devig([H, D, A])
    pov, pun = _devig([OV, UN])
    t = m.fthg + m.ftag
    rows = [  # (market, model_p, market_p, price, won)
        ("HOME", probs.p_home, ph, H, m.fthg > m.ftag),
        ("DRAW", probs.p_draw, pd, D, m.fthg == m.ftag),
        ("AWAY", probs.p_away, pa, A, m.ftag > m.fthg),
        ("OVER25", probs.p_over_25, pov, OV, t > 2),
        ("UNDER25", 1 - probs.p_over_25, pun, UN, t <= 2),
        ("DC_1X", probs.p_home + probs.p_draw, ph + pd, 1 / (1 / H + 1 / D), m.fthg >= m.ftag),
        ("DC_X2", probs.p_draw + probs.p_away, pd + pa, 1 / (1 / D + 1 / A), m.ftag >= m.fthg),
        ("DC_12", probs.p_home + probs.p_away, ph + pa, 1 / (1 / H + 1 / A), m.fthg != m.ftag),
    ]
    return [r for r in rows if BAND[0] <= r[3] <= BAND[1]]


def choose(rule, rows):
    if not rows:
        return None
    if rule == "MODEL":
        return max(rows, key=lambda r: r[1])
    if rule == "MARKET":
        return max(rows, key=lambda r: r[2])
    best = max(rows, key=lambda r: (r[1] + r[2]) / 2)
    if rule == "CONSENSUS":
        return best
    if abs(best[1] - best[2]) > 0.07:
        return None
    if rule == "AGREE70" and (best[1] + best[2]) / 2 < 0.70:
        return None
    return best


def run():
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="",
                         refit_every_days=14)
    stats = {r: defaultdict(lambda: [0, 0, 0.0]) for r in RULES}   # key -> [n, wins, pnl]
    for carry_s, test_s, leagues in GROUPS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception as e:
                print(f"skip {lg} {test_s}: {e}", flush=True)
                continue
            hist = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            cuts = refit_cut_dates([r.date for r in test], 14)
            warm = None
            n_m = 0
            for cut in cuts:
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                if not block:
                    continue
                model, _ = get_model(lg, cut, hist, cfg, warm)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                for m in block:
                    p = predict(model, m.home_team, m.away_team)
                    if p is None:
                        continue
                    rows = candidates(m, p)
                    n_m += 1
                    for rule in RULES:
                        c = choose(rule, rows)
                        if c is None:
                            continue
                        for key in ("ALL", f"{lg} {test_s}", f"mkt:{c[0]}"):
                            s = stats[rule][key]
                            s[0] += 1
                            s[1] += c[4]
                            s[2] += (c[3] - 1) if c[4] else -1
            print(f"done {lg} {test_s}: {n_m} matches", flush=True)
    return stats


def report(stats) -> str:
    L = ["SELECTION STUDY — one pick per match, band 1.20-2.00, opening prices",
         "", f"{'rule':10} {'picks':>6} {'hit%':>6} {'ROI%':>7}"]
    for r in RULES:
        n, w, pnl = stats[r]["ALL"]
        L.append(f"{r:10} {n:6d} {100*w/max(n,1):6.1f} {100*pnl/max(n,1):7.2f}")
    L += ["", "By market (rule: share of picks, hit%, ROI%):"]
    for r in RULES:
        parts = []
        for k, (n, w, pnl) in sorted(stats[r].items()):
            if k.startswith("mkt:"):
                parts.append(f"{k[4:]} n={n} hit={100*w/n:.0f}% roi={100*pnl/n:+.1f}%")
        L.append(f"  {r}: " + " | ".join(parts))
    L += ["", "By league (AGREE70 / CONSENSUS / MODEL  hit% roi%):"]
    keys = sorted(k for k in stats["MODEL"] if not k.startswith("mkt:") and k != "ALL")
    for k in keys:
        cells = []
        for r in ("AGREE70", "CONSENSUS", "MODEL"):
            n, w, pnl = stats[r].get(k, [0, 0, 0.0])
            cells.append(f"{r}: n={n} {100*w/max(n,1):.0f}% {100*pnl/max(n,1):+.1f}%")
        L.append(f"  {k:32} " + " | ".join(cells))
    return "\n".join(L)


if __name__ == "__main__":
    out = report(run())
    print(out)
    Path(__file__).with_name("SELECTION_STUDY.md").write_text("```\n" + out + "\n```\n", encoding="utf-8")
