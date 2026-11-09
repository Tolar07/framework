"""
SECOND-HALF STUDY (Architect 2026-11-09): "the first half of the season will
give an informed decision of what will happen when they face themselves in
the second half ... league position, table, points, goal difference ... this
is where motivation will begin to matter."

The question, tested honestly: once every club has played every other club
once, does what the first half shows ADD to the bookmaker's price for the
return game? Inputs (engine/inputs.second_half, all read strictly before the
day, this season only):

  rev_gd / rev_goals   this season's first meeting of the pair, from today's
                       home side's view (the "how they faced each other" input)
  half_ppg_gap         points per game gap (league position, in rate form)
  half_gd_gap          goal difference per game gap
  motive_gap           stakes: a side is live when a title / Europe / relegation
                       line is within reach (half the points left) on either
                       side of it; +1 = only the home side has something to play
                       for, -1 = only the away side
  dead_count           how many of the two are in a dead rubber (0, 1, 2)

Baseline: the market's OPENING price, de-vigged (football-data.co.uk, the book
the loader prefers). The same feature test as backtest/inputs_study.wf_preds:
each feature's weight is fitted on earlier days only and the day is scored
with and without it (Brier, log loss, 2 standard errors). The money columns:
the bets each version takes at chance x opening >= 1.03, their ROI at the
opening price and their CLV (opening / closing - 1). The closing price's own
Brier is shown as the bar any input has to get near.

A study, not a selector: an input goes live only through the retrain /
promotion path with verdict ADDS INFORMATION on both Brier and log loss
(standing promotion rule 2026-11-04). Writes backtest/SECOND_HALF_STUDY.md
and memory/second_half_gate.json (framework-data).

    python backtest/second_half_study.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.inputs_study import wf_preds  # noqa: E402
from engine import inputs as ip  # noqa: E402
from engine import walkforward as wf  # noqa: E402

OUT = ROOT / "backtest" / "SECOND_HALF_STUDY.md"
GATE = ROOT / "memory" / "second_half_gate.json"
LEAGUES = ("Premier League", "Championship", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
           "Eredivisie", "Primeira Liga", "Scottish Premiership", "Belgian Pro League")
SEASONS = ("1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526")
FEATS = ("rev_gd", "rev_goals", "half_ppg_gap", "half_gd_gap", "motive_gap", "dead_count")
OUTCOMES = ("home win", "draw", "away win", "over 2.5")
EDGE = 0.03
LATE = 0.75             # "late" = both sides past this share of their season


def devig(prices: list) -> list | None:
    if not prices or any(not isinstance(x, (int, float)) or x <= 1 for x in prices):
        return None
    inv = [1 / x for x in prices]
    s = sum(inv)
    return [i / s for i in inv]


def market_rows(m) -> dict[str, tuple]:
    """outcome -> (p_open, y, {open, close, p_close}) for one MatchResult."""
    od = m.odds
    if od is None:
        return {}
    o1 = devig([od.home.open, od.draw.open, od.away.open])
    c1 = devig([od.home.close, od.draw.close, od.away.close])
    ou = devig([od.over25.open, od.under25.open])
    cu = devig([od.over25.close, od.under25.close])
    ys = {"home win": int(m.fthg > m.ftag), "draw": int(m.fthg == m.ftag),
          "away win": int(m.fthg < m.ftag), "over 2.5": int(m.fthg + m.ftag > 2)}
    out = {}
    if o1:
        for i, (k, mp) in enumerate((("home win", od.home), ("draw", od.draw), ("away win", od.away))):
            out[k] = (o1[i], ys[k], {"open": mp.open, "close": mp.close, "p_close": c1[i] if c1 else None})
    if ou:
        out["over 2.5"] = (ou[0], ys["over 2.5"],
                           {"open": od.over25.open, "close": od.over25.close, "p_close": cu[0] if cu else None})
    return out


def money(scored: list[tuple]) -> dict:
    """Bets (chance x opening >= 1 + EDGE) by the market alone vs market + feature."""
    def side(use_q: bool) -> dict:
        roi, clv = [], []
        for _d, p, q, y, e in scored:
            o, c = (e or {}).get("open"), (e or {}).get("close")
            if not o:
                continue
            if (q if use_q else p) * o >= 1 + EDGE:
                roi.append(o * y - 1)
                if c:
                    clv.append(o / c - 1)
        mr, sr = wf._mean_se(roi)
        mc, _ = wf._mean_se(clv)
        return {"bets": len(roi), "roi": round(100 * mr, 2), "roi_se": round(100 * sr, 2),
                "clv": round(100 * mc, 2)}
    return {"market": side(False), "with_feature": side(True)}


def collect(load=None) -> tuple[dict, dict]:
    if load is None:
        from data.football_data_source import load_league as load
    rows: dict[tuple, list] = {(o, f, seg): [] for o in OUTCOMES for f in FEATS for seg in ("all", "late")}
    close_b: dict[str, list] = {o: [] for o in OUTCOMES}
    cover: dict[str, Any] = {"league_seasons": 0, "second_half": 0, "with_first_meeting": 0}
    for lg in LEAGUES:
        for s in SEASONS:
            try:
                ms, _ = load(lg, s)
            except Exception as err:  # noqa: BLE001
                print(f"  {lg} {s}: skipped ({str(err)[:60]})", flush=True)
                continue
            if not ms:
                continue
            cover["league_seasons"] += 1
            H = ip.History(ip.from_results(ms))
            for m in sorted(ms, key=lambda r: r.date):
                f = ip.second_half(H, m.home_team, m.away_team, m.date)
                if f["half_ppg_gap"] is None:
                    continue
                mk = market_rows(m)
                if not mk:
                    continue
                cover["second_half"] += 1
                cover["with_first_meeting"] += f["rev_gd"] is not None
                t = ip.table_asof(H, m.date)
                n = t[m.home_team]["size"]
                late = min(t[m.home_team]["played"], t[m.away_team]["played"]) >= LATE * 2 * (n - 1)
                for o, (p, y, e) in mk.items():
                    if e.get("p_close") is not None:
                        close_b[o].append((p, e["p_close"], y))
                    for k in FEATS:
                        rows[(o, k, "all")].append((m.date, p, y, f[k], e))
                        if late:
                            rows[(o, k, "late")].append((m.date, p, y, f[k], e))
            print(f"  {lg} {s}: {cover['second_half']} second-half matches so far", flush=True)
    res = {}
    for key, rs in rows.items():
        summ, scored = wf_preds(rs)
        summ["money"] = money(scored)
        res[" | ".join(key)] = summ
    bars = {}
    for o, xs in close_b.items():
        if xs:
            bars[o] = {"n": len(xs), "brier_open": round(sum((p - y) ** 2 for p, _c, y in xs) / len(xs), 4),
                       "brier_close": round(sum((c - y) ** 2 for _p, c, y in xs) / len(xs), 4)}
    cover["bars"] = bars
    return res, cover


def write(res: dict, cover: dict) -> str:
    L = ["# SECOND-HALF STUDY — does the first half of the season beat the price for the return game?", "",
         "Written by `backtest/second_half_study.py` (Architect 2026-11-09). Second-half games only (both clubs "
         "have played everyone once), " + ", ".join(LEAGUES) + f"; seasons {SEASONS[0]}-{SEASONS[-1]}. "
         "Baseline: the market's opening price, de-vigged. Each input's weight is fitted on earlier days only. "
         "Gain > 0 = the input helped; a verdict needs 100+ scored matches and 2 standard errors. Money: bets at "
         f"chance x opening >= {1 + EDGE:.2f}, ROI at the opening price, CLV = opening / closing - 1.", "",
         f"Coverage: {cover['league_seasons']} league-seasons, {cover['second_half']} second-half matches, "
         f"{cover['with_first_meeting']} with this season's first meeting on record.", "",
         "## The bar: how good the price already is (Brier, lower = better)", "",
         "| outcome | matches | opening price | closing price |", "|---|---|---|---|"]
    for o, b in cover.get("bars", {}).items():
        L.append(f"| {o} | {b['n']} | {b['brier_open']} | {b['brier_close']} |")
    for seg, title in (("all", "All second-half games"), ("late", f"Late season (both past {int(LATE * 100)}% of games)")):
        L += ["", f"## {title}", "",
              "| outcome | input | scored | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | "
              "market bets: ROI / CLV | with input: ROI / CLV |", "|---|---|---|---|---|---|---|---|"]
        for o in OUTCOMES:
            for k in FEATS:
                s = res.get(f"{o} | {k} | {seg}")
                if not s or not s.get("scored"):
                    L.append(f"| {o} | {k} | 0 | PENDING | PENDING | NOT ENOUGH DATA | - | - |")
                    continue
                mm, mf = s["money"]["market"], s["money"]["with_feature"]
                L.append(f"| {o} | {k} | {s['scored']} | {s['brier_gain']:+.5f} ± {s['brier_se']:.5f} | "
                         f"{s['logloss_gain']:+.5f} ± {s['logloss_se']:.5f} | {s['verdict']} / {s['verdict_logloss']} | "
                         f"{mm['roi']:+.2f}% / {mm['clv']:+.2f}% ({mm['bets']}) | "
                         f"{mf['roi']:+.2f}% / {mf['clv']:+.2f}% ({mf['bets']}) |")
    passed = [k for k, s in res.items()
              if s.get("verdict") == "ADDS INFORMATION" and s.get("verdict_logloss") == "ADDS INFORMATION"]
    L += ["", "## Verdict", ""]
    if passed:
        L.append("Inputs that add to the opening price on both Brier and log loss (candidates for the shadow → "
                 "promotion path, never straight to stakes): " + ", ".join(f"`{k}`" for k in passed) + ".")
    else:
        L.append("No second-half input adds to the market's opening price on both Brier and log loss: none goes live. "
                 "The price already carries the table, the goal difference, the first meeting and the stakes.")
    L += ["", "An input that adds to the probability is still not an edge until its bets beat the close (CLV)."]
    return "\n".join(L) + "\n"


def main() -> None:
    res, cover = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(write(res, cover), encoding="utf-8")
    GATE.parent.mkdir(parents=True, exist_ok=True)
    GATE.write_text(json.dumps({"cover": cover, "results": res}, indent=1, sort_keys=True), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
