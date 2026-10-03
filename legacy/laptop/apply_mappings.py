#!/usr/bin/env python3
"""Apply the 268 mappings to team_map.py in alphabetical order"""

import re

# Read the current team_map.py
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\booking\team_map.py", "r", encoding="utf-8") as f:
    content = f.read()

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

# Now extract the existing SPORTYBET_TEAMS dict
# Find the SPORTYBET_TEAMS dict
start_idx = content.find('SPORTYBET_TEAMS: dict[str, str] = {')
if start_idx == -1:
    print("Could not find SPORTYBET_TEAMS dict")
    exit(1)

# Find the end of the dict (the closing brace at the right indentation level)
brace_count = 0
end_idx = start_idx
for i, char in enumerate(content[start_idx:], start=start_idx):
    if char == '{':
        brace_count += 1
    elif char == '}':
        brace_count -= 1
        if brace_count == 0:
            end_idx = i + 1
            break

dict_content = content[start_idx:end_idx]

# Extract existing entries
existing_entries = {}
# Pattern to match entries: "Key": "Value",
entry_pattern = r'"([^"]+)"\s*:\s*"([^"]+)"\s*,'
for match in re.finditer(entry_pattern, dict_content):
    key = match.group(1)
    value = match.group(2)
    existing_entries[key] = value

print(f"Found {len(existing_entries)} existing entries")

# Merge new mappings (new ones take precedence for duplicates)
merged = {**existing_entries, **new_mappings}
print(f"Total after merge: {len(merged)} entries")

# Sort alphabetically
sorted_keys = sorted(merged.keys())

# Build the new dict content
new_dict_lines = ['SPORTYBET_TEAMS: dict[str, str] = {']
for key in sorted_keys:
    new_dict_lines.append(f'    "{key}": "{merged[key]}",')
new_dict_lines.append('}')
new_dict_content = '\n'.join(new_dict_lines)

# Replace in the original content
new_content = content[:start_idx] + new_dict_content + content[end_idx:]

# Write back
with open(r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\booking\team_map.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Successfully updated team_map.py")

# Verify the result
import subprocess
result = subprocess.run(["python", "-c", "from booking.team_map import SPORTYBET_TEAMS; print(len(SPORTYBET_TEAMS))"],
                       capture_output=True, text=True, cwd=r"C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv")
print(f"Verification: {result.stdout.strip()} entries in SPORTYBET_TEAMS")
if result.stderr:
    print(f"Error: {result.stderr}")

import re