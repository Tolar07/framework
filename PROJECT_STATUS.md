# OLP XDV — Project Status

*Single source of truth for what's working, what's broken, and what needs unblocking. Updated each session. Where this file and the code disagree, the code + `RATIFICATIONS.md` are the authority (HR35 applies here too — nothing is invented to fill a gap).*

---

## ✅ WORKING (as of 2026-08-12)

| Area | Status | Evidence |
|------|--------|----------|
| **Daily pipeline** | Green | `run_daily.py` completes end-to-end; boards written to `output/boards/`; last run 2026-08-11 complete AND delivered to Telegram |
| **Data pipeline (multi-source)** | Green | TheSportsDB → odds → API-Football failover with circuit breakers; SportyBet cache as fixture fallback |
| **Dixon-Coles + Elo + xG + Bookmaker engines** | Green | Four independent opinions computed per fixture |
| **Consensus vote (ID412/413)** | Green | Majority across available engines, persisted to brain |
| **League whitelist = unified pool (ID401)** | Green | **18 leagues** (incl. Conference League, added 2026-08-10), ONE pool — every whitelisted league scan- AND deploy-eligible |
| **Softness tiers (ID402)** | **REMOVED 2026-08-11** | `engine/softness.py` deleted; `engine/leagues.py` is the only league-eligibility home. No `SOFTNESS_PAUSED`/tier logic remains anywhere |
| **Market gate (ID405)** | **OPEN; scope overridden 2026-08-11** | `engine/markets.py` `BLOCKED = {}` — all markets deployable. **Away wins may now be RECOMMENDED** (Architect directive: "ID four zero five should be ignored. All markets remains open.") — recommendation-layer exclusions removed; the honest historical note (away measured negative) stays; `blocked()` backstop keeps any future gate one-key away |
| **Same-day product bet (2026-08-10)** | Active | THE CALL, produced bet, accas, singles draw ONLY from fixtures kicking off today; the 3-day window stays the scan reference |
| **Multi-market EDGE selection (2026-08-11)** | Active | Every fixture evaluates ALL 12 model-scorable markets (1X2, O/U1.5, O/U2.5, BTTS Yes/No, Double Chance 1X/X2/12) and books its OWN single best market by **EDGE** (EV = model_prob × price − 1, not raw probability); Acca A sorts `(ev, prob, fixture)` desc; O1.5/BTTS/DC prices come from the api-football parser (same request, zero extra quota) |
| **SportyBet booking codes** | Active (best-effort) | `booking/booking_codes.py` — Playwright captures booking codes per acca; codes pre-fill the slip, NEVER stake (Phase-2 safe); per-leg BOOKED/MANUAL |
| **Team-name mapping (OLP ↔ SportyBet)** | Green 2026-08-11 | `booking/team_map.py` — reverse resolver (`resolve_team_to_model`) is EXACT + normalized-exact ONLY, NO fuzzy (HR35). Fixed wrong-club corruption (Millwall→AC Milan, Club Brugge→Cercle, Excelsior→Sparta). 33-check regression suite passes |
| **CLV logging + CL-LIVE capture** | Active | Paper legs logged, closing lines captured near kickoff |
| **Health monitor** | Active | 9 probes, 2-hourly Task Scheduler, state-change alerts only; self-heals stale live-season CSVs (NOT odds-fixture caches — re-pulling would spend the quota it protects) |
| **Web feed (single tier, 2026-08-12)** | Green | **The web IS the Telegram board** (one render, two outlets): `/dashboard/{date}` → raw `board_<date>.json` → `build_feed_payload()` → feed page. **Admin tier PAUSED** — `/admin*`, `/stats`, `/why`, `/api/admin/*`, `/api/trigger-board` removed → 404. Auto-feed = auto-publish (no publish step). Binance design tokens |
| **Feed audit (never silent)** | Green | `run_daily.py` writes `output/boards/telegram_<date>.txt` (byte-faithful feed body) + stamps `feed_audit.jsonl` (gate/override numbers) after writing the board |
| **Booking-codes erasure bug** | **FIXED 2026-08-12** | A booking-skip run no longer unlinks `acca_<date>_codes.json` (the M5LMFE capture destroyed by a MANUAL regen on 2026-08-11); the file is date-scoped and retained |
| **Telegram push** | Green | Daily board delivered at 07:00 via notify.py; 2026-08-11 run delivered |
| **Email copy channel** | Green | SMTP delivery, best-effort, never fails run (disabled in `.env` by default) |
| **Brain (SQLite persistence)** | Green | Model caching, prediction log, `/stats` queries |
| **Test suite** | Green | All suites passing incl. new `tests/team_map_reverse_test.py` |

