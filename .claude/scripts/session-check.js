#!/usr/bin/env node
/**
 * session-check.js — Detect other sessions' pending changes
 *
 * Usage: node .claude/scripts/session-check.js
 * Output: JSON or human-readable summary of cross-session state
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = 'c:/Users/Motunrayo/omniroute test';

function runCmd(cmd, cwd = REPO_ROOT) {
  try {
    const output = execSync(cmd, { cwd, encoding: 'utf8', stdio: 'pipe', timeout: 10000 });
    return { success: true, output: output.trim() };
  } catch (e) {
    return { success: false, output: e.stdout?.toString() || e.message, error: e.stderr?.toString() };
  }
}

function getGitInfo() {
  const info = {};

  // Current branch
  info.branch = runCmd('git rev-parse --abbrev-ref HEAD').output || 'unknown';

  // Working tree status
  const status = runCmd('git status --porcelain');
  info.workingTree = status.output ? status.output.split('\n').filter(Boolean) : [];

  // Staged changes
  const staged = runCmd('git diff --cached --name-only');
  info.staged = staged.output ? staged.output.split('\n').filter(Boolean) : [];

  // Unpushed commits (local only)
  const unpushed = runCmd('git log --oneline @{u}..HEAD 2>/dev/null');
  info.unpushed = unpushed.output ? unpushed.output.split('\n').filter(Boolean) : [];

  // Unpulled commits (remote has, we don't)
  const unpulled = runCmd('git log --oneline HEAD..@{u} 2>/dev/null');
  info.unpulled = unpulled.output ? unpulled.output.split('\n').filter(Boolean) : [];

  // Last commit
  const lastCommit = runCmd('git log -1 --format="%h %s (%an, %ar)"');
  info.lastCommit = lastCommit.output || 'none';

  // Submodule status
  const subStatus = runCmd('git submodule status');
  info.submodules = subStatus.output ? subStatus.output.split('\n').filter(Boolean) : [];

  // Recent commits (last 10)
  const recent = runCmd('git log --oneline -10');
  info.recentCommits = recent.output ? recent.output.split('\n').filter(Boolean) : [];

  // Stash list
  const stashes = runCmd('git stash list');
  info.stashes = stashes.output ? stashes.output.split('\n').filter(Boolean) : [];

  return info;
}

function analyzeOtherSessions(info) {
  const findings = [];

  // 1. Working tree changes = someone (maybe us) has uncommitted work
  if (info.workingTree.length > 0) {
    findings.push({
      type: 'working-tree',
      severity: 'info',
      message: `${info.workingTree.length} file(s) with uncommitted changes in working tree`,
      details: info.workingTree
    });
  }

  // 2. Staged changes = someone staged but didn't commit
  if (info.staged.length > 0) {
    findings.push({
      type: 'staged',
      severity: 'warning',
      message: `${info.staged.length} file(s) staged but not committed (other session?)`,
      details: info.staged
    });
  }

  // 3. Unpulled commits = other session pushed
  if (info.unpulled.length > 0) {
    findings.push({
      type: 'unpulled',
      severity: 'warning',
      message: `${info.unpulled.length} commit(s) on remote not pulled (other session pushed)`,
      details: info.unpulled
    });
  }

  // 4. Unpushed commits = we have local commits not shared
  if (info.unpushed.length > 0) {
    findings.push({
      type: 'unpushed',
      severity: 'info',
      message: `${info.unpushed.length} local commit(s) not pushed`,
      details: info.unpushed
    });
  }

  // 5. Dirty submodule = other session changed submodule
  const dirtySubs = info.submodules.filter(s => s.startsWith('+') || s.startsWith('-') || s.includes('dirty'));
  if (dirtySubs.length > 0) {
    findings.push({
      type: 'submodule',
      severity: 'warning',
      message: `${dirtySubs.length} submodule(s) have uncommitted changes`,
      details: dirtySubs
    });
  }

  // 6. Stashes = other session may have stashed work
  if (info.stashes.length > 0) {
    findings.push({
      type: 'stashes',
      severity: 'info',
      message: `${info.stashes.length} stash(es) exist`,
      details: info.stashes.slice(0, 3)
    });
  }

  return findings;
}

function printHuman(info, findings) {
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('🔍 SESSION CHECK — Cross-Session State Analysis');
  console.log('═══════════════════════════════════════════════════════════\n');

  console.log(`📍 Branch: ${info.branch}`);
  console.log(`📝 Last commit: ${info.lastCommit}\n`);

  if (findings.length === 0) {
    console.log('✅ No cross-session conflicts detected');
    console.log('   Working tree clean, no unpulled commits, submodules synced\n');
  } else {
    findings.forEach(f => {
      const icon = f.severity === 'warning' ? '⚠️' : 'ℹ️';
      console.log(`${icon}  ${f.message}`);
      if (f.details && f.details.length > 0) {
        f.details.slice(0, 5).forEach(d => console.log(`      ${d}`));
        if (f.details.length > 5) console.log(`      ... and ${f.details.length - 5} more`);
      }
      console.log('');
    });
  }

  console.log('📋 Recent commits (last 10):');
  info.recentCommits.slice(0, 5).forEach(c => console.log(`   ${c}`));
  if (info.recentCommits.length > 5) console.log(`   ... and ${info.recentCommits.length - 5} more`);

  console.log('\n═══════════════════════════════════════════════════════════\n');
}

function printJSON(info, findings) {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    repo: REPO_ROOT,
    branch: info.branch,
    lastCommit: info.lastCommit,
    workingTree: info.workingTree,
    staged: info.staged,
    unpushed: info.unpushed,
    unpulled: info.unpulled,
    submodules: info.submodules,
    stashes: info.stashes,
    findings: findings,
    recentCommits: info.recentCommits
  }, null, 2));
}

function main() {
  const args = process.argv.slice(2);
  const jsonMode = args.includes('--json') || args.includes('-j');

  const info = getGitInfo();
  const findings = analyzeOtherSessions(info);

  if (jsonMode) {
    printJSON(info, findings);
  } else {
    printHuman(info, findings);
  }

  // Exit code: 0 = clean, 1 = warnings, 2 = errors
  const hasWarnings = findings.some(f => f.severity === 'warning');
  process.exit(hasWarnings ? 1 : 0);
}

main().catch(err => {
  console.error('FATAL:', err.message);
  process.exit(2);
});