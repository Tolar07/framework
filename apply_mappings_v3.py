#!/usr/bin/env python3
"""Apply the 268 mappings to team_map.py in alphabetical order"""

import re

# Read the current team_map.py
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\booking\team_map.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Read the new mappings
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\all_268_mappings_clean.txt", "r", encoding="utf-8") as f:
    new_mappings_lines = f.readlines()

# Parse the new mappings
new_mappings = {}
for line in new_mappings_lines:
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    # Format: "SportyBet Name": "Model Key",  # League
    match = re.match(r'"([^"]+)"\s*:\s*"([^"]+)"\s*,\s*#\s*(.+)', line)
    if match:
        sb_name = match.group(1)
        model_key = match.group(2)
        league = match.group(3)
        new_mappings[sb_name] = (model_key, league)

print(f"Parsed {len(new_mappings)} new mappings")

# Find the start and end of SPORTYBET_TEAMS dict
start_line = -1
end_line = -1
brace_count = 0

for i, line in enumerate(lines):
    if 'SPORTYBET_TEAMS: dict[str, str] = {' in line:
        start_line = i
        brace_count = 1
        continue
    if start_line != -1:
        brace_count += line.count('{')
        brace_count -= line.count('}')
        if brace_count == 0:
            end_line = i
            break

print(f"Dict spans lines {start_line} to {end_line}")

# Extract existing entries from lines[start_line+1:end_line]
existing_entries = {}
entry_pattern = r'^\s*"([^"]+)"\s*:\s*(\([^)]+\)|"[^"]*")\s*,?\s*(?:#.*)?$'

for i in range(start_line + 1, end_line):
    line = lines[i].rstrip()
    match = re.match(entry_pattern, line)
    if match:
        key = match.group(1)
        value = match.group(2)
        existing_entries[key] = value

print(f"Found {len(existing_entries)} existing entries")

# Merge new mappings (new ones take precedence for duplicates)
# Convert new mappings to same format as existing (simple strings, not tuples)
merged = {}
for key, value in existing_entries.items():
    merged[key] = value

for key, (model_key, league) in new_mappings.items():
    merged[key] = f'"{model_key}"'

print(f"Total after merge: {len(merged)} entries")

# Sort alphabetically
sorted_keys = sorted(merged.keys())

# Build the new dict content
new_lines = lines[:start_line + 1]  # Up to and including the opening line
for key in sorted_keys:
    new_lines.append(f'    "{key}": {merged[key]},\n')
new_lines.append('}\n')
new_lines.extend(lines[end_line + 1:])

# Write back
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\booking\team_map.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Successfully updated team_map.py")

# Verify the result
import subprocess
result = subprocess.run(["python", "-c", "from booking.team_map import SPORTYBET_TEAMS; print(len(SPORTYBET_TEAMS))"],
                       capture_output=True, text=True, cwd=r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv")
print(f"Verification: {result.stdout.strip()} entries in SPORTYBET_TEAMS")
if result.stderr:
    print(f"Error: {result.stderr}")