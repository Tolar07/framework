"""
NBA PERIOD STUDY — team totals, regulation total and half/quarter lines
(order 41 paper board; Architect 2026-10-07: "build A and B together and C").

SportyBet lists, on NBA games, home/away points totals (227/228), a
regulation-time total (18), 1st-half handicaps (66) and quarter handicaps
(303). Each needs a fair chance from the sharp closing line — and, before
any of them is priced, the spread of real results around that line.

Same data and split as backtest/NBA_STUDY.md: ESPN regular seasons,
2023-24 LEARNS every setting, 2024-25 and 2025-26 are the TEST (never used
to choose anything). The line is ESPN BET's closing spread S (home handicap,
negative = home favoured) and total T.

  home points   ~ Normal((T - S) / 2 + b, sd)       away: (T + S) / 2
  regulation    ~ Normal(T + b, sd)                  quarters 1-4 only
  period margin ~ Normal(k x (-S), sd)               1st half, quarters 1-3
  period total  ~ Normal(k x T, sd)                  1st half, 1st quarter
  full margin   ~ Normal(-S, sd)                     (the board's MARGIN_SD)

Team quarter shares: does a team's own share of its points in the 1st
quarter / 1st half (season to date, shrunk toward the league) predict the
period better than one league-wide share? Used only if it beats the flat
share on the test seasons.

    python backtest/nba_period_study.py      -> backtest/NBA_PERIOD_STUDY.md
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date
from math import erf, sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_source as ns  # noqa: E402

SEASONS = {2024: (date(2023, 10, 24), date(2024, 4, 14)),
           2025: (date(2024, 10, 22), date(2025, 4, 13)),
           2026: (date(2025, 10, 21), date(2026, 4, 12))}
LEARN, TEST = (2024,), (2025, 2026)
SHRINK_GAMES = 20          # team share = (team pts + 20 games at league share) / ...
MIN_GAIN = 0.01            # team shares must cut test RMSE by 1%+ to be used
OUT = ROOT / "backtest" / "NBA_PERIOD_STUDY.md"


def games() -> dict[int, list]:
    out = {}
    for s, (a, b) in SEASONS.items():
        out[s] = [g for g in ns.season_games(a, b) if g.stype == 2 and g.completed
                  and g.total is not None and g.spread is not None
                  and g.q_home and g.q_away and len(g.q_home) >= 4 and len(g.q_away) >= 4]
    return out


def _mean(xs):
    return sum(xs) / len(xs)


def _sd(xs):
    m = _mean(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _rmse(xs):
    return sqrt(sum(x * x for x in xs) / len(xs))


def _phi(z):
    return 0.5 * (1 + erf(z / sqrt(2)))


def _k(ys, xs):
    """Least-squares slope through the origin: y ≈ k x."""
    return sum(y * x for y, x in zip(ys, xs, strict=True)) / sum(x * x for x in xs)


# ── quantities per game ──────────────────────────────────────────────────────
def per_game(g) -> dict:
    qh, qa = g.q_home, g.q_away
    exp_home, exp_away = (g.total - g.spread) / 2, (g.total + g.spread) / 2
    return {"T": g.total, "S": g.spread, "x": -g.spread,
            "exp_home": exp_home, "exp_away": exp_away,
            "home": g.hs, "away": g.as_, "margin": g.hs - g.as_,
            "reg": sum(qh[:4]) + sum(qa[:4]), "ot": len(qh) > 4,
            "h1_m": sum(qh[:2]) - sum(qa[:2]), "h1_t": sum(qh[:2]) + sum(qa[:2]),
            **{f"q{n}_m": qh[n - 1] - qa[n - 1] for n in (1, 2, 3)},
            "q1_t": qh[0] + qa[0], "h1_home": sum(qh[:2]), "h1_away": sum(qa[:2]),
            "q1_home": qh[0], "q1_away": qa[0], "reg_home": sum(qh[:4]), "reg_away": sum(qa[:4])}


def fit_all(rows: list[dict]) -> dict:
    """Every setting, learned on `rows` (the learn season)."""
    f = {}
    rh = [r["home"] - r["exp_home"] for r in rows]
    ra = [r["away"] - r["exp_away"] for r in rows]
    f["home_b"], f["away_b"] = _mean(rh), _mean(ra)
    f["team_sd"] = _sd(rh + ra)
    rr = [r["reg"] - r["T"] for r in rows]
    f["reg_b"], f["reg_sd"] = _mean(rr), _sd(rr)
    f["margin_sd"] = _sd([r["margin"] - r["x"] for r in rows])
    f["total_sd"] = _sd([r["home"] + r["away"] - r["T"] for r in rows])
    for p in ("h1", "q1", "q2", "q3"):
        k = _k([r[f"{p}_m"] for r in rows], [r["x"] for r in rows])
        f[f"{p}_m_k"], f[f"{p}_m_sd"] = k, _sd([r[f"{p}_m"] - k * r["x"] for r in rows])
    for p in ("h1", "q1"):
        k = _k([r[f"{p}_t"] for r in rows], [r["T"] for r in rows])
        f[f"{p}_t_k"], f[f"{p}_t_sd"] = k, _sd([r[f"{p}_t"] - k * r["T"] for r in rows])
    return f


def calibration(rows, mean_fn, actual_fn, sd, offsets=(-9, -6, -3, 0, 3, 6, 9)):
    """For lines `offset` points from the model's centre: predicted vs real Over rate."""
    out = []
    for off in offsets:
        pred = 1 - _phi((off + 0.5) / sd)              # a .5 line just above centre+off
        hit = sum(actual_fn(r) > mean_fn(r) + off + 0.5 for r in rows) / len(rows)
        out.append((off, pred, hit))
    return out


