"""Test script for notify.deliver"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from output.notify import deliver

print("Testing notify.deliver...")
result = deliver('Test message from OLP XDV')
print(f'Result: {result}')