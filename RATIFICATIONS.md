# OLP XDV — Ratification Log

Append-only, per HR33. Each entry is written **at the time of the change**
(HR44), not reconstructed afterwards. Authority is recorded per entry:
the Architect's bright lines (capital, staking, fabrication, verification,
honest-edge) are never auto-ratified — Section 12.

---

## 2026-08-09 · SAME-DAY PRODUCT BET + 4-LEG ACCAS + SPORTYBET BOOKING CODES — standing rule, by order of the ARCHITECT

**What the Architect asked:** "new rule product bet should focus only on
fixtures available for that day nothing else… at the end of the production the
framework can now name a set of 4 leg acca in 2 or 3 places be honest and tell
me what you think and you can then book the sportybet codes each acca bet."

**What changed (standing rule 2026-08-09, commit `d7ccbdd`):**

1. **Same-day-only product bet.** THE CALL, the produced bet, TODAY'S PICKS
   parlay and the acca set draw ONLY from fixtures kicking off TODAY
   (`kickoff_date == today`), on every path: `output/produce_bet.py`
   (`render_daily_recommendation`, `render_part1_the_call`,
   `render_produce_bet`, `render_telegram_board`), `webapp/render.py` client
   call, `webapp/produce.py`, `scripts/accumulator_prep.py`. The wider 3-day
   window stays the scan reference (PART 2 / scan tables), not the bet. A
   fixture with no kickoff date is NEVER assumed to be today (HR35).
2. **Up to three 4-leg accumulators** (`engine/acca.py`, new): from today's
   deploy-eligible shortlist, ranked by EV (prob as tiebreak), Acca 1/2/3 are
   disjoint combinations. Every leg is in a **capital-cleared market**
   (`mkt.DEPLOYABLE` = Draw + Under 2.5, ID405 unchanged — the acca follows the
   gate automatically). Combined odds = product of the leg prices; combined
   chance stated as such ("legs are not independent"). Fewer than 4 eligible
   today → a SHORTENED acca, honestly labelled, never padded. SportyBet's own
   draw price is preferred over the Odds API. `run_daily` writes
   `acca_<date>.json/.txt` (additive, faults never kill the board) and both the
   Telegram and web renders carry the acca block.
3. **SportyBet booking codes, Phase-2 safe** (`booking/booking_codes.py`, new):
   a Playwright pass reads `acca_<date>.json`, resolves each leg's fixture in
   the SportyBet cache, walks the SPA (country → league → match → market) and
   captures the BOOKING CODE SportyBet returns. A booking code only pre-fills
   the Architect's betslip — the module NEVER clicks Place Bet, so no stake is
   ever placed. Per-leg status is BOOKED or MANUAL (a leg the browser cannot
   drive is named for hand-entry, never guessed). Best-effort: a browser fault
   degrades every acca to MANUAL, never a run failure.

**The honest assessment the Architect asked for:** the acca is a *product
shape*, not a demonstrated edge. The backtest is negative overall and the
deployable book's positive residual is drift, not skill (2026-08-08 entry) —
an acca multiplies the variance of legs that are not independent, and the
combined odds understate the real risk. The framework is naming bets an
informed operator can choose between, with the honest-edge line attached; it
is NOT claiming a profitable system. Booking codes are conveniences, not
permission to stake.

**Guardrails kept:** HR35 (no-date fixtures never assumed today; shortened
accas never padded; a code the browser can't read is MANUAL, never fabricated).
ID405 unchanged (Draw + Under 2.5 only). Phase 2 bright line — codes only,
zero capital, the Architect still reviews and pastes. The data-leak boundary
holds: the client sees fixture + market + price + probability per leg, never
EV or market keys.

**Authority:** Architect direct instruction. Changes what the product bet and
board contain, so not under the auto-ratification grant. No capital, staking,
fabrication, verification or honest-edge behaviour changed.

---

## 2026-08-09 · SOFTNESS PAUSED — ID402 deploy gate suspended — by order of the ARCHITECT

**What the Architect asked:** "remove all tiers in bet production and produce
bet normally pause softness."

**What changed:** `engine/softness.SOFTNESS_PAUSED = True` makes the ID402
softness-tier deploy gate a no-op in bet production:
- Every whitelisted league is now deploy-eligible (`is_deploy_eligible` returns
  True for all tiers A-D; HR34 unrated `"?"` leagues still excluded).
- `DEPLOY_POOL_CAP` (6) is lifted — `build_deploy_shortlist` returns all
  market-gate-cleared fixtures when paused.
- THE CALL is ranked purely priced-first then EV/conviction (no tier priority).
- The odds price pull widens from A/B-only to all whitelisted leagues
  (quota self-limits via `check_quota` / `QUOTA_HARD_FLOOR`).

**Unchanged bright lines:**
- **ID405 market gate stays active** — away win, Over 2.5, and home win remain
  blocked from capital (evidence: negative CLV for the model AND random).
- Phase 2 paper-only, zero capital, Architect-only deployment.
- HR35 honesty — unpriced fixtures render NO DATA / are flagged for Architect
  confirmation, never guessed.

**Evidence basis:** the 2026-08-04 null measurement (recorded, not acted on at
the time): softness A/B scored +0.084% vs C/D +0.075% mean CLV — a +0.008pp
difference on 588 vs 1270 legs. Softness was "unproven, not disproven";
pausing the tier gate on that null evidence widens exposure to the full
whitelist. This is the Architect's call, not a model result.

**Reversible:** set `engine.softness.SOFTNESS_PAUSED = False` to restore ID402
(A/B only, cap 6). The machinery is intact.

**Authority:** Architect direct instruction. No capital, staking, fabrication,
verification or honest-edge behaviour changed (the market gate is unchanged).
All softness/multi-league/engine-regression/webapp suites green.

## 2026-08-07 · Health monitor — self-triggering, self-healing awareness — built by order of the ARCHITECT

**What the Architect asked:** "can you build me a self healing monitoring bot"
(after the 07:00 run failed silently twice and only the launch marker proved
the difference between "never started" and "started and crashed").

**What was built:** `monitor/health_monitor.py` — a 9-probe awareness layer that
runs on ITS OWN schedule (Task Scheduler "OLP XDV Health Monitor", every 2h,
via `health_monitor.bat` + `setup_health_monitor_task.ps1`, idempotent like the
poller task). It answers the questions the daily run assumes are fine:

1. **Phase guard** — is the paper-only capital block still in force?
2. **Env completeness** — are the keys the pipeline needs actually set?
3. **Brain health** — does `brain/olp.db` open, migrate, and hold model state?
4. **CLV ledger** — does `clv/clv_log.json` parse and hold the canonical legs?
5. **Odds quota** — how much of the free-tier monthly quota is left?
6. **Cache freshness** — are the TTL caches within their max ages?
7. **Last daily run** — did the latest run complete AND deliver?
8. **Web dashboard** — is the local server reachable?
9. **Data-source circuits** — is any fallback source stuck in circuit_open?

**Self-healing:** the stale LIVE-season results feed is re-downloaded (the
file whose staleness cost the Phase-3 gate its reachability) — a heal only
counts as healed when the file is actually fresh afterwards, and it reuses the
owner's own refresh path so a failed refresh keeps the stale snapshot (HR35:
never a guessed heal).

**Alerting — state changes only:** a NEW problem, a RESOLVED problem, or one
still open after the 26h reminder ring alerts exactly once over best-effort
Telegram. A problem that keeps failing check-to-check does NOT re-alert, so a
2-hourly monitor never spams the phone. Same never-raises discipline as the
watchdog — the monitor can never crash its own scheduler.

**Live first run (2026-08-07):** 4 real findings surfaced — env missing
THESPORTSDB_KEY, odds quota at 4/5 (the deploy-league guard), stale fixture
caches (expected pre-season: 3-day window, no today-only re-pull), and last
run completed but did not deliver to Telegram. Each honest, none guessed.

**Authority:** Architect. Additive infrastructure under the auto-ratification
grant — monitoring and alerting change no capital, staking, fabrication,
verification or honest-edge behaviour, and nothing a probe reports alters the
board. Test suite: `tests/health_monitor_test.py` (alert-on-change,
resolution, reminder ring, heal honesty). The same commit carries the other
session's scan-only **Austrian Bundesliga** capture (odds sport key + tier D
whitelist — verified live 2026-08-07; no history source covers it, so its
fixtures list honestly unrated NO DATA — PENDING until one does) and the
**SourceNoData** refinement to the multi-source layer (a quiet league is a
valid empty answer, not a fault — it falls through to the next source without
tripping the circuit breaker).

---

## 2026-08-07 · Approve→Publish gate + admin search + grouping/flags/badges on both dashboards — ratified by the ARCHITECT

**What the Architect asked** (restated for the record): "Good set of upgrades —
let me restate a few garbled bits back to you before writing the plan." Four
additions to the two-tier dashboard:

1. **Admin search/filter bar** above THE CALL — live filter (no page reload) by
   date, league (ID401 whitelist), team name, market type, softness tier; a
   clicked result opens the same expand-in-place detail panel already built.
2. **Approve → Publish to Client** — the one manual gate in the publish path.
   It commits the board exactly as reviewed in admin (not a fresh re-fetch) to
   the published store the client reads; nothing reaches the client dashboard
   automatically, and every publish is written to `publish_audit.jsonl`
   (timestamp, what went out, by whom).
3. **Client visual overhaul** — a hero (today's date + the strongest pick
   surfaced), card-forward layout, hover/transition states, the amber/teal
   accent system. Same data, no data change.
4. **THE SCAN grouped by league** (collapsible section per league) and sorted
   within each league by pick confidence, strongest first — on BOTH dashboards,
   on top of admin's existing detail-on-expand.
5. **Flags + badges on both dashboards** — country flag next to each league
   name (flagcdn.com, the one external flag source) and a club crest/badge next
   to each team. Badges: real crests where a free source covers the club
   (TheSportsDB-adjacent URLs are NOT used at render time — the export is
   self-contained), otherwise a deterministic initials fallback (`_initials`)
   with a colour derived from the club name — never a generic placeholder that
   looks like real data; the fallback is labelled a placeholder.

**What was built:**

