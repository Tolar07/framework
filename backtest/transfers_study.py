"""
TRANSFERS STUDY (Architect 2026-11-09 plan, step 5). Does what a club did in the
January window (data/transfers: FotMob's signings and departures, market value,
else fee) tell us anything the price doesn't, for its league games after the window?

Season 2025-26 only: FotMob keeps moves from January 2026, so last winter's window
is the one on record. Every league game from 4 February 2026 to the season's end,
both clubs found in the transfer record. Inputs (home minus away, euros in millions,
signed log so one mega-deal doesn't swamp the rest):
  jan_net_gap      net value signed minus sold in the window
  jan_in_gap       value signed
  jan_out_gap      value sold (positive = the home side lost more)
  jan_top_out_gap  the biggest single departure
  jan_moves        how many moves both clubs made (for totals and the draw)

Same test as backtest/second_half_study: de-vigged opening price (market average)
as the baseline, weights fitted on earlier days only, Brier and log loss with two
standard errors, ROI and CLV of the bets. One season is small: a NOT ENOUGH DATA or
NO CLEAR EFFECT here says "keep recording", not "transfers don't matter". The
weekly record (profiles.yml) builds the 2026-27 winter window for the re-run.

    python backtest/transfers_study.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.inputs_study import wf_preds  # noqa: E402
from backtest.second_half_study import LEAGUES, LOWER, market_rows, money  # noqa: E402
from data import euro_fixtures as ef  # noqa: E402
from data import transfers as tr  # noqa: E402
from engine.name_match import resolve  # noqa: E402

OUT = ROOT / "backtest" / "TRANSFERS_STUDY.md"
GATE = ROOT / "memory" / "transfers_gate.json"
SEASON = "2526"
FEATS = ("jan_net_gap", "jan_in_gap", "jan_out_gap", "jan_top_out_gap", "jan_moves")
OUTCOMES = ("home win", "draw", "away win", "over 2.5")


def slog(x: float) -> float:
    """Signed log of a euro amount in millions."""
    m = x / 1e6
    return math.copysign(math.log1p(abs(m)), m)


def link(fotmob_names: list[str], fd_names: list[str]) -> dict[str, str]:
    """{football-data name: FotMob name}, strict: exact, the name resolver, then the
    European-fixtures token rule; ambiguous names are left out."""
    out = {n: n for n in fd_names if n in fotmob_names}
    for fm_name, fd in resolve(fotmob_names, fd_names).items():
        out.setdefault(fd, fm_name)
    for fm_name in fotmob_names:
        if fm_name in out.values():
            continue
        hit = ef.match_club(fm_name, [n for n in fd_names if n not in out])
        if hit:
            out[hit] = fm_name
    return out


def features(wh: dict, wa: dict) -> dict[str, float]:
    return {"jan_net_gap": slog(wh["net"]) - slog(wa["net"]),
            "jan_in_gap": slog(wh["value_in"]) - slog(wa["value_in"]),
            "jan_out_gap": slog(wh["value_out"]) - slog(wa["value_out"]),
            "jan_top_out_gap": slog(wh["top_out"]) - slog(wa["top_out"]),
            "jan_moves": float(wh["n_in"] + wh["n_out"] + wa["n_in"] + wa["n_out"])}


def collect(record: dict, load=None) -> tuple[dict, dict]:
    if load is None:
        from data.football_data_source import load_league as load
    start, end = tr.winter_window("2026-01-15")
    rows: dict[tuple, list] = {(o, f): [] for o in OUTCOMES for f in FEATS}
    cover: dict[str, Any] = {"leagues": 0, "matches": 0, "unlinked_teams": []}
    for lg in LEAGUES + LOWER:
        teams = record.get(lg) or {}
        if not teams:
            continue
        try:
            ms, _ = load(lg, SEASON)
        except Exception as err:  # noqa: BLE001
            print(f"  {lg}: skipped ({str(err)[:60]})", flush=True)
            continue
        fd_names = sorted({m.home_team for m in ms} | {m.away_team for m in ms})
        ln = link(sorted(teams), fd_names)
        cover["unlinked_teams"] += [f"{lg}: {n}" for n in fd_names if n not in ln]
        cover["leagues"] += 1
        win = {fd: tr.window(teams[fmn]["moves"], start, end) for fd, fmn in ln.items()}
        for m in sorted(ms, key=lambda r: r.date):
            if m.date < end or m.home_team not in win or m.away_team not in win:
                continue
            mk = market_rows(m)
            if not mk:
                continue
            f = features(win[m.home_team], win[m.away_team])
            cover["matches"] += 1
            for o, (p, y, e) in mk.items():
                for k in FEATS:
                    rows[(o, k)].append((m.date, p, y, f[k], e))
        print(f"  {lg}: {cover['matches']} matches so far", flush=True)
    res = {}
    for key, rs in rows.items():
        summ, scored = wf_preds(rs)
        summ["money"] = money(scored)
        res[" | ".join(key)] = summ
    return res, cover


def write(res: dict, cover: dict) -> str:
    L = ["# TRANSFERS STUDY — does the January window beat the price for the games after it?", "",
         "Written by `backtest/transfers_study.py` (Architect 2026-11-09). Season 2025-26, league games from "
         "4 February 2026; January 2026 moves from FotMob (market value, else fee). Baseline: the market's "
         "opening price, de-vigged. Weights fitted on earlier days only; a verdict needs 100+ scored matches and "
         "2 standard errors. One season: a null result means keep recording, not that transfers don't matter.", "",
         f"Coverage: {cover['leagues']} leagues, {cover['matches']} matches with both clubs on the transfer record; "
         f"{len(cover['unlinked_teams'])} club-seasons not linked (mostly clubs relegated since, which FotMob's "
         "current league pages no longer list).", "",
         "| outcome | input | scored | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | "
         "with input: ROI ± se / CLV (bets) |", "|---|---|---|---|---|---|---|"]
    for o in OUTCOMES:
        for k in FEATS:
            s = res.get(f"{o} | {k}")
            if not s or not s.get("scored"):
                L.append(f"| {o} | {k} | 0 | PENDING | PENDING | NOT ENOUGH DATA | - |")
                continue
            mf = s["money"]["with_feature"]
            L.append(f"| {o} | {k} | {s['scored']} | {s['brier_gain']:+.5f} ± {s['brier_se']:.5f} | "
                     f"{s['logloss_gain']:+.5f} ± {s['logloss_se']:.5f} | {s['verdict']} / {s['verdict_logloss']} | "
                     f"{mf['roi']:+.2f}% ± {mf['roi_se']:.2f} / {mf['clv']:+.2f}% ({mf['bets']}) |")
    passed = [k for k, s in res.items()
              if s.get("verdict") == "ADDS INFORMATION" and s.get("verdict_logloss") == "ADDS INFORMATION"]
    L += ["", "## Verdict", "",
          ("Inputs that add to the opening price on both Brier and log loss (shadow first): "
           + ", ".join(f"`{k}`" for k in passed) + ".") if passed else
          "No January-window input adds to the market's opening price on both Brier and log loss this season: "
          "none goes live. The weekly record keeps building for the 2026-27 window."]
    return "\n".join(L) + "\n"


def main() -> None:
    record = tr.latest()
    if not record:
        print("NO DATA — PENDING: run python data/transfers.py first")
        return
    res, cover = collect(record)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(write(res, cover), encoding="utf-8")
    GATE.parent.mkdir(parents=True, exist_ok=True)
    GATE.write_text(json.dumps({"cover": cover, "results": res}, indent=1, sort_keys=True), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
