import os
import sys
sys.path.insert(0, '.')

from output.notify import broadcast

with open('output/boards/heartbeat_2026-08-31.txt', 'r', encoding='utf-8') as f:
    content = f.read()

print(f"Sending heartbeat ({len(content)} chars)...")
ok, notes = broadcast(content)
print(f"Success: {ok}")
for note in notes:
    print(f"  {note}")