#!/usr/bin/env node
/**
 * vault-memory-sync.js — Bidirectional sync between canonical vault and agent memory
 */
const fs = require('fs');
const path = require('path');

const VAULT_ROOT = 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv/docs/obsidian-vault';
const MEMORY_ROOT = 'c:/Users/Motunrayo/.claude/projects/C--Users-Motunrayo-omniroute-test/memory';
const BACKUP_DIR = path.join(MEMORY_ROOT, 'sync-backups');
const COMPLIANCE_LOG = path.join(MEMORY_ROOT, 'memory_compliance.log');
const CONFIG_PATH = path.join(__dirname, '..', '..', '..', '.claude', 'config', 'vault-memory-mappings.json');

function loadMappings() {
  try {
    const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    return config.FILE_MAPPINGS;
  } catch (e) {
    console.error(`[vault-memory-sync] Failed to load mappings from ${CONFIG_PATH}: ${e.message}`);
    process.exit(1);
  }
}

const FILE_MAPPINGS = loadMappings();

function log(msg) { console.error(`[vault-memory-sync] ${msg}`); }
function fileHash(filepath) {
  try {
    const content = fs.readFileSync(filepath, 'utf8');
    let hash = 0;
    for (let i = 0; i < content.length; i++) { hash = ((hash << 5) - hash) + content.charCodeAt(i); hash |= 0; }
    return hash.toString(16);
  } catch { return null; }
}
function readFileSafe(filepath) { try { return fs.readFileSync(filepath, 'utf8'); } catch { return null; } }
function writeFileSafe(filepath, content) {
  try { const dir = path.dirname(filepath); if (!fs.existsSync(dir)) { fs.mkdirSync(dir, { recursive: true }); } fs.writeFileSync(filepath, content, 'utf8'); return true; }
  catch (e) { log(`Failed to write ${filepath}: ${e.message}`); return false; }
}
function ensureBackupDir() { if (!fs.existsSync(BACKUP_DIR)) { fs.mkdirSync(BACKUP_DIR, { recursive: true }); } }
function backupFile(sourcePath, label) { ensureBackupDir(); const timestamp = new Date().toISOString().replace(/[:.]/g, '-'); const basename = path.basename(sourcePath); const backupName = `${timestamp}_${label}_${basename}`; const backupPath = path.join(BACKUP_DIR, backupName); try { fs.copyFileSync(sourcePath, backupPath); return backupPath; } catch (e) { log(`Backup failed for ${sourcePath}: ${e.message}`); return null; } }
function appendCompliance(entry) { const timestamp = new Date().toISOString(); const line = `[${timestamp}] ${entry}\n`; try { fs.appendFileSync(COMPLIANCE_LOG, line, 'utf8'); } catch (e) { log(`Failed to write compliance log: ${e.message}`); } }

function checkStatus() {
  log('=== Vault <-> Memory Sync Status ===\n');
  let diverged = 0, missingVault = 0, missingMemory = 0, inSync = 0;
  FILE_MAPPINGS.forEach(mapping => {
    const vaultPath = path.join(VAULT_ROOT, mapping.vault);
    let memoryPath = null;
    if (mapping.memory && !mapping.memory.endsWith('/')) { memoryPath = path.join(MEMORY_ROOT, mapping.memory); }
    else if (mapping.memory && mapping.memory.endsWith('/')) { memoryPath = path.join(MEMORY_ROOT, mapping.memory); }
    const vaultHash = fileHash(vaultPath);
    const memoryHash = memoryPath ? fileHash(memoryPath) : null;
    if (!vaultHash && !memoryHash) { log(`  ${mapping.vault} <-> ${mapping.memory || '(none)'}: MISSING BOTH`); }
    else if (!vaultHash && memoryHash) { log(`  ${mapping.vault}: ONLY IN MEMORY (${memoryHash.slice(0,8)}) [${mapping.direction}]`); missingVault++; }
    else if (!memoryHash && mapping.memory) { log(`  ${mapping.vault}: ONLY IN VAULT (${vaultHash.slice(0,8)}) [${mapping.direction}]`); missingMemory++; }
    else if (vaultHash && memoryHash && vaultHash === memoryHash) { log(`  ${mapping.vault}: IN SYNC (${vaultHash.slice(0,8)}) [${mapping.direction}]`); inSync++; }
    else if (vaultHash && memoryHash) { log(`  ${mapping.vault}: DIVERGED vault=${vaultHash.slice(0,8)} memory=${memoryHash.slice(0,8)} [${mapping.direction}]`); diverged++; }
    else if (vaultHash && !memoryHash && mapping.direction === 'vault-to-memory') { log(`  ${mapping.vault}: ONLY IN VAULT (${vaultHash.slice(0,8)}) [${mapping.direction}] (memory file not yet created)`); missingMemory++; }
    else { log(`  ${mapping.vault}: HASH ERROR vault=${vaultHash} memory=${memoryHash} [${mapping.direction}]`); diverged++; }
  });
  log(`\nSummary: ${inSync} in sync, ${diverged} diverged, ${missingVault} missing in vault, ${missingMemory} missing in memory`);
  return { diverged, missingVault, missingMemory, inSync };
}

