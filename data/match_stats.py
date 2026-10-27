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
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATS_DIR = ROOT / "data" / "match_stats"
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
                stats = parse_stats(fm.match_details(m["id"]))
            except Exception:  # noqa: BLE001 — counted below; the next run retries it
                failed += 1
                continue
            time.sleep(pause)
            seen.add(m["id"])
            rows.append({"date": day, "league": fx.get("league"), "home": fx["home"], "away": fx["away"],
                         "fotmob_id": m["id"], "score": m.get("score"), "stats": stats})
        if unmatched:
            notes.append(f"{day}: {unmatched} of {len(fixtures)} rated fixtures not found on FotMob")
        if failed:
            notes.append(f"{day}: {failed} FotMob match page(s) unavailable — retried next run")
    archive(rows, folder)
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
