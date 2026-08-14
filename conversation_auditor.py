"""
Conversation Auditor — detects hallucination patterns, data fabrication, and
verification failures in fixture reporting sessions.

Learns from the 2026-08-14 incident where 22 "whitelisted fixtures" were
presented without live verification, including major-league matches (PL, La
Liga, Serie A, Bundesliga, Ligue 1) that hadn't started yet.

Usage:
    python conversation_auditor.py audit <transcript.jsonl>
    python conversation_auditor.py check-fixtures <date>
    python conversation_auditor.py leagues-calendar
"""
from __future__ import annotations

import sys
import os
import json
import re
import argparse
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding for Unicode symbols
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ── League season-start calendar (verified 2026-08-14 via Perplexity + official sites) ──
# UPDATE when new season dates are confirmed.
LEAGUE_SEASON_START: dict[str, str] = {
    "Premier League":      "2026-08-21",
    "La Liga":             "2026-08-15",
    "Serie A":             "2026-08-22",
    "Bundesliga":          "2026-08-28",
    "Ligue 1":             "2026-08-21",
    "Eredivisie":          "2026-08-14",   # started — Telstar vs Sparta confirmed
    "Championship":        "2026-08-14",   # started — Wolves vs Blackburn confirmed
    "Primeira Liga":       "2026-08-14",   # started — Sporting CP vs Vitória confirmed
    "Turkish Super Lig":   "2026-08-14",   # Süper Lig — Galatasaray vs Çorum confirmed
    "Austrian Bundesliga": "2026-08-14",   # LASK vs Ried confirmed
    "Belgian Pro League":  "2026-08-14",   # Cercle Brugge vs Sint-Truiden confirmed
    "Danish Superliga":    "2026-08-14",   # Viborg vs AGF confirmed
    "Ekstraklasa":         "2026-08-14",   # Legia vs Radomiak confirmed
    "Norwegian Eliteserien": "2026-08-14", # Rosenborg vs Viking confirmed
    "Swedish Allsvenskan": "2026-08-14",   # Elfsborg vs Västerås confirmed
    # Add more as verified
}

# ── Known failure patterns (from 2026-08-14 incident) ──
FAILURE_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "FAB-001",
        "name": "Major-league fixture before season start",
        "description": "Claiming PL/La Liga/Serie A/Bundesliga/Ligue 1 matches before their confirmed 2026-27 start date",
        "regex": r"(?:Premier League|La Liga|Serie A|Bundesliga|Ligue 1).*(?:vs|versus)",
        "check": "date < LEAGUE_SEASON_START[league]",
        "severity": "CRITICAL",
        "guardrail": "Always check LEAGUE_SEASON_START before listing any major league fixture",
    },
    {
        "id": "FAB-002",
        "name": "Compiled list without live source",
        "description": "Presenting a fixture list from memory/cache without querying at least 2 live sources",
        "regex": r"(?:today'?s fixtures|fixture list|matches today)",
        "check": "no live_source tag in output",
        "severity": "HIGH",
        "guardrail": "Every fixture output must cite live sources",
    },
    {
        "id": "FAB-003",
        "name": "Cup/friendly mixed with league fixtures",
        "description": "Coppa Italia, Scottish League Cup, friendlies listed alongside league matches",
        "regex": r"(?:Coppa Italia|Scottish League Cup|Friendly|Club Friendly)",
        "check": "context is league fixtures filter",
        "severity": "MEDIUM",
        "guardrail": "Filter by deploy-eligible whitelist only",
    },
    {
        "id": "FAB-004",
        "name": "Date drift",
        "date": "Using fixtures from wrong date",
        "description": "Presenting yesterday's or next week's fixtures as today's",
        "check": "claim_date != date.today()",
        "severity": "HIGH",
        "guardrail": "Always use date.today().isoformat() AND verify against live source timestamp",
    },
]


def check_league_calendar(target_date: str) -> list[dict[str, str]]:
    """Check which leagues are actually in season on a given date.

    Returns list of leagues that have NOT started yet (hallucination risk).
    """
    not_started = []
    for league, start in LEAGUE_SEASON_START.items():
        if target_date < start:
            not_started.append({"league": league, "season_start": start, "target_date": target_date})
    return not_started


