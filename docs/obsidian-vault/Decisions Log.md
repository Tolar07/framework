# Decisions Log.md — Running Record of Architect Directives

> **Single source of truth for "what did the Architect actually decide and when."**
> Backfilled from repo history + `RATIFICATIONS.md` (verified 2026-08-11), then
> the four explicit 2026-08-11 directives are recorded. **Every future directive
> gets appended here.** Cross-links to [[Rules.md]], [[Protected Constants.md]],
> and [[Architecture.md]].

## Backfilled history (from RATIFICATIONS.md + git)

| Date | Directive | Effect |
|------|-----------|--------|
| 2026-08-04/08 | **ID405 market restrictions** — Away/Over2.5/Home Win blocked from capital on negative-CLV backtest evidence | Market gate narrowed to Draw + Under 2.5 (later reversed, see 2026-08-10) |
| 2026-08-05 | **WhatsApp delivery (ID406)** — official Meta Cloud API board delivery | WhatsApp channel added |
| 2026-08-06 | **WhatsApp KILLED** — token expiry + template-approval pain; the web dashboard replaces it | ID406 dead; credentials env-commented so it CANNOT send |
| 2026-08-06 | **Email copy channel + recalibration SHADOW (ID407)** | `output/email_deliver.py`, `engine/recalibration.py` |
| 2026-08-06 | **Four operational upgrades (ID408)** — run watchdog, gate telemetry, team-alias suggestions, auto-retry | `monitor/run_watchdog.py`, `engine/cross_league.py`, `data/retry.py` |
| 2026-08-06 | **EFL Cup on board + odds-quota override + fixtures never dropped (ID409)** | `pipeline/odds.py`, `data/fixtures_source.py` |
| 2026-08-06 | **EVENTSDAY fallback (ID410)** — today's cup qualifiers reach the board | `data/` fixtures path (exact fn name unverified — see [[Open Questions.md]]) |
| 2026-08-07 | **3-day rolling window** ratified as the scan reference | `days_ahead=3` |
| 2026-08-09 | **Softness PAUSED** (not yet deleted) + **market scope fix** + **full-picture board** + **accumulator prep script** | All leagues deploy-eligible, no cap; `scripts/accumulator_prep.py` |
| 2026-08-10 | **ID405 market gate OPENED** — `BLOCKED = {}`, all 5 markets deployable; the earlier negative-CLV evidence is NOT dismissed, the book is widened to test forward in paper mode | `engine/markets.py` |
| 2026-08-10 | **Same-day product bet** — THE CALL / produced bet / accas / singles draw ONLY from fixtures kicking off today (replaces 3-day window as the *product* rule; 3-day stays scan reference) | `RATIFICATIONS.md` §1437 |
| 2026-08-10 | **Production intent** — Acca A = top 4–5 highest-confidence fixtures, each leg that fixture's own single highest-probability market; no forced diversity; a fixture never appears in two bets; remainder → split accas + singles, each with its own booking code | `engine/acca.py`, `.claude/OLP_XDV_PRODUCTION_INTENT.md` |
| 2026-08-10 | **Ranking by confidence** — legs ranked by model probability (was EV) | `engine/acca.py` |
| 2026-08-10 | **Conference League added** — 17th → **18th** whitelisted league | `engine/leagues.py` |
| 2026-08-11 | **ARCHITECT_SIGNOFF=1** — publish the current board to the client dashboard, running live **side-by-side with paper** until mean CLV turns positive; override is never silent (stamped into `publish_audit.jsonl`) | `.env`, `webapp/schema.py` |
| 2026-08-11 | **Go-live: PHASE 2 → 3** — capital block lifted; framework may record real stakes but NEVER places a bet; capital authority stays with the Architect | `config.py` (`PHASE = 3`), commit `62ba6b9` + retroactive RATIFICATIONS entry (commit `76216e0`) |

## The four directives for this record (11 Aug 2026) — all verified in code

