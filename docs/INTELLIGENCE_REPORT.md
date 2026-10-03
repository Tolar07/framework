# OLP XDV — INTELLIGENCE & INTEGRATION REPORT
**Generated:** 2026-08-12 · **Scope:** prediction-site data sourcing, framework pipeline, cloned repos, sports-skills, blood-product relationships, automation prompts.

---

## PART 1 — How Production Prediction Sites Source Their Data

### 1.1 The shared architecture every major site uses

PredictZ, Forebet, SoccerVista, Windrawwin, BetExplorer (and StatoSoso, Tips.GG, etc.) all run the **same 4-layer stack**:

| Layer | What it does | Typical source | Who does it |
|---|---|---|---|
| **L1 — Fixture feed** | "What matches exist in the next 3–14 days?" | TheSportsDB, API-Football, ESPN, paid XML sports feeds (SportsDT, Sportradar, Feedconstruct) | All |
| **L2 — Historical results** | "What happened in past seasons?" (for form/lookup tables) | football-data.co.uk CSVs, API-Football, Footystats, ClubElo | All |
| **L3 — Odds feed** | "What is the market price?" (for value flags) | The Odds API, Betfair/Exchange, bookmaker affiliate APIs, SportyBet/Bet365 scraping | BetExplorer, Windrawwin, Forebet (odds tabs) |
| **L4 — Model/editorial** | "What do we predict + why?" | In-house (Poisson/Dixon-Coles/Elo) OR paid model API OR human tipsters | PredictZ (editorial+model), Forebet (algorithmic), SoccerVista (form-based) |

**Key insight — they are NOT all doing their own modelling.** Most are one of three archetypes:

- **Archetype A (Aggregator):** BetExplorer, Windrawwin — they mostly *re-publish* bookmaker odds + historical H2H/results. Minimal proprietary modelling. Their "edge" is presentation (filters, value flags vs market).
- **Archetype B (Algorithmic):** Forebet — runs its own Poisson-style expected-goals + form model, publishes probabilities and a 1X2 pick. Pulls fixtures/results from open feeds, odds for "value vs market" comparison.
- **Archetype C (Editorial + Light Model):** PredictZ, SoccerVista — human-curated predictions backed by simple form/table statistics; odds/results from affiliate feeds.

### 1.2 Specific sourcing patterns (from public observation + the open-source clones we hold)

- **PredictZ:** Fixtures + results from a licensed feed (historically Football-Data.co.uk-family + bespoke scraping); predictions are editorial with a statistical form layer. Bookmaker odds shown via affiliate (Bet365) embeds.
- **Forebet:** Self-built Poisson/EG model; fixtures/results scraped/licensed; live scores from a third-party widget. Fully automated, no human in the loop per match.
- **SoccerVista:** Form-based lookup tables (last N results, H2H) over historical CSV; odds via affiliate feed. Prediction = trend continuation.
- **Windrawwin / BetExplorer:** Odds-comparison-first. They ingest bookmaker prices across 20+ books, derive implied probabilities, and show "value" when their consensus diverges from a single book. Fixtures from a sports-data API.

### 1.3 What this means for OLP XDV

**OLP XDV already exceeds the archetype-A/B sites on data redundancy** (multi-source failover with circuit breakers, `data/multi_source.py`) and **equals/exceeds Forebet on modelling** (4 independent engines + consensus + CLV gate). The gaps vs the *best* commercial sites are:

1. **No live in-match score feed** (client dashboard requirement, flagged open in `OLP_XDV_FUNCTION_MAP.md`). Commercial sites embed a live-score widget.
2. **xG limited to Big-5** (Understat). Commercial "analytics" sites increasingly show xG for more leagues via paid StatBomb/Opta.
3. **Continental + smaller-league history gaps** (HNL, Austrian Bundesliga, EFL Cup) — these sites fill them with paid API-Football or scraping.
4. **Booking-code automation** — SportyBet has no public code-generation API; commercial tipping sites that do auto-build slips use bookmaker *affiliate* APIs (not available to us without a commercial agreement).

---

## PART 2 — OLP XDV Current Data Pipeline & Gaps

### 2.1 Live data sources (wired, in priority/failover order)

