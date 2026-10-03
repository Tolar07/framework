#!/usr/bin/env python3
"""Parse the team name audit report and extract all 268 mappings to add to team_map.py"""

import re
from pathlib import Path

# Repo-relative. These paths were hardcoded to
# C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\..., which resolves on
# one machine only -- and because the open() runs at module scope, merely
# IMPORTING this file raised FileNotFoundError everywhere else.
REPO_ROOT = Path(__file__).resolve().parent
REPORT = REPO_ROOT / "data" / "team-name-audit" / "report-2026-08-23.md"
OUTPUT = REPO_ROOT / "all_268_mappings_clean.txt"

# Read the audit report
with open(REPORT, "r", encoding="utf-8") as f:
    content = f.read()

# Find the section between "## Additions to team_map.py" and "## Normalization Collisions"
start_marker = "## Additions to team_map.py (SPORTYBET_TEAMS)"
end_marker = "## Normalization Collisions"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find section markers")
    exit(1)

section = content[start_idx:end_idx]

# Find table rows
# Pattern: | League | SportyBet Name | Model Key | Normalized | Confidence | Reason |
pattern = r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|'

matches = re.findall(pattern, section)

mappings = []
for match in matches:
    league, sb_name, model_key, normalized, confidence, reason = match
    # Skip header rows
    if league.strip().lower() == "league" or "---" in league:
        continue
    # Skip rows that don't have proper data
    if not league.strip() or not sb_name.strip():
        continue

    mappings.append({
        "league": league.strip(),
        "sportybet_name": sb_name.strip(),
        "model_key": model_key.strip(),
        "normalized": normalized.strip(),
        "confidence": confidence.strip(),
        "reason": reason.strip()
    })

print(f"Found {len(mappings)} mappings from audit report")

# Also write to a file for easy reference
with open(OUTPUT, "w", encoding="utf-8") as f:
    for m in mappings:
        f.write(f'"{m["sportybet_name"]}": "{m["model_key"]}",  # {m["league"]}\n')

print(f"\nWritten to all_268_mappings_clean.txt")