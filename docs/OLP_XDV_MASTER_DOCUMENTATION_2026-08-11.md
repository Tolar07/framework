# OLP XDV — MASTER DOCUMENTATION

> **Date:** 2026-08-12 · **Repo:** `olp_xdv_agent/olp_xdv` · **Branch:** `elo-persistence`
> **Purpose:** Single reference for anyone — human or AI — who needs to understand the framework as it is **actually built today**, including every place where the docs disagree with the code. Where the written docs and the code conflict, this document says so and treats **the code + `RATIFICATIONS.md`** as the authority (RATIFICATIONS is append-only per HR33).
> **Honesty rule (HR35) applies to this document too:** nothing here is invented to fill a gap; where something is unknown it is marked as such.

---

## 0. ONE-PARAGRAPH SUMMARY

OLP XDV is a **Phase-3 live** football-betting calibration framework — the capital block was lifted by **Architect order 2026-08-11** (`config.PHASE` 2→3, commit `62ba6b9`). A daily 07:00 pipeline (`run_daily.py`) scans **19 whitelisted leagues** (one unified pool — softness tiers were removed on 2026-08-10; UEFA Super Cup added 2026-08-12), fits **Dixon-Coles + Elo + xG + Bookmaker** models into one consensus, builds a board, logs **paper legs with closing-line value (CLV)**, produces a **today-only** production bet (Acca A + split accas + singles) where each fixture picks its own single best market across the **full universe** — 1X2, O/U1.5, O/U2.5, BTTS, Double Chance — by **EDGE** (EV = model_prob × price − 1, ratified 2026-08-11; away wins may now be recommended, ID405 scope overridden), priced on **SportyBet's own 1X2 line** + api-football multi-market prices (wired 2026-08-11 so the acca builds even when the Odds API quota is exhausted) with **SportyBet booking codes**, and delivers to **Telegram** and a **single-tier feed web** — the web **IS** the Telegram board (one render, two outlets; the admin tier was paused 2026-08-12 and its routes removed → 404). Auto-feed = auto-publish: the daily run's production feeds the web directly. It has **never staked a kobo** and still never places a bet — capital authority stays with the Architect, who turns a booking code into money. The statistical Phase-3 gate (≥30 legs with CLV AND positive mean CLV AND Architect sign-off) is **not met**: **12/30 legs with CLV, mean CLV −1.631% (negative)** — the system is currently *losing* to the closing line and has **no demonstrated edge**. The go-live is an explicit **Architect override** of that gate: on **2026-08-11 the Architect set `ARCHITECT_SIGNOFF=1`** and the current board is **published live to the client dashboard**, running **side-by-side with paper** until mean CLV turns positive — an override that is never silent: the live gate numbers + override flag are stamped into `publish_audit.jsonl` and the honest-edge statement stays on the client view.

---

## 1. EVERY RULE AS CODED

### 1.1 HR rules (hard requirements — `HR###`)

| Rule | Name / meaning | Status | Where it lives |
|------|----------------|--------|----------------|
| **HR15** | **90-minute basis** — results settle on full-time (90-min) score, not extra time / penalties | **Active** | `clv/clv_logger.py`, grading |
| **HR30** | **Numerical MES required** — every capital pick carries a numerical Market Edge Score; MES = breakeven trigger price = `1/model_prob` (optional edge buffer). No live price → explicit exception note, never a silent blank | **Active** | `engine/mes.py` |
| **HR33** | **RATIFICATIONS append-only** — the ratification log is never rewritten | **Active** | `RATIFICATIONS.md` |
| **HR34** | **Unratified leagues never scan- or deploy-eligible** — only `WHITELISTED_LEAGUES` counts; whitelist changes are Architect-only | **Active** | `engine/leagues.py` (`is_deploy_eligible`) |
| **HR35** | **No fabrication** — missing data renders `NO DATA — PENDING` everywhere; a gate never matches display text (canonical keys instead); CONFLICT/NO-DATA never silently resolved | **Active (36 refs — the most-cited rule)** | Everywhere |
| **HR44** | **Ratify at time of change** — each RATIFICATIONS entry is written when the change happens | **Active** | `RATIFICATIONS.md` |
| **HR46** | **CLV logging** — paper legs carry entry price (CL-LIVE) + closing line (CL-ARCHIVE) | **Active** | `clv/clv_logger.py`, `clv/closing_capture.py` |
| **HR48** | **Kickoff-date guard** — a leg with no recorded kickoff date is refused; a no-date fixture is NEVER assumed to be today | **Active** | `bets/produced_bet.py`, `clv/closing_capture.py` |
| **HR51** | **Capital phase** — Phase 2 = paper only, zero capital; Phase 3 (live capital) gated on ≥30 legs with CLV + positive mean CLV + Architect V7 sign-off; `assert_paper_only()` is a hard fail, not a warning | **Active (Phase 2)** | `config.py`, `clv/phase3_gate.py` |
| **HR52** | **Pro-rigor auto-ratification** for changes that add real data sources without weakening existing checks | **Active** | `RATIFICATIONS.md` |
| **HR53** | **Full-detail-but-honest / plain-language mandate** — board uses full club names, markets in words; completeness never overrides honesty | **Active** | `output/produce_bet.py`, `engine/markets.py` (`display()`) |

