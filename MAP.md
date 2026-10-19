# MAP — where everything is

Read this with `CLAUDE.md` at the start of every session. It is the one list of
every place OLP XDV keeps something: what runs, what is stored, who gets what,
which secrets, what is parked, what survives only in git history, and what
lives outside this repo. If you find something that is not here, add it here in
the same session. Built 2026-10-04 from a full audit of this repo (main, all 75
branches, `legacy/`, the vault) and the workspace repo `Tolar07/omniroute-test`.
Paths are relative to this repo; `omniroute-test:<path>` is the workspace repo;
`<sha>:<path>` exists only in git history. `tests/agent_refs_test.py` fails if
a path named here stops existing.

---

## 1. What runs

Everything live runs in GitHub Actions on `main`. Times UTC unless marked; the board slots and every time on the boards are UK time (BST = UTC+1, GMT = UTC+0 from the last Sunday of October; `engine/uktime.py`, Architect 2026-10-15).

| Workflow | When | Runs | Commits back |
|---|---|---|---|
| `daily.yml` | 20:47 (evening, tomorrow's card), 05:47 (morning refresh); also dispatched with `target_date` + `slot` | `run_daily.py --only-production --heartbeat`; morning also `run_nba.py --night` (NBA board, order 41, 11–17 h before tip-off; evening = backup only) | `clv/clv_log.json`, `output/boards/`, `output/picks/`, `data/survivor/`, `memory/`, `output/nba_ladders/`, `output/nba_markets/`, `backtest/NBA_MARKET_STUDY.md`, `backtest/NBA_LADDER_STUDY.md`, `data/sharp/` |
| `watchdog.yml` | 23:17, 08:17 | `monitor/run_watchdog.py` — starts a slot that never ran | — |
| `supervisor.yml` | after every `daily.yml` run | `monitor/supervisor.py` — one status message | — |
| `news.yml` | one job looping every 20 min 09:00–20:40, started by `daily.yml` after each board; backup cron every 2 h; hands itself on before GitHub's 6-hour limit | `monitor/news_loop.py` → `news_check.py` — lineups, price drift, closing price | `output/picks/`, each round |
| `nba_watch.yml` | one job looping every 15 min while an NBA game tips within 6 h; started by `daily.yml`'s evening run, backup cron 16:05/19:05/22:05; hands itself on before 6 h | `monitor/nba_watch.py` — sharp line vs SportyBet, booked picks + LAG notes + VALUE GONE price checks of sent picks to the Architect only, ladder snapshots | `output/picks/nba_watch_*`, `output/nba_watch/`, `output/nba_ladders/`, `output/nba_markets/`, each round |
| `study_send.yml` | manual only (from 2026-10-13) | `scripts/send_study.py <data/study/…/*.txt>` — sends one saved study file to the Architect's own chat (`TELEGRAM_OWNER_CHAT_ID`, else `TELEGRAM_CHAT_ID`), never to subscribers | nothing |
| `commands.yml` | one job looping every 5 min; started by `daily.yml` after each board, hourly cron as a backup starter; hands off before 6 h | `monitor/commands_loop.py` — answers the Architect's Telegram commands. Was hourly and GitHub delivered 6 runs in 35 h (measured 14 Oct), so /board could wait six hours | `clv/clv_log.json`, `memory/` — committed after any round that answered something |
| `profiles.yml` | Mondays 04:41 + manual | `data/team_profiles.py` (every team of 29 FotMob competitions) and `data/league_strength.py` (cross-league ratings). Both were "by hand" until 2026-10-14 while ORDER 43 read them on every board | everything under `data/teams/` (the profile snapshot, the team cache, the league ratings and the club-to-league map) — committed weekly; a week that rebuilds nothing prints a `::warning::` |
| `matchbook_ledger.yml` | daily 05:23 + manual | `monitor/matchbook_ledger.py` — reads the live Matchbook agent's graded ledger from the private repo `Tolar07/matchbook-agent` (read-only deploy key) and writes an ANONYMISED summary: bets, won vs expected, CLV against Matchbook's closing price, per market family and source. ORDER 44 shifts each market family's chances by it (`engine/learning.py`); shown in the weekly review | `data/matchbook/summary.json` — committed when it changes; counts and rates only, never a stake, £ or id (this repo is public) |
| `reasoning.yml` | started by every `daily.yml` board run; backup crons 22:17, 07:17, 13:17 | `monitor/reasoning_run.py` → `engine/reasoning.py` — the thinking step (Architect 2026-10-19): Gemini judges each single (back / lower / veto, own chance, reasons). Advisory only | `output/reasoning/reasoning_<date>.json`, `memory/reasoning_record.json` (verdicts vs results) |
| `live.yml` | one job per matchday, started by `daily.yml` after each board; backup crons 11:09/14:09/17:09/19:09; hands off before 6 h | `monitor/live_loop.py` — the matchday minute by minute (shares `live_tracker.round_once`): every board fixture's FotMob score, xG, shots on target and reds beside SportyBet's live 1X2 / goal-line / BTTS prices. One Telegram to the ARCHITECT ONLY per round with an event; a quiet round is silent; a full-time summary at the end | `data/study/<date>/live/<fotmob id>.jsonl`, committed every ~20 min |
| `universe.yml` | every 3 h at :20, and started by every `daily.yml` board run (missed runs just delay grading) | `monitor/universe_sweep.py` — every SportyBet football + basketball game, covered or not: first/last price, graded from Flashscore; once a day the study, plus FotMob post-match stats of the last 3 days' rated fixtures (`data/match_stats.py`); before kick-off each football game gets both teams' FotMob profile (`data/team_profiles.py`) | `data/universe/graded_<month>.jsonl`, `backtest/UNIVERSE_STUDY.md`, `data/match_stats/`, `backtest/MATCH_STATS_STUDY.md`, `data/teams/` (team cache), `backtest/PROFILE_STUDY.md` |
| `commands.yml` | hourly at :05 | `output/telegram_commands.py` | `clv/clv_log.json`, `memory/` |
| `weekly.yml` | Mondays 07:51 | `scripts/weekly_review.py` | — |
| `tests.yml` | every push / PR to main | ruff + mypy gates, `tests/run_all.py` | — |
| `claude-review.yml` | every PR | Claude review; idle until `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` is set | — |
| `backtest.yml` | 2nd of every month 12:13 + manual | full CLV backtest; metrics history | `backtest/results/` |

**Routines (claude.ai, outside the repo)** — they dispatch `daily.yml` on time
because GitHub's cron runs late or not at all:

| Routine | Schedule (UK time) | ID |
|---|---|---|
| OLP XDV evening board | 21:47 daily (`CRON_TZ=Europe/London` since 2026-10-15) | `trig_01Vcrxe7wjgfQAnT42d9Vpbz` and a duplicate `trig_01MsTr3s2u7nnYz8CTx4bhsD` (disabled) |
| OLP XDV morning board | 06:47 daily (`CRON_TZ=Europe/London`) | `trig_01TnihPuzt1q4kCFqgQqxWLi` and a duplicate `trig_014L97BjwDoGsR7hDoENRJoi` (disabled) |
| OLP XDV weekly agent review | Mondays 09:51 (`CRON_TZ=Europe/London`), read-only, push + email | `trig_01RsYF3PXPrkvjGBwiYp3opE` |
| Re-check omniroute-test#2 | one-off reminder for a frozen-branch PR | `trig_01C87oUyMkvBBxeuDvwTQczH` |

Since 2026-10-07 the two board Routines also carry `Tolar07/framework` as a source, so a re-fired or fresh-session run can dispatch (the 7 Oct evening re-fire failed with HTTP 403 without it; the scheduled runs post into a persistent session that already had access). Each slot has two Routines; the duplicate guard (`output/boards/sent_<date>_<slot>`)
makes the second one skip. **GitHub cron is unreliable here:** on 4 Oct the
05:47 board cron fired at 11:16; `news.yml`'s 20-minute cron ran 6 times in
three days (so it is now one looping job the board run starts);
`commands.yml` fires every 3–6 hours rather than hourly.

## 2. Who gets what on Telegram

| Chat | Gets | Set by |
|---|---|---|
| The Architect (`TELEGRAM_CHAT_ID`) | everything | secret |
| bet365 board | the Architect only — `TELEGRAM_OWNER_CHAT_ID` if set, else `TELEGRAM_CHAT_ID` (order 29) | secret |
| NBA board + NBA line watch (live test since 2026-10-07, placed by hand from the codes) | the Architect only — `TELEGRAM_OWNER_CHAT_ID` if set, else `TELEGRAM_CHAT_ID` (order 41) | secret |
| Subscribers | booking codes only (order 33) | secret `TELEGRAM_SUBSCRIBER_CHAT_IDS`, comma-separated |
| Commands | answered for the Architect's chat only | `output/telegram_commands.py` |

The three subscriber chat ids were first collected by the laptop's /start
auto-subscribe (2026-08-24). A public copy with all four ids is still at
`legacy/laptop/memory/telegram_subscribers.txt` — delete it once the supervisor
status shows "subscribers: 3 chat(s)". The 12:46 UTC run on 4 Oct saw the
secret empty: it must be a **repository** secret on Tolar07/framework.

## 3. Secrets and settings

GitHub → Tolar07/framework → Settings → Secrets and variables → Actions →
Repository secrets. Values are never in the repo.

| Secret | Read by | For |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `output/notify.py`, `output/telegram_commands.py` | the bot — **rotate, see §10** |
| `TELEGRAM_CHAT_ID` | notify, commands, `run_daily.py` | the Architect's chat |
| `TELEGRAM_OWNER_CHAT_ID` | `run_daily.py`, notify | optional separate chat for the bet365 board |
| `TELEGRAM_SUBSCRIBER_CHAT_IDS` | `output/notify.py` | subscribers (order 33) |
| `ODDS_API_KEY` | `pipeline/odds.py` | The Odds API, last-resort prices — **rotate, see §10** |
| `MATCHBOOK_LEDGER_KEY` | `matchbook_ledger.yml` | private half of a READ-ONLY deploy key on `Tolar07/matchbook-agent` (fetches its `ledger/`); added 2026-10-15 |
| `GEMINI_API_KEY` | `reasoning.yml` | the Architect's Google AI Studio key (free tier); set 2026-10-19. Optional repo variable `GEMINI_MODEL` pins a model, else the newest stable Flash-Lite |
| `THESPORTSDB_KEY` | `data/thesportsdb_fixtures.py` (falls back to the public key) | fixtures |
| `API_FOOTBALL_KEY` | `data/fixtures_source.py`, `data/api_football_results.py` | fixtures fallback; free plan, ends 2026-10-17 |
| `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` | `claude-review.yml` | PR review — not set |
| `GITHUB_TOKEN` | watchdog, supervisor | automatic |

Read by code but passed by no workflow (laptop only): `ALERT_EMAIL_TO`,
`ALERT_SMTP_*`, `ALERT_WEBHOOK_URL`, `FIRECRAWL_API_KEY`, `PERPLEXITY_API_KEY` — used only by
laptop scripts parked in `legacy/laptop/parked_2026-10-05/` (2026-10-05).

**Settings that live in code** (change only with the Architect):

| Setting | Where |
|---|---|
| Phase, capital switch | `config/__init__.py` (`PHASE = 3`, `CAPITAL_ENABLED`) |
| Leagues scanned | `engine/slate.py` `WHITELIST_LEAGUES`; only leagues with a `SPORTYBET_TOURNAMENT_ID` in `pipeline/odds_sportybet.py` are actually scanned (HNL, Champions League, Europa League and Conference League were added 2026-10-05, market-implied; Turkey, Greece, Austria, Switzerland, Norway and Sweden the same day, model-rated) |
| Board focus (one competition gets the board for a day; the rest are study picks, graded, never sent) | `config/focus.json` (`{"YYYY-MM-DD": ["Champions League"]}`), read by `engine/focus.py` — Architect 2026-10-12 |
| Odds band, 50% floor, tiers | `engine/slate.py` (`DEPLOY_ODDS_MIN/MAX`, `MIN_MODEL_PROB`, `AGREE_PP`, `BANKER_MIN`) |
| Pick preferences, drift, news swap | `run_daily.py` (`UNDER_PREF_PP`, `EV_PREF_PP`, `DRIFT_DEMOTE`, `NEWS_SWAP_PP`) |
| Stakes and stop-loss | `engine/staking.py` (% of bankroll — **no bankroll figure is recorded anywhere**) |
| AI Survivor | `engine/survivor.py` (£100 genesis, £1 stake) |
| Learning | `engine/learning.py` (90-day window, 10 results, 3 match days) |
| Phase 3 CLV gate | `clv/clv_logger.py` (`PHASE3_GATE_MIN_LEGS = 30`, mean must be positive) — see §12 |
| Season | `orchestrator.fit_season_code()` — the last completed season, switching on 1 July (2026-10-05; was a fixed `"2526"`) |
| Team spellings | `engine/name_match.py`, `TEAM_ALIASES` in `pipeline/odds_sportybet.py` |
| NBA teams (ESPN id/code, SportyBet Sportradar id, bet365 draft name, NBA_Betting code) | `engine/nba_teams.py` (`TEAMS`, `BET365_CONFIRMED = False`); all 30 SportyBet ids on file (LAC/SAC/TOR via Sportradar stats, 2026-10-07) — a new or conflicting id is flagged on the run |

## 4. What the system remembers

| Path | Written by | Read by | In git? |
|---|---|---|---|
| `clv/clv_log.json` | `run_daily.py`, `/log` | run_daily, /status, `scripts/olp_query.py` | yes |
| `data/matchbook/summary.json` | `monitor/matchbook_ledger.py` (`matchbook_ledger.yml`) | `scripts/weekly_review.py` | yes (anonymised) |
| `data/universe/graded_*.jsonl.gz` `mb_first` / `mb_last` | `data/matchbook_prices.py` (called by `monitor/universe_sweep.py` every sweep — Matchbook public prices for the same markets, no login; 2026-10-16 bet365 → Matchbook) | `backtest/matchbook_price_study.py` → `backtest/MATCHBOOK_PRICE_STUDY.md` (coverage, both-book returns, SportyBet-above-Matchbook-fair mismatches); `run_nba.py` / `monitor/nba_watch.py` show each NBA pick's Matchbook back price (bet365 lines retired) | yes |
| `output/boards/board_<date>.txt`, `bet365_<date>.txt` | `run_daily.py` | commands, supervisor, olp_query | yes |
| `output/boards/sent_<date>_<slot>` | `daily.yml` | the duplicate guard, supervisor | yes |
| `output/picks/picks_<date>.json` | `engine/picks_ledger.py`, `news_check.py` | learning, staking, scorecard, supervisor, weekly review | yes |
| `output/picks/nba_<date>.json`, `nba_watch_<date>.json` | `run_nba.py` (board), `monitor/nba_watch.py` (watch, `source: watch`) | `run_nba.py` grades both (closing value) and keeps their records apart | yes |
| `output/nba_watch/<date>.json` | `monitor/nba_watch.py` — first sharp line seen per game, LAGs reported | the watch (line moves, no repeat alerts) | yes |
| `output/nba_ladders/<date>.jsonl` | `engine/nba_ladder.py` via `run_nba.py` and the watch — every SportyBet NBA ladder + its fitted centre/spread | `backtest/nba_ladder_study.py` → `backtest/NBA_LADDER_STUDY.md` | yes |
| `output/nba_markets/<date>.jsonl` | `engine/nba_markets.py` via `run_nba.py` and the watch (from 2026-10-13) — every market SportyBet lists on each NBA game, at every look | `backtest/nba_market_study.py` → `backtest/NBA_MARKET_STUDY.md` (daily, `daily.yml`): each market's landed rate vs SportyBet's fair chance, short vs long side; the board's STUDY LINES (order 41) | yes |
| `data/survivor/` | `engine/survivor.py` | survivor | yes |
| `data/sharp/sharp_<date>.json` | `monitor/sharp_list.py` (from 2026-10-14, every `daily.yml` run) — the PARALLEL sharp-value list (order 37 amended): every pick SportyBet prices above the Betfair Exchange's fair odds, with its real booking code, graded in place from Flashscore | `backtest/price_band_study.py` → `backtest/PRICE_BAND_STUDY.md` (board vs study vs sharp list, same grader); it never touches the board | yes |
| `backtest/PRICE_BAND_STUDY.md` | `backtest/price_band_study.py` (by hand and whenever the study is refreshed) — the board's graded record by price band and by tier, recomputed from `output/picks/`: the evidence that withdrew order 3's "safest 1.50" | the Architect, the board's footer, order 37's parallel test | yes |
| `docs/ratifications/2026-10-14-orders-3-7-37.md` | this session (2026-10-14) — the ratification entry for the orders 3 / 7 / 37 amendment, written out because `RATIFICATIONS.md` is on the protected list | the Architect, to append to `RATIFICATIONS.md` | yes |
| `data/universe/graded_<date>_<HHMM>.jsonl.gz` (+ the first plain `graded_2026-10.jsonl`) | `engine/universe.py` via `universe.yml` — one compressed file per sweep, one line per graded game (both sports, every SportyBet competition): first/last price, covered or not, result | `backtest/universe_study.py` → `backtest/UNIVERSE_STUDY.md`; nothing selects on it (2026-10-07) | yes |
| `data/universe/notes/<date>.sent` | `monitor/universe_sweep.py` — marks the day's paper-book note as sent to the Architect (once a day, first sweep after 06:00 UTC) | the sweep | yes |
| `data/cache/` (the universe sweep's pending games, gzipped) | the universe sweep — prices of games not yet graded | the sweep | Actions cache only (`universe.yml`) |
| `data/match_stats/<month>.jsonl`, `team_profiles.json` | `data/match_stats.py` via `universe.yml` — FotMob post-match stats (possession, xG, shots, big chances, corners, cards …) of every fixture the board rated | `backtest/match_stats_study.py` → `backtest/MATCH_STATS_STUDY.md` (league styles, what decides matches, team profiles); nothing selects on it (2026-10-07) | yes |
| `backtest/PAPER_BOOK.md` | `backtest/paper_book_study.py` (daily, via `universe.yml`) — the system's own £1 paper bets: fixed rules (`engine/paper_book.py`) on every graded game at the first price, return ± se, CLV, why they won/lost, paper 3-leg accas (landed vs what their prices promised), verdict (READY TO PROPOSE needs 100+ bets, 2 se, positive CLV); recomputed from `data/universe/`, no extra store | the Architect (proposals) | yes |
| `backtest/BETFAIR_CLOSE_STUDY.md` | `backtest/betfair_close_study.py` (by hand, 2026-10-12) — the walk-forward goals model and bet365 vs the Betfair Exchange closing price (football-data BFEC*): forecast accuracy, model-into-close blend, line movement, value of picks against the close; fit records cached in `backtest/cache/` (not committed) | the Architect, sessions; nothing selects on it | yes (the .md and the script) |
| `data/study/<date>/` | by hand (sessions), from 2026-10-13 — study boards built outside the live run: the boards, every booking code made that day (README.md lists them), the scripts that built them | graded at the end of the day by the session; nothing selects on them | yes |
| `data/teams/` — `latest.json.gz`, `profiles_<date>.json.gz`, `team_cache.json.gz` | `data/team_profiles.py` — `latest`/`profiles_<date>` by hand (`python data/team_profiles.py`): every team of 29 competitions from FotMob (squad, positions, injuries, coach, formation, form, season stats per match, style tiers against its league); `team_cache` by `universe.yml` (compact profiles, 7-day cache) | the sweep attaches both teams' profile + read to every football game before kick-off (kept in `data/universe/` when graded); paper book P1–P5 (`engine/paper_book.py`); `backtest/profile_study.py` → `backtest/PROFILE_STUDY.md` (daily). Nothing on the live board selects on it (2026-10-13) | yes (latest + cache; dated snapshots local) |
| `data/teams/league_strength.json`, `data/teams/team_leagues.json` | `data/league_strength.py` by hand (from 2026-10-13): one rating per FotMob league (goals per match), fitted from matches between leagues — European competitions + qualifiers, other continents' club competitions, the European countries' domestic cups — and each club's current league | `data/team_profiles.py`: a cross-league profile read moves each side's goal hint by half the gap; an unrated league reads PENDING | yes |
| Tipster slips from X (slips, decoded legs, grades, per-poster TIPSTER_STUDY.md with closing-line value of every leg against the universe sweep's last SportyBet price (2026-10-12), nameless aggregates.json) | collector `C:\Users\Motunrayo\tipster_slips\` on the desktop (Claude in Chrome), on TWO LIVE Windows scheduled tasks — neither of them among the 14 OLP desktop tasks disabled on 2026-10-08 (checked from the desktop 2026-10-14): **"Tipster Slip Collector (X, read-only)"** runs `collect.ps1` (Ready; last run 14 Oct 12:10 UTC, result 0) and **"OLP_TipsterSlips"** runs `run_cycle.ps1` (Running when checked, ~3-hourly). The folder also holds `collect_ucl.ps1`, `decoded_*.jsonl`, `graded_*.jsonl`, `TIPSTER_STUDY.md`, `aggregates.json`, `logs/` and ~25 ad-hoc helper scripts. State 2026-10-14: **277 slip lines over 7–14 Oct (07:2, 08:22, 09:33, 10:29, 11:25, 12:68, 13:71, 14:27) — collection never stopped; GRADING stops at 12 Oct and `TIPSTER_STUDY.md` was last written 13 Oct 12:08**, so ~98 lines are ungraded and nothing has been reported to the Architect since. Analysis runs on the desktop: `monitor/tipster_run.py --dir <that folder>` (`engine/tipsters.py`, `backtest/tipster_study.py`) | the Architect only — PRIVATE on the desktop by the Architect's decision (2026-10-08): handles and per-poster records never enter any repo; only nameless aggregates may feed learning | **no — desktop only** |
| `data/cups/results.json` | `data/european_archive.archive_cups` (every run, from Flashscore) — Turkish Cup ties, every round, with both clubs' divisions | `backtest/cup_study.py` → `backtest/TURKISH_CUP_STUDY.md`; nothing prices the cup yet (2026-10-07) | yes |
| `data/european/results.json` | `data/european_archive.py` (every run, from Flashscore) | nothing yet — the history a current-season European model needs (2026-10-05) | yes |
| `memory/telegram_offset.json` | commands | commands | yes |
| `memory/corrections.csv` | `/note` | heartbeat + weekly review list the open ones (`engine/loss_watch.open_notes`, order 39) | yes |
| `memory/knowledge.json` | daily run (`engine/loss_watch.remember`) | supervisor (updated today?), sessions; what was learned: market x competition results, flags, learning corrections, 120-day history | yes |
| `memory/proposals.json` | daily run (`loss_watch.propose`), `/approve` `/reject` | daily run (approved blocks drop candidates), heartbeat, `/proposals`, supervisor | yes |
| `logs/daily_<date>.log` (Run ID, delivery notes) | `run_daily.py` | nobody in CI — **lost after every run**; the Actions job log has it | no |
| `data/cache/`, `backtest/cache/` | the fetchers | the fetchers | Actions cache only |
| `data/sportybet/` | laptop dump, 2026-08-23 | nothing yet — every SportyBet country/tournament id, for wider coverage | yes |
| `docs/records/` | — | — | the Architect's production intent (10 Aug) and the recovered real-money track record |

`leagues.json` (August's 61-league registry) and `fixtures.json` (read by nothing) were parked in
`legacy/laptop/parked_2026-10-05/` on 2026-10-05. `data/heartbeat/` is the input
`scripts/rebuild_survivor.py` rebuilds AI Survivor from (recovery only).

## 5. Outside sources

| Source | Module | Key |
|---|---|---|
| SportyBet NG — prices, booking codes, closing prices | `pipeline/odds_sportybet.py`, `pipeline/sportybet_booking.py`, `news_check.py` | none |
| football-data.co.uk — history, bet365 prices, Betfair Exchange fair odds (sharp check) | `data/football_data_source.py`, `pipeline/odds_footballdata.py`, `verification/fixture_check.py`, `pipeline/sharp.py` | none |
| ESPN (+ DraftKings prices) | `data/espn_fixtures.py`, `pipeline/odds_verify.py` | none |
| FotMob — team news, lineups | `data/fotmob.py` | none |
| Flashscore feed — results, first-half score (full time − the feed's second-half BC/BD), European results archive | `data/flashscore_results.py`, `data/european_archive.py` | public header |
| Understat — xG | `engine/xg_model.py` | none |
| International results (GitHub) | `data/international_source.py` | none |
| TheSportsDB, API-Football, The Odds API | see §3 | secrets |
| Telegram, GitHub API | notify, commands, watchdog, supervisor | secrets |

## 6. Documents — which to trust

**Live** (they win over everything else): `CLAUDE.md`, `STANDING_ORDERS.md`
(orders 1–33, test-enforced), the CURRENT STATE block of
`docs/obsidian-vault/STATE.md`, this file, `docs/LINEAGE_MERGE_2026-10-03.md`,
`.claude/agents/olp-xdv-*.md`, `backtest/*_STUDY.md`.

**Register:** `docs/obsidian-vault/Rules.md` is still where HR/ID numbers are
looked up; the code it names is the laptop line's.

**Directive logs stopped:** `ARCHITECT_DIRECTIVES.md` (last 2026-08-21),
`RATIFICATIONS.md` (2026-08-23), `docs/obsidian-vault/Decisions Log.md`
(2026-08-31). Every directive since is a standing order.

**Historical** (marked so at the top, kept as record): `Protected Constants.md`,
`Decisions Log.md`, `Fixture Gathering Method.md`, `api-football-integration.md`,
`Knowledge-Persistence.md`, `Vault-Memory-Index.md`, `Viking Match Analysis 2026-08-18.md`,
`Agents.md`, `Architecture.md`, `Loops.md`, `OLP XDV.md`,
`OLP_XDV_Framework_Index.md`, `docs/STATE.md` (22 Aug), `docs/RUNBOOK_DISASTER_RECOVERY.md`,
`docs/LEAGUE_DATA_COVERAGE.md`, `docs/LEAGUE_INTELLIGENCE_DOSSIER.md`,
`docs/OLP_XDV_MASTER_DOCUMENTATION_2026-08-11.md`, `docs/INTELLIGENCE_REPORT.md`,
`docs/AUTOMATED_T3_RESULTS_PLAN.md`, `docs/OLP_XDV_COMPILED_REFERENCE.md`.

`Telegram Output Spec.md` is the Architect's text and is not edited; its status
section at the bottom marks where the orders supersede it.

`docs/obsidian-vault/Open Questions.md` was overwritten by an agent error on
2026-08-27 (`66d84aa`); its 18 Aug questions were restored on 2026-10-04.

## 7. Parked code — `legacy/`

`legacy/laptop/` (the laptop line), `legacy/laptop_tests/`,
`legacy/olpxdv_framework/` — never imported, never run (`legacy/laptop/README.md`).
What the laptop had that the live line does not:

| Feature | Parked at | Architect asked? |
|---|---|---|
| ~~Kickoff time on every fixture~~ — BUILT 2026-10-04 (order 28, KO column, Lagos time) | `legacy/laptop/output/production_board.py` | yes — 17 Sep spec; 19 Sep "the country and the time" |
| Booking-code odds check: a code's odds must equal the legs' product, ±5% (ID415) | `legacy/laptop/booking/booking_codes.py` | yes — 20 Aug, ratified 23 Aug |
| bet365 limited to top-flight European leagues | `legacy/laptop/booking/bet365_scope.py` | 19 Sep (order 29 now lists the full market) |
| Match context: rest, fixture congestion, stage ("motivation"), ±10% | `legacy/laptop/engine/context.py` | 19 Sep |
| Phone commands /send /run /produce /code /fixtures /stats, buttons | history `81ef177:output/telegram_commands.py` | /send, /produce bet, /stats — yes |
| Email copy of each board (ID407) | `legacy/laptop/output/email_deliver.py` | yes — 6 Aug |
| Web dashboard (ID412) | `legacy/laptop/webapp/` | yes — August |
| In-play monitor (order 8 names it) | `legacy/laptop/scripts/live_monitor.py` | order 8 |
| Feed freshness / quota / league drop-out alerts | `legacy/laptop/monitor/health_monitor.py` | yes — 7 Aug |
| Telegram commands answered within a minute | `legacy/laptop/output/telegram_webhook.py` | implied |

Data worth knowing about: `legacy/laptop/2526` (SQLite — the only August CLV
record: 76 paper legs, 48 with CLV, 6 produced bets);
`legacy/laptop/booking/team_map.py` (~900 SportyBet name mappings vs ~165 live);
`legacy/laptop/booking/league_map.py` (bet365 country/league names — use when
confirming the bet365 board's names); the laptop boards of 7 Aug–19 Sep under
`legacy/laptop/output/boards/`; `legacy/laptop/clv/phase3_gate.json` is a
hand-edited gate record ("test-approval") — never trust it.

## 8. Only in git history

| What | Where | How to read |
|---|---|---|
| The laptop versions of 21 live files (run_daily, produce_bet, telegram_commands, markets, odds, flashscore, football_data…) — lost to main in the 3 Oct merge, not in `legacy/` | branch `elo-persistence` (tip `81ef177`), merged by `55f1da6` | `git fetch origin elo-persistence` (the default fetch skips it), then `git show 81ef177:<path>` |
| PR #1's 16 Sep fixes: production floor of 10 matches per team, whole-season Flashscore fetch, TheSportsDB by league, a 500-line update to the league registry (`legacy/laptop/parked_2026-10-05/leagues.json`) | branch `claude/fix-cache-contamination`, merge `021dd2e` ("main wins") | `git show origin/claude/fix-cache-contamination:<path>` |
| A developer `CLAUDE.md` (17 Sep), never merged | branch `claude/claude-rc-xj5xfe` | superseded |

The other 71 `claude/*` branches are fully on main. Every branch is a frozen
backup: bring nothing back unless the Architect names it.

## 9. Outside this repo

**Workspace repo `Tolar07/omniroute-test`** (public; this repo is its
submodule at `omniroute-test:olp_xdv_agent/olp_xdv`):
- `omniroute-test:olp_xdv_agent/ticket1.PNG` … `ticket 4.PNG`, `Capture*.PNG` — screenshots of real bets (`ticket1` shows an IP address). The track record itself is copied to `docs/records/`.
- `omniroute-test:legacy/workspace/` — a second parked pipeline, plus the boards sent 22 Aug–9 Sep, graded accas of 22 Aug, and `feed_audit.jsonl` with a ₦50,000 bankroll (the only bankroll figure anywhere).
- `omniroute-test:docs/STATE.md` — the workspace journal.
- `omniroute-test:external/football-prediction/crosschecks/` — six de-vig / Dixon-Coles cross-check scripts.
- `omniroute-test:.claude/settings.json` — the laptop's Claude settings; it holds the Obsidian Local REST token in plain text (§10).
- **24 empty folders** (gitlinks with no address, so their code exists only on the laptop): `automaton` (holds `constitution.md`, the bright-lines file), `closing_edge`, `sports-skills` (this repo's `sports-*` skills point to it), `graphify`, `ruflo`, `claude-code-action`, `free-llm-api-resources`, and 17 under `external/`.

**The laptop** (`C:\Users\Motunrayo\omniroute test`): both `.env` files (all
keys); `~/.claude/projects/C--Users-Motunrayo-omniroute-test/memory/` (12
memory notes the workspace `CLAUDE.md` lists); `memory/conversations/`
(transcripts, git-ignored); `Documents\OLP_XDV_Vault` (retired mirror);
`analysis\SECRETS.local.md`; the Windows scheduled tasks — the Architect
decided on 3 Oct to retire them (STATE open item 6), the workspace journal still
says ten "stay on" (result check, hourly fixtures, SportyBet cache, closing
line, Flashscore scrape, live monitor, auto-sync, team-name audit, match
analysis, MCP watchdog).

**The live Matchbook agent** (Architect amendment 2026-10-15, the one exception to the
capital bright line — it lives OUTSIDE this repo, which still never stakes): code in
`omniroute-test:matchbook_live/` (branch `ccr-8337175b-znydr8`) deployed to the private
repo `Tolar07/matchbook-agent`, run every 15 min by a self-hosted runner `matchbook-uk` on
the laptop (state in `C:\olp\matchbook_state`). It READS this repo's `output/picks/` and
publishes its graded ledger to its own `ledger/`, which `matchbook_ledger.yml` reads back.
Secrets there: the Matchbook login, the OmniRoute oracle, the Telegram bot.

**Elsewhere:** private repos `Tolar07/closing_edge` and
`Tolar07/CLV-log-and-framework-docs` (empty); the first track record (3 Aug) in
the claude.ai chat "Deep level system loading"; the Routines in §1; the
SportyBet and bet365 accounts (no details recorded, on purpose).

## 10. Credentials exposed in public history — rotate

Deleting a file does not remove it from a public repo's history; the fix is a
new key.

| What | Where it shows | Do |
|---|---|---|
| Telegram bot token | commit `22e057e` (`send_board.py`, 16 Aug) | @BotFather → /revoke → new token into `TELEGRAM_BOT_TOKEN` |
| The Odds API key | printed in laptop boards of 11–15 Aug (redacted in the tree 2026-10-04, still in history) | new key at the-odds-api.com → `ODDS_API_KEY` |
| TheSportsDB key | workspace commit `a3f6478e` | new key → `THESPORTSDB_KEY` |
| Obsidian Local REST token | `omniroute-test:.claude/settings.json` (current tree) | regenerate in Obsidian; keep it out of the repo |
| Admin dashboard password (first 3 characters) | `API Keys.md` (redacted 2026-10-04, still in history) | change it if the dashboard is ever used again |

## 11. Known defects (found 2026-10-04; struck through = fixed)

- ~~`news.yml` ran 6 times in three days~~ — FIXED 2026-10-04: one looping job started by the board run (`monitor/news_loop.py`). If main moves and the picks file conflicts, that round's results are not saved and the next round re-checks (an alert can repeat).
- ~~`/log` legs had no match date and were never graded~~ — FIXED 2026-10-04: `/log` finds the match on a recent board (league + date) or takes a date you add, and refuses wording it can't settle.
- `memory/corrections.csv` (`/note`) is listed on the heartbeat and in the weekly review until acted on (2026-10-05, order 39); nothing applies it automatically.
- ~~The capital refusal message said capital is disabled at PHASE 3~~ — corrected 2026-10-04.
- ~~HNL, Champions League and Europa League are whitelisted but never scanned~~ — FIXED 2026-10-05: SportyBet ids added; priced market-implied (with the Conference League).
- `daily`, `commands` and `news` push with `pull --rebase || true; push || echo` in separate concurrency groups — a conflict silently drops that run's commit. **2026-10-08: it did** — the 7 Oct evening board's commit was dropped and a late cron re-sent the board to everyone. Fixed for the board: the sent marker is saved to main on its own right after delivery (`monitor/push_marker.py`), NBA ladder logs merge as a union (`.gitattributes`), and the persist step now warns instead of failing silently. `commands` and `news` keep the old pattern.
- The run log (with the Run ID) is not kept after a CI run (order 30 says it is).
- `.claude/hooks/check_protected_files.py` guards files that no longer exist; the real constants (`config/__init__.py`, `engine/slate.py`) are unguarded. No hook blocks `git add -A`.
- Fixed 2026-10-05: `backtest.yml`'s dead step (a missing test) removed and it runs monthly; `sync-health.yml` (pointed at a folder not in this repo) parked in `legacy/laptop/parked_2026-10-05/`.
- Two corrupted headings in the STATE journal, under the 2026-09-05 entry (`---ork:`, `---ospective`); the original text is lost.

## 12. Waiting on the Architect

- **Phase 3 CLV gate** — three values on record: 0 legs, gate waived (`ARCHITECT_DIRECTIVES.md`, 21 Aug); 12 legs, mean not required (Decisions Log, 24 Aug); 30 legs and a positive mean (the code). The code rules until the Architect says which stands (a protected constant).
- **Laptop scheduled tasks** — retire (STATE, 3 Oct) or keep (workspace journal)?
- **HR59** has two meanings on record ("Architect Authorization Protocol", Aug; "Traceable output", now).
- The lost and parked features in §7 and §8 — which to bring back.
- The duplicate Routines in §1 — keep one per slot?
