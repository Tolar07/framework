#!/usr/bin/env python3
"""Parse the team name audit report and extract all 268 mappings to add to team_map.py"""

import re

# Read the audit report
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\data\team-name-audit\report-2026-08-23.md", "r", encoding="utf-8") as f:
    content = f.read()

# Find the "Additions to team_map.py" table
# Pattern: | League | SportyBet Name | Model Key | Normalized | Confidence | Reason |
pattern = r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|'

matches = re.findall(pattern, content)

mappings = []
for match in matches:
    league, sb_name, model_key, normalized, confidence, reason = match
    # Skip header rows
    if league.strip().lower() == "league" or "---" in league:
        continue
    # Skip the normalization collisions section
    if "normalized" in league.lower() and "conflicting" in reason.lower():
        break

    mappings.append({
        "league": league.strip(),
        "sportybet_name": sb_name.strip(),
        "model_key": model_key.strip(),
        "normalized": normalized.strip(),
        "confidence": confidence.strip(),
        "reason": reason.strip()
    })

print(f"Found {len(mappings)} mappings from audit report")

# Print all mappings grouped by league
current_league = None
for m in mappings:
    if m["league"] != current_league:
        current_league = m["league"]
        # Write to file instead of printing to avoid encoding issues
    # We'll just write to file

# Also write to a file for easy reference
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\all_268_mappings.txt", "w", encoding="utf-8") as f:
    for m in mappings:
        f.write(f'"{m["sportybet_name"]}": "{m["model_key"]}",  # {m["league"]}\n')

print(f"\nWritten to all_268_mappings.txt")