### 1.2 ID rules (design IDs / ratified components — `ID###`)

| ID | Name / meaning | Status | Where it lives |
|----|----------------|--------|----------------|
| **ID82** | **Elo rating engine** — built from the same match data as Dixon-Coles; shown beside DC | **Active** | `engine/elo.py` |
| **ID401** | **League whitelist = unified pool** — 25 leagues (incl. Conference League added 2026-08-10, UEFA Super Cup added 2026-08-12). Every whitelisted league is scan- AND deploy-eligible | **Active** | `engine/leagues.py` `WHITELISTED_LEAGUES` |
| **ID402** | **Softness tiers** (A/B/C/D ranking, deploy cap, scan-only class) | **FULLY REMOVED 2026-08-11** — no tier logic remains anywhere: `engine/softness.py` deleted, `engine/leagues.py` is the only league-eligibility home (unified pool). No `softness_tier()` function, no `SOFTNESS_TIER`/`SOFTNESS_PAUSED`/`DEPLOY_POOL_CAP` constants, no tier column in live schemas (migrations v7/v8 drop it). Nothing left that could silently re-enable tiers | `engine/leagues.py` |
| **ID403** | **Multi-factor verification tiers** — VERIFIED / SINGLE-SOURCE / CONFLICT / NO-DATA / DERIVED; CONFLICT & NO-DATA never silently resolved | **Active** | `verification/id403.py` |
| **ID404** | **Source trust register** — ratified sources; trust tier sets corroboration requirement | **Active** | `RATIFICATIONS.md`, `data/` |
| **ID405** | **Market gate** — which markets may carry (paper) capital. **OPENED 2026-08-10:** `BLOCKED = {}`, all markets deployable. **Scope overridden 2026-08-11 (Architect directive):** away wins may now be **recommended**, not just shown — the recommendation-layer exclusions were removed (the honest historical note that away measured negative stays as context; the brain learns from live legs). The earlier block (Away −2% CLV, Home −0.6%, Over2.5 −0.7% backtest evidence) is *not* dismissed — forward observation decides whether markets re-close via `BLOCKED` | **OPEN — all markets deployable; away may be recommended** | `engine/markets.py` |
| **ID412** | **Cross-engine consensus vote** — majority across available engines, persisted to brain | **Active** | `engine/consensus.py` |
| **ID413** | **Devigged implied probability** — market's devigged 1X2 as the EV anchor | **Active** | `engine/markets.py` (`MARKETS_1X2`), `run_daily.py` |
| **ID414** | **Market-anchored display probability / true modal scoreline** — Poisson modal scoreline for display + EV | **Active** | `engine/dixon_coles.py`, `webapp/schema.py` |

### 1.3 Standing rules / recent Architect orders (not HR/ID-numbered)

| Rule | Status | Where recorded |
|------|--------|----------------|
| **Same-day product bet (2026-08-10, replaces the 3-day rolling window)** | **Active** — THE CALL, produced bet, accas, singles draw ONLY from fixtures kicking off today; the 3-day window stays the scan reference | `RATIFICATIONS.md` §1437 |
| **Production intent (2026-08-10; ranking 2026-08-11)** — Acca A = top 4–5 highest-EDGE fixtures, each leg the fixture's own single best market across the **full universe** (1X2, O/U1.5, O/U2.5, BTTS, Double Chance); no forced diversity; a fixture never appears in two bets; remainder → split accas (~4–5 legs) + singles, each with its own booking code | **Active** | `engine/acca.py`, `.claude/OLP_XDV_PRODUCTION_INTENT.md` |
| **Ranking by EDGE (2026-08-11, replaced 2026-08-10 probability ranking)** — legs ranked by EV = model_prob × price − 1 (where the book misprices the fixture in our favour — the signal that drives positive CLV; probability stays visible as information); tiebreak probability, then canonical market order | **Active** | `engine/acca.py` |
| **Architect publish override (2026-08-10)** — `ARCHITECT_SIGNOFF=1` bypasses the statistical client-publish gate; override is never silent (stamped in audit log + honest-edge statement stays on client view) | **Active** | `webapp/schema.py` |
| **Single-tier feed web (2026-08-12, replaces the two-tier dashboard of 2026-08-07)** — the web IS the Telegram board (one render, two outlets): `/dashboard/{date}` → raw `board_<date>.json` → `build_feed_payload()` → feed page. **Admin tier PAUSED** — `/admin*`, `/stats`, `/why`, `/api/admin/*`, `/api/trigger-board` removed → 404. Auto-feed = auto-publish; gate numbers shown honestly + stamped to `feed_audit.jsonl` (never silent) | **Active** | `webapp/server.py`, `webapp/schema.py` |
| **Binance design pass (2026-08-10)** — dashboard styling follows `design-md/binance/DESIGN.md` tokens in `proto.css` | **Active** | `webapp/` |