1. **Softness / deploy-eligibility gate (Tier A/B league restriction, FIX 3) CANCELLED — market opened to all leagues.**
   Verified: `engine/softness.py` deleted from the tree; `engine/leagues.py` is the single home (`WHITELISTED_LEAGUES`, 25 leagues, `is_deploy_eligible()` = whitelist membership only). ID402 FULLY REMOVED. → [[Rules.md]]

2. **ID405 (away wins never recommended) OVERRIDDEN — away-win recommendations now allowed.**
   Verified: `engine/markets.py:61` "SCOPE OVERRIDDEN 2026-08-11 (Architect directive, named): away wins may now be …" + `BLOCKED = {}`. All markets deployable. → [[Rules.md]]

3. **API key priority: paid key PRIMARY, free/router keys BACKUP only.**
   Verified: `pipeline/odds.py` `_odds_keys()` walks `ODDS_API_KEY` (the personal/paid key) first, then `ODDS_API_KEY_BACKUP` (free-tier reset or a router key). The pipeline uses whichever has quota above the floor; the api-football fallback covers the 5 deploy leagues when both are spent. → [[Architecture.md]]

4. **Market selection changed: per fixture, evaluate all available markets (1X2, O/U 1.5, O/U 2.5, double chance, BTTS) and select whichever has the strongest signal for that fixture, rather than defaulting to 1X2.**
   Verified: `engine/acca.py:141-152` `_best_deployable_leg()` — every fixture evaluated across `mkt.EDGE_MARKETS` (1X2, O/U1.5, O/U2.5, BTTS, Double Chance); picks its OWN single best market by highest **EDGE = model_prob × price − 1**, tiebreak model_prob, then canonical order. → [[Rules.md]], [[Open Questions.md]]

---

## ⚠ What this log could NOT verify (flagged honestly)

- **Exact dating of earlier RATIFICATIONS entries** was transcribed from the log's own headers; the four 2026-08-11 directives above are the ones checked directly against code.
- The **calibration-log league scope** question (did it widen with the softness cancellation?) is NOT resolved — see [[Open Questions.md]].
- The **go-live ratification was retroactive**: `config.py` claimed "Recorded in RATIFICATIONS.md (2026-08-11)" but no entry existed until appended 2026-08-11 (commit `76216e0`).

---

## 2026-08-16 · HR56 Architect Directive Supremacy + Whitelist reconciliation

**Directive (chat, 2026-08-16):**
1. **HR56 formalized** as a hard rule in [[Rules.md]] (Directive Supremacy).
2. **Whitelist consolidated to 61** — the union of historical 18 (2026-08-10), 25 (2026-08-12), and current 61 (2026-08-13 aggressive European expansion) is **61 distinct leagues** (18⊂61; 25⊂61 with 4 renames). A literal sum (104) would fabricate 43 leagues → HR35 forbids. The authoritative file is `config/leagues.json` (loaded by `engine/league_registry.py` at import; `engine/leagues.py` `WHITELISTED_LEAGUES` is derived).
3. **Git-tracked repo copy is canonical** — `olp_xdv_agent/olp_xdv/docs/obsidian-vault/` is the single source of truth for governance docs. The `Documents/OLP_XDV_Vault` mirror (non-git, drifted) is deprecated.

**Implemented in code (retroactive ratification):**
- `config/leagues.json` already at 61 (`deploy_eligible=true` for all 61) — committed clean at HEAD (`f571f9f`), no reversion.
- `engine/league_registry.py` is the runtime loader (authoritative).
- **Note:** The 61 was originally added by agent commit `811eefb` (2026-08-13, message "fix(data): correct thesportsdb league IDs + add verified TEAM_ALIASES") without a dated Architect directive — a breach of HR34 / Protected Constants #5. This is now **retroactively ratified** by HR56 r7 audit order.

