"""
ICE HOCKEY walk-forward backtest (standing order 50, Week A of the multi-sport rollout).

For every NHL regular-season game of the test seasons, the goals model (engine/hockey_model.py)
is fitted ONLY on games before a purge gap (refit every REFIT_DAYS days, the gap = PURGE_DAYS),
then scored on: 1X2 after 60 minutes, winner incl. OT, Over/Under 5.5 (60 min), home +1.5 incl.
OT. Against two baselines: league rates (no team info) and the base Poisson model.
Every setting tried (half-life x draw boost) is counted and reported (the deflated-result rule,
docs/obsidian-vault/Trading-Agent-Knowledge-Bridge.md §1); the best is picked on the FIRST test
season and reported on the LATER ones only.

No free historical closing odds were found for hockey, so this measures accuracy, not return;
return and closing-line value come from the shadow board's own graded record (run_hockey.py, run by the multi-sport board).

  python backtest/hockey_backtest.py            writes backtest/ICE_HOCKEY_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import nhl_source as nhl  # noqa: E402
from engine import hockey_model as hm  # noqa: E402

REFIT_DAYS = 7
PURGE_DAYS = 1
HALF_LIVES = (90.0, 180.0, 365.0)
DRAW_BOOSTS = (1.0, 1.15, 1.3)
MARKETS = [("1", "", "Home"), ("1", "", "Draw"), ("1", "", "Away"), ("406", "", "Home"),
           ("18", "total=5.5", "Over 5.5"), ("410", "hcp=1.5", "Home (+1.5)")]
OUT = ROOT / "backtest" / "ICE_HOCKEY_STUDY.md"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def run(games: list[dict], test: list[dict], half_life: float, boost: float) -> dict:
    """{market label: (brier sum, logloss sum, n)} over the test games."""
    out = {f"{m}|{o}": [0.0, 0.0, 0] for m, _s, o in MARKETS}
    model, fitted_at = None, None
    for g in test:
        ko = _dt(g["ko"])
        if fitted_at is None or ko - fitted_at >= timedelta(days=REFIT_DAYS):
            cut = (ko - timedelta(days=PURGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
            model = hm.fit(games, cut, half_life=half_life)
            fitted_at = ko
        if model is None or not model.knows(g["home"], g["away"]):
            continue
        model.draw_boost = boost
        grid = model.grid(g["home"], g["away"])
        reg, final = nhl.reg_score(g), (g["hs"], g["as"])
        for mid, spec, o in MARKETS:
            p = hm.chance(mid, spec, o, grid, model.ot_home)
            y = hm.settle(mid, spec, o, reg, final)
            if p is None or y is None:
                continue
            p = min(max(p, 1e-4), 1 - 1e-4)
            r = out[f"{mid}|{o}"]
            r[0] += (p - y) ** 2
            r[1] += -(y * math.log(p) + (1 - y) * math.log(1 - p))
            r[2] += 1
    return out


def baseline(train: list[dict], test: list[dict]) -> dict:
    """League rates from the training seasons only."""
    rates = {}
    for mid, spec, o in MARKETS:
        ys = [hm.settle(mid, spec, o, nhl.reg_score(g), (g["hs"], g["as"])) for g in train]
        ys = [y for y in ys if y is not None]
        rates[f"{mid}|{o}"] = sum(ys) / len(ys)
    out = {k: [0.0, 0.0, 0] for k in rates}
    for g in test:
        for mid, spec, o in MARKETS:
            y = hm.settle(mid, spec, o, nhl.reg_score(g), (g["hs"], g["as"]))
            if y is None:
                continue
            p, r = rates[f"{mid}|{o}"], out[f"{mid}|{o}"]
            r[0] += (p - y) ** 2
            r[1] += -(y * math.log(p) + (1 - y) * math.log(1 - p))
            r[2] += 1
    return out


def total(res: dict) -> float:
    return sum(v[0] for v in res.values()) / max(1, sum(v[2] for v in res.values()))


def main() -> None:
    games = [g for g in nhl.history(seasons=3) if g["type"] == 2]
    seasons = sorted({g["season"] for g in games})
    tune_s, test_s = seasons[1], seasons[2:]
    tune = [g for g in games if g["season"] == tune_s]
    test = [g for g in games if g["season"] in test_s]
    tries = []
    for hl in HALF_LIVES:
        for b in DRAW_BOOSTS:
            r = run(games, tune, hl, b)
            tries.append((total(r), hl, b))
            print(f"tune {tune_s} half-life {hl:.0f} draw x{b}: Brier {total(r):.5f}")
    tries.sort()
    _best, hl, b = tries[0]
    final = run(games, test, hl, b)
    plain = run(games, test, hm.HALF_LIFE, 1.0)
    base = baseline([g for g in games if g["season"] < test_s[0]], test)
    lines = [
        "# Ice hockey backtest (NHL, walk-forward)",
        "",
        f"Written by `backtest/hockey_backtest.py` on {datetime.now():%Y-%m-%d %H:%M} UTC. Standing order 50.",
        "",
        f"* Games: {len(games)} NHL regular-season games, seasons {', '.join(map(str, seasons))}.",
        f"* Refit every {REFIT_DAYS} days on games before a {PURGE_DAYS}-day purge gap; never on the game scored.",
        f"* Settings tried: {len(tries)} (half-life {list(HALF_LIVES)} x draw boost {list(DRAW_BOOSTS)}), "
        f"chosen on {tune_s} only: **half-life {hl:.0f} days, draw boost x{b}**.",
        f"* Reported on later games only ({', '.join(map(str, test_s))}, {len(test)} games; the current season is partial).",
        "* No free historical closing odds for hockey: this is accuracy, not return. Return and value",
        "  against the exchange close come from the shadow board's graded record (`data/ice_hockey/scoreboard.json`).",
        "",
        "| Market | n | Brier: league rate | Brier: plain model | Brier: chosen model | Log loss (chosen) |",
        "|---|---|---|---|---|---|",
    ]
    for k in final:
        bf, pf, cf = base[k], plain[k], final[k]
        if not cf[2]:
            continue
        lines.append(f"| {k} | {cf[2]} | {bf[0] / bf[2]:.4f} | {pf[0] / pf[2]:.4f} | {cf[0] / cf[2]:.4f} | {cf[1] / cf[2]:.4f} |")
    lines += ["", f"Overall Brier: league rate {total(base):.5f}, plain model {total(plain):.5f}, chosen {total(final):.5f}.",
              "", "All tries on the tuning season:", ""]
    lines += [f"* half-life {h:.0f}, draw x{bb}: {s:.5f}" for s, h, bb in tries]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
