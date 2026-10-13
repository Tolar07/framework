"""
13 OCT DEEP STUDY — the end-of-day analysis (Architect: "do an analysis of
everything at the end of today ... the fixtures we were not involved in ...
look at their stats ... in-depth dive").

Reads what the day left behind and writes backtest/DAY_STUDY_2026-10-13.md:
  1. every leg made on 13 Oct graded together — live board, the superseded
     02:19 board, the study board, the BTTS calls — and P/L by market type;
  2. the Unders: every Under-goals leg (did both teams score, total goals),
     SportyBet's own Over/Under 3.5 calibration across the universe archive,
     and the walk-forward model calibration (backtest/GOALS_LINE_STUDY.md);
  3. every FotMob game of the day with post-match stats (day_stats.jsonl):
     which stats went with BTTS, with 4+ goals, with an Under 3.5 losing;
  4. whether pre-match team profiles told more than SportyBet's price.

    python data/study/2026-10-13/deep_study.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import grade_day as gd  # noqa: E402

from data.flashscore_results import _sim  # noqa: E402
from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "DAY_STUDY_2026-10-13.md"
FAMILY = {"1": "1X2", "10": "Double chance", "11": "Draw no bet", "13": "Home/Away no bet", "14": "European handicap",
          "16": "Asian handicap", "18": "Match goals O/U", "19": "Team goals O/U", "20": "Team goals O/U",
          "24": "Team goals band", "26": "Odd/Even", "29": "BTTS", "33": "Win to nil", "36": "Total & BTTS",
          "37": "1X2 & total", "63": "1st half double chance", "547": "Double chance & total", "548": "Multigoals"}


def res_for(name: str, res: dict) -> dict | None:
    h, a = name.split(" v ", 1)
    best = max(res, key=lambda k: min(_sim(h, k.split(" v ")[0]), _sim(a, k.split(" v ", 1)[1])), default=None)
    if best and min(_sim(h, best.split(" v ")[0]), _sim(a, best.split(" v ", 1)[1])) >= 0.6:
        return res[best]
    return None


def all_legs(res: dict) -> list[dict]:
    """[{board, fixture, family, pick, price, result}] — every 13 Oct leg."""
    legs = []
    live = json.loads((ROOT / "output/picks/picks_2026-10-13.json").read_text(encoding="utf-8"))
    sup = json.loads((ROOT / "output/picks/superseded/picks_2026-10-13_20261013T0219.json").read_text(encoding="utf-8"))
    for board, doc in (("live board", live), ("02:19 board (superseded)", sup)):
        for p in doc["singles"]:
            mid, spec, outcome = (p["market"].replace("SB:", "").split("|") + ["", ""])[:3]
            legs.append({"board": board, "fixture": p["fixture"], "family": FAMILY.get(mid, mid), "pick": p["pick"],
                         "price": p["price"], "spec": spec, "outcome": outcome, "mid": mid,
                         "result": gd.settle(mid, spec, outcome, res_for(p["fixture"], res))})
    study = json.loads((HERE / "engine_board.json").read_text(encoding="utf-8"))
    for leg in study["legs"]:
        pk = leg["pick"]
        sel = pk["sel"]
        legs.append({"board": "study board", "fixture": leg["match"], "family": FAMILY.get(str(sel["marketId"]), pk["fam"]),
                     "pick": f"{pk['mdesc']} {pk['pick']}", "price": pk["price"], "spec": sel.get("specifier", ""),
                     "outcome": pk["pick"], "mid": str(sel["marketId"]), "stated": pk["win"],
                     "result": gd.settle(sel["marketId"], sel.get("specifier", ""), pk["pick"], res_for(leg["match"], res))})
    codes = json.loads((HERE / "study_codes_v2.json").read_text(encoding="utf-8"))
    for b in codes["btts"]:
        legs.append({"board": "BTTS calls", "fixture": b["match"], "family": "BTTS", "pick": f"BTTS {b['call']}",
                     "price": b["price"], "spec": "", "outcome": b["call"], "mid": "29", "stated": b["win"],
                     "result": gd.settle("29", "", b["call"], res_for(b["match"], res))})
    return legs


def pl(rows: list[dict]) -> tuple[int, int, int, float]:
    done = [r for r in rows if r["result"] in ("won", "lost", "void")]
    w = sum(r["result"] == "won" for r in done)
    lost = sum(r["result"] == "lost" for r in done)
    ret = sum(r["price"] if r["result"] == "won" else 1.0 if r["result"] == "void" else 0.0 for r in done)
    return w, lost, len(done) - w - lost, ret - len(done)


def universe_ou35() -> list[str]:
    """SportyBet's own Under 3.5: its fair chance (last price, margin removed) against what landed."""
    bands: dict[float, list] = defaultdict(list)
    for r in uv.load_graded():
        if r.get("sport") != "football" or not r.get("result") or r["result"].get("after_90"):
            continue
        p = (r.get("last") or {}).get("p", {}).get("ou3.5")
        if not p or min(p) <= 1:
            continue
        fair_u = (1 / p[1]) / (1 / p[0] + 1 / p[1])
        b = min(int(fair_u * 10), 9) / 10
        bands[b].append((fair_u, int(r["result"]["h"] + r["result"]["a"] <= 3), p[1]))
    L = ["| SportyBet's fair Under 3.5 | games | landed | stated (avg) | £1 at its price |", "|---|---:|---:|---:|---:|"]
    for b in sorted(bands):
        xs = bands[b]
        if len(xs) >= 20:
            L.append(f"| {b:.0%}–{b + 0.1:.0%} | {len(xs)} | {100 * sum(x[1] for x in xs) / len(xs):.1f}% | "
                     f"{100 * sum(x[0] for x in xs) / len(xs):.1f}% | {100 * sum(x[1] * x[2] - 1 for x in xs) / len(xs):+.1f}% |")
    return L


