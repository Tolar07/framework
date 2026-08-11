# OLP XDV Agent CLI — Command Reference

## Invocation

```
py -3.12 agent_cli.py <command> [--json] [--brain <path>] [--phase <phase>] [--limit <n>] [command-specific opts]
```

All commands support:
- `--json` — structured JSON output (envelope: `{"status": true, "data": ..., "message": ""}`)
- `--brain <path>` — override brain DB path (default: `brain/store.DEFAULT_BRAIN_PATH`)
- `--phase <phase>` — phase filter for CLV/gate/telemetry (default: `phase2_paper`)
- `--limit <n>` — row limit for predictions/produced bets (default: 100 / 30)

Default output is human-readable text. Use `--json` for agent tool-loading.

---

## stats

Brain overview — CLV by market/league/tier, gate, telemetry, outcomes, produced bets, last run.

```bash
py -3.12 agent_cli.py stats --json
py -3.12 agent_cli.py stats --phase phase2_paper
```

**JSON data fields:**
- `overview` — `predictions_summary()` dict (n_rows, n_runs, last_run_date, last_run_id, last_run_predictions)
- `clv_by_market` — list of `{market, n, mean_clv_pct, n_beat_close}`
- `clv_by_league` — list of `{league, n, mean_clv_pct}`
- `clv_by_tier` — list of `{tier, n, mean_clv_pct}`
- `engine_clv` — list of `{model_engine, n, mean_clv_pct}` sorted by -n
- `calibration_by_market` — list of `{market, n, mean_clv_pct, mean_hit, mean_model_prob}`
- `gate_status` — `{legs_logged_total, legs_with_clv, gate_requirement, mean_clv_pct, positive_mean_clv, gate_met_pending_architect_signoff, note}`
- `leg_telemetry` — telemetry dict
- `produced_bets` — `{days, legs, settled, won, pending, hit_rate, by_day}`
- `last_run` — last run dict or null

---

## lookup <query>

What did we predict for a team/fixture.

```bash
py -3.12 agent_cli.py lookup "Fenerbahce" --json
py -3.12 agent_cli.py lookup "Arsenal vs Chelsea" --json --limit 50
```

The query is matched case-insensitively and accent-folding against team names and fixtures.
If no rows match, returns `{"status": true, "data": [], "message": "NO DATA - PENDING"}`.

**JSON data:** list of prediction row dicts from `Brain.predictions_for`.

---

## board [--date D] [--raw|--published]

Produced board JSON for a date (default: latest published).

```bash
py -3.12 agent_cli.py board --json                              # latest published board
py -3.12 agent_cli.py board --date 2026-01-15 --json            # specific date published
py -3.12 agent_cli.py board --date 2026-01-15 --raw --json      # raw board file
```

- `--raw` — read the raw board file from `output/boards/<date>.json`
- `--published` (default) — read the client-trimmed published board via `webapp.schema.read_published`

If no boards exist, returns an error envelope.

---

## clv [--by market|league|tier] [--phase P]

CLV breakdown.

```bash
py -3.12 agent_cli.py clv --by market --json
py -3.12 agent_cli.py clv --by league --phase phase2_paper --json
py -3.12 agent_cli.py clv --by tier --json
```

**JSON data:** list of `{market|league|tier, n, mean_clv_pct, n_beat_close}` (n_beat_close only for market).

---

## gate

Phase-3 gate status + road-to-gate.

```bash
py -3.12 agent_cli.py gate --json
```

**JSON data fields:**
- `gate_status` — `{legs_logged_total, legs_with_clv, gate_requirement, mean_clv_pct, positive_mean_clv, gate_met_pending_architect_signoff, note}`
- `leg_telemetry` — telemetry dict (total_legs, settled_legs, won_legs, hit_rate_pct, mean_clv_pct)

---

## audit [--no-odds] [--league L]

League coverage audit (READY/BLOCKED per league).

```bash
py -3.12 agent_cli.py audit --no-odds --json                    # all leagues, skip odds check
py -3.12 agent_cli.py audit --league "Danish Superliga" --json  # single league
```

- `--no-odds` — skip the odds-source check (faster; doesn't need provisioned keys)
- `--league L` — audit only one league (default: all whitelisted leagues)

Imports `config` to load `.env` provisioned keys (same pattern as `league_audit.py`).

**JSON data:** dict keyed by league name → `{ready: bool, details: {...}}`.

---

## leagues

Whitelisted leagues + tier.

```bash
py -3.12 agent_cli.py leagues --json
```

**JSON data:** list of `{league, tier}` for all whitelisted leagues (currently 17 leagues, one pool — tiers are back-compat only).

---

## schema

JSON-Schema tool definitions for agent tool-loading.

```bash
py -3.12 agent_cli.py schema --json
```

Returns the full command schema (name, description, parameters with types) for all 8 commands. Mirrors the `_generate_schema` pattern from `sports_skills/cli.py`.

---

## Error Handling

All errors are graceful (no tracebacks):
- Missing brain DB → `{"status": false, "message": "Brain not found at <path>"}`
- No data for query → `{"status": true, "data": [], "message": "NO DATA - PENDING"}`
- Unknown command → argparse exits with usage
- Any exception → `{"status": false, "message": "<ExceptionType>: <message>"}`

**HR35:** Never fabricates numbers. Missing data is reported as `NO DATA - PENDING`, never a guessed value.