### 1.4 Where docs and code DISAGREE (verified 2026-08-11, docs updated same day)

`PROJECT_STATUS.md` and `ARCHITECTURE.md` were **rewritten to the ratified state on 2026-08-11**; the drift below is closed. Kept here for the historical record of what was wrong, with the corrected code-truth beside it.

| Claim in docs (was) | Doc | What the code actually does (now in the doc) |
|---------------|-----|-----------------------------|
| "ID405 market gate **ACTIVE** — Away/Over2.5/Home blocked from deploy" | `PROJECT_STATUS.md` (2026-08-09), `ARCHITECTURE.md` | Gate **OPEN** — `engine/markets.py` `BLOCKED = {}`; all markets deployable (ratified 2026-08-10); **away may be recommended (scope overridden 2026-08-11, Architect directive)**. **Fixed in docs 2026-08-11** |
| "Softness tiers active / `SOFTNESS_PAUSED=True` (reversible)" | `PROJECT_STATUS.md`, `ARCHITECTURE.md` | Softness **deleted** — `engine/softness.py` removed, `engine/leagues.py` is the new home; no `SOFTNESS_PAUSED` anywhere. **Fixed in docs 2026-08-11** |
| "17 leagues" | `ARCHITECTURE.md`, `RATIFICATIONS.md` (2026-08-10 §1584) | **18 leagues** — Conference League added 2026-08-10. **Fixed in docs 2026-08-11** |
| "3-day rolling window for product bet" | `ARCHITECTURE.md` | **Strict single-day** since 2026-08-10. **Fixed in docs 2026-08-11** |
| "Phase 3 gate 0/30" | `PROJECT_STATUS.md` | **12/30** legs with CLV (15 logged). **Fixed in docs 2026-08-11** |
| "4-leg acca set (up to 3 accas)" | `PROJECT_STATUS.md`, `ARCHITECTURE.md` | **Acca A + splits + singles** production shape (2026-08-10 production intent). **Fixed in docs 2026-08-11** |
| "TODAY'S PICKS parlay" | `ARCHITECTURE.md` | Retired; `recommendation=""` in web payload. **Fixed in docs 2026-08-11** |
| "THESPORTSDB_KEY empty" | `ARCHITECTURE.md` | **Set** in `.env` (personal key, len 10). **Fixed in docs 2026-08-11** |
| "Odds quota 3/500" | master doc first draft | **1/500** (paid primary key) as of 2026-08-11; multi-key chain — paid `ODDS_API_KEY` primary → `ODDS_API_KEY_BACKUP` → `ODDS_API_KEY_TERTIARY` — + api-football fallback (O1.5/BTTS/DC on the same request) for the deploy leagues. **Fixed in docs 2026-08-11** |
| Health monitor "last run errored (code 2)" | master doc first draft | Exit code **2 is by design** — the monitor exits 2 whenever ANY issue exists. Env + Telegram-delivery issues GONE 2026-08-11; quota honest (1 left). **Fixed in docs 2026-08-11** |
| "`ARCHITECT_SIGNOFF` unset" | master doc §4/§5, `ARCHITECTURE.md` | **SET = 1** (2026-08-11) — board published to client dashboard, live side-by-side with paper until CLV positive. **Fixed in docs 2026-08-11** |
| "THE CALL + acca draw only from Draw+Under2.5 (ID405)" | `PROJECT_STATUS.md` §18 | Market gate open — each fixture picks its OWN best market across the full EDGE universe (1X2, O/U1.5, O/U2.5, BTTS, DC), 2026-08-11. **Fixed in docs 2026-08-11** |

---

## 2. FULL ARCHITECTURE

### 2.1 The pipeline (SCAN → TRIGGER → PRODUCTION → PUBLISH)

```
            ┌────────────────────────────────────────────────────────────┐
            │  07:00 DAILY RUN — run_daily.py  (Task Scheduler, enabled)  │
            └────────────────────────────────────────────────────────────┘
 SCAN        grade yesterday → fixtures → odds → engine → verify → board → log → notify
            │
            ├─ data/  football-data.co.uk history (fit) + multi-source fixtures:
            │         TheSportsDB → odds-derived → API-Football → SportyBet cache
            │         (failover with circuit breakers; all 4 primary sources currently fail,
            │          so fixtures come from the SportyBet cache)
            │
 TRIGGER     ├─ Task Scheduler "OLP XDV Daily Board" — 07:00, enabled, last run OK
            └─ (admin trigger /api/trigger-board and /api/admin/produce were REMOVED
                with the admin tier 2026-08-12 → 404; the 07:00 run is the only producer)
            │
 PRODUCTION  ├─ orchestrator.run_all_leagues() — 18-league scan, ONE unified pool (ID401)
            │    → fit Dixon-Coles per league, Elo, xG (top-5 Understat), Bookmaker
            ├─ consensus (ID412) → verification (ID403) → deploy shortlist
            │    → produce_bet / THE CALL (today only) + accas (engine/acca.py)
            │    → booking codes (booking/booking_codes.py — Playwright, NEVER stakes)
            │    → log paper legs with entry price (CL-LIVE) — capital blocked (HR51)
            │
 PUBLISH     ├─ feed_text = telegram board + full-board URL (when set) — built ONCE
            ├─ write output/boards/telegram_<date>.txt (byte-faithful feed = the SAME body delivered)
            ├─ write board_<date>.json (raw, unchanged) + stamp feed_audit.jsonl (gate numbers, never silent)
            ├─ notify.deliver(push_text=feed_text) → Telegram
            └─ AUTO-FEED = AUTO-PUBLISH (2026-08-12): web reads the raw board directly via
               schema.read_feed() → build_feed_payload(); no publish step, no /admin
               (the publish gate arithmetic stays in check_client_publish_gate as the
                protected single source of truth — no web route invokes it)
```

