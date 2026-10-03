# Architecture.md — The Pipeline End to End

> How OLP XDV actually works, verified against the code 2026-08-11. This is the
> SCAN → trigger production → publish flow, plus the CLV loop, the admin
> dashboard, and the Telegram/client output. Rule and constant references point
> to [[Rules.md]] and [[Protected Constants.md]].

---

## One-line model
A daily pipeline pulls results + odds, fits four engines (Dixon-Coles, Elo, xG,
bookmaker) into one consensus, builds a board, picks a **today-only** production
bet (Acca A + split accas + singles) priced on **SportyBet's own 1X2 line** with
**booking codes**, logs **paper legs with CLV**, and delivers to Telegram + a
two-tier web dashboard. It **never places a bet** — the Architect turns a
booking code into money.

## Trigger
- `run_daily.py` — the daily 22:00 pipeline (Task Scheduler task "OLP XDV Daily Board"). Also runnable manually / via `monitor/run_monitor.py`.
- `scripts/hourly-fixture-check.js` — **hourly fixture refresh** (Task Scheduler task "OLP XDV Hourly Fixture Check"). Runs every hour: checks for upcoming fixtures not yet kicked off; if no board for today, triggers full `run_daily.py`; if board exists, runs lightweight pipeline (agents 1-4) for odds/fixture refresh. See [[Loops.md]].
- `orchestrator.py` — coordinates the run stages (deprecated, replaced by `olp_xdv_pipeline.py`).

## Stage 1 — SCAN (data → probabilities)
| Step | Code | Notes |
|------|------|-------|
| Odds | `pipeline/odds.py` | **Multi-key Odds API** (personal key primary, backup key second — see [[Decisions Log.md]] 11 Aug); falls back to `data/api_football_odds.py` (api-football free, 5 deploy leagues) when quota is spent. Quota floors: 40 (prices), 5 (fixture capture, Architect-authorized). |
| Results | `data/football_data_source.py` | football-data.co.uk CSVs; live-season feeds heal stale snapshots |
| Fixtures | `data/thesportsdb_fixtures.py`, `data/fixtures_source.py`, `data/multi_source_concrete.py`, `data/espn_source.py` | TheSportsDB / ESPN / fixtures fallback incl. EVENTSDAY fallback (ID410) |
| xG | `data/xg_source.py` | xG engine input |
| Engines | `engine/dixon_coles.py`, `engine/elo.py`, `engine/cross_league.py`, `engine/xg_*.py` | Dixon-Coles (Poisson modal, ID414) + Elo (ID82) + cross-league blend + xG + bookmaker anchor |
| Consensus | `engine/consensus.py` | cross-engine vote (ID412), devigged implied probability as EV anchor (ID413) |
| League pool | `config/leagues.json` → `engine/league_registry.py` → `engine/leagues.py` | **61 leagues** (unified pool, HR34, `deploy_eligible=true` for all); `engine/leagues.py` `WHITELISTED_LEAGUES` is derived from registry; no tiers (ID402 removed). Authoritative file is `config/leagues.json`. |
| Verification | `verification/id403.py` | multi-factor source tiers; CONFLICT/NO-DATA never silently resolved (HR35) |

## Stage 2 — TRIGGER PRODUCTION (probabilities → a bet)
| Step | Code | Notes |
|------|------|-------|
| Shortlist | `engine/leagues.py` `build_deploy_shortlist()` | all whitelisted leagues, **same-day only** (HR35, 2026-08-10 rule) |
| Market selection | `engine/acca.py` `_best_deployable_leg()` | **per fixture, evaluate ALL markets** (1X2, O/U1.5, O/U2.5, BTTS, DC); pick the single best by highest **EDGE = model_prob × price − 1**, tiebreak prob (2026-08-11 directive) |
| MES | `engine/mes.py` | numerical trigger price = `1/model_prob` per leg (HR30) |
| Accas / product | `engine/acca.py`, `output/produce_bet.py`, `bets/produced_bet.py` | Production intent: Acca A = top 4–5 highest-confidence fixtures, each leg that fixture's own best market; remainder → split accas + singles; a fixture never appears in two bets; all same-day (HR48 kickoff-date guard) |
| Pricing | SportyBet 1X2 attrs (from `booking/` cache) preferred; Odds API / api-football fill O1.5/BTTS/DC | SportyBet is the book the Architect bets at |

