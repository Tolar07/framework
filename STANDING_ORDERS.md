# ARCHITECT'S STANDING ORDERS — OLP XDV (main)

These are the Architect's standing rules for the framework. They live on `main`
and are enforced by `tests/standing_orders_test.py`: if a merge, a combine, or a
new session ever reverts one of them, that test fails. **Read this file before
changing selection, delivery, phase or market logic.** Changing any order below
requires the Architect's explicit instruction — not an agent's own judgement,
and not "ratified on backtest evidence".

| # | Order | Where it lives |
|---|---|---|
| 1 | **Phase 3 — live capital, Architect-deployed.** No "Phase 2 / paper calibration" wording in anything the Architect reads. The system never places a stake; the Architect deploys. | `config.PHASE = 3` |
| 2 | **All markets open.** Home, Draw, Away, Over 2.5, Under 2.5 are all deployable. No market is blocked (Architect 2026-08-10; restored 2026-10-01 after the combine re-introduced the old ID405 block). | `engine/markets.py BLOCKED = {}`, `engine/slate.py BLOCKED_DEPLOY_MARKETS = {}` |
| 3 | **Deploy odds band: 1.20 – 2.00, safest 1.50.** Nothing above 2.00 is ever deployed; nothing below 1.20. | `engine/slate.py DEPLOY_ODDS_*` |
| 4 | **Winnable picks only.** A deploy pick must be one the model rates ≥ 50% to win — never a fallback the model expects to lose. | `engine/slate.py DEPLOY_MIN_MODEL_PROB` |
| 5 | **Canonical board** `##########OLP XDV#########` — TABLE 1–4, real SportyBet booking codes. **No cap** (Architect 2026-10-02): every in-band fixture is a single with its own code; ALL picks are grouped into accas of 4–5 legs (strongest first), each with its own code; and into mega slips of ≤26 legs (SportyBet can't take 78 on one slip), each with its own code. | `output/produce_bet.py`, `engine/slate.py` |
| 6 | **Telegram delivery twice daily:** ~10 PM Lagos for the NEXT day's fixtures, ~7 AM Lagos refresh for today. Production board on pick days + a heartbeat EVERY day. Failure alert on a broken run. | `.github/workflows/daily.yml` |
| 7 | **Coverage:** 16 leagues + UEFA Nations League + League One, League Two, National League and FA Cup (2026-10-02), all priced from SportyBet. | `pipeline/odds_sportybet.py` |
| 8 | **Live match monitoring source: Flashscore.co.uk.** | (monitoring) |
| 9 | **Never fabricate** (HR35): no invented prices, scores or constants. Missing data shows as NO DATA — PENDING. | everywhere |
| 10 | **Every fixture gets production; nothing dropped** (2026-10-02). Alternative markets are open and bookable: Double Chance, Over/Under 1.5 / 2.5 / 3.5, BTTS. A fixture the model can't rate is priced MARKET-IMPLIED (SportyBet prices, margin removed, marked ᴹ, no edge claimed) instead of NO DATA. Every fixture's row shows its in-band pick, odds and an alternative market. | `engine/markets.py`, `engine/market_implied.py`, `orchestrator.py` |
| 11 | **Pick the outcome each match is most likely to produce — where the model AND the bookmaker agree.** Each fixture's pick is the in-band market with the highest consensus (model + de-vigged market). ★ BANKER = straight win, both agree ≥70% (backtest: ~82% won, ~+4% over 290 picks, two seasons). ✓ SAFE = both agree. ⚠ SPLIT = they disagree by >7pp — shown, never deployed. Singles and accas rank BANKER first. Evidence: `backtest/SELECTION_STUDY.md`. | `run_daily.py`, `engine/slate.py` |
| 12 | **Full market ladder.** Every full-time SportyBet market is scored for every fixture — 1X2, Double Chance, Draw No Bet, Asian & European handicaps, Over/Under lines, team goals, BTTS, clean sheet, win to nil, goal range, Multigoals, DC/1X2 & goals combos. Picks rank on the chance the bet actually **wins** (a void is not a win). A line whose price contradicts the book's own 1X2/goals prices by >8pp is skipped as mislabeled. Under-goals picks give way to a non-Under outcome within 3pp (Architect preference). | `engine/full_markets.py`, `run_daily.py` |
| 13 | **The model sees this season, not just last.** Domestic models fit on last season + the current season, weighted to recent matches (half-life 240 days). Backtest: better accuracy, ~94% of matches rated (vs ~66%), smaller gap to the market, fewer SPLITs, better SAFE picks. Evidence: `backtest/RECENCY_STUDY.md`. | `orchestrator.py` |
| 14 | **Every fixture on the slips** — where the model and SportyBet disagree, the bookmaker's pick is followed (ᴮ BOOK; its pick won 73.1% vs the model's 71.0%). | `run_daily.py` |
| 15 | **Certainty + 50%+ accas.** Every single shows a certainty rating — how sure we are its chance % is right: HIGH (model and SportyBet within 3 pts), MEDIUM (within 7), LOW (disagree or one source only). Every day, 3-leg accas with a combined chance of 50%+ are built from HIGH then MEDIUM legs only (never LOW), each with its own code, listed first in ALL CODES. The 1.20 floor stays. | `run_daily.py`, `output/produce_bet.py` |
| 16 | **Results loop.** Every board's picks are recorded (`output/picks/`) and graded from Flashscore (regular-time results only); the heartbeat carries a scorecard (W-L, hit %, profit at 1 unit, by tier and certainty; slips landed). | `engine/picks_ledger.py`, `data/flashscore_results.py` |
| 17 | **Team news.** Injuries/suspensions (FotMob, weighted by market value) flag picks and lower certainty; every 20 min a pre-kickoff check re-tests picks against the confirmed XI and alerts on Telegram when the team a pick depends on is weakened or rotated. Nothing is auto-dropped — the Architect decides. | `engine/team_news.py`, `news_check.py` |
| 18 | **Market-anchored chance.** A pick's chance = 75% SportyBet (margin removed) + 25% model. The model alone over-states chances by 4-5 pts; leaning on the market keeps the % honest. Evidence: `backtest/ANCHOR_STUDY.md`. | `engine/slate.py`, `run_daily.py` |
| 19 | **xG in the model (top 5 leagues).** The model's scoreline grid = average of the goals model and an xG rating (Understat, 240-day half-life) — more accurate than goals alone in both test seasons. Squad value stays a team-news weight only (no free history to validate it in the model). Evidence: `backtest/XG_STUDY.md`. | `engine/xg_model.py`, `orchestrator.py` |
| 20 | **Closing-line value on every pick.** In the last 35 minutes before kickoff the pre-kickoff job records SportyBet's price for each pick; CLV = entry / closing − 1 (positive = the price shortened after we picked — the fastest proof of skill). Average CLV and % of picks beating the close are in the daily scorecard. | `news_check.py`, `engine/picks_ledger.py` |
| 21 | **Staking tied to proven edge.** Every single shows a suggested stake (% of bankroll): quarter-Kelly up to 2% only where a tier's edge is proven; 0.5% break-even; 0.25% losing; halved for LOW certainty. Slips: 50%+ accas 0.5%, accas 0.25%, megas 0.1%. Stop-loss: a tier whose last 20 graded picks lost ≥ 6 units is PAUSED. Backtest priors give way to live results. | `engine/staking.py` |
| 22 | **Automatic learning from results.** Every graded pick corrects the next board, per market family (1X2, Double chance, handicap, team goals …) and per league: shift = (wins − expected wins) / (picks + 30), counted only once a family/league has 10+ results spread over 3+ match days (Architect 2026-10-04: one good day must not turn the next board into one market), capped at ±10 pts per pick. A family or league that keeps losing has its chances cut and drops below the 50% floor on its own; one that keeps winning rises. The heartbeat lists the corrections in force. | `engine/learning.py`, `run_daily.py` |
| 23 | **AI Survivor (heartbeat lineage).** Paper lineages, genesis £100. A lineage only bets on a pick that clears the **lineage bar** (Architect 2026-10-03): ≥ 80% chance, HIGH/MEDIUM certainty, no injury/rotation flag, price no worse than ~2% under fair, pre-match; strongest lineage gets the strongest pick, stake 1. With no such pick it **waits** (alive) — it is never filled from the rest of the board, and a held pick that drops below the bar before kickoff is withdrawn. WIN pays stake × (price − 1) and the lineage splits into 2 offspring at once (a child inherits any pick the winner already holds); ONE LOSS is extinction; max 16 alive (raised from 8, Architect 2026-10-03), slots allocated so no survivor is ever deleted; a lineage with no eligible fixture that day simply waits (stays alive); one reseeded at £1 if all die. Graded from Flashscore; the heartbeat shows generation, lifeforce, results and holdings. Continued from the laptop state of 19 Sep (rebuild: `scripts/rebuild_survivor.py`). | `engine/survivor.py`, `data/survivor/` |
| 24 | **Value-aware picks + automatic news swap (2026-10-02).** Among each fixture's outcomes within 2 pts of the top win chance (narrowed from 4 after backtest/MARKET_STUDY.md), the one with the best expected value (chance × price) is picked — safety first, then value, so heavy-margin markets (e.g. Multigoals) give way. Every pick's EV is recorded and the scorecard compares +EV vs −EV results. A pick that depends on a team weakened by injuries/suspensions/rotation (CAUTION/RISK) swaps automatically to the likeliest alternative within 6 pts that the news doesn't touch. | `run_daily.py`, `engine/picks_ledger.py` |
| 25 | **Price drift guard + live calibration (2026-10-02).** Backtest of 29,000 picks (backtest/MARKET_STUDY.md): picks whose price drifts out 5%+ before kickoff lost −10.9%; picks that shorten 5%+ made +2.6%. The 7am refresh demotes any pick that drifted 5%+ since the 10pm board to LOW certainty (out of 50%+ accas, stake halved); 1–3 h before kickoff each pick's price is re-read and a 5%+ drift is alerted on Telegram with its slips. The scorecard shows Brier score, log loss and "said X% → won Y%" calibration buckets. | `run_daily.py`, `news_check.py`, `engine/picks_ledger.py` |
| 26 | **Live capital bylaw (Architect 2026-10-03, amended same day: SportyBet instead of Bet365).** Live capital is authorised on **SportyBet only**, as a test: **£1 (or the naira equivalent) per acca** on the day's accas. The Architect places them by hand by loading each acca's SportyBet booking code (Load code → stake → Place Bet); the system never logs in to a betting account and never places a bet. Everything else stays paper. Results are graded from the picks ledger like every slip. | Architect |
| 27 | **Free multi-source verification (2026-10-03).** No paid API, ever. Every board fixture is looked up in ESPN's free scoreboard and football-data.co.uk's fixture files; two independent sources agreeing stamps it ✓ VERIFIED (ID403). A match another source lists postponed/cancelled is ⚠ CONFLICT and is not deployed (it stays on the board with the reason). Every SportyBet price on the board's day is checked against bet365 (football-data) and DraftKings (ESPN) with margins removed; a difference of more than 5 pts is shown on the board, never hidden, and does not change the pick. | `verification/fixture_check.py`, `pipeline/odds_verify.py`, `data/espn_fixtures.py` |
| 28 | **Country + league on every pick (2026-10-04).** Every pick the Architect reads names where it is played, so it can be found on the betting site: club matches as country · league (Spain · La Liga 2), national-team and continental matches by competition (UEFA Nations League). On the board's tables (own column), every acca and 50%+ acca leg, THE PICK, team news, the price check, AI Survivor and the pre-kickoff alerts. A league with no country on file shows its own name — never a guessed country. | `engine/competitions.py`, `output/produce_bet.py` |
| 29 | **bet365 board, to the Architect only (2026-10-04).** SportyBet and bet365 offer different bets (bet365 has no "win to nil — no"), so the same run also builds a bet365 board: each deploy pick is kept when bet365 offers it, otherwise replaced by the likeliest winnable outcome bet365 does offer (50%+, SportyBet price in band, Under-goals last, never one the team news flags); a fixture with none is listed, never dropped. Grouped by country + league, singles and accas, no booking codes. No bet365 price is invented: each pick shows DEPLOY AT (break-even for its chance, never below 1.20) and SportyBet's price for reference. Sent as its own Telegram message to the Architect only (`TELEGRAM_OWNER_CHAT_ID`, else the board's chat) and saved as `output/boards/bet365_<date>.txt`. The bet365 list is the full betting market — every market the ladder scores, Double Chance & Goals included — except win to nil "no" (Architect 2026-10-04); the bet365 market names are a draft until the Architect confirms them. Live capital stays SportyBet-only (order 26). | `output/bet365_board.py`, `run_daily.py` |
| 30 | **17 Sep spec items kept (Architect 2026-10-04).** The board header carries a Run ID (`OLPXDV-<UTC yyyymmdd-hhmm>-<6 hex>`, printed at the start of the run and written to the run log) and "Fixtures scanned · Verified"; a board without a valid Run ID is never sent — it is saved, the run fails and the failure alert fires (HR59). NO-DATA fixtures leave Table 1 for one collapsed line under it — listed, never dropped (HR35); no line when there are none. Table 1 is grouped by competition, strongest pick first, and a board too long for one message splits between competitions, never mid-row; a competition too long for one message continues with "(cont.)". | `output/produce_bet.py`, `output/notify.py`, `run_daily.py` |
| 31 | **Alternative-market accas (Architect 2026-10-04).** Besides the main slips, every deploy fixture gets an alternative leg — its likeliest winnable in-band outcome (≥50%, 1.20–2.00) from a DIFFERENT market family than its main pick, never one the team news flags — and those legs are grouped into their own accas of 4–5 (TABLE 3B, "Alt A, B …"), each with its own SportyBet code, listed in ALL CODES, recorded and graded in the picks ledger. Table 1's alternative market is the same leg. It spreads the risk over different outcomes of the same matches; it does not raise the hit rate. Not part of the £1 live test (26) unless the Architect says so. | `output/produce_bet.py`, `run_daily.py`, `engine/picks_ledger.py` |

