#!/usr/bin/env python3
"""
Temporary script to run the open questions report.
"""
import sys
sys.path.insert(0, '.')
from open_questions_report import main
sys.argv = ['open_questions_report.py', '--vault', 'docs/obsidian-vault', '--output', 'OPEN_QUESTIONS_REPORT.md']
main()