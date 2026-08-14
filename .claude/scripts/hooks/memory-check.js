#!/usr/bin/env node
/**
 * memory-check.js — HR54 Mandatory Memory Check-In/Check-Out
 *
 * Runs on SessionStart (check-in) and SessionEnd (check-out).
 * Enforces: every session must read canonical memory before output,
 * and write substantive changes back before ending.
 *
 * Canonical store: Documents/OLP_XDV_Vault (Obsidian vault)
 * Cross-platform (Windows, macOS, Linux)
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';

const VAULT_ROOT = 'C:/Users/Motunrayo/Documents/OLP_XDV_Vault';
const VAULT_API_KEY = '32f3dcf8f4b514ce5b6fce5dfd04dc7f0f9d4d01636834b792e33b7803cd1143';

// The canonical memory files that MUST be read every session
const CANONICAL_MEMORY_FILES = [
  'OLP XDV.md',
  'Rules.md',
  'Decisions Log.md',
  'Open Questions.md',
  'Protected Constants.md',
  'Architecture.md',
  'Agents.md'
];

// File to track session memory compliance
const MEMORY_COMPLIANCE_LOG = path.join(ROOT, 'memory', 'memory_compliance.log');

function log(msg) {
  console.error(`[memory-check] ${msg}`);
}

function readVaultFile(filename) {
  return new Promise((resolve, reject) => {
    const encoded = encodeURIComponent(filename);
    const options = {
      hostname: 'localhost',
      port: 27124,
      path: `/vault/${encoded}`,
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${VAULT_API_KEY}`,
        'Accept': 'text/markdown'
      },
      rejectUnauthorized: false
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          resolve(data);
        } else if (res.statusCode === 404) {
          resolve(null);
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(10000, () => req.destroy(new Error('Timeout')));
    req.end();
  });
}

function writeComplianceEntry(action, details) {
  const timestamp = new Date().toISOString();
  const entry = `${timestamp} | ${action} | ${details}\n`;
  try {
    if (!fs.existsSync(path.dirname(MEMORY_COMPLIANCE_LOG))) {
      fs.mkdirSync(path.dirname(MEMORY_COMPLIANCE_LOG), { recursive: true });
    }
    fs.appendFileSync(MEMORY_COMPLIANCE_LOG, entry);
  } catch (e) {
    log(`Failed to write compliance log: ${e.message}`);
  }
}

async function checkIn() {
  log('=== HR54 CHECK-IN: Reading canonical memory ===');

  let allRead = true;
  let totalLines = 0;

  for (const file of CANONICAL_MEMORY_FILES) {
    try {
      const content = await readVaultFile(file);
      if (content) {
        const lines = content.split('\n').length;
        totalLines += lines;
        log(`  �� ${file} (${lines} lines)`);
      } else {
        log(`  �� ${file}: NOT FOUND in vault`);
        allRead = false;
      }
    } catch (e) {
      log(`  �� ${file}: ${e.message}`);
      allRead = false;
    }
  }

  if (allRead) {
    log(`��� CHECK-IN COMPLETE: ${CANONICAL_MEMORY_FILES.length} files read (${totalLines} total lines)`);
    writeComplianceEntry('CHECK-IN', `OK: ${CANONICAL_MEMORY_FILES.length} files, ${totalLines} lines`);
  } else {
    log('��� CHECK-IN FAILED: Could not read all canonical memory files');
    writeComplianceEntry('CHECK-IN', 'FAILED: incomplete vault read');
    process.exit(1); // Hard failure per HR54
  }

  return true;
}

async function checkOut() {
  log('=== HR54 CHECK-OUT: Verifying memory writes ===');

  // Check if any canonical files were modified this session
  // by comparing file sizes/timestamps or checking git status
  const gitStatus = require('child_process').spawnSync('git', ['status', '--short'], {
    cwd: ROOT, encoding: 'utf8'
  });

  const changes = gitStatus.stdout.trim().split('\n').filter(Boolean);
  const vaultChanges = changes.filter(c =>
    c.includes('Documents/OLP_XDV_Vault') ||
    c.includes('memory/') ||
    c.includes('RATIFICATIONS.md') ||
    c.includes('Decisions Log.md') ||
    c.includes('Open Questions.md')
  );

  if (vaultChanges.length > 0) {
    log(`  �� Memory writes detected: ${vaultChanges.join(', ')}`);
    writeComplianceEntry('CHECK-OUT', `OK: ${vaultChanges.length} memory files modified`);
  } else {
    // Check if there are any code changes that imply a memory update should have happened
    const codeChanges = changes.filter(c =>
      c.endsWith('.py') || c.endsWith('.js') || c.endsWith('.json')
    );

    if (codeChanges.length > 0) {
      log(`  ��� Code changes detected (${codeChanges.length} files) but NO memory files updated`);
      log(`  ��� HR54: Substantive changes require memory write. Update Decisions Log.md or Open Questions.md.`);
      writeComplianceEntry('CHECK-OUT', `WARNING: ${codeChanges.length} code files changed, 0 memory files`);
    } else {
      log(`  �� No substantive changes this session`);
      writeComplianceEntry('CHECK-OUT', 'OK: no substantive changes');
    }
  }

  log('=== HR54 CHECK-OUT COMPLETE ===');
  process.exit(0);
}

async function main() {
  const action = process.argv[2] || 'check-in';

  if (action === 'check-in') {
    await checkIn();
  } else if (action === 'check-out') {
    await checkOut();
  } else {
    log(`Usage: node memory-check.js [check-in|check-out]`);
    process.exit(1);
  }
}

main().catch(err => {
  console.error('[memory-check] Fatal:', err.message);
  process.exit(1);
});