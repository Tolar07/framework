#!/usr/bin/env python3
"""
Backfill Aug 31 and Sep 1 heartbeat results into history.jsonl and lineage.json.

This script records the missing historical results that were in the heartbeat
board files but never written to the lineage system.
"""

import json
from datetime import date, datetime
from pathlib import Path

# Add the olp_xdv to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.heartbeat_lineage import (
    load_population,
    save_population,
    record_heartbeat_result,
    breed_next_generation,
    render_lineage_report,
)
from output.heartbeat import HeartbeatFixture, save_heartbeat_record

REPO_ROOT = Path(__file__).parent.parent
HISTORY_FILE = REPO_ROOT / "data" / "heartbeat" / "history.jsonl"


def create_heartbeat_fixture(fixture: str, league: str, pick: str, prob: float,
                              edge: float, market_type: str, bookmaker: str,
                              price: float, kickoff: str, verification: bool,
                              lineage_id: str = None, generation: int = 0) -> HeartbeatFixture:
    """Create a HeartbeatFixture with all fields."""
    return HeartbeatFixture(
        fixture=fixture,
        kickoff_time=kickoff,
        league=league,
        pick=pick,
        probability=prob,
        edge=edge,
        market_type=market_type,
        bookmaker=bookmaker,
        price=price,
        verification_passed=verification,
        lineage_id=lineage_id,
        generation=generation,
    )


