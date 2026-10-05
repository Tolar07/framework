# Parked 2026-10-05

The Architect asked for every piece of the framework to be connected to something
and doing a job (2026-10-05). An audit found these files connected to nothing that
runs: each needed the laptop (Windows paths, laptop scheduled tasks, MCP servers)
or was read by no code. They are parked here, never imported and never run, the
same as the rest of `legacy/laptop/` (see `../README.md` to bring one back).

| File | Was | Why parked | What does its job now |
|---|---|---|---|
| `mcp_health.py` | probed the laptop's MCP servers | laptop task, retired 2026-10-03; no workflow passes its keys | `watchdog.yml`, `supervisor.yml` |
| `alert_dispatcher.py` | SMTP/webhook alerts | only `mcp_health.py` and `alert_failure.ps1` called it | Telegram alerts in `daily.yml`, `watchdog.yml`, `supervisor.yml` |
| `rotate_logs.py` | rotated `.bat`-redirected logs | only `mcp_watchdog.bat` ran it | the run log in `memory/runs.jsonl` rotates itself (`monitor/json_log.record_run`) |
| `run_daily.bat`, `mcp_watchdog.bat`, `alert_failure.ps1` | laptop scheduled tasks | Windows-only; `alert_failure.ps1` called a script that no longer exists | GitHub Actions |
| `leagues.json` | August's 61-league registry | read by nothing | `engine/slate.py` `WHITELIST_LEAGUES` |
| `fixtures.json` | an old fixture dump | read by nothing | the daily fetch (HR59) |
| `workflows/sync-health.yml` | vault-sync check | pointed at `./olp_xdv_agent/olp_xdv` (the workspace layout) and `C:/Users/...` paths; could not run here | `tests/agent_refs_test.py` checks every path the docs name |

The 8 generic `.claude/rules/*.md` files (TypeScript examples) moved to
`.claude/legacy/rules/` in the same change: they loaded into every session and
contradicted this repo's own rules (80% coverage, Playwright, other models).
