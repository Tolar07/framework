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

Do not answer questions about framework state from this file or from
inference — read those two files, the code, or the run history.

## THE LIVE LOOP — DO NOT BREAK IT

Everything runs in GitHub Actions on `main`. Times are UTC (Lagos = UTC+1).

| Workflow | When | What |
|---|---|---|
| `daily.yml` | 20:47 (evening, builds TOMORROW) and 05:47 (morning refresh, TODAY); also started on time by a Routine | `run_daily.py --only-production --heartbeat --target-date <day>`; commits `clv/clv_log.json`, `output/boards`, `output/picks`, `data/survivor`, `memory/` |
| `watchdog.yml` | 23:17 and 08:17 | `monitor/run_watchdog.py` — Telegram alert when a slot's board run never succeeded |
| `news.yml` | every 20 min, 09:00-20:40 | `news_check.py` — confirmed lineups, price drift, closing price per pick |
| `commands.yml` | hourly | `output/telegram_commands.py` — answers /status /board /verify /why /log /note /debrief |
| `tests.yml` | every push / PR to main | ruff + mypy gates, `tests/run_all.py` |
| `backtest.yml`, `sync-health.yml` | manual | CLV backtest + metrics history; vault sync check |

What each piece is protecting — read before changing it:

| Thing | Why it is the way it is |
|---|---|
| Duplicate guard in `daily.yml` (`output/boards/sent_<date>_<slot>`, checked against the LATEST main) | The Routine and the GitHub cron both start each slot; the second one for the same day + slot must skip, or the board is sent twice. |
| Late-evening guard in `daily.yml` (`date -u +%H` >= 12) | GitHub sometimes fires the evening cron after midnight UTC; without the guard the run jumps a day ahead (2026-10-01). |
| `--only-production` + `--heartbeat` | Board only on pick days; a short "system alive" heartbeat every day. A dry day is silence on the board, never a fake board. |
| `monitor/run_watchdog.py` + `watchdog.yml` | A dropped GitHub cron is silent; `daily.yml` only alerts on a run that FAILS. |
| `engine/name_match.py` (strict, unique matches; `EXPLICIT` table) | Rates feed spellings ("Blackpool FC") with the model's history ("Blackpool"). Loosening it would put one club's rating on another. |
| SPLIT rejection text in `run_daily.py` (`market_p` may be None → `PENDING`) | Formatting a missing market price crashed the whole run (fixed 2026-10-03). |
| Picks ledger (`engine/picks_ledger.py`) | Records every pick AND every rated fixture; graded from Flashscore, regular time only. The scorecard and `engine/learning.py` read it. |

**Verify, do not assume.** Check the loop with the GitHub Actions run list
for `daily.yml` and `watchdog.yml` (conclusion `success` for each slot), and
`python tests/run_all.py` locally. A run that "should have" happened is not
evidence that it did.

**Do not run `git stash` in this repo.** Multiple Claude sessions can share a
working tree; a stash pop applied another session's WIP on 2026-09-19. Use
explicit file copies for temporary reverts.

**Do not `git add -A`.** Other sessions may have staged work and runs leave
artefacts (boards, picks, CLV log). Add explicit paths only — the commit
guard hook blocks `git add -A`. Work on a branch and merge through a PR whose
`tests.yml` run is green.

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

- **Fixture verification reaches SINGLE-SOURCE only.** Fixtures come from
  TheSportsDB (T2) and are stamped `○ SINGLE-SOURCE` by
  `verification/id403.py`; no T1 fixture source (ESPN, football-data) is
  wired into the live path, so no fixture reaches VERIFIED. The laptop ESPN
  source is parked at `legacy/laptop/data/espn_source.py`.
- **F2 price quorum** (`pipeline/odds_verify.py`, PR #6) is merged and
  tested but not called from the live odds path — an Architect decision.
- Market-implied fixtures (`ᴹ` on the board, `prob_source == "market"`)
  carry the bookmaker's numbers, not the model's; no edge is claimed.

## DOCUMENTS

- `STANDING_ORDERS.md` — the Architect's standing rules. Authoritative.
- `docs/obsidian-vault/STATE.md` — current state (top block) + session
  journal. Authoritative for state.
- `docs/LINEAGE_MERGE_2026-10-03.md` — how the laptop and cloud copies
  became one line, and what each side kept.
- `legacy/laptop/README.md` — what was parked and how to bring a feature back.
- `backtest/*_STUDY.md` — the evidence behind each selection rule.

Do not create new spec documents. Amend STATE.md. If a new file is
genuinely needed, add a pointer line to STATE.md in the same session.

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