def append_to_history(record: dict) -> None:
    """Append a record to history.jsonl."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  Appended to history.jsonl: {record['date']} - {record['fixture']} - {record['result']}")


def backfill_aug31() -> None:
    """Backfill Aug 31, 2026 results."""
    print("\n=== BACKFILLING AUG 31, 2026 ===")

    # Match 1: SC Braga v Vitória SC - BTTS Yes (52%) -> Actual 1-0 -> BTTS NO -> LOSS
    hb1 = create_heartbeat_fixture(
        fixture="SC Braga v Vitória SC",
        league="Primeira Liga",
        pick="Both teams to score — yes",
        prob=0.52,
        edge=0.099,
        market_type="BTTS",
        bookmaker="Bet365",
        price=1.91,
        kickoff="??:??",
        verification=True,
    )

    # Append to history with result
    record1 = {
        "date": "2026-08-31",
        "fixture": "SC Braga v Vitória SC",
        "league": "Primeira Liga",
        "pick": "Both teams to score — yes",
        "probability": 0.52,
        "edge": 0.099,
        "market_type": "BTTS",
        "bookmaker": "Bet365",
        "price": 1.91,
        "kickoff_time": "??:??",
        "verification_passed": True,
        "result": "LOSS",  # Actual: 1-0 -> BTTS = NO
        "timestamp": "2026-08-31T22:15:00.000000"
    }
    append_to_history(record1)

    # Record result to lineage
    record_heartbeat_result(hb1, "LOSS", "2026-08-31")
    print(f"  Lineage updated for LOSS")

    # Match 2: Osasuna v Getafe - BTTS No (69%) -> Actual 1-0 -> BTTS NO -> WIN
    hb2 = create_heartbeat_fixture(
        fixture="Osasuna v Getafe",
        league="La Liga",
        pick="Both teams to score — no",
        prob=0.69,
        edge=0.061,
        market_type="BTTS",
        bookmaker="Bet365",
        price=1.53,
        kickoff="??:??",
        verification=True,
    )

    record2 = {
        "date": "2026-08-31",
        "fixture": "Osasuna v Getafe",
        "league": "La Liga",
        "pick": "Both teams to score — no",
        "probability": 0.69,
        "edge": 0.061,
        "market_type": "BTTS",
        "bookmaker": "Bet365",
        "price": 1.53,
        "kickoff_time": "??:??",
        "verification_passed": True,
        "result": "WIN",  # Actual: 1-0 -> BTTS = NO
        "timestamp": "2026-08-31T22:15:00.000000"
    }
    append_to_history(record2)
    record_heartbeat_result(hb2, "WIN", "2026-08-31")
    print(f"  Lineage updated for WIN")

    # Breed next generation for Sep 1
    breed_next_generation([], "2026-08-31")
    print(f"  Bred next generation for 2026-08-31")


def backfill_sep1() -> None:
    """Backfill Sep 1, 2026 results."""
    print("\n=== BACKFILLING SEP 1, 2026 ===")

    # Match 1: Lincoln v Blackburn - Blackburn or Draw (80%) -> Actual 0-0 -> Draw -> WIN
    hb1 = create_heartbeat_fixture(
        fixture="Lincoln City v Blackburn Rovers",
        league="Championship",
        pick="Blackburn or Draw (double chance)",
        prob=0.80,
        edge=0.192,
        market_type="DC",
        bookmaker="SportyBet",
        price=1.67,
        kickoff="??:??",
        verification=True,
    )

    record1 = {
        "date": "2026-09-01",
        "fixture": "Lincoln City v Blackburn Rovers",
        "league": "Championship",
        "pick": "Blackburn or Draw (double chance)",
        "probability": 0.80,
        "edge": 0.192,
        "market_type": "DC",
        "bookmaker": "SportyBet",
        "price": 1.67,
        "kickoff_time": "??:??",
        "verification_passed": True,
        "result": "WIN",  # Actual: 0-0 -> Draw -> WIN
        "timestamp": "2026-09-01T22:15:00.000000"
    }
    append_to_history(record1)
    record_heartbeat_result(hb1, "WIN", "2026-09-01")
    print(f"  Lineage updated for WIN")

    # Match 2: Birmingham v Southampton - BTTS Yes (43%) -> Actual 1-1 -> BTTS YES -> WIN
    hb2 = create_heartbeat_fixture(
        fixture="Birmingham City v Southampton",
        league="Championship",
        pick="Both teams to score — yes",
        prob=0.43,
        edge=0.134,
        market_type="BTTS",
        bookmaker="SportyBet",
        price=1.67,
        kickoff="??:??",
        verification=True,
    )

    record2 = {
        "date": "2026-09-01",
        "fixture": "Birmingham City v Southampton",
        "league": "Championship",
        "pick": "Both teams to score — yes",
        "probability": 0.43,
        "edge": 0.134,
        "market_type": "BTTS",
        "bookmaker": "SportyBet",
        "price": 1.67,
        "kickoff_time": "??:??",
        "verification_passed": True,
        "result": "WIN",  # Actual: 1-1 -> BTTS = YES
        "timestamp": "2026-09-01T22:15:00.000000"
    }
    append_to_history(record2)
    record_heartbeat_result(hb2, "WIN", "2026-09-01")
    print(f"  Lineage updated for WIN")

    # Match 3: Portsmouth v Derby - Derby or Draw (43%) -> Actual 0-2 -> Derby wins -> WIN
    hb3 = create_heartbeat_fixture(
        fixture="Portsmouth v Derby County",
        league="Championship",
        pick="Derby or Draw (double chance)",
        prob=0.43,
        edge=0.063,
        market_type="DC",
        bookmaker="SportyBet",
        price=1.67,
        kickoff="??:??",
        verification=True,
    )

    record3 = {
        "date": "2026-09-01",
        "fixture": "Portsmouth v Derby County",
        "league": "Championship",
        "pick": "Derby or Draw (double chance)",
        "probability": 0.43,
        "edge": 0.063,
        "market_type": "DC",
        "bookmaker": "SportyBet",
        "price": 1.67,
        "kickoff_time": "??:??",
        "verification_passed": True,
        "result": "WIN",  # Actual: 0-2 -> Derby wins -> WIN
        "timestamp": "2026-09-01T22:15:00.000000"
    }
    append_to_history(record3)
    record_heartbeat_result(hb3, "WIN", "2026-09-01")
    print(f"  Lineage updated for WIN")

    # Breed next generation for Sep 2
    breed_next_generation([], "2026-09-01")
    print(f"  Bred next generation for 2026-09-01")


def backfill_sep2() -> None:
    """Backfill Sep 2, 2026 - breed for today."""
    print("\n=== BREEDING FOR SEP 2, 2026 ===")
    breed_next_generation([], "2026-09-02")
    print(f"  Bred next generation for 2026-09-02")


def main():
    print("Backfilling missing heartbeat history and lineage...")

    # Run backfills in chronological order
    backfill_aug31()
    backfill_sep1()
    backfill_sep2()

    # Print final lineage report
    print("\n=== FINAL LINEAGE REPORT ===")
    print(render_lineage_report())


if __name__ == "__main__":
    main()