## Stage 3 — PUBLISH
| Step | Code | Notes |
|------|------|-------|
| Gate | `webapp/schema.py` `check_client_publish_gate()` | ≥30 legs with CLV + positive mean CLV, **or** `ARCHITECT_SIGNOFF` override ([[Protected Constants.md]] items 1–3) |
| Publish | `webapp/schema.py` `write_published()` | trimmed client payload → `output/boards/published/board_<date>.json`; gate numbers + override stamped into `output/boards/published/publish_audit.jsonl` |
| Dashboard | `webapp/server.py` | two-tier: `/dashboard` (client view, honest-edge statement) + `/admin` (authed, full internals); `webapp/export.py`, `webapp/render.py`, `webapp/render_v2.py`, `webapp/produce.py`, `webapp/crests.py` |
| Telegram | `output/notify.py` (`send_telegram`), `output/telegram_commands.py`, `output/telegram_webhook.py` | daily board at 07:00; Telegram poller daemon |
| Booking codes | `booking/booking_codes.py` (read-only, never stakes), `booking/sportybet_fixtures.py` (Playwright SPA cache builder), `booking/bridge.py`, `booking/team_map.py` | SportyBet 1X2 price + booking code per acca/single; reverse team resolver is exact-only (HR35) |
| Email copy | `output/email_deliver.py` | best-effort, never fails a run (ID407) |

## CLV / calibration loop
| Step | Code |
|------|------|
| Log paper legs at entry | `clv/clv_logger.py` (entry price CL-LIVE; 90-min grading, HR15) |
| Capture closing lines near kickoff | `clv/closing_capture.py` (HR48 date guard) |
| Statistical gate | `clv/phase3_gate.py` (HR51; 12/30 legs, mean −1.631% as of 2026-08-11) |
| Recalibration shadow + backtest | `engine/recalibration.py`, `backtest/` (ID407 shadow mode) |

## Monitoring / ops
| Piece | Code |
|-------|------|
| Health monitor | `monitor/health_monitor.py` — 9 probes, self-healing live CSVs, state-change Telegram alerts, exit 0/2 (2 = issues exist, **by design**) |
| Run watchdog | `monitor/run_watchdog.py` (ID408) |
| Data quality | `monitor/data_quality.py` — whitelisted leagues have fresh duplicate-free feeds |
| Cup training / dead-man's switch | `monitor/cup_training.py`, `monitor/dead_mans_switch.py` |

## Storage
- **Brain** — `brain/store.py` SQLite: model state, prediction log, `/stats` queries (schema v8 as of 2026-08-11; softness columns dropped v7/v8).
- **Output** — `output/boards/` (daily boards, published + audit), `output/boards/acca_<date>_codes.json`.
- **Caches** — `data/cache/` (football_data CSVs, fixtures_from_odds `*_0d.json`, sportybet fixtures).
- **Logs** — `logs/` (`daily_*.log`, `health_monitor.log`, `health_state.json`, `web_server.log`).

---

## ⚠ Standing risks (honest, 2026-08-11)
- **Odds API quota = 1/500** on the primary key → prices are NO DATA — PENDING for non-deploy leagues; api-football covers the 5 deploy leagues. Monthly reset or a pasted backup key heals it.
- **Statistical CLV gate not met** (12/30, −1.631%) — publication runs on the Architect override. See [[Protected Constants.md]].
- **Conference League** is whitelisted but football-data.co.uk does NOT carry it; current-season fixtures need a verified TheSportsDB id / ESPN slug (HR35, nothing guessed).

Back to [[OLP XDV.md]].
