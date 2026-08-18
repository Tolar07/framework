#!/usr/bin/env node
/**
 * audit-conversation.js — Pre-archive conversation audit
 *
 * Runs on SessionEnd BEFORE archive-conversation.js.
 * Audits the conversation transcript for fabrication patterns.
 * If CRITICAL findings found → blocks archive, writes report to memory/audit/
 * If clean → exits 0 to allow archive to proceed.
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const REPO_ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';
const MEMORY_ROOT = path.join(process.env.USERPROFILE || process.env.HOME || '', '.claude', 'projects', 'C--Users-Motunrayo-omniroute-test');
const AUDIT_DIR = path.join(MEMORY_ROOT, 'audit');
const CONVERSATIONS_DIR = path.join(REPO_ROOT, 'memory', 'conversations');
const AUDITOR_SCRIPT = path.join(REPO_ROOT, 'conversation_auditor.py');

function log(msg) {
  console.error(`[AuditConversation] ${msg}`);
}

function ensureAuditDir() {
  if (!fs.existsSync(AUDIT_DIR)) {
    fs.mkdirSync(AUDIT_DIR, { recursive: true });
  }
}

function findTranscript() {
  // First check CLAUDE_TRANSCRIPT_PATH env var
  if (process.env.CLAUDE_TRANSCRIPT_PATH && fs.existsSync(process.env.CLAUDE_TRANSCRIPT_PATH)) {
    return process.env.CLAUDE_TRANSCRIPT_PATH;
  }

  // Fallback: look in conversations dir for most recent transcript
  if (fs.existsSync(CONVERSATIONS_DIR)) {
    const files = fs.readdirSync(CONVERSATIONS_DIR)
      .filter(f => f.endsWith('.jsonl'))
      .sort()
      .reverse();
    if (files.length > 0) {
      return path.join(CONVERSATIONS_DIR, files[0]);
    }
  }

  // Fallback: look in CLAUDE_PROJECTS_DIR
  const CLAUDE_PROJECTS_DIR = path.join(MEMORY_ROOT);
  if (fs.existsSync(CLAUDE_PROJECTS_DIR)) {
    const files = fs.readdirSync(CLAUDE_PROJECTS_DIR)
      .filter(f => f.endsWith('.jsonl'))
      .sort()
      .reverse();
    if (files.length > 0) {
      return path.join(CLAUDE_PROJECTS_DIR, files[0]);
    }
  }

  return null;
}

async function main() {
  const transcriptPath = findTranscript();

  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    log('No transcript found, skipping audit');
    process.exit(0);
  }

  log(`Auditing transcript: ${transcriptPath}`);

  // Run conversation auditor with --json output
  const result = spawnSync('python', [AUDITOR_SCRIPT, 'audit', transcriptPath, '--json'], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    timeout: 30000
  });

  if (result.error) {
    log(`Auditor execution failed: ${result.error.message}`);
    // Non-blocking: don't prevent archive on auditor failure
    process.exit(0);
  }

  let auditReport;
  try {
    auditReport = JSON.parse(result.stdout.trim());
  } catch (e) {
    log(`Failed to parse auditor JSON output: ${e.message}`);
    log(`STDOUT: ${result.stdout}`);
    log(`STDERR: ${result.stderr}`);
    process.exit(0);
  }

  const { summary, findings } = auditReport;
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

  // Always write audit report to memory/audit/
  ensureAuditDir();
  const reportName = `audit_${timestamp}.json`;
  const reportPath = path.join(AUDIT_DIR, reportName);
  fs.writeFileSync(reportPath, JSON.stringify(auditReport, null, 2), 'utf8');
  log(`Audit report written to ${reportPath}`);

  // Also append summary to vault Audit Reports.md
  const vaultAuditPath = path.join(REPO_ROOT, 'docs', 'obsidian-vault', 'Audit Reports.md');
  const vaultEntry = `\n\n---\n\n## Audit Report ${new Date().toISOString()}\n\n- **Transcript:** ${path.basename(transcriptPath)}\n- **Total Incidents:** ${summary.total_incidents}\n- **CRITICAL:** ${summary.critical}\n- **HIGH:** ${summary.high}\n- **MEDIUM:** ${summary.medium}\n- **Passed:** ${summary.passed}\n- **Blocked:** ${summary.blocked}\n- **Full Report:** \`memory/audit/${reportName}\`\n`;
  try {
    const existing = fs.existsSync(vaultAuditPath) ? fs.readFileSync(vaultAuditPath, 'utf8') : '# Audit Reports\n\nAppend-only log of conversation audit results.\n';
    fs.writeFileSync(vaultAuditPath, existing + vaultEntry, 'utf8');
  } catch (e) {
    log(`Failed to append to vault Audit Reports.md: ${e.message}`);
  }

  // Log findings
  if (findings.length > 0) {
    log(`Found ${findings.length} incidents:`);
    findings.forEach(f => {
      log(`  [${f.severity}] ${f.pattern_id}: ${f.pattern_name} (line ${f.line})`);
    });
  } else {
    log('No fabrication patterns detected.');
  }

  // Block archive if CRITICAL findings
  if (summary.blocked) {
    log('CRITICAL findings detected — BLOCKING archive');
    console.error('AUDIT_BLOCKED: CRITICAL fabrication patterns found. Archive prevented.');
    process.exit(1); // Non-zero exit blocks subsequent hooks
  }

  log('Audit passed — archive may proceed');
  process.exit(0);
}

main().catch(err => {
  console.error('[AuditConversation] Error:', err.message);
  process.exit(0); // Never block on error
});