---

## 🔴 BROKEN / NEEDS FIX (Current Sprint)

| # | Issue | Root Cause | Fix Status |
|---|-------|------------|------------|
| **1** | **Odds API quota spent** — paid primary key 1/500 remaining (hard floor 5) | The monthly quota is nearly exhausted | **MITIGATED 2026-08-11** — multi-key chain: paid `ODDS_API_KEY` (primary) → `ODDS_API_KEY_BACKUP` → `ODDS_API_KEY_TERTIARY` walked in order; api-football free fallback (now incl. O1.5/BTTS/DC prices, same request) serves the deploy leagues; entry prices honestly `NO DATA — PENDING` elsewhere (HR35, refuses to spend the month). Heals on the monthly reset or a pasted key |
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
| **Odds API reset / backup key** | Paid primary key at 1/500 kills price pulls for non-deploy leagues; CLV capture stalls; the honest `NO DATA — PENDING` gap widens. Paste a fresh key in `ODDS_API_KEY` (paid) / `ODDS_API_KEY_BACKUP` / `ODDS_API_KEY_TERTIARY` (free), or wait for the monthly reset | **High** — the live blocker |
| **Capital deployment (Phase 3)** | Real money is the Architect's decision alone — gate needs ≥30 legs with CLV, positive mean CLV, and V7 sign-off | **Architect's call** |

---

## 🎯 NEXT ACTIONS

**Sprint 2026-08-11 ✅ COMPLETE** — multi-key Odds API (paid primary + free backups), `ARCHITECT_SIGNOFF=1` + board published to client dashboard (live side-by-side with paper until CLV positive), SportyBet team-map reverse resolver (no-fuzzy, HR35) + 33-check regression suite, health monitor verified (exit code 2 is by design; env + Telegram-delivery issues GONE; quota reported honestly), **multi-market EDGE selection + ID405 scope override + paid-key primary** (go-live, RATIFICATIONS §1781). See `docs/OLP_XDV_MASTER_DOCUMENTATION_2026-08-11.md`.

**Sprint 2026-08-12 ✅ COMPLETE — single-tier feed web, admin paused** — the web IS the Telegram board (one render, two outlets, parity test pins every Telegram line on the page); admin tier hard-paused (`/admin*`, `/stats`, `/why`, `/api/admin/*`, `/api/trigger-board` → 404); auto-feed = auto-publish (`telegram_<date>.txt` byte-faithful feed + `feed_audit.jsonl` gate stamp); **booking-codes erasure bug fixed** (date-scoped codes file retained, never unlinked). All 10 web suites green.

Next up (in priority order):

1. **Monitor quota reset / paste backup key** — the live blocker. Once quota returns, run_daily refreshes the stale odds-fixture caches and price pulls resume.
2. **Watch CLV daily** — the live side-by-side run is the honest test: publish override stays until mean CLV turns positive; gate re-blocks automatically if `ARCHITECT_SIGNOFF` is unset.
3. **Model refit for away overconfidence** — model claims ~39% away, delivers ~30%; structural, needs refit before Phase 3.

---

*Last updated: 2026-08-12 — this file is the single status reference. Do not reconstruct from chat history. If it disagrees with the code, trust the code + RATIFICATIONS.md and fix this file.*
