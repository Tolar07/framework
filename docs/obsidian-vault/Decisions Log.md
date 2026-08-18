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
