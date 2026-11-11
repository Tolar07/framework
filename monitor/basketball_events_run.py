"""
Basketball player events for tonight's and tomorrow's NBA games, and the grade of past days (framework #558).
RECORD-ONLY / SHADOW: writes output/basketball_events/ and nothing else; no pick, stake or board reads it.

    python monitor/basketball_events_run.py [--date YYYY-MM-DD]

1. Updates the player-stat log (engine/basketball_events.update_stats) from finished box scores.
2. Per NBA game of the night: the expected starters and available players (data/nba_players.night_sheets), the team
   points of engine/nba_projection.py, each player's expected minutes / points / rebounds / assists / threes with the
   players' points scaled to add up to the team's projected points, and the Over / Under chance at SportyBet's line
   (output/nba_markets, markets 921-924) beside SportyBet's own prices.
3. Label per stat: `shadow` until backtest/basketball_events_study.py lists it in BASKET_PUBLISH.
4. Grades past files from the stat log: MAE and the Over Brier at SportyBet's line, beside the last-10 baseline,
   in output/basketball_events/grades.json.
World basketball and NCAA: team level only (no player box scores in the framework) - listed in config/sport_parity.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_players as npl  # noqa: E402
from engine import basketball_events as be  # noqa: E402
from engine import nba_projection as proj  # noqa: E402

OUT = ROOT / "output" / "basketball_events"
MARKETS = ROOT / "output" / "nba_markets"
STUDY = ROOT / "backtest" / "BASKETBALL_EVENTS_STUDY.md"
GRADE_DAYS = 10


def study_numbers() -> tuple[list[str], dict[str, float]]:
    try:
        txt = STUDY.read_text(encoding="utf-8")
    except OSError:
        return [], dict(be.DEFAULT_DISP)
    m = re.search(r"BASKET_PUBLISH = \[(.*?)\]", txt)
    d = re.search(r"DISP = \{(.*?)\}", txt)
    disp = dict(be.DEFAULT_DISP)
    if d:
        for k, v in re.findall(r"'(\w+)': ([\d.]+)", d.group(1)):
            disp[k] = float(v)
    return (re.findall(r"'(\w+)'", m.group(1)) if m else []), disp


def latest_lines(day: str) -> dict[str, dict]:
    """espn_id -> {norm name: {stat: line row}} from the newest snapshot of each event in the day's market file."""
    path = MARKETS / f"{day}.jsonl"
    best: dict[str, dict] = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("espn_id") and (r["espn_id"] not in best or r["at"] > best[r["espn_id"]]["at"]):
                best[r["espn_id"]] = r
    return {k: be.player_lines(v.get("markets") or []) for k, v in best.items()}


def build_game(game: dict, teams: dict, lg: dict, hist: dict, league: dict, published: list[str],
               disp: dict, lines: dict, day: str) -> dict:
    p = proj.project(game, teams, lg)
    out: dict = {"espn_id": game["espn_id"], "tip": game["tip"], "home": game["home"], "away": game["away"],
                 "players": []}
    pr = p.get("projection")
    out["team_points"] = {"home": pr["home_pts"], "away": pr["away_pts"]} if pr else None
    if pr is None:
        out["why"] = p.get("why") or ["no team projection"]
    for side, sheet, pts in (("home", game["home_sheet"], pr and pr["home_pts"]),
                             ("away", game["away_sheet"], pr and pr["away_pts"])):
        starters = set(sheet.get("starters") or [])
        rows = []
        for pl in sheet.get("players") or []:
            e = be.expected(hist.get(pl["id"], []), league, proj.PLAY_CHANCE.get(pl.get("status", ""), 1.0))
            if e is None or e["min"] < be.MIN_EXPECTED:
                continue
            rows.append({"id": pl["id"], "name": pl["name"], "team": game[side], "starter": pl["name"] in starters,
                         "status": pl.get("status") or "", "min": e["min"], "games": e["games"],
                         **{s: e[s] for s in be.STATS}})
        scale = be.scale_points(rows, pts)
        for r in rows:
            sb = lines.get(be.norm_name(r["name"]), {})
            stats = {}
            for s in be.STATS:
                mean = r.pop(s)
                row = {"mean": round(mean, 2), "label": "proven" if s in published else "shadow",
                       "baseline": round(be.baseline(hist[r["id"]], s), 2)}
                if s in sb:
                    ln = sb[s]
                    row["sportybet"] = {**ln, **(be.over_under(mean, ln["line"], disp[s]) or {})}
                stats[s] = row
            r["stats"] = stats
        out["players"] += rows
        out.setdefault("points_scale", {})[side] = None if scale is None else round(scale, 3)
        out.setdefault("sum_points", {})[side] = round(sum(r["stats"]["pts"]["mean"] for r in rows), 1)
    return out


def grade_files(rows: list[dict], today: date) -> dict:
    """Grade each past file once from the stat log; keep the running record."""
    path = OUT / "grades.json"
    rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"days": {}}
    played = {(r["g"], r["p"]): r for r in rows}
    for f in sorted(OUT.glob("basketball_events_*.json"))[-GRADE_DAYS:]:
        day = f.stem.split("_")[-1]
        if day >= today.isoformat() or day in rec["days"]:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        agg = {s: {"n": 0, "ae": 0.0, "ae_base": 0.0, "brier": 0.0, "n_line": 0} for s in be.STATS}
        for g in data.get("games") or []:
            for p in g.get("players") or []:
                actual = played.get((g["espn_id"], p["id"]))
                if actual is None:
                    continue
                for s, v in p["stats"].items():
                    a = agg[s]
                    a["n"] += 1
                    a["ae"] += abs(v["mean"] - actual[s])
                    a["ae_base"] += abs(v["baseline"] - actual[s])
                    sb = v.get("sportybet")
                    if sb and "over" in sb and actual[s] != sb["line"]:
                        a["n_line"] += 1
                        a["brier"] += (sb["over"] - int(actual[s] > sb["line"])) ** 2
        if any(a["n"] for a in agg.values()):
            rec["days"][day] = agg
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8", newline="\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    a = ap.parse_args()
    now = datetime.now(UTC)
    day = date.fromisoformat(a.date) if a.date else now.date()
    for n in be.update_stats():
        print(f"  stats: {n}")
    rows = be.load_stats()
    published, disp = study_numbers()
    OUT.mkdir(parents=True, exist_ok=True)
    if rows:
        teams, lg = proj.team_table(npl.load_log(npl.TEAM_LOG))
        hist, league = be.by_player(rows), be.league_rates(rows)
        for d in (day, day + timedelta(days=1)):
            start = datetime(d.year, d.month, d.day, 10, tzinfo=UTC)
            try:
                games, _notes = npl.night_sheets(start, start + timedelta(hours=24), now)
            except Exception as e:  # noqa: BLE001 - a data hiccup never stops the run
                print(f"  {d}: player data unavailable ({str(e)[:80]})")
                continue
            lines = latest_lines(d.isoformat())
            doc = {"date": d.isoformat(), "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "label": "shadow", "published_stats": published,
                   "games": [build_game(g, teams, lg, hist, league, published, disp, lines, d.isoformat())
                             for g in games],
                   "gap": "world basketball / NCAA: team level only (no player box scores yet)"}
            (OUT / f"basketball_events_{d.isoformat()}.json").write_text(
                json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
            print(f"  {d}: {len(doc['games'])} games, {sum(len(g['players']) for g in doc['games'])} players")
    else:
        print("  PENDING: no player-stat log yet")
    grade_files(rows, day)
    return 0


if __name__ == "__main__":
    sys.exit(main())