### 2.2 Components (engine, storage, calibration, delivery)

| Component | Path | What it does |
|-----------|------|--------------|
| **Daily pipeline** | `run_daily.py` | Orchestrates the 07:00 run end-to-end (grade→fixtures→odds→engine→verify→board→log→notify). Phase-2 calibration instrument; capital hard-blocked |
| **Orchestrator** | `orchestrator.py` | `run_all_leagues()` scans all 19 whitelisted leagues into one board; `pull→fit→scan→board→log` per operating protocol (no stop-and-ask) |
| **League pool** | `engine/leagues.py` | `WHITELISTED_LEAGUES` (18) + `is_deploy_eligible()` (whitelist membership only) + `build_deploy_shortlist()` (honours `mkt.blocked()` as structural backstop) |
| **Dixon-Coles** | `engine/dixon_coles.py` | Per-league Poisson model fit + `predict_adjusted` + true modal scoreline (ID414) |
| **Elo** | `engine/elo.py` | ID82 Elo rating, same match data |
| **xG** | `data/xg_source.py` | Understat top-5 xG, treated like any other source (ID403) |
| **Bookmaker** | `engine/` (bookmaker), `engine/consensus.py` | Devigged implied probabilities (ID413); four independent opinions → majority vote (ID412) |
| **Consensus** | `engine/consensus.py` | Cross-engine vote persisted to brain |
| **Verification** | `verification/id403.py` | Multi-factor tiers (ID403) — VERIFIED/SINGLE-SOURCE/CONFLICT/NO-DATA/DERIVED |
| **Recalibration** | `engine/recalibration.py` | Platt-scaling style calibration, inert below minimum settled-leg counts |
| **Brain (SQLite)** | `brain/store.py` | Persistent memory: model fits, predictions, legs mirror, runs, corrections |
| **Stats renderer** | `brain/report.py` | Plain-language `/stats` for non-technical Architect |
| **CLV logger** | `clv/clv_logger.py` | Canonical JSON ledger; `phase2_status()` evaluates the gate; `grade_all_pending()` |
| **Closing capture** | `clv/closing_capture.py` | Captures closing lines near kickoff (CL-ARCHIVE); HR48 date guards |
| **Phase 3 gate** | `clv/phase3_gate.py` | Separate Architect sign-off record for capital deployment |
| **Produces/verify** | `output/produce_bet.py` | Plain-language THE CALL / produced bet / verify-results rendering (HR53) |
| **Telegram** | `output/telegram_commands.py` | Long-polling daemon: `/send /produce /verify /stats /board /why` |
| **Notifiers** | `output/notify.py`, `whatsapp_deliver.py`, `email_deliver.py` | Delivery; email skipped when `EMAIL_*` unset |
| **Booking codes** | `booking/booking_codes.py` | Playwright drives SportyBet SPA, captures booking codes per acca; READ-ONLY — never stakes, never clicks "Place Bet" |
| **Booking bridge/odds** | `booking/bridge.py` | SportyBet odds read for leg pricing |
| **Team-name mapping** | `booking/team_map.py` | OLP XDV ↔ SportyBet names. Forward `resolve_team()` (fuzzy ok) + REVERSE `resolve_team_to_model()` — reverse is EXACT + normalized-exact ONLY, NO fuzzy (HR35: a wrong-club map attaches a real price to the wrong team, worse than an honest gap). Reverse table `_MODEL_BY_SPORTYBET` built first-wins so canonical keys win collisions |
| **Web feed (single tier)** | `webapp/server.py` | The web IS the Telegram board (2026-08-12): `/dashboard/{date}` → raw board → `build_feed_payload()` → `render_v2.render_dashboard()`. `/api/board.json` + `/api/board/{date}` feed payloads; `/api/analyst` scoped to the feed. `/history`, `/metrics`, `/health`, `/static`, `/api/live-scores` public. **Admin tier removed** — `/admin*`, `/stats`, `/why`, `/api/admin/*`, `/api/trigger-board` → 404 |
| **Schema** | `webapp/schema.py` | Board JSON contract; `trim_payload()`; `build_feed_payload()` (trim + honest gate/edge fields); `read_feed()`; `stamp_feed_audit()`; protected `check_client_publish_gate()` + `write_published()` retained (no web route calls them — the gate stays as the single source of truth) |
| **Produce preview** | `webapp/produce.py` | Real-time fixture prediction production (preview only, no ledger writes) |
| **Health monitor** | `health_monitor.py` | Hourly probes, state-change alerts; exit code 2 = issues exist (BY DESIGN); env + Telegram-delivery issues GONE 2026-08-11, quota honest (1 left) |
| **Agent CLI** | `agent_cli.py` | Read-only query surface for AI agents (brain + ledger + coverage) |

