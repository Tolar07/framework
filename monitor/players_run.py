"""
Football player predictions for today's and tomorrow's rated fixtures, and the grade of past days (framework #557).
RECORD-ONLY / SHADOW: writes output/players/ and nothing else; no pick, stake or board reads it.

    python monitor/players_run.py [--date YYYY-MM-DD]

1. Needs output/events/events_<date>.json (the team totals, monitor/events_run.py) and the board's rated fixtures.
2. The predicted XI of each side comes from FotMob's lineup for the match (data/fotmob.py, strict two-name match);
   no lineup = that side reads PENDING (HR35), nothing invented.
3. engine/player_model.py turns the team totals into per-player numbers that add up to them; written to
   output/players/players_<date>.json, label "shadow" until backtest/player_study.py publishes a stat (PLAYER_PUBLISH).
4. Grades past files against data/match_players (the same game's players): Brier of "carded" and its running record
   in output/players/grades.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import match_stats as ms  # noqa: E402
from engine import event_model as em  # noqa: E402
from engine import fixture_match as fm  # noqa: E402
from engine import player_model as pm  # noqa: E402

PICKS = ROOT / "output" / "picks"
EVENTS = ROOT / "output" / "events"
OUT = ROOT / "output" / "players"
STUDY = ROOT / "backtest" / "PLAYER_MODEL_STUDY.md"
GRADE_DAYS = 10
BASE = {"card_chance": "cards", "scorer_chance": "sot"}   # output key -> the study event that vouches for it


def published() -> list[str]:
    try:
        m = re.search(r"PLAYER_PUBLISH = \[(.*?)\]", STUDY.read_text(encoding="utf-8"))
    except OSError:
        return []
    return re.findall(r"'(\w+)'", m.group(1)) if m else []


def lineup(details: dict) -> dict:
    """{"home": [{id, name, gk, position}], "away": [...], "type": predicted|confirmed|None} from a FotMob page."""
    lu = (details.get("content") or {}).get("lineup") or {}
    out: dict = {"type": lu.get("lineupType"), "referee": (ms.referee(details) or {}).get("name")}
    for side in ("home", "away"):
        t = lu.get(side + "Team") or {}
        out[side] = [{"id": p.get("id"), "name": p.get("name"), "gk": bool(p.get("isGoalkeeper")) or
                      p.get("positionId") == 0, "position": p.get("positionStringShort") or p.get("role")}
                     for p in t.get("starters") or [] if p.get("id") is not None]
    return out


def predict_day(day: str, model: pm.PlayerModel, matches: list[dict], allowed: list[str], fetch=None) -> dict | None:
    """fetch(day) -> FotMob match list, fetch_details(id) -> page; injected in tests, FotMob otherwise."""
    ev_path = EVENTS / f"events_{day}.json"
    if not ev_path.exists() or not (PICKS / f"picks_{day}.json").exists():
        return None
    events = json.loads(ev_path.read_text(encoding="utf-8"))
    rated = {(r.get("home"), r.get("away")): r
             for r in json.loads((PICKS / f"picks_{day}.json").read_text(encoding="utf-8")).get("rated") or []
             if isinstance(r, dict)}
    if fetch is None:
        from data import fotmob
        fetch = (fotmob.matches_on, fotmob.match_details, fotmob.find_match)
    matches_on, details_of, find = fetch
    try:
        listed = matches_on(day)
    except Exception as e:  # noqa: BLE001 - FotMob down: every game reads PENDING, nothing invented
        print(f"{day}: FotMob match list failed ({e}) - PENDING")
        listed = []
    games = []
    for g in events.get("games", []):
        sides: dict = {}
        found = find(listed, g["home"], g["away"]) if listed else None
        lu = None
        if found:
            try:
                lu = lineup(details_of(found["id"]))
            except Exception as e:  # noqa: BLE001
                print(f"{g['home']} v {g['away']}: lineup failed ({e}) - PENDING")
        xg = em.xg_from_grid((rated.get((g["home"], g["away"])) or {}).get("scores"))
        ref = (lu or {}).get("referee")
        factor = pm.referee_factor(matches, ref, g.get("league"), day)
        for i, side in enumerate(("home", "away")):
            xi = (lu or {}).get(side) or []
            tt = {ev: e[side] for ev, e in g.get("events", {}).items() if side in e}
            if len(xi) < 11 or not tt:
                sides[side] = {"pending": "no predicted XI" if len(xi) < 11 else "no team totals", "players": []}
                continue
            p = model.predict_side(xi, tt, xg[i] if xg else None, factor)
            for o in p["players"]:      # only what the walk-forward study let through carries a number
                o["events"] = {k: v for k, v in o["events"].items() if BASE.get(k, k) in allowed}
            sides[side] = {"lineup_type": lu.get("type"), "players": p["players"], "pending": p["pending"] or None}
        games.append({"home": g["home"], "away": g["away"], "league": g.get("league"), "referee_cards_factor":
                      round(factor, 3),
                      "home_side": sides["home"], "away_side": sides["away"]})
    return {"date": day, "built": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "label": "shadow",
            "model": "engine/player_model.py", "study": "backtest/PLAYER_MODEL_STUDY.md",
            "events_published": allowed, "games": games}


def grade(players: list[dict], today: str) -> dict:
    """Past players files against the saved lines of the same game: how often "carded" went the way the model leaned."""
    rec = {"players": 0, "brier": 0.0, "lean_right": 0, "games": 0}
    for f in sorted(OUT.glob("players_*.json")):
        day = f.stem.split("_", 1)[1]
        if day >= today or (date.fromisoformat(today) - date.fromisoformat(day)).days > GRADE_DAYS:
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        played = [r for r in players if r["date"] == day]
        for g in doc.get("games", []):
            one_per_game = list({r.get("fotmob_id"): r for r in played}.values())
            hit = fm.find_match(g["home"], g["away"], one_per_game, lambda r: (r["home"], r["away"]))
            if not hit or not hit.strong:
                continue
            fid = hit.item.get("fotmob_id")
            by_id = {r["id"]: r for r in played if r.get("fotmob_id") == fid}
            rec["games"] += 1
            for side in ("home", "away"):
                for o in (g.get(side + "_side") or {}).get("players", []):
                    p = o["events"].get("card_chance")
                    r = by_id.get(o["id"])
                    if p is None or r is None:
                        continue
                    y = int(pm.stat_of(r, "cards") > 0)
                    rec["players"] += 1
                    rec["brier"] += (p - y) ** 2
                    rec["lean_right"] += int((p >= 0.5) == bool(y))
    n = rec["players"]
    return {"graded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "days": GRADE_DAYS, "games": rec["games"],
            "players": n, "card_brier": round(rec["brier"] / n, 4) if n else None,
            "card_lean_right_pct": round(rec["lean_right"] / n, 3) if n else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="UK date to build (default: today and tomorrow)")
    args = ap.parse_args(argv)
    lines = pm.load_players()
    if not lines:
        print("player model: no saved player lines (data/match_players) - nothing built: NO DATA - PENDING")
        return 0
    allowed = published()
    model = pm.PlayerModel.fit(lines)
    matches = em.load_history()
    uk = datetime.now(ZoneInfo("Europe/London")).date()
    days = [args.date] if args.date else [uk.isoformat(), (uk + timedelta(days=1)).isoformat()]
    OUT.mkdir(parents=True, exist_ok=True)
    for day in days:
        doc = predict_day(day, model, matches, allowed)
        if doc is None:
            print(f"{day}: no board or team-events file - nothing built")
            continue
        (OUT / f"players_{day}.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        print(f"{day}: {len(doc['games'])} games, events published {allowed or 'NONE (shadow, pending study)'}")
    g = grade(lines, uk.isoformat())
    (OUT / "grades.json").write_text(json.dumps(g, indent=1) + "\n", encoding="utf-8")
    print("graded:", g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