function push(dryRun = false) {
  log(`=== Push: Memory -> Vault ${dryRun ? '(DRY-RUN)' : ''} ===`);
  let pushed = 0, failed = 0;
  FILE_MAPPINGS.forEach(mapping => {
    if (!['bidirectional', 'memory-to-vault', 'memory-to-vault-append'].includes(mapping.direction)) return;
    const vaultPath = path.join(VAULT_ROOT, mapping.vault);
    let memoryPath = null;
    if (mapping.memory && !mapping.memory.endsWith('/')) { memoryPath = path.join(MEMORY_ROOT, mapping.memory); }
    else if (mapping.memory && mapping.memory.endsWith('/')) { const convDir = path.join(MEMORY_ROOT, mapping.memory); if (fs.existsSync(convDir)) { const files = fs.readdirSync(convDir).filter(f => f.endsWith('.md')).sort().reverse(); if (files.length > 0) { memoryPath = path.join(convDir, files[0]); } } }
    if (!memoryPath || !fs.existsSync(memoryPath)) { log(`  ! ${mapping.vault}: No memory source`); return; }
    const content = readFileSafe(memoryPath);
    if (!content) { log(`  x ${mapping.vault}: Failed to read memory`); failed++; return; }
    if (mapping.direction === 'memory-to-vault-append') { const existing = readFileSafe(vaultPath) || ''; const header = `\n\n---\n\n## Conversation Summary ${new Date().toISOString()}\n\n`; const finalContent = existing + header + content; if (!dryRun) { backupFile(vaultPath, 'pre-push'); if (writeFileSafe(vaultPath, finalContent)) { log(`  + ${mapping.vault} (appended)`); pushed++; } else failed++; } else { log(`  [DRY-RUN] Would append to ${mapping.vault}`); pushed++; } }
    else { if (!dryRun) { backupFile(vaultPath, 'pre-push'); if (writeFileSafe(vaultPath, content)) { log(`  + ${mapping.vault}`); pushed++; } else failed++; } else { log(`  [DRY-RUN] Would copy to ${mapping.vault}`); pushed++; } }
  });
  log(`Pushed ${pushed} files, ${failed} failed`);
}

function pull(dryRun = false) {
  log(`=== Pull: Vault -> Memory ${dryRun ? '(DRY-RUN)' : ''} ===`);
  let pulled = 0, failed = 0;
  FILE_MAPPINGS.forEach(mapping => {
    if (!['bidirectional', 'vault-to-memory'].includes(mapping.direction)) return;
    if (!mapping.memory) return;
    const vaultPath = path.join(VAULT_ROOT, mapping.vault);
    const memoryPath = path.join(MEMORY_ROOT, mapping.memory);
    if (!fs.existsSync(vaultPath)) { log(`  ! ${mapping.vault}: Not in vault`); return; }
    const content = readFileSafe(vaultPath);
    if (!content) { log(`  x ${mapping.vault}: Failed to read vault`); failed++; return; }
    if (!dryRun) { backupFile(memoryPath, 'pre-pull'); if (writeFileSafe(memoryPath, content)) { log(`  + ${mapping.memory}`); pulled++; } else failed++; } else { log(`  [DRY-RUN] Would copy to ${mapping.memory}`); pulled++; }
  });
  log(`Pulled ${pulled} files, ${failed} failed`);
}