### 2.3 What changed when softness was cancelled (2026-08-10)

- **Before:** `engine/softness.py` carried `SOFTNESS_TIER`, `SOFTNESS_PAUSED`, `DEPLOY_ELIGIBLE_TIERS`, `DEPLOY_POOL_CAP`, `_tier_words()`; leagues ranked A/B/C/D; deploy shortlist came only from eligible tiers; board rendered tier labels; accas drew only from capital-cleared tiers.
- **After (2026-08-11, fully removed):** `engine/softness.py` is **deleted**; `engine/leagues.py` holds `WHITELISTED_LEAGUES` (18) + `is_deploy_eligible()` (whitelist membership only). No `softness_tier()` function or back-compat slot remains — the column is dropped from live schemas by migrations v7/v8. `on_deploy_shortlist` = whitelisted + rated + verification not CONFLICT/NO-DATA. Board renders one unified deploy pool with no tier labels. **Deploy eligibility is now: on the whitelist, or it does not deploy.**

### 2.4 Calibration / CLV logging

- Paper legs logged each daily run for rated, whitelisted, priced fixtures on a deployable market (all markets now).
- Entry price stamped `CL-LIVE` (the price used at decision time); closing line captured near kickoff and stamped `CL-ARCHIVE`; `clv_pct` computed; `grade_all_pending()` settles against the 90-minute result (HR15) when it appears.
- Ledger (`clv/clv_log.json`) and brain legs mirror both carry the record; `phase2_status()` (in `clv_logger.py`) is the gate evaluator the board JSON embeds.

---

## 3. EVERY AGENT IN THE SYSTEM

| Agent | What it is | Authorized to do | Explicitly barred from |
|-------|-----------|------------------|------------------------|
| **Claude Code — session A/B** (this repo) | The interactive coding agent; two sessions share the working tree, git is the only sync | Edit code, run tests, inspect state, update docs, commit | *Nothing on its own authority:* all changes go through the safe-move protocol + Architect review |
| **Telegram poller daemon** | `output/telegram_commands.py --loop`, PID active | Answer `/send /produce /verify /stats /board /why` on the live Telegram chat; deliver the daily board | Cannot publish to clients (publish is admin-web only), cannot stake (Phase 2) |
| **AI Analyst** (web dashboard `/api/analyst`) | Claude 3.5 Sonnet (Anthropic) chat endpoint | Answer questions about the board given a trimmed view | **Offline today** — `ANTHROPIC_API_KEY` not set; also rate-limited 10 req/min |
| **Task Scheduler jobs** | "OLP XDV Daily Board" (07:00, enabled, last OK) + "OLP XDV Health Monitor" (hourly, last run errored code 2) | Run the daily pipeline / health probes unattended | Anything beyond their defined batch; capital never touched |
| **agent_cli.py** | Read-only query surface | Let another AI agent query brain/ledger/coverage | No writes, no stake, no publish |
| **sports-skills + everything-claude-code plugins** | `.claude/skills`, `.claude/agents` (7 subagents installed) | Assistive tooling for Claude Code sessions | Nothing autonomous |
| **Gemini / DeepSeek** | — | — | **Do not exist in this repo.** Verified: no integration, no keys, no code. The PROMPT2 "every agent" list is fully covered by the above |

---

## 4. REPO STRUCTURE (plain language)

