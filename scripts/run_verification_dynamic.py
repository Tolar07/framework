#!/usr/bin/env python3
"""
OLP XDV - Dynamic Results Verification Wrapper
===============================================
Waits until (latest kickoff time of the day + 130 minutes) then runs grade_results.py.

This ensures we wait for all matches to complete (including late Champions League games)
before grading predictions.
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the olp_xdv directory to path so we can import from data/
sys.path.insert(0, str(Path(__file__).parent))

from data.multi_source_concrete import get_latest_kickoff_today

# Deploy leagues - same as in grade_results.py
DEPLOY_LEAGUES = [
    "Scottish Premiership",   # SC0
    "Eredivisie",              # N1
    "Belgian Pro League",      # B1
    "Danish Superliga",        # Denmark
    "Polish Ekstraklasa",      # Poland
]

def get_current_season() -> str:
    """
    Calculate the current football season based on today's date.
    Football season typically runs August to May.
    """
    today = datetime.now(timezone.utc)
    year = today.year
    month = today.month

    # If month >= August, season starts this year
    # If month < August, season started last year
    if month >= 8:
        season_start_year = year
    else:
        season_start_year = year - 1

    # Format as "2526" for 2025-2026 season
    season = f"{str(season_start_year)[2:4]}{str(season_start_year + 1)[2:4]}"
    return season

def main():
    print("[INFO] OLP XDV Dynamic Results Verification Wrapper")
    print("[INFO] Calculating latest kickoff time for today...")

    try:
        # Get current season
        fixtures_season = get_current_season()
        print(f"[INFO] Using fixtures season: {fixtures_season}")

        # Get latest kickoff time today
        latest_kickoff = get_latest_kickoff_today(DEPLOY_LEAGUES, fixtures_season)

        if latest_kickoff is None:
            print("[WARN] No fixtures found for today - running verification immediately")
            target_time = datetime.now(timezone.utc)
        else:
            print(f"[INFO] Latest kickoff today: {latest_kickoff.isoformat()}")

            # Add 130 minutes buffer
            target_time = latest_kickoff + timedelta(minutes=130)
            print(f"[INFO] Target verification time: {target_time.isoformat()} (latest kickoff + 130 minutes)")

        # Calculate wait time
        now = datetime.now(timezone.utc)
        wait_seconds = (target_time - now).total_seconds()

        if wait_seconds > 0:
            print(f"[INFO] Waiting {wait_seconds/60:.1f} minutes until verification time...")
            time.sleep(wait_seconds)
            print("[INFO] Wait complete - running verification")
        else:
            print(f"[INFO] Target time has already passed by {-wait_seconds/60:.1f} minutes - running verification immediately")

        # Run grade_results.py
        print("[INFO] Starting OLP XDV Results Verification Agent...")
        from grade_results import main as grade_main
        exit_code = grade_main()
        sys.exit(exit_code)

    except Exception as e:
        print(f"[ERROR] Dynamic verification wrapper failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()