function reconcile(dryRun = false) {
  log(`=== Reconcile: Auto-resolve ${dryRun ? '(DRY-RUN)' : ''} ===`);
  const status = checkStatus();
  if (status.diverged === 0) { log('No conflicts.'); return; }
  let resolved = 0, failed = 0;
  FILE_MAPPINGS.forEach(mapping => {
    if (mapping.direction !== 'bidirectional') return;
    const vaultPath = path.join(VAULT_ROOT, mapping.vault);
    const memoryPath = mapping.memory ? path.join(MEMORY_ROOT, mapping.memory) : null;
    if (!memoryPath) return;
    const vaultHash = fileHash(vaultPath);
    const memoryHash = fileHash(memoryPath);
    if (!vaultHash || !memoryHash || vaultHash === memoryHash) return;
    const vaultStat = fs.statSync(vaultPath);
    const memoryStat = fs.statSync(memoryPath);
    const vaultTime = vaultStat.mtimeMs, memoryTime = memoryStat.mtimeMs;
    const winner = vaultTime > memoryTime ? 'vault' : 'memory';
    const winnerPath = winner === 'vault' ? vaultPath : memoryPath;
    const loserPath = winner === 'vault' ? memoryPath : vaultPath;
    log(`  ${mapping.vault}: ${winner} wins (vault=${vaultTime.toFixed(0)}, memory=${memoryTime.toFixed(0)})`);
    if (!dryRun) { backupFile(vaultPath, 'pre-reconcile'); backupFile(memoryPath, 'pre-reconcile'); const winnerContent = readFileSafe(winnerPath); if (winnerContent && writeFileSafe(loserPath, winnerContent)) { log(`    + Synced`); resolved++; } else { log(`    x Failed`); failed++; } } else { log(`    [DRY-RUN] Would sync`); resolved++; }
  });
  log(`Resolved ${resolved}, failed ${failed}`); appendCompliance(`RECONCILE: ${resolved} resolved, ${failed} failed`);
}

function backup(dryRun = false) {
  log(`=== Backup ${dryRun ? '(DRY-RUN)' : ''} ===`);
  let backedUp = 0;
  FILE_MAPPINGS.forEach(mapping => {
    const vaultPath = path.join(VAULT_ROOT, mapping.vault);
    if (fs.existsSync(vaultPath)) { if (!dryRun) { if (backupFile(vaultPath, 'vault')) backedUp++; } else { log(`  [DRY-RUN] backup vault/${mapping.vault}`); backedUp++; } }
    if (mapping.memory && !mapping.memory.endsWith('/')) { const memoryPath = path.join(MEMORY_ROOT, mapping.memory); if (fs.existsSync(memoryPath)) { if (!dryRun) { if (backupFile(memoryPath, 'memory')) backedUp++; } else { log(`  [DRY-RUN] backup memory/${mapping.memory}`); backedUp++; } } }
  });
  log(`Backed up ${backedUp} files`);
}

function main() {
  const args = process.argv.slice(2);
  const mode = args[0] || 'status';
  const dryRun = args.includes('--dry-run') || args.includes('-n');
  if (!fs.existsSync(VAULT_ROOT)) { log(`x Vault not found: ${VAULT_ROOT}`); process.exit(1); }
  if (!fs.existsSync(MEMORY_ROOT)) { log(`x Memory not found: ${MEMORY_ROOT}`); process.exit(1); }
  switch (mode) {
    case 'push': push(dryRun); break;
    case 'pull': pull(dryRun); break;
    case 'reconcile': reconcile(dryRun); break;
    case 'backup': backup(dryRun); break;
    case 'status': default: checkStatus(); break;
  }
}
main();