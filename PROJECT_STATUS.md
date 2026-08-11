# OLP XDV — Project Status

*Single source of truth for what's working, what's broken, and what needs unblocking. Updated each session. Where this file and the code disagree, the code + `RATIFICATIONS.md` are the authority (HR35 applies here too — nothing is invented to fill a gap).*

---

## ✅ WORKING (as of 2026-08-11)

| Area | Status | Evidence |
|------|--------|----------|
| **Daily pipeline** | Green | `run_daily.py` completes end-to-end; boards written to `output/boards/`; last run 2026-08-11 complete AND delivered to Telegram |
| **Data pipeline (multi-source)** | Green | TheSportsDB → odds → API-Football failover with circuit breakers; SportyBet cache as fixture fallback |
| **Dixon-Coles + Elo + xG + Bookmaker engines** | Green | Four independent opinions computed per fixture |
| **Consensus vote (ID412/413)** | Green | Majority across available engines, persisted to brain |
| **League whitelist = unified pool (ID401)** | Green | **18 leagues** (incl. Conference League, added 2026-08-10), ONE pool — every whitelisted league scan- AND deploy-eligible |
| **Softness tiers (ID402)** | **REMOVED 2026-08-11** | `engine/softness.py` deleted; `engine/leagues.py` is the only league-eligibility home. No `SOFTNESS_PAUSED`/tier logic remains anywhere |
| **Market gate (ID405)** | **OPEN 2026-08-10** | `engine/markets.py` `BLOCKED = {}` — all five 1X2 markets + O/U + BTTS deployable. Earlier Away/Over2.5/Home block re-closable by re-adding to `BLOCKED` |
| **Same-day product bet (2026-08-10)** | Active | THE CALL, produced bet, accas, singles draw ONLY from fixtures kicking off today; the 3-day window stays the scan reference |
| **Production intent accas (2026-08-10)** | Active | Acca A = top 4–5 highest-confidence fixtures (each leg the fixture's own highest-probability market); remainder → split accas + singles; legs ranked by model probability; booking codes to Telegram; a fixture never appears in two bets |
| **SportyBet booking codes** | Active (best-effort) | `booking/booking_codes.py` — Playwright captures booking codes per acca; codes pre-fill the slip, NEVER stake (Phase-2 safe); per-leg BOOKED/MANUAL |
| **Team-name mapping (OLP ↔ SportyBet)** | Green 2026-08-11 | `booking/team_map.py` — reverse resolver (`resolve_team_to_model`) is EXACT + normalized-exact ONLY, NO fuzzy (HR35). Fixed wrong-club corruption (Millwall→AC Milan, Club Brugge→Cercle, Excelsior→Sparta). 33-check regression suite passes |
| **CLV logging + CL-LIVE capture** | Active | Paper legs logged, closing lines captured near kickoff |
| **Health monitor** | Active | 9 probes, 2-hourly Task Scheduler, state-change alerts only; self-heals stale live-season CSVs (NOT odds-fixture caches — re-pulling would spend the quota it protects) |
| **Two-tier web dashboard** | Green | `/dashboard` (client, trimmed) + `/admin` (authed, full internals); Binance design tokens |
| **Admin publish gate** | Active | Manual "Approve → Publish to Client" with audit log; `ARCHITECT_SIGNOFF=1` override stamped honestly into `publish_audit.jsonl` |
| **Telegram push** | Green | Daily board delivered at 07:00 via notify.py; 2026-08-11 run delivered |
| **Email copy channel** | Green | SMTP delivery, best-effort, never fails run (disabled in `.env` by default) |
| **Brain (SQLite persistence)** | Green | Model caching, prediction log, `/stats` queries |
| **Test suite** | Green | All suites passing incl. new `tests/team_map_reverse_test.py` |

---

## 🔴 BROKEN / NEEDS FIX (Current Sprint)

| # | Issue | Root Cause | Fix Status |
|---|-------|------------|------------|
| **1** | **Odds API quota spent** — primary (personal) key 1/500 remaining (hard floor 5) | The monthly free-tier quota is nearly exhausted | **MITIGATED 2026-08-11** — multi-key support: `ODDS_API_KEY` (main) + `ODDS_API_KEY_BACKUP` (backup) walked in order; api-football free fallback serves the 5 deploy leagues; entry prices honestly `NO DATA — PENDING` elsewhere (HR35, refuses to spend the month). Heals on the monthly reset or a pasted backup key |
| **2** | **No demonstrated edge (backtest negative)** | Cross-season backtest mixed; away market consistently negative | Structural — needs model refit before Phase 3; monitor whether 2526-style positives repeat |
| **3** | **Away-market overconfidence** | Model claims ~39% away, delivers ~30% | Structural; needs model refit, no screen/nudge fixes it |

---

## 🟡 PARTIAL / NEEDS VERIFICATION

| Area | Status | Notes |
|------|--------|-------|
| **WhatsApp** | Killed by Architect (2026-08-06) | Token expiry + template approval pain; web dashboard replaces it |
| **Phase 3 gate** | 12/30 legs with CLV, mean CLV −1.631% | Paper-only; gate NOT met (negative CLV). **Architect override active** (`ARCHITECT_SIGNOFF=1`, 2026-08-11): board published to client dashboard, running live side-by-side with paper until mean CLV turns positive. Override never silent — stamped in audit log + honest-edge statement stays on client view |
| **Stale odds-fixture caches** | Warn (not critical) | `data/cache/fixtures_from_odds/*.json` ~5 days old; deliberately NOT auto-healed (re-pull spends quota). Refreshes on next run once quota returns |

---

## 📋 NEED FROM ARCHITECT TO UNBLOCK

| Need | Why | Urgency |
|------|-----|---------|
| **Odds API reset / backup key** | Primary key at 1/500 kills price pulls for non-deploy leagues; CLV capture stalls; the honest `NO DATA — PENDING` gap widens. Paste a fresh key in `ODDS_API_KEY` or `ODDS_API_KEY_BACKUP`, or wait for the monthly reset | **High** — the live blocker |
| **Capital deployment (Phase 3)** | Real money is the Architect's decision alone — gate needs ≥30 legs with CLV, positive mean CLV, and V7 sign-off | **Architect's call** |

---

## 🎯 NEXT ACTIONS

**Sprint 2026-08-11 ✅ COMPLETE** — multi-key Odds API (personal main + backup), `ARCHITECT_SIGNOFF=1` + board published to client dashboard (live side-by-side with paper until CLV positive), SportyBet team-map reverse resolver (no-fuzzy, HR35) + 33-check regression suite, health monitor verified (exit code 2 is by design; env + Telegram-delivery issues GONE; quota reported honestly). See `docs/OLP_XDV_MASTER_DOCUMENTATION_2026-08-11.md`.

Next up (in priority order):

1. **Monitor quota reset / paste backup key** — the live blocker. Once quota returns, run_daily refreshes the stale odds-fixture caches and price pulls resume.
2. **Watch CLV daily** — the live side-by-side run is the honest test: publish override stays until mean CLV turns positive; gate re-blocks automatically if `ARCHITECT_SIGNOFF` is unset.
3. **Model refit for away overconfidence** — model claims ~39% away, delivers ~30%; structural, needs refit before Phase 3.

---

*Last updated: 2026-08-11 — this file is the single status reference. Do not reconstruct from chat history. If it disagrees with the code, trust the code + RATIFICATIONS.md and fix this file.*
