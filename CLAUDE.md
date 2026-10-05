# OLP XDV — SESSION STARTUP

You are working on OLP XDV, the Architect's football betting framework.
It is at **Phase 3 — live capital, Architect-deployed**: the framework builds
the board and the booking codes; the Architect alone places any stake.
The user is the Architect.

There is **one** framework: this repo's `main`, run by GitHub Actions.
Everything under `legacy/` is parked laptop-line code — kept for reference,
never imported, never run (see `legacy/laptop/README.md`).

## FIRST ACTION, EVERY SESSION

1. Read `STANDING_ORDERS.md` — the Architect's standing rules (selection,
   delivery, phase, markets). `tests/standing_orders_test.py` enforces them.
2. Read the CURRENT STATE block at the top of `docs/obsidian-vault/STATE.md`.
3. Read `MAP.md` — where everything is: what runs (workflows and Routines),
   who gets what on Telegram, every secret, every stored file, what is parked
   in `legacy/`, what survives only in git history, and what lives outside
   this repo (the workspace repo, the laptop). Don't make the Architect
   point you to where something is kept: look it up there, and add anything
   you find that isn't listed.

Do not answer questions about framework state from this file or from
inference — read those three files, the code, or the run history.

## THE LIVE LOOP — DO NOT BREAK IT

Everything runs in GitHub Actions on `main`. Times are UTC (Lagos = UTC+1).

