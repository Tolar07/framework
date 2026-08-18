#!/usr/bin/env node
/**
 * session-vault-inject.js — HR58 Part2 (enforced cross-session memory continuity)
 *
 * Runs on SessionStart. Prints the canonical governance-vault digest to
 * STDOUT (console.log) so Claude Code injects it as session context.
 *
 * WHY STDOUT, NOT additionalContext:
 *   The structured `additionalContext` JSON field applies only to tool events
 *   (PreToolUse/PostToolUse). SessionStart injects plain-text STDOUT — it is
 *   one of only three events (with UserPromptSubmit / UserPromptExpansion) that
 *   add stdout to the session. The older session-start.js / session-init.js
 *   hooks write everything to stderr (log() -> console.error) and therefore
 *   never reach the injected context. That is the exact "not just a timestamp"
 *   gap this hook closes: real vault content, bounded in size.
 *
 * Reads the CANONICAL vault from the git-tracked repo copy
 * (docs/obsidian-vault/) via the filesystem — NO dependency on the Obsidian
 * Local REST API (port 27124), which is down whenever Obsidian is closed and
 * would otherwise empty the context. The deprecated Documents/OLP_XDV_Vault
 * mirror is intentionally NOT read here (Architect 2026-08-16: repo copy is
 * authoritative).
 *
 * Never blocks session start: any error -> exit(0) with a short note.
 */

const fs = require('fs');
const path = require('path');

const ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';

const VAULT_DIR = path.join(ROOT, 'docs', 'obsidian-vault');

// Priority order: read-first so the most safety-critical content leads.
const PRIORITY_FILES = [
  'Rules.md',
  'Protected Constants.md',
  'Open Questions.md',
  'Decisions Log.md',
  'Architecture.md',
];

// Per-file cap to keep injected context bounded (char count).
const PER_FILE_CAP = 6 * 1024;

function readFileSafe(p) {
  try {
    return fs.readFileSync(p, 'utf8');
  } catch {
    return null;
  }
}

function main() {
  if (!fs.existsSync(VAULT_DIR)) {
    console.log(
      `[vault-inject] CANONICAL VAULT NOT FOUND at ${VAULT_DIR} — ` +
      `skipping context injection (no data fabricated).`);
    process.exit(0);
  }

  const stamp = new Date().toISOString().slice(0, 10);
  const lines = [];
  lines.push('═══════════════════════════════════════════════════════════');
  lines.push(`📚 OLP XDV CANONICAL VAULT INJECTION (${stamp})`);
  lines.push('   Source of truth: git-tracked docs/obsidian-vault/');
  lines.push('   (deprecated Documents/OLP_XDV_Vault mirror is NOT read)');
  lines.push('═══════════════════════════════════════════════════════════');

  let totalChars = 0;
  for (const name of PRIORITY_FILES) {
    const full = readFileSafe(path.join(VAULT_DIR, name));
    if (full === null) {
      lines.push(`\n--- ${name}: NOT FOUND (skipped) ---`);
      continue;
    }
    const truncated = full.length > PER_FILE_CAP;
    const body = truncated ? full.slice(0, PER_FILE_CAP) : full;
    totalChars += body.length;
    lines.push(`\n═══════════════════════════════════════════════════════════`);
    lines.push(`📄 ${name} (${full.length} chars${truncated ? ', truncated to ' + PER_FILE_CAP : ''})`);
    lines.push(`═══════════════════════════════════════════════════════════`);
    lines.push(body);
    if (truncated) {
      lines.push(`[full text: docs/obsidian-vault/${name}]`);
    }
  }

  lines.push('\n═══════════════════════════════════════════════════════════');
  lines.push(`✅ VAULT CONTEXT INJECTED (${totalChars} chars total) — read before acting`);
  lines.push('═══════════════════════════════════════════════════════════');

  console.log(lines.join('\n'));
  process.exit(0);
}

main();
