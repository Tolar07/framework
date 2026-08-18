#!/usr/bin/env node
/**
 * obsidian-sync.js — Sync project docs with Obsidian vault
 *
 * Pushes: olp_xdv/docs/obsidian-vault/* → C:/Users/Motunrayo/Documents/OLP_XDV_Vault/*
 * Pulls:  C:/Users/Motunrayo/Documents/OLP_XDV_Vault/* → olp_xdv/docs/obsidian-vault/*
 * Retire: Migrate unique mirror files to canonical, mark mirror read-only
 *
 * Run via SessionEnd hook or manually:
 *   node .claude/scripts/hooks/obsidian-sync.js [push|pull|status|retire-mirror] [--dry-run]
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const PROJECT_DOCS = 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv/docs/obsidian-vault';
const VAULT_ROOT = 'C:/Users/Motunrayo/Documents/OLP_XDV_Vault';

// Core sync files (governance docs)
const SYNC_FILES = [
  'Agents.md',
  'Architecture.md',
  'Decisions Log.md',
  'OLP XDV.md',
  'Open Questions.md',
  'Protected Constants.md',
  'README.md',
  'Rules.md'
];

// Mirror-only files to migrate during retirement
const MIRROR_ONLY_FILES = [
  'API Keys.md',
  'OLP_XDV_Framework_Index.md',
  'Vault-Memory-Index.md'
];

// Files that exist ONLY in canonical vault (not in mirror)
const CANONICAL_ONLY_FILES = [
  'Loops.md'
];

const DEPRECATED_NOTICE = `# DEPRECATED MIRROR — DO NOT EDIT

> **Architect Directive 2026-08-16:** The canonical vault is the git-tracked copy at:
> \`olp_xdv_agent/olp_xdv/docs/obsidian-vault/\`
>
> This folder (\`Documents/OLP_XDV_Vault/\`) is a **deprecated mirror** maintained for backward compatibility only.
> All edits must be made in the canonical vault. Changes here will be overwritten by the sync process.
>
> **Mirror retired:** 2026-08-18 (auto-migrated unique files to canonical vault)
>
> ---
>
> ### Migrated Files (now in canonical vault)
> - \`Vault-Memory-Index.md\` → canonical vault (updated)
> - \`OLP_XDV_Framework_Index.md\` → canonical vault (updated)
> - \`API Keys.md\` → canonical vault (sanitized, credentials only in .env)
> - \`Loops.md\` → already in canonical vault
>
> ### Files Remaining Here (read-only reference)
> - \`Pipeline Runs/\` — historical pipeline artifacts
> - \`.obsidian/\` — Obsidian workspace config
> - \`.trash/\` — Obsidian trash
`;

function log(msg) {
  console.error(`[obsidian-sync] ${msg}`);
}

function runMcp(tool, args) {
  // MCP tools are invoked via the harness, not directly.
  // For hook use, we call the obsidian CLI via npx if available,
  // or use the MCP bridge. Here we use a simple file-based approach
  // since the hook runs in the same environment as the agent.
  return { success: false, reason: 'Use MCP tools from agent context' };
}

function fileHash(filepath) {
  try {
    const content = fs.readFileSync(filepath, 'utf8');
    // Simple hash for comparison
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      hash = ((hash << 5) - hash) + content.charCodeAt(i);
      hash |= 0;
    }
    return hash.toString(16);
  } catch {
    return null;
  }
}

function readFileSafe(filepath) {
  try {
    return fs.readFileSync(filepath, 'utf8');
  } catch {
    return null;
  }
}

function writeFileSafe(filepath, content) {
  try {
    const dir = path.dirname(filepath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(filepath, content, 'utf8');
    return true;
  } catch (e) {
    log(`Failed to write ${filepath}: ${e.message}`);
    return false;
  }
}

function copyFile(src, dst, dryRun = false) {
  if (dryRun) {
    log(`  [DRY-RUN] Would copy: ${path.basename(src)}`);
    return true;
  }
  try {
    fs.copyFileSync(src, dst);
    log(`  ✓ ${path.basename(src)}`);
    return true;
  } catch (e) {
    log(`  ✗ ${path.basename(src)}: ${e.message}`);
    return false;
  }
}

function checkStatus() {
  log('=== Sync Status ===');
  log('\n--- Governance Files (bidirectional) ---');
  SYNC_FILES.forEach(f => {
    const projPath = path.join(PROJECT_DOCS, f);
    const vaultPath = path.join(VAULT_ROOT, f);
    const projHash = fileHash(projPath);
    const vaultHash = fileHash(vaultPath);

    if (!projHash && !vaultHash) {
      log(`  ${f}: MISSING BOTH`);
    } else if (!projHash) {
      log(`  ${f}: ONLY IN MIRROR (${vaultHash.slice(0,8)})`);
    } else if (!vaultHash) {
      log(`  ${f}: ONLY IN CANONICAL (${projHash.slice(0,8)})`);
    } else if (projHash === vaultHash) {
      log(`  ${f}: IN SYNC (${projHash.slice(0,8)})`);
    } else {
      log(`  ${f}: DIVERGED canonical=${projHash.slice(0,8)} mirror=${vaultHash.slice(0,8)}`);
    }
  });

  log('\n--- Mirror-Only Files (to migrate on retire) ---');
  MIRROR_ONLY_FILES.forEach(f => {
    const vaultPath = path.join(VAULT_ROOT, f);
    const vaultHash = fileHash(vaultPath);
    if (vaultHash) {
      log(`  ${f}: EXISTS in mirror (${vaultHash.slice(0,8)}) — will migrate`);
    } else {
      log(`  ${f}: NOT FOUND in mirror`);
    }
  });

  log('\n--- Canonical-Only Files ---');
  CANONICAL_ONLY_FILES.forEach(f => {
    const projPath = path.join(PROJECT_DOCS, f);
    const projHash = fileHash(projPath);
    if (projHash) {
      log(`  ${f}: EXISTS in canonical (${projHash.slice(0,8)})`);
    } else {
      log(`  ${f}: NOT FOUND in canonical`);
    }
  });
}

function push(dryRun = false) {
  log(`=== Push: Canonical → Mirror ${dryRun ? '(DRY-RUN)' : ''} ===`);
  let pushed = 0;
  SYNC_FILES.forEach(f => {
    const src = path.join(PROJECT_DOCS, f);
    const dst = path.join(VAULT_ROOT, f);
    if (fs.existsSync(src)) {
      if (copyFile(src, dst, dryRun)) pushed++;
    } else {
      log(`  ✗ ${f} (not in canonical)`);
    }
  });
  log(`Pushed ${pushed} files`);
}

function pull(dryRun = false) {
  log(`=== Pull: Mirror → Canonical ${dryRun ? '(DRY-RUN)' : ''} ===`);
  let pulled = 0;
  SYNC_FILES.forEach(f => {
    const src = path.join(VAULT_ROOT, f);
    const dst = path.join(PROJECT_DOCS, f);
    if (fs.existsSync(src)) {
      if (copyFile(src, dst, dryRun)) pulled++;
    } else {
      log(`  ✗ ${f} (not in mirror)`);
    }
  });
  log(`Pulled ${pulled} files`);
}

function retireMirror(dryRun = false) {
  log(`=== Retire Mirror: Migrate unique files to Canonical ${dryRun ? '(DRY-RUN)' : ''} ===`);

  if (!fs.existsSync(PROJECT_DOCS)) {
    log(`✗ Canonical vault not found: ${PROJECT_DOCS}`);
    process.exit(1);
  }
  if (!fs.existsSync(VAULT_ROOT)) {
    log(`✗ Mirror vault not found: ${VAULT_ROOT}`);
    process.exit(1);
  }

  let migrated = 0;
  let failed = 0;

  // 1. Migrate mirror-only files to canonical
  log('\n--- Migrating mirror-only files ---');
  MIRROR_ONLY_FILES.forEach(f => {
    const src = path.join(VAULT_ROOT, f);
    const dst = path.join(PROJECT_DOCS, f);
    if (fs.existsSync(src)) {
      const content = readFileSafe(src);
      if (content) {
        // For API Keys.md, sanitize credentials (keep structure, remove values)
        let finalContent = content;
        if (f === 'API Keys.md') {
          finalContent = sanitizeApiKeys(content);
          log(`  ✓ ${f} (sanitized)`);
        } else {
          log(`  ✓ ${f}`);
        }
        if (writeFileSafe(dst, finalContent)) {
          migrated++;
        } else {
          failed++;
        }
      }
    } else {
      log(`  ⚠ ${f}: Not found in mirror, skipping`);
    }
  });

  // 2. Create DEPRECATED_NOTICE.md in mirror root
  log('\n--- Marking mirror as deprecated ---');
  const noticePath = path.join(VAULT_ROOT, 'DEPRECATED_NOTICE.md');
  if (writeFileSafe(noticePath, DEPRECATED_NOTICE)) {
    log(`  ✓ DEPRECATED_NOTICE.md created in mirror root`);
  } else {
    failed++;
  }

  // 3. Make mirror files read-only (Windows: attrib +R)
  if (!dryRun) {
    try {
      spawnSync('attrib', ['+R', '/S', '/D', path.join(VAULT_ROOT, '*.md')], { shell: true });
      log(`  ✓ Mirror .md files marked read-only`);
    } catch (e) {
      log(`  ⚠ Could not set read-only: ${e.message}`);
    }
  } else {
    log(`  [DRY-RUN] Would mark mirror .md files read-only`);
  }

  log(`\n=== Mirror Retirement ${dryRun ? '(DRY-RUN)' : ''} Complete ===`);
  log(`Migrated: ${migrated} files`);
  if (failed > 0) log(`Failed: ${failed} files`);
  log(`\nNext steps:`);
  log(`  1. Verify canonical vault has all migrated files`);
  log(`  2. Remove mirror from additionalDirectories in settings.json`);
  log(`  3. Update Vault-Memory-Index.md in canonical to reflect new state`);
  log(`  4. Future: remove mirror folder entirely`);
}

function sanitizeApiKeys(content) {
  // Replace actual credential values with placeholders
  return content
    .replace(/`[a-f0-9]{32}`/g, '`<REDACTED>`')  // 32-char hex keys
    .replace(/`[A-Za-z0-9_-]{20,}`/g, '`<REDACTED>`')  // Long tokens
    .replace(/`\d{10}:[A-Za-z0-9_-]{35}`/g, '`<REDACTED>`')  // Telegram bot tokens
    .replace(/`pplx-[A-Za-z0-9_-]{40,}`/g, '`<REDACTED>`')  // Perplexity keys
    .replace(/`fc-[a-f0-9]{32}`/g, '`<REDACTED>`')  // Firecrawl keys
    .replace(/\| `.*?` \|/g, '| `<REDACTED>` |');  // Table cells with backticks
}

function main() {
  const args = process.argv.slice(2);
  const mode = args[0] || 'status';
  const dryRun = args.includes('--dry-run') || args.includes('-n');

  if (!fs.existsSync(PROJECT_DOCS)) {
    log(`✗ Canonical vault not found: ${PROJECT_DOCS}`);
    process.exit(1);
  }
  if (!fs.existsSync(VAULT_ROOT)) {
    log(`✗ Mirror vault not found: ${VAULT_ROOT}`);
    process.exit(1);
  }

  switch (mode) {
    case 'push':
      push(dryRun);
      break;
    case 'pull':
      pull(dryRun);
      break;
    case 'retire-mirror':
      retireMirror(dryRun);
      break;
    case 'status':
    default:
      checkStatus();
      break;
  }
}

main();