def stats_section() -> tuple[list[str], list[dict]]:
    path = HERE / "day_stats.jsonl"
    games = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    games = [g for g in games if g["stats"].get("sot") and None not in g["ft"]]
    with_xg = sum(1 for g in games if g["stats"].get("xg"))
    L = [f"FotMob listed {len(games)} finished games with post-match stats (covered or not); {with_xg} of them "
         "publish xG (lower leagues mostly don't — their xG rows are the xG games only). Ball recoveries and "
         "distance covered: FotMob publishes neither — PENDING.", ""]
    if not games:
        return L + ["NO DATA — PENDING"], games
    keys = ["xg", "xgot", "shots", "sot", "big", "box_touches", "possession", "tackles", "interceptions",
            "duels_won", "aerials", "clearances", "saves", "corners", "fouls"]

    def total(g, k):
        v = g["stats"].get(k)
        return None if not v or None in v else (v[0] + v[1] if k != "possession" else abs(v[0] - v[1]))

    def low(g, k):
        v = g["stats"].get(k)
        return None if not v or None in v else min(v)
    groups = {"BTTS yes": [g for g in games if min(g["ft"]) > 0], "BTTS no": [g for g in games if min(g["ft"]) == 0],
              "4+ goals (Under 3.5 lost)": [g for g in games if sum(g["ft"]) >= 4],
              "0–3 goals (Under 3.5 won)": [g for g in games if sum(g["ft"]) <= 3]}
    L += ["Match totals (both sides added; possession = the gap between the sides). 'Weaker side' = the lower of "
          "the two teams' figure — what decides BTTS.", "",
          "| Stat | BTTS yes | BTTS no | 4+ goals | 0–3 goals | weaker side: BTTS yes | weaker side: BTTS no |",
          "|---|---:|---:|---:|---:|---:|---:|"]

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return f"{sum(xs) / len(xs):.2f}" if xs else "PENDING"
    for k in keys:
        L.append(f"| {k} | " + " | ".join(avg([total(g, k) for g in groups[n]]) for n in groups) + " | "
                 f"{avg([low(g, k) for g in groups['BTTS yes']])} | {avg([low(g, k) for g in groups['BTTS no']])} |")
    L += ["", f"Games: BTTS yes {len(groups['BTTS yes'])}, no {len(groups['BTTS no'])}; 4+ goals "
          f"{len(groups['4+ goals (Under 3.5 lost)'])}, 0–3 {len(groups['0–3 goals (Under 3.5 won)'])}."]
    # finishing: goals minus xG
    xgames = [g for g in games if g["stats"].get("xg") and None not in g["stats"]["xg"]]
    over = sorted(xgames, key=lambda g: -(sum(g["ft"]) - (g["stats"]["xg"][0] + g["stats"]["xg"][1])))
    L += ["", "Biggest finishing swings (goals − xG, both sides):"]
    for g in over[:5] + over[-5:]:
        gx = g["stats"]["xg"][0] + g["stats"]["xg"][1]
        L.append(f"- {g['home']} {g['ft'][0]}-{g['ft'][1]} {g['away']} ({g['league']}): xG {gx:.2f}, "
                 f"goals − xG {sum(g['ft']) - gx:+.2f}")
    return L, games


