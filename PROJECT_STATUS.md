# OLP XDV — Project Status

*Single source of truth for what's working, what's broken, and what needs unblocking. Updated each session.*

---

## ✅ WORKING (as of 2026-08-09)

| Area | Status | Evidence |
|------|--------|----------|
| **Daily pipeline** | Green | `run_daily.py` completes end-to-end; boards written to `output/boards/` |
| **Data pipeline (multi-source)** | Green | TheSportsDB → odds → API-Football failover with circuit breakers |
| **Dixon-Coles + Elo + xG + Bookmaker engines** | Green | Four independent opinions computed per fixture |
| **Consensus vote (ID412/413)** | Green | Majority across available engines, persisted to brain |
| **Market gate (ID405)** | Active | Away Win, Over 2.5, Home Win blocked from deploy |
| **Softness tiers (ID402)** | Active | 17 leagues across A/B/C/D; deploy only from A/B, cap 6 |
| **3-day rolling window** | Active | `days_ahead=3` (ratified 2026-08-07) |
| **Promoted-club carry-over** | Active | Prior-season fit rates newly promoted clubs |
| **CLV logging + CL-LIVE capture** | Active | Paper legs logged, closing lines captured near kickoff |
| **Health monitor** | Active | 9 probes, 2-hourly Task Scheduler, state-change alerts only |
| **Two-tier web dashboard** | Green | `/dashboard` (client) + `/admin` (authed, full internals) |
| **Admin publish gate** | Active | Manual "Approve → Publish to Client" with audit log |
| **Telegram push** | Green | Daily board delivered at 07:00 via notify.py |
| **Email copy channel** | Green | SMTP delivery, best-effort, never fails run |
| **Brain (SQLite persistence)** | Green | Model caching, prediction log, `/stats` queries |
| **Test suite** | 41/41 green | All suites passing |

---

## 🔴 BROKEN / NEEDS FIX (Current Sprint)

| # | Issue | Root Cause | Fix Status |
|---|-------|------------|------------|
| **1** | **Market scope bug** — board only shows Draw/Under 2.5 picks | `BLOCKED_DEPLOY_MARKETS` in `engine/softness.py` blocks "home win" AND "away win", leaving only Draw + Under 2.5 as deployable. But the *approved market list* (per Architect) is: **Win, Away Win, Double Chance, Over/Under 1.5, Over/Under 2.5, BTTS** — 6 markets, not 2. The gate was narrowed based on backtest evidence but the display/selection logic wasn't updated to use the full approved list for scanning/ranking. | ✅ **FIXED 2026-08-09** — added `APPROVED_MARKETS` (display/scan: all 9 canonical keys) separate from `DEPLOYABLE` (capital gate: Draw + Under 2.5). `_best_market_desc`, legacy table, scan grid now use the approved list. Deploy gate unchanged (ID405 still blocks Away/Over2.5/Home from capital). |
| **2** | **Full-picture board display** — only Tier A/B fixtures show in THE CALL; scan leagues C/D with fixtures are in PART 2 but not visibly grouped with deploy candidates | The scan IS wide (all 17 leagues in PART 2), but the Telegram/phone board (`render_telegram_board`) and web dashboard group by league without highlighting which fixtures are Tier A/B accumulator candidates. Need: **every fixture visible, grouped by league, with A/B candidates marked as a distinct subset at top**. | ✅ **FIXED 2026-08-09** — Telegram `render_scan_tables` shows ALL fixtures per league with Tier A/B `on_deploy_shortlist` marked ★ "ACCUMULATOR CANDIDATES" at top; web scan table (client + admin) sorts acc candidates first with ⭐ + teal highlight + league badge count. |
| **3** | **Accumulator prep script missing** | No script exists to take Tier A/B picks and format a ready-to-paste bet slip (selections, combined odds, suggested stake). Must NOT auto-submit — Architect pastes manually into SportyBet. | ✅ **BUILT 2026-08-09** — `scripts/accumulator_prep.py` reads today's `board_<date>.json`, extracts Tier A/B shortlist, formats `Fixture — Market @ Odds (prob)` legs, combined odds, suggested stake. READ-ONLY, never places a bet. Flags ID405-blocked picks + no-price legs for Architect review. |

---

## 🟡 PARTIAL / NEEDS VERIFICATION

| Area | Status | Notes |
|------|--------|-------|
| **WhatsApp** | Killed by Architect (2026-08-06) | Token expiry + template approval pain; web dashboard replaces it |
| **Odds API quota** | Critical (4/500) | Free tier exhausted; fixture capture allowed down to 5, price pulls blocked <40 |
| **Phase 3 gate** | 0/30 legs with CLV | Paper-only; needs Architect V7 sign-off before any capital |
| **Away-market overconfidence** | Structural | Model claims ~39% away, delivers ~30%; no screen/nudge fixes it — needs model refit |

---

## 📋 NEED FROM ARCHITECT TO UNBLOCK

| Need | Why | Urgency |
|------|-----|---------|
| **Confirm approved market list for DISPLAY vs DEPLOY** | The backtest says only Draw + Under 2.5 have positive CLV (and even Draw's is drift). But you named 6 markets as "approved": Win, Away Win, Double Chance, O/U 1.5, O/U 2.5, BTTS. Do you want all 6 shown/scanned but only 2 deployable? Or was the 6-market list the *deploy* intent and the backtest gate should be revisited? | **High** — fixes #1 |
| **Odds API quota upgrade or reset** | 4 credits left kills price pulls for deploy leagues; CLV capture stalls; Phase 3 gate can't advance | **High** — blocks live EV/CLV |
| **Personal TheSportsDB key** | Unblocks second-division data for promoted-club carry-over (5 clubs stuck NO DATA) | **Medium** |
| **SportyBet bet-slip format confirmation** | For accumulator prep script: single bet slip or multiple? Stake per leg or total? | **Medium** — needed for #3 |

---

## 🎯 NEXT ACTIONS

**Sprint 2026-08-09 ✅ COMPLETE** — all three items (market scope, full-picture display, accumulator prep) fixed and committed (`db687b5`).

Next up (in priority order):

1. **Run accumulator prep on a live board** — `python scripts/accumulator_prep.py` against today's `board_2026-08-09.json` once the daily run writes it; confirm the slip format against SportyBet (needs Architect's bet-slip answer, below).
2. **Unblock odds pipeline** — Odds API quota (4/500 left) stalls live EV/CLV + Phase 3 CLV gate. Architect must upgrade/reset before live price pulls resume.
3. **Model refit for away overconfidence** — model claims ~39% away, delivers ~30%; no screen/nudge fixes it. Structural; needs refit before Phase 3.
4. **Promoted-club carry-over data** — 5 clubs stuck NO DATA until personal TheSportsDB key lands.
5. **Land other session's in-flight work** — `run_daily.py` SportyBet cache-warm hook (imports clean), `monitor/data_quality.py` (mid-edit, IndentationError), `scripts/check_csv_validation.py`, `tests/data_quality_test.py` — verify, then reconcile commit.

---

*Last updated: 2026-08-09 — this file is the single status reference. Do not reconstruct from chat history.*
