# OLP XDV — working protocol for Claude sessions

This repo is worked by **more than one Claude session at a time**. Sessions
cannot message each other. **Git is the only sync mechanism** — the other
session edits the same files and commits independently, and it may do so
while you are mid-task.

## The Safe Move — the DEFAULT opening move for EVERY task

Applies to **everything** done in this repo (board/Telegram output, engine,
tests, config, docs, anything) — not just board work. Treat it as the standing
way of working in a two-session tree, not a special case:

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
5. Re-check `git status` after finishing — the other session may have written
   again; combine and commit rather than leaving a divergent tree.

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

## everything-claude-code integration

This repo uses the **everything-claude-code** plugin (installed at `.claude/` from
`C:\Users\Motunrayo\Downloads\everything-claude-code-main\everything-claude-code-main`).
All agents, skills, commands, rules, hooks, and contexts are available in every session.

Key components now available:
- **Agents**: planner, architect, tdd-guide, code-reviewer, security-reviewer, build-error-resolver, e2e-runner, refactor-cleaner, doc-updater
- **Skills**: coding-standards, backend-patterns, frontend-patterns, continuous-learning, strategic-compact, tdd-workflow, security-review, eval-harness, verification-loop
- **Commands**: /plan, /tdd, /e2e, /code-review, /build-fix, /refactor-clean, /learn, /checkpoint, /verify, /setup-pm
- **Rules**: security, coding-style, testing, git-workflow, agents, performance, patterns, hooks
- **Hooks**: tmux reminders, git push review, doc blocking, PR logging, prettier, TypeScript check, console.log audit, session persistence, continuous learning extraction
- **Contexts**: dev, review, research modes for dynamic system prompt injection

**Use these proactively** — e.g., `tdd-guide` for new features, `code-reviewer` after writing code, `planner` for complex tasks.

## Design reference — awesome-design-md (standing)

Dashboard/UI styling uses **awesome-design-md** — a design-token library at
`C:\Users\Motunrayo\Downloads\awesome-design-md-main\awesome-design-md-main`
(`design-md/<brand>/DESIGN.md` for 73 brands). The current web dashboard
(`webapp/static/css/proto.css`) is a **Binance DESIGN.md token pass** (ratified
2026-08-10): canvas dark `#0b0e11`, surface `#1e2329`, hairline `#2b3139`,
amber primary `#FCD535`, trading up `#0ecb81` / down `#f6465d`.

When changing or extending the web UI, keep the Binance tokens in `proto.css`
(they are the ratified palette). If a new design language is ever chosen, pull
it from the awesome-design-md collection and ratify the swap — tokens are a
skin, never a reason to hide data (honest-edge + data-density stay intact).
