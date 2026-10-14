"""
CLV SYNC — feed the closing prices the pre-kickoff loop already captured into
the CLV log the Phase 3 gate reads (Architect 2026-10-14: "fix the CLV
plumbing").

THE BUG THIS FIXES
  Order 20 captures a real SportyBet closing price for every board single in
  the last 35 minutes before kickoff — `news_check.capture_closing()` writes
  it onto the PICKS LEDGER (`output/picks/picks_<date>.json`: `closing_price`,
  `clv`). The Phase 3 gate and the scorecard read a DIFFERENT store, the CLV
  log (`clv/clv_log.json`), which only `run_daily`'s own grading fills from
  the football-data archive.

  The two never talked. On 2026-10-14 the ledger held 273 legs with a real
  closing price; the CLV log held 35. The gate therefore read 35 legs, mean
  CLV +2.31%, and reported "gate met" — while the same board measured over
  all 273 legs came to -0.04% +/- 0.15%, i.e. indistinguishable from the
  close. Capital authority was being unlocked by a sampling artifact.

WHAT IT DOES
  For every ledger single that carries a captured closing price, find the CLV
  leg for the same (fixture, market, kickoff date) that has no closing price
  yet, and record it through the logger's own `log_close()` — so `clv_pct` is
  computed by the one formula (`compute_clv`), from the leg's OWN entry price.
  Nothing is invented: a ledger leg with no match in the log is counted and
  reported, never appended, and a leg that already has a closing price is
  left exactly as it was.

  `clv/clv_logger.py` is a protected file; this module only uses its public
  API and never edits it.

    python clv/clv_sync.py            sync and report
    python clv/clv_sync.py --dry-run  report what would change, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clv.clv_logger import DEFAULT_LOG_PATH, CLVLog  # noqa: E402

LEDGER_DIR = ROOT / "output" / "picks"


def ledger_closes(ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    """[{fixture, market, kickoff, closing_price}] for every recorded pick that
    carries a captured closing price — board singles, study picks and the
    alternative legs the pre-kickoff loop also prices."""
    out, seen = [], set()
    for path in sorted(ledger_dir.glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = list(doc.get("singles") or []) + list(doc.get("study") or [])
        for alt in doc.get("alts") or []:
            rows += list(alt.get("alt_legs") or [])
        for r in rows:
            close = r.get("closing_price")
            fixture, market = r.get("fixture"), r.get("market")
            day = (r.get("kickoff_utc") or r.get("kickoff") or "")[:10]
            if not (close and fixture and market and day):
                continue
            key = (fixture.split(" (")[0], market, day)
            if key in seen:
                continue
            seen.add(key)
            out.append({"fixture": key[0], "market": market, "kickoff": day,
                        "closing_price": float(close)})
    return out


def sync(log: CLVLog | None = None, ledger_dir: Path = LEDGER_DIR,
         dry_run: bool = False) -> dict:
    """Record every ledger closing price on its CLV leg. Returns a report."""
    log = log or CLVLog(path=DEFAULT_LOG_PATH)
    # (fixture, market, kickoff date) -> every leg logged for that pick. The
    # same pick is logged once per board run (evening, morning refresh), so one
    # ledger row can close several legs.
    index: dict[tuple, list] = {}
    for leg in log.legs:
        if leg.entry_odds and leg.match_date:
            index.setdefault((leg.fixture, leg.market, leg.match_date[:10]), []).append(leg)
    filled = already = unmatched = 0
    for row in ledger_closes(ledger_dir):
        legs = index.get((row["fixture"], row["market"], row["kickoff"]))
        if not legs:
            unmatched += 1                    # no leg for this pick — counted, never appended
            continue
        open_legs = [leg for leg in legs if leg.closing_odds is None]
        if not open_legs:
            already += 1                      # closed on an earlier run or by run_daily's archive
            continue
        for leg in open_legs:
            if not dry_run:
                log.log_close(leg.leg_id, closing_odds=row["closing_price"],
                              closing_capture_path="CL-PREKICKOFF")
            filled += 1
    with_clv = sum(1 for leg in log.legs if leg.clv_pct is not None)
    return {"filled": filled, "already_closed": already, "unmatched_ledger_rows": unmatched,
            "legs_with_clv": with_clv, "legs_total": len(log.legs), "dry_run": dry_run}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="feed captured closing prices into the CLV log")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    a = ap.parse_args(argv)
    r = sync(dry_run=a.dry_run)
    print(f"CLV sync{' (dry run)' if r['dry_run'] else ''}: {r['filled']} closing price(s) recorded, "
          f"{r['already_closed']} already closed, {r['unmatched_ledger_rows']} with no matching leg · "
          f"{r['legs_with_clv']}/{r['legs_total']} legs now carry CLV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
