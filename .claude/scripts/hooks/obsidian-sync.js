#!/usr/bin/env node
/**
 * obsidian-sync.js — Sync project docs with Obsidian vault
 *
 * Pushes: olp_xdv/docs/obsidian-vault/* → C:/Users/Motunrayo/Documents/OLP_XDV_Vault/*
 * Pulls:  C:/Users/Motunrayo/Documents/OLP_XDV_Vault/* → olp_xdv/docs/obsidian-vault/*
 *
 * Run via SessionEnd hook or manually: node .claude/scripts/hooks/obsidian-sync.js [push|pull|status]
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const PROJECT_DOCS = 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv/docs/obsidian-vault';
const VAULT_ROOT = 'C:/Users/Motunrayo/Documents/OLP_XDV_Vault';

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

function checkStatus() {
  log('=== Sync Status ===');
  SYNC_FILES.forEach(f => {
    const projPath = path.join(PROJECT_DOCS, f);
    const vaultPath = path.join(VAULT_ROOT, f);
    const projHash = fileHash(projPath);
    const vaultHash = fileHash(vaultPath);

    if (!projHash && !vaultHash) {
      log(`  ${f}: MISSING BOTH`);
    } else if (!projHash) {
      log(`  ${f}: ONLY IN VAULT (${vaultHash.slice(0,8)})`);
    } else if (!vaultHash) {
      log(`  ${f}: ONLY IN PROJECT (${projHash.slice(0,8)})`);
    } else if (projHash === vaultHash) {
      log(`  ${f}: IN SYNC (${projHash.slice(0,8)})`);
    } else {
      log(`  ${f}: DIVERGED proj=${projHash.slice(0,8)} vault=${vaultHash.slice(0,8)}`);
    }
  });
}

function push() {
  log('=== Push: Project → Vault ===');
  let pushed = 0;
  SYNC_FILES.forEach(f => {
    const src = path.join(PROJECT_DOCS, f);
    const dst = path.join(VAULT_ROOT, f);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, dst);
      log(`  ✓ ${f}`);
      pushed++;
    } else {
      log(`  ✗ ${f} (not in project)`);
    }
  });
  log(`Pushed ${pushed} files`);
}

function pull() {
  log('=== Pull: Vault → Project ===');
  let pulled = 0;
  SYNC_FILES.forEach(f => {
    const src = path.join(VAULT_ROOT, f);
    const dst = path.join(PROJECT_DOCS, f);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, dst);
      log(`  ✓ ${f}`);
      pulled++;
    } else {
      log(`  ✗ ${f} (not in vault)`);
    }
  });
  log(`Pulled ${pulled} files`);
}

function main() {
  const mode = process.argv[2] || 'status';

  if (!fs.existsSync(PROJECT_DOCS)) {
    log(`✗ Project docs not found: ${PROJECT_DOCS}`);
    process.exit(1);
  }
  if (!fs.existsSync(VAULT_ROOT)) {
    log(`✗ Vault not found: ${VAULT_ROOT}`);
    process.exit(1);
  }

  switch (mode) {
    case 'push':
      push();
      break;
    case 'pull':
      pull();
      break;
    case 'status':
    default:
      checkStatus();
      break;
  }
}

main();