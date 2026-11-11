"""
MATCH STATS — how each covered match was actually played (Architect
2026-10-07: "learn how these games are played ... the tactical profile";
"yes add both" — post-match stats from FotMob).

After a match the board rated (output/picks/picks_<date>.json "rated" —
every fixture in a covered league), its FotMob match page gives the
balance of play: possession, shots, shots on target, big chances, expected
goals (where FotMob has them), corners, box touches, passing, cards, keeper
saves. The match is found with the same strict, unambiguous two-name rule as
grading (data.fotmob.find_match) — a wrong match would teach the wrong
lesson (ID48). One line per match goes to data/match_stats/<month>.jsonl;
backtest/match_stats_study.py turns them into league styles and team
profiles. Nothing selects on it: a finding becomes a rule only by the
Architect. A stat FotMob doesn't publish for a match is absent, never 0 (HR35).

2026-11-11 (framework #556, Architect: "show me a football match stats ... Flashscore ... all these things"):
each line also keeps EVERY team stat FotMob publishes ("full": all / h1 / h2 — about 45 per side: shots off
target, blocked, woodwork, inside/outside box, xG open play / set play / on target, passes by half, long balls,
crosses, throw-ins, offsides, tackles, interceptions, blocks, clearances, duels, aerials, dribbles...) and the
referee. Every player's line (minutes, position, rating and every stat FotMob gives him, cards and fouls
included) goes to data/match_players/<month>.jsonl. `python data/match_stats.py --backfill` fills both in for
lines saved before this.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATS_DIR = ROOT / "data" / "match_stats"
PLAYERS_DIR = ROOT / "data" / "match_players"
PERIODS = {"All": "all", "FirstHalf": "h1", "SecondHalf": "h2"}
# FotMob keys that are only group headers (value [None, None])
HEADERS = {"shots", "passes", "defense", "duels", "discipline", "expected_goals"}
LEDGER_DIR = ROOT / "output" / "picks"
# FotMob stat key -> our name
KEEP = {"BallPossesion": "possession", "expected_goals": "xg", "total_shots": "shots",
        "ShotsOnTarget": "sot", "shots_inside_box": "shots_in_box", "big_chance": "big_chances",
        "big_chance_missed_title": "big_missed", "touches_opp_box": "box_touches",
        "corners": "corners", "passes": "passes", "accurate_passes": "passes_acc",
        "fouls": "fouls", "yellow_cards": "yellow", "red_cards": "red", "keeper_saves": "saves"}


def _num(v) -> float | None:
    """'369 (83%)' -> 369, '1.42' -> 1.42, None stays None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(v))
    return float(m.group(1)) if m else None


def parse_stats(details: dict) -> dict[str, list[float]]:
    """{our name: [home, away]} from a FotMob match page; missing stats left out."""
    out: dict[str, list[float]] = {}
    groups = ((details.get("content") or {}).get("stats") or {}).get("Periods", {}).get("All", {}).get("stats", [])
    for grp in groups:
        for s in grp.get("stats", []):
            name = KEEP.get(s.get("key"))
            vals = s.get("stats") or []
            if not name or name in out or len(vals) != 2:
                continue
            h, a = _num(vals[0]), _num(vals[1])
            if h is not None and a is not None:
                out[name] = [h, a]
    return out


def _key(k: str) -> str:
    return k.split(".")[-1]          # "matchstats.headers.tackles" -> "tackles"


def parse_full(details: dict) -> dict[str, dict[str, list[float]]]:
    """Every team stat FotMob publishes, by period: {"all"|"h1"|"h2": {key: [home, away]}}. '325 (78%)' -> 325."""
    out: dict[str, dict[str, list[float]]] = {}
    periods = ((details.get("content") or {}).get("stats") or {}).get("Periods") or {}
    for per, short in PERIODS.items():
        got: dict[str, list[float]] = {}
        for grp in (periods.get(per) or {}).get("stats", []):
            for st in grp.get("stats", []):
                k = _key(st.get("key") or "")
                vals = st.get("stats") or []
                if not k or k in got or len(vals) != 2:
                    continue
                h, a = _num(vals[0]), _num(vals[1])
                if h is not None and a is not None:
                    got[k] = [h, a]
        if got:
            out[short] = got
    return out


def referee(details: dict) -> dict | None:
    r = ((details.get("content") or {}).get("matchFacts") or {}).get("infoBox", {}).get("Referee")
    if not isinstance(r, dict) or not r.get("text"):
        return None
    return {"name": r.get("text"), "id": r.get("id"), "country": r.get("country")}