**Fixtures** (`build_fixtures_multi_source`):
1. TheSportsDB (season feed → eventsday) — P10
2. ESPN scoreboard (key-free; covers continental + Austrian/HNL) — P15
3. Odds API (derived fixtures) — P20
4. API-Football (paid-plan fallback) — P30

**Historical results** (`build_results_multi_source`):
1. football-data.co.uk CSV (`E0`, `SP1`, `I1`, `D1`, `F1`, `SC0`, `BE1`, `N1`, `E1`, `P1`, `DK1`, `POL`) — P10
2. football-data.org (live current-season, free reg, P0 gap fix 2026-08-12) — P12
3. API-Football (paid, fallback) — P15
4. TheSportsDB results (continental/HNL, reference-only T2) — P20

**Odds** (`build_odds_multi_source`, per-league):
1. The Odds API UK (`h2h,totals`) — P10
2. The Odds API EU — P15
3. API-Football odds (free-plan fallback) — P20

**xG** (`build_xg_multi_source`):
- Understat (Big-5 + RFPL only) — P10

**Live scores:** football-data.co.uk / TheSportsDB (no dedicated in-play feed yet).

**Booking:** SportyBet (via `booking/` modules — requests client + Playwright cache builder + bridge).

### 2.2 The 4 prediction engines
- **Dixon-Coles** (`engine/dixon_coles.py`) — goals model, canonical for legs/CLV/calibration.
- **Elo** (`engine/elo.py`) — cross-league result history, independent failure mode.
- **xG** (`data/xg_source.py`) — chance quality, Big-5 only.
- **Consensus** (`engine/consensus.py`) — ScoreGPT-style majority vote across DC/Elo/xG/**Bookmaker (4th voter)**.

### 2.3 Documented gaps (from `LEAGUE_DATA_COVERAGE.md` + code)
| Gap | League(s) | Current state | Fix path |
|---|---|---|---|
| History T1 missing | HNL, Austrian Bundesliga | ❌ GAP | API-Football paid OR football-data.org current-season |
| History T1 missing | EFL Cup, domestic cups | ❌ GAP | TheSportsDB fixtures only; no CSV |
| xG | All non-Big-5 (14 leagues) | ❌ GAP | Understat limitation; consider StatsBomb open / penaltyblog scrapers |
| Live scores | All | ⚠️ no dedicated in-play feed | ESPN/API-Football live endpoint |
| Odds (Croatia) | HNL | ⚠️ unverified sport key | probe `/v4/sports` |
| Booking map | Austrian Bundesliga | ⚠️ TBC | verify SportyBet sidebar |

---

## PART 3 — Cloned GitHub Repos & Their Value

All under `external/`. Reference-only unless noted.

| Repo | What it is | Value to OLP XDV | Integration risk |
|---|---|---|---|
| **sports-skills** (machina-sports) | 20+ skills: football-data, betting, markets, polymarket, kalshi, F1, cricket, etc. | **HIGH** — installed as `.claude/skills/`, 4 already wired. Independent verification inputs (ESPN/H2H/ClubElo/Understat/FPL). | Low (read-only skills) |
| **sports-betting-claude** | Methodology skills: edge-detection (de-vig→Kelly→anti-bias), bankroll, performance, sport-specific | **MEDIUM** — `edge-detection/SKILL.md` is a clean reference for the existing `engine/mes.py` + `engine/markets.py` blend logic. Mostly US sports. | Low (methodology only) |
| **betting-odds-tracker** | Real-time line-movement snapshots + sharp-money (RLM) flags via The Odds API + SHIP | **MEDIUM/HOLD** — needs 2 API keys; candidate future *input feeder* if sharp-money signalling is ever ratified. NOT wired. | Medium (keys + new pipeline) |
| **betting-app-skill** | Next.js14 + Supabase pari-mutuel patterns | **LOW (patterns only)** — webapp is stdlib Python; only architecture patterns transfer. | N/A |
| **design-skills** | 6 design sources (emilkowalski, vercel, taste-skill, ui-ux-pro-max, extract-design-system) | **PRESENTATION ONLY** — already copied into `.claude/skills/`. Never touches prediction logic. | None |
| **football-prediction** (4 repos) | penaltyblog (Cython DC/Poisson/Bayesian + scrapers), soccerstan, Dixon-Coles-Predictor, MatchOutcomeAI | **MEDIUM (cross-check only)** — penaltyblog is a strong DC/Bayesian cross-check of our engine math; do NOT adopt its model as ours (ours stays hand-rolled/auditable). | Low (cross-check, not merge) |
| **nba-patterns** | NBA_Betting + nba-prediction architecture | **N/A** — NBA markets banned in hard rules; prediction models never borrowed. | None |
| **soccer_xg** (low-priority) | Event-level xG | **FILED** — only relevant with real event data (we don't have it per xG coverage conclusion). | None |

**Recommendation:** sports-skills (done), sports-betting-claude edge-detection (reference), football-prediction/penaltyblog (DC cross-check test). The rest are reference-only and should stay unintegrated per CLAUDE.md.

---

## PART 4 — The "Blood Products" & Their Constant Communication

The framework's five core components talk to each other every run. Here is the **communication graph**:

```
                         ┌─────────────────────────────────────┐
                         │   MULTI-SOURCE FABRIC               │
                         │   (data/multi_source*.py)          │
                         │   fixtures · results · odds · xG   │
                         └───────────────┬─────────────────────┘
                                         │ failover-ordered data
                                         ▼
        ┌────────────────────────────────────────────────────────────────┐
        │                      ENGINE (math heart)                         │
        │  Dixon-Coles ──┐                                                  │
        │  Elo ─────────┼─► compute_consensus() ──► avg 1X2 + majority     │
        │  xG ──────────┘        ↑                                          │
        │  Bookmaker(4th) ───────┘ implied_1x2 (devigged)                  │
        │        │                 │                                        │
        │        │ blend_toward_market() (disagreement-weighted)            │
        │        ▼                 ▼                                        │
        │   model_prob + market_anchored prob → MES trigger price           │
        └───────────────┬───────────────────────┬──────────────────────────┘
                        │ predictions            │ graded outcomes
                        ▼                        ▼
        ┌───────────────────────┐      ┌──────────────────────────────────┐
        │   BRAIN (truth store) │      │   CLV LEDGER / GATE              │
        │   brain/store.py      │      │   clv/clv_logger.py             │
        │   model_state · preds │      │   log_entry → log_close → CLV%   │
        │   legs(mirror) · runs │◄─────┤   gate: ≥30 legs + mean CLV > 0  │
        └───────────┬───────────┘      └──────────────┬───────────────────┘
                    │                                  │
                    │ sync_legs() / calibration_by_market() / engine_clv()
                    ▼                                  ▼
        ┌────────────────────────────────────────────────────────────────┐
        │   BOARD / PUBLISH (output + webapp + Telegram)                   │
        │   produce_bet → render → SportyBet code → client/admin dashboards│
        └────────────────────────────────────────────────────────────────┘
```

### 4.1 Each product, what it speaks, and to whom

| Product | Speaks (emits) | Listens to (consumes) | Transport |
|---|---|---|---|
| **Multi-source fabric** | typed dicts: `{fixtures, dates, skipped, source}` / `{results}` / `{fixtures w/ odds}` / `{ratings}` | nothing (origin) | kwargs-tolerant `fetch()` |
| **Engine** | `FixtureProbabilities` (DC), `(p_home,p_draw,p_draw)` (Elo/xG), `Consensus`, `model_prob` per market, MES trigger price | multi-source data; `implied_1x2` from odds | in-process function calls |
| **Brain** | SQLite rows: `model_state`, `predictions`, `legs` (mirror), `runs`, `corrections` | engine predictions; CLV ledger via `sync_legs()` | `Brain` class (WAL) |
| **CLV Ledger/Gate** | `LoggedLeg` (entry→close→CLV%); `phase2_status()` gate verdict | engine picks (via orchestrator); closing odds (CL-LIVE/ARCHIVE) | `CLVLog` JSON (canonical) + brain mirror |
| **Board/Publish** | rendered board, SportyBet codes, dashboard JSON | Brain predictions; CLV gate status; booking bridge | `produce_bet` → webapp/Telegram |

### 4.2 The "constant talking" (every run, in order)
1. **Multi-source → Engine:** failover delivers fixtures+results+odds+xG for each league.
2. **Engine internally:** DC fit → Elo rates → xG (Big-5) → Bookmaker devig → `compute_consensus` → `blend_toward_market` → `trigger_price` (MES).
3. **Engine → Brain:** every rated prediction persisted (`append_predictions`); model_state cached by `content_hash` (reuse if identical).
4. **Engine → CLV Ledger:** canonical DC pick logged as paper leg (`log_entry`).
5. **Brain ↔ CLV Ledger:** `sync_legs()` mirrors JSON→brain; `gate_status()` reads brain SQL.
6. **CLV Ledger → Brain:** settled results + closing odds → `clv_pct` → calibration evidence (`calibration_by_market`, `engine_clv`).
7. **Brain → Engine (next run):** `engine_clv` + `ensemble_weights` feed consensus *weighting* (CLV-proven engine counts more).
8. **Brain/CLV → Board:** gate status gates publish; predictions render with consensus + MES.
9. **Board → Booking:** `booking/bridge.py` resolves SportyBet codes for publishable picks.

**The loop is honest by design:** HR35 (never fabricate) is enforced at every edge — a missing source raises `SourceNoData` (falls through, no circuit-trip), a missing price → `model_prob` stays honest scan-only, a missing CLV → `NO DATA — PENDING`.

---

## PART 5 — Automated Implementation Prompts

Each prompt is self-contained for an agent (claude/code-reviewer/planner). Protected-constant diffs route to `code-reviewer-config` per CLAUDE.md.

### PROMPT A — Close HNL & Austrian Bundesliga history gap
```
ROLE: backend-architect
TASK: Wire football-data.org (already implemented in data/football_data_org_source.py,
      priority 12 in build_results_multi_source) as the T1 history source for HNL and
      Austrian Bundesliga, which currently show ❌ GAP in LEAGUE_DATA_COVERage.md.
STEPS:
 1. Confirm football_data_org_source.fetch_current_season_results covers both leagues
    (Croatia: 'HNL', Austria: 'Austrian Bundesliga' — verify the football-data.org slugs).
 2. If football-data.org lacks them, fall back to API-Football results
    (data/api_football_results.py) — but that needs a PAID plan; log a data_flag and
    leave the league scan-only rather than fabricating history (HR35).
 3. Update docs/LEAGUE_DATA_COVERAGE.md rows 15 & 16: change History ❌→✅ with the
    active source, add a 🔧 note if paid plan required.
 4. Add a monitor/data_quality.py check that alerts if either league's history returns
    < 4 matches (promoted-club floor).
VERIFY: pytest tests/test_data_coverage.py — both leagues return ≥4 results in season 2526.
CONSTRAINT: Do NOT touch BLOCKED/market gate/CLV thresholds (protected).
```

### PROMPT B — Add a live in-play score feed (client dashboard requirement)
```
ROLE: backend-architect
TASK: Add a live-score multi-source so the client Scan tab can show real-time scores
      post-kickoff (currently an open item in OLP_XDV_FUNCTION_MAP.md).
STEPS:
 1. Build data/live_scores.py with a LiveScoresSource(DataSource) for:
      - ESPN scoreboard live endpoint (key-free, covers all leagues)
      - API-Football live scores (free-plan fallback)
 2. Register in data/multi_source_concrete.py build_current_results_multi_source OR a
    new build_live_scores_multi_source(); add to SourceRegistry.
 3. Expose via agent_cli.py (`scores` command) and a webapp polling endpoint
    (server.py) that returns {fixture: {status, home_goals, away_goals, minute}}.
 4. Wire the client dashboard Scan row: pre-kickoff shows kickoff time; post-kickoff
    shows live score from this feed.
VERIFY: unit test with a mocked ESPN live response; integration against tonight's fixtures.
CONSTRAINT: Read-only display — never feed live scores into the model fit (leakage guard).
```

### PROMPT C — Penaltyblog DC cross-check harness
```
ROLE: tdd-guide
TASK: Build a cross-check test that fits our Dixon-Coles on the SAME training rows as
      penaltyblog's DixonColesGoalModel and asserts the 1X2 probabilities agree within
      a tolerance (our engine stays canonical; this is a sanity net, not a replacement).
STEPS:
 1. pip install penaltyblog into the test venv (dev dependency only, NOT production).
 2. In tests/cross_check/test_dc_vs_penaltyblog.py:
      - load a whitelisted league's football-data.co.uk rows
      - fit both models, predict 50 held-out fixtures
      - assert |our_p - penaltyblog_p| < 0.05 mean absolute error per outcome
 3. If disagreement > tolerance, flag for code-reviewer (possible bug in OUR fit),
     do NOT switch engines.
VERIFY: pytest tests/cross_check/ — must pass on 2425 + 2526 seasons.
CONSTRAINT: penaltyblog is reference-only; its model never enters the production path.
```

### PROMPT D — Sharp-money (RLM) signal as optional verification input
```
ROLE: architect (READ-ONLY analysis first)
TASK: Evaluate whether betting-odds-tracker's reverse-line-movement flags should become
      an OPTIONAL verification input (honest-edge: independent input, not an override).
STEPS:
 1. Read external/betting-odds-tracker/SKILL.md + its The Odds API + SHIP integration.
 2. Confirm it needs 2 API keys (The Odds API already used; SHIP key NEW).
 3. If Architect ratifies: add data/sharp_money.py as a 5th consensus input ONLY when
     the SHIP key is present; otherwise silent (HR35 — never fabricate).
 4. It must pass through the publish gate (ID403 multi-factor verify) like any source.
VERIFY: design doc + RATIFICATIONS.md entry BEFORE any code.
CONSTRAINT: This touches verification logic — route through code-reviewer-config.
            Do NOT auto-merge; needs explicit Architect sign-off (see CLAUDE.md
            "Protected" list — capital/verification gating).
```

### PROMPT E — Extend xG beyond Big-5 (research, non-blocking)
```
ROLE: researcher
TASK: Survey free/low-cost xG sources for the 14 non-Big-5 whitelisted leagues.
STEPS:
 1. Check penaltyblog's Understat scraper coverage vs our xg_source.is_covered().
 2. Survey: StatsBomb open data, FBref, soccer-xg (event-level, currently filed),
     FotMob/API-Football xG fields.
 3. Report: which leagues CAN be covered for free, which need paid, which are impossible.
 4. Do NOT implement — produce docs/X\_SOURCING_OPTIONS.md for Architect review.
CONSTRAINT: xG coverage is a calibration-scope decision; any expansion needs ratification.
```

### PROMPT F — Automate the daily intelligence loop (daemon)
```
ROLE: devops-troubleshooter
TASK: Add a scheduled job (Task Scheduler, sibling of existing 06:00/15:00 Data Steward)
      that runs the data_quality monitor + multi-source health report and posts a
      concise summary to the Architect via Telegram (reuse the resident poller channel).
STEPS:
 1. Extend monitor/data_quality.py to emit a structured health dict
     (stale cache, duplicates, missing coverage, circuit-breaker states).
 2. Add a Telegram formatter that truncates to the top N flags.
 3. Register a new scheduled task "Data Health Watchdog" at 21:00 daily.
VERIFY: dry-run prints the health dict; Telegram send mocked in tests.
CONSTRAINT: No model/CLV/gate changes.
```

---

## APPENDIX — Quick-reference source map

| Need | Best current source | Fallback | Notes |
|---|---|---|---|
| Fixtures (all leagues) | TheSportsDB | ESPN → Odds API → API-Football | ESPN covers continental + no-ID |
| History (11 Euro leagues) | football-data.co.uk | football-data.org (live) → API-Football | CSVs end-of-season |
| History (continental/HNL) | TheSportsDB (T2 ref) | API-Football (paid) | not calibration-grade |
| Odds (1X2 + totals) | The Odds API UK/EU | API-Football odds | free tier = 5 markets |
| xG (Big-5) | Understat | — | only Big-5 + RFPL |
| Bookmaker 4th-voter | The Odds API devig | API-Football | implied_1x2 |
| Live scores | (GAP) | ESPN/API-Football | see Prompt B |
| Booking codes | SportyBet bridge | manual | no public API |
| Independent verify | sports-skills (ESPN/H2H/ClubElo) | polymarket/kalshi | read-only skills |
```