```
olp_xdv/
├── run_daily.py           07:00 daily pipeline (SCAN→…→notify)
├── orchestrator.py        18-league scan → one board
├── config.py              PHASE, capital bright line (assert_paper_only), dotenv loader
├── agent_cli.py           read-only AI-query surface
├── league_audit.py        league coverage audit (fit/fixtures/odds/names verdict)
├── health_monitor.py      hourly health probes
├── engine/                Dixon-Coles, Elo, consensus, markets, mes, recalibration,
│                          acca builder, leagues (whitelist, was softness)
├── data/                  football-data history, TheSportsDB/API-Football fixtures,
│                          xG (Understat), multi-source failover, competition catalogue
├── clv/                   clv_logger (ledger + gate eval), closing_capture, phase3_gate
├── brain/                 SQLite store + plain-language /stats
├── output/                produce_bet (renders), notify/whatsapp/email, telegram_commands
├── booking/               sportybet_client, fixtures, bridge, booking_codes (Playwright)
├── webapp/                server.py (single-tier feed web), schema.py (gate+trim+feed+audit), produce.py,
│                          render*.py, static/ (Binance-design proto.css), design_reference/
├── verification/          id403 multi-factor tiers
├── backtest/              CLV backtest, out-of-sample calibration layer
├── monitor/               cup_training, data_quality
├── tests/                 40+ test files (engine, webapp, CLV, stress, quota, …)
├── docs/                  OLP_XDV_COMPILED_REFERENCE.md, LEAGUE_INTELLIGENCE_DOSSIER.md,
│                          LEAGUE_DATA_COVERAGE.md, THIS file
├── RATIFICATIONS.md       append-only rule log (authority after the code)
├── ARCHITECTURE.md / PROJECT_STATUS.md   overview docs — updated to ratified state 2026-08-11 (was stale; §1.4)
├── CLAUDE.md              two-session working protocol (safe move)
└── .env                   credentials (ADMIN_*, ODDS_API_KEY [paid, primary] + ODDS_API_KEY_BACKUP + ODDS_API_KEY_TERTIARY, THESPORTSDB_KEY,
                           API_FOOTBALL_KEY, TELEGRAM_*, WHATSAPP_ENABLED, OLP_REQUIRE_ADMIN_AUTH,
                           ARCHITECT_SIGNOFF=1)
```

---

## 5. WHERE THINGS STAND RIGHT NOW (2026-08-11)

### 5.1 The gate

| Metric | Value | Needed | Verdict |
|--------|-------|--------|---------|
| Phase 2 paper legs logged | **15** | — | — |
| Legs with logged CLV | **12** | **≥ 30** | ❌ NOT met (18 short) |
| Mean CLV | **−1.631%** | **> 0** | ❌ NOT met (currently losing to the closing line) |
| `gate_met` | **false** | true | ❌ |
| `ARCHITECT_SIGNOFF` env | **SET = 1** (2026-08-11) | `=1` to publish/override | ✅ override active |
| Projected days-to-gate (if mean were positive) | 7.2 | — | irrelevant — mean is negative |

**Consequence:** the statistical gate is NOT met, but the **Architect override (`ARCHITECT_SIGNOFF=1`) is live** (2026-08-11 decision): the current board is **published live**, running side-by-side with paper until mean CLV turns positive. Since 2026-08-12 this is **auto-feed = auto-publish** — the daily run writes the board and the web reads it directly (no approve→publish route; the admin tier is paused). The override is never silent — the run stamps the live gate numbers + `override: true` into `feed_audit.jsonl`, the gate callout on the page shows OVERRIDE, and the honest-edge statement stays on the page ("Phase 2 — paper calibration, 12/30 legs logged. Not yet a demonstrated edge."). If the Architect unsets the flag, the gate re-blocks automatically.

### 5.2 Paper-leg record (all 15)

- **12 settled** with closing line: **3 won / 9 lost** (25% hit rate) — that's why mean CLV is negative.
- **3 stuck pending** (Danish Superliga, closing line never captured): Sonderjyske v Viborg (1X2_HOME, 1X2_DRAW), Randers FC v Lyngby (UNDER_2_5) — they will **never count** toward the 30 unless a closing line appears.
- Per-market: 1X2_DRAW −2.367% (5 legs), 1X2_HOME −0.863% (3), UNDER_2_5 −1.288% (4). **Zero Away and zero Over2.5 legs** have been logged since the gate opened.
- All 15 are Eredivisie / Danish Superliga / Scottish Premiership — no leg from the other 15 whitelisted leagues yet.

### 5.3 Scan vs eligible vs blocked today

- **25 leagues** scanned by the 07:00 run (board 2026-08-11 + UEFA Super Cup added 2026-08-12): 16 coverage-READY, **2 BLOCKED (no working history source)** — Conference League + EFL Cup.
- Board 08-11: **13 fixtures, 4 rated, 4 on deploy shortlist**; produced bet has **4 legs** (Lyon win, St. Gilloise win, Olympiakos win, Fenerbahçe win) — published to the client dashboard under the override.
- Board 08-12 (already generated): **0 fixtures** — nothing rated for tomorrow.
- **Team-name mismatches FIXED 2026-08-11** — the SportyBet cache builder was calling the forward resolver backwards, so model_home/model_away held SportyBet spellings and the fuzzy matcher attached real prices to WRONG clubs ("Millwall FC"→AC Milan, "Club Brugge"→Cercle Brugge, "Excelsior Rotterdam"→Sparta Rotterdam). New `resolve_team_to_model()` (reverse table, EXACT + normalized-exact only, NO fuzzy — HR35) fixes the direction; `tests/team_map_reverse_test.py` (33 checks) pins it.
- **Remaining board flags** dominated by the **Odds API quota (1/500, floor 5)** on non-deploy leagues — entry prices are honestly `NO DATA — PENDING` (HR35); api-football serves the 5 deploy leagues meanwhile.

### 5.4 The two structural reasons the gate is stuck

