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
