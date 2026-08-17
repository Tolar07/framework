#!/usr/bin/env node
/**
 * SessionStart Hook - Load previous context on new session
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Runs when a new Claude session starts. Checks for recent session
 * files and notifies Claude of available context to load.
 */

const path = require('path');
const fs = require('fs');
const {
  getSessionsDir,
  getLearnedSkillsDir,
  findFiles,
  ensureDir,
  log,
  readFile
} = require('../lib/utils');
const { getPackageManager, getSelectionPrompt } = require('../lib/package-manager');

const REPO_ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';

const MEMORY_DIR = path.join(REPO_ROOT, 'memory');
const CONVERSATIONS_DIR = path.join(MEMORY_DIR, 'conversations');

async function main() {
  const sessionsDir = getSessionsDir();
  const learnedDir = getLearnedSkillsDir();

  // Ensure directories exist
  ensureDir(sessionsDir);
  ensureDir(learnedDir);
  ensureDir(MEMORY_DIR);
  ensureDir(CONVERSATIONS_DIR);

  log('═══════════════════════════════════════════════════════════');
  log('🔄  OLP XDV — SESSION START — CONTEXT RESTORATION');
  log('═══════════════════════════════════════════════════════════');

  // ── 1. Canonical Memory Files (MEMORY.md index) ────────────────
  const memoryIndexPath = path.join(MEMORY_DIR, 'MEMORY.md');
  if (fs.existsSync(memoryIndexPath)) {
    const memoryIndex = readFile(memoryIndexPath);
    if (memoryIndex) {
      log('\n📚  CANONICAL MEMORY INDEX (MEMORY.md):');
      log('   ' + memoryIndex.split('\n').map(l => l.trim()).filter(Boolean).join('\n   '));
    }
  }

  // List all memory files
  const memoryFiles = fs.readdirSync(MEMORY_DIR).filter(f => f.endsWith('.md') && f !== 'MEMORY.md');
  if (memoryFiles.length > 0) {
    log('\n📄  AVAILABLE MEMORY FILES:');
    for (const f of memoryFiles) {
      log(`   • ${f}`);
    }
  }

  // ── 2. Past Conversation Transcripts ────────────────────────────
  const transcripts = fs.readdirSync(CONVERSATIONS_DIR)
    .filter(f => f.endsWith('.jsonl'))
    .sort((a, b) => {
      const aTime = fs.statSync(path.join(CONVERSATIONS_DIR, a)).mtimeMs;
      const bTime = fs.statSync(path.join(CONVERSATIONS_DIR, b)).mtimeMs;
      return bTime - aTime;
    });

  if (transcripts.length > 0) {
    log(`\n💬  PAST SESSION TRANSCRIPTS: ${transcripts.length} archived`);
    log('   Most recent:');
    transcripts.slice(0, 5).forEach(t => {
      const stats = fs.statSync(path.join(CONVERSATIONS_DIR, t));
      const size = (stats.size / 1024).toFixed(1);
      const date = stats.mtime.toISOString().split('T')[0];
      log(`   • ${t} (${size} KB, ${date})`);
    });
    if (transcripts.length > 5) {
      log(`   ... and ${transcripts.length - 5} more`);
    }
    log(`   📁 Location: ${CONVERSATIONS_DIR}`);
  }

  // ── 3. Recent Session Files (.tmp) ──────────────────────────────
  const recentSessions = findFiles(sessionsDir, '*.tmp', { maxAge: 7 });

  if (recentSessions.length > 0) {
    log('\n📝  RECENT SESSION CONTEXT FILES:');
    recentSessions.slice(0, 3).forEach(s => {
      const content = readFile(s.path);
      if (content) {
        const lines = content.split('\n').filter(l => l.trim()).slice(0, 10);
        log(`   📄 ${path.basename(s.path)}:`);
        lines.forEach(l => log(`      ${l}`));
      }
    });
  }

  // ── 4. Learned Skills ───────────────────────────────────────────
  const learnedSkills = findFiles(learnedDir, '*.md');
  if (learnedSkills.length > 0) {
    log(`\n🧠  LEARNED SKILLS: ${learnedSkills.length} available in ${learnedDir}`);
    learnedSkills.slice(0, 5).forEach(s => log(`   • ${path.basename(s.path)}`));
  }

  // ── 5. Package Manager ──────────────────────────────────────────
  const pm = getPackageManager();
  log(`\n📦  PACKAGE MANAGER: ${pm.name} (${pm.source})`);

  if (pm.source === 'fallback' || pm.source === 'default') {
    log('[SessionStart] No package manager preference found.');
    log(getSelectionPrompt());
  }

  // ── 6. Quick Reminders ──────────────────────────────────────────
  log('\n⚡  QUICK REMINDERS:');
  log('   • Safe-move protocol: git status → git log → combine → commit → edit');
  log('   • Protected constants: ARCHITECT_SIGNOFF, CLV gate, ID405 override, softness=open');
  log('   • Memory check-in: HR54 mandatory (runs automatically)');
  log('   • Commit always: never leave working tree dirty');
  log('   • Everything-claude-code: use agents/skills/commands proactively');

  log('\n═══════════════════════════════════════════════════════════');
  log('✅  CONTEXT LOADED — READY TO WORK');
  log('═══════════════════════════════════════════════════════════\n');

  process.exit(0);
}

main().catch(err => {
  console.error('[SessionStart] Error:', err.message);
  process.exit(0); // Don't block on errors
});