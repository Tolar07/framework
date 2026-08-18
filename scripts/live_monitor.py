#!/usr/bin/env python
"""
Live fixture monitor — key-free, covers all whitelisted leagues via ESPN.

Polls ESPN scoreboard every 60s (configurable) and prints a live board with
status, score, minute, and kickoff time for every match today across all
whitelisted leagues.

Usage:
    python -m scripts.live_monitor [--interval 60] [--hours 16]

ESPN is the primary live source (key-free, covers all WHITELISTED_LEAGUES).
"""

from __future__ import annotations

import argparse
import datetime
import json
import time
from typing import Optional

from engine.league_registry import registry
from data.live_scores import ESPNFixturesSource, LiveScore


def format_match(score: LiveScore) -> str:
    """Format a single match line."""
    status = score.status
    if status == "LIVE":
        minute = f" {score.minute}'" if score.minute is not None else " ?'"
        return f"  🔴 LIVE{minute:>5s}  {score.home_team:22s} {score.home_score}-{score.away_score}  {score.away_team:22s}  [{score.league}]"
    elif status == "HT":
        return f"  🟡 HT        {score.home_team:22s} {score.home_score}-{score.away_score}  {score.away_team:22s}  [{score.league}]"
    elif status == "FT":
        return f"  🟢 FT        {score.home_team:22s} {score.home_score}-{score.away_score}  {score.away_team:22s}  [{score.league}]"
    elif status == "SCHEDULED":
        ko = score.kickoff.isoformat() if score.kickoff else "TBD"
        return f"  ⚪ {ko}  {score.home_team:22s} v  {score.away_team:22s}  [{score.league}]"
    elif status in ("POSTPONED", "CANCELLED"):
        return f"  ⚫ {status:10s}  {score.home_team:22s} v  {score.away_team:22s}  [{score.league}]"
    else:
        return f"  ? {status:10s}  {score.home_team:22s} v  {score.away_team:22s}  [{score.league]}"


def monitor_leagues(interval: int, hours: int) -> None:
    """Monitor all whitelisted leagues with ESPN."""
    source = ESPNFixturesSource()
    leagues = registry.WHITELISTED_LEAGUES
    deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)

    print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')} UTC] Live monitor started")
    print(f"  Leagues: {len(leagues)}")
    print(f"  Poll interval: {interval}s")
    print(f"  Runs until: {deadline.strftime('%H:%M:%S')} UTC")
    print(f"  Source: ESPN (key-free)")
    print()

    last_board = None
    cycle = 0

    while datetime.datetime.now(datetime.timezone.utc) < deadline:
        cycle += 1
        now = datetime.datetime.now(datetime.timezone.utc)
        today = datetime.date.today().isoformat()

        all_scores: list[LiveScore] = []
        errors: list[str] = []

        for league in leagues:
            try:
                scores = source.fetch_live_scores(league, today)
                all_scores.extend(scores)
            except Exception as e:
                errors.append(f"{league}: {e}")

        # Sort by status (LIVE first), then by league, then by kickoff
        def sort_key(s: LiveScore):
            status_order = {"LIVE": 0, "HT": 1, "FT": 2, "SCHEDULED": 3, "POSTPONED": 4, "CANCELLED": 5}
            return (status_order.get(s.status, 9), s.league, s.kickoff or datetime.date.max)

        all_scores.sort(key=sort_key)

        # Build board
        lines = [f"[{now.strftime('%H:%M:%S')} UTC] Cycle {cycle} — {len(all_scores)} match(es) today across {len(leagues)} leagues"]
        if errors:
            lines.append(f"  Errors: {'; '.join(errors[:5])}{'...' if len(errors) > 5 else ''}")
        lines.append("")

        if all_scores:
            current_league = None
            for score in all_scores:
                if score.league != current_league:
                    current_league = score.league
                    lines.append(f"  ── {current_league} ──")
                lines.append(format_match(score))
        else:
            lines.append("  No fixtures found for today (may be off-season or no matches scheduled)")

        board = "\n".join(lines)

        if board != last_board:
            print(board)
            last_board = board
            print()  # spacing

        time.sleep(interval)

    print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')} UTC] Monitor finished")


def main():
    parser = argparse.ArgumentParser(description="Live fixture monitor (ESPN, key-free)")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default: 60)")
    parser.add_argument("--hours", type=int, default=16, help="Hours to run (default: 16)")
    args = parser.parse_args()

    try:
        monitor_leagues(args.interval, args.hours)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()