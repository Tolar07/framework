# Context Restore Command

**Purpose**: Manually trigger full context restoration (same as SessionStart hooks)

**Usage**: `/context-restore` or `node .claude/scripts/hooks/session-start.js && node .claude/scripts/hooks/session-init.js`

## What it does:

1. **Loads canonical memory** - Reads all `.md` files from `memory/` (11 files including MEMORY.md index)
2. **Shows past sessions** - Lists all 113+ archived transcripts in `memory/conversations/`
3. **Git safe-move check** - Shows git status, staged/unstaged changes, recent commits
4. **Loads core docs** - CLAUDE.md, ARCHITECTURE.md, PROJECT_STATUS.md, RATIFICATIONS.md
5. **Team briefing** - TEAM_BRIEFING.md, DISPATCH_PROTOCOL.md, PROJECT_STATUS.md
6. **Environment** - .env keys loaded
7. **Skills detection** - Auto-detects relevant skills based on pending changes
8. **Data verification** - League catalog status
9. **Protected constants reminder** - Lists all 7 protected constants that require Architect approval
10. **Permissions** - Shows allow-rules count
11. **Team roster** - All available agents and skills
12. **Obsidian vault sync** - Reads 7 canonical vault files, checks sync status

## Auto-run:

This runs **automatically on every SessionStart** via hooks in `.claude/settings.json`:
- `session-start.js` → context summary
- `session-init.js` → deep initialization
- `memory-check.js check-in` → HR54 mandatory vault read

## Manual trigger:

```bash
node .claude/scripts/hooks/session-start.js
node .claude/scripts/hooks/session-init.js
```

## Memory compliance:

- **Check-in** (SessionStart): Reads all 7 vault files → fails if any missing
- **Check-out** (SessionEnd): Verifies memory writes for substantive changes

The memory files in `memory/` are the distilled knowledge from all past sessions.
The transcripts in `memory/conversations/` are the raw conversation history (113+ sessions).