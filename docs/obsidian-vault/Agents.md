# Agents.md — The Full Agent Roster

> All 16 project agents in `.claude/agents/`, verified 2026-08-11 from frontmatter.
> The **7 chusri agents** came from commit `f9063b2` ("install 7
> chusri/claude-code-agents subagents, project-scoped"); the other **9** come
> from the "Everything Claude Code" plugin (`code-reviewer`, `architect`,
> `planner`, `build-error-resolver`, `refactor-cleaner`, `e2e-runner`,
> `doc-updater`, `tdd-guide`, `security-reviewer`).
> Built-in agents available to any session (`Plan`, `Explore`, `general-purpose`,
> `claude-code-guide`, `statusline-setup`) are listed at the end.

## Plugin + chusri project agents

| Agent | Origin | Model | Tools | Function |
|-------|--------|-------|-------|----------|
| **architect** | plugin | opus | Read, Grep, Glob | System design, scalability, technical decision-making; use proactively for new features/refactors |
| **backend-architect** | chusri | sonnet | — | RESTful API design, microservice boundaries, DB schemas; reviews for scalability/performance bottlenecks |
| **build-error-resolver** | plugin | opus | Read, Write, Edit, Bash, Grep, Glob | Fixes build/TypeScript errors with minimal diffs; no architectural edits; gets the build green fast |
| **code-reviewer** | plugin | opus | Read, Grep, Glob, Bash | Expert code review (quality/security/maintainability); **MUST be used for all code changes** |
| **code-reviewer-config** | chusri | sonnet | — | Config-variant code reviewer (defaults, no custom tools) |
| **database-admin** | chusri | sonnet | — | DB operations, backups, replication, monitoring, permissions, recovery |
| **devops-troubleshooter** | chusri | sonnet | — | Production debugging, log analysis, deployment failures, incident response |
| **doc-updater** | plugin | opus | Read, Write, Edit, Bash, Grep, Glob | Documentation & codemap upkeep (`/update-codemaps`, `/update-docs`, CODEMAPS, READMEs) |
| **e2e-runner** | plugin | opus | Read, Write, Edit, Bash, Grep, Glob | Playwright end-to-end tests; quarantines flaky tests; uploads artifacts |
| **frontend-developer** | chusri | sonnet | — | React components, responsive layouts, client-side state, a11y |
| **planner** | plugin | opus | Read, Grep, Glob | Planning complex features/refactors; auto-activated for planning tasks |
| **refactor-cleaner** | plugin | opus | Read, Write, Edit, Bash, Grep, Glob | Dead-code cleanup, dedup, refactoring (knip/depcheck/ts-prune) |
| **security-auditor** | chusri | opus | — | Vulnerability review, secure auth, OWASP compliance, JWT/OAuth2/CORS/CSP/encryption |
| **security-reviewer** | plugin | opus | Read, Write, Edit, Bash, Grep, Glob | Vulnerability detection/remediation; flags secrets, SSRF, injection, unsafe crypto, OWASP Top 10 |
| **tdd-guide** | plugin | opus | Read, Write, Edit, Bash, Grep | Write-tests-first enforcement; 80%+ coverage |
| **ui-ux-designer** | chusri | sonnet | — | Interface designs, wireframes, design systems, research, a11y |

## Resolved overlaps

- **code-reviewer vs code-reviewer-config** — the plugin's full reviewer (opus, all review tools, "MUST BE USED") vs the chusri config/default variant (sonnet, no custom tools). **Use `code-reviewer`.**
- **architect vs backend-architect** — the plugin's system architect (opus) vs the chusri backend/API specialist (sonnet). **Use `architect` for system-wide decisions; `backend-architect` for API/service design.**
- **security-reviewer vs security-auditor** — per project convention **`security-reviewer` is RETIRED in favor of `security-auditor`** (the chusri agent). ⚠ Honest flag: **both `.md` files still exist in `.claude/agents/`** — the retirement is a convention, not yet a deletion. Confirm before relying on either.

## Built-in agents (available in every session)

| Agent | Function |
|-------|----------|
| **Plan** | Software-architecture planning; step-by-step implementation plans |
| **Explore** | Read-only search across the codebase (broad fan-out) |
| **general-purpose** | Research + multi-step tasks |
| **claude-code-guide** | Answers about Claude Code / Claude Agent SDK itself |
| **statusline-setup** | Configures the Claude Code status line |

## Project skills (for context)

`.claude/skills/` carries the OLP XDV skills (notably the read-only **`olp-xdv`** query surface for the brain/CLV/board/league-audit), plus design/motion/data skills. The plugin also adds commands, rules, hooks, contexts, and scripts under `.claude/plugins/`. Agents should consult [[Rules.md]] and [[Protected Constants.md]] before acting.
