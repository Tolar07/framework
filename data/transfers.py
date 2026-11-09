"""
TRANSFERS (Architect 2026-11-09 plan, step 5: "formation, league goals, injury, transfer news").

Every club's signings and departures from its FotMob team page (free, no key): date,
direction, market value (else the fee), loan or not. Nothing else in the framework
reads transfers; a January window can change a squad between the two meetings of a
season. FotMob keeps the moves since January 2026 (so last season's winter window
is on record for a study: backtest/transfers_study.py).

  fetch_team(team_id)      [{date, dir in|out, value, loan, name, position}]
  window(moves, start, end)  the sums inside one window: value in, value out, net,
                             the biggest single departure, how many moves
  run()                    every team of the covered leagues -> data/teams/transfers_<date>.json
                           (weekly, profiles.yml), {league: {FotMob team name: moves}}

A label and a study input, never a selector. A value FotMob doesn't publish is
absent, never 0 (HR35): a move with neither market value nor fee counts in the move
count but adds nothing to the sums.

    python data/transfers.py                 every covered league
    python data/transfers.py "Premier League"
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402
from data.team_profiles import _TEAM, FOTMOB_LEAGUE, league_teams  # noqa: E402

TEAMS_DIR = ROOT / "data" / "teams"
CUPS = {"Champions League", "Europa League", "Conference League"}


def _value(m: dict) -> float | None:
    v = m.get("marketValue")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    fee = (m.get("fee") or {}).get("value")
    return float(fee) if isinstance(fee, (int, float)) and fee > 0 else None


def parse(page: dict, team_id: int) -> list[dict]:
    """Moves of one team page; contract extensions are not moves."""
    out, seen = [], set()
    for m in (page.get("transfers") or {}).get("allTransfers") or []:
        if m.get("contractExtension"):
            continue
        d = (m.get("transferDate") or "")[:10]
        if not d:
            continue
        if m.get("toClubId") == team_id:
            direction = "in"
        elif m.get("fromClubId") == team_id:
            direction = "out"
        else:
            continue
        k = (m.get("playerId"), d, direction)
        if k in seen:
            continue
        seen.add(k)
        out.append({"date": d, "dir": direction, "value": _value(m), "loan": bool(m.get("onLoan")),
                    "name": m.get("name"), "position": (m.get("position") or {}).get("label")})
    return sorted(out, key=lambda x: x["date"])


def fetch_team(team_id: int) -> list[dict]:
    return parse(fm._get(_TEAM.format(tid=team_id)), team_id)


def window(moves: list[dict], start: str, end: str) -> dict[str, Any]:
    """Sums of the moves with start <= date < end (euros)."""
    inn = [m for m in moves if start <= m["date"] < end and m["dir"] == "in"]
    out = [m for m in moves if start <= m["date"] < end and m["dir"] == "out"]
    vi = sum(m["value"] or 0 for m in inn)
    vo = sum(m["value"] or 0 for m in out)
    return {"n_in": len(inn), "n_out": len(out), "value_in": vi, "value_out": vo, "net": vi - vo,
            "top_out": max((m["value"] or 0 for m in out), default=0.0)}


def winter_window(day: str) -> tuple[str, str]:
    """The January window of the season `day` is in: Jan 1 - Feb 3 (UK / most of Europe)."""
    y, m = int(day[:4]), int(day[5:7])
    yr = y if m < 8 else y + 1
    return f"{yr}-01-01", f"{yr}-02-04"


def run(leagues: list[str] | None = None, pause: float = 0.3) -> str:
    leagues = leagues or [lg for lg in FOTMOB_LEAGUE if lg not in CUPS]
    doc: dict[str, dict] = {}
    failed = 0
    for lg in leagues:
        try:
            teams = league_teams(FOTMOB_LEAGUE[lg])
        except Exception:  # noqa: BLE001 — one league down: the rest still run
            failed += 1
            continue
        doc[lg] = {}
        for t in teams:
            try:
                doc[lg][t["name"]] = {"id": t["id"], "moves": fetch_team(t["id"])}
            except Exception:  # noqa: BLE001 — counted; next week retries
                failed += 1
            time.sleep(pause)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    TEAMS_DIR.mkdir(parents=True, exist_ok=True)
    (TEAMS_DIR / f"transfers_{day}.json").write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    n = sum(len(v) for v in doc.values())
    return f"transfers: {n} teams in {len(doc)} leagues saved, {failed} failed"


def latest(folder: Path = TEAMS_DIR) -> dict:
    files = sorted(folder.glob("transfers_*.json")) if folder.exists() else []
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else {}


if __name__ == "__main__":
    print(run(sys.argv[1:] or None))
