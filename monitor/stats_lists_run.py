"""
The statistics lists (framework #581-#584, Architect 2026-11-12: "Stats are key"). RECORD / SHADOW / PAPER ONLY:
writes output/league_profiles/, output/first_half/, output/corners/ and the four study reports; no pick, stake or
board reads any of it. The lower-league paper board itself runs inside every universe sweep
(monitor/universe_sweep.py -> engine/lower_league_value.attach); its study is re-run here.

    python monitor/stats_lists_run.py [--no-fetch] [--no-studies]      (stats_lists.yml, started by the VM clock)

1. League profiles (#581)          engine/league_profile.py   -> output/league_profiles/latest.json
2. First-half model, shadow (#582) engine/first_half.py       -> output/first_half/first_half_<date>.json for
                                   today's and tomorrow's rated board fixtures, grades.json (past days against
                                   the half-time score), top_home.json (most first-half goals per home game)
3. Corner consistency (#583)       engine/corner_consistency.py -> output/corners/consistency.json
4. Studies                         backtest/LEAGUE_PROFILE_STUDY.md, FIRST_HALF_STUDY.md,
                                   CORNER_CONSISTENCY_STUDY.md, LOWER_LEAGUE_VALUE_STUDY.md, and
                                   MARKET_RATES_STUDY.md (every market of every sport we cover)
Every step runs on its own: one failing never stops the others.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PICKS = ROOT / "output" / "picks"
FH_OUT = ROOT / "output" / "first_half"
GRADE_DAYS = 14


def first_half(now: datetime, fetch: bool) -> str:
    from engine import first_half as fh
    from engine import fixture_match as fm
    from engine import stats_history as sh
    prev = f"{int(sh.CURRENT[:2]) - 1:02d}{int(sh.CURRENT[2:]) - 1:02d}"
    hist, _ = sh.load_history(seasons=(prev, sh.CURRENT), fetch=fetch)
    sporty = sh.load_sportybet()
    model = fh.FirstHalf(hist)
    FH_OUT.mkdir(parents=True, exist_ok=True)
    built = []
    for day in (now.date(), now.date() + timedelta(days=1)):
        path = PICKS / f"picks_{day}.json"
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        games = []
        for r in doc.get("rated") or []:
            if isinstance(r, dict) and r.get("home") and r.get("away"):
                games.append({"home": r["home"], "away": r["away"], "league": r.get("league"),
                              "kickoff": r.get("kickoff") or r.get("ko"),
                              **model.predict(r.get("league"), r["home"], r["away"])})
        (FH_OUT / f"first_half_{day}.json").write_text(json.dumps(
            {"date": str(day), "label": "shadow", "built": now.strftime("%Y-%m-%dT%H:%MZ"),
             "model": "engine/first_half.py", "study": "backtest/FIRST_HALF_STUDY.md", "games": games},
            indent=1, ensure_ascii=False), encoding="utf-8")
        built.append(f"{day}: {len(games)}")
    # grade past days against half-time scores (football-data rows and the SportyBet sweep, same date)
    played = [r for r in hist + sporty if r.get("hthg") is not None]
    rec = {"games": 0, "brier": 0.0, "brier_league": 0.0, "hit_over05": 0, "mean_p": 0.0}
    today = now.date()
    for f in sorted(FH_OUT.glob("first_half_*.json")):
        day = f.stem.rsplit("_", 1)[1]
        try:
            d = date.fromisoformat(day)
        except ValueError:
            continue
        if d >= today or (today - d).days > GRADE_DAYS:
            continue
        rows = [r for r in played if r["date"] == day]
        for g in json.loads(f.read_text(encoding="utf-8")).get("games", []):
            hit = fm.find_match(g["home"], g["away"], rows, lambda r: (r["home"], r["away"]))
            if not hit or not hit.strong:
                continue
            y = int(hit.item["hthg"] + hit.item["htag"] > 0)
            base = model.league_over05(g.get("league"))
            rec["games"] += 1
            rec["brier"] += (g["over05"] - y) ** 2
            rec["brier_league"] += (base - y) ** 2
            rec["hit_over05"] += y
            rec["mean_p"] += g["over05"]
    n = rec["games"]
    if n:
        for k in ("brier", "brier_league", "mean_p"):
            rec[k] = round(rec[k] / n, 4)
        rec["hit_over05"] = round(rec["hit_over05"] / n, 4)
    rec.update(graded_at=now.strftime("%Y-%m-%dT%H:%MZ"), days=GRADE_DAYS, label="shadow")
    (FH_OUT / "grades.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    cur = [r for r in hist if r["season"] == sh.CURRENT]
    since = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    tops = fh.top_home(cur + [r for r in sporty if r["date"] >= since])
    (FH_OUT / "top_home.json").write_text(json.dumps(
        {"generated_at": now.strftime("%Y-%m-%dT%H:%MZ"), "min_home_games": fh.MIN_TEAM,
         "population": len({(r["home"], r["league"]) for r in cur + sporty if r.get("hthg") is not None}),
         "source": f"football-data.co.uk {sh.CURRENT} + SportyBet sweep (last 60 days)", "teams": tops},
        indent=1, ensure_ascii=False), encoding="utf-8")
    return f"first half: boards {', '.join(built) or 'none'}; graded {n}; top home {len(tops)}"


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    fetch = "--no-fetch" not in argv
    now = datetime.now(UTC)
    steps = []

    def step(name, fn):
        try:
            steps.append(fn())
        except Exception as e:  # noqa: BLE001 - one list failing never stops the others
            steps.append(f"{name}: FAILED ({type(e).__name__}: {str(e)[:120]})")

    from engine import corner_consistency as cc
    from engine import league_profile as lp
    step("league profiles", lambda: lp.run(now, fetch=fetch))
    step("first half", lambda: first_half(now, fetch))
    step("corners", lambda: cc.run(now, fetch=fetch))
    # lists 7-21 and the index the live list test picks from (engine/stat_lists.py, engine/list_picks.py)
    from engine import stat_lists as sl
    step("stat lists 7-21", lambda: sl.write(sl.build(now=now, tennis=fetch)))
    if "--no-studies" not in argv:
        sys.path.insert(0, str(ROOT / "backtest"))
        import corner_consistency_study
        import first_half_study
        import league_profile_study
        import lower_league_value_study
        import market_rates_study
        flag = [] if fetch else ["--no-fetch"]
        for mod in (league_profile_study, first_half_study, corner_consistency_study):
            step(mod.__name__, lambda m=mod: f"{m.__name__}: exit {m.main(flag)}")
        step("lower_league_value_study", lambda: f"lower_league_value_study: exit {lower_league_value_study.main([])}")
        step("market_rates_study", lambda: f"market_rates_study: exit {market_rates_study.main([])}")
    print("\n".join(steps))
    return 1 if all("FAILED" in s for s in steps) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
