"""
SQUAD PROFILES — every covered team's player roles and the manager's rotation habit, weekly
(engine/squad_profile.py; Architect 2026-11-04: "gather a profile on all the players").

Reads the team list from data/teams/latest.json.gz (the weekly FotMob team profiles, run just
before this in profiles.yml) and writes data/players/squads.json.gz:
    {"built_at", "teams": {<FotMob team id>: profile}}
One FotMob team page plus the last 10 match pages per team; a match page is fetched once and
shared by both of its teams. A team that fails is kept from last week's file.

    python monitor/squad_profiles.py            every covered team
    python monitor/squad_profiles.py 8633 8650  just these team ids
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402
from engine import squad_profile as sp  # noqa: E402

OUT = ROOT / "data" / "players" / "squads.json.gz"
TEAMS = ROOT / "data" / "teams" / "latest.json.gz"
PAUSE = 0.3


def load(path: Path = OUT) -> dict:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"teams": {}}


def team_ids(path: Path = TEAMS) -> list:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            db = json.load(f)
    except (OSError, ValueError):
        return []
    ids = []
    for lg in (db.get("leagues") or {}).values():
        for t in lg.get("teams") or []:
            if t.get("id") and t["id"] not in ids:
                ids.append(t["id"])
    return ids


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ids = [int(x) for x in argv] or team_ids()
    old = load()
    out = {"built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "source": "fotmob.com",
           "teams": dict(old.get("teams") or {})}

    def get(url: str) -> dict:
        time.sleep(PAUSE)
        return fm._get(url)

    ok = failed = 0
    for tid in ids:
        try:
            prof = sp.build(tid, get)
        except Exception as e:  # noqa: BLE001 — one team failing keeps last week's copy
            failed += 1
            print(f"{tid}: kept last week's profile ({str(e)[:60]})", flush=True)
            continue
        if prof:
            out["teams"][str(tid)] = prof
            ok += 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(f"squad profiles: {ok} built, {failed} kept from last week, {len(out['teams'])} on file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