## Telegram output — everything that reaches your phone

This is the one record of the Telegram output (Architect 2026-10-04). Each
line points to the order that sets it; change the order, not this list.

**1. The board** — pick days, ~10 PM Lagos for tomorrow and ~7 AM refresh (6)
- Header: `##########OLP XDV#########`, date, Run ID, fixtures scanned · verified (5, 30)
- TABLE 1 — every rated fixture, grouped by competition: Country · League (28),
  AI pick + win % with ★ BANKER / ✓ SAFE / ᴮ BOOK / ⚠ SPLIT (11, 14), odds,
  alternative market (10), O1.5/O2.5 and DC/BTTS, ✓ VERIFIED / ○ / ⚠ source (27),
  ᴹ market-implied (10); NO-DATA fixtures on one line under it (30); mega code (5)
- TABLE 2 — deploy singles in the 1.20–2.00 band, ≥50% (3, 4): chance, odds,
  certainty (15), stake (21), own SportyBet code (5); price check (27); team news (17); mega code (5)
- TABLE 3A — 3-leg 50%+ accas from HIGH/MEDIUM legs, own codes (15)
- TABLE 3 — every pick in 4–5-leg accas, strongest first, own codes; mega slips ≤ 26 legs (5)
- TABLE 3B — the same fixtures on a different market each, in 4–5-leg alt accas, own codes (31)
- TABLE 4 — the primary single and Acca A
- Footer — honest edge, odds band, calibration; ALL CODES as the final message (5)
- Sent only with a valid Run ID; long boards split between competitions (30)

