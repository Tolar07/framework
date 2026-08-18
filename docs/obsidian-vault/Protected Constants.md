# Protected Constants.md — Things No Agent May Edit or Self-Approve

> These are the levers that decide whether money moves and what clients see.
> **None of them may be changed, bypassed, or "fixed" by an agent without an
> explicit, named Architect instruction.** If you believe one is wrong, write it
> in [[Open Questions.md]] — do not flip it. Verified 2026-08-11.
> Cross-links to [[Decisions Log.md]] and [[Rules.md]].

---

## 1. `ARCHITECT_SIGNOFF`
- **What:** the Architect's override authority for the statistical client-publish gate. `ARCHITECT_SIGNOFF=1` in `.env` publishes the current board to the client dashboard even when the CLV gate is not met.
- **Current value:** `1` (set 2026-08-11 by Architect — run live side-by-side with paper until mean CLV turns positive).
- **Why protected:** it is the ONLY thing standing between the clients and a system that is currently **losing** to the closing line. It must never be flipped by an agent.
- **Never silent:** the override + live gate numbers are stamped into `publish_audit.jsonl`, and the honest-edge statement stays on the client view.
- **Implements:** `webapp/schema.py` (`_gate_state`, `check_client_publish_gate`, `write_published`).
- **Linked:** [[Decisions Log.md]] 2026-08-11 `ARCHITECT_SIGNOFF=1`.

## 2. The CLV / legs-required publish gate
- **What:** a board publishes only when ≥ **30** logged legs carry CLV **AND** the mean CLV is **positive**.
- **Current state:** **12/30** legs with CLV, mean CLV **−1.631%** (negative) → the statistical gate is **NOT met**. Publication is happening solely because of the `ARCHITECT_SIGNOFF` override (item 1).
- **Why protected:** this is the integrity measure that prevents shipping a losing model as if it were a winning one. It is deliberately strict.
- **Implements:** `webapp/schema.py`, `clv/phase3_gate.py`, `clv/clv_logger.py`, `clv/closing_capture.py`.
- **Linked:** [[Rules.md]] HR51; [[Architecture.md]] CLV/calibration.

## 3. Client-publish gating
- **What:** the admin "Approve → Publish to Client" flow (`webapp/server.py` `/admin`), the trimmed client-facing payload, and the audit log `publish_audit.jsonl`. A publish is an outward-facing, hard-to-reverse action.
- **Why protected:** publishing content to clients is a release; it must go through the gate (item 2) or an explicit Architect override (item 1). Never bypass both.
- **Implements:** `webapp/schema.py`, `webapp/server.py`, `output/boards/published/`.
- **Linked:** [[Decisions Log.md]] 2026-08-11 publish override.

## 4. Capital-deployment logic
- **What:** `config.PHASE` (2 = paper only / 3 = live capital permitted), `CAPITAL_ENABLED = PHASE >= 3`, and the `clv/phase3_gate.py` requirements. The framework NEVER places a bet — no auto-submission, no Playwright stake entry. Capital authority is **the Architect's alone**.
- **Current value:** `PHASE = 3` (lifted 2026-08-11, Architect order; commit `62ba6b9`).
- **Why protected:** this is the paper→real-money boundary. Lifting it is irreversible in effect; the bright line "code never stakes" must never erode.
- **Implements:** `config.py`, `clv/phase3_gate.py`, `booking/booking_codes.py` (read-only by construction).
- **Linked:** [[Decisions Log.md]] 2026-08-11 go-live; [[Rules.md]] HR51.

## 5. Related protections (smaller, but Architect-only too)
- **`WHITELISTED_LEAGUES`** — league eligibility is Architect-only (HR34); the **authoritative file is `config/leagues.json`** (loaded by `engine/league_registry.py` at import; `engine/leagues.py` `WHITELISTED_LEAGUES` is a derived back-compat symbol). Current whitelist = **61 leagues** (2026-08-13 aggressive European expansion, retroactively ratified 2026-08-16). Historical sizes 18 (2026-08-10) → 25 (2026-08-12) → 61 are the SAME growing list; the union is 61. Adding a league means editing `config/leagues.json` (with per-source IDs) — never editing `engine/leagues.py` directly.
- **`RATIFICATIONS.md`** — append-only (HR33); never rewritten, only extended.
- **`engine/markets.py` `BLOCKED`** — the ID405 market gate. It is currently OPEN (`BLOCKED = {}`); **re-closing a market** is an Architect decision (the negative-CLV evidence that justified the earlier block is not dismissed).
- **`.env` credentials** — `ODDS_API_KEY` (primary) / `ODDS_API_KEY_BACKUP` (backup), `THESPORTSDB_KEY`, `TELEGRAM_BOT_TOKEN`. Re-enabling a killed channel (e.g. WhatsApp) requires Architect approval per the standing order.
- **`config.PHASE` is not the only gate** — even at Phase 3, the CLV gate (item 2) governs what is published; the two are independent.

## 6. **ALL FIXTURES ELIGIBLE — PERMANENT RULE (2026-08-18 Architect Directive)**
- **What:** Every fixture from every whitelisted league is scan-eligible AND deploy-eligible. No softness tiers, no deploy caps, no scan-only classes, no "Tier A/B" restrictions. The whitelist (61 leagues, `config/leagues.json`) IS the eligibility boundary — inside it, every fixture is equal.
- **Why protected:** This codifies the 2026-08-11 cancellation of ID402 (softness tiers fully removed) and the 2026-08-16 consolidation to 61 leagues as a permanent, non-regressible rule. No agent may re-introduce tiering, caps, or partial-eligibility without an explicit, named Architect instruction.
- **Implements:** `engine/leagues.py` (`is_deploy_eligible()` = whitelist membership only), `engine/league_registry.py` (loads `config/leagues.json`), `config/leagues.json` (authoritative).
- **Linked:** [[Decisions Log.md]] 2026-08-11 ID402 FULLY REMOVED; [[Rules.md]] HR34, ID401, ID402.

---

## How to treat this list
- **Editing any of these without a named Architect instruction is a violation of HR35 spirit and the standing safety rules.** If you genuinely need one changed, surface it as an [[Open Questions.md]] item and wait.
- Every item here that has been touched by a directive links back to its row in [[Decisions Log.md]].
