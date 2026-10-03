# OLP XDV — Cross-Team Dispatch Protocol

> **How native agents, plugin agents, and gstack skills coordinate.**
> Loaded by session-init hook. Read by all agents on startup.

---

## 1. Communication Model

**Sessions cannot message each other directly.** All coordination is **git-based** + **file-based** + **vault-synced**.

| Layer | Mechanism | Who Uses It |
|-------|-----------|-------------|
| **Primary** | Git commits (conventional, attributed) | All agents, all sessions |
| **Escalation** | GitHub Issues (opened by `/spec`, closed by `/ship`) | `/spec`, `/ship`, `planner` |
| **Review** | PR reviews (`code-reviewer`, `/review`, `code-reviewer-config`) | All code-producing agents |
| **Decisions** | `RATIFICATIONS.md` (append-only, Architect-only edits) | Architect, `code-reviewer-config` blocks |
| **Context** | `.claude/memory/*.md` + Obsidian Vault | All sessions via hooks |
| **Runtime State** | `feed_audit.jsonl`, `board_<date>.json`, `clv/*` | Pipeline agents, `olp-xdv-specialist` |

---

## 2. Agent Categories & Interfaces

### 2.1 Native Domain Agents (OLP XDV Submodule)
**Location:** `olp_xdv_agent/olp_xdv/.claude/agents/`
**Invocation:** `Agent` tool with `subagent_type: "general-purpose"` (or named specialist agents)
**Contract:** Read `CLAUDE.md` + `TEAM_BRIEFING.md` + `DISPATCH_PROTOCOL.md` before any work.
**Outputs:** Code changes, test files, docs updates — all via git.

| Agent | Handoff Target | Handoff Signal |
|-------|----------------|----------------|
| `planner` | `architect` / `backend-architect` | Implementation plan committed |
| `architect` | Implementation agents | Design doc + `ARCHITECT_SIGNOFF` if rule change |
| `tdd-guide` | `code-reviewer` | Tests passing (80%+) |
| `code-reviewer` | `code-reviewer-config` (if protected) / done | Review complete / blocked |
| `code-reviewer-config` | **Architect** (blocks merge) | Protected-constant flag → explicit question |
| `security-auditor` | `code-reviewer` | Auth/data/API review complete |
| `e2e-runner` | `doc-updater` | Critical flows verified |
| `doc-updater` | — | Docs match code |
| Pipeline 1-10 | Next in sequence | Stage output written to expected path |

### 2.2 Plugin Agents (Parent Repo)
**Location:** `.claude/agents/` (parent repo)
**Invocation:** Available in every session via `Agent` tool
**Contract:** Same as native — read all briefing docs first.

| Agent | Role | Typical Trigger |
|-------|------|-----------------|
| `olp-xdv-specialist` | Full-stack OLP specialist | Telegram/daemon/web, booking, parity, daily pipeline |
| `productivity-assistant` | Files, forms, email | General productivity, form fill, Outlook SMTP |

### 2.3 Plugin Skills (Parent Repo)
**Location:** `.claude/skills/` (parent repo)
**Invocation:** `Skill` tool (e.g., `Skill({skill: "impeccable"})`)
**Contract:** Skills are **stateless workflows** — they execute a defined procedure, not open-ended reasoning.

| Skill | Use When |
|-------|----------|
| `impeccable`, `taste-skill`, `brutalist-skin`... | Dashboard/UI work only (presentation layer) |
| `sports-football-data`, `sports-betting`... | Independent verification inputs (honest-edge) |
| `olp-xdv` | Read-only brain/CLV/board queries |
| `security-review` | Security audit of changes |
| `verification-loop`, `eval-harness` | Self-check loops |

### 2.4 GStack Skills (Global `~/.claude/skills/gstack/`)
**Invocation:** Slash commands (e.g., `/qa`, `/review`, `/ship`, `/spec`)
**Contract:** **Release-engineering layer** — product ops, release, QA, security audit, design.