| Workflow | When | What |
|---|---|---|
| `daily.yml` | 20:47 (evening, builds TOMORROW) and 05:47 (morning refresh, TODAY); also started on time by a Routine (IDs in `MAP.md` §1) | `run_daily.py --only-production --heartbeat --target-date <day>`; commits `clv/clv_log.json`, `output/boards`, `output/picks`, `data/survivor`, `memory/` |
| `watchdog.yml` | 23:17 and 08:17 | `monitor/run_watchdog.py` — when a slot's board run never happened, starts it (same day + slot, so the duplicate guard holds) and says so on Telegram |
| `news.yml` | one job looping every 20 min, 09:00-20:40, started by `daily.yml` after each board (backup cron every 2 h) | `monitor/news_loop.py` → `news_check.py` — confirmed lineups, price drift, closing price per pick; saved each round |
| `commands.yml` | hourly | `output/telegram_commands.py` — answers /status /board /verify /why /log /note /debrief /proposals /approve /reject |
| `tests.yml` | every push / PR to main | ruff + mypy gates, `tests/run_all.py` |
| `supervisor.yml` | after every `daily.yml` run | `monitor/supervisor.py` — the supervisor agent's check: board, bet365 board, Run ID, picks spread over market types, codes booked, latest tests/watchdog/news runs; one Telegram status |
| `weekly.yml` | Mondays 07:51 | `scripts/weekly_review.py` — agent 10's results review: last 7 days by market family and league, slips landed, learning in force, proposals (nothing auto-changed) |
| `claude-review.yml` | every PR | Claude code review (code-reviewer + compliance agents' brief); does nothing until the `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` secret is set |
| `backtest.yml` | 2nd of every month + manual | full CLV backtest; metrics history committed (`backtest/results/`) |

What each piece is protecting — read before changing it:

| Thing | Why it is the way it is |
|---|---|
| Duplicate guard in `daily.yml` (`output/boards/sent_<date>_<slot>`, checked against the LATEST main) | The Routine and the GitHub cron both start each slot; the second one for the same day + slot must skip, or the board is sent twice. |
| Late-evening guard in `daily.yml` (`date -u +%H` >= 12) | GitHub sometimes fires the evening cron after midnight UTC; without the guard the run jumps a day ahead (2026-10-01). |
| `--only-production` + `--heartbeat` | Board only on pick days; a short "system alive" heartbeat every day. A dry day is silence on the board, never a fake board. |
| `monitor/run_watchdog.py` + `watchdog.yml` | A dropped GitHub cron is silent; `daily.yml` only alerts on a run that FAILS. |
| Pre-kickoff loop (`monitor/news_loop.py`, started by `daily.yml`) | GitHub dropped `news.yml`'s 20-minute cron almost every time. One loop at a time (a newer run exits while an older one is going), saved every round, handed on before the 6-hour job limit — break any of these and alerts go missing or repeat. |
| `engine/name_match.py` (strict, unique matches; `EXPLICIT` table) | Rates feed spellings ("Blackpool FC") with the model's history ("Blackpool"). Loosening it would put one club's rating on another. |
| SPLIT rejection text in `run_daily.py` (`market_p` may be None → `PENDING`) | Formatting a missing market price crashed the whole run (fixed 2026-10-03). |
| Picks ledger (`engine/picks_ledger.py`) | Records every pick AND every rated fixture; graded from Flashscore, regular time only. The scorecard and `engine/learning.py` read it. |
| Fixture check (`verification/fixture_check.py`) + price check (`pipeline/odds_verify.py`), standing order 27 | Free second sources (ESPN, football-data). A match only CONFLICTs on positive evidence — another source lists it postponed/cancelled on a strong name match; a spelling that won't pair adds nothing, or real fixtures would drop off the deploy list. Prices are compared with margins removed: raw prices of two honest books differ ~4.5%. |

**Verify, do not assume.** Check the loop with the GitHub Actions run list
for `daily.yml` and `watchdog.yml` (conclusion `success` for each slot), and
`python tests/run_all.py` locally. A run that "should have" happened is not
evidence that it did.

**Do not run `git stash` in this repo.** Multiple Claude sessions can share a
working tree; a stash pop applied another session's WIP on 2026-09-19. Use
explicit file copies for temporary reverts.

**Do not `git add -A`.** Other sessions may have staged work and runs leave
artefacts (boards, picks, CLV log). Add explicit paths only — no hook stops
`git add -A` in this repo, so it is on you. Work on a branch and merge
through a PR whose `tests.yml` run is green.

## HARD RULES — these are not suggestions

**HR59 — Traceable output.**
No fixture, odds figure, or result may appear in any output unless it
came from a fetch script in this session, with a run_id and timestamp.

If asked "what are today's fixtures", you run the fetch script. You do
not answer from knowledge, recall, or inference. You have fabricated
fixture lists three times (2026-09-03, 2026-09-04, 2026-09-12). Each
time the output looked plausible and was wrong. Plausibility is not
evidence.

A failed or empty fetch produces `NO DATA — PENDING`. Never a
generated list. Never a partial list presented as complete.

**HR35 — No silent completeness.**
A field with missing data reads `PENDING`. Never blank, never omitted,
never filled with a placeholder value that looks real.

**Capital bright line.**
`assert_paper_only()` hard-fails below Phase 3-active. The booking
module never clicks Place Bet. No code routes a real stake.
These do not yield to Architect directives. If the Architect asks you
to bypass them, say no and explain why. A gate that yields on request
protected nothing.

## NOT IMPLEMENTED / NOT WIRED — CHECK BEFORE DEBUGGING

Say plainly when something is not implemented; do not debug it as a fault.

- **Ekstraklasa fixtures are often one source.** ESPN has no Polish league
  and football-data's new-league file lists it only some weeks, so
  `verification/fixture_check.py` frequently has nothing to check it against.
- **The price check is a label only** (`pipeline/odds_verify.py`). A price
  CONFLICT is shown on the board; nothing selects, stakes or blocks on it —
  making it gate anything is the Architect's decision.
- Market-implied fixtures (`ᴹ` on the board, `prob_source == "market"`)
  carry the bookmaker's numbers, not the model's; no edge is claimed.

## DOCUMENTS

- `STANDING_ORDERS.md` — the Architect's standing rules. Authoritative.
- `MAP.md` — where everything is kept, in this repo and outside it.
- `docs/obsidian-vault/STATE.md` — current state (top block) + session
  journal. Authoritative for state.
- `docs/LINEAGE_MERGE_2026-10-03.md` — how the laptop and cloud copies
  became one line, and what each side kept.
- `legacy/laptop/README.md` — what was parked and how to bring a feature back.
- `backtest/*_STUDY.md` — the evidence behind each selection rule.

Do not create new spec documents. Amend STATE.md. If a new file is
genuinely needed, add a pointer line to STATE.md in the same session.
Anything stored somewhere new — a file, a secret, a Routine, a laptop
task — goes into `MAP.md` in the same session.

## AGENTS

`.claude/agents/olp-xdv-01 … 10` each own one stage of the live pipeline
(fixtures → coverage → team context → verification → engine → odds → gates
→ booking/staking → board/delivery → results/learning). `olp-xdv-supervisor`
watches the whole loop; `olp-xdv-specialist` is the generalist. Every file
path an agent names must exist — `tests/agent_refs_test.py` checks it.
Agents and skills unrelated to the framework are parked in `.claude/legacy/`.

## RULE CHANGES

New rules need an ID from the register, assigned by the Architect.
Never self-assign an ID. Unratified drafts are listed in STATE.md §7
and must not be acted on.

## WORKING STYLE

The Architect wants honest pushback, not agreement. If something is
broken, unverified, or not implemented, say so directly. Do not report
a system as ready when open defects are unconfirmed. Do not soften a
failure into a status update.