def audit_transcript(transcript_path: str) -> list[dict[str, Any]]:
    """Audit a conversation transcript JSONL for fabrication patterns."""
    findings: list[dict[str, Any]] = []
    path = Path(transcript_path)

    if not path.exists():
        print(f"ERROR: transcript not found: {path}")
        return findings

    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Check assistant messages for fixture claims
            content = ""
            if isinstance(entry.get("content"), str):
                content = entry["content"]
            elif isinstance(entry.get("content"), list):
                for block in entry["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        content += block.get("text", "")

            if not content:
                continue

            for pattern in FAILURE_PATTERNS:
                if re.search(pattern.get("regex", ""), content, re.IGNORECASE):
                    findings.append({
                        "line": line_num,
                        "pattern_id": pattern["id"],
                        "pattern_name": pattern["name"],
                        "severity": pattern["severity"],
                        "snippet": content[:200],
                        "guardrail": pattern["guardrail"],
                    })

    return findings


def print_audit_report(findings: list[dict[str, Any]]) -> None:
    """Print human-readable audit report."""
    if not findings:
        print("✓ No fabrication patterns detected.")
        return

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    high = [f for f in findings if f["severity"] == "HIGH"]
    medium = [f for f in findings if f["severity"] == "MEDIUM"]

    print(f"\n{'='*60}")
    print(f"CONVERSATION AUDIT REPORT")
    print(f"{'='*60}")
    print(f"Total incidents: {len(findings)}")
    print(f"  CRITICAL: {len(critical)}")
    print(f"  HIGH:     {len(high)}")
    print(f"  MEDIUM:   {len(medium)}")
    print()

    for f in findings:
        print(f"[{f['severity']}] {f['pattern_id']}: {f['pattern_name']}")
        print(f"  Line {f['line']}: {f['snippet'][:100]}...")
        print(f"  Guardrail: {f['guardrail']}")
        print()


def check_fixtures_command(target_date: str) -> None:
    """Pre-flight check: which leagues should NOT have fixtures on this date?"""
    print(f"\n{'='*60}")
    print(f"LEAGUE CALENDAR CHECK FOR {target_date}")
    print(f"{'='*60}\n")

    not_started = check_league_calendar(target_date)

    if not_started:
        print("⚠  LEAGUES NOT YET STARTED (hallucination risk if fixtures claimed):")
        for entry in not_started:
            print(f"  ❌ {entry['league']:25s} — starts {entry['season_start']} "
                  f"(target {entry['target_date']} = {entry['season_start']} "
                  f"-> {'BEFORE start' if entry['target_date'] < entry['season_start'] else 'OK'})")
    else:
        print("✓ All known leagues have started by this date.")

    print(f"\nLeagues confirmed active on {target_date}:")
    active = [lg for lg, start in LEAGUE_SEASON_START.items() if target_date >= start]
    for lg in sorted(active):
        print(f"  ✓ {lg}")


def leagues_calendar_command() -> None:
    """Print the full league calendar."""
    print(f"\n{'='*60}")
    print("LEAGUE SEASON-START CALENDAR (2026-27)")
    print(f"{'='*60}\n")
    for league, start in sorted(LEAGUE_SEASON_START.items(), key=lambda x: x[1]):
        today = date.today().isoformat()
        status = "✓ ACTIVE" if today >= start else f"⏳ starts {start}"
        print(f"  {league:25s}  {start}  {status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversation Auditor — learn from hallucination mistakes")
    sub = parser.add_subparsers(dest="command")

    audit = sub.add_parser("audit", help="Audit a conversation transcript JSONL")
    audit.add_argument("transcript", help="Path to .jsonl transcript file")

    check = sub.add_parser("check-fixtures", help="Pre-flight: check which leagues are active on a date")
    check.add_argument("date", help="Target date (YYYY-MM-DD)")

    sub.add_parser("leagues-calendar", help="Print full league season-start calendar")

    args = parser.parse_args()

    if args.command == "audit":
        findings = audit_transcript(args.transcript)
        print_audit_report(findings)

    elif args.command == "check-fixtures":
        check_fixtures_command(args.date)

    elif args.command == "leagues-calendar":
        leagues_calendar_command()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