| Slash Command | When to Use | Output |
|---------------|-------------|--------|
| `/office-hours` | New idea / empty repo | Reframed product brief |
| `/spec` | Vague intent → executable spec | GitHub issue + optional worktree agent |
| `/plan-ceo-review` | Feature idea | CEO-level critique |
| `/plan-eng-review` | Architecture needed | Locked data flow, edge cases, tests |
| `/plan-design-review` | UI/design needed | Dimension ratings 0-10 |
| `/autoplan` | All of above in one | Full plan package |
| `/review` | Pre-landing PR | Bugs CI misses |
| `/codex` | Second opinion | Codex review/challenge/consult |
| `/investigate` | Bug root cause | Systematic investigation (no fixes) |
| `/qa` | Staging URL | Bugs found + fixed + re-verified |
| `/qa-only` | Staging URL | Bug report only |
| `/ship` | Ready to merge | Tests, review, push, PR |
| `/land-and-deploy` | PR approved | Merge, CI, deploy, verify |
| `/cso` | Security audit | OWASP + STRIDE report |
| `/design-review` | Live site | Visual audit + atomic fix loop |
| `/context-save` | Pausing work | Serialized git state + decisions |
| `/context-restore` | Resuming work | Restored context |
| `/health` | Code quality | Type check, linter, tests, dead code |
| `/benchmark` | Perf regression | CWV, page load |

---

## 3. Handoff Patterns

### 3.1 Native → Native (Pipeline)
```
olp-xdv-01-ingestion → olp-xdv-02-listfilter → olp-xdv-03-entity-profiling
    → olp-xdv-04-data-verification → olp-xdv-05-xdv-core → olp-xdv-06-odds-audit
    → olp-xdv-07-compliance → olp-xdv-08-execution → olp-xdv-09-teamlead
    → olp-xdv-10-ceo
```
Each writes its output to the expected path. Next agent reads it. **No git commit between stages** — orchestrator commits at end.

### 3.2 Native → Plugin Specialist
```
planner (native) → olp-xdv-specialist (plugin)
```
**Signal:** Commit with message `plan: <feature> — planner → olp-xdv-specialist`
**Specialist reads:** `git show HEAD` + `TEAM_BRIEFING.md` + relevant module files.

### 3.3 Plugin Specialist → GStack (Release)
```
olp-xdv-specialist → /ship → /qa → /land-and-deploy
```
**Signal:** `/ship` runs tests, `/review`, pushes, opens PR.
**GStack reads:** PR diff, `CLAUDE.md`, runs its own checks.

### 3.4 GStack → Native (Fix Loop)
```
/qa finds bug → /review flags → native agent fixes → /qa re-verifies
```
**Signal:** `/qa` output includes exact file:line + failure scenario.
**Native agent reads:** `/qa` report, fixes, commits `fix: <bug> — /qa → <agent>`.

### 3.5 Protected-Constant Escalation
```
Any agent touches protected constant
    ↓
code-reviewer-config blocks (auto-flag in PR review)
    ↓
Creates GitHub issue: "PROTECTED: <constant> — <agent> proposes <change>"
    ↓
Architect decides (records in RATIFICATIONS.md)
    ↓
doc-updater syncs CLAUDE.md / ARCHITECTURE.md
    ↓
Original agent re-applies with Architect's explicit approval
```

---

## 4. Git Commit Conventions (Cross-Team)

### 4.1 Format
```
<type>(<scope>): <description> — <from-agent> → <to-agent>

<body if needed>
Co-Authored-By: Claude <noreply@anthropic.com>
```

### 4.2 Types
| Type | Meaning |
|------|---------|
| `feat` | New capability |
| `fix` | Bug fix |
| `refactor` | Internal restructure |
| `docs` | Documentation only |
| `test` | Test additions/changes |
| `chore` | Tooling, config, deps |
| `plan` | Planner output |
| `review` | Review findings |
| `reconcile` | Safe-move combine |

### 4.3 Examples
```
feat(pipeline): add ClubElo stretch fallback — planner → olp-xdv-specialist
fix(booking): SportyBet cache anti-contamination gate — olp-xdv-specialist → code-reviewer
reconcile: combine session work — safe-move protocol
review: /qa found 3 bugs on staging — /qa → olp-xdv-08-execution
PROTECTED: ARCHITECT_SIGNOFF logic — code-reviewer-config → Architect
```

