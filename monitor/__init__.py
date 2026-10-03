"""Monitoring for the live framework.

run_watchdog.py   starts a scheduled daily board run that never happened and
                  says so on Telegram (.github/workflows/watchdog.yml).
mcp_health.py     probes the laptop's MCP servers (laptop task "OLP XDV MCP
                  Watchdog").
alert_dispatcher.py, json_log.py  shared alert and structured-log helpers.

The laptop "brain" and its cup monitor were parked in legacy/laptop/ on
2026-10-03; outcome learning lives in engine/picks_ledger.py (every rated
fixture is recorded and graded) and engine/learning.py.
"""
