# STATE.md — Daily Audit & Framework State

> **Daily fixture verification, outcome audit, and knowledge integration.**
> Updated each session with retrospective findings, calibration adjustments, and lessons learned.

---

# CURRENT STATE — as of 2026-10-03

There is ONE framework: `main` of Tolar07/framework, run by GitHub Actions.
Laptop-line code is parked in `legacy/laptop/` (never imported, never run);
the laptop's Windows board task is disabled. Rules: `STANDING_ORDERS.md`.

| Field | Value | Source |
|-------|-------|--------|
| Phase | 3 — live capital, Architect-deployed. The framework never places a stake | `config/__init__.py` (`PHASE = 3`) |
| CAPITAL_ENABLED | True (derived, `PHASE >= 3`) | `config/__init__.py` |
| Telegram delivery | ON — board on pick days, heartbeat every day | `.github/workflows/daily.yml`, standing order 6 |
| Board runs | 20:47 UTC (evening, next day's card) and 05:47 UTC (morning refresh); Routine + cron, duplicate-guarded | `.github/workflows/daily.yml` |
| Missed-run watchdog | 23:17 and 08:17 UTC — starts a slot's board that never ran and says so on Telegram | `.github/workflows/watchdog.yml` |
| CLV log (2026-10-03) | 388 legs logged, 9 with CLV, mean CLV +1.655% | `clv/clv_log.json` via `python scripts/olp_query.py status` |
| Phase 3 CLV gate | NOT MET — 9 of 30 legs with CLV (mean positive) | `clv/clv_logger.py` `phase2_status()` |
| Tests | `python tests/run_all.py` green; `tests.yml` on every push/PR | `.github/workflows/tests.yml` |

**Canonical documents:** `STANDING_ORDERS.md` (rules, test-enforced), this
file (state), `MAP.md` (where everything is kept — repo, history, workspace,
laptop, secrets, Routines), `Rules.md` (HR/ID register only),
`docs/LINEAGE_MERGE_2026-10-03.md` (how the copies became one).
`Decisions Log.md` and `Protected Constants.md` are historical since 3 Oct:
every directive after 31 Aug is a standing order.

## Open items (2026-10-03)

| # | Item | Status |
|---|------|--------|
| 1 | Fixtures reach `○ SINGLE-SOURCE` only — no T1 fixture source (ESPN / football-data fixtures) is wired into the live path, so no fixture is VERIFIED (ID403) | **CLOSED 2026-10-03** — every fixture checked against ESPN + football-data (`verification/fixture_check.py`, standing order 27; Ekstraklasa often still one source) |
| 2 | F2 price quorum (`pipeline/odds_verify.py`, PR #6) merged and tested but not called from the live odds path | **CLOSED 2026-10-03** — switched on (Architect): SportyBet vs bet365 + DraftKings, margin removed, 5 pts; a label only (standing order 27) |
| 3 | Feed team names not matching the model's history (23 fixtures market-priced on 2026-10-03) | **CLOSED 2026-10-03** — `engine/name_match.py` (#51) |
| 4 | A SPLIT pick with no market price crashed the whole daily run | **CLOSED 2026-10-03** — #48 |
| 5 | A dropped GitHub cron was silent (only failures alerted) | **CLOSED 2026-10-03** — missed-run watchdog (#50); it starts the missed run itself, and handles its own cron firing after midnight (#54) |
| 6 | Laptop scheduled data tasks still run against laptop-only files (three `.bat` files missing; tasks failing) | OPEN — retiring them on the laptop (Architect decision 2026-10-03). The workspace journal (`omniroute-test:docs/STATE.md`) still lists ten as "stay on"; the names are in `MAP.md` §9 |
| 7 | Picks showed no country or league, so a pick was hard to find on the betting site (the Architect's request had been lost — in no doc or commit) | **CLOSED 2026-10-04** — standing order 28; labels from `engine/competitions.py` (new file) |
| 8 | bet365 doesn't offer every SportyBet bet (no "win to nil — no"), so SportyBet picks can't always be placed there | **BUILT 2026-10-04** — standing order 29: a bet365 board from the same run, sent to the Architect only (`output/bet365_board.py`, new file). List widened to the full betting market (Double Chance & Goals included; only win to nil "no" left off) by the Architect the same day. OPEN: the bet365 market names (`BET365_MARKETS`) are a draft until the Architect checks them against the app; no free bet365 price feed, so picks show DEPLOY AT, not a bet365 price; bet365 picks are not yet in the picks ledger (not graded) |
| 9 | Telegram output changes were spread over the 17 Sep spec, standing orders and commits, and the spec contradicted the live board | **CLOSED 2026-10-04** — one record: "Telegram output" section of `STANDING_ORDERS.md`; the 17 Sep spec marked superseded where it conflicts; its Run ID header + send gate, NO-DATA line and competition-boundary splitting built (order 30) |
| 10 | 4 Oct morning board was 11/13 Double Chance with no alternative markets: one day's results (DC 22/23 on 3 Oct) moved every pick, and the alternative was taken from a pool narrowed to 3 pts | **CLOSED 2026-10-04** — alternatives from the full in-band pool (#67); learning needs 3+ match days (order 22); alternative-market accas with their own codes (order 31) |
| 11 | Agents and skills only acted when a session called them; nothing checked each board or reviewed results | **BUILT 2026-10-04** — supervisor status after every board (`supervisor.yml`), weekly results review (`weekly.yml`), Claude PR review (`claude-review.yml`, OPEN: needs an `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` secret). Workspace add-ons (closing_edge, sports-skills, graphify, automaton, ruflo, claude-code-action, free-llm-api-resources, external/*) are pointers with no source URL in omniroute-test — nothing to connect until they are pushed somewhere reachable |
| 12 | A pick flagged LOW certainty, drifting price or model disagreement stayed the main pick; its alternative was only shown | **BUILT 2026-10-04** — standing order 32: it switches (⇄) to a steadier agreeing market within 5 pts; the original is graded too and the weekly review compares them |
| 13 | The board went to ONE chat (`TELEGRAM_CHAT_ID`). The laptop line broadcast every board to the chats that pressed /start (`memory/telegram_subscribers.txt`, 2026-08-24 — three besides the Architect); the GitHub Actions line never had that broadcast, and the file was parked in `legacy/laptop/` on 3 Oct | **BUILT 2026-10-04** — order 33: every chat in the `TELEGRAM_SUBSCRIBER_CHAT_IDS` secret gets everything the Architect gets (board, heartbeat, pre-kickoff and run alerts, supervisor status, weekly review) except the bet365 board; the supervisor status flags an empty secret. OPEN: the 12:46 UTC run on 4 Oct saw the secret EMPTY — it must be a *repository* secret on Tolar07/framework. OPEN: the bot token was committed in plain text on 2026-08-16 (`22e057e`, public history) — revoke it with @BotFather and update `TELEGRAM_BOT_TOKEN` |
| 14 | Things the system depends on were scattered: the subscriber list sat only in a parked laptop file, the Routines that start the board were recorded nowhere, four directive logs stopped in August, and the laptop versions of 21 live files survive only in git history | **BUILT 2026-10-04** — `MAP.md`: one list of where everything is kept (workflows and Routine IDs, who gets what, every secret, stored files, parked features, history-only work, the workspace repo and the laptop), read at session start (`CLAUDE.md`), paths test-checked. Records brought in: `docs/records/` (production intent 10 Aug, real-money track record), `data/sportybet/` (SportyBet tournament ids). Stale notes marked HISTORICAL; `Open Questions.md` restored (an agent error overwrote it 27 Aug). OPEN: credentials to rotate (MAP §10), defects found (MAP §11), decisions (MAP §12) |
| 15 | The pre-kickoff check (lineups, price drift, closing prices — orders 17, 20, 25) almost never ran: GitHub ran `news.yml`'s 20-minute cron 6 times in three days | **FIXED 2026-10-04** — one job loops every 20 min 09:00-20:40 UTC (`monitor/news_loop.py`), started by `daily.yml` after each board (the morning board is Routine-started); saves each round; hands itself on before GitHub's 6-hour job limit; a backup cron every 2 h starts it if missing; `tests/news_loop_test.py` |
| 16 | A price logged with `/log` was never graded and never got CLV: it was saved with no match date, and the grader refuses a leg it can't pin to one match | **FIXED 2026-10-04** — `/log Home v Away | Market | price [| YYYY-MM-DD]` finds the match on a recent board (league, date, the board's spelling) or uses the date given; wording it can't settle is refused, nothing half-logged. `/note` and the capital refusal now say what is true. `tests/telegram_log_test.py` |
| 17 | No kickoff time on the board, though the Architect asked for it (17 Sep spec; 19 Sep "the country and the time") — the laptop board had it, the live one never did | **BUILT 2026-10-04** — order 28: KO column (Lagos time) on Tables 1–2, before every acca leg and bet365 single; from SportyBet's event start (FotMob's for deploy picks); PENDING when no source gave a time |
| 18 | Dry runs (`run_daily.py --no-send`, `tests/stress_test.py`) rewrote the real picks ledger, CLV log and boards — on 5 Oct a stress test wrote an unsent 109-fixture board over the real one | **FIXED 2026-10-05** (branch `claude/olpxdv-framework-improvements-40hlc8`) — a dry run works on scratch copies; `tests/dry_run_sandbox_test.py` |
| 19 | BTTS never picked though it landed in 7 of 12 graded fixtures (3–4 Oct) | **STUDIED 2026-10-05** — `backtest/BTTS_STUDY.md`: the model under-rates BTTS by ~3–10 pts; its strongest calls land ~60–67%, so ranking on win chance never picks it. **BTTS CORRECTED 2026-10-05** (Architect: "do both") — `engine/calibration.py` scales the model's BTTS yes/no chance to what landed (raw 45% -> 53%, 75% -> 66%; held-out Brier 0.2502 -> 0.2462), `tests/calibration_test.py`. OPEN: picking BTTS / Over-goals where the price beats fair (Architect approved 5 Oct) — not built: the session's permission check stopped it midway and the partial change was removed |
| 20 | Underdog handicaps in FA Cup ties were the worst picks on 3 Oct: across the board's versions plus-line handicaps won 24/32 (−2.55 units at ~1.22, break-even ~82%) — Enfield +2.5 lost 6–1, Cirencester +3.5 lost 4–0, Dulwich +2.5 lost 5–0 | **BUILT 2026-10-05** (Architect: "stop picking underdog handicaps in FA Cup games") — standing order 38: never scored in FA Cup fixtures, so the likeliest other outcome is picked; `tests/standing_orders_test.py` |
| 21 | Results were learned from only through the learning shift (still waiting on 50 results); `/note` corrections were read by nothing; no loop turned a losing market into a decision | **BUILT 2026-10-05** — standing order 39: losing-market watch on the heartbeat and weekly review, proposals answered with `/approve` / `/reject` on Telegram, approved blocks applied before the pick, `memory/knowledge.json` written every run and checked by the supervisor, open `/note`s listed; `tests/loss_watch_test.py` |
| 22 | Pieces connected to nothing (audit 2026-10-05, Architect: "make sure everything is connected to something and has a function") | **DONE 2026-10-05** — connected: `scripts/olp_query.py` answers Telegram `/lookup` and `/picks`; `monitor/json_log.py` writes the committed run log `memory/runs.jsonl` (every Run ID kept, order 30), read by the supervisor; `backtest.yml` runs the full backtest monthly (dead step removed); unused packages dropped from `requirements.txt`. Parked in `legacy/laptop/parked_2026-10-05/` (laptop-only or read by nothing): `mcp_health.py`, `alert_dispatcher.py`, `rotate_logs.py`, the `.bat`/`.ps1` files, `config/leagues.json`, `fixtures.json`, `sync-health.yml`; the TypeScript `.claude/rules` to `.claude/legacy/rules/`. OPEN: `claude-review.yml` idles until an `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` secret is set; the four `sports-*` skills need `pip install sports-skills` in the session; `.claude/settings.json` hooks are the laptop's (ECC syntax, `C:/` paths) |
| 25 | The framework only learned from the leagues it covers | **BUILT 2026-10-07** (Architect: "examine every fixture that has played ... that we have not covered ... both for basketball and football ... learn how the betting goes on them") — `universe.yml` every 3 h: every SportyBet football (~1,650) and basketball (~220) game, first/last pre-kick-off price, covered or not; graded from Flashscore with the strict grading match; `data/universe/graded_<month>.jsonl`; `backtest/UNIVERSE_STUDY.md` (calibration, price bands, standout competitions with 30+ games, covered vs not, price moves). A study, not a selector — a finding becomes a rule only by the Architect. In-play / live tactical data: no free live-stats feed across leagues — not built. **Post-match stats BUILT 2026-10-07** (Architect: "yes add both"): FotMob stats of every rated fixture (`data/match_stats.py` → `data/match_stats/`, team profiles, `backtest/MATCH_STATS_STUDY.md`); first 31 matches: the side with more big chances won 62% / lost 4%, more possession won only 35%. Order 38 extended to the Turkish Cup (2026-10-07). Also 2026-10-07: Turkish Cup added to coverage (market-implied, `sr:tournament:96`); NBA live test at £1 a pick (orders 26, 41) |
| 26 | Closed SportyBet lines (status 2: stale prices, not bettable) were read as real offers — tonight's three NBA codes couldn't be placed (2026-10-07) | **FIXED 2026-10-07** (`da24079`): only open markets count everywhere (football reader + booking, NBA pricing, ladder, watch price check, universe). Ladder study re-run on open lines only: totals and team totals about right, handicap ladder ~2 points wider than results but **no open line had positive value** (best −0.4%) — the earlier "+24%" and "too wide" readings were closed-line artefacts. **Paper book BUILT** (Architect: "place bets within yourself ... learn"): 12 fixed rules bet £1 on paper at the first price on every graded game, `backtest/PAPER_BOOK.md`; a rule is proposed only with 100+ bets, return 2 se above zero and positive CLV. **2026-10-08** (Architect, via the coordinator session: "keep learning how to build an acca properly ... be technically ready for Friday"): paper accas (3 legs a day from F8 / F1+F2 / F8+F1+B1, landed vs promised), why-breakdowns per rule, and a once-a-day paper-book note to the Architect's chat (`universe.yml`) |
| 27 | The 8 Oct evening board (and bet365 board, heartbeat) went to everyone twice: the 7 Oct 22:07 UTC run delivered, its persist commit lost a rebase conflict on an NBA ladder log, the sent marker went with it, and the 00:24 UTC late cron found no marker | **FIXED 2026-10-09** — marker saved to main on its own right after delivery (`monitor/push_marker.py`); NBA ladder logs merge as a union; persist warns instead of dropping silently; `tests/sent_marker_test.py` reproduces the 7 Oct sequence |
| 24 | Turkish Cup not covered (only the Super Lig is); the Architect asked for its results to be studied and learned from | **STARTED 2026-10-07** (Architect: "study each of the fixtures, study the outcome and use it for training the model") — every daily run archives the cup's results from Flashscore with both clubs' divisions (`data/cups/results.json`); `backtest/cup_study.py` → `backtest/TURKISH_CUP_STUDY.md`. First 27 qualification ties: 11% level after 90, 3.4 goals per 90, home won 59%, half-time leader won 14/15, division gaps decided little. OPEN: the cup is not priced — SportyBet lists it as `sr:tournament:96` but did not list most qualification ties; adding it (market-implied) is the Architect's call |
| 23 | NBA paper board (order 41) priced only five markets once a day; SportyBet's ladder pricing, line moves before tip-off and its team-total / half / quarter markets were unmeasured | **BUILT 2026-10-07** (Architect: "build A and B together and C") — Architect's chat only; **LIVE TEST from 2026-10-07** (orders 26, 41 amended: "we are doing live tests") — picks placed by hand from their codes, the framework never stakes. A: every SportyBet NBA ladder saved with its fitted centre and spread (`engine/nba_ladder.py`, `output/nba_ladders/`), measured by `backtest/nba_ladder_study.py` → `backtest/NBA_LADDER_STUDY.md`. B: `monitor/nba_watch.py` + `nba_watch.yml` — every 15 min while a game tips within 6 h, sharp line vs SportyBet; new value or a line move SportyBet hasn't followed becomes a graded paper pick (`output/picks/nba_watch_<date>.json`) or a LAG note. C: `backtest/NBA_PERIOD_STUDY.md` (2023-24 learns, 2024-26 test): team totals sd 11.3, regulation total T−1.0 sd 17.2, 1st-half margin 0.639×(−S) sd 11.0, quarters 1–3 sd 8.2–8.5; team-by-team quarter shares did NOT beat one league share. Board now prices 227/228/18/66/303. First read (preseason, 5 games): SportyBet's handicap ladders imply sd ~16–17 vs 13.5–13.75 measured — wider, so its far lines' near-certain sides may pay above fair. OPEN: regular-season ladders from 20 Oct decide it; the Q4 / 2nd-half overtime rule on SportyBet unconfirmed (not priced); bet365 names still a draft |
| 27 | Tipster slips lean on SportyBet specials (1X2 - 2UP/1UP early payout, "Home or Over 2.5", win either half, 3 in a row) that nothing could grade, and the paper book never priced them | **BUILT 2026-10-09** (Architect: "look at how they are doing it so you can learn") — the universe sweep keeps 2UP/1UP prices; early payout settles from FotMob goal times (`data/fotmob.Timelines`, own goals read from the running score, extra time excluded; a timeline that disagrees with the score is not used; no goal times = unsettled, never guessed). Paper rules F11 2UP / F12 plain win / F13 home-or-draw bet the SAME home sides (75%+ margin-free, 2UP offered), counted from 2026-10-10. Tipster grading maps and settles the specials (re-mapping slips decoded before), class `special` kept apart from aligned/risky. Paper only. |

---

# Laptop line — last state as of 2026-09-16 (HISTORICAL, superseded 2026-10-03)

> `CLAUDE.md` tells every session to read this file first because it holds
> current phase, suspension status, live defects and which documents are
> canonical. Until 2026-09-16 it held none of those — it was a reverse-
> chronological work journal — so sessions read it, found nothing, and
> proceeded on inference. This block exists to satisfy that contract. Keep it
> at the top and keep it current; append session entries below it.

| Field | Value | Source |
|-------|-------|--------|
| Phase | 3 (live capital, Architect-deployed 2026-08-11) | `config/__init__.py` |
| CAPITAL_ENABLED | True (derived, `PHASE >= 3`) | `config/__init__.py` |
| ARCHITECT_SIGNOFF | 1 (override active) | `.env` |
| CLV gate | 30 legs + positive mean CLV | `clv/phase3_gate.py` |
| Gate status | NOT MET (17/30 legs, mean CLV −2.467%) | Board 2026-08-19 |
| Publishing | Suspended by this session pending defect review | see below |

**Canonical documents:** this file (state), `Rules.md` (HR/ID register),
`Decisions Log.md` (Architect directives), `Protected Constants.md`.
`TELEGRAM_BLEND_DESIGN.md` is SUPERSEDED — do not read.

> **2026-10-03 — one repo, one line.** The laptop line (this file's history)
> and the cloud line (`main`, GitHub Actions daily board) were merged with
> main's code winning every shared file. The table above is the laptop line's
> last state; the live board now comes from `main`. What was kept, dropped,
> and why — including why the laptop `run_daily.bat` loop no longer runs on
> this code — is in `docs/LINEAGE_MERGE_2026-10-03.md`.

### Laptop-line defects (historical — most concern code now parked in `legacy/laptop/`)

| # | Defect | Status |
|---|--------|--------|
| 1 | SportyBet cache stale; league mapping wrong (Chelsea v Bournemouth filed under Ligue 2, Türkiye v France under Serie A) | **CLOSED 2026-09-19** — staleness root-caused: the hourly "SportyBet Cache Refresh" task registered its executable as `C:\Users\Motunrayo\omniroute` with `test\...` as arguments (unquoted space), so it failed every hour since 2026-09-06 with ERROR_BAD_EXE_FORMAT. Task repaired, `LastTaskResult=0`. |
| 2 | SportyBet Playwright cache warm hangs (killed at 11 min) | OPEN |
| 3 | Pipeline exits 0 on failure — Task Scheduler recorded success daily through a two-week outage | **CLOSED 2026-09-19** — `run_daily.py`'s `__main__` block now `sys.exit(1)` when the run produces neither a board nor deliverable output. (No `main()` exists in that file: `return` there is a compile error that `ast.parse` does not catch.) |
| 4 | Two implementations of the core stage; the live path returns empty (4.8 s) while the real work (91.5 s) is discarded. Third copy at `olp_xdv_pipeline_fixed.py` | OPEN |
| 5 | ESPN tier contradicts itself: `verification/id403.py` says T1, `data/espn_source.py:239` hardcodes T2, `CLAUDE.md` says T1 | OPEN |
| 6 | `fixtures_agent.py` never queries ESPN — the one working T1 source is not wired into the fixture agent | OPEN |
| 7 | Sync memory→vault still 0 files: matches memory slug names (`protected-constants.md`) against vault title names (`Protected Constants.md`), no mapping | OPEN |
| 8 | `grade_results.py:251` is an acknowledged stub | **SUPERSEDED 2026-09-19** — heartbeat grading no longer depends on it. `scripts/grade_pending_heartbeats.py` settles results against real ESPN scores using the canonical `market_key`, now persisted on every heartbeat record. 10 of 11 backlogged heartbeats graded. The stub itself is still there. |
| 9 | ~30 zero-byte shell-redirect artefacts untracked in repo root (`1`, `2`, `cd`, `git`, `List[Dict]`, `}`) | OPEN |
| 10 | `dry_run=True` passed to `run_pipeline` is inert — stored in state, never read | OPEN |

**Stale guidance corrected 2026-09-16:** `CLAUDE.md` warns that
`fixtures_agent.py` is stubbed with hardcoded Premier League fixtures. That is
no longer true — it has five real fetchers. Treat that warning as historical.

---

## 2026-09-19 — Session Work: the nightly loop was producing nothing, and saying it worked

### What the Architect asked for
Booking codes for today's board, then full automation: 22:00 grades yesterday
and produces tomorrow, so Telegram holds everything by 07:00.

### Delivered today (all verified against the live site, not asserted)
- **13 SportyBet booking codes**, every one passing its own odds check.
  4 accas (UMZF2F, SN20NH, VNVCAL, S8L7NF), 1 mega 20-leg (VHK4PU @ 836.06),
  6 heartbeat singles, 1 heartbeat global (ZPXXB4 @ 8.32).
- **First booking code this framework has ever produced that passed
  verification.** Root cause of the long-standing failure: the odds reader
  preferred `potential_win / total_stake`, and SportyBet NG adds an
  accumulator bonus to Potential Win, so it returned `odds x (1 + bonus)`.
  Measured ladder on slips whose legs were independently verified: 2 legs
  +1.8%, 3 legs +3.0%, 4 legs +4.8%, 5 legs +7.2%. The real tolerance is
  **5%, not the 2% the docstring in `verify_external_code.py` still claims**,
  so 5-leg accas — every production acca — were unbookable. Fix reads the
  displayed "Odds" instead. Tolerance untouched.
- **Draw No Bet and Double Chance never worked**: `_MARKET_UI_MAP` drove them
  with glyph codes ("1X", "1") that SportyBet renders nowhere. The live match
  page shows "Home or Draw", "Draw or Away", "Home", "Away". 0/6 driven before,
  20/20 legs after.
- **16 competitions unmapped on a name mismatch**, not absence — SportyBet's
  menu lists every one; the discovery script compared OLP's names to
  SportyBet's ("Austrian Bundesliga" vs Austria/"Bundesliga"). Cost 51 of 241
  fixtures, including all 11 Taça de Portugal ties.
- **Heartbeat grading had never run.** `record_heartbeat_result` had zero
  callers, so 8 lineages sat at 0W-0L across three generations. 10 of 11
  backlogged heartbeats now graded (7W-3L); population 8 -> 6 alive, 2 extinct.

### The nightly loop: three silent defects, all now closed
1. `run_daily.py` never passed the target date to Stage B. 241 fixtures
   gathered, **0 shortlisted**, logged as "none priced with positive edge".
   One argument.
2. The run **always exited 0**, so the scheduler never alerted.
3. `breed_next_generation` **destroyed capital** at the population cap:
   `[:MAX_LINEAGES]` sliced off exactly the winners its own guard had carried
   forward. 78.71 -> 52.60 on every breed.

Plus two dead scheduled tasks nobody was watching: result verification exiting
1 nightly on a missing `sqlite3` module, and the hourly SportyBet cache
refresh failing since **2026-09-06** because its action path was unquoted and
"omniroute test" contains a space. That last one is why every cache was stale
this morning and booking would have resolved zero legs.

### New this session
`booking/bookability.py` (gate: competition in registry AND market with a
proven drive path), `booking/bet365_scope.py` (35 top-flight European
competitions), `output/bet365_board.py` (separate Bet365 production, no
codes — Bet365 has none), `engine/context.py` (rest days, congestion,
competition stage; bounded +/-10%, logged).

### Measured findings worth keeping
- **Competition prestige predicted no booking failure. Market family predicted
  all of them.** Totals 13/13 booked including Latvia and Croatia; DNB 0/4
  including Serie A and 2. Bundesliga.
- **Under 3.5 dominance is the 1.50 cap, not model preference.** Inside the cap
  the picks ARE max-EV on 19 of 20 fixtures; a higher-EV market exists above
  the cap on 19 of 20. Keeping the cap is right while calibration is unproven.
- **Bet365 adds zero coverage.** Not one competition today is Bet365-reachable
  and SportyBet-unreachable. Its value is price, not reach.
- **API-Football is on the FREE plan** (100 req/day), confirmed against the
  API's own `/status`. `API Keys.md` claimed paid since 2026-08-19 and that
  stale row has misled several sessions. Injuries stay blocked.

### Open, needing the Architect
- Breeding slot allocation (6 winners, 8 slots) is my rule, not a ratified one.
- Team news/injuries need a real paid plan.
- `verify_external_code.py` still documents a 2% tolerance; the code is 5%.

---

## 2026-09-16 — Session Work: Root-caused session memory loss and a two-week pipeline outage

### The reported symptom
"At the beginning of every session the framework looks like it has forgotten
what it's supposed to do." That had a specific, mechanical cause.

### Root cause of the memory loss
`scripts/vault-memory-sync.js` set `MEMORY_ROOT` to
`path.join(__dirname, '..', '.claude', 'projects', 'c--Users-Motunrayo-omniroute-test', 'memory')`
— a path **inside the repo** (note the lowercase `c--`), not
`~/.claude/projects/C--Users-Motunrayo-omniroute-test/memory`, which is the
store Claude Code actually loads at session start. That in-repo directory
exists, so every run reported *"success — 0 files synchronized"* while the real
memory was never read or written. **HR54 was nominally enforced and actually a
no-op.** In-repo copy held 22 stale files; the real store holds 30.
Fixed: resolves from `os.homedir()`, and exits non-zero if the root is missing.
Verified: 16 files vault→memory, previously 0.

### Root cause of the pipeline outage (no successful run since 2026-09-02)
Four defects in one chain, each masking the next:

1. **Credentials never loaded.** `config/__init__.py` built its dotenv path as
   `Path(__file__) / ".env"` — joining a filename onto the module *file*,
   giving `.../config/__init__.py/.env`, which can never exist. All 14
   credentials sat unread; runs still exited 0 logging "0 fixtures across 0
   leagues". Now 5/5 critical keys present.
2. **PyYAML imported but never declared** (`run_daily` → `verify_fixtures` →
   `bridge` → `knowledge_persistence` → `yaml`). Killed the run at import on
   any fresh venv or CI runner. Added to `requirements.txt`.
3. **The error handler crashed the run.** `_mark()` opened the runlog with no
   encoding, taking Windows cp1252. It is the function the failure paths call,
   so logging a *recoverable* error whose text contained box-drawing characters
   (Playwright's "please run playwright install" notice) raised
   `UnicodeEncodeError` inside the except block and killed the pipeline.
4. **A status string discarded the board.** The fallback branch rendered the
   board, then built a flag via `state['payloads'].get(5, ...)` —
   `run_pipeline` defines `payloads` as a **list**, not a dict keyed by agent.
   The except branch then reset `board_text = ""`, throwing away a board that
   had already rendered. **This is why `board_2026-09-05/06/08/09.txt` are 0
   bytes.** Counting moved to an `else` branch.

### Fixture fabrication — three compounding defects
The fixture agent reported **163 fixtures** for 2026-09-16, every row stamped
`verified`, when ESPN (T1) carried **13**.

1. `fetch_flashscore` unioned **all 40** scrape files. FlashScore's
   `match_datetime` carries no year, so any historical scrape holding that
   day/month lands on the target date. One corrupt scrape from 2026-08-29 had
   stamped Celje's entire Europa League league-phase schedule with the same
   `16.09. 20:00`. Now bounded to the week before the match day.
2. Dedup keyed on raw `home|away|date`, but names drift between scrapes
   ("Leverkusen"/"Bayer Leverkusen"), so one match survived once per spelling.
   **29 teams played more than once on a single day**; Celje and AZ Alkmaar
   appeared 7 times each. Dedup now normalises names.
3. **The F2 quorum gate enforced nothing** — `_apply_verification` tested for
   at least ONE source, trivially true for every row. Everything was stamped
   verified unconditionally. Now: two or more distinct sources, or one T1
   source, with tiers resolved through `verification/id403.SOURCE_TRUST`.

**Verified after fix:** flashscore rows 88 → 38; duplicate teams 29 → **0**;
Celje 7 → 1 matching ESPN; Europa League slate 9, matching ESPN's 9
one-for-one; La Liga 4 in both; 422 stale cache rows now correctly UNVERIFIED.

### Today's fixtures (HR59: `run_id=2c9306436136`, `fetched_at=2026-09-16T15:51:52Z`, ESPN T1)
**La Liga (4)** — Atlético Madrid v Osasuna · Deportivo v Sevilla · Barcelona v
Racing Santander · Levante v Athletic Club
**Europa League (9)** — Ararat-Armenia v Sparta Prague · Omonia Nicosia v Celta
Vigo · AC Milan v Benfica · Anderlecht v Lyon · Bayer Leverkusen v NK Celje ·
Hapoel Be'er v Dinamo Zagreb · Olympiacos v Jagiellonia Białystok · SK Sturm
Graz v Stade Rennais · Sunderland v AZ Alkmaar

No Premier League, Serie A, Bundesliga or Ligue 1 today; next PL fixtures 18–19 Sep.

### Bets — NOT PRODUCED
Agent 5 generated 8 acca legs and 3 singles from the pre-fix fixture set, i.e.
from data in which teams played seven matches a day. Those legs were **not**
published and should not be used. Publishing stays suspended until defects 1–4
above are closed. All runs this session used `--no-send --no-whatsapp
--no-email`; nothing reached Telegram.

### Commits
`23b8e6b` config/env · `03ca729` pipeline · `0090e8f` fixtures · `4f1fa651` sync (root)

### Not done
278 files remain uncommitted in the submodule (other sessions' in-flight work
plus defect 9's junk). Not swept into a commit deliberately.

---

## 2026-08-21 — Session Work: Four-Table Output Structure Implementation

### Implementation Completed
- **File modified**: `output/produce_bet.py`
- **Four new render functions added**:
  1. `render_layer2_full_grid()` — TABLE 1: Every fixture × every market probability with Selected Pick column, one shared booking code for entire Layer 2
  2. `render_layer1_compact()` — TABLE 2: One row per deploy-eligible fixture with its own booking code (Layer 1 compact)
  3. `render_acca_route()` — TABLE 3: Capital-eligible fixtures grouped into accas, each acca with its own booking code
  4. `render_the_pick()` — TABLE 4: Final recommendation after all three tables (primary single + Acca A recommendation)

### Key Features
- All `EDGE_MARKETS` evaluated (1X2, Double Chance, Over/Under 0.5/1.5/2.5/3.5, BTTS, Draw No Bet, HT/FT, Correct Score top 6) — ID405 gate open per Architect 2026-08-11 override
- Booking code consistency: Layer 2 = one shared code; Layer 1 = per-fixture codes; Acca Route = per-acca codes
- EV-based market selection (`model_prob × price − 1`) per fixture for "Selected Pick" column
- Falls back to stored `best_market` / SportyBet odds when odds index unavailable
- Honest-edge compliance: NO DATA — PENDING preserved throughout (HR35)
- Architecture integration: called from `render_produce_bet()` in order Table 1 → 2 → 3 → 4

### Testing
- Syntax verified: `python -m py_compile output/produce_bet.py` — clean

### Next Steps
- Run full pipeline to generate board with new four-table structure
- Verify booking code generation for all three layers
- Confirm SportyBet bridge integration produces codes for each layer

---

## 2026-09-08 — Session Work: Database schema fix and odds parsing improvement

### Implementation Completed
- **File modified**: `brain/store.py`
  - Added `outcome` column to `odds_history` table schema
  - Set default outcome to 'Pending' for odds collection
- **File modified**: `data/apifootball_client.py`
  - Fixed odds parsing to handle structured format with "value" and "odd" fields
  - Updated comment examples to show correct structure: {"value": "Home", "odd": "2.10"}
- **File modified**: `feed_audit.jsonl`
  - Appended today's feed audit entries from pipeline run

### Key Features
- Database schema enhancement to track bet outcomes for future CLV calculations
- Corrected API Football client to properly parse structured odds data
- Maintains audit trail of pipeline executions

### Testing
- Syntax verified: `python -m py_compile brain/store.py` — clean
- Syntax verified: `python -m py_compile data/apifootball_client.py` — clean

### Next Steps
- Continue monitoring feed accuracy and odds collection
- Prepare for outcome tracking implementation when match results become available
- Verify CLV calculation foundation is solid

---

---

## 2026-09-05 — Session Work: Fix SportyBet Data Issue for Reliable Pipeline

### Problem Identified
- SportyBet cache files were outdated (mostly from Aug 31 - Sep 2, 2026)
- FlashScore data was available and current for Sep 5-6, 2026
- ESPN source was failing due to API limitation (only accepts single date per request)
- TheSportsDB source had no data for current season
- Verification gate requires either: (a) SportyBet + ≥1 other source, OR (b) single T1 source (ESPN/football-data)

### Fixes Applied
1. **Fixed ESPN source** (`data/espn_source.py`):
   - Modified `fetch_upcoming()` to iterate over each day individually since ESPN's scoreboard API only accepts a single date per request
   - Fixed status checking to use `status.type.name` (e.g., "STATUS_SCHEDULED") instead of `status.type.state` (e.g., "pre")
   - Added proper error handling to continue processing other days if one day fails

2. **Fixed TheSportsDB source** (`data/multi_source_concrete.py`):
   - Changed TheSportsDB fixture source to raise `SourceNoData` when no fixtures found
   - This allows the multi-source fabric to properly failover to ESPN when TheSportsDB has no data

3. **Enhanced verification logic** (already correct):
   - The verification gate in `booking/verify_fixtures.py` correctly implements F2 QUORUM RULE:
     * A fixture is VERIFIED when: SportyBet + ≥1 other source agree, OR a SINGLE T1 source carries it
     * ESPN is correctly rated as T1 in `verification/id403.py` SOURCE_TRUST
   - OUTAGE SEMANTICS properly drop fixtures with only one source to prevent fabrication

### Results
- **FlashScore**: 748 fixtures available for 2026-09-06 (T1 source per Architect approval)
- **ESPN**: 25 fixtures available for 2026-09-06 (T1 source)  
- **SportyBet**: 20 fixtures available (cached from Sep 2, but still useful for corroboration)
- **Verification Outcomes** (for sample fixtures):
  - Fixtures with FlashScore + ESPN: VERIFIED (T1 source: FlashScore OR ESPN)
  - Fixtures with SportyBet + ESPN: VERIFIED (SportyBet + T1 source)
  - Fixtures with FlashScore only: KEPT UNVERIFIED (awaiting corroboration)
  - Fixtures with SportyBet only: KEPT UNVERIFIED (awaiting corroboration)
  - Fixtures with no sources: properly dropped (not shown in output)

### Impact on Pipeline
- The daily pipeline will now run successfully even with outdated SportyBet cache
- ESPN provides reliable T1 source for verification when available
- FlashScore provides T1 source for verification (per Architect approval 2026-08-16)
- LIVE MATCHES section in `output/produce_bet.py` shows all FlashScore fixtures for tracking
- Verification gate maintains integrity: no fabrication, only verified fixtures proceed to booking

### Files Modified
- `data/espn_source.py` - Fixed ESPN date iteration and status checking
- `data/multi_source_concrete.py` - Fixed TheSportsDB failover behavior
- `output/produce_bet.py` - Added LIVE MATCHES section for flashscore-only fixtures
- `docs/obsidian-vault/STATE.md` - Updated with this session's work

### Verification Commands Tested
```bash
# Test ESPN source directly
python -c "from data.espn_source import fetch_upcoming; f,s = fetch_upcoming('Premier League', '2728', 14); print(f'ESPN: {len(f)} fixtures')"

# Test multi-source failover
python -c "from data.multi_source_concrete import get_fixtures; r = get_fixtures('Premier League', '2728', 14); print(f'Multi-source: {len(r.get(\"fixtures\", []))} fixtures from {r.get(\"source\")}')"

# Test full verification
python -c "from booking.verify_fixtures import verify_board; from fixtures_agent import fetch_flashscore; from data.multi_source_concrete import get_fixtures; from booking.bridge import load_sportybet_fixtures; from datetime import date; t = date.today().isoformat(); fs = fetch_flashscore(t); espn = get_fixtures('Premier League', '2728', 14, None); sb = load_sportybet_fixtures('Premier League', 45, 72); print(f'Sources - FS:{len(fs)}, ESPN:{len(espn.get(\"fixtures\",[]))}, SB:{len(sb)}')"
```

---ork: Fixed TheSportsDB fixtures NoneType error in multi-source chain

### Problem Identified
- Daily pipeline was failing with "object of type 'NoneType' has no len()" error in data/multi_source_concrete.py
- Root cause: TheSportsDBFixturesSource.fetch() method was not checking for None returns from tsdb.fetch_upcoming() and tsdb.fetch_today()
- This affected the old multi-source chain used by the pipeline orchestrator, while the new provider chain in fixtures_and_odds_providers.py was already fixed

### Fix Applied
- Modified data/multi_source_concrete.py to properly handle None returns:
  - Line 53: Changed `if fixtures:` to `if fixtures is not None and len(fixtures) > 0:`
  - Line 65: Changed `if day_fixtures:` to `if day_fixtures is not None and len(day_fixtures) > 0:`
- This ensures graceful degradation per HR35 when a provider returns no data
- The fix allows the pipeline to continue with empty data rather than crashing

### Verification
- Ran full daily pipeline for date 2026-09-04 with all whitelisted leagues
- Pipeline completed successfully (exit code 0) with notifications disabled
- Confirmed the fix resolves the NoneType error across all leagues in the whitelist
- The provider fallback chain (API-Football → TheSportsDB → SportyBet) now handles None returns properly

### Files Modified
- `olp_xdv_agent/olp_xdv/data/multi_source_concrete.py` - Fixed None checks in TheSportsDBFixturesSource.fetch()
- `logs/auto-sync/auto-sync-2026-09-04.log` - Pipeline execution log

---ospective Audit (Fixtures 2026-08-05 to 2026-08-09)

### Fixtures Audited
- **10 fixtures** across 10 dates (2026-08-05 → 2026-08-09)
- **23 settled legs** (from predictions table + legs table in brain/olp.db)
- **Engines evaluated**: consensus, bookmaker, dc, elo, cross, xg

### Hit Rate Summary

| Engine | Predictions | Settled | Hit Rate |
|--------|-------------|---------|----------|
| consensus | 1254 | 11 | **45.5%** |
| dc | 2694 | 14 | **42.9%** |
| elo | 1332 | 5 | **60.0%** |
| cross | 318 | 1 | 0.0% |
| bookmaker | 147 | 0 | — |
| xg | 48 | 0 | — |

**Overall**: 34.8% hit rate (8/23 legs correct)

---

### Calibration Audit — Probability Bin Analysis

| Prob Bin | Predictions | Hits | Hit Rate | Avg Prob | Calibration Error |
|----------|-------------|------|----------|----------|-------------------|
| 0.0–0.1 | 1 | 0 | 0.0% | 5.0% | -5.0pp |
| 0.1–0.2 | 2 | 0 | 0.0% | 15.0% | -15.0pp |
| **0.2–0.3** | **11** | **2** | **18.2%** | **24.4%** | **-6.2pp** |
| 0.3–0.4 | 4 | 2 | 50.0% | 35.0% | +15.0pp |
| 0.4–0.5 | 3 | 3 | 100.0% | 45.0% | +55.0pp |
| 0.5–0.6 | 2 | 1 | 50.0% | 55.0% | -5.0pp |
| 0.6–0.7 | 1 | 0 | 0.0% | 65.0% | -65.0pp |
| **0.8–0.9** | **2** | **0** | **0.0%** | **85.0%** | **-85.0pp** |

**Critical Findings:**
- **0.2–0.3 bin**: Model overconfident by ~6pp (18.2% actual vs 24.4% predicted) — 11 predictions, only 2 hits
- **0.8–0.9 bin**: **Severe overconfidence** — 0% hit rate vs 85% predicted (2 predictions, both misses)
- Model appears **miscalibrated at extremes** — both low-prob and high-prob predictions unreliable

---

### Miss Pattern Analysis

#### By League
| League | Misses | Total Legs | Miss Rate | Notes |
|--------|--------|------------|-----------|-------|
| Eredivisie | 8 | 8 | **100%** | All legs missed — systemic issue |
| Scottish Premiership | 5 | 5 | **100%** | All legs missed — systemic issue |
| Premier League | 1 | 1 | 100% | Small sample |
| La Liga | 0 | 0 | — | No settled legs |
| Champions League | 0 | 0 | — | No settled legs |

**Eredivisie & Scottish Premiership are critical problem leagues** — 13 combined misses with 0 hits. Recommend: flag for reduced weight or separate calibration track.

#### By Market
| Market | Misses | Hits | Hit Rate |
|--------|--------|------|----------|
| 1X2_HOME | 5 | 3 | 37.5% |
| 1X2_AWAY | 3 | 2 | 40.0% |
| 1X2_DRAW | 5 | 1 | **16.7%** |
| Over 1.5 | 2 | 0 | 0.0% |
| Over 2.5 | 2 | 1 | 33.3% |
| Under 2.5 | 0 | 1 | 100.0% |
| BTTS_Yes | 2 | 0 | 0.0% |
| Draw (Double Chance) | 1 | 0 | **0.0%** |

**Draw markets consistently missed** — 1X2_DRAW 16.7%, Double Chance Draw 0%. Model struggles with draw probability estimation.

#### By Engine (misses only)
| Engine | Misses |
|--------|--------|
| consensus | 6 |
| dc | 8 |
| elo | 2 |
| cross | 1 |

dc (Dixon-Coles) has highest miss count — expected given highest prediction volume.

---

### CLV (Closing Line Value) Analysis

- **Mean CLV**: -2.467% (17 legs with CLV captured)
- **Positive CLV legs**: 1 / 17
- **Gate status**: 17/30 legs, mean CLV negative → **Gate NOT met**
- **Architect signoff**: Active (ARCHITECT_SIGNOFF=1) — Phase 3 live capital deployed despite gate miss

**Interpretation**: Model edge is not materializing at closing line. The market is efficiently pricing against our predictions.

---

### Core Lessons Extracted

1. **Calibration drift at probability extremes** — The model is unreliable for both very low (<0.3) and very high (>0.8) probability predictions. These bins need either:
   - Separate calibration curves per bin
   - Temperature scaling post-processing
   - Exclusion from deployment until recalibrated

2. **Eredivisie & Scottish Premiership are untrustworthy** — 100% miss rate across 13 legs. Possible causes:
   - Insufficient historical depth for current season
   - Squad/manager changes not captured
   - Odds source quality issues for these leagues
   - **Action**: Downweight or quarantine these leagues in deployment

3. **Draw probability estimation is broken** — Consistent underperformance across 1X2_DRAW and Double Chance Draw markets. The Poisson/Dixon-Coles model structure may systematically misestimate draw probabilities.

4. **Negative mean CLV indicates no live edge** — Despite paper hit rates ~35-45%, the market closes against us. This suggests:
   - Model predictions are public/known (information leakage)
   - Odds movement is efficient against our signals
   - Deployment timing (entry price capture) may be suboptimal

5. **Engine consensus helps but not enough** — Consensus engine hit rate (45.5%) beats dc (42.9%), but both below 50%. Ensemble weighting (currently consensus=0.926, dc=0.926, elo=0.926) may need rebalancing toward elo (60% hit rate on small sample).

---

### Recommended Actions

| Priority | Action | Owner |
|----------|--------|-------|
| **P0** | Add calibration tracking per probability bin to daily monitoring | Data Quality Monitor |
| **P0** | Quarantine Eredivisie & Scottish Premiership from Acca A (deploy to singles only) | Bet Production (HR58) |
| **P1** | Investigate draw market model structure — consider separate draw probability model | Engine (dc/elo) |
| **P1** | Review odds capture timing — are we capturing entry prices at optimal moment? | CLV Logger |
| **P2** | Rebalance ensemble weights toward elo (higher hit rate) | Engine Config |
| **P2** | Add league-specific calibration curves (not global) | Recalibration Engine |

---

### Vault & Memory Sync

- **Canonical vault**: `olp_xdv_agent/olp_xdv/docs/obsidian-vault/`
- **Agent memory**: `.claude/projects/C--Users-Motunrayo-omniroute-test/memory/`
- **Sync status**: Pending (run `node scripts/vault-memory-sync.js` after this update)

---

## 2026-08-23 Production Pipeline — Daily Retrospective

### Fixture Verification

| Item | Status | Notes |
|------|--------|-------|
| Acca count | **7 accas (A–G)** | Source: `acca_2026-08-23.json` |
| Total legs settled | **8 / 35** | 6W / 2L = 75.0% win rate |
| Pending (unverifiable) | **27 legs** | T1 (football-data.co.uk) empty/headers-only for all leagues (schema change); T2 (ESPN) covered 29 fixtures |

**Root cause of verification delay:** ESPN results module had two bugs:
1. `build_cache` keyword-argument dispatch missing (runtime TypeError — now fixed in `booking/sportybet_fixtures.py`)
2. `_extract_closing_odds` crashed on `None` entries in `competitions[0].odds` — ESPN returns `[None]` not `[]` (now fixed in `data/espn_results.py`)

**Data sources used:**
1. **football-data.co.uk (T1)** — All season files empty/headers-only (schema changed or file truncated)
2. **ESPN API (T2)** — Working; matched 29 of 35 fixtures across 8 leagues
3. **Manual verification (T3)** — Not run; 27 legs genuinely unverifiable (HR35 gap)

---

### Outcome Audit

| Acca | Legs Settled | W/L | Acca Status | Combined Odds |
|------|-------------|-----|-------------|---------------|
| A | 1/5 | 1W 0L | PENDING | 9.81 |
| B | 1/5 | 1W 0L | PENDING | 8.21 |
| C | 0/5 | 0W 0L | PENDING | 8.57 |
| D | 1/5 | 1W 0L | PENDING | 7.36 |
| E | 1/5 | 1W 0L | PENDING | 9.98 |
| F | 0/5 | 0W 0L | PENDING | 7.66 |
| G | 2/5 | 2W 0L | PENDING | 6.39 |

**Settled acca outcomes:** 0 fully settled (all 7 accas have ≥3 pending legs)  
**Win rate (settled legs):** 75.0% (6W / 2L)

**Settled leg details:**
| Acca | Fixture | Market | Score | Outcome |
|------|---------|--------|-------|---------|
| A | FC Porto 2-0 Arouca | OVER_1.5 | 2-0 | WIN |
| D | Club Brugge 1-0 Cercle Brugge | 1X2_HOME | 1-0 | WIN |
| E | Brighton 4-0 Aston Villa | DC_1X | 4-0 | WIN |
| G | Elche 0-5 Barcelona | OVER_2.5 | 0-5 | WIN |
| G | Newcastle 2-2 Liverpool | OVER_2.5 | 2-2 | WIN |
| B | Atalanta 2-1 Sassuolo | BTTS_NO | 2-1 | LOSS |
| D | Rennes 2-2 PSG | 1X2_AWAY | 2-2 | LOSS |
| B | Torino 1-2 Milan | OVER_1.5 | 1-2 | WIN (AWAY_WIN pick) |

---

### CLV Integration Status

**CLV log entries for 2026-08-23: 0 entries**  
**Quantified CLV footprint match_score: 0 entries from acca legs in CLV log**

Same root cause as Aug 22: CLV capture not running during production Stage B. The `clv/closing_capture.py` / Data Steward daemon not persisting closing lines. Gap persists Aug 10-23.

**Action required:** Investigate `clv/closing_capture.py` and Data Steward (06:00/15:00) capture logic.

---

### Knowledge Integration

**Key observations from Aug 23:**
1. **T1 source degraded systemically** — football-data.co.uk schema change affects all leagues. Need schema-flexible parser or T1b source.
2. **ESPN T2 works but incomplete** — 29/35 fixtures; misses some La Liga 2, Ligue 2, Swiss, Eredivisie early fixtures.
3. **OVER_2.5 value continues** — Barcelona 5-0, Newcastle-Liverpool 2-2 both wins. Counter to "cagey opener" hypothesis from Aug 22.
4. **BTTS_NO still lossy** — Atalanta-Sassuolo 2-1 (both scored). xG/shot-volume screening needed before BTTS_NO.
5. **DC_1X on strong home wins working** — Porto, Club Brugge, Brighton all delivered home wins.

---

### Framework Constants (Protected — Do Not Modify)

| Constant | Value | Source |
|----------|-------|--------|
| PHASE | 3 (live capital, Architect-deployed 2026-08-11) | `config.py` |
| ARCHITECT_SIGNOFF | 1 (override active) | `.env` |
| CLV Gate | 30 legs + positive mean CLV | `clv/phase3_gate.py` |
| Gate Status | 17/30 legs, mean CLV -2.467% → NOT MET | Board 2026-08-19 |
| Whitelist | 61 leagues (`config/leagues.json`) | ID401 |
| All Fixtures Eligible | YES (HR58, 2026-08-18) | `engine/leagues.py` |
| Odds Floor | 1.20 | `engine/acca.py` |
| Odds Preferred Ceiling | 1.50 | `engine/acca.py` |
| Odds Hard Cap | 2.00 | `engine/acca.py` + `engine/markets.py` |
| EDGE Formula | `model_prob × price − 1` | `engine/acca.py` |
| Markets Deployable | All (BLOCKED = {}) | ID405 override 2026-08-11 |

---

## Next Audit Target

**2026-08-21**: Fixtures from 2026-08-10 to 2026-08-14 (next 5-day window)

---

## 2026-08-22 — Session Work: League Coverage Reduction (Top 20 Only)

### Implementation Completed
- **File modified**: `config/leagues.json`
- **Change**: Reduced deploy-eligible leagues from 72 to 20 (top-tier European leagues + major competitions)
- **Deploy-eligible set to TRUE (20):**
  1. Premier League (England)
  2. La Liga (Spain)
  3. Serie A (Italy)
  4. Bundesliga (Germany)
  5. Ligue 1 (France)
  6. Champions League (Europe)
  7. Europa League (Europe)
  8. Conference League (Europe)
  9. Scottish Premiership (Scotland)
  10. Belgian Pro League (Belgium)
  11. Eredivisie (Netherlands)
  12. Championship (England)
  13. La Liga 2 (Spain)
  14. Serie B (Italy)
  15. 2. Bundesliga (Germany)
  16. Ligue 2 (France)
  17. Primeira Liga (Portugal)
  18. Turkish Super Lig (Turkey)
  19. Russian Premier League (Russia)
  20. Swiss Super League (Switzerland)

- **Deploy-eligible set to FALSE (52):** All other UEFA top-flight leagues (Danish Superliga, Ekstraklasa, HNL, Austrian Bundesliga, Greek Super League, Czech First League, Romanian Liga I, Ukrainian Premier League, Serbian Super Liga, Norwegian Eliteserien, Swedish Allsvenskan, Finnish Veikkausliiga, Hungarian NB I, Slovak Super Liga, Slovenian PrvaLiga, Bulgarian First League, Israeli Premier League, Cypriot First Division, Albanian Superliga, Armenian Premier League, Azerbaijani Premyer Liqa, Belarusian Premier League, Kazakhstan Premier League, Kosovan Superliga, Latvian Virsliga, Lithuanian A Lyga, Luxembourg National Division, Maltese Premier League, Moldovan Super Liga, Montenegrin First League, Estonian Meistriliiga, Georgian Erovnuli Liga, Northern Irish Premiership, Welsh Premier League, Republic of Ireland Premier Division, Icelandic Urvalsdeild, Faroe Islands Premier League, North Macedonian First League, Bosnian Premier League, Gibraltarian National League, Andorran Primera Divisió, Sanmarinese Campionato, Liechtensteiner Cup) plus domestic cups (Coppa Italia, Copa del Rey, DFB-Pokal, Coupe de France, FA Cup, KNVB Beker, Taça de Portugal, UEFA Super Cup, EFL Cup)

### Rationale
- Per user directive: "the top 20 leagues and competition is true the rest is false"
- Focuses deployment on highest-quality, best-covered leagues with reliable data sources
- Reduces noise from lower-tier and minor leagues with poor odds coverage and calibration issues
- Aligns with P0 action from 2026-08-20 audit: "Quarantine Eredivisie & Scottish Premiership from Acca A" — note: these remain in top 20 but flagged for singles-only deployment

### Testing
- JSON syntax verified
- All 72 leagues accounted for (20 true, 52 false)

### Next Steps
- Verify pipeline runs with reduced league set
- Monitor hit rate improvement from focused coverage
- Consider further quarantine of Eredivisie/Scottish Premiership per audit findings

---

## 2026-08-25 — Session Work: Cups Restored to Deploy-Eligible

### Implementation Completed
- **File modified**: `config/leagues.json`
- **Change**: Re-enabled 9 domestic cups + UEFA Super Cup as deploy-eligible (per user directive)
- **Cups now TRUE (9):**
  1. Coppa Italia (Italy)
  2. Copa del Rey (Spain)
  3. DFB-Pokal (Germany)
  4. Coupe de France (France)
  5. FA Cup (England)
  6. KNVB Beker (Netherlands)
  7. Taça de Portugal (Portugal)
  8. UEFA Super Cup (World)
  9. EFL Cup (England)

### New Deploy-Eligible Count
- **Total: 29** (20 original top-tier leagues + 9 cups)
- **Deploy-eligible FALSE: 43** (all other minor leagues + Liechtensteiner Cup)

### Rationale
- User explicitly requested cups be restored to eligible list
- Major domestic cups have strong odds coverage via Odds API and API-Football
- EFL Cup specifically was skipped today (2026-08-25) — now back in rotation

### Testing
- JSON syntax verified
- All 72 leagues accounted for (29 true, 43 false)

---

## 2026-08-26 — Session Work: Telegram Push Suppression for Empty Boards

### Implementation Completed
- **File modified**: `run_daily.py`
- **Change**: Added guard at `run_daily.py:1677-1704` to suppress Telegram phone push when the board has no deployable call (no Acca A, no split accas, no singles). The board is still written to `telegram_<date>.txt` for the web feed / audit trail.

### Rationale
- Empty/paper-only boards ("NO DEPLOY-ELIGIBLE CALL this session") are honest, valid outputs — they just don't need to wake the phone.
- Prior behavior: every run that completed `send=True` pushed to Telegram, flooding the channel with zero-call noise.
- New behavior: `has_deployable` checks `production.acca_a`, `production.split_accas`, `production.singles` — only pushes when there's a real deployable call.
- Board still persists to disk + web feed; only the phone push is gated.

### Testing
- Syntax verified (`python -m py_compile run_daily.py`)
- Logic aligns with `build_production_bets` return shape in `engine/acca.py` (production object has `acca_a`, `split_accas`, `singles` attributes).

---

## 2026-08-30 — Session Work: Nightly Production Schedule Shift (22:00 Night Before)

### Implementation Completed
- **Files modified**:
  1. `setup_daily_board_task.ps1` — Windows Task Scheduler trigger changed from `07:00` to `22:00`
  2. `scripts/install_scheduler_tasks.ps1` — Task definition updated to `Daily 22:00`
  3. `.github/workflows/daily.yml` — GitHub Actions cron changed from 07:00 to `0 21 * * *` (21:00 UTC = 22:00 Africa/Lagos)
  4. `run_daily.bat` — Launcher updated to calculate tomorrow's date via PowerShell (handles month/year rollover) and pass `--date %tomorrow%` to `run_daily.py`

### Rationale
- **Architect directive 2026-08-30**: "all production must be made the night before the next change 7am to 10pm the night before"
- Change window: 07:00–22:00 the night before deployment
- Tomorrow's production must be made by 22:00 today
- This ensures boards are ready before the 07:00 change window opens

### Technical Details
- **Windows Task Scheduler**: Primary local automation — runs `run_daily.bat` at 22:00 daily
- **GitHub Actions**: CI/CD backup — runs at 21:00 UTC (22:00 Africa/Lagos) daily
- **run_daily.py**: Already supports `--date` parameter for next-day production via `target_date` argument; `board_date = target_date or today` with `scan_window = max(0, (date.fromisoformat(board_date) - date.today()).days)`
- **run_daily.bat**: Now calculates tomorrow's date using PowerShell `Get-Date -Format yyyy-MM-dd -Date (Get-Date).AddDays(1)` — correctly handles month/year rollover (unlike the previous manual date math)

### Testing
- Syntax verified for all modified files
- PowerShell date calculation tested: `powershell -NoProfile -Command "& {Get-Date -Format yyyy-MM-dd -Date (Get-Date).AddDays(1)}"` returns correct tomorrow date
- Task Scheduler update requires re-running `setup_daily_board_task.ps1` as Administrator

### Next Steps
- Re-run `setup_daily_board_task.ps1` as Administrator to register the 22:00 task
- Verify GitHub Actions workflow triggers at 21:00 UTC tonight
- Monitor first nightly run to confirm board is generated for next day

---

*Generated by daily retrospective audit workflow. Append new entries above this line.*