---

## 5. Session Initialization Checklist (All Agents)

Every session **must** run this before any work:

```bash
# 1. Safe-move
git status --short
git log --oneline -5

# 2. Read briefing docs
cat CLAUDE.md
cat TEAM_BRIEFING.md
cat DISPATCH_PROTOCOL.md

# 3. Check for other session's uncommitted work
git diff --cached --name-only
git diff --name-only

# 4. If changes exist: combine, commit with --only, then proceed
```

---

## 6. Tool Access by Agent Category

| Tool | Native | Plugin | GStack |
|------|--------|--------|--------|
| `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob` | ✅ Full | ✅ Full | ✅ Full |
| `Agent` (launch subagents) | ✅ | ✅ | ❌ (slash commands instead) |
| `Skill` (invoke skills) | ✅ | ✅ | ❌ (slash commands instead) |
| `Task` (background) | ✅ | ✅ | ✅ |
| `mcp__playwright__*` | ✅ | ✅ | ✅ (`/browse`, `/qa`) |
| `mcp__firecrawl__*` | ✅ | ✅ | ✅ (`/scrape`) |
| `mcp__obsidian__*` | ✅ | ✅ | ✅ |
| `mcp__perplexity__*` | ✅ | ✅ | ✅ |
| Slash commands (`/qa`, `/review`...) | ✅ | ✅ | ✅ Native |

---

## 7. Conflict Resolution Rules

1. **Git wins** — last commit on a file is authoritative. Safe-move combines, never overwrites.
2. **Protected constants win** — `code-reviewer-config` block is absolute. No agent consensus overrides.
3. **Architect decides** — on protected constants, only explicit Architect decision (in `RATIFICATIONS.md`) unblocks.
4. **GStack for release, Native for domain** — don't use `/ship` to design engine logic; don't use `planner` to run QA.
5. **Documentation = code** — `doc-updater` runs after every merge. If docs drift, it's a bug.

---

## 8. Emergency Procedures

### 8.1 Corrupted Live Test (CLV Gate Bypassed)
```
1. STOP all agents
2. code-reviewer-config creates emergency flag
3. Architect reviews diff + RATIFICATIONS.md
4. Rollback commit if needed (git revert)
5. Re-run daily pipeline from clean state
```

### 8.2 Divergent Sessions (Both Committed Different Things)
```
1. git fetch origin
2. git rebase origin/main (or merge)
3. Resolve conflicts — preserve BOTH sessions' intent
4. Commit reconciliation: 'reconcile: merge sessions — <note>'
5. Both sessions re-read TEAM_BRIEFING.md
```

### 8.3 Skill/Agent Version Mismatch
```
/gstack-upgrade  # updates gstack
git pull in olp_xdv submodule  # updates native agents/skills
Re-run session-init hook
```

---

## 9. Quick Reference — Who to Call

| Need | Call |
|------|------|
| "I have a vague idea" | `/office-hours` or `/spec` |
| "Architecture this feature" | `planner` → `architect` |
| "Write tests first" | `tdd-guide` |
| "Review my code" | `code-reviewer` (mandatory) |
| "Security audit" | `security-auditor` or `/cso` |
| "QA the staging site" | `/qa <url>` |
| "Fix a bug systematically" | `/investigate` |
| "Ship this PR" | `/ship` |
| "Deploy to prod" | `/land-and-deploy` |
| "Read brain/CLV/board" | `olp-xdv` skill |
| "Verify odds/edge math" | `sports-betting` skill |
| "Get ESPN/football-data" | `sports-football-data` skill |
| "Polish the dashboard" | `impeccable` / `taste-skill` |
| "Book SportyBet code" | `olp-xdv-specialist` |
| "Run daily pipeline manually" | `py -3.12 run_daily.py` |
| "Build SportyBet cache" | `py -3.12 -m booking.sportybet_fixtures build` |

---

*Cross-team protocol. All agents read this on session init via session-init hook.*