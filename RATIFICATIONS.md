# OLP XDV — Ratification Log

Append-only, per HR33. Each entry is written **at the time of the change**
(HR44), not reconstructed afterwards. Authority is recorded per entry:
the Architect's bright lines (capital, staking, fabrication, verification,
honest-edge) are never auto-ratified — Section 12.

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
