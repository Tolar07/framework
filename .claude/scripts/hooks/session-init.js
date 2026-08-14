#!/usr/bin/env node
/**
 * session-init.js — OLP XDV Session Initialization
 *
 * Runs on SessionStart. Enhances the existing session-start.js with:
 * 1. Safe-move protocol (git status + log check)
 * 2. Auto-detection of relevant skills based on pending task
 * 3. OLP XDV context loading
 * 4. Data quality verification
 *
 * Cross-platform (Windows, macOS, Linux)
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const https = require('https');

const ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';

const VAULT_ROOT = 'C:/Users/Motunrayo/Documents/OLP_XDV_Vault';
const VAULT_API_KEY = '32f3dcf8f4b514ce5b6fce5dfd04dc7f0f9d4d01636834b792e33b7803cd1143';

function run(cmd, args, cwd) {
  try {
    const r = spawnSync(cmd, args, { cwd, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
    return { stdout: r.stdout || '', stderr: r.stderr || '', code: r.status || 0 };
  } catch (e) {
    return { stdout: '', stderr: e.message, code: 1 };
  }
}

function log(msg) {
  console.error(`[session-init] ${msg}`);
}

function checkGit() {
  // Safe-move protocol: check git status first
  const status = run('git', ['status', '--short'], ROOT);
  const logRes = run('git', ['log', '--oneline', '-5'], ROOT);

  if (status.code === 0) {
    const changes = status.stdout.trim().split('\n').filter(Boolean);
    const staged = changes.filter(l => l.startsWith('M ') || l.startsWith('A ') || l.startsWith('D ')).length;
    const modified = changes.filter(l => l.startsWith(' M') || l.startsWith('??')).length;

    log(`Git branch: ${run('git', ['branch', '--show-current'], ROOT).stdout.trim()}`);
    log(`Staged changes: ${staged}, Unstaged: ${modified}, Untracked: ${changes.filter(l => l.startsWith('??')).length}`);
    log(`⚠ Safe-move: Another session may have staged ${staged} files. Use 'git commit --only <paths>' to avoid sweeping them.`);
  }

  if (logRes.code === 0) {
    log(`Recent commits:\n${logRes.stdout.trim()}`);
  }
}

function loadContext() {
  const files = ['CLAUDE.md', 'ARCHITECTURE.md', 'PROJECT_STATUS.md', 'RATIFICATIONS.md'];
  files.forEach(f => {
    const p = path.join(ROOT, f);
    if (fs.existsSync(p)) {
      log(`✓ Loaded ${f} (${fs.statSync(p).size} bytes)`);
    } else {
      log(`✗ Missing ${f}`);
    }
  });

  // Check .env
  const envPath = path.join(ROOT, '.env');
  if (fs.existsSync(envPath)) {
    const env = fs.readFileSync(envPath, 'utf8');
    const keys = (env.match(/^([A-Z_]+)=/gm) || []).map(s => s.replace('=', '')).filter(k => !k.includes('SECRET') && !k.includes('KEY'));
    log(`✓ .env loaded (${keys.length} non-secret keys)`);
  }
}

function detectSkills() {
  // Auto-detect based on recent changes (untracked files hint at task type)
  const status = run('git', ['status', '--short'], ROOT).stdout;
  const skills = new Set();

  const triggers = {
    'betting': /odds|edge|kelly|arb|parlay|devig/i,
    'football-data': /football|xg|standings|league|fixture/i,
    'olp-xdv': /brain|clv|gate|board|audit/i,
    'security-review': /security|vuln|audit|secret/i,
    'dataviz': /chart|dashboard|plot|visual/i,
  };

  Object.entries(triggers).forEach(([skill, re]) => {
    if (re.test(status)) skills.add(skill);
  });

  // Always load olp-xdv for this project
  skills.add('olp-xdv');

  log(`🎯 Skills available: ${[...skills].join(', ')}`);
  return [...skills];
}

function verifyData() {
  const catPath = path.join(ROOT, 'config', 'leagues.json');
  if (fs.existsSync(catPath)) {
    try {
      const cat = JSON.parse(fs.readFileSync(catPath, 'utf8'));
      const n = cat.leagues ? Object.keys(cat.leagues).length : 0;
      log(`📊 Data: ${n} leagues configured`);
    } catch (e) {
      log(`✗ Catalog parse error: ${e.message}`);
    }
  } else {
    log('ℹ No league catalog found at config/leagues.json');
  }
}

function checkPermissions() {
  const settingsPath = path.join(ROOT, '.claude', 'settings.local.json');
  if (fs.existsSync(settingsPath)) {
    try {
      const s = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
      const allow = (s.permissions?.allow || []).length;
      log(`⚙️  Permissions: ${allow} allow-rules configured`);
    } catch (e) {
      log(`✗ settings.local.json parse error`);
    }
  }
}

// Read vault files via local REST API
async function readVaultContext() {
  const keyFiles = [
    'OLP XDV.md',
    'Rules.md',
    'Decisions Log.md',
    'Open Questions.md',
    'Protected Constants.md',
    'Architecture.md',
    'Agents.md'
  ];

  log('📚 Reading Obsidian vault context...');

  for (const file of keyFiles) {
    try {
      const content = await readVaultFile(file);
      if (content) {
        const lines = content.split('\n').length;
        const preview = content.slice(0, 200).replace(/\n/g, ' ');
        log(`  ✓ ${file} (${lines} lines): ${preview}...`);
      } else {
        log(`  ⚠ ${file}: empty or not found`);
      }
    } catch (e) {
      log(`  ✗ ${file}: ${e.message}`);
    }
  }
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
      rejectUnauthorized: false // self-signed cert
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

// Also check vault sync status
function checkVaultSync() {
  const syncScript = path.join(ROOT, '.claude', 'scripts', 'hooks', 'obsidian-sync.js');
  if (fs.existsSync(syncScript)) {
    const result = spawnSync('node', [syncScript, 'status'], { cwd: ROOT, encoding: 'utf8' });
    if (result.code === 0) {
      const lines = result.stdout.trim().split('\n');
      const diverged = lines.filter(l => l.includes('DIVERGED')).length;
      const synced = lines.filter(l => l.includes('IN SYNC')).length;
      log(`🔄 Vault sync: ${synced} synced, ${diverged} diverged`);
      if (diverged > 0) {
        log(`  ⚠ Run 'node .claude/scripts/hooks/obsidian-sync.js push|pull' to resolve`);
      }
    }
  }
}

async function main() {
  log('=== OLP XDV Session Initialization ===');

  if (!fs.existsSync(path.join(ROOT, '.git'))) {
    log('✗ Not a git repo at ' + ROOT);
    process.exit(0);
  }

  checkGit();
  loadContext();
  detectSkills();
  verifyData();
  checkPermissions();

  // NEW: Read Obsidian vault for context
  checkVaultSync();
  await readVaultContext().catch(e => log(`✗ Vault read failed: ${e.message}`));

  log('=== Ready ===');
  process.exit(0);
}

main();