**Doc updates applied (this commit):**
- [[Rules.md]] — HR56 row added; ID401 updated to "61 leagues" with authoritative-file chain; "Ranking by confidence" superseded by EDGE; two new doc-vs-code disagreements (#5 two vaults, #6 config/leagues.json authority).
- [[Open Questions.md]] — Item 1 updated 25→61; new Item 9 (two vaults).
- [[Protected Constants.md]] — Item 5 updated to 61 + authoritative file chain.
- [[Architecture.md]] — League pool line updated to 61 + authoritative file chain.
- [[OLP XDV.md]] — Already says "61 whitelisted leagues"; vault location note updated to canonical repo copy.

**Committed & saved:** this session will commit the four doc changes above. The 61 whitelist was already committed in `config/leagues.json`.

**Discrepancy found & resolved:** the undocumented 61 expansion (`811eefb`) + two drifting vaults + stale doc numbers (18/25/61) — all resolved by this reconciliation per HR56 r7.

---

## 2026-08-18 · ALL FIXTURES ELIGIBLE — Permanent Rule (Architect Directive)

**Directive (chat, 2026-08-18):**
"new rule all fixtures are eligible never forget"

**Effect:**
1. **Codified as permanent rule** in [[Protected Constants.md]] §6 and [[Rules.md]] Standing Rules: every fixture from every whitelisted league (61 leagues, `config/leagues.json`) is scan-eligible AND deploy-eligible. No softness tiers, no deploy caps, no scan-only classes, no "Tier A/B" restrictions. The whitelist IS the eligibility boundary — inside it, every fixture is equal.
2. **Non-regressible** — no agent may re-introduce tiering, caps, or partial-eligibility without an explicit, named Architect instruction.
3. **Retroactively ratifies** the 2026-08-11 ID402 cancellation (softness tiers fully removed) and 2026-08-16 consolidation to 61 leagues as permanent governance.

**Implemented in docs (this commit):**
- [[Protected Constants.md]] — Added §6 "ALL FIXTURES ELIGIBLE — PERMANENT RULE" with cross-links to ID402 removal, HR34, ID401.
- [[Rules.md]] — Added "ALL FIXTURES ELIGIBLE" standing rule with implementing code references.

**Already implemented in code (verified):**
- `engine/leagues.py` — `is_deploy_eligible()` = whitelist membership only (no tiering logic remains)
- `engine/league_registry.py` — loads `config/leagues.json` (61 leagues, all `deploy_eligible=true`)
- `config/leagues.json` — authoritative source, all 61 leagues marked `deploy_eligible=true`
- `run_daily.py` — unified pool: "every rated fixture across all whitelisted leagues is deploy-eligible, so pull prices for all of them" (line ~680)

**Committed & saved:** this session will commit the doc changes above. The code implementation was already in place from 2026-08-11/16.

---

## 2026-08-18 · BET PRODUCTION LOGIC — Hard Rule (HR58)

**Directive (chat, 2026-08-18):**
"make the bet production logic a hard rule"

**Effect:**
1. **Codified as HR58** in [[Rules.md]] — the production bet pipeline in `engine/acca.py` is PROTECTED and may not be silently altered.
2. **Added as Protected Constant #7** in [[Protected Constants.md]] — Bet Production Logic HARD RULE with all 10 components enumerated.
3. **Non-regressible** — any change requires explicit Architect ratification in RATIFICATIONS.md.

**Components Protected (from `engine/acca.py` and `engine/markets.py`):**
1. **Eligibility**: kickoff_date == today (HR35), `on_deploy_shortlist`, DEPLOYABLE market with live price
2. **Multi-market selection**: ALL `EDGE_MARKETS` (1X2, O/U 1.5, O/U 2.5, BTTS, Double Chance) via `_best_deployable_leg()`; each fixture picks its OWN best market by highest **EDGE = model_prob × price − 1**, tiebreak model_prob, then canonical order
3. **Hard odds cap**: MAX_ODDS_CAP = 2.00 (FL-bias guardrail) — reject any market priced > 2.00
4. **Agreement gate (opt-in)**: when `agreement_band` set, only markets where model and book implied prob agree within band; default None = shipped EV-ranking
5. **Acca A**: top 4–5 highest-EDGE legs (shortened if fewer, never padded)
6. **Split accas**: remainder split into ~4–5 leg groups (never one giant acca), deterministic chunking
7. **Singles**: every remaining fixture's natural best market as standalone slip, EACH with own booking code
8. **No fixture in two bets** — once in Acca A, removed from pool
9. **Write-back**: leg's pick written onto BoardFixture (best_market_key, best_market, best_price, best_model_prob, best_mes_ev) so CALL, produced-bet record, and scan show SAME market
10. **Verification stamp**: every leg carries `verification_stamp` from gate (✓ SportyBet ✓ FlashScore or ⚠ unverified) through to Telegram and web — byte-faithful per webapp_feed_parity_test

**Implemented in docs (this commit):**
- [[Rules.md]] — Added HR58 row with full component list and implementing code references
- [[Protected Constants.md]] — Added §7 "Bet Production Logic — HARD RULE" with cross-links
- [[Viking Match Analysis 2026-08-18.md]] — Created analysis document validating HR58 against actual match result (Dinamo Zagreb 2-2 Viking)

**Already implemented in code (verified):**
- `engine/acca.py` — `build_production_bets`, `_best_deployable_leg`, `_make_acca`, `_chunk_remainder`, `render_production_block`
- `engine/markets.py` — `EDGE_MARKETS`, `BLOCKED`, `DEPLOYABLE`, `model_prob`, `blend_toward_market`, `MAX_ODDS_CAP = 2.00`
- `config.py` — paper-only gate (`assert_paper_only()`)

**Committed & saved:** this session will commit the doc changes above. The code implementation was already in place from 2026-08-11 (EDGE-ranking directive) and 2026-08-10 (production intent).

---

## 2026-08-19 · ODDS DEPLOYMENT POLICY — 1.20 floor, 1.50 preferred sweet spot, 2.00 cap (Architect Directive)

**Directive (chat, 2026-08-19):**
"the framework or logic must all negative EV ODDS from 1.20 to 1.50 odds is acceptable. but 1.50 to 2.00 which is the max is 50/50 if i will make a bet personally i bet between 1.20 to 1.50 to be safe and add them as an acca to get the best value dependant on the amount of fixtures available"

**Effect (deployment filter — NOT a calibration change):**
1. **Hard floor `MIN_ODDS_FLOOR = 1.20`** — any market priced below 1.20 is rejected (heavy favourites: overround swallows any perceived edge, negligible EV even when model agrees).
2. **Preferred zone `PREFERRED_ODDS_CEILING = 1.50`** — the "safe" deployment sweet spot. A fixture's best leg is chosen from the 1.20–1.50 zone FIRST; a 1.50–2.00 leg is admitted only when no preferred-zone market exists for that fixture. Mirrors the Architect's personal risk tolerance: accas built from short-priced legs with compounded value.
3. **Hard ceiling unchanged `MAX_ODDS_CAP = 2.00`** — (FL-bias guardrail) reject any market priced above 2.00. The 1.50–2.00 band is the fallback band, not the primary target.
4. **Acca composition** — Acca A / split accas / singles draw only from admitted legs (1.20–2.00, preferred 1.20–1.50); the number of fixtures available determines how many legs compound.

**Is this a protected-constant change?** No. This is a deployment filter consistent with the existing `max_odds_cap` pattern — it does NOT touch ARCHITECT_SIGNOFF, the CLV/legs gate, capital deployment, ID405 scope, or calibration (probabilities are untouched; only which priced legs get bet). HR58's protected components (1–10) are unchanged in structure; the odds window is an additional admission filter inside `_best_deployable_leg()`.

**Implemented in code (this commit):**
- `engine/acca.py` — new constants `MIN_ODDS_FLOOR = 1.20`, `PREFERRED_ODDS_CEILING = 1.50`; `_best_deployable_leg()` gains `min_odds_floor` / `preferred_ceiling` params + floor check + preferred-zone tracking (`best_in_preferred or best`); `build_production_bets()` / `build_accas()` thread the two params (defaults active everywhere — callers unchanged).

**Tests (this commit):**
- `tests/acca_builder_test.py` — REAL TICKET regression updated: 12/14 admitted (Belgium 2.05 above cap, South Africa 1.16 below floor), every admitted leg in [1.20, 2.00]; new PREFERRED ZONE block asserts a 1.45 leg beats a 1.55 leg on the same fixture, and a 2.10 leg is rejected leaving only the 1.80 fallback.

**Committed & saved:** this session will commit `engine/acca.py` + `tests/acca_builder_test.py` + this log entry.

---

## 2026-08-24 · CLV GATE OVERRIDE — Survival-Mode Testing (Architect Directive)

**Directive (chat, 2026-08-24):**
"CLV gate bypass for survival testing — publish allowed on leg count only (12 legs minimum). Re-enable when CLV turns positive."

**Effect:**
1. **CLV publish gate modified** — the requirement "mean CLV > 0" is suspended for survival-mode testing. The 12-leg minimum (down from 30) remains as the sole publish gate.
2. **Reasoning** — The framework needs live survival fixtures (25–35 per board, 1–2 assure survival) to accumulate CLV data. Current mean CLV ≈ -9.4% blocks all publishing, preventing the very data collection needed to turn CLV positive.
3. **Re-enable trigger** — Gate auto-re-enables when mean CLV ≥ 0 across ≥12 logged legs.
4. **Audit trail** — All boards published under override are stamped `clv_gate_override=true` in `publish_audit.jsonl` for post-hoc analysis.

**Protected Constant Impact:**
- [[Protected Constants.md]] §2 "CLV Gate" — threshold temporarily suspended (not deleted). The original gate (12/30 legs, mean CLV > 0) remains the permanent rule; this override is a named, time-boxed exception.

**Code Changes Required (this commit):**
- `run_daily.py` / `clv/clv_logger.py` — read `CLV_GATE_OVERRIDE` env var or check directive flag; if active, allow publish at 12 legs regardless of mean CLV
- `config.py` — add `CLV_GATE_OVERRIDE = os.getenv("CLV_GATE_OVERRIDE", "0") == "1"`

**Committed & saved:** this session will commit the code changes and this log entry.

---

## 2026-08-28 · ARCHITECT SIGNOFF REAFFIRMED — Proceed Past Negative CLV + Heartbeat Dispatched

**Directive (chat, 2026-08-28):**
"Architect sign-off: Required but blocked by negative CLV proceed" + "send the heartbeat to telegram"

**Effect:**
1. **Sign-off reaffirmed** — the Architect explicitly authorizes proceeding despite negative mean CLV (currently ≈ -10.21% across 42 legs). This reaffirms the 2026-08-21 HR59 gate-suspension (gate already `gate_met=True`), so it is NOT a protected-constant change — only a named Architect instruction on the record. Capital authority remains Architect-only; `config.assert_paper_only()` still enforces no real stake routed by code.
2. **Heartbeat dispatched to Telegram** — `output/heartbeat_2026-08-28.txt` (Racing Santander v Elche, BTTS yes, 60%, +10.0% edge, Bet365 1.67) delivered via `notify.deliver()` (primary chat + subscribers). A copy was placed in `output/boards/` so the `/heartbeat` command serves it on request.

**Status at directive:**
- Legs with logged CLV: 42/30 required (gate passed on count)
- Mean CLV: -10.21% (negative — gate met only under HR59 waiver)
- Gate status: MET (waived by Architect directive, signed off)
- Architect sign-off: REQUIRED & AFFIRMED this session (Architect-only capital authority intact)


