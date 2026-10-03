#!/usr/bin/env python3
"""Send today's heartbeat to Telegram using existing notify infrastructure."""

import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env first
from dotenv import load_dotenv
load_dotenv()

from output.notify import broadcast

# Read today's heartbeat
heartbeat_path = os.path.join(os.path.dirname(__file__), 'output', 'boards', 'heartbeat_2026-09-02.txt')

with open(heartbeat_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("Sending heartbeat to Telegram...")
print(f"Content length: {len(content)} chars")

ok, notes = broadcast(content)

print(f"Result: {'SUCCESS' if ok else 'FAILED'}")
for note in notes:
    print(f"  {note}")