# ── team quarter shares ──────────────────────────────────────────────────────
def team_share_errors(by_season: dict[int, list], f: dict) -> dict[str, tuple[float, float]]:
    """Test-season RMSE (flat league share, team shares) for 1st-quarter and
    1st-half totals and margins. Team shares use only games BEFORE each game
    (prior season carried in), shrunk toward the league share."""
    league = {p: f[f"{p}_t_k"] for p in ("q1", "h1")}
    errs = defaultdict(lambda: ([], []))
    acc = defaultdict(lambda: {"q1": 0.0, "h1": 0.0, "reg": 0.0})
    for s in sorted(by_season):
        if s != min(by_season):          # carry half of last season's evidence in
            for t in acc:
                for k in acc[t]:
                    acc[t][k] *= 0.5
        for g in sorted(by_season[s], key=lambda g: g.tip):
            r = per_game(g)
            share = {}
            for side, team in (("home", g.home), ("away", g.away)):
                a = acc[team]
                pad = SHRINK_GAMES * 112.0
                share[side] = {p: (a[p] + league[p] * pad) / (a["reg"] + pad) for p in ("q1", "h1")}
            if s in TEST:
                for p in ("q1", "h1"):
                    flat_t = f[f"{p}_t_k"] * r["T"]
                    team_t = share["home"][p] * r["exp_home"] + share["away"][p] * r["exp_away"]
                    errs[f"{p} total"][0].append(r[f"{p}_t"] - flat_t)
                    errs[f"{p} total"][1].append(r[f"{p}_t"] - team_t)
                    flat_m = f[f"{p}_m_k"] * r["x"]
                    team_m = (share["home"][p] * r["exp_home"] - share["away"][p] * r["exp_away"]
                              + (f[f"{p}_m_k"] - league[p]) * r["x"])
                    errs[f"{p} margin"][0].append(r[f"{p}_m"] - flat_m)
                    errs[f"{p} margin"][1].append(r[f"{p}_m"] - team_m)
            for side, team in (("home", g.home), ("away", g.away)):
                acc[team]["q1"] += r[f"q1_{side}"]
                acc[team]["h1"] += r[f"h1_{side}"]
                acc[team]["reg"] += r[f"reg_{side}"]
    return {k: (_rmse(a), _rmse(b)) for k, (a, b) in errs.items()}


