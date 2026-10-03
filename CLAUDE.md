# OLP XDV — SESSION STARTUP

You are working on OLP XDV, a paper-stage analytical betting framework.
The user is the Architect.

## FIRST ACTION, EVERY SESSION

Read `docs/obsidian-vault/STATE.md` before doing anything else. It holds
current phase, suspension status, live defects, and which documents are
canonical. Do not answer questions about framework state from this file
or from inference — read STATE.md.

## THE NIGHTLY LOOP IS LIVE — DO NOT BREAK IT (2026-09-19)

The 22:00 automation runs unattended and the Architect relies on the board
being in Telegram by 07:00. It was repaired on 2026-09-19 after producing
nothing for weeks while reporting success. **Before touching any of the
following, read this list and understand why each line exists.**

| Thing | Why it is the way it is |
|---|---|
| `run_stage_b(..., today=board_date)` in `run_daily.py` | Without it Stage B evaluates tomorrow's fixtures against today, shortlists ZERO, and reports "no edge". This single argument was the whole outage. |
| `sys.exit(1)` at the end of `run_daily.py`'s `__main__` | The run used to always exit 0, so a two-week outage logged as fourteen successes. There is no `main()` in that file — use `sys.exit`, not `return`. |
| Slot allocation in `breed_next_generation` | The old `[:MAX_LINEAGES]` truncation deleted winning lineages and their capital (78.71 → 52.60 per breed). Never reintroduce a slice that can drop a live lineage. |
| `applied_to_lineage` markers in `history.jsonl` | Grading runs nightly and `record_heartbeat_result` MUTATES bankrolls. Without the marker every night re-pays old results. Superseded records must be marked too, or the next run applies a stale LOSS and kills a live lineage. |
| `node:sqlite` in `scripts/hourly-fixture-check.js` | The `sqlite3` npm package is NOT installed; the task died on it nightly. Do not "fix" this back to `require('sqlite3')`. |
| The SportyBet Cache Refresh scheduled task | Its action must quote the path — "omniroute test" contains a space. Unquoted, it fails hourly with ERROR_BAD_EXE_FORMAT and every cache goes stale, which silently breaks booking. |

**Verify, do not assume.** Check the loop is still healthy with:

    powershell -NoProfile -Command "Get-ScheduledTask | ? {$_.TaskName -match 'OLP XDV'} | % { $i=Get-ScheduledTaskInfo $_.TaskName; '{0} | {1} | last={2}' -f $_.TaskName,$_.State,$i.LastTaskResult }"

`LastTaskResult=0` is success. Anything else is a real failure — these tasks
have a history of failing silently for weeks.

**Do not run `git stash` in this repo.** Multiple Claude sessions share this
working tree; a stash pop applied another session's WIP on 2026-09-19. Use
explicit file copies for temporary reverts.

**Do not `git add -A`.** The repo root holds ~30 untracked zero-byte
shell-redirect artefacts and other sessions may have staged work. Add explicit
paths only.

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

## STUBS — CHECK BEFORE DEBUGGING

As of 2026-09-12, `fixtures_agent.py` is stubbed: it returns hardcoded
Premier League fixtures regardless of date. Suspected stubs elsewhere:
`read_betslip_combined_odds` (returns 100.0), the odds layer (repeated
identical odds across unrelated fixtures).

Before debugging any data problem, run:

    grep -rn "stub\|STUB\|placeholder\|hardcod\|dummy\|mock\|NotImplemented\|TODO" --include=*.py .

Do not debug a stub as though it were a fault. Say plainly when a
module is not implemented.

## FIXTURE VERIFICATION GATE

A fixture is verified by either:
- SportyBet + at least one other source, or
- a single T1 source (ESPN or football-data)

T1: ESPN, football-data. Not T1: SportyBet, TheSportsDB, FlashScore.

Existing source modules: `data/espn_source.py`,
`data/apifootball_client.py`, and the multi-source concentrator.
ESPN was fixed 2026-09-05 (day iteration, `status.type.name`).
Check whether `fixtures_agent.py` actually calls these before building
anything new.

## DOCUMENTS

- `docs/obsidian-vault/STATE.md` — current state. Authoritative.
- `CHANGELOG.md` — session history. Read only if you need past context.
- `OFFICIAL_PIPELINE_OUTPUT_SPEC.md` — output format. Live.
- `TELEGRAM_BLEND_DESIGN.md` — SUPERSEDED. Do not read.

Do not create new spec documents. Amend STATE.md. If a new file is
genuinely needed, add a pointer line to STATE.md in the same session.

## RULE CHANGES

New rules need an ID from the register, assigned by the Architect.
Never self-assign an ID. Unratified drafts are listed in STATE.md §7
and must not be acted on.

## WORKING STYLE

The Architect wants honest pushback, not agreement. If something is
broken, unverified, or not implemented, say so directly. Do not report
a system as ready when open defects are unconfirmed. Do not soften a
failure into a status update.