1. **Odds API quota is spent (1/500, hard floor 5)** — the paid primary key is at its monthly cap. **Multi-key chain 2026-08-11** (`pipeline/odds.py`): `_resolve_key()` walks the paid `ODDS_API_KEY` (primary) → `ODDS_API_KEY_BACKUP` → `ODDS_API_KEY_TERTIARY`, using whichever has quota above the floor; if all are spent, the api-football free fallback (100 req/day, today±1) prices the deploy leagues — now including the multi-market prices (O1.5, BTTS, Double Chance) parsed from the SAME request, zero extra quota — and every other league honestly reports `NO DATA — PENDING` (HR35) rather than fabricating prices. Heals on the monthly reset or a pasted backup key.
2. **Mean CLV is negative** — even if legs reached 30, `mean_clv > 0` fails. The system must *demonstrate* it beats the closing line, not just log volume. 9 of 12 settled legs currently lose to the closing line. This is exactly what the live side-by-side publish (Architect override) is now measuring forward.

### 5.5 Open findings / open questions

1. ~~ID405 scope question~~ **OVERRIDDEN 2026-08-11** (Architect directive, named — RATIFICATIONS §1781): away wins may now be **recommended**, not just shown; the recommendation-layer exclusions were removed. The negative-CLV evidence that once blocked Away/Home/Over2.5 (−2%, −0.6%, −0.7%) is *not* dismissed — whether those markets re-close is now answered by **forward live observation** (the side-by-side publish IS the test; the brain learns from live legs). Calibration-log league scope remains unchanged.
2. **Calibration-league-scope question** (raised after softness cancellation): calibration evidence was historically Eredivisie/Danish/Scottish-only; the unified pool now deploys across 18 leagues without per-league forward evidence. Cross-league fit (`engine/cross_league.py`) mitigates, but the 15-leg record is 3-league-only.
3. **Conference League + EFL Cup** are whitelisted but have no working history source → scan to NO DATA; Conference League also has no verified Odds API sport key → can never price even when quota resets.
4. **3 stale pending legs** — Danish Superliga closing lines never captured; won't count without a close.
5. ~~Health monitor errored (result code 2)~~ **CLOSED 2026-08-11** — exit code 2 is BY DESIGN (`sys.exit(0 if all(r.is_fine()...) else 2)`); it is the honest signal that issues exist. Verified: env (missing THESPORTSDB_KEY) and last_run (not delivered to Telegram) issues are GONE; quota reports honestly (1 left); the two remaining flags (quota, stale odds-fixture caches) are the accepted quota blocker + a deliberately-un-healed cache (re-pull spends quota).
6. **AI Analyst offline** — `ANTHROPIC_API_KEY` not set.
7. ~~Docs drift~~ **CLOSED 2026-08-11** — `PROJECT_STATUS.md` + `ARCHITECTURE.md` rewritten to the ratified state (see §1.4).
8. **3 boards published** (2026-08-07, 2026-08-10, 2026-08-11) — the 2026-08-11 publish is the first under the Architect override, running live side-by-side with paper until mean CLV turns positive.

---

## Changelog