- `schema.py`: `trim_payload()` (client-safe trimming), `write_published()` +
  `read_published()` + `PUBLISHED_DIR` + `read_audit_log()` (the published
  store, gitignored like the raw boards — runtime state, never committed).
- `server.py`: `POST /api/admin/publish` (Basic-auth'd, admin-only, writes the
  exact admin-reviewed payload), client `/dashboard` reads the published store
  not the raw board dir, `/api/board.json` trimmed.
- `render.py`: `render_admin_dashboard()` (full internal view + search/filter
  data-attrs + inline JS), client `render_dashboard()` with hero + grouped
  league scan, `_pick_confidence` sort key, `_flag_html`, `_initials` fallback
  crest, crest/flag rendering on BOTH views.
- `export.py`: client-only export reads the published store; `stats.json` stays
  out (admin-only diagnostic).
- `monitor/health_monitor.py` + `logs/health_state.json`: the health monitor
  (reconciled in from the parallel session's work).

**Guardrails kept:** HR35 (a missing published board reads NO DATA — PENDING,
never a guess; a newer schema is refused). The data-leak boundary from the
previous entry still holds — the client view ships only trimmed payloads. The
Audit log records the operator action; the capital block and honest-edge
statements are untouched. All 40 test suites green, including the five webapp
suites (render/schema/server/export/crest) rewritten for the boundary and the
publish gate.

**Authority:** Architect. New routes, a new publish gate, and a client visual
redesign reverse the prior "no manual publish step" reading, so they were not
taken under the auto-ratification grant. No capital, staking, fabrication,
verification or honest-edge behaviour changed.

---

## 2026-08-07 · Two-tier web dashboard: public client + authed /admin — ratified by the ARCHITECT

**What the Architect asked:** "use it ui and every design from it everything
study and copy the website" with the ScoreGPT reference (scoregpt.app) and the
approved design_reference HTML files — a dark, phone-first football-prediction
dashboard. The design was approved as two views built on the SAME reference
language.

**What was built:**

1. **Public client view** (`/dashboard/{date}`, the static export, `/api/board.json`):
   predictions only. Header (`OLP XDV · 07:00`), **THE CALL** (deploy shortlist
   as expandable cards: pick + probability + "Deploy At" trigger; tapping opens
   the full 10-market grid — 1X2, goals lines, BTTS, double chance), **THE SCAN**
   (every fixture across every league in one click-to-expand table with compact
   codes: `1X2` favourite, `O1.5/O2.5`, `DC/BTTS`). This is exactly the approved
   reference layout.
2. **Authed admin view** (`/admin/{date}`, `/stats`, `/why`, `/api/admin/board.json`):
   the same design PLUS the model internals — Dixon-Coles / Elo / xG probabilities,
   engine divergence, HR30 MES (entry price, EV, bookmaker), verification
   (verified/single-source stamp), softness tier, cap counter, data flags,
   "Verified — Yesterday" graded rows, and the **honest-edge statement + capital
   authority** footer with the Phase-3 gate bar. Protected by HTTP Basic auth
   (`ADMIN_USER` / `ADMIN_PASS` in .env). No `ADMIN_PASS` set → /admin returns a
   503 "set ADMIN_PASS", never a default password.
3. **The DATA-LEAK BOUNDARY (the critical guardrail):** `schema.trim_payload()`
   strips every internal from the public payload *before* the client renderer
   ever sees it — elo/xg second opinions, engine divergence, consensus votes,
   verification, EV verdicts, softness tier, gate, calibration, data flags,
   kickoff date, price. The client "full analysis" market grid is derived from
   the market probabilities alone, so it needs nothing the client is denied.
   Enforced by the render, schema, server and export test suites (the server
   test asserts no internal string appears in `/dashboard` or `/api/board.json`,
   and `/api/admin/board.json` requires auth).
4. **Static export is now client-only:** `webapp/site/` ships `index.html` +
   trimmed `board.json` + a README explaining the boundary. `stats.json` is
   deliberately NOT exported (it is the admin diagnostic layer; a static host
   cannot authenticate). The only external fetch anywhere is the
   Architect-approved Google Fonts CDN (Barlow Condensed / Inter / IBM Plex
   Mono), with system fallbacks for offline.
5. The old scorecard (TODAY'S PICKS parlay / gate tiles / yesterday-rolling
   bars) is superseded by this two-tier layout; the honest-edge and capital
   authority lines moved to /admin (the Architect's explicit choice — the
   public client view matches the approved HTML and omits them).

**Honest consequence, surfaced:** the public client shows the predictions and
the honest NO DATA — PENDING rows (HR35); it deliberately does NOT claim the
honest-edge/capital statements, because those are the operator's own guardrails,
not a product claim. The operator's copy (admin view + /stats) keeps them.

**Authority:** Architect. New rendering layer + new authed route; the design
replaces a ratified board layout, so it was not taken under the auto-
ratification grant. No capital, staking, fabrication, verification or honest-
edge behaviour changed (the honest-edge text still ships — on /admin). All 38
test suites green, including the four webapp suites rewritten for the boundary.

---

## 2026-08-07 · The profitability question, answered with a complete 2x2 — by order of the ARCHITECT

**What the Architect asked:** "how can the edge become profitable — find a
lasting solution".

**What was measured (the full experiment matrix on the 2425 walk-forward
backtest, all four cells run and compared):**

| cell | ALL | away (1X2_A) | draw (1X2_D) | home | O2.5 | U2.5 |
|---|---|---|---|---|---|---|
| baseline | 2952 · **-0.410%** t=-2.85 | **-2.125%** t=-5.50 | +0.415% | +0.233% | -0.550% | +0.247% |
| + calibration | 3230 · **-0.358%** t=-2.64 | -1.738% t=-4.00 | +0.451% | -0.182% | -0.781% | +0.214% |
| + market blend | 2652 · **-0.426%** t=-2.72 | -2.097% t=-5.28 | +0.415% | +0.236% | -0.613% | +0.230% |
| + both | 2776 · **-0.425%** t=-2.78 | **-1.991%** t=-4.58 | **+0.546%** t=2.40 | -0.185% | -0.608% | -0.016% |

**Three independent conclusions, each measured not assumed:**

1. **The entire negative lives in the away market.** In every cell, the away
   bucket is ~-2% (t between -4.0 and -5.5); the draw is the model's ONLY
   genuine edge (+0.42 to +0.55%, beat 53-56%), home and U2.5 are roughly
   neutral. The model's away probabilities are wrong (claims ~39%, delivers
   ~30%) and the closing line is honest (hit ≈ fair_close), so every away
   pick loses to the close wherever it is selected.
2. **No probability-side nudge can fix aways.** Bounded out-of-sample
   calibration (cap ±3pp and ±15pp measured earlier), a market-anchored
   blend proportional to disagreement (the other session's ID414), and both
   together all leave aways at ~-1.7 to -2.1%. The fix does not belong in any
   screen or post-hoc nudge — it belongs in the model's away probabilities at
   FIT time, or in not betting aways at all.
3. **The deployable gated book is positive.** The ID405 market gate already
   restricts capital to home/draw/under2.5. That gated book is **+0.13% to
   +0.29% across all four cells** — positive everywhere, with the draw as its
   engine. The gate is the lasting solution's foundation, and it was already
   ratified and (this session) fully enforced.

**What was changed (combined with the other session's ID414 in a
reconciliation commit):**
1. `engine/softness._confidence` now ranks unpriced fixtures by their best
   DEPLOYABLE market only. Verified leak on the live 08-07 board: 2 of 6
   CALL entries were unpriced away-conviction picks (Sparta v Feyenoord,
   Zwolle v Ajax) — the board recommending exactly the markets the ledger
   refuses to log. Now excluded.
2. `build_deploy_shortlist` gains a structural backstop: a fixture whose
   headlined market key is blocked cannot enter THE CALL even if softness
   A/B.
3. `backtest_report` now prints the Market blend knob (a --blend-market run
   was previously indistinguishable from the baseline).
4. The other session's ID414 (market-anchored display probability + EV on the
   blend, backtest --blend-market) is preserved, committed, and measured.

**The honest recommendation to the Architect:** profitability, if it exists,
comes from (a) the gated deployable book — positive in every experiment cell
— proven FORWARD through the 30-leg Phase-3 gate; and (b) fixing the model's
away probabilities at fit time (asymmetric home advantage, time-decay) so
aways stop being a guaranteed bleed. The framework is NOT yet a demonstrated
edge; the gate exists for exactly that reason.

**Guardrails:** no capital, staking, fabrication, verification or
honest-edge behaviour changed. The blend is display + EV only; the ledger
keeps raw model probabilities (no feedback loop). The gate only narrows what
can be deployed.

**Authority:** Architect. The gate enforcement reverses no ratified decision
and only narrows; it and the measurements were taken at explicit request.

---

## 2026-08-07 · Promoted-club honesty: per-case NO DATA message + second-division mechanism — by order of the ARCHITECT

**What the Architect asked:** after the 3-day window filled the board (22/27
rated), the remaining NO DATA rows (Cambuur, ADO Den Haag, AC Horsens,
Lommel, Beveren) carried a message that offered "the fixtures source spells
it differently (a name-mapping gap)" as the FIRST possibility for every
unknown team — including clubs that are not mapping gaps at all. The
Architect asked to fix "this and all occurrences".

**The finding (verified, not assumed):** all 5 are clubs NEWLY PROMOTED from
a second division, NOT spelling gaps. Verified against every fit season
(2324/2425/2526) AND the framework's own suggest_aliases machinery — every
one returns "no close match in the model pool", so no alias exists that would
rate them. Fabricating one would violate HR35.

**What was built:**
1. **Per-case NO DATA message** (`_unrated_detail` in orchestrator.py): the
   message now resolves each unknown team against the fitted roster. A close
   alias match → a REAL mapping gap, named target, "verify and add to
   TEAM_ALIASES". No match → "newly promoted with no top-flight history in
   the fit window — no alias can rate it; becomes rateable once it has played
   enough top-flight matches". Applies to every occurrence through the shared
   path.
2. **Second-division mechanism, wired and tested** (`predict_adjusted` in
   engine/dixon_coles.py, `load_second_division` in
   data/football_data_source.py, promoted-team detection in the carry-over
   fit): a promoted club's second-division season rates it through the
   carry-over model, with a CONSERVATIVE level adjustment (PROMOTION_SCALE
   0.90 / PROMOTION_OPPONENT_SCALE 1.08 — its goals came against weaker
   defences; better a cautious number than a confident wrong one).