def players(details: dict, home_id=None) -> list[dict]:
    """One flat line per player who has stats: every FotMob stat key -> value (and key_total for x/y stats)."""
    out: list[dict] = []
    for p in ((details.get("content") or {}).get("playerStats") or {}).values():
        if not isinstance(p, dict):
            continue
        row: dict = {"id": p.get("id"), "name": p.get("name"), "team_id": p.get("teamId"), "team": p.get("teamName"),
               "gk": bool(p.get("isGoalkeeper"))}
        if home_id is not None:
            row["side"] = "home" if p.get("teamId") == home_id else "away"
        for grp in p.get("stats") or []:
            for _title, st in (grp.get("stats") or {}).items():
                k, v = st.get("key"), (st.get("stat") or {})
                if not k or v.get("value") is None or isinstance(v.get("value"), bool):
                    continue
                k = _key(k)
                row[k] = v["value"]
                if v.get("total") is not None:
                    row[k + "_total"] = v["total"]
        out.append(row)
    # cards come from the match events, not the player stat sheet
    events = (((details.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
    by_id: dict = {r["id"]: r for r in out}
    for e in events:
        if e.get("type") != "Card" or e.get("playerId") not in by_id:
            continue
        r = by_id[e["playerId"]]
        kind = "red" if "red" in str(e.get("card", "")).lower() else "yellow"
        r[kind] = r.get(kind, 0) + 1
        r.setdefault("card_minutes", []).append(e.get("time"))
    return out


def home_team_id(details: dict):
    teams = (details.get("general") or {}).get("homeTeam") or (details.get("header") or {}).get("teams", [{}])[0]
    return teams.get("id") if isinstance(teams, dict) else None


def enrich(row: dict, details: dict) -> list[dict]:
    """Adds "full" and "referee" to a match line; returns its player lines."""
    full = parse_full(details)
    if full:
        row["full"] = full
    ref = referee(details)
    if ref:
        row["referee"] = ref
    pl = players(details, home_team_id(details))
    return [{"date": row["date"], "fotmob_id": row["fotmob_id"], "league": row.get("league"),
             "home": row["home"], "away": row["away"], **p} for p in pl]


def archive_players(lines: list[dict], folder: Path = PLAYERS_DIR) -> None:
    by_month: dict[str, list[dict]] = {}
    for r in lines:
        by_month.setdefault(r["date"][:7], []).append(r)
    for month, rs in by_month.items():
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / f"{month}.jsonl").open("a", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")


def backfill(folder: Path = STATS_DIR, players_dir: Path = PLAYERS_DIR, pause: float = 0.4,
             limit: int | None = None, fetch=None) -> tuple[int, int]:
    """Re-read FotMob for every saved line without "full" (oldest first); rewrites the month files in place.
    Returns (lines filled, pages that failed). Safe to run again: filled lines are skipped."""
    if fetch is None:
        from data import fotmob as fm
        fetch = fm.match_details
    done = failed = 0
    have_players = set()
    for pp in players_dir.glob("*.jsonl"):
        for line in pp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                have_players.add(json.loads(line).get("fotmob_id"))
    for path in sorted(folder.glob("*.jsonl")):
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        new_players: list[dict] = []
        changed = False
        for r in rows:
            if "full" in r or not r.get("fotmob_id"):
                continue
            if limit is not None and done >= limit:
                break
            try:
                det = fetch(r["fotmob_id"])
            except Exception:  # noqa: BLE001 — left for the next run
                failed += 1
                continue
            pl = enrich(r, det)
            if r["fotmob_id"] not in have_players:
                new_players += pl
                have_players.add(r["fotmob_id"])
            changed = True
            done += 1
            time.sleep(pause)
        if changed:
            path.write_text("".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n" for r in rows),
                            encoding="utf-8")
            archive_players(new_players, players_dir)
    return done, failed


def rated_fixtures(day: str, ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    """Every fixture the board rated for `day` (covered leagues only)."""
    path = ledger_dir / f"picks_{day}.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in doc.get("rated", []) if r.get("home") and r.get("away")]


def seen_ids(folder: Path = STATS_DIR) -> set:
    ids = set()
    for p in folder.glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.add(json.loads(line).get("fotmob_id"))
    return ids


def collect(days: int = 3, today: date | None = None, folder: Path = STATS_DIR,
            ledger_dir: Path = LEDGER_DIR, pause: float = 0.4) -> tuple[int, list[str]]:
    """Fetch stats for the rated fixtures of the last `days` days that have
    finished and aren't archived yet. Returns (archived, notes)."""
    from data import fotmob as fm
    today = today or date.today()
    seen = seen_ids(folder)
    notes, rows = [], []
    player_lines: list[dict] = []
    for back in range(1, days + 1):
        day = (today - timedelta(days=back)).isoformat()
        fixtures = rated_fixtures(day, ledger_dir)
        if not fixtures:
            continue
        try:
            matches = fm.matches_on(day)
        except Exception as e:  # noqa: BLE001 — FotMob down: the next run retries
            notes.append(f"{day}: FotMob unavailable ({str(e)[:50]})")
            continue
        unmatched = failed = 0
        for fx in fixtures:
            m = fm.find_match(matches, fx["home"], fx["away"])
            if m is None:
                unmatched += 1
                continue
            if not m.get("finished") or m["id"] in seen:
                continue
            try:
                det = fm.match_details(m["id"])
                stats = parse_stats(det)
            except Exception:  # noqa: BLE001 — counted below; the next run retries it
                failed += 1
                continue
            time.sleep(pause)
            seen.add(m["id"])
            row = {"date": day, "league": fx.get("league"), "home": fx["home"], "away": fx["away"],
                   "fotmob_id": m["id"], "score": m.get("score"), "stats": stats}
            player_lines += enrich(row, det)
            rows.append(row)
        if unmatched:
            notes.append(f"{day}: {unmatched} of {len(fixtures)} rated fixtures not found on FotMob")
        if failed:
            notes.append(f"{day}: {failed} FotMob match page(s) unavailable — retried next run")
    archive(rows, folder)
    archive_players(player_lines, folder.parent / "match_players")
    return len(rows), notes


def archive(rows: list[dict], folder: Path = STATS_DIR) -> None:
    by_month: dict[str, list[dict]] = {}
    for r in rows:
        by_month.setdefault(r["date"][:7], []).append(r)
    for month, rs in by_month.items():
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / f"{month}.jsonl").open("a", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")


def load(folder: Path = STATS_DIR) -> list[dict]:
    rows = []
    for p in sorted(folder.glob("*.jsonl")):
        rows += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows


if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, str(ROOT))       # run as a script: make the framework's packages importable
    if "--backfill" in _sys.argv:
        n_lim = None
        for a in _sys.argv:
            if a.startswith("--limit="):
                n_lim = int(a.split("=", 1)[1])
        filled, bad = backfill(limit=n_lim)
        print(f"match stats backfill: {filled} lines filled, {bad} FotMob pages failed (retried next run)")
