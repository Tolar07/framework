# OLP XDV — Ratification Log

Append-only, per HR33. Each entry is written **at the time of the change**
(HR44), not reconstructed afterwards. Authority is recorded per entry:
the Architect's bright lines (capital, staking, fabrication, verification,
honest-edge) are never auto-ratified — Section 12.

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