**The honest blocker:** the DATA is unreachable with current credentials.
football-data publishes NONE of the needed second divisions (D2 is the GERMAN
2. Bundesliga — verified and deliberately never mapped; N2/B2 are dead
links; DNK is the Danish Superliga only). TheSportsDB has the leagues but the
free test key truncates league discovery to 5, and API-Football's free tier
stops before the 2425 season. So SECOND_DIVISION_CODES is EMPTY by design:
the mechanism is ready (a personal TheSportsDB key is the documented path —
one code + one league ID per league wires it), and the 5 clubs stay honest NO
DATA until then, or self-rate in ~2–4 weeks once they have top-flight
matches. The wrong D2 cache created while investigating was deleted.

**Guardrails:** no capital, staking, fabrication, verification or
honest-edge behaviour changed. The message is MORE honest (never claims a
mapping that doesn't exist); the mechanism feeds nothing until real data
exists. New suite: `tests/promoted_club_test.py` (7 checks).

**Authority:** Architect. The message change and the mechanism change what
appears on the board, so they were taken at explicit request; HR35 kept
throughout.

---

## 2026-08-07 · Out-of-sample calibration layer in the CLV backtest — built by order of the ARCHITECT

**What the Architect asked:** after the three-way CLV breakdown showed the entire
negative result living in the away market (1X2_A at **-2.125%, t=-5.50**, negative
in all six leagues), I recommended recalibrating the model's probabilities toward
the closing line. The Architect ratified the prototype: "yes do what is best".

**What was built:** `backtest/clv_backtest.py` gains an out-of-sample per-market
calibration layer (`CalibrationState`), gated behind `--calibrate` (default OFF,
so the baseline selector is byte-identical and every prior run stays
reproducible). It reuses `engine/recalibration.py`'s `apply()` and mirrors its
evidence gate / cap / ramp contract, but the cap is a config knob
(`--cal-max-adjustment`) because the measured overconfidence (9-17pp) exceeds the
live machinery's fixed ±3pp bound. WALK-FORWARD HONESTY: block k's delta comes
only from blocks < k — a match's outcome is recorded only after its whole block
has been predicted, so selection never calibrates on its own outcomes. Tests
`12a-14` in `tests/clv_backtest_test.py` pin the gate, the bound, the
walk-forward ordering, and the "calibrated MES gates selection, raw model_prob
stays on the leg" contract (no feedback loop). The report now prints the
calibration config and a per-market MODEL CALIBRATION block (model_p vs hit vs
fair_close) so overconfidence is visible on every run.

**What the measurement found — honestly, a NEGATIVE result:** calibration does
NOT rescue the away market. Before/after on the same 2425 season:

| cap | ALL LEAGUES | 1X2_A | tier A/B |
|---|---|---|---|
| OFF (baseline) | -0.410% (t=-2.84) | -2.125% (t=-5.50) | -0.616% |
| ±3pp (live bound) | -0.368% | -2.072% | -0.568% |
| ±10pp | -0.305% | -1.792% | -0.428% |
| ±15pp, gate 5 | -0.358% | -1.738% | -0.547% |

Even at 3-5x the live bound, 1X2_A stays ~-1.8% (t≈-4). Calibration nudges the
headline but cannot fix the away bucket: the model's away picks lose to the
closing line wherever they are selected. This is a **structural calibration
failure on aways, not a selection-knob failure** — devigging the screen was also
measured to be a no-op (100% of the same legs survive). The recalibration
machinery the live path already has (inert at present for lack of settled legs)
is, on this evidence, **not sufficient** to make the away market profitable; the
fix belongs in the model's away probabilities themselves, not in any screen or
bounded nudge.

**Guardrails:** backtest-only and additive — `calibrate` defaults OFF, no capital,
staking, fabrication, verification or honest-edge behaviour changed. The
calibration layer and report block are measurement infrastructure; the finding
is recorded, not tuned around.

**Authority:** Architect. Additive infrastructure under the auto-ratification
grant, built at explicit request. All 37 suites green.

---

## 2026-08-07 · Fixture window 0→3 days + promoted-club carry-over — ratified by the ARCHITECT

**What the Architect asked:** "just like scoregpt everyday there is a
prediction and it wont display no data how can we fix that" — a non-empty
board with real predictions every day. Given two choices, the Architect chose
**next 3 days** (a rolling window, like ScoreGPT) and **maximize coverage
while keeping HR35** (never fabricate; widen what is honestly rated).

**1. Window: today-only → next 3 days.** The 2026-08-05 today-only decision
was reversed. `run_daily.run(days_ahead=0)` → `days_ahead=3` (CLI
`--days-ahead` to override). Root cause of the empty boards: early August is
preseason — no league has a fixture *today*, but Eredivisie's season opens
tomorrow (Cambuur v Excelsior, PSV v Sittard, Ajax, Feyenoord…) and a 3-day
rolling window surfaces them. The window already threads through every fixture
source; TheSportsDB's season feed re-filters its cached list, so a warm run
costs no extra network. Telegram `/produce bet` and `/send` inherit the
default automatically. TODAY'S PICKS is probability-based and works even with
zero prices.

**2. Promoted-club carry-over fit.** A secondary Dixon-Coles model fit on the
PREVIOUS completed season (2425), used ONLY to rate a fixture the primary
2526 model cannot (a club relegated after 2425 and re-promoted for 2627 has no
2526 history). The primary model is untouched — a full two-season fit would
dilute form for every team and worsen the away-market overconfidence the CLV
backtest found; carry-over only widens coverage where the primary has nothing.
The carry model is a real DC fit on real prior-season data, never a guess, and
carry-rated fixtures are named in a per-league data flag so they are never
mistaken for primary-window ratings. Fixtures neither model can rate stay
honest NO DATA — PENDING (HR35). Measured on Eredivisie's opening round:
6 of 9 rated with the window alone, 7 of 9 with carry-over; the 2 remaining
(Cambuur, Excelsior, ADO Den Haag) are truly new from the second division.

**Honest note — the Odds API quota:** 496/500 credits used, 4 left (hard
floor 5), so entry prices and the continental odds-derived fixture feed are
NO DATA until the quota resets. Predictions, TODAY'S PICKS, and THE CALL
(conviction-ranked fallback) still flow. A quota upgrade or a reset is needed
for THE CALL's EV and CLV to resume.

**Authority:** Architect. The window and the coverage change reverse a
ratified decision and change what appears on the board, so they were not taken
under the auto-ratification grant.

---

## 2026-08-05 · The Brain (central persistent memory) — built by order of the ARCHITECT

**What the Architect asked:** "the framework agent need a brain" and, after
the design was presented, "yes build the brain".

**What was built:** `brain/olp.db` (SQLite, stdlib-only, gitignored) as an
additive persistence + query layer. Three jobs:

1. **Remember the model.** `scan_one_league(brain=)` stores fitted
   Elo / Dixon-Coles / cross-league params keyed by `content_hash` (sha1 over
   the exact training rows + fit-config salt). An unchanged history is a
   provably identical fit (BUG6 reproducibility), so the cached parameters are
   reused verbatim. Measured steady-state: **refits 0 of 15 leagues** (was 15),
   Elo fully incremental. The engine maths is unchanged — this is persistence,
   not a model change.
2. **Never forget a prediction.** Every rated board prediction is persisted
   (1X2 / O1.5 / O2.5 / BTTS + Elo second opinion).
3. **Answer questions.** New `/stats` telegram command (CLV by market/league/
   tier, prediction counts, last-run summary, pending corrections read back).
   Team lookup is accent-insensitive (Fenerbahce finds Fenerbahçe).

**Guardrails:** `clv/clv_log.json` stays the canonical ledger (the brain's
`legs` is a full-refresh mirror — the JSON always wins). HR35 kept throughout:
missing data reads NO DATA — PENDING, never a guess; a newer schema or payload
version is refused, never adapted. `/note` no longer claims corrections apply
automatically — they are read back by `/stats`.

**Authority:** Architect. Additive infrastructure under the auto-ratification
grant, built at explicit request; no capital, staking, fabrication,
verification or honest-edge behaviour changed. The two new test suites plus
the telegram extensions guard it.

---

## 2026-08-05 · Board is today-only + compact codes — ratified by the ARCHITECT

**What the Architect asked:** "when bet is produce is it today fixture across
the leagues". The run had been scanning a **14-day fixture window**, so an
otherwise quiet Wednesday still showed ~80 fixtures (weekend domestic rounds
mixed into a Wednesday board). The Architect chose **today only**, then chose
the **compact-codes layout** (see the previous entry) after the plain-word
format read as too long and deformed on a phone.

1. **Today-only window.** `orchestrator.scan_one_league` gains `days_ahead`
   (default 14 for tooling that plans ahead); `run_daily.run()` defaults
   `days_ahead=0` and threads it to the thesportsdb, odds-derived and
   api-football fixture sources. `/produce bet`, `/send` and the 07:00 run now
   show literally today's matches across all 15 leagues. Measured: the
   14-day board (11.7k chars, 4 parts) became today's board (669 chars, 1 part).
2. **Honest consequences, surfaced not hidden:** on days with no fixtures the
   board is near-empty, and THE CALL can be empty when today's games are all
   scan-only leagues — today's only matches were UCL qualifiers (tier D), so
   there was no deploy-eligible call. That is correct: you can only bet on
   what is playable today.

**Authority:** Architect. The window and the layout change what appears on the
board, so they were not taken under the auto-ratification grant.

---

## 2026-08-05 · UCL captured via the odds feed + plain-language board — ratified by the ARCHITECT

**What the Architect saw:** UCL/UEL qualifiers on Flashscore but nothing on the
board, and the board read like a wall of technical noise. Two fixes.

1. **UEFA Champions League fixtures are now captured.** TheSportsDB's UCL/UEL
   league IDs were resolved by name+country (lookupleague.php, spaced probes on
   the public test key — not guessed): **Champions League = 4480, Europa League
   = 4481**. Their eventsseason feed lags weeks behind, so the ACTIVE
   current-season capture path is the ODDS feed: `soccer_uefa_champs_league_qualification`
   is now a ratified sport key in pipeline/odds.py, mapped to Champions League.
   `scan_one_league` now falls back to odds-derived fixtures whenever TheSportsDB
   has nothing in the window (previously it only fell back when TheSportsDB
   raised — a league that returned empty was silently NO DATA). Team aliases
   verified against the cross-league fitted pool ("AGF Aarhus"→Aarhus,
   "Fenerbahce"→Fenerbahçe, "SK Sturm Graz"→Sturm Graz) so the model can rate
   the fixtures it knows and honestly say "no prediction yet" for the rest.
   Verified live 2026-08-05: AGF Aarhus v Sabah FK and Fenerbahce v SK Sturm
   Graz appear with real book prices, and Fenerbahce v Sturm Graz carries a full
   model prediction. Europa League has NO current-season source (no odds sport
   key, stale TheSportsDB feed, API-Football free tier stops at 2024) — honest
   NO DATA until one exists.

2. **The board is plain language.** All markets, readable to a non-technical
   person: each rated fixture shows "Win chance: X% · Draw % · Y%", the goals
   and BTTS lines, and a flagged ⭐ Pick — no 1X2/O2.5/column-code jargon. THE
   CALL reads "⭐ Fenerbahce v Sturm Graz — Fenerbahce to win (56%) · value +23%".
   Fixed the EV ranking so a 70%-confident unpriced row can no longer outrank a
   +20%-EV priced row (call_key now separates priced from unpriced first).

**Authority:** Architect. New sport key, new team aliases, board format change.

---

## 2026-08-04 · Wide-eyes daily scan + EV-ranked CALL + compact board — ratified by the ARCHITECT

**What:** three connected decisions taken together, because the daily run was
capturing the wrong universe and presenting it in a way too long for a phone.

1. **The daily scan is now the full 15-league whitelist, not the 5 softness
   A/B leagues.** Previously `run_daily.py` built its scan set from
   `DEPLOY_ELIGIBLE_TIERS`, so an approved league (Premier League, Serie A,
   Champions League) never appeared on the board at all — "wide eyes" existed
   only in the dead `orchestrator --all` CLI path. Scan and deploy are now
   decoupled: **SCAN is wide, DEPLOY stays narrow.** The CALL still draws only
   from softness A/B, capped at 6 (ID402 unchanged); the odds pull stays A/B
   only, so scan-only leagues' prices don't burn the free-tier quota. Showing
   a competition is not staking it.

2. **THE CALL is ranked by expected value, not model conviction.**
   `build_deploy_shortlist` ranked by the model's strongest probability because
   no price existed at board time. Markets are now attached before the
   shortlist is built, so `best_mes_ev` exists — the ≤6 now fill with the
   highest-EV fixtures (conviction as the fallback for unpriced rows, e.g. a
   competition with no odds source).

3. **Telegram output is compact tables.** `/produce bet` previously returned
   the 20k-char file board. All channels (`/produce bet`, `/send`, 07:00) now
   show the same compact per-league table board: every league scanned that day,
   each rated fixture with its model prediction and a **Pick** column (the
   recommended prediction), THE CALL with an **EV** column, data flags
   compressed to a one-line count. Full detail remains in the file board and
   `/why`.

**Deferred, honestly:** Champions League / Europa League were originally
considered blocked on a personal TheSportsDB key. They are NOT — see the
next entry: the IDs were resolved by name+country on the test key
(lookupleague.php, spaced probes), and the ACTIVE capture path for the
current season is the odds feed (soccer_uefa_champs_league_qualification),
which works with the existing key and no registration. TheSportsDB's own
UCL/UEL feed lags weeks behind; a personal key would not change that.

**Authority:** Architect. These change what appears on the board and the
shortlist, so they were not taken under the auto-ratification grant.

---

## 2026-08-04 · ID82 Elo Rating Engine — ratified by the ARCHITECT

**What:** A second, independent rating engine (`engine/elo.py`), ported from
DataEngine v277.1 sheet ELO RATINGS. It appears on the board as a **second
opinion beside Dixon-Coles**, never blended into it.

**Authority:** Architect. This changes what appears on the board, so it was not
taken under the auto-ratification grant.

**Formulas, as specified in ID82:**

```
E(home) = 1 / (1 + 10^((ELO_away − ELO_home − 65) / 400))
New ELO = Old + 20 × GD_mod × (Result − E)
```

Home advantage 65 Elo, K-factor 20, base 1500. `GD_mod` was undefined in ID82;
the standard World Football Elo taper is used and documented in the module.

**Why a second engine.** Dixon-Coles rates attack and defence within a pool
where everyone plays everyone — which is exactly why it cannot compare a Dutch
club to an English one. Elo updates a single number from results in any
competition, so cross-league comparability is structural.

It is also **genuinely independent**: different inputs (results and margins,
not goal counts), different mathematics (sequential updating, not maximum
likelihood), different failure modes. That is what ID403 means by independent
factors — and it is the opposite of ID130's convergence model, where sixteen
prediction sites reading the same public information agree by construction.

**Measured, 2024 Champions League league phase, each match predicted from
ratings that existed BEFORE it:**

| Configuration | Brier | Top-pick hit |
|---|---|---|
| Elo, 1 pass | 0.5545 | 57.3% |
| Elo, 3 burn-in passes | 0.4482 | 68.1% |
| **Elo, 6 burn-in passes** | **0.4306** | 67.4% |
| Dixon-Coles *(in-sample)* | 0.4247 | 69.4% |

Uniform guessing scores 0.667. Elo matches Dixon-Coles while being fully
out-of-sample; the Dixon-Coles figure is flattered by having been fitted on
those very matches.

**Known limit, stated rather than hidden.** Elo cannot separate leagues that
never meet. Championship clubs play no continental football, so Burnley and
Leeds still rate above Real Madrid in the pooled model. Ratings are comparable
only across leagues that actually play each other. This does not affect the
intended use (UCL/UEL, where every club has ≥8 continental matches).

**Scope of this ratification:**
- ✅ Elo shown as a second opinion on every board fixture
- ✅ `divergence()` raises a REVIEW flag when the engines differ by >12pp
- ❌ Does **not** change deploy gating (ID402 softness A/B, ≤6, unchanged)
- ❌ Does **not** feed MES, staking, or the Phase 3 gate

---

## 2026-08-03 · Sources ratified under the Section 12 grant

Functional, non-breaking source additions. Shown plainly, reversible in one word.

| Source | Tier | Role |
|---|---|---|
| **thesportsdb.com** | T2 | Upcoming fixtures. Community-editable, so fixtures stamp ○ SINGLE-SOURCE until a second source provides F2 quorum. |
| **the-odds-api.com** | T1 | Live entry prices — the missing piece for HR30 numerical MES and HR46 CLV logging. |
| **api-football.com** | T1 | Fallback history for competitions football-data.co.uk does not carry. Free tier stops at 2024, so anything sourced here is flagged STALE and is not calibration-grade (13.2). |

**Conference League (API-Football id 848)** is used as a cross-league
**calibration bridge only** — 108 league-phase matches that sharpen the shared
European scale. It is **not** ratified as a competition to bet; that would be
an HR34 whitelist change and remains Architect-only.

---

## Corrections to the source record

**`CRO` does not exist.** The framework's source table listed Croatia as
football-data.co.uk extra-league code `CRO`. Verified 2026-08-03: `/new/CRO.csv`
returns 404, and `/new/CRA.csv` is **Brazil**. Croatia is absent from
football-data.co.uk entirely. HNL history now comes from API-Football (stale-flagged).

**ID130 (v285.3) remains superseded.** Its Tier A list promotes Statarea to
PRIORITY, while master v303.15 §7.1 and `verification/id403.py` both mark it
REJECTED. Its convergence model (9+ of 16 sources agreeing ⇒ Ƈ-1 eligible)
treats correlated tipster sites as independent factors, which is the
self-certification failure ID403 exists to prevent — and it selects for public
consensus, which is where value is thinnest.

---

## 2026-08-04 · ID405 Market Gate — ratified on backtest evidence

**What:** Two markets are blocked from carrying capital. `engine/softness.py`
`BLOCKED_DEPLOY_MARKETS`, enforced in `run_daily.log_paper_legs`.

| Market | Mean CLV | t | Legs | Placebo on same market |
|---|---|---|---|---|
| 1X2 Away | **−1.883%** | −4.515 | 606 | −1.707% (also negative) |
| Over 2.5 | **−0.716%** | −2.783 | 442 | — |

**Why it is safe to ratify without further sign-off:** the gate only ever
NARROWS the deploy pool. It cannot admit a market that was previously allowed,
so it reduces exposure rather than extending it. Capital authority is unchanged.

**Effect on the whole backtest:** removing these two markets moves overall mean
CLV from **−0.404% to +0.326%**, and turns the model from behind
always-favourite (−0.404 vs −0.047) to ahead of it (+0.326 vs +0.165).

**Away is a market property, not a model bug.** Random selection loses on away
wins too (−1.707%). This is favourite-longshot drift: long prices drift longer
toward the close, so anyone backing them early loses to the line. There is no
model fix; the market is the problem.

---

## 2026-08-04 · Findings recorded — NOT acted on

Three measurements that change what the framework can claim. None triggers a
rule change here; all three are the Architect's to decide on.

**1. The softness ranking shows no measurable CLV advantage.**
With away legs excluded, tier A/B scored **+0.084%** and tier C/D **+0.075%** —
a difference of **+0.008pp** on 588 vs 1270 legs. The earlier apparent −0.354pp
A/B disadvantage was the away effect, concentrated in A/B leagues, not softness.

*Not proposing removal.* ID402's A/B restriction is a capital-safety mechanism;
dropping it would widen exposure to the most efficient markets in football on
evidence that is null, not negative. The honest statement is that softness is
**unproven**, not disproven.

**2. The model is not the source of the observed CLV.**
On draws alone — the model's single best market — random selection scored
**+0.729% (t=3.466)** against the model's **+0.617% (t=2.179)**. Whatever
positive CLV exists after the market gate comes from **which markets are taken**,
not from the model's probability estimates.

**3. Nothing here is statistically significant.**
On the clean market set the model reaches +0.326% at t=1.722, against
always-favourite +0.165% and random +0.217%. The margin over random is ~0.1pp.
The MD2 Pressure Test's own bar of 100+ settled picks is the more defensible
gate than HR51's 30 — at 30 legs the standard error cannot separate a real edge
from zero.

**Honest status, unchanged:** an excellent informed process, NOT a demonstrated
profitable edge. CLV logged forward: still zero.

---

## 2026-08-04 · Pre-season stress test — PASSED

**What:** `tests/stress_test.py` — 31 checks across six stages, exercising
every path and every failure mode I could reach.

| Stage | Checks |
|---|---|
| 1. Suite regression | 5 test suites, all green |
| 2. Engine invariants on real data | Attack centred, rho fitted (not clamped), Elo zero-sum, 1X2 sums to 1, overs monotonic, no 0% outcomes |
| 3. Safety gates under direct attack | PHASE=2 refuses every stake value, ID405 blocks a 85% away win and 98% Over 2.5 from becoming a Pick, domain lookalikes rejected, T3 aggregators cannot verify, CLV sign correct, HR35 date guard holds |
| 4. Live pipeline end-to-end | run_daily.run() completes in 4.5s and produces a 19k-char board |
| 5. Failure injection | Unknown league / thin history / chunker overload — every one degrades honestly to NO DATA — PENDING |
| 6. Scheduler | launcher.log confirms today's run fired and exited 0 |

**Two failures on the first pass were caught and named as TEST bugs, not
framework bugs:** an under-sized chunker input (2.5k chars against a 3.9k
limit) that couldn't force a split, and a scheduler assertion that
mis-sliced the log tail. Both fixed; both were the kind of test that would
have silently passed forever without actually checking anything.

**What this proves:** the instrumentation is sound. The CLV number, once it
accumulates, will mean what it says.

**What this does not prove:** that the model has an edge. Only the forward
log will settle that. Backtest evidence still stands: +0.326% mean CLV over
2952 legs at t=1.722 — not statistically significant, and the surviving CLV
comes from market selection (ID405) rather than model probabilities.

**Pre-season readiness gate: CLEARED.**

---

## 2026-08-05 · Telegram board rebuilt for the phone — by order of the ARCHITECT

**What the Architect asked:** "The Telegram output keeps giving me too many
information I don't need." The phone message was to become a compact table of
the day's fixtures + predictions (no market columns), plus the day's
recommended pick — a 2/3/4-leg parlay — drawn from ANY rated game that day
(even Champions League-only days), with the probabilities shown. Header and
flag-count line were explicitly kept.

**What was built** (all in `output/produce_bet.py`, one render path feeds the
scheduled run, `/send` and `/produce bet`):

1. **`⭐ TODAY'S PICKS` recommendation.** The day's highest-probability
   predicted RESULTS (home / draw / away), capped at **4 legs**
   (`RECOMMEND_MAX_LEGS`); 2+ legs become a parlay whose combined chance is the
   product of the legs, stated honestly as the chance *all* legs win, with the
   caveat that parlay legs are not independent. A predicted **away win is never
   a recommendation leg** (ID405 — proven-negative market), though the scan
   table still shows it honestly as the prediction.
2. **Per-league fixture tables.** Every fixture that day is one row inside a
   code fence — `Fixture | Prediction` (e.g. `Fenerbahçe 56%`); unrated rows
   stay visible as `NO DATA — PENDING` (HR35). Market columns, xG/DC lines and
   EV text moved off the phone to the saved board and `/board`, `/why`.
3. Header, `⚠ N data flag(s)` line and the honest-edge/capital-authority
   footer retained. The old `⭐ RECOMMENDED — THE CALL` (deploy-shortlist only)
   and the `_compact_fixture`/`_compact_pick` helpers were replaced; xG's third
   opinion now renders only on the wide board (`tests/xg_test.py` updated).

**HR35 guardrail intact:** nothing is fabricated to look complete — `NO DATA —
PENDING` remains the honest fallback, and the honest-edge statement still
heads the footer.

**Note on provenance:** the previous "TODAY'S PICKS" telegram format
(commit `80d9dc1`, from the second Claude session) did not match the
Architect's answers to the rebuild questions (it stripped the header/flags and
kept only deploy-eligible picks). It was replaced by this entry's design.

