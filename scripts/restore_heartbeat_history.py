"""
Restore data/heartbeat/history.jsonl, destroyed by a CWD-relative test teardown.

WHAT HAPPENED (2026-09-17)
tests/test_heartbeat_staking.py resolved Path("data/heartbeat/history.jsonl")
against the CURRENT WORKING DIRECTORY and called unlink() on it in both
setup_method and teardown_method. pytest runs from the repo root, so that path
pointed at the REAL production history. Running the test suite deleted nine
graded heartbeat results going back to 2026-08-27 -- silently, with no error.
The test has been fixed to use tmp_path; this script restores the data.

PROVENANCE -- every field is traced, nothing is recalled or inferred
Two independent records of the same nine heartbeats survived the deletion:

  lineage_ledger.jsonl (on disk, re-read by this script)
      date, fixture, market_type, probability, result
      Authoritative. `outcome_hit` true/false maps to WIN/LOSS.

  data/heartbeat/history.jsonl at the WORKSPACE ROOT (on disk, re-read)
      An orphan written by the same CWD-relative bug in save_heartbeat_record.
      Carries the full original record for 2026-08-29 only.

  PRICES (this session's transcript)
      Read out of the real file earlier in the same session, before the
      deletion. Recorded here rather than dropped, but flagged per record:
      "price_source": "session-read" instead of "ledger".

Fields that CANNOT be recovered for most rows -- pick text, edge, bookmaker,
kickoff_time, original timestamp, verification_passed -- are written as null.
They are NOT guessed. A reconstructed record that invented them would be
indistinguishable from an original capture, which is the failure HR35 exists to
prevent.

Every restored record carries "reconstructed": true and a "source" field so no
downstream consumer can mistake it for a first-hand capture.

Usage:
    python scripts/restore_heartbeat_history.py --dry-run
    python scripts/restore_heartbeat_history.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = REPO_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT))

LEDGER = REPO_ROOT / "lineage_ledger.jsonl"
ORPHAN = WORKSPACE_ROOT / "data" / "heartbeat" / "history.jsonl"
TARGET = REPO_ROOT / "data" / "heartbeat" / "history.jsonl"

# Prices read from the real history.jsonl earlier in this session, before the
# test deleted it. Keyed by (date, fixture) so a price can never land on the
# wrong record. Flagged as "session-read" in the output, never as ledger data.
SESSION_READ_PRICES: dict[tuple[str, str], float | None] = {
    ("2026-08-27", "Brighton v Tromso"): None,          # was genuinely unpriced
    ("2026-08-28", "Racing Santander v Elche"): 1.67,
    ("2026-08-29", "Lokomotiv v Dynamo (Russian Premier League)"): 1.67,
    ("2026-08-30", "Başakşehir v Kasımpaşa"): 1.73,
    ("2026-08-31", "SC Braga v Vitória SC"): 1.91,
    ("2026-08-31", "Osasuna v Getafe"): 1.53,
    ("2026-09-01", "Lincoln City v Blackburn Rovers"): 1.67,
    ("2026-09-01", "Birmingham City v Southampton"): 1.67,
    ("2026-09-01", "Portsmouth v Derby County"): 1.67,
}


def load_ledger_legs() -> list[dict]:
    """Unique (date, fixture) legs from the ledger, in date order.

    The ledger itself was appended three times over by the same CWD-relative
    path defect, so identical rows are deduplicated on (date, fixture, market).
    """
    if not LEDGER.exists():
        raise SystemExit(f"ledger not found: {LEDGER}")

    seen: set[tuple] = set()
    out: list[dict] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for leg in row.get("legs") or []:
            key = (row["date"], leg.get("fixture"), leg.get("market"))
            if key in seen:
                continue
            seen.add(key)
            out.append({"date": row["date"], **leg})
    out.sort(key=lambda r: (r["date"], r["fixture"]))
    return out


def load_orphan() -> dict[tuple[str, str], dict]:
    """Full original records from the workspace-root orphan, keyed (date, fixture)."""
    if not ORPHAN.exists():
        return {}
    out = {}
    for line in ORPHAN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[(r.get("date"), r.get("fixture"))] = r
    return out


def build_records() -> list[dict]:
    orphan = load_orphan()
    records: list[dict] = []

    for leg in load_ledger_legs():
        key = (leg["date"], leg["fixture"])
        orig = orphan.get(key, {})
        price = SESSION_READ_PRICES.get(key)

        records.append({
            "date": leg["date"],
            "lineage_id": None,          # never recorded; the defect this fixes
            "generation": None,
            "fixture": leg["fixture"],
            "league": orig.get("league"),
            "pick": orig.get("pick"),
            "probability": leg.get("predicted_prob"),
            "edge": orig.get("edge"),
            "market_type": leg.get("market"),
            "bookmaker": orig.get("bookmaker"),
            "price": price if price is not None else orig.get("price"),
            "kickoff_time": orig.get("kickoff_time"),
            "verification_passed": orig.get("verification_passed"),
            "result": "WIN" if leg.get("outcome_hit") else "LOSS",
            "timestamp": orig.get("timestamp"),
            # Provenance -- so nothing downstream mistakes this for a capture.
            "reconstructed": True,
            "source": "lineage_ledger.jsonl" + ("+orphan" if orig else ""),
            "price_source": "session-read" if price is not None else (
                "orphan" if orig.get("price") else None),
            "reconstructed_note": (
                "restored 2026-09-17 after tests/test_heartbeat_staking.py "
                "deleted the live file via a CWD-relative unlink"
            ),
        })
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    records = build_records()
    wins = sum(1 for r in records if r["result"] == "WIN")

    print(f"Reconstructed {len(records)} record(s), {wins}W-{len(records) - wins}L")
    print(f"  ledger : {LEDGER}")
    print(f"  orphan : {ORPHAN} ({'present' if ORPHAN.exists() else 'absent'})")
    print()
    for r in records:
        px = f"{r['price']:.2f}" if r["price"] else "UNPRICED"
        print(f"  {r['date']}  {r['fixture'][:44]:<44} {r['market_type']:<5} "
              f"{px:>8}  {r['result']}")

    if TARGET.exists():
        print(f"\nREFUSING: {TARGET} already exists — not overwriting. "
              f"Move it aside first if you intend to replace it.")
        return 1

    if args.dry_run:
        print(f"\nDRY RUN — nothing written. Would write {len(records)} record(s) "
              f"to {TARGET}")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nRESTORED {len(records)} record(s) -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
