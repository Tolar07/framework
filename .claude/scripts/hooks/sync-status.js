#!/usr/bin/env node
/**
 * sync-status.js — Sync health dashboard for SessionStart injection
 *
 * Outputs sync health summary to STDOUT for SessionStart context injection.
 * Shows: last sync time, pending conflicts, divergence metrics, audit status.
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const REPO_ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';
const MEMORY_ROOT = path.join(process.env.USERPROFILE || process.env.HOME || '', '.claude', 'projects', 'C--Users-Motunrayo-omniroute-test');
const VAULT_ROOT = path.join(REPO_ROOT, 'docs', 'obsidian-vault');
const AUDIT_DIR = path.join(MEMORY_ROOT, 'audit');
const COMPLIANCE_LOG = path.join(MEMORY_ROOT, 'memory_compliance.log');

function fileHash(filepath) {
  try {
    const content = fs.readFileSync(filepath, 'utf8');
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

function getSyncStatus() {
  const FILE_MAPPINGS = [
    { vault: 'Agents.md', memory: 'olp-xdv-agent.md', direction: 'bidirectional' },
    { vault: 'Architecture.md', memory: null, direction: 'vault-to-memory' },
    { vault: 'Decisions Log.md', memory: null, direction: 'vault-to-memory' },
    { vault: 'Open Questions.md', memory: 'open-questions.md', direction: 'bidirectional' },
    { vault: 'Protected Constants.md', memory: null, direction: 'vault-to-memory' },
    { vault: 'Rules.md', memory: 'rules.md', direction: 'bidirectional' },
    { vault: 'Loops.md', memory: 'loops.md', direction: 'vault-to-memory' },
    { vault: 'README.md', memory: 'readme.md', direction: 'vault-to-memory' },
    { vault: 'Vault-Memory-Index.md', memory: 'MEMORY.md', direction: 'bidirectional' },
    { vault: 'OLP_XDV_Framework_Index.md', memory: 'framework-index.md', direction: 'vault-to-memory' },
    { vault: 'Audit Reports.md', memory: 'conversations/', direction: 'memory-to-vault-append' },
  ];

  let inSync = 0, diverged = 0, missingVault = 0, missingMemory = 0;
  const details = [];

  FILE_MAPPINGS.forEach(mapping => {
    const vaultPath = path.join(VAULT_ROOT, mapping.vault);
    let memoryPath = null;
    if (mapping.memory && !mapping.memory.endsWith('/')) {
      memoryPath = path.join(MEMORY_ROOT, mapping.memory);
    }

    const vaultHash = fileHash(vaultPath);
    const memoryHash = memoryPath ? fileHash(memoryPath) : null;

    if (!vaultHash && !memoryHash) {
      details.push({ file: mapping.vault, status: 'MISSING_BOTH', direction: mapping.direction });
    } else if (!vaultHash && memoryHash) {
      details.push({ file: mapping.vault, status: 'ONLY_MEMORY', direction: mapping.direction });
      missingVault++;
    } else if (!memoryHash && mapping.memory) {
      details.push({ file: mapping.vault, status: 'ONLY_VAULT', direction: mapping.direction });
      missingMemory++;
    } else if (vaultHash && memoryHash && vaultHash === memoryHash) {
      details.push({ file: mapping.vault, status: 'IN_SYNC', direction: mapping.direction });
      inSync++;
    } else if (vaultHash && memoryHash) {
      details.push({ file: mapping.vault, status: 'DIVERGED', direction: mapping.direction });
      diverged++;
    }
  });

  return { inSync, diverged, missingVault, missingMemory, details };
}

function getLastSyncTime() {
  try {
    if (fs.existsSync(COMPLIANCE_LOG)) {
      const content = fs.readFileSync(COMPLIANCE_LOG, 'utf8');
      const lines = content.trim().split('\n').filter(l => l.trim());
      if (lines.length > 0) {
        // Extract timestamp from last line
        const lastLine = lines[lines.length - 1];
        const match = lastLine.match(/\[(.*?)\]/);
        if (match) return match[1];
      }
    }
  } catch (e) {
    // Ignore
  }
  return 'Never';
}

function getAuditStatus() {
  try {
    if (fs.existsSync(AUDIT_DIR)) {
      const files = fs.readdirSync(AUDIT_DIR)
        .filter(f => f.startsWith('audit_') && f.endsWith('.json'))
        .sort()
        .reverse();
      if (files.length > 0) {
        const latest = files[0];
        const content = fs.readFileSync(path.join(AUDIT_DIR, latest), 'utf8');
        const report = JSON.parse(content);
        return {
          latest: latest,
          passed: report.summary?.passed,
          critical: report.summary?.critical || 0,
          total: report.summary?.total_incidents || 0,
          timestamp: report.timestamp
        };
      }
    }
  } catch (e) {
    // Ignore
  }
  return { latest: 'None', passed: true, critical: 0, total: 0, timestamp: null };
}

function getConversationCount() {
  const CONV_DIR = path.join(REPO_ROOT, 'memory', 'conversations');
  try {
    if (fs.existsSync(CONV_DIR)) {
      return fs.readdirSync(CONV_DIR).filter(f => f.endsWith('.jsonl')).length;
    }
  } catch (e) {
    // Ignore
  }
  return 0;
}

function getMirrorStatus() {
  const MIRROR_ROOT = 'C:/Users/Motunrayo/Documents/OLP_XDV_Vault';
  try {
    if (fs.existsSync(path.join(MIRROR_ROOT, 'DEPRECATED_NOTICE.md'))) {
      return 'RETIRED (read-only)';
    } else if (fs.existsSync(MIRROR_ROOT)) {
      return 'ACTIVE (deprecated)';
    }
  } catch (e) {
    // Ignore
  }
  return 'NOT FOUND';
}

function main() {
  const sync = getSyncStatus();
  const lastSync = getLastSyncTime();
  const audit = getAuditStatus();
  const convCount = getConversationCount();
  const mirror = getMirrorStatus();

  // Output formatted status for SessionStart injection
  console.log('╔══════════════════════════════════════════════════════════════╗');
  console.log('║  SYNC STATUS DASHBOARD                                        ║');
  console.log('╠══════════════════════════════════════════════════════════════╣');
  console.log(`║  Vault ↔ Memory Sync:    ${sync.inSync} in sync, ${sync.diverged} diverged, ${sync.missingVault} missing vault, ${sync.missingMemory} missing mem  ║`);
  console.log(`║  Last Reconcile:         ${lastSync}                                    ║`);
  console.log(`║  Mirror Status:          ${mirror.padEnd(52)} ║`);
  console.log(`║  Conversations Archived: ${convCount.toString().padStart(2)}                                                     ║`);
  console.log(`║  Last Audit:             ${audit.latest?.replace('audit_', '').replace('.json', '') || 'Never'.padEnd(42)} ║`);
  console.log(`║  Audit Result:           ${audit.passed ? '✓ PASSED' : '✗ BLOCKED'} (CRITICAL: ${audit.critical}, Total: ${audit.total})                          ║`);
  console.log('╚══════════════════════════════════════════════════════════════╝');

  // Also output machine-readable JSON to stderr for potential parsing
  console.error(JSON.stringify({
    sync,
    lastSync,
    audit,
    convCount,
    mirror,
    timestamp: new Date().toISOString()
  }));
}

main();