## 2026-08-05 · WhatsApp delivery (official Meta Cloud API) — ID406

**What the Architect asked:** deliver the daily board to WhatsApp too — "the
same" as Telegram: same picks, same daily board text (whatever
`render_telegram_board` produces — the Architect-approved `OLP XDV — DAILY
BOARD` push with the `⭐ TODAY'S PICKS` parlay). Chose the **official Meta
Cloud API** (no ban risk, free tier) and **push-only** scope (no command
daemon).

**What was built:**

1. **`output/whatsapp_deliver.py`** — a sender mirroring `output/notify.py`'s
   discipline exactly: `send_whatsapp(body) -> (ok, notes)`, never raises,
   retries transient faults 3×, refuses to send when credentials are missing
   (unconfigured ⇒ silently off — the framework behaves exactly as before).
   Reuses `notify._stamp` + `notify._chunk` so the WhatsApp message is
   **byte-identical** to the Telegram push. Because the 7am push is
   **business-initiated**, it is sent as a **template message** (Meta rule:
   free-form text only works inside the 24h customer-service window); the
   template body is a single `{{1}}` placeholder carrying the full text, so one
   template serves any content. Over-cap bodies are split into a few messages.
2. **`.env` keys** — `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_TO`, `WHATSAPP_TEMPLATE_NAME` (default `olp_daily_pick`),
   `WHATSAPP_LANGUAGE` (default `en`). Commented placeholders only — no values
   baked into the repo.