**2. The bet365 board** — its own message, to you only, after the board (29)

**3. The heartbeat** — every day, even with no picks (6): scorecard and
calibration (16, 25), closing-line value (20), staking and stop-loss (21),
learning corrections (22), AI Survivor (23)

**4. Pre-kickoff alerts** — every 20 min, 09:00–20:40 UTC: confirmed-lineup
news (17) and price drift (25), each with the slips that carry the pick

**5. Run alerts** — a failed run (6), and a board slot that never ran (`watchdog.yml`)

**6. Commands** — /board /status /verify /why /log /note /debrief, answered hourly (`commands.yml`)

**7. Supervisor status** — after every board run: ALL CLEAR or the issues
found, problems first (`supervisor.yml`, `monitor/supervisor.py`)

**8. Weekly review** — Mondays ~08:51 Lagos: results by market family and
league, slips landed, learning, proposals (`weekly.yml`, `scripts/weekly_review.py`)

The Telegram Output Spec of 2026-09-17 (`docs/obsidian-vault/Telegram Output
Spec.md`) is kept as the Architect's text but is SUPERSEDED wherever it
disagrees with these orders: no 2-acca cap (5), 1.20–2.00 band not 1.50 (3),
real booking codes not PENDING (5), the four-table board not the stacked
`render_production_board` blocks (5). Its Run ID, NO-DATA line and
competition-boundary splitting were kept as order 30.

_Last updated 2026-10-04._