def main() -> int:
    by = games()
    learn = [per_game(g) for s in LEARN for g in by[s]]
    test = [per_game(g) for s in TEST for g in by[s]]
    f = fit_all(learn)
    L = ["# NBA PERIOD STUDY — team totals, regulation total, half and quarter lines", "",
         "ESPN regular seasons with the closing ESPN BET spread and total and all four quarter "
         "scores. **2023-24 learns every setting; 2024-25 and 2025-26 are the test.** "
         "Written by `backtest/nba_period_study.py`.", ""]
    for s in SEASONS:
        L.append(f"- {s - 1}-{str(s)[2:]}: {len(by[s])} games")
    L += ["", "## Q1 · Spread of real results around the closing line", "",
          "Learned on 2023-24; the test column is the same measure on 2024-25 + 2025-26 "
          "(no refit). Close agreement = the setting holds out of sample.", "",
          "| Quantity | Centre | sd (learn) | sd (test) | bias on test |", "|---|---|---|---|---|"]

    def row(name, centre, sd, resid):
        L.append(f"| {name} | {centre} | {sd:.2f} | {_sd(resid):.2f} | {_mean(resid):+.2f} |")

    row("Full-game margin", "−S", f["margin_sd"], [r["margin"] - r["x"] for r in test])
    row("Full-game total", "T", f["total_sd"], [r["home"] + r["away"] - r["T"] for r in test])
    row("Home points (227)", f"(T−S)/2 {f['home_b']:+.2f}", f["team_sd"],
        [r["home"] - r["exp_home"] - f["home_b"] for r in test])
    row("Away points (228)", f"(T+S)/2 {f['away_b']:+.2f}", f["team_sd"],
        [r["away"] - r["exp_away"] - f["away_b"] for r in test])
    row("Regulation total (18)", f"T {f['reg_b']:+.2f}", f["reg_sd"],
        [r["reg"] - r["T"] - f["reg_b"] for r in test])
    for p, name in (("h1", "1st-half margin (66)"), ("q1", "1st-quarter margin (303)"),
                    ("q2", "2nd-quarter margin (303)"), ("q3", "3rd-quarter margin (303)")):
        row(name, f"{f[p + '_m_k']:.3f} × (−S)", f[p + "_m_sd"],
            [r[p + "_m"] - f[p + "_m_k"] * r["x"] for r in test])
    for p, name in (("h1", "1st-half total"), ("q1", "1st-quarter total")):
        row(name, f"{f[p + '_t_k']:.3f} × T", f[p + "_t_sd"],
            [r[p + "_t"] - f[p + "_t_k"] * r["T"] for r in test])
    ot = sum(r["ot"] for r in test) / len(test)
    L += ["", f"Overtime in {ot:.1%} of test games (it counts in the full-game, team-total and "
          "handicap markets, never in the regulation total or a half/quarter).", ""]

    L += ["## Q2 · Calibration on the test seasons", "",
          "A line placed `offset` points above the centre (plus 0.5): the Over rate the "
          "Normal curve predicts with the LEARNED sd, against how often it landed.", ""]
    for name, mean_fn, act_fn, sd in (
            ("Home points", lambda r: r["exp_home"] + f["home_b"], lambda r: r["home"], f["team_sd"]),
            ("Regulation total", lambda r: r["T"] + f["reg_b"], lambda r: r["reg"], f["reg_sd"]),
            ("1st-half margin", lambda r: f["h1_m_k"] * r["x"], lambda r: r["h1_m"], f["h1_m_sd"]),
            ("Full-game margin", lambda r: r["x"], lambda r: r["margin"], f["margin_sd"])):
        cal = calibration(test, mean_fn, act_fn, sd)
        L += [f"**{name}** (sd {sd:.2f})", "", "| offset | predicted Over | landed |", "|---|---|---|"]
        L += [f"| {o:+d} | {p:.1%} | {h:.1%} |" for o, p, h in cal]
        L.append("")

    errs = team_share_errors(by, f)
    L += ["## Q3 · Team quarter shares vs one league share (test seasons)", "",
          f"Each team's share of its own points in the period, season to date (half of last "
          f"season carried in), shrunk with {SHRINK_GAMES} games at the league share. "
          f"Used only if it cuts the test error by {MIN_GAIN:.0%} or more.", "",
          "| Period line | RMSE league share | RMSE team shares | change | verdict |",
          "|---|---|---|---|---|"]
    use = {}
    for k, (flat, team) in sorted(errs.items()):
        gain = (flat - team) / flat
        use[k] = gain >= MIN_GAIN
        L.append(f"| {k} | {flat:.2f} | {team:.2f} | {-gain:+.1%} | "
                 f"{'**use team shares**' if use[k] else 'keep league share'} |")

    t = fit_all(test)                    # the same measures on the test seasons
    sd = {k: round(max(f[k], t[k]), 1) for k in f if k.endswith("sd")}
    L += ["", "## Settings for engine/nba_value.py", "",
          "Centres and shares as learned on 2023-24. Each spread is the LARGER of the learn "
          "and test value: a curve a little too wide can only make the board see less value "
          "on the near-certain side of a far line, never more.", "", "```",
          f"MARGIN_SD = {sd['margin_sd']}", f"TOTAL_SD = {sd['total_sd']}",
          f"TEAM_SD = {sd['team_sd']}; HOME_B = {f['home_b']:+.2f}; AWAY_B = {f['away_b']:+.2f}",
          f"REG_B = {f['reg_b']:+.2f}; REG_SD = {sd['reg_sd']}",
          f"H1_MARGIN = ({f['h1_m_k']:.3f}, {sd['h1_m_sd']})"]
    L += [f"Q{n}_MARGIN = ({f[f'q{n}_m_k']:.3f}, {sd[f'q{n}_m_sd']})" for n in (1, 2, 3)]
    L += [f"H1_TOTAL = ({f['h1_t_k']:.3f}, {sd['h1_t_sd']}); Q1_TOTAL = ({f['q1_t_k']:.3f}, {sd['q1_t_sd']})",
          "```", ""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
