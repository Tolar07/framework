#!/usr/bin/env node
/**
 * pre-commit-auto-sync.js — Pre-commit hook that runs auto-sync before commit
 *
 * Install: Copy to .git/hooks/pre-commit or add to husky
 * Runs: vault-memory sync → git add -A (sweeps other sessions) → then allows commit
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = 'c:/Users/Motunrayo/omniroute test';
const SYNC_SCRIPT = path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv', '.claude', 'scripts', 'hooks', 'vault-memory-sync.js');
const LOG_DIR = path.join(REPO_ROOT, 'logs', 'pre-commit-sync');
const LOG_FILE = path.join(LOG_DIR, `pre-commit-${new Date().toISOString().split('T')[0]}.log`);

function ensureLogDir() {
  if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });
}

function log(msg) {
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] ${msg}\n`;
  ensureLogDir();
  fs.appendFileSync(LOG_FILE, line, 'utf8');
  console.log(line.trim());
}

function runCmd(cmd, cwd = REPO_ROOT) {
  try {
    const output = execSync(cmd, { cwd, encoding: 'utf8', stdio: 'pipe', timeout: 30000 });
    return { success: true, output: output.trim() };
  } catch (e) {
    return { success: false, output: e.stdout?.toString() || e.message, error: e.stderr?.toString() };
  }
}

function checkOtherSessions() {
  log('\n🔍 Checking for other sessions\' pending work...');

  // Check for uncommitted changes in working tree
  const status = runCmd('git status --porcelain');
  if (status.success && status.output.trim()) {
    log(`   ⚠️  Working tree has uncommitted changes:`);
    status.output.split('\n').filter(Boolean).forEach(l => log(`      ${l}`));
  }

  // Check for staged changes
  const staged = runCmd('git diff --cached --name-only');
  if (staged.success && staged.output.trim()) {
    log(`   📦 Staged changes (will be committed):`);
    staged.output.split('\n').filter(Boolean).forEach(f => log(`      ${f}`));
  }

  // Check for unpushed commits (other session may have pushed)
  const upstream = runCmd('git log --oneline @{u}..HEAD 2>/dev/null || echo "no-upstream"');
  if (upstream.success && upstream.output.trim() && upstream.output.trim() !== 'no-upstream') {
    log(`   ⬆️  Local commits not pushed: ${upstream.output.split('\n').length}`);
  }

  const downstream = runCmd('git log --oneline HEAD..@{u} 2>/dev/null || echo "no-upstream"');
  if (downstream.success && downstream.output.trim() && downstream.output.trim() !== 'no-upstream') {
    log(`   ⬇️  Remote commits not pulled: ${downstream.output.split('\n').length}`);
    log(`      Run: git pull --rebase`);
  }

  return { status: status.output, staged: staged.output };
}

async function main() {
  log('═══════════════════════════════════════════════════════════');
  log('🔄 PRE-COMMIT AUTO-SYNC STARTED');
  log('═══════════════════════════════════════════════════════════');

  // 1. Check other sessions
  checkOtherSessions();

  // 2. Run vault-memory sync (bidirectional reconcile)
  log('\n📦 Step 1: Vault <-> Memory sync (HR54)');
  const syncResult = runCmd(`node "${SYNC_SCRIPT}" reconcile`);
  if (syncResult.success) {
    log(`   ✅ Sync complete`);
  } else {
    log(`   ⚠️  Sync had issues (non-blocking): ${syncResult.output}`);
  }

  // 3. Git add all (sweeps other sessions' staged files)
  log('\n📥 Step 2: Git add -A (sweeps other sessions\' staged files)');
  const addResult = runCmd('git add -A');
  if (addResult.success) {
    log('   ✅ Staged all changes');
  } else {
    log(`   ❌ Add failed: ${addResult.error}`);
    process.exit(1); // Block commit on add failure
  }

  // 4. Verify something to commit
  const diffResult = runCmd('git diff --cached --name-only');
  const stagedFiles = diffResult.success ? diffResult.output.split('\n').filter(Boolean) : [];

  if (stagedFiles.length === 0) {
    log('\n📝 No staged changes after sync — commit will be empty');
    log('   (This is OK — commit will be aborted by git)');
  } else {
    log(`\n✅ Ready to commit ${stagedFiles.length} file(s)`);
  }

  log('\n═══════════════════════════════════════════════════════════');
  log('✅ PRE-COMMIT AUTO-SYNC COMPLETE — Proceeding with commit');
  log('═══════════════════════════════════════════════════════════\n');

  process.exit(0); // Allow commit to proceed
}

main().catch(err => {
  log(`\n❌ FATAL: ${err.message}`);
  process.exit(1); // Block commit on fatal error
});