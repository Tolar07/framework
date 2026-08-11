# OLP XDV — COMPILED REFERENCE DOCUMENT

> **REPO CROSS-CHECK (Claude Code, 2026-08-08):** Saved into the working repo (`docs/`) on 2026-08-08 and cross-checked against the live codebase. The cross-check target named below, `OLP_XDV_MASTER_v303.15.md`, does **not** exist in this repo as of 2026-08-08 — the live authorities are `RATIFICATIONS.md` (append-only) + the code + `ARCHITECTURE.md`. This compiled reference describes the framework's **real-money era (April–July 2026)**; the repo is the **Phase-2 paper-only rebuild**. Stale or missing claims are annotated inline as `REPO CROSS-CHECK:` callouts.

### Built by Claude.ai chat, [today's date], from confirmed conversation search
### CROSS-CHECK AGAINST: OLP_XDV_MASTER_v303.15.md — that file was purpose-built on 3 Aug 2026 by a session with direct working context. If it exists in your Claude Code project, IT is more authoritative than this reconstruction. This document exists because you asked for a file directly from me, and because a second, independent version is a useful check against staleness or gaps in the first.

> **REPO CROSS-CHECK:** `OLP_XDV_MASTER_v303.15.md` is **absent** from this repo (verified 2026-08-08). Only `RATIFICATIONS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `EUROPEAN_COMPETITIONS.md` exist at root. So this compiled reference is the closest available copy of the historical spec; the repo itself is the authority.

**Honesty notice (HR35 applies to this document too):** this was compiled from `conversation_search` results — snippets and summaries, not a guaranteed-complete raw archive. Everything below is something I actually found and can trace to a real past session. Nothing below is invented to fill a gap. Where something is known to be incomplete, it's marked as such rather than smoothed over.

---

## SECTION 1 — SOURCE TRUST REGISTER (ID404) — "the whitelist"

Ratified 22 July 2026. Governing principle: **trust tier sets the corroboration requirement — it never exempts a capital-relevant datum from independent cross-check.** "Independent" excludes two pages of the same site.

| Source | Role | Tier | Status |
|---|---|---|---|
| FootyStats.org | Primary AMBER feed — base rates, fixtures, results, per-club O2.5/BTTS | T1 | ✅ |
| Football-Data.co.uk | Historical results + CLOSING odds, CSV, all 5 deploy leagues (Scotland/Netherlands/Belgium main; Denmark/Poland extra), back to 1993/2000 | T1 | ✅ |
| Transfermarkt | Structured squad / transfer / market-value | T1 | ✅ |
| FBref | Structured squad/xG stats | T1 | ✅ |
| Wikipedia season pages | Composition, promotion/relegation, personnel | T1 | ✅ (per-page recency caveat) |
| SPFL.co.uk / club sites | Official Scotland | T1 | ✅ |
| Predictz.com | Facts only, cross-source, NO tips | T2 | ✅ |
| BBC Sport / Sky Sports / ESPN | Free-text news, F2 partners | T2 | ✅ |
| Flashscore | JS-locked — Architect-fed only, cannot be automated | — | ⚠️ |
| Statarea / Stats Perform | Tipster / paywalled | — | ❌ REJECTED |

**To verify next (HR52):** The Odds API / Betfair Exchange (live odds — Football-Data is weekly/historical, not in-play); ClubElo (cross-league ratings, only if Euro qualifiers ever ratified).

> **REPO CROSS-CHECK:** `verification/id403.py` SOURCE_TRUST (as of 2026-08-08) agrees in substance with two corrections: **predictz.com is T3** (not T2), and **flashscore.com is REJECTED** (never usable, not even a lead — stricter than this table's "Architect-fed only"). `statarea.com` REJECTED ✓. Two sources missing from this table: **`thesportsdb.com` T2** (ratified 2026-08-03, HR34, the upcoming-fixtures source) and **`api-football.com` T1** (historical results). Both were added after the 22 July ratification.

**⚠ KNOWN CONFLICT:** an earlier (8 April 2026) version of a "whitelist" exists with completely different domains — flashscore.com, sofascore.com, fotmob.com, bbc.co.uk/sport, espn.com, nba.com, sportingnews.com, whoscored.com, fbref.com, transfermarkt.com — treated as clean citable sources. That list is SUPERSEDED by the table above (e.g. Flashscore is no longer a clean source, it's Architect-fed only). If Claude Code or the repo is reading the April version, that is the likely source of any "missing whitelist" confusion. Both files should be checked for and the April version archived/removed if still present.

> **REPO CROSS-CHECK (RESOLVED):** the April-version whitelist is **not present anywhere in this repo** (verified 2026-08-08 — none of sofascore/fotmob/whoscored/nba.com/sportingnews appear as a source anywhere; the only trace of flashscore is as `REJECTED` in `verification/id403.py:48`). The conflict is already resolved in the code — nothing to archive or remove here.

---

## SECTION 2 — LEAGUE WHITELIST (ID401) — 18 leagues

**GREEN (tool-fed):**
Premier League · La Liga · Serie A · Bundesliga · Ligue 1 · Champions League · Europa League · Conference League (added 2026-08-10)

**AMBER (FootyStats + F2 verification):**
Scottish Premiership · Belgian Pro League · Eredivisie · Championship · Primeira Liga · Danish Superliga · Ekstraklasa · HNL

*Turkish Süper Lig dropped to Ring-2 watchlist. Stage 2 leagues (Segunda, 2.Bundesliga, Serie B, Ligue 2) locked until 20 Championship predictions logged.*

**Data coverage caveat (confirmed directly, not assumed):** Football-Data.co.uk does NOT cover Champions League, Europa League, Conference League, or HNL — no continental competitions in that source, and Croatia isn't in its country list. Those four leagues need a different historical source before they can be backtested the same way as the other 12. Conference League IS modelled (cross-league fit pool, API-Football id 848) — the remaining gap is a current-season FIXTURES source; see `competition_catalogue.py`.

> **REPO CROSS-CHECK (updated 2026-08-11):** softness tiering was **fully removed** — the GREEN/AMBER feed-tool split and the evidence-based A/B/C/D tiers are gone. `engine/softness.py` is deleted; `engine/leagues.py` holds the unified 18-league whitelist (`WHITELISTED_LEAGUES`) and `is_deploy_eligible()` (whitelist membership only). Every whitelisted league is scan- AND deploy-eligible — no tiers, no cap, no `SOFTNESS_PAUSED`.

---

## SECTION 3 — THE ENGINE (v3.1)

**Dixon-Coles goal model, xG-fed.** Two paths: xG-fed (preferred — FootyStats attack/defence strengths, win-prob becomes cross-check) and win-prob fallback (tool-fed GREEN fixtures, promoted clubs). Low-score correction via Dixon-Coles tau, rho = −0.13.

**Five bugs found and fixed during the rebuild:**
- **BUG1** — mismatch totals inflated (a 95%-favorite read as 4.47 expected goals / 82% O2.5). Fixed: supremacy maps to goal difference only; total anchored to league average with a hard clamp.
- **BUG2** — probabilities not summing to 100% were accepted silently. Fixed: normalized-with-note or rejected.
- **BUG3** — no home advantage (home/away splits mirrored each other). Fixed: per-league home/away split added.
- **BUG4** — (low-score correlation) — Dixon-Coles tau correction applied.
- **BUG5** — (referenced in later sessions re: goals-market display always defaulting to "Over" even when Under was favored) — fixed to always show whichever side is ≥50%.

> **REPO CROSS-CHECK:** ✓ matches the current `engine/` suite (Dixon-Coles + Elo + xG/Understat + bookmaker devig + consensus). rho = −0.13 and the goals-display ≥50% fix are in place.

> **INDEPENDENT VALIDATION (2026-08-11):** DC scoring math cross-checked against the reference implementation `RyanSCodes/Dixon-Coles-Football-Predictor` (py3 port of its Monte-Carlo fit + tau correction). Tau formulas are byte-identical between the two. Both fitted on the same 356-match 2015/16 EPL window (pre-07/05/2016) and scored on the same 5 out-of-sample fixtures. Model-agnostic negative log-likelihood on the training window: OLP **1005.7** vs reference **1085.1** (+79.4) — the reference's greedy MC hill-climb lands in a bad local optimum (it rates champions Leicester's attack 0.78 and Man Utd's attack *below Bournemouth's*). Where both fits are sane (2/5 fixtures) they agree ≤5.3pp and track the market; OLP tracks the market correctly on 4/5. **Conclusion: no bug in OLP's DC; the reference repo is not a usable independent sanity band as-is and is NOT wired in.** Evidence (throwaway, outside repo): `external/football-prediction/crosschecks/` (also holds the penaltyblog 7-method de-vig comparison — OLP's proportional devig == multiplicative, and on real 1X2 closing lines the 7 methods agree ≤0.7pp on the longshot, so the method choice is second-order).

---

## SECTION 4 — VERIFICATION (ID403 / ID403.1)

**Tiers:** ✓ VERIFIED (full capital eligible) · ○ SINGLE-SOURCE (no capital alone) · ⚠ CONFLICT (shows both, picks neither) · NO DATA — PENDING · DERIVED (model-only, formula shown inline).

**Folded legacy gates:**
- V2 recency-rejection: live score 15 min · odds 60 min · lineup 180 min · fixture 24h · roster 7 days
- V5 market-alignment: >15pp gap between model and market raises a DIVERGENCE flag
- V7 sign-off: capital clears only when all inputs VERIFIED and Architect explicitly acknowledges

> **REPO CROSS-CHECK:** ✓ the five tiers are exactly `verification/id403.py` (`VERIFIED / SINGLE-SOURCE / CONFLICT / NO-DATA / DERIVED`). V7 survives as the **`ARCHITECT_SIGNOFF`** gate (`webapp/schema.check_client_publish_gate`); V5 survives as the **engine-divergence** flag (`engine/elo.py:divergence`, `engine/consensus.py:split`); the V2 recency windows (15/60/180min, 24h, 7d) do not exist as a standalone mechanism in the current code — they were folded into the tier rules (legacy).

---

## SECTION 5 — MATCHDAY SLATE ENGINE (ID402) — "wide eyes, narrow hands"

Model-only SCAN is wide — every whitelisted league gets scanned every run, whether or not its season has started. THE CALL / DEPLOY draws from the SAME unified pool — softness tiering was **fully removed 2026-08-11** (`engine/softness.py` deleted): every whitelisted league is deploy-eligible, `DEPLOY_POOL_CAP` is gone, THE CALL ranks priced-first then EV/conviction (see `engine/leagues.call_key`), and the odds price pull widens to all 18 whitelisted leagues (quota self-limits via `check_quota`). No `SOFTNESS_PAUSED`, no tier A/B/C/D — nothing left that could be re-enabled.

> **REPO CROSS-CHECK:** ✓ `engine/leagues.py`. Scan = all 18 whitelisted leagues, all deploy-eligible. Deploy gating honours the ID401 whitelist only (`is_deploy_eligible`) and the ID405 market gate (`engine/markets.py` `blocked()`); the ID405 gate is currently OPEN (`BLOCKED = {}`). Softness removal recorded in RATIFICATIONS.md (2026-08-11).

---

## SECTION 6 — OUTPUT CONTRACTS (frozen, v303.11 + HR53)

**PRODUCE BET** — six-part structure: Header (date/mode/phase/leagues/calibration) → THE CALL (deploy shortlist) → THE SCAN (full wide board) → REJECTED/WATCHLIST → DATA INTEGRITY (ID403 tier counts) → HARD RULES + SIGN-OFF.

**VERIFY RESULTS** — graded against 90-minute FT basis only (HR15). FT confirmed by direct URL or NO DATA — PENDING, never guessed.

**HR53 — full-detail mandate:** completeness never overrides honesty. A missing datum renders as "NO DATA — PENDING," never filled to look complete.

> **REPO CROSS-CHECK:** the six-part PRODUCE BET contract now maps to the **webapp/admin** structure (two-tier dashboard, 2026-08-07), not the Telegram phone push. The phone push was deliberately **slimmed** (2026-08-05) to: header → THE CALL (⭐ per-pick lines) → compact per-league scan → footer. Data flags, league counts, calibration line, honest-edge line, market columns/xG/EV moved off the phone to `/board`, `/why`, `/status`, `/stats`, and `/admin`. Nothing lost — but the phone no longer carries the six-part full board. VERIFY RESULTS (HR15, 90-min FT basis) ✓ still the settlement rule.

---

## SECTION 7 — HARD RULES CONFIRMED IN THIS HISTORY

- **HR35** — no fabrication, ever. A missing input is reported as missing, never guessed.
- **HR30** — every capital pick carries a numerical MES (Market Edge Score) — no capital pick without one.
- **HR46** — CLV Log on Lock. A closing line must be captured and logged for every capital/paper leg. This is the instrument that actually separates a real edge from a lucky run — not hit rate alone.
- **HR52 / HR53** — pro-rigor auto-ratification for fixes that add real data sources without weakening any existing check; full-detail-but-honest output mandate.
- **Capital authority** — permanently, exclusively the Architect's. Never automated, never delegated, no exceptions carried across sessions.
- **Odds are Architect-fed** — no readable live-odds source exists; the engine outputs a trigger price, the Architect enters the real market price manually.
- **Banned markets (standing):** Correct Score · Bookings · First Half Under 0.5 · Accumulators >15.00 · NBA spreads ≤2.5 moneylines · NBA Over-bracket capital.
- **Post-mortem fixes (standing):** H2H data capped at 18 months, same division only · 4+ squad absences drops confidence one tier · no simultaneous Team-WIN-high-confidence AND Under 2.5 on the same fixture · dead-rubber fixtures get home −5%/away −confidence adjustment.

> **REPO CROSS-CHECK:** HR30/35/46/52/53 ✓ all live in the code; capital authority ✓ (`config.assert_paper_only()`, hard fail below Phase 3).
>
> **OUTDATED — "Odds are Architect-fed":** odds are now **automated**. `pipeline/odds.py` pulls live prices from **The Odds API** (free tier, `ODDS_API_KEY` set) and, since 2026-08-08, falls back to the **API-Football free plan** (`data/api_football_odds.py`) when the Odds API quota is exhausted. The Architect-fed path survives only as a **`/log` Telegram-command fallback** (`output/telegram_commands.py:200-222`) when no live odds exist.
>
> **OUTDATED — banned markets:** the broad standing list was replaced by the evidence-based **`engine/markets.py` `BLOCKED`** gate. Deployable markets are now **1X2_DRAW + U2.5 only** (commit `7f20792`, 2026-08-08): `1X2_AWAY` was blocked earlier (backtest −2%, t=−5.5) and `1X2_HOME` was added to `BLOCKED` after the 10-league pressure test showed it negative. The board still *shows* home/away probabilities; they just can't carry capital or headline THE CALL.

---

## SECTION 8 — TRACK RECORD (confirmed figures — separate from CLV, which is still mostly ungathered)

- **World Cup knockout tickets (R32/R16/QF):** 4 real SportyBet accumulators, ₦13,000 staked → ₦578,502 returned, 30/31 legs won
- **World Cup R32 mega-acca:** 16 legs, 9/9 settled legs won
- **A ₦496,491 accumulator exists but is QUARANTINED** — the framework itself ruled this does not count as edge evidence, despite winning, due to a process breach. Do not treat it as proof of anything.
- **Mode C (European finals) cumulative:** +₦8,780 across 3 sessions (UEL Final +₦3,680, UECL Final +₦3,100, UCL Final +₦2,000), 8W/4L (66.7%)
- **Overall calibration snapshot (30 May 2026):** 39 picks, 25W/14L (64.1%)
- **Known real losses (part of the honest record, not omitted):** 13 May session (-₦22,780) · 15 May session (-₦22,780) · 16 May FA Cup Final Day, 21 vehicles (-₦17,600)
- **CLV coverage:** genuinely still near zero. Entry prices exist for a handful of legs; closing prices at kickoff are not captured for almost any of the above. This is a real, open gap — not withheld data.

> **REPO CROSS-CHECK:** this track record is **historical (pre-Phase-2) and is deliberately NOT part of the current repo's evidence base.** The repo is Phase-2 paper-only (zero capital, hard-blocked in `config.py`), and the honest-edge statement is explicit that the edge is **not** a demonstrated profitable edge. The ₦496,491 acca stays quarantined. Current ledger (2026-08-08): **12 paper legs, 0 with CLV** — matching the document's "CLV genuinely near zero."

---

## SECTION 9 — AUTOMATION STATUS

- **v303.15 master document** — already compiled 3 Aug 2026, should exist as `OLP_XDV_MASTER_v303.15.md` in the Claude Code project, alongside a lean auto-loaded `CLAUDE.md` carrying the bright lines (HR35, zero-capital phase gate, Architect-only capital, honest-edge caveat).
- **CLV backtest** — `clv_backtest.py` exists and is runnable (walk-forward Dixon-Coles, no look-ahead, flat-stake value bets vs collected odds) — confirmed NOT blocked on live paper legs, since it runs against historical closing odds already in Football-Data.co.uk's CSVs.
- **Phase gate:** capital deployment requires ≥30 Phase 2 paper legs with logged CLV, positive mean CLV, and explicit Architect sign-off (`ARCHITECT_SIGNOFF`). Currently not met — this is the system working correctly, not a bug.
- **Self-correction is bounded, not autonomous:** source-trust scores and calibration-from-outcomes update automatically; any rule, verification, or capital change is PROPOSED by the agent and must be APPROVED by the Architect — never auto-written.

> **REPO CROSS-CHECK:** `OLP_XDV_MASTER_v303.15.md` is **absent** (2026-08-08) — see the top note. `backtest/` exists (`backtest/backtest_report.py`, `clv_backtest` era) and is runnable ✓. Phase gate matches `config.py` ✓. Bounded self-correction ✓ (CLV-gated recalibration is inert until 15 settled legs/market; changes go through RATIFICATIONS.md, Architect-only).

---

## WHAT THIS DOCUMENT DOES NOT CLAIM

- This is not guaranteed to be 100% of everything since April — it's everything I could directly confirm through search in this conversation.
- The full ~197-prediction figure referenced separately has not been fully reconciled against Section 8 above.
- Directive numbers between roughly ID100–ID396 exist in the framework's history but are not individually itemized here — only the ones directly surfaced through search are listed. The master v303.15 document, if intact, almost certainly has the complete numbered list.

---

## REPO CROSS-CHECK — ADDED SINCE (present in the repo but absent from this reconstruction)

- **The Brain** — `brain/olp.db` (SQLite, stdlib): persists fitted model state (content-hash reuse → 15/15 refits→0), every board prediction, and the CLV legs mirror. Schema v5.
- **Two-tier web dashboard** — `webapp/`: public `/dashboard` (trimmed client payload via `schema.trim_payload()`) + authed `/admin` (full internals, Basic auth), static export, and the **approve → publish gate** (`POST /api/admin/publish`; nothing reaches the client without a human approve).
- **Health monitoring** — `monitor/run_health_monitor.py`, `run_watchdog.py`, `dead_mans_switch.py` + Task Scheduler jobs (every 2h + 08:15): verify the 07:00 run happened and alert on silent failure.
- **Bookmaker 4th engine + consensus** — `engine/markets.py` (devigged 1X2) + `engine/consensus.py` (majority-of-4, split guardrail); display + brain only, never changes the logged signal.
- **xG third opinion** — `data/xg_source.py` (Understat, Big-5 + RFPL), `fit_xg`/`predict_xg`; cross-check, not a capital signal.
- **CL-LIVE closing capture** — `clv/closing_capture.py`: records the live feed's price ≤60 min before kickoff as a leg's closing line (HR35: never estimated).
- **API-Football odds fallback** — `data/api_football_odds.py` (2026-08-08): serves Bet365/Pinnacle/WH 1X2 + O/U2.5 when the Odds API free tier is exhausted; today±1 window only.
- **Promoted-club carry-over model** — `orchestrator.py`: a secondary DC model fit on the previous season (2425) rates newly-promoted clubs that the primary 2526 model can't see; genuine new clubs stay honest NO DATA.
- **Produced-bet verification (ID415)** — `bets/produced_bet.py`: settles yesterday's produced picks vs real results in the daily run, automated.
