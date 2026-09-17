# OLP XDV — SESSION STARTUP

You are working on OLP XDV, a paper-stage analytical betting framework.
The user is the Architect.

## FIRST ACTION, EVERY SESSION

Read `docs/obsidian-vault/STATE.md` before doing anything else. It holds
current phase, suspension status, live defects, and which documents are
canonical. Do not answer questions about framework state from this file
or from inference — read STATE.md.

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