3. **`run_daily.py` wiring** — after the Telegram delivery succeeds, the same
   text is pushed to WhatsApp when configured. WhatsApp is the **copy** channel,
   not the source of truth: a failure is logged but **never fails the run**
   (Telegram remains phone-critical). `--no-whatsapp` CLI flag +
   `WHATSAPP_ENABLED=0` toggle.
4. **`tests/whatsapp_deliver_test.py`** — 7 mocked-network checks (URL/auth/
   template payload, retry, persistent failure, env-missing guard, requests-
   missing guard, chunking, explicit-param override). All green; the existing
   suites (telegram_commands, engine_regression, stress 31/31, smoke, stress2)
   stay green.

**Guardrails:** Telegram delivery failure still fails the run (unchanged).
WhatsApp is additive and inert until the Architect registers a Meta app and
drops the credentials into `.env`. Nothing here touches capital, staking,
fabrication, verification, or the honest-edge statement.

**Known constraint (not a bug):** a real (non-test) WhatsApp Business number
needs an **approved template** for the business-initiated daily push; approval
takes hours and may require business verification. Until then the channel is
verified on Meta's **test number** (templates usable immediately, recipient
whitelisted as a test recipient).

**Authority:** Architect — plan approved before build; additive delivery
channel under the auto-ratification grant, no bright-line behaviour changed.

## 2026-08-06 · Email copy channel + recalibration SHADOW mode — ID407

**What the Architect asked** (both answered explicitly): (1) the official
WhatsApp template approval was taking hours, so add an **instant, zero-approval
second channel** → **email (SMTP)**. (2) the brain's self-adaptation is gated
on 15 settled CLV legs (currently none) — the Architect asked why it can't
adapt on its own; the answer is the honest-edge discipline (fast
self-adaptation = overfitting the backtest = fabricated edge), and the
Architect chose a **SHADOW mode** to watch the signal build without applying it.

**What was built:**

1. **`output/email_deliver.py`** — SMTP sender mirroring `notify.py` /
   `whatsapp_deliver.py` discipline exactly: `send_email(body) -> (ok, notes)`,
   never raises, retries transient faults 3×, refuses to send when credentials
   are missing (unset/empty ⇒ silently off). Reuses `notify._stamp` so email
   carries the **same stamped text** as Telegram/WhatsApp. Email has no length
   limit → one message, subject `OLP XDV — Daily Board <date> · <phase>`.
   `.env` keys (commented = off): `EMAIL_USER`, `EMAIL_APP_PASSWORD`,
   `EMAIL_TO`, `EMAIL_SMTP_HOST` (default smtp.gmail.com), `EMAIL_SMTP_PORT`
   (default 587). Wired into `run_daily` after WhatsApp — best-effort copy,
   never fails the run; `--no-email` flag + `EMAIL_ENABLED=0` toggle.
2. **`engine/recalibration.shadow_adjustments(rows)`** — the WOULD-BE
   adjustment for every market with ANY settled evidence, including below the
   `MIN_LEGS` gate, same bounded formula. **NEVER applied** — the engine only
   changes once a market crosses `MIN_LEGS`. `run_daily` surfaces it as a
   `SHADOW calibration (below gate, NOT applied): …` flag line, distinct from
   the applied `Calibration active:` line and never repeating markets already
   live. Currently renders nothing (no settled leg has a closing line yet) —
   honest NO DATA — PENDING, exactly as designed.
3. **Tests** — `tests/email_deliver_test.py` (5 mocked-SMTP checks) and
   recalibration tests 8–9 (shadow traced-but-inert below gate; shadow ==
   applied above gate; empty with zero evidence). WhatsApp test helper fixed to
   clear ALL `WHATSAPP_*` keys — the real `.env` now carries credentials and
   the suite must be hermetic against it. All suites green (email, whatsapp,
   telegram_commands, engine_regression, recalibration, stress, smoke).

**Guardrails:** both additions are additive and inert until configured; email
needs a Gmail app-password (user-side, one-time); shadow never touches THE
CALL's EV. No change to capital, staking, fabrication, verification, or the
honest-edge statement.

**Authority:** Architect — both directions chosen explicitly before build;
additive under the auto-ratification grant, no bright-line behaviour changed.


---

## 2026-08-06 · CL-LIVE closing-line capture — the structural CLV gap closed

**Why:** the Phase-3 gate needs >=30 paper legs with logged CLV. A closing
line is what makes CLV measurable, but until now ONLY the football-data
archive (CL-ARCHIVE) could produce one — on football-data's schedule (next
morning) and only for the markets it publishes (Danish Superliga, an
extra-schema league, carries 1X2 closing prices but NO totals). A paper leg
therefore could not earn a CLV number until the archive published, and some
markets could never earn one at all. HR46's CL-LIVE path existed on paper but
was never built.

