"""
EUROPEAN CONGESTION STUDY (Architect 2026-11-09 plan, step 2: "it varies for
different competitions"). Motivation across competitions mostly shows as
rotation: a club with a European game a few days before or after a league
match may rest players, more so before a knockout tie. The rest study
(REST_STUDY.md) couldn't see this: football-data has league games only.
data/euro_fixtures adds every Champions / Europa / Conference League game.

For every league match (9 countries with European clubs, 2018-19 to 2025-26),
per side: a European game within NEAR days BEFORE, within NEAR days AFTER, and
a knockout game (February-May) within NEAR days after. Inputs (home minus away
unless named): euro_before_gap, euro_after_gap, euro_ko_after_gap, and
euro_any (how many of the two have a European game either side, for totals).

Same test as backtest/second_half_study: the market's opening price (de-vigged,
market average) is the baseline, each input's weight is fitted on earlier days
only, verdict on Brier and log loss (2 standard errors), ROI / CLV of the bets.
Also scored on second-half games only (late, when league stakes and cup
stakes pull against each other). A study, not a selector.

    python backtest/euro_congestion_study.py
"""
from __future__ import annotations

import bisect
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.inputs_study import wf_preds  # noqa: E402
from backtest.second_half_study import SEASONS, market_rows, money  # noqa: E402
from data import euro_fixtures as ef  # noqa: E402
from engine import inputs as ip  # noqa: E402

OUT = ROOT / "backtest" / "EURO_CONGESTION_STUDY.md"
GATE = ROOT / "memory" / "euro_congestion_gate.json"
NEAR = 4
FEATS = ("euro_before_gap", "euro_after_gap", "euro_ko_after_gap", "euro_any")
OUTCOMES = ("home win", "draw", "away win", "over 2.5")


def _shift(d: str, k: int) -> str:
    return (date.fromisoformat(d) + timedelta(days=k)).isoformat()


def side_flags(games: list[dict], day: str) -> dict[str, int]:
    """games: one club's European games sorted by date. Flags for a league match on `day`."""
    ds = [g["date"] for g in games]
    i = bisect.bisect_left(ds, day)
    before = i > 0 and ds[i - 1] >= _shift(day, -NEAR)
    j = bisect.bisect_right(ds, day)
    after = j < len(ds) and ds[j] <= _shift(day, NEAR)
    ko = after and games[j]["ko"]
    return {"before": int(before), "after": int(after), "ko": int(bool(ko))}


def features(eu: dict[str, list[dict]], home: str, away: str, day: str) -> dict[str, float]:
    h, a = side_flags(eu.get(home, []), day), side_flags(eu.get(away, []), day)
    return {"euro_before_gap": float(h["before"] - a["before"]),
            "euro_after_gap": float(h["after"] - a["after"]),
            "euro_ko_after_gap": float(h["ko"] - a["ko"]),
            "euro_any": float(max(h["before"], h["after"]) + max(a["before"], a["after"]))}


def collect(load=None) -> tuple[dict, dict]:
    if load is None:
        from data.football_data_source import load_league as load
    rows: dict[tuple, list] = {(o, f, seg): [] for o in OUTCOMES for f in FEATS for seg in ("all", "second half")}
    cover: dict[str, Any] = {"league_seasons": 0, "matches": 0, "with_euro_side": 0, "unmatched": []}
    for lg in ef.COUNTRY:
        for s in SEASONS:
            try:
                ms, _ = load(lg, s)
            except Exception as err:  # noqa: BLE001
                print(f"  {lg} {s}: skipped ({str(err)[:60]})", flush=True)
                continue
            clubs = sorted({m.home_team for m in ms} | {m.away_team for m in ms})
            eu, miss = ef.club_dates(s, lg, clubs)
            cover["unmatched"] += [f"{s} {lg}: {x}" for x in miss]
            cover["league_seasons"] += 1
            H = ip.History(ip.from_results(ms))
            for m in sorted(ms, key=lambda r: r.date):
                mk = market_rows(m)
                if not mk:
                    continue
                f = features(eu, m.home_team, m.away_team, m.date)
                cover["matches"] += 1
                cover["with_euro_side"] += f["euro_any"] > 0
                sh = ip.second_half(H, m.home_team, m.away_team, m.date)["half_ppg_gap"] is not None
                for o, (p, y, e) in mk.items():
                    for k in FEATS:
                        rows[(o, k, "all")].append((m.date, p, y, f[k], e))
                        if sh:
                            rows[(o, k, "second half")].append((m.date, p, y, f[k], e))
            print(f"  {lg} {s}: {cover['matches']} matches so far", flush=True)
    res = {}
    for key, rs in rows.items():
        summ, scored = wf_preds(rs)
        summ["money"] = money(scored)
        res[" | ".join(key)] = summ
    return res, cover


def write(res: dict, cover: dict) -> str:
    L = ["# EUROPEAN CONGESTION STUDY — does a European game either side of a league match beat the price?", "",
         "Written by `backtest/euro_congestion_study.py` (Architect 2026-11-09). League matches of "
         + ", ".join(ef.COUNTRY) + f", seasons {SEASONS[0]}-{SEASONS[-1]}; European games from openfootball "
         f"(Champions League from 2018-19, Europa / Conference League from 2020-21 / 2021-22). A side is flagged "
         f"with a European game within {NEAR} days before / after; knockout = February-May. Baseline: the "
         "market's opening price, de-vigged. Each input's weight fitted on earlier days only; a verdict needs 100+ "
         "scored matches and 2 standard errors. Money: bets at chance x opening >= 1.03, ROI at the opening price, "
         "CLV = opening / closing - 1.", "",
         f"Coverage: {cover['league_seasons']} league-seasons, {cover['matches']} matches, "
         f"{cover['with_euro_side']} with a European game either side for at least one club; "
         f"{len(cover['unmatched'])} European club names left unmatched.", ""]
    for seg in ("all", "second half"):
        L += [f"## {seg.capitalize()} league games", "",
              "| outcome | input | scored | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | "
              "with input: ROI ± se / CLV (bets) |", "|---|---|---|---|---|---|---|"]
        for o in OUTCOMES:
            for k in FEATS:
                s = res.get(f"{o} | {k} | {seg}")
                if not s or not s.get("scored"):
                    L.append(f"| {o} | {k} | 0 | PENDING | PENDING | NOT ENOUGH DATA | - |")
                    continue
                mf = s["money"]["with_feature"]
                L.append(f"| {o} | {k} | {s['scored']} | {s['brier_gain']:+.5f} ± {s['brier_se']:.5f} | "
                         f"{s['logloss_gain']:+.5f} ± {s['logloss_se']:.5f} | {s['verdict']} / "
                         f"{s['verdict_logloss']} | {mf['roi']:+.2f}% ± {mf['roi_se']:.2f} / {mf['clv']:+.2f}% "
                         f"({mf['bets']}) |")
        L.append("")
    passed = [k for k, s in res.items()
              if s.get("verdict") == "ADDS INFORMATION" and s.get("verdict_logloss") == "ADDS INFORMATION"]
    L += ["## Verdict", ""]
    L.append(("Inputs that add to the opening price on both Brier and log loss (shadow first, never straight to "
              "stakes): " + ", ".join(f"`{k}`" for k in passed) + ".") if passed else
             "No European-congestion input adds to the market's opening price on both Brier and log loss: none "
             "goes live. The price already carries the midweek.")
    L += ["", "Limit: domestic cups are still invisible (no free multi-season cup fixture source wired)."]
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