def profile_section(games: list[dict]) -> list[str]:
    """Pre-match profiles (data/teams) for the day's games against BTTS / 4+ goals, beside the price."""
    from data import league_strength as ls
    from data import team_profiles as tp
    db, st = tp.load(), ls.load()
    graded = {(r["home"], r["away"]): r for r in uv.load_graded() if r.get("sport") == "football"
              and (r.get("ko") or "")[:10] == "2026-10-13" and r.get("result")}
    rows = []
    for g in [g for g in games if g["stats"].get("xg")]:
        th, ta = tp.find(db, g["home"]), tp.find(db, g["away"])
        if not th or not ta:
            continue
        r = tp.profile_read(th, ta, ls.gap(st, th.get("stats_league"), ta.get("stats_league")))
        if r.get("home_goals_hint") is None:
            continue
        h, a = r["home_goals_hint"], r["away_goals_hint"]
        p_btts = (1 - math.exp(-h)) * (1 - math.exp(-a))
        lam = h + a
        p_4 = 1 - sum(math.exp(-lam) * lam ** k / math.factorial(k) for k in range(4))
        sb = next((v for (hh, aa), v in graded.items() if min(_sim(g["home"], hh), _sim(g["away"], aa)) >= 0.6), None)
        bp = (sb or {}).get("last", {}).get("p", {}).get("btts") if sb else None
        mk = (1 / bp[0]) / (1 / bp[0] + 1 / bp[1]) if bp and min(bp) > 1 else None
        rows.append({"p_btts": p_btts, "p_4": p_4, "mk_btts": mk, "btts": int(min(g["ft"]) > 0), "four": int(sum(g["ft"]) >= 4)})
    if not rows:
        return ["NO DATA — PENDING (no game of the day had both teams in the profile database)"]
    n = len(rows)
    b_prof = sum((r["p_btts"] - r["btts"]) ** 2 for r in rows) / n
    with_mk = [r for r in rows if r["mk_btts"] is not None]
    L = [f"{n} of the day's games had both teams profiled. Profile BTTS chance said {100 * sum(r['p_btts'] for r in rows) / n:.0f}% "
         f"on average, BTTS landed {100 * sum(r['btts'] for r in rows) / n:.0f}%; profile 4+ goals said "
         f"{100 * sum(r['p_4'] for r in rows) / n:.0f}%, landed {100 * sum(r['four'] for r in rows) / n:.0f}%. "
         f"Brier (BTTS): profile {b_prof:.3f}."]
    if with_mk:
        m = len(with_mk)
        bm = sum((r["mk_btts"] - r["btts"]) ** 2 for r in with_mk) / m
        bp2 = sum((r["p_btts"] - r["btts"]) ** 2 for r in with_mk) / m
        bb = sum((0.75 * r["mk_btts"] + 0.25 * r["p_btts"] - r["btts"]) ** 2 for r in with_mk) / m
        L.append(f"On the {m} that also had SportyBet's BTTS price: Brier market {bm:.3f}, profile {bp2:.3f}, "
                 f"75/25 blend {bb:.3f} (lower is better).")
    L.append(f"Sample: {n} games, one day — too small to say the profiles beat the price; it goes into "
             "backtest/PROFILE_STUDY.md's running count (P1–P5 paper rules from 13 Oct).")
    return L


