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

Everything live runs in GitHub Actions on `main`. Times UTC (Lagos = UTC+1).

| Workflow | When | Runs | Commits back |
|---|---|---|---|
| `daily.yml` | 20:47 (evening, tomorrow's card), 05:47 (morning refresh); also dispatched with `target_date` + `slot` | `run_daily.py --only-production --heartbeat` | `clv/clv_log.json`, `output/boards/`, `output/picks/`, `data/survivor/`, `memory/` |
| `watchdog.yml` | 23:17, 08:17 | `monitor/run_watchdog.py` — starts a slot that never ran | — |
| `supervisor.yml` | after every `daily.yml` run | `monitor/supervisor.py` — one status message | — |
| `news.yml` | one job looping every 20 min 09:00–20:40, started by `daily.yml` after each board; backup cron every 2 h; hands itself on before GitHub's 6-hour limit | `monitor/news_loop.py` → `news_check.py` — lineups, price drift, closing price | `output/picks/`, each round |
| `commands.yml` | hourly at :05 | `output/telegram_commands.py` | `clv/clv_log.json`, `memory/` |
| `weekly.yml` | Mondays 07:51 | `scripts/weekly_review.py` | — |
| `tests.yml` | every push / PR to main | ruff + mypy gates, `tests/run_all.py` | — |
| `claude-review.yml` | every PR | Claude review; idle until `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` is set | — |
| `backtest.yml`, `sync-health.yml` | manual | CLV backtest; vault sync check | `backtest/results/` |

**Routines (claude.ai, outside the repo)** — they dispatch `daily.yml` on time
because GitHub's cron runs late or not at all:

| Routine | Schedule (Lagos) | ID |
|---|---|---|
| OLP XDV evening board | 21:47 daily | `trig_01Vcrxe7wjgfQAnT42d9Vpbz` and a duplicate `trig_01MsTr3s2u7nnYz8CTx4bhsD` |
| OLP XDV morning board | 06:47 daily | `trig_01TnihPuzt1q4kCFqgQqxWLi` and a duplicate `trig_014L97BjwDoGsR7hDoENRJoi` |
| OLP XDV weekly agent review | Mondays 09:51, read-only, push + email | `trig_01RsYF3PXPrkvjGBwiYp3opE` |
| Re-check omniroute-test#2 | one-off reminder for a frozen-branch PR | `trig_01C87oUyMkvBBxeuDvwTQczH` |

Each slot has two Routines; the duplicate guard (`output/boards/sent_<date>_<slot>`)
makes the second one skip. **GitHub cron is unreliable here:** on 4 Oct the
05:47 board cron fired at 11:16; `news.yml`'s 20-minute cron ran 6 times in
three days (so it is now one looping job the board run starts);
`commands.yml` fires every 3–6 hours rather than hourly.

## 2. Who gets what on Telegram

| Chat | Gets | Set by |
|---|---|---|
| The Architect (`TELEGRAM_CHAT_ID`) | everything | secret |
| bet365 board | the Architect only — `TELEGRAM_OWNER_CHAT_ID` if set, else `TELEGRAM_CHAT_ID` (order 29) | secret |
| Subscribers | everything except the bet365 board (order 33) | secret `TELEGRAM_SUBSCRIBER_CHAT_IDS`, comma-separated |
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
| `THESPORTSDB_KEY` | `data/thesportsdb_fixtures.py` (falls back to the public key) | fixtures |
| `API_FOOTBALL_KEY` | `data/fixtures_source.py`, `data/api_football_results.py` | fixtures fallback; free plan, ends 2026-10-17 |
| `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` | `claude-review.yml` | PR review — not set |
| `GITHUB_TOKEN` | watchdog, supervisor | automatic |

Read by code but passed by no workflow (laptop only): `ALERT_EMAIL_TO`,
`ALERT_SMTP_*`, `ALERT_WEBHOOK_URL` (`monitor/alert_dispatcher.py`),
`FIRECRAWL_API_KEY`, `PERPLEXITY_API_KEY` (`monitor/mcp_health.py`).

**Settings that live in code** (change only with the Architect):

| Setting | Where |
|---|---|
| Phase, capital switch | `config/__init__.py` (`PHASE = 3`, `CAPITAL_ENABLED`) |
| Leagues scanned | `engine/slate.py` `WHITELIST_LEAGUES`; only leagues with a `SPORTYBET_TOURNAMENT_ID` in `pipeline/odds_sportybet.py` are actually scanned (HNL, Champions League, Europa League and Conference League were added 2026-10-05, market-implied; Turkey, Greece, Austria, Switzerland, Norway and Sweden the same day, model-rated) |
| Odds band, 50% floor, tiers | `engine/slate.py` (`DEPLOY_ODDS_MIN/MAX`, `MIN_MODEL_PROB`, `AGREE_PP`, `BANKER_MIN`) |
| Pick preferences, drift, news swap | `run_daily.py` (`UNDER_PREF_PP`, `EV_PREF_PP`, `DRIFT_DEMOTE`, `NEWS_SWAP_PP`) |
| Stakes and stop-loss | `engine/staking.py` (% of bankroll — **no bankroll figure is recorded anywhere**) |
| AI Survivor | `engine/survivor.py` (£100 genesis, £1 stake) |
| Learning | `engine/learning.py` (90-day window, 10 results, 3 match days) |
| Phase 3 CLV gate | `clv/clv_logger.py` (`PHASE3_GATE_MIN_LEGS = 30`, mean must be positive) — see §12 |
| Season | `orchestrator.fit_season_code()` — the last completed season, switching on 1 July (2026-10-05; was a fixed `"2526"`) |
| Team spellings | `engine/name_match.py`, `TEAM_ALIASES` in `pipeline/odds_sportybet.py` |

## 4. What the system remembers

| Path | Written by | Read by | In git? |
|---|---|---|---|
| `clv/clv_log.json` | `run_daily.py`, `/log` | run_daily, /status, `scripts/olp_query.py` | yes |
| `output/boards/board_<date>.txt`, `bet365_<date>.txt` | `run_daily.py` | commands, supervisor, olp_query | yes |
| `output/boards/sent_<date>_<slot>` | `daily.yml` | the duplicate guard, supervisor | yes |
| `output/picks/picks_<date>.json` | `engine/picks_ledger.py`, `news_check.py` | learning, staking, scorecard, supervisor, weekly review | yes |
| `data/survivor/` | `engine/survivor.py` | survivor | yes |
| `data/european/results.json` | `data/european_archive.py` (every run, from Flashscore) | nothing yet — the history a current-season European model needs (2026-10-05) | yes |
| `memory/telegram_offset.json` | commands | commands | yes |
| `memory/corrections.csv` | `/note` | **nothing** (see §11) | yes |
| `logs/daily_<date>.log` (Run ID, delivery notes) | `run_daily.py` | nobody in CI — **lost after every run**; the Actions job log has it | no |
| `data/cache/`, `backtest/cache/` | the fetchers | the fetchers | Actions cache only |
| `data/sportybet/` | laptop dump, 2026-08-23 | nothing yet — every SportyBet country/tournament id, for wider coverage | yes |
| `docs/records/` | — | — | the Architect's production intent (10 Aug) and the recovered real-money track record |

Tracked but read by nothing: `config/leagues.json` (the 61-league registry of
August), `fixtures.json`, `data/heartbeat/`.

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
| PR #1's 16 Sep fixes: production floor of 10 matches per team, whole-season Flashscore fetch, TheSportsDB by league, a 500-line `config/leagues.json` update | branch `claude/fix-cache-contamination`, merge `021dd2e` ("main wins") | `git show origin/claude/fix-cache-contamination:<path>` |
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
- `memory/corrections.csv` (`/note`) is read by nothing — `/note` now says so instead of claiming the corrections are applied.
- ~~The capital refusal message said capital is disabled at PHASE 3~~ — corrected 2026-10-04.
- ~~HNL, Champions League and Europa League are whitelisted but never scanned~~ — FIXED 2026-10-05: SportyBet ids added; priced market-implied (with the Conference League).
- `daily`, `commands` and `news` push with `pull --rebase || true; push || echo` in separate concurrency groups — a conflict silently drops that run's commit.
- The run log (with the Run ID) is not kept after a CI run (order 30 says it is).
- `.claude/hooks/check_protected_files.py` guards files that no longer exist; the real constants (`config/__init__.py`, `engine/slate.py`) are unguarded. No hook blocks `git add -A`.
- `backtest.yml` calls a test that does not exist; `sync-health.yml` points at a folder that does not exist in this repo.
- Two corrupted headings in the STATE journal, under the 2026-09-05 entry (`---ork:`, `---ospective`); the original text is lost.

## 12. Waiting on the Architect

- **Phase 3 CLV gate** — three values on record: 0 legs, gate waived (`ARCHITECT_DIRECTIVES.md`, 21 Aug); 12 legs, mean not required (Decisions Log, 24 Aug); 30 legs and a positive mean (the code). The code rules until the Architect says which stands (a protected constant).
- **Laptop scheduled tasks** — retire (STATE, 3 Oct) or keep (workspace journal)?
- **HR59** has two meanings on record ("Architect Authorization Protocol", Aug; "Traceable output", now).
- The lost and parked features in §7 and §8 — which to bring back.
- The duplicate Routines in §1 — keep one per slot?
