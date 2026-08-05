# OLP XDV — working protocol for Claude sessions

This repo is worked by **more than one Claude session at a time**. Sessions
cannot message each other. **Git is the only sync mechanism** — the other
session edits the same files and commits independently, and it may do so
while you are mid-task.

## The Safe Move (mandatory before ANY board/Telegram/edit work)

1. `git status --short` — see what is dirty and whether the other session left
   changes.
2. `git log --oneline -5` — see whether the other session committed since your
   last check.
3. If HEAD advanced or the working tree changed since your last check:
   - inspect the diff (`git diff`, `git show <new-head>`),
   - **preserve the other session's work** — combine it with yours rather than
     overwriting it,
   - commit the combined safe state **before** making new edits.
4. Only then edit.

## Combining safe states

- Never discard the other session's committed work or uncommitted changes.
- A reconciliation commit that captures BOTH sessions' changes is the expected
  way to sync (see `b506631` for the pattern).
- If the working tree has changes you did not make, treat them as the other
  session's in-flight work: check, combine, commit, then proceed.
- After combining, re-check `git status` before trusting the tree is stable —
  the other session may still be writing.

## Commit conventions

- Commit with a clear message stating which session contributed what.
- End every commit message with:
  `Co-Authored-By: Claude <noreply@anthropic.com>`

## Architecture context

Board format, the Brain, caching, the WhatsApp copy channel, and daemon wiring
are recorded in the Claude memory note `olp-xdv-agent`. Board decisions are
ratified in `RATIFICATIONS.md` (append-only). The honest-edge statement and the
capital block (Phase 2 = paper only, zero capital) are Architect bright lines —
never bypassed.
