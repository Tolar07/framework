---
name: obsidian-communication
description: |
  Bidirectional communication agent for Obsidian vault.
  Reads, writes, searches, and syncs with the OLP XDV vault at C:\Users\Motunrayo\Documents\OLP_XDV_Vault.
  Uses MCP Obsidian tools for all operations.
metadata:
  type: project
---

# Obsidian Communication Agent

This agent provides full read/write/search/sync capabilities with the OLP XDV Obsidian vault.

## Vault Configuration

- **Vault path**: `C:\Users\Motunrayo\Documents\OLP_XDV_Vault`
- **Local REST API**: `https://localhost:27124` (secure) / `http://localhost:27123` (insecure)
- **API Key**: `32f3dcf8f4b514ce5b6fce5dfd04dc7f0f9d4d01636834b792e33b7803cd1143`
- **Sync target**: Project docs at `docs/obsidian-vault/` ↔ Vault root

## Available Operations

### Read Operations
| Operation | MCP Tool | Use Case |
|-----------|----------|----------|
| Read file | `mcp__obsidian__read_text_file` | Get full file content |
| Read with head/tail | `mcp__obsidian__read_text_file` + `head`/`tail` | Large files |
| List directory | `mcp__obsidian__list_directory` | Browse vault structure |
| Directory tree | `mcp__obsidian__directory_tree` | Full recursive view |
| Search files | `mcp__obsidian__search_files` | Find by glob pattern |
| Get file info | `mcp__obsidian__get_file_info` | Metadata (size, modified, etc.) |

### Write Operations
| Operation | MCP Tool | Use Case |
|-----------|----------|----------|
| Write file | `mcp__obsidian__write_file` | Create/overwrite file |
| Edit file | `mcp__obsidian__edit_file` | Line-based edits (diff) |
| Create directory | `mcp__obsidian__create_directory` | Ensure path exists |
| Move/rename | `mcp__obsidian__move_file` | Reorganize vault |

### Batch Operations
| Operation | MCP Tool | Use Case |
|-----------|----------|----------|
| Read multiple | `mcp__obsidian__read_multiple_files` | Efficient batch reads |

## Sync Strategy

### Project → Vault (Push)
Syncs from `olp_xdv/docs/obsidian-vault/` to vault root:
- `Agents.md` → `Agents.md`
- `Architecture.md` → `Architecture.md`
- `Decisions Log.md` → `Decisions Log.md`
- `OLP XDV.md` → `OLP XDV.md`
- `Open Questions.md` → `Open Questions.md`
- `Protected Constants.md` → `Protected Constants.md`
- `README.md` → `README.md`
- `Rules.md` → `Rules.md`

### Vault → Project (Pull)
Reads from vault to update project docs (useful for external edits).

## Usage Examples

### Read a vault file
```javascript
// Read OLP XDV.md
const content = await mcp__obsidian__read_text_file({
  path: "C:/Users/Motunrayo/Documents/OLP_XDV_Vault/OLP XDV.md"
});
```

### Write to vault
```javascript
// Write decision log entry
await mcp__obsidian__write_file({
  path: "C:/Users/Motunrayo/Documents/OLP_XDV_Vault/Decisions Log.md",
  content: "# Decisions Log\n\n## 2026-08-12\n- New session-init agent created\n- Obsidian communication agent created"
});
```

### Search for files
```javascript
// Find all .md files containing "gate"
const results = await mcp__obsidian__search_files({
  path: "C:/Users/Motunrayo/Documents/OLP_XDV_Vault",
  pattern: "**/*.md"
});
```

### Sync project docs to vault
```javascript
// Push all project docs to vault
const files = [
  "Agents.md", "Architecture.md", "Decisions Log.md",
  "OLP XDV.md", "Open Questions.md", "Protected Constants.md",
  "README.md", "Rules.md"
];
for (const f of files) {
  const content = fs.readFileSync(`docs/obsidian-vault/${f}`, 'utf8');
  await mcp__obsidian__write_file({
    path: `C:/Users/Motunrayo/Documents/OLP_XDV_Vault/${f}`,
    content
  });
}
```

## Auto-Sync Hooks

Can be configured via `SessionEnd` hook to auto-sync on session end:
```json
{
  "matcher": "*",
  "hooks": [{
    "type": "command",
    "command": "node .claude/scripts/hooks/obsidian-sync.js"
  }]
}
```

## Integration with Session-Init

The `session-init` agent can call this agent to:
1. Pull latest vault state on session start
2. Push local changes on session end
3. Keep decisions log current across sessions

## Claude Desktop Connection

Two connection methods available:

### 1. Local REST API (Direct HTTP)
- **Endpoint**: `https://localhost:27124`
- **Auth**: Bearer token `32f3dcf8f4b514ce5b6fce5dfd04dc7f0f9d4d01636834b792e33b7803cd1143`
- **Cert**: Self-signed (use `-k`/`--insecure` with curl)
- **Use from**: Any HTTP client, scripts, browser

### 2. MCP Server (for Claude Desktop / Claude Code)
- **Config**: Added to both `%APPDATA%/Claude/claude_desktop_config.json` and project `.claude/settings.json`
- **Package**: `@af/mcp-obsidian` via `@smithery/cli`
- **Vault path**: `C:\Users\Motunrayo\Documents\OLP_XDV_Vault`
- **Restart required**: After config changes, restart Claude Desktop

### Sync Architecture

```
┌─────────────────────┐     SessionEnd hook      ┌──────────────────────┐
│  Project docs       │ ──────────────────────►  │  Obsidian Vault      │
│  docs/obsidian-vault│    obsidian-sync.js      │  Documents/OLP_XDV_  │
│                     │     (file copy)          │  Vault/              │
└─────────────────────┘                          └──────────────────────┘
         ▲                                               │
         │                                               ▼
         │                    REST API / MCP            ┌──────────────────────┐
         └──────────────────────────────────────────────►│  Claude Desktop      │
          (read-only queries,                           │  (real-time access)  │
           agent tool calls)                            └──────────────────────┘
```

### Usage from Claude Desktop

Once connected via MCP, in Claude Desktop you can:
- Ask "What's in my OLP XDV vault?"
- Say "Add a decision to Decisions Log.md"
- Query "Search for 'gate' across all vault notes"
- Get real-time vault access without file copying

## Error Handling

All operations should wrap in try/catch:
```javascript
try {
  const content = await mcp__obsidian__read_text_file({ path });
} catch (e) {
  if (e.message.includes('ENOENT')) {
    // File doesn't exist
  } else if (e.message.includes('EACCES')) {
    // Permission denied (API key issue?)
  }
  throw e;
}
```

## Notes

- The vault has the `obsidian-local-rest-api` plugin installed with HTTPS cert
- API key is stored in `.obsidian/plugins/obsidian-local-rest-api/data.json`
- Use MCP tools (not direct HTTP) for all operations — they handle auth/SSL
- The vault is also accessible at `C:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv/docs/obsidian-vault/` (project copy)