def main() -> None:
    res = gd.results()
    legs = all_legs(res)
    L = ["# DAY STUDY — 13 Oct 2026", "",
         "End-of-day analysis (`data/study/2026-10-13/deep_study.py`). Results from FotMob (full time; half time from "
         "the goal minutes). £1 flat on every leg.", "", "## 1. Everything made today, graded", "",
         "| Board | legs | won | lost | void | P/L |", "|---|---:|---:|---:|---:|---:|"]
    for board in ("live board", "02:19 board (superseded)", "study board", "BTTS calls"):
        w, lost, v, p = pl([r for r in legs if r["board"] == board])
        L.append(f"| {board} | {w + lost + v} | {w} | {lost} | {v} | {p:+.2f}u |")
    pend = [r for r in legs if r["result"] == "PENDING"]
    if pend:
        L.append(f"\nPENDING (no result or rule): {', '.join(r['fixture'] + ' ' + r['pick'] for r in pend)}")
    L += ["", "### By market type (all boards together)", "", "| Market | legs | won | lost | void | P/L |", "|---|---:|---:|---:|---:|---:|"]
    fam = defaultdict(list)
    for r in legs:
        fam[r["family"]].append(r)
    for f, rs in sorted(fam.items(), key=lambda kv: pl(kv[1])[3]):
        w, lost, v, p = pl(rs)
        L.append(f"| {f} | {w + lost + v} | {w} | {lost} | {v} | {p:+.2f}u |")
    st = [r for r in legs if r.get("stated") is not None and r["result"] in ("won", "lost")]
    if st:
        L += ["", f"Stated chance vs landed (study board + BTTS calls, {len(st)} decided): said "
              f"{100 * sum(r['stated'] for r in st) / len(st):.0f}% on average, landed "
              f"{100 * sum(r['result'] == 'won' for r in st) / len(st):.0f}%."]
    # 2. Unders
    L += ["", "## 2. The Unders", "", "Every Under-goals leg on any 13 Oct board:", "",
          "| Board | Fixture | Pick | Result | Score | BTTS |", "|---|---|---|---|---|---|"]
    for r in legs:
        if r["outcome"].startswith("Under"):
            rr = res_for(r["fixture"], res)
            sc = f"{rr['ft'][0]}-{rr['ft'][1]}" if rr else "PENDING"
            bt = ("yes" if min(rr["ft"]) > 0 else "no") if rr else "PENDING"
            L.append(f"| {r['board']} | {r['fixture']} | {r['pick']} | {r['result']} | {sc} | {bt} |")
    L += ["", "SportyBet's own Under 3.5 across every graded universe game (its fair chance, margin removed, vs landed):", ""]
    L += universe_ou35()
    gl = ROOT / "backtest" / "GOALS_LINE_STUDY.md"
    L += ["", "The model's own 3.5 / 4.5 lines, walk-forward: see `backtest/GOALS_LINE_STUDY.md`"
          + (" (below)." if gl.exists() else " — PENDING (still running).")]
    if gl.exists():
        L += [""] + gl.read_text(encoding="utf-8").split("\n", 4)[4].splitlines()
    # 3. stats
    L += ["", "## 3. Every game of the day — what the stats say", ""]
    s_lines, games = stats_section()
    L += s_lines
    # 4. profiles
    L += ["", "## 4. Did pre-match team profiles tell more than the price?", ""] + profile_section(games)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
