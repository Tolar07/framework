"""Data-quality monitor — the instrument that notices when the DATA went bad.

The health monitor (health_monitor.py) watches the pipeline's machinery — env,
quota, circuits, brain. This module watches the data ITSELF: the cached results
feeds that every prediction and every CLV settlement is built on.

Checks (HR35 throughout — a finding states what was observed, never a guess):

  1. STALE CACHE     — a cached CSV older than its TTL (live season 6h,
                       completed 30d) means the next run settles legs against
                       last night's snapshot. Surfaced as a finding.
  2. DUPLICATES      — the same (date, home, away) twice in one season file is
                       a feed error; it would teach the engine one match twice.
  3. MISSING COVERAGE— a whitelisted league with NO cached file for the live
                       season is a coverage gap: its fixtures render
                       NO DATA — PENDING forever, and the Phase 3 gate cannot
                       fill itself.

Never raises: the monitor must never crash its own schedule. A cache dir that
is unreadable is itself a finding, not a crash.

USAGE
    python monitor/data_quality.py               # print the report
    python monitor/data_quality.py --json        # machine-readable report
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import football_data_source as fds  # noqa: E402
from engine.softness import WHITELISTED_LEAGUES  # noqa: E402

CACHE_DIR = fds.DEFAULT_CACHE_DIR


@dataclass
class DataFinding:
    """One concrete data-quality problem. `level` is 'info' | 'warn' | 'error'."""
    level: str
    league: str
    problem: str

    def to_dict(self) -> dict:
        return {"level": self.level, "league": self.league, "problem": self.problem}


def _default_season() -> str:
    """The season code the daily run FITS the model on (its default arg), which
    is the season whose results must be cached. The fixtures season is a
    different axis (upcoming fixtures) and is NOT what this check targets."""
    return "2526"


def _file_age_seconds(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return float("inf")


def _scan_duplicates(path: Path, season: str) -> list[str]:
    """Same (date, home, away) twice in one CSV -> feed error. Only meaningful
    within ONE season file, so Extra-schema files (all seasons bundled) are
    filtered to the requested season first."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [f.lstrip("﻿").strip() for f in (reader.fieldnames or [])]
    is_extra = "HomeTeam" not in fieldnames and "Home" in fieldnames
    home_col = "Home" if is_extra else "HomeTeam"
    away_col = "Away" if is_extra else "AwayTeam"
    seen: set[tuple[str, str, str]] = set()
    dupes: list[str] = []
    for row in reader:
        if is_extra:
            lbl = f"20{season[:2]}/20{season[2:]}"
            if (row.get("Season") or "").strip() != lbl:
                continue
        date_, h, a = row.get("Date", "").strip(), row.get(home_col, "").strip(), row.get(away_col, "").strip()
        if not date_ or not h or not a:
            continue
        key = (date_, h, a)
        if key in seen:
            dupes.append(f"{date_} {h} v {a}")
        seen.add(key)
    return dupes


def check(season: str | None = None) -> list[DataFinding]:
    """Run all data-quality checks over the cached results feeds.

    Returns a list of DataFinding (empty when the data is clean). Never raises;
    an unreadable cache is a finding."""
    findings: list[DataFinding] = []
    season = season or _default_season()
    live = fds._season_is_live(season)

    if not CACHE_DIR.exists():
        return [DataFinding("error", "*",
                            f"cache dir {CACHE_DIR} is missing — no results "
                            f"feed available at all")]
    live_ttl = fds.LIVE_SEASON_MAX_AGE_SECONDS
    done_ttl = fds.COMPLETED_SEASON_MAX_AGE_SECONDS

    cached = {p.stem: p for p in CACHE_DIR.glob("*.csv")}

    for league in sorted(WHITELISTED_LEAGUES):
        # Cache files are named <League>_<season>.csv; the league part can
        # contain underscores (e.g. Belgian_Pro_League). Find any file whose
        # name starts with the league's own stem.
        stem = league.replace(" ", "_")
        files = [p for name, p in cached.items() if name.startswith(stem)]

        # 1. missing coverage: no live-season file at all for a whitelisted league
        #
        # Three shapes of file, three ways to know it's covered:
        #   standard  -> <League>_<season>.csv  (the season is IN the name)
        #   extra     -> <League>_all.csv  (every season bundled in one download;
        #              the season filter is applied at parse time, so the file
        #              itself never carries the season label)
        #   uncovered -> legitimately has no football-data file at all
        if league in fds.EXTRA_CODES:
            live_file = next((p for p in files if p.name.endswith("_all.csv")),
                             None)
        else:
            live_file = next((p for p in files if season in p.name), None)
        if live_file is None:
            # Sources-elsewhere leagues (continental cups, Croatia, EFL Cup) have
            # no football-data.co.uk file by design — say so rather than cry wolf
            # (HR35). Key off the source's own coverage set so this list cannot
            # drift out of sync with what the loader actually supports.
            if league in fds.UNCOVERED_LEAGUES:
                continue
            findings.append(DataFinding(
                "warn", league,
                f"no {season} results cache — coverage gap (fixtures stay "
                f"NO DATA — PENDING; the Phase 3 gate cannot fill itself)"))
            continue

        # 2. stale cache: live-season file over its TTL
        age = _file_age_seconds(live_file)
        ttl = live_ttl if live else done_ttl
        if age > ttl:
            findings.append(DataFinding(
                "warn", league,
                f"{live_file.name} is {age/3600:.0f}h old (TTL {ttl/3600:.0f}h) — "
                f"the next run settles legs against a stale snapshot"))

        # 3. duplicates within the live-season file
        dupes = _scan_duplicates(live_file, season)
        if dupes:
            findings.append(DataFinding(
                "error", league,
                f"{len(dupes)} duplicate row(s): " + "; ".join(dupes[:3]) +
                ("; …" if len(dupes) > 3 else "")))

    return findings


def render_report(findings: list[DataFinding]) -> str:
    if not findings:
        return ("DATA QUALITY: CLEAN — every whitelisted league has a fresh, "
                "duplicate-free results feed.")
    lines = [f"DATA QUALITY: {len(findings)} finding(s)"]
    for f in findings:
        lines.append(f"  [{f.level.upper()}] {f.league}: {f.problem}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="OLP XDV data-quality report")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--season", default=None, help="season code to check (default live)")
    a = ap.parse_args()
    findings = check(a.season)
    if a.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        print(render_report(findings))
    sys.exit(1 if any(f.level == "error" for f in findings) else 0)


if __name__ == "__main__":
    main()
