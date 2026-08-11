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
   Verified: `engine/softness.py` deleted from the tree; `engine/leagues.py` is the single home (`WHITELISTED_LEAGUES`, 18 leagues, `is_deploy_eligible()` = whitelist membership only). ID402 FULLY REMOVED. → [[Rules.md]]

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