- **2026-08-12 — single-tier feed web; admin tier paused; codes-erasure bug fixed.** (1) **The web IS the Telegram board** (one render, two outlets): `run_daily.py` builds `feed_text` once → persists `output/boards/telegram_<date>.txt` (byte-faithful — the same body `notify.deliver` sends) → stamps `feed_audit.jsonl` (gate/override numbers, never silent). The web reads the raw `board_<date>.json` via `schema.read_feed()` → `build_feed_payload()` (trim + honest gate/edge fields only — no Elo/xG/consensus/EV/verification internals) → `render_v2.render_dashboard()` feed page (hero, flags, gate callout PASS/OVERRIDE/NOT MET, PRODUCTION BETS block = Acca A hero → split accas → singles each with its own booking code, lean scan, yesterday-graded, 7-day rolling, honest-edge line) on the Binance tokens. **Admin tier PAUSED** — `/admin*`, `/stats`, `/why`, `/api/admin/*`, `/api/trigger-board` removed → 404 (not 401/503). Auto-feed = auto-publish: no publish step; `check_client_publish_gate()`/`write_published()` remain as protected constants (the gate stays the single source of truth, but no web route invokes it). (2) **Booking-codes erasure bug FIXED**: the no-booking-codes branch no longer unlinks `acca_<date>_codes.json` — a date-scoped capture (e.g. M5LMFE, destroyed 2026-08-11 by a MANUAL regen) is retained. (3) **Parity pinned by `tests/webapp_feed_parity_test.py`** — one `ProductionBets` rendered to both Telegram text (`engine.acca.render_production_block`) and the web page; every substantive Telegram line (incl. the ` — ` separator and each booking code) is asserted as a substring of the page text. All 10 web suites green (`webapp_schema`, `webapp_run_daily`, `webapp_render_v2`, `webapp_feed_parity`, `webapp_server`, `webapp_export`, `webapp_render`, `integration`, `booking_codes`, `engine_regression`). Legacy `render.py` keeps only `render_dashboard` (legacy client) + history/404; admin renderers deleted. `/api/analyst` scoped to the feed payload (no internals).
- **2026-08-11 — softness/tiering fully removed (not just cancelled).** The 2026-08-10 cancellation is now a deletion: `engine/softness.py` removed from the tree; `engine/leagues.py` (unified pool, 25 leagues) is the single league-eligibility home; the stale `tests/softness_mes_test.py` (which imported the deleted module and broke pytest collection) is superseded by `tests/leagues_test.py` and removed; the mypy gate now checks `engine/leagues.py`. No `softness_tier` / `SOFTNESS_PAUSED` / `DEPLOY_POOL_CAP` code, function, constant, or live schema column remains.
- **2026-08-11 (afternoon) — live-state hardening.** (1) **Multi-key Odds API**: `pipeline/odds.py` `_resolve_key()` walks the paid `ODDS_API_KEY` (primary) → `ODDS_API_KEY_BACKUP` → `ODDS_API_KEY_TERTIARY`; api-football free fallback prices the deploy leagues when all are spent; otherwise honest `NO DATA — PENDING` (HR35). (2) **Architect override live**: `ARCHITECT_SIGNOFF=1`, board 2026-08-11 published to the client dashboard (running side-by-side with paper until mean CLV turns positive); `write_published()` stamps the live gate numbers + `override: true` into `publish_audit.jsonl`. (3) **SportyBet team-map reverse resolver**: `booking/team_map.py` + `sportybet_fixtures.py` fixed the backwards-resolver bug that attached real prices to wrong clubs; reverse lookup is exact-only (no fuzzy), regression-pinned by `tests/team_map_reverse_test.py` (33 checks). (4) **Docs brought to the ratified state**: `PROJECT_STATUS.md` + `ARCHITECTURE.md` rewritten (§1.4 drift closed). (5) **Health monitor verified**: exit code 2 is by design; env + Telegram-delivery issues gone; quota honest (1 left).
- **2026-08-11 (evening) — go-live: multi-market EDGE selection + ID405 scope override + paid-key primary (commit `e8fbf64`, RATIFICATIONS §1781).** (1) **ID405 scope overridden** (Architect, named: "ID four zero five should be ignored. All markets remains open.") — away wins may now be RECOMMENDED, not just shown; recommendation-layer exclusions removed across produce_bet/produced_bet/accumulator_prep/webapp; the honest historical note (away measured negative) stays; `blocked()` backstop remains. (2) **Multi-market EDGE selection** — every fixture evaluates ALL 12 model-scorable markets (1X2, O/U1.5, O/U2.5, BTTS Yes/No, Double Chance 1X/X2/12) and books its OWN single best market by EV = model_prob × price − 1 (not raw probability); Acca A sorts `(ev, prob, fixture)` desc. (3) **Price universe widened** — `FixtureOdds` gains over15/under15/btts_yes/btts_no/dc_1x/dc_x2/dc_12; the api-football parser reads O1.5/BTTS/DC from the SAME payload (zero extra requests); HR35 holds (absent market = no price = honest scan-only). (4) **Paid Odds API key = primary**; free keys demoted to `ODDS_API_KEY_BACKUP` / new `ODDS_API_KEY_TERTIARY`. (5) **Booking codes reach the phone** — `cmd_produce("bet")` passes `booking_codes=True` so the produce reply carries codes (or honest MANUAL). Tests: new `tests/multi_market_edge_test.py` (13 checks); full suite 60 green + 2 known flakes green isolated. Honest constraint recorded: Odds API archive only closes 1X2 + O/U2.5, so BTTS/DC/O1.5 legs may have entry price but NO closing line → CLV NO DATA at first (brain still learns hit/miss).
- **2026-08-11 (night) — produced-bet record `pick_market` KeyError fixed (commit `4cd8aae`).** `_leg_from_board` wrote `pick` (1X2 result) and `best_market` but never the schema-v6 `pick_market` column, so `brain.sync_produced_bets` raised `KeyError('pick_market')` on every run with a rated fixture today — the `produced_<date>.json` was written but the brain mirror silently never synced. Regression present since ID415 (commit `0793283`), surfaced as "⚠ produced-bet record failed ('pick_market')" on the 08-09/08-11 boards. Fix: the leg now carries `pick_market` = the fixture's best EV market key (`best_market_key`, the multi-market EDGE selection result), falling back to the 1X2 result pick when unpriced; `store.py` falls back to `pick` for legacy rows (NOT NULL column, never NULL). New `tests/produced_bet_record_test.py` (6 checks) pins the record + mirror path and legacy sync. Full suite 60 green + the 2 env-bound odds suites (pass with `.env`) + the known stress2 warm-reuse flake.

*End of master documentation. Generated 2026-08-11 by Claude Code; updated 2026-08-12 with the single-tier feed web (admin paused, auto-feed = auto-publish), the codes-erasure fix, and the feed audit.*
