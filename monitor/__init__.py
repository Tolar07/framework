"""Monitoring for the live framework.

run_watchdog.py   starts a scheduled daily board run that never happened and
                  says so on Telegram (.github/workflows/watchdog.yml).
supervisor.py     one status after every board run (supervisor.yml): board,
                  codes, workflows, the knowledge file and the run log.
news_loop.py      the pre-kickoff loop (news.yml -> news_check.py).
json_log.py       structured JSON lines; the committed run log memory/runs.jsonl
                  (one line per board run, order 30).

The laptop MCP probe and alert dispatcher were parked in
legacy/laptop/parked_2026-10-05/; the laptop "brain" in legacy/laptop/ on
2026-10-03. Outcome learning lives in engine/picks_ledger.py, engine/learning.py
and engine/loss_watch.py (memory/knowledge.json).
"""
