"""Read-only questions about the live framework's own records.

Answers "how are we doing", "what did we predict for X", "show the board"
from what the daily runs saved — never by running the pipeline and never by
fetching anything (HR59: these are records of earlier fetches, each with its
date). Missing records read NO DATA — PENDING (HR35).

  python scripts/olp_query.py status
  python scripts/olp_query.py board [YYYY-MM-DD]
  python scripts/olp_query.py picks [YYYY-MM-DD]
  python scripts/olp_query.py scorecard [--days 7]
  python scripts/olp_query.py lookup <team>
  python scripts/olp_query.py leagues
Add --json for structured output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BOARDS = ROOT / "output" / "boards"
PICKS = ROOT / "output" / "picks"
PENDING = "NO DATA — PENDING"


def _dates(folder: Path, prefix: str, suffix: str) -> list[str]:
    return sorted(p.name[len(prefix):-len(suffix)] for p in folder.glob(f"{prefix}*{suffix}"))


def _ledger(day: str | None) -> dict | None:
    days = _dates(PICKS, "picks_", ".json")
    day = day or (days[-1] if days else None)
    path = PICKS / f"picks_{day}.json"
    return json.loads(path.read_text(encoding="utf-8")) if day and path.exists() else None


def status() -> dict:
    from clv.clv_logger import CLVLog
    from config import PHASE_LABEL
    boards = _dates(BOARDS, "board_", ".txt")
    picks = _dates(PICKS, "picks_", ".json")
    return {"phase": PHASE_LABEL, "clv": CLVLog().phase2_status(),
            "latest_board": boards[-1] if boards else PENDING,
            "latest_picks": picks[-1] if picks else PENDING}


def board(day: str | None) -> dict:
    days = _dates(BOARDS, "board_", ".txt")
    day = day or (days[-1] if days else None)
    path = BOARDS / f"board_{day}.txt"
    return {"date": day or PENDING,
            "board": path.read_text(encoding="utf-8") if day and path.exists() else PENDING}


def picks(day: str | None) -> dict:
    doc = _ledger(day)
    if doc is None:
        return {"date": day or PENDING, "singles": PENDING}
    return {"date": doc["date"], "singles": [
        {k: s.get(k) for k in ("fixture", "league", "pick", "price", "chance",
                               "certainty", "code", "result", "ft")}
        for s in doc["singles"]]}


def lookup(team: str) -> dict:
    t = team.lower()
    rows = []
    for day in _dates(PICKS, "picks_", ".json"):
        doc = _ledger(day) or {}
        for s in doc.get("singles", []):
            if t in s["fixture"].lower():
                rows.append({"date": day, "fixture": s["fixture"], "pick": s["pick"],
                             "chance": s["chance"], "result": s["result"], "ft": s["ft"]})
        for r in doc.get("rated", []):
            if t in r["fixture"].lower():
                rows.append({"date": day, "fixture": r["fixture"], "src": r["src"],
                             "p_home_draw_away": r["p"][:3], "ft": r["ft"]})
    return {"query": team, "rows": rows or PENDING}


def leagues() -> dict:
    from engine.slate import WHITELIST_LEAGUES, is_deploy_eligible
    return {"leagues": [{"league": lg, "deploy_eligible": is_deploy_eligible(lg)}
                        for lg in WHITELIST_LEAGUES]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV read-only queries")
    ap.add_argument("command", choices=["status", "board", "picks", "scorecard",
                                        "lookup", "leagues"])
    ap.add_argument("arg", nargs="?", default=None)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "scorecard":
        from engine.picks_ledger import scorecard
        out: object = {"scorecard": scorecard(a.days)}
    elif a.command == "lookup":
        if not a.arg:
            ap.error("lookup needs a team or fixture name")
        out = lookup(a.arg)
    elif a.command in ("board", "picks"):
        out = board(a.arg) if a.command == "board" else picks(a.arg)
    else:
        out = status() if a.command == "status" else leagues()
    if a.json:
        print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    elif isinstance(out, dict) and len(out) == 1:
        val = next(iter(out.values()))
        print(val if isinstance(val, str) else json.dumps(val, indent=1, default=str, ensure_ascii=False))
    else:
        print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
