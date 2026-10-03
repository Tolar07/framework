# Pipeline Coordination Refactor — Implementation Plan

**Problem**: Two disconnected pipeline implementations exist:
1. `olp_xdv_pipeline.py` — 10-agent mathematical pipeline with file-based handoff bus (`pipeline_agent_bus.py`)
2. `orchestrator.py` — Daily board pipeline (produces Telegram/board output)
3. `run_daily.py` — CLI entry point that calls `orchestrator.py`

They run independently. The 10-agent pipeline never produces the board; the board pipeline never runs the math stack.

**Goal**: Make `olp_xdv_pipeline.py` the **single orchestrator** that runs the full sequence and produces the board output, then deprecate `orchestrator.py`.

---

## Phase 1: Audit & Contract Definition

### 1.1 Map current data contracts
- [ ] Read `orchestrator.py` → identify exact output shape it produces for the board
- [ ] Read `olp_xdv_pipeline.py` → identify Agent 10 (CEO) output shape
- [ ] Define the **unified output schema** that satisfies both: board render + audit trail

### 1.2 Identify which agents are actually needed for board production
- Agent 1 (Ingestion) → Agent 2 (Filter) → Agent 4 (Verification) → Agent 5 (XDV Core) → Agent 6 (Odds Audit) → Agent 10 (CEO) → Board
- Agents 3, 7, 8, 9 may be optional/conditional — document decision

---

## Phase 2: Extend `olp_xdv_pipeline.py` as Main Entry Point

### 2.1 Add `run_pipeline()` function that:
- Creates run_id
- Executes agents 1→2→4→5→6→10 in sequence via the handoff bus
- Returns final CEO payload

### 2.2 Add `render_board_from_pipeline(ceo_payload)` function that:
- Takes Agent 10 output
- Produces the exact same board artifacts `orchestrator.py` produces:
  - `telegram_<date>.txt` (byte-faithful)
  - `feed_audit.jsonl` gate stamp
  - `acca_<date>_codes.json` (SportyBet booking codes)

### 2.3 Add CLI entry point: `python -m olp_xdv_pipeline --date 2026-08-18`

---

## Phase 3: Wire Into Daily Operations

### 3.1 Update `run_daily.py`:
- Replace `from orchestrator import run_daily_board` with `from olp_xdv_pipeline import run_pipeline, render_board_from_pipeline`
- Keep same CLI interface (date argument, dry-run flag)

### 3.2 Update Task Scheduler / daemon wiring:
- Daily Board (07:00) → calls new pipeline entry point
- Health Monitor / Watchdog → check pipeline stage status via `pipeline_agent_bus.get_pipeline_status()`

---

## Phase 4: Deprecate `orchestrator.py`

### 4.1 Verify parity:
- Run both pipelines for same date → diff `telegram_<date>.txt` outputs (must be byte-identical)
- Run `tests/webapp_feed_parity_test.py` — must pass

### 4.2 Move `orchestrator.py` → `orchestrator_DEPRECATED.py` with header comment
- Keep for reference during transition window (1 week)
- Remove after verified

---

## Phase 5: Hardening & Observability

### 5.1 Add pipeline-level retry/timeout per agent
- Agent 1 (scraping): 120s timeout, 2 retries
- Agent 5 (math): 180s timeout, 1 retry
- Others: 60s timeout, 1 retry

### 5.2 Add structured logging per stage (duration, fixture count, error details)

### 5.3 Add `pipeline_agent_bus.get_pipeline_status()` integration in health monitor

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `olp_xdv_pipeline.py` | Add `run_pipeline()`, `render_board_from_pipeline()`, CLI |
| `run_daily.py` | Switch import from orchestrator → pipeline |
| `pipeline_agent_bus.py` | Add per-agent timeout/retry helpers (optional) |
| `orchestrator.py` | Deprecate (rename) after parity verified |

---

## Acceptance Criteria

1. `python -m olp_xdv_pipeline --date 2026-08-18` produces identical `telegram_2026-08-18.txt` to current `run_daily.py`
2. `tests/webapp_feed_parity_test.py` passes
3. Daily Board daemon (07:00) runs via new pipeline without code change to scheduler
4. `pipeline_agent_bus.get_pipeline_status()` shows all stages green for a successful run
5. No regression in CLV gate / feed audit / acca codes

---

## Risk Mitigation

- **Parity risk**: Run side-by-side for 3 days before cutover (old orchestrator + new pipeline), diff outputs daily
- **Agent 5 math timeout**: Add explicit timeout wrapper; on timeout, mark stage failed, halt pipeline with clear error
- **SportyBet cache timing**: Agent 1 must wait for `booking.bridge` cache to be fresh (Data Steward runs 06:00 + 15:00)

---

## Rollback Plan

If parity fails: `git checkout orchestrator.py` and revert `run_daily.py` import — zero-downtime rollback.