#!/usr/bin/env python3
"""Test booking code generation with actual Champions League acca payload."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from booking.booking_codes import book_accas

# Load the acca payload
acca_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'boards', 'acca_2026-08-25.json')
with open(acca_path) as f:
    acca_payload = json.load(f)

print("Testing booking with acca payload:")
print(json.dumps(acca_payload, indent=2))

# Run booking (headless=True for testing)
result = book_accas(acca_payload, headless=True)
print("\n=== BOOKING RESULT ===")
print(json.dumps(result, indent=2))