**What was built** (`clv/closing_capture.py`, wired into `run_daily._run`,
built by Architect authorization "do what is best for the framework"):

1. `capture_closing_lines(log, leagues, odds_index=, now=)` records the live
   feed's price near kickoff as the leg's closing line, capture path CL-LIVE.
   The daily run passes the `odds_index` it already fetched for the day's
   rated leagues — capture costs zero extra quota. Also runnable standalone:
   `python -m clv.closing_capture [league ...]` (a scheduled pass near kickoff
   closes legs the archive cannot).
2. **The honesty rule (HR35) is the core of the design:** a price captured
   HOURS before kickoff is an intraday price, not a closing line — treating it
   as the close would manufacture CLV out of nothing. Capture fires only inside
   the window: no earlier than `CLOSING_WINDOW_MINUTES=60` before kickoff, no
   later than `KICKOFF_GRACE_MINUTES=10` after it (once in-play the API stops
   quoting h2h anyway). Kickoff is read from the-odds-api `commence_time`; the
   leg's `match_date` must match the fixture's kickoff DATE (HR48-style guard —
   a same-pairing meeting on another day is never closed). A leg outside the
   window stays PENDING, never estimated.
3. `grade_open_legs` now: prefers the canonical archive close (upgrades a
   CL-LIVE close to CL-ARCHIVE when the archive publishes); keeps the CL-LIVE
   close when the archive has none (the leg still earns its CLV, no false NO
   DATA flag); and only a leg with NO closing line from either path is NO DATA
   — PENDING.

**Tests:** `tests/closing_capture_test.py` — 9 checks (window maths, in-window
capture, intraday/in-play refusal, date guard, first-capture-wins, entry-less
and dateless refusal, archive upgrade, CL-LIVE survival, honest NO DATA). All
20 suites green.

**Guardrails untouched:** nothing estimates, nothing overwrites a real close,
capital/staking/fabrication rules unchanged. Entry prices remain CL-LIVE at
pick time; this only ADDS a closing path, never changes one.

## 2026-08-06 · Four operational upgrades — run watchdog, gate telemetry, team-alias suggestions, auto-retry — ID408

**What the Architect asked:** "is there any logic that needs to be upgraded and
new logic added" — and chose ALL FOUR proposed upgrades.

**What was built:**

1. **Run watchdog** — `monitor/run_watchdog.py`. The daily run logs loudly
   *inside* itself, but nothing noticed when the run **never happened** — the
   disabled scheduler task that produced today's silent no-push is exactly that
   class. The watchdog verifies `logs/daily_<date>.log` contains BOTH
   `run completed OK` AND a `delivered N part(s) to Telegram` line (a built
   but undelivered board is NOT a completed run — same rule run_daily enforces
   by raising), and when either is missing sends a best-effort Telegram ALERT.
   Never raises, so it can't crash its own scheduler. `--date`/`--logs-dir`
   args; designed to run on its own schedule after the 07:00 slot.
2. **Gate telemetry** — `Brain.leg_telemetry()` + a "Road to the gate" block
   in `/stats`. Honest trajectory: legs logged / with closing line / settled,
   the CLV-capture rate (fraction of SETTLED legs that earn a closing line),
   observed legs-per-day, the sustained CLV-leg production rate, and a
   projected days-to-gate. **0.0 capture survives as a real signal** ("settled
   but NO closing line — capture is failing") distinct from None ("nothing
   settled yet"); when no CLV legs are being produced the projection reads
   NO DATA — PENDING (HR35).
3. **Team-alias suggestions** — `engine/cross_league.suggest_aliases()`.
   When a fixtures-feed name isn't in the fitted pool (e.g. Sabah FK), the
   board flag now lists likely pool matches (accent/case-folded exact match
   scores1.0, difflib fuzzy follows; a genuinely unknown team yields nothing).
   **Suggestions only — never auto-applied**: an unverified alias is a silent
   mis-rating (the same bright line verify_aliases() enforces).
4. **Auto-retry** — `run_daily._retry_transient()`: a network fetch is retried
   once on a transient fault (connection reset / DNS / timeout) so one blip
   doesn't degrade today's board to NO DATA. Quota exhaustion and logic errors
   pass straight through to the caller's own guard. Applied to the live-odds
   pull; the CL-LIVE capture is additionally wrapped so a bug or transient
   fault there can never kill the whole daily board (it degrades to a flag,
   legs stay PENDING).

**Tests:** `tests/run_watchdog_test.py` (7), `tests/gate_telemetry_test.py` (3),
`tests/team_alias_test.py` (5), `tests/retry_transient_test.py` (5). All prior
suites re-run green (brain_store, brain_orchestrator, engine_regression,
email, whatsapp, telegram_commands, recalibration, fixtures_cache, monitor,
closing_capture, multi_league, xg, softness_mes, clv_backtest, stress, stress2,
smoke). The telemetry tests caught and fixed a real honesty bug: `if rate` was
treating a legitimate 0.0 capture rate as "no data".

**Bright lines untouched:** nothing here estimates, staked capital, or changes
the honest-edge statement; aliases are suggested not applied; the projection is
labelled a projection and reads NO DATA when it cannot be stated.

**Authority:** Architect — all four directions chosen explicitly before build;
additive operational upgrades under the auto-ratification grant, no bright-line
behaviour changed.

---

## 2026-08-06 · CUP TRAINING LOOP — monitor EFL Cup / J-League / Europa quals live, teach the brain

**Why:** the daily run logs paper legs only for deploy-eligible (softness A/B)
leagues. The cups — EFL Cup, J-League, Europa League quals, Champions League
quals — involve clubs from the 15 approved leagues but were never logged, so
the brain never saw them. The Architect authorised (2026-08-06): log a paper
leg on EVERY cup fixture — O1.5 as the baseline plus every priced market
(1X2, O2.5, U2.5) — to train the brain. The monitor settles each completed
match, so the brain accumulates hit-rate + CLV evidence per market.

**What was built** (Architect authorization):

1. `monitor/cup_training.py` — new module.
   - `log_cup_legs`: O1.5 on every fixture (outcome evidence, `model_prob=None`
     — the monitor does not run the DC model; a fabricated probability would
     poison the engine's hit-vs-model residual) + priced markets where the feed
     quotes them, with the REAL price. Idempotent.
   - `settle_cup_legs`: matches completed events to logged legs on (home, away,
     kickoff DATE), settles hit via canonical rules. Never overwrites; never
     matches the wrong fixture (HR48).
2. `monitor/run_monitor.py` — watches EFL Cup + J-League + Europa quals
   alongside UCL quals (`TSDB_ONLY_SPORTS` routes Europa to TheSportsDB since
   it has no odds key), logs cup legs each pass, captures CL-LIVE closing lines
   for priced cup legs, settles completed matches. `run_once` + `_live_watch`
   both covered.
3. `pipeline/odds.py` — SPORT_KEYS gains EFL Cup (`soccer_england_efl_cup`) and
   J League (`soccer_japan_j_league`), both verified live 2026-08-06.
4. `clv/closing_capture.py` — `capture_closing_lines` takes a `phase` param so
   cup-training legs can earn closing lines too (default unchanged).

**PHASE SEPARATION (the whole point):** cup legs are written with
`phase="cup_training"`, NOT `"phase2_paper"`. The brain's legs mirror +
`clv_by_market` read them, so the engine LEARNS from the cups, while the
Phase-3 capital gate counts ONLY `phase2_paper` — a flood of cup legs can
never graduate the framework by volume. Training the brain is not a back-door
to capital.

**Honest constraints:** Europa quals have no price source (Odds API carries
no Europa/Conference key) -> those legs are outcome-only (O1.5 evidence, CLV
NO DATA — PENDING). The predictions table stays empty for cup legs (its
`model_prob` is NOT NULL; cup legs honestly carry None). Model-vs-reality
comparison remains with the board predictions, which the daily run prices.

**Verified live 2026-08-06:** the monitor now sees Bristol City v Walsall
(EFL Cup, 18:45) and Jagiellonia v Rangers / Lech Poznań v KÍ Klaksvík /
Lincoln Red Imps v Omonia (Europa quals) — the exact fixtures the Architect
named.

**Tests:** `tests/cup_training_test.py` (5 checks: O1.5+priced logging, phase
separation, idempotency, settle to brain, gate exclusion). All 25 suites green.

## 2026-08-06 · EFL Cup on the board + odds-quota override + fixtures never dropped — ID409

**What the Architect asked:** "we have EFL and uefa qualifications match today
why is not showing in the framework". The framework returned an honest empty
board — and the investigation showed the fixtures EXISTED in the data but were
invisible for three stacked reasons, each fixed or answered:

1. **EFL Cup was not scanned.** `Bristol City v Walsall` (tonight) is a real,
   priced event in the Odds feed (`soccer_england_efl_cup`, active+verified)
   — but the EFL Cup was not in the 15-league whitelist, so the framework never
   looked. **Fixed:** `SOFTNESS_TIER["EFL Cup"] = "D"` (scan-only, NEVER a
   capital pick — same tier as Champions League/La Liga) + odds SPORT_KEY. The
   daily board now reads `Leagues: 16` and lists the EFL Cup table.
   *(The other Claude session independently added the EFL Cup + J-League odds
   keys for its cup-training loop in cffa59c; reconciled — one key, no
   duplication.)*
2. **The odds quota guard blocked the only source for these fixtures.** The
   free Odds API was at 34/500 (floor 40), and `check_quota()` refused to
   spend — so the odds-derived fixture path (the ONLY current-season source for
   EFL/UCL-qualifier fixtures: TheSportsDB lags, API-Football's free tier stops
   at 2024) went silent for the rest of August. **Architect authorized
   spending.** `QUOTA_HARD_FLOOR = 5`: FIXTURE CAPTURE may now spend below 40
   down to 5 (one spend buys a 6h-cached fixture LIST — far more coverage than
   a routine price pull), while the routine PRICE-PULL floor (40) is untouched
   for every other caller. A fixture-capture call can never spend the last of
   the month.
3. **A league with fixtures but no history dropped them all.** `scan_one_league`
   early-returned `[]` when `load_league` raised (EFL Cup has no football-data
   CSV) or when history was <20 matches — so even a league with real fixtures
   showed nothing. **Fixed:** `_render_unrated_fixtures()` — such fixtures now
   appear on the wide-eyes board as **NO DATA — PENDING** rows with an explicit
   reason ("no fitted history — fixture listed, not rated"), never silently
   dropped (HR35).

**Honest answers to the rest of the question:** the UCL-qualifier events in the
feed are the **Aug 11** round (Sabah FK v AGF Aarhus, Bodø/Glimt v Union SG,
…), not today — the Aug 5 round already played. The EFL Championship season
opens **Aug 14**. If the Architect saw a qualifying fixture dated today, it is
likely a Europa/Conference qualifier — which the framework has NO source for
(no active odds sport key; documented gap).

**Verified live 2026-08-06:** full pipeline board shows
`EFL CUP → Bristol City v Walsall  NO DATA — PENDING`.

**Tests:** `tests/quota_override_test.py` (5: floor ordering, price-pull still
blocked<40, fixture-capture allowed<40, hard floor respected, EFL Cup tier-D);
`tests/multi_league_test.py` updated (thin-history league now renders NO DATA
rows instead of an empty board — the honest contract). All suites green
(quota_override, fixtures_cache, multi_league, softness_mes, engine_regression,
brain_orchestrator, telegram_commands, closing_capture, smoke).

**Bright lines untouched:** EFL Cup is scan-only, never deployable; the
fixture-capture spend stops at the hard floor (the month can't exhaust); NO
DATA rows carry no fabricated probability.

**Authority:** Architect — EFL Cup inclusion and the quota spend both chosen
explicitly; additive under the auto-ratification grant.

---

## 2026-08-06 · EVENTSDAY FALLBACK — today's cup qualifiers reach the board (ID410)

**Why:** the Architect asked why Europa League qualifiers (Jagiellonia v
Rangers etc.) were not displaying on today's board. Investigation: the scan's
TheSportsDB path used `eventsseason.php`, whose feed LAGS WEEKS BEHIND for
continental qualifiers (verified live — Europa League 4481 showed July-only
events while the real Aug 6 qualifiers were invisible), so nothing landed in
the TODAY-only window.

**What was built:**
- `data/thesportsdb_fixtures.py`: `fetch_today(league, day)` — pulls the
  `eventsday.php` feed, the same source the monitor already watches these
  matches on. Already-played and team-name-missing rows excluded (HR35).
- `orchestrator.py`: when the season feed returns nothing in the window and
  `days_ahead==0` (today-only board), falls back to `fetch_today` before the
  odds feed, flagged ("fixtures from eventsday (season feed lags)").

**Verified live 2026-08-06:** the daily board now shows all 3 Europa League
quals (Jagiellonia v Rangers, Lech Poznań v KÍ Klaksvík, Lincoln Red Imps v
Omonia Nicosia) as honest NO DATA — PENDING rows — the same matches the
cup-training monitor settles for the brain. EFL Cup (Bristol City v Walsall)
was already on the board via the other session's ID409.

**Tests:** `tests/eventsday_fallback_test.py` (3 checks). All 26 suites green.

## 2026-08-06 · WEB DASHBOARD replaces WhatsApp, enriches Telegram — ID412

**What the Architect asked:** "build a web app or app for the framework to
solve the whatsapp issue and telegram". The WhatsApp channel had been a
recurring liability (token expired again this session; Meta template approval
for business-initiated messages). The Architect chose, explicitly: **web
replaces WhatsApp**, Telegram keeps pushing the morning summary, and the full
rich board lives at a URL — a **local dashboard first, hostable** so it can be
opened from anywhere.

**What was built (all stdlib-only, no pip — matches the repo's ethos):**
- `webapp/schema.py` — the board JSON contract. `run_daily` now writes
  `output/boards/board_<date>.json` next to the .txt each run (date, phase,
  leagues, the serialized BoardFixture list, data flags, gate status +
  leg telemetry, and the already-rendered ⭐ picks text so the web never
  re-implements the pick rule and drifts from the phone board). Additive and
  cheap; `--no-web` skips it.
- `webapp/render.py` — plain-language, phone-first HTML from that JSON: header,
  ⭐ TODAY'S PICKS, THE CALL (with EV), per-league fixture tables (NO DATA —
  PENDING rows shown, never dropped — HR35), the Phase-3 gate strip, ⚠ flags
  (collapsible), and the honest-edge + capital-authority footer ALWAYS present.
  Colours follow the dataviz method: status colours only (good/warning/
  serious), each with an icon + label, never colour alone.
- `webapp/server.py` — stdlib `ThreadingHTTPServer`, READ-ONLY over the boards
  + the brain: `/` (→ today), `/board/<date>`, `/history`, `/stats`, `/why`,
  `/api/board.json`, `/api/stats.json`. A missing date is an honest **404**
  (never a guess); traversal is blocked; the server never writes to the repo
  (tested).
- `webapp/export.py` — writes a self-contained `webapp/site/` (index.html +
  board.json + stats.json + README) ready for any static host — the "open it
  anywhere" half. Hosting setup (account + URL) is a short follow-up needing
  the Architect.
- `webapp/start_server.bat` — double-click launcher (binds 0.0.0.0 so a phone
  on the same Wi-Fi can open the board).
- **WhatsApp retired by default:** `WHATSAPP_ENABLED` now defaults to `0`
  (module + tests kept — reversible). `BOARD_URL` env appends a "Full board:
  <URL>" link to the Telegram push once the dashboard is hosted.

**Verified 2026-08-06:** live `run_daily.run(send=False)` wrote the JSON; the
server served today's board, history, stats, /why and the JSON API from localhost;
the export produced a host-ready site.

**Tests:** 5 new suites — `webapp_schema` (lossless round-trip, FileNotFoundError,
newer-schema refused), `webapp_render` (picks/call/honest-edge/capital present,
NO DATA shown, tags balanced), `webapp_server` (real HTTP server on an ephemeral
port: 302, 404-not-guess, read-only, JSON API), `webapp_export` (self-contained
site), `webapp_run_daily` (JSON written next to the txt; web=False skips).
**All 31 suites green.**

**Bright lines untouched:** the dashboard is read-only; it never fabricates a
prediction (HR35); WhatsApp's code is retained so nothing is destroyed, only
defaulted off; capital authority and the honest-edge statement are never
trimmed from any view.

**Authority:** Architect — the channel change (WhatsApp off by default) and the
web dashboard were both chosen explicitly in answer to the question.

---

## 2026-08-06 · ENGINE CONSENSUS — majority vote across DC/Elo/xG (ID412)

**Why:** the Architect reviewed ScoreGPT's methodology (scoregpt.app/
methodology): five independent frontier LLMs each analyse a match blind, a
meta-layer takes a MAJORITY VOTE on the result + averaged scoreline, and
every prediction is graded against the real result afterward. The Architect
chose to add the same *structure* over OLP's three real engines, which
already produce independent 1X2 opinions per fixture but were never combined
into a vote.

**Three decisions confirmed by the Architect:**
1. **Role — display + brain only.** Consensus is computed, shown on the full
   board, and persisted to the brain for learning. It does NOT change what is
   logged — DC stays canonical for paper legs / CLV / calibration.
2. **Render surface — full board + /why only.** The phone board stays lean
   (2026-08-05 decision intact); no consensus text on Telegram.
3. **Quorum — majority of available engines.** 2-of-2 or 2-of-3 agreement =
   consensus; 1-of-1 (a lone engine is not a consensus) or a 1-1/1-1-1 tie =
   NO CONSENSUS (shown honestly). Any disagreement sets `split=True` — the
   divergence guardrail, now extended to cover xG (the existing
   `engine_divergence` flag only compared Elo vs Dixon-Coles).

**What was built:**
- `engine/consensus.py` — pure vote logic. Each engine's pick is the argmax
  of its own 1X2; averaged 1X2 = mean of the available engines' probabilities
  (the ScoreGPT "averaged" analog).
- `output/produce_bet.py` — `BoardFixture.consensus` field + CONSENSUS render
  line in the per-fixture block (after the xG third opinion). A no-majority
  split renders "NO CONSENSUS — engines disagree" in full view, never smoothed.
- `orchestrator.py` — computes the consensus for every RATED fixture.
- `run_daily.py` — persists consensus 1X2 rows (`model_engine='consensus'`)
  only when a majority exists; a split is never persisted (HR35: not a
  prediction). The rows grade against reality like any other model opinion.
- `brain/report.py` — `/why` lookups read back the consensus line.

**Tests:** `tests/consensus_test.py` (9 checks: quorum rules, render, phone
leanness, brain persistence). All 33 suites green.

---

## 2026-08-06 · BOOKMAKER ENGINE — equal 4th vote in the consensus (ID413)

**Why:** the Architect asked for "more data" and named the bookmaker as the
next engine. The three existing engines (Dixon-Coles goals model, Elo result
history, xG chance quality) all predict from *modeled* inputs. The bookmaker
is different: its odds are the aggregate of real money — the sharpest single
calibration source in football. The ScoreGPT structure gains a fourth,
genuinely independent voter.

**Two decisions confirmed by the Architect:**
1. **Equal 4th vote.** The market's devigged implied 1X2 joins DC/Elo/xG in
   the consensus majority. With all four agreeing you get "4 of 4 engines".
   Because the market is the best-calibrated signal, the consensus leans
   toward it, and model-vs-market divergence becomes a *stronger* warning
   (the market dissents explicitly, not just per-market).
2. **Proportional devig.** `p_i = (1/odds_i) / Σ(1/odds_j)` over
   home/draw/away — the standard 3-way margin removal. Implied probs sum to
   exactly 1, so they fit the existing vote/average machinery. HR35: refuses
   a two-price "1X2" (would fabricate the missing side).

**Scope unchanged from ID412:** display + brain only. The bookmaker opinion
renders on the full board ("Fourth opinion — bookmaker, real-money aggregate,
margin removed") and persists to the brain as `model_engine='bookmaker'`
rows, graded against reality like any other opinion. It NEVER changes what is
logged — DC stays canonical for legs/CLV/calibration. The phone board stays
lean. Scan-only leagues honestly show NO DATA (odds are pulled only for A/B
deploy leagues, quota protection).

**What was built:**
- `engine/markets.py` — `implied_1x2(fx)`: proportional devig of the full 1X2.
- `engine/consensus.py` — `compute_consensus(..., market_probs=None)`; the
  majority rule (`agreeing > n/2`) already generalizes to 4 (3-of-4 = consensus,
  2-2 = NO CONSENSUS).
- `output/produce_bet.py` — `BoardFixture.market_probs` + render line.
- `run_daily.py` — computes `implied_1x2` in the odds-attach loop and
  RECOMPUTES the consensus with the market (orchestrator's 3-opinion consensus
  predates the odds); persists `model_engine='bookmaker'` rows.
- `brain/report.py` — `/why` lookups read back the bookmaker row.
- `webapp/schema.py` — serializes `market_probs` + the consensus dict.

**Tests:** `tests/bookmaker_engine_test.py` (9 checks: devig math, HR35
refusals, 4-engine quorum, render, persistence) + a 4-engine case in
`consensus_test.py`. All 34 suites green.

---

## 2026-08-06 · Multi-source data redundancy layer — ratified under the auto-grant

**What the Architect asked:** "fix all data gap forever get multiple api as
backup for intelligence gathering". The daily board has been gapped by any one
provider going down (a TheSportsDB season-feed lag, an odds quota dip, a free
API-Football plan error all produced NO DATA — PENDING on their own).

**What was built:** `data/multi_source.py` + `data/multi_source_concrete.py` —
a unified redundancy fabric over every data type the pipeline fetches:

- **Fixtures** now fail over in priority order: TheSportsDB (season feed →
  eventsday for today-only) → odds-derived fixtures → API-Football (paid-plan
  fallback). One provider down degrades to the next, never to NO DATA.
- **History / current results / xG / odds** get the same multi-source treatment.
- **Circuit breakers + health metrics** per source: after repeated failures a
  source is paused (not hammered), and the run reports which provider served
  each league + any OPEN circuit on the board.

**Integration:** `orchestrator.scan_one_league` now calls
`get_fixtures()` instead of the hand-rolled 4-step try-chain (same priority
order, now with circuit breakers + health). `run_daily` surfaces the health
report per run. `webapp/render.py` got two bugfixes so the ScoreGPT-restyled
dashboard imports and runs again (missing paren on an implicit string join;
tuple→list on elo/xg probs after JSON serialization).

**Honest limits:** API-Football's free tier CANNOT see the current season
(deterministic `{'plan': ...}` error) — it stays a paid-plan-only fallback, and
the layer reports that honestly rather than guessing. Odds quota floors still
protect the free-tier month. History results do NOT mix football-data (current
season) with API-Football (free tier stops at 2024) — wrong-season data would
misrate, so history keeps its single-source integrity.

**Authority:** Architect (auto-grant — additive redundancy, no change to
capital, staking, fabrication, verification or honest-edge behaviour).
Tests: `tests/multi_source_test.py` extended (failover + all-down exhaustion);
all 36 suites green.

---

## 2026-08-06 · WhatsApp channel KILLED — by ARCHITECT order

**What the Architect decided:** after the template watcher looped silently for
hours on a stale Meta access token (`Authentication Error` — the token, not the
template), the Architect said "kill whatsapp". The channel is now dead at two
layers:

1. `run_daily.py` already retired it by default (`WHATSAPP_ENABLED` default 0,
   ID412 — the web dashboard replaced it); the recurring template-approval
   watcher cron job has been deleted.
2. `.env` credentials are now **commented out** (`WHATSAPP_ENABLED=0` plus all
   `WHATSAPP_*` keys) so the channel CANNOT send even if the flag is flipped.
   The module short-circuits with "not set — delivery skipped" instead of
   burning a Meta API call.

**Honest record:** the failure was the access token, not the template. If
WhatsApp is ever wanted back, a fresh token + an approved template are the
prereqs, and it needs Architect sign-off to re-enable (ID412 stands: the web
dashboard is the "anywhere" home).

**Authority:** Architect. Delivery-channel change only — no capital, staking,
fabrication, verification or honest-edge behaviour changed. All 36 suites green.

---

## 2026-08-08 · 1X2 Home added to the deploy market gate — 10-league CLV pressure test

**Why:** the Architect asked for a full pressure test: *"check all the 15 leagues
for this CLV pressure test, fix it, make it profitable."* The instruction was to
narrow deploy to what the evidence actually supports — not to manufacture an
edge, and specifically to apply the honest controls the framework already has.

**What the pressure test found (all 10 leagues with a football-data.co.uk
closing-odds source; the other 5 — Champions League, Europa League, Danish
Superliga, Ekstraklasa, HNL — have no CLV source and cannot be measured):**

| Market | 2425 mean CLV | 2526 mean CLV | 2425 placebo | 2526 placebo | verdict |
|--------|--------------|--------------|--------------|--------------|---------|
| 1X2 Away (already blocked) | -1.457% (t=-5.17) | -0.283% | — | — | market drift |
| Over 2.5 (already blocked) | -0.770% (t=-4.25) | +0.084% | — | — | market drift |
| 1X2 Home | -0.640% (t=-2.33) | -0.625% (t=-2.46) | -0.524% (t=-2.73) | -0.137% | negative both seasons |
| 1X2 Draw | +0.404% (t=2.01) | +0.593% (t=2.68) | +0.575% (t=4.34) | +0.197% | placebo >= model — drift, not skill |
| Under 2.5 | +0.054% | +0.233% | +0.092% | -0.236% | no signal |

**The honest reading — and why the gate narrows rather than widens:** the draw
market's positive CLV is *not* a model edge. Random selection on draws returns
+0.575% (2425) — better than the model's +0.404%. That is favourite-longshot
drift in the draw direction, the mirror image of the away-market drift that
already blocked 1X2 Away. Claiming draw as a demonstrated edge would be exactly
the "beautifully designed wrong number" the framework exists to refuse. So the
pressure test *narrows*: **1X2 Home** shows the same negative-for-everyone
pattern as Away (model loses both seasons; random loses 2425) and is now blocked.

**What changed:** `engine/markets.py` `BLOCKED` gains `HOME` (canonical key path)
and `engine/softness.py` `BLOCKED_DEPLOY_MARKETS` gains `"home win"` (display-name
path). `DEPLOYABLE` is derived from `BLOCKED`, so the deploy shortlist now draws
from **1X2_DRAW + UNDER_2_5 only** — narrower, one-way, exactly ID405's rule.
The board still *shows* home-win probabilities (prediction is not deployment);
it just cannot carry capital or headline THE CALL as a deployable pick. On the
narrowed universe the backtest is positive in both seasons (+0.199% 2425,
+0.351% 2526, t=2.78 on 2526) — but that residual is drift, NOT skill, and this
entry records that explicitly so it is never mistaken for a demonstrated edge.

**Phase 3 gate unchanged:** still 0 logged legs with CLV, still paper-only, still
requires Architect V7 sign-off. Blocking home does NOT get the framework closer
to capital — it gets the deploy universe closer to honest.

**Authority:** Architect (via direct instruction to pressure-test and narrow to
evidence). Restriction-only — narrows what may carry capital, cannot admit any
previously-excluded market. No capital, staking, fabrication, verification or
honest-edge behaviour changed. All 40/41 suites green (stress2 is a slow
concurrency stress test, run separately with extended timeout).

---

## 2026-08-10 · STRICT SINGLE-DAY PRODUCTION (reverses the 2026-08-07 3-day rolling window) — by order of the ARCHITECT

**What the Architect asked:** "when I have trigger production, it should only
show me that this production… it should only produce matches of fixtures or
competition for today. If I click tomorrow, it should do that for tomorrow. And
even if it's going to do it automatically for me in the daily run… don't produce
into the future. A production that is triggered for that [day] is for that day
alone."

**What changed (commit HEAD):**

1. **Every production is pinned to ONE calendar day.** `run_daily.run()`
   gains `target_date` (YYYY-MM-DD, default None = today). The board, accas,
   produced-bet record, acca/booking-code files and web payload are all written
   for that date, and only fixtures whose `kickoff_date == board_date` survive.
   This **reverses** the 2026-08-07 ratification of a rolling `days_ahead=3`
   scan window — today-only (`days_ahead=0`) was then reversed for producing
   empty early-August boards; the Architect now explicitly wants the honest
   quiet board back. The `days_ahead` default becomes `0` (today only) in both
   the CLI and the library; the scan window only ever widens far enough to
   REACH a future `target_date`, and the kickoff-date filter is the hard
   guarantee that nothing from an adjacent day survives.
2. **Manual trigger honours the selected date.** `webapp/server.py`
   `POST /api/trigger-board?date=<d>` now passes `target_date=<d>` into
   `run_daily.run()` (it previously parsed the date and then ignored it while
   running `days_ahead=3`). Choosing tomorrow produces tomorrow's board only.
3. **Strict-day pacing.** A today-only scan falls back to TheSportsDB's
   `eventsday` endpoint for any league with no today fixture in its cached
   season feed; the free key rate-limits at ~1 req/s, so the scan loop now
   paces per-league calls (`time.sleep(1.1)` when scanning today only) to avoid
   429ing a league that DOES have today's fixture into a false NO DATA.
   Inert for future-date runs (cached season feed, no throttle needed).

**Verified against real sources (2026-08-10, the 16 approved leagues + EFL Cup
+ Austrian Bundesliga):** Monday 10 Aug has **exactly 2 fixtures** — `Silkeborg
v Odense` (Danish Superliga) and `Santa Clara v Nacional` (Primeira Liga) —
confirmed via TheSportsDB season feed (cached) and `eventsday`. Every other
approved league has zero fixtures that day. This matches the Architect's
expectation ("very few matches today"). A quiet day is now an honest quiet
board, never a wider net.

**Authority:** Architect (direct instruction, 2026-08-10). Restriction-only in
the scan sense — it narrows what a production can contain to one day and cannot
admit an off-day fixture. No capital, staking, fabrication, verification or
honest-edge behaviour changed; a fixture without a provable kickoff date is
refused rather than guessed (HR35). All webapp test suites green.
