---
name: session-init
description: |
  Initialize OLP XDV session with all relevant skills, tools, and context.
  Runs on SessionStart hook and can be invoked manually.
  Combines: safe-move protocol, skill auto-detection, git status, environment checks.
metadata:
  type: project
---

# Session Initialization Agent for OLP XDV

This agent sets up the complete OLP XDV working environment on session start.
It combines the safe-move protocol, skill discovery, and context loading.

## Execution Flow

### 1. Safe-Move Protocol (ALWAYS FIRST)
Per the memory instructions, ALWAYS start by checking git status and log:

```bash
cd /path/to/olp_xdv
git status
git log --oneline -5
```

**Why:** Another session may have staged changes. Plain `git commit` sweeps ALL staged files into your commit. Use `git commit --only <paths>` to commit only your changes.

### 2. Environment Detection

Detect the active project root:
- Check `OLP_XDV_ROOT` env var
- Fallback: `c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv`
- Verify `.git` exists and CLAUDE.md present

### 3. Skill Auto-Detection

Based on the current task/query, load relevant skills:

| Trigger | Skills to Load |
|---------|----------------|
| "board", "predict", "CLV", "gate", "audit", "leagues" | `olp-xdv` (local) |
| "odds", "edge", "kelly", "arbitrage", "parlay", "devig" | `betting` (sports-skills) |
| "football", "soccer", "Premier League", "xG", "standings" | `football-data` (sports-skills) |
| "data viz", "chart", "dashboard", "plot", "visualize" | `dataviz` (built-in) |
| "security", "audit", "vulnerability" | `security-review` (local) |
| "refactor", "clean", "simplify" | `simplify` (built-in) |
| "config", "permissions", "hooks", "settings" | `update-config` (built-in) |
| "run", "start", "screenshot", "launch" | `run` (built-in) |

### 4. Context Loading

Load key project files:
- `CLAUDE.md` — project instructions
- `ARCHITECTURE.md` — system architecture
- `PROJECT_STATUS.md` — current status
- `RATIFICATIONS.md` — ratified decisions
- `.env` — environment variables

### 5. Permission Checks

Verify critical permissions in `settings.local.json`:
- Python/pip commands
- Git operations
- gh CLI
- pytest/vitest/playwright

### 6. Data Quality Check

Run quick data sanity:
```bash
python -c "
import json
with open('data/leagues/catalog.json') as f:
    cat = json.load(f)
print(f'Leagues: {len(cat[\"leagues\"])}')
print(f'Season: {cat[\"current_season\"]}')
"
```

---

## Invocation

**Automatic (via SessionStart hook):**
The `.claude/scripts/hooks/session-start.js` already runs. This agent enhances it.

**Manual:**
```
/session-init
```
or
```
> session-init
```

---

## Output

On completion, report:
```
✅ Session initialized
📍 Project: OLP XDV @ <path>
🔧 Git: <branch> <status>
🎯 Skills loaded: <list>
📊 Data: <season> <leagues>
⚙️  Permissions: <ok/warn>
```

---

## Integration with Existing Hooks

The `session-start.js` hook already:
- Loads recent sessions
- Reports learned skills
- Detects package manager

This agent **adds**:
- Safe-move protocol (git status/log)
- Skill auto-detection based on task
- OLP XDV specific context loading
- Data quality verification