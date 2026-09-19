#!/usr/bin/env node
/**
 * hourly-fixture-check.js — Hourly fixture refresh for matches yet to start
 *
 * Runs every hour to:
 * 1. Find fixtures in the database that haven't kicked off yet
 * 2. Refresh their odds and verify data freshness
 * 3. Run a lightweight pipeline pass on upcoming matches only
 * 4. Update board if new fixtures appear or odds change significantly
 * 5. Skip matches that have already kicked off (no point generating bets on live games)
 *
 * This replaces the daily-only 07:00 run with hourly awareness of match timing.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
// node:sqlite, not the sqlite3 npm package (fixed 2026-09-19).
//
// The 'OLP XDV Daily Result Verification' scheduled task had been exiting 1
// every night on "Cannot find module 'sqlite3'" -- the dependency was never
// installed. The task reported failure faithfully and nothing was reading it,
// so result verification had simply not been running.
//
// node:sqlite ships with Node (>=22) and needs no native build, so this
// cannot break again by an npm install being skipped on a fresh machine.
const { DatabaseSync } = require('node:sqlite');

const REPO_ROOT = 'c:/Users/Motunrayo/omniroute test';
const DB_PATH = path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv', 'brain', 'olp.db');
const LOG_DIR = path.join(REPO_ROOT, 'logs', 'hourly-fixture-check');
const STATE_FILE = path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv', 'data', 'hourly-fixture-state.json');

function ensureDirs() {
  [LOG_DIR].forEach(d => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  });
}

function log(msg) {
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] ${msg}\n`;
  ensureDirs();
  fs.appendFileSync(path.join(LOG_DIR, `hourly-fixture-${new Date().toISOString().split('T')[0]}.log`), line, 'utf8');
  console.log(line.trim());
}

function runCmd(cmd, cwd = REPO_ROOT) {
  try {
    const output = execSync(cmd, { cwd, encoding: 'utf8', stdio: 'pipe', timeout: 600000 });
    return { success: true, output: output.trim() };
  } catch (e) {
    return { success: false, output: e.stdout?.toString() || e.message, error: e.stderr?.toString() };
  }
}

function runSQL(query) {
  return new Promise((resolve, reject) => {
    let db;
    try {
      db = new DatabaseSync(DB_PATH, { readOnly: true });
      const rows = db.prepare(query).all();
      resolve({ success: true, rows });
    } catch (err) {
      reject(err);
    } finally {
      if (db) { try { db.close(); } catch (_) { /* already closed */ } }
    }
  });
}

function loadLastState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch (e) {
    log(`Warning: Could not load last state: ${e.message}`);
  }
  return { lastRun: null, lastBoardDate: null, processedRunIds: [] };
}

function saveLastState(state) {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
  } catch (e) {
    log(`Warning: Could not save state: ${e.message}`);
  }
}

async function getUpcomingFixtures() {
  // Get fixtures from predictions table that haven't kicked off yet
  // We use predictions since full_slate_results has settled matches
  // Note: predictions table only has match_date, not kickoff_time
  const query = `
    SELECT DISTINCT p.league, p.fixture, p.match_date,
           p.run_id, p.predicted_at, p.market, p.model_engine, p.model_prob,
           p.entry_odds, p.bookmaker, p.ev, p.on_deploy_shortlist
    FROM predictions p
    WHERE p.hit IS NULL
    AND p.match_date >= date('now')
    ORDER BY p.match_date ASC
  `;
  try {
    const result = await runSQL(query);
    return result.rows.map(row => ({
      league: row.league,
      fixture: row.fixture,
      match_date: row.match_date,
      kickoff_time: null, // Not available in predictions table
      run_id: row.run_id,
      predicted_at: row.predicted_at,
      market: row.market,
      engine: row.model_engine,
      probability: parseFloat(row.model_prob),
      odds: row.entry_odds ? parseFloat(row.entry_odds) : null,
      bookmaker: row.bookmaker,
      ev: row.ev ? parseFloat(row.ev) : null,
      on_deploy_shortlist: row.on_deploy_shortlist
    }));
  } catch (e) {
    log(`❌ Failed to query upcoming fixtures: ${e.message}`);
    return [];
  }
}

async function getKickedOffFixtures() {
  // Get fixtures that have already kicked off (for reference/skipping)
  const query = `
    SELECT DISTINCT p.league, p.fixture, p.match_date, p.kickoff_time
    FROM predictions p
    WHERE p.hit IS NOT NULL
    AND p.match_date <= date('now')
    ORDER BY p.match_date DESC
    LIMIT 50
  `;
  try {
    const result = await runSQL(query);
    return result.rows.map(row => ({
      league: row.league,
      fixture: row.fixture,
      match_date: row.match_date,
      kickoff_time: row.kickoff_time
    }));
  } catch (e) {
    log(`❌ Failed to query kicked-off fixtures: ${e.message}`);
    return [];
  }
}

async function getLatestBoard() {
  // Check if there's a board generated today
  const boardDir = path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv', 'output', 'boards');
  if (!fs.existsSync(boardDir)) return null;

  const files = fs.readdirSync(boardDir)
    .filter(f => (f.startsWith('board_') || f.startsWith('produced_')) && (f.endsWith('.json') || f.endsWith('.txt')))
    .sort()
    .reverse();

  if (files.length === 0) return null;

  try {
    // Try to find a board with today's date in content
    const today = new Date().toISOString().split('T')[0];
    
    for (const fileName of files) {
      let boardDate = null;
      let data = { fixtures: [] };

      if (fileName.endsWith('.json')) {
        const content = JSON.parse(fs.readFileSync(path.join(boardDir, fileName), 'utf8'));
        boardDate = content.date || content.board_date;
        data = content;
      } else {
        // Parse txt file header for date
        const content = fs.readFileSync(path.join(boardDir, fileName), 'utf8');
        const match = content.match(/Date: (\d{4}-\d{2}-\d{2})/);
        if (match) {
          boardDate = match[1];
        }
      }
      
      // If we found a board for today, return it immediately
      if (boardDate === today) {
        return { file: fileName, data: data, boardDate };
      }
    }
    
    // Fallback: return the latest one found
    const fileName = files[0];
    let boardDate = null;
    let data = { fixtures: [] };
    if (fileName.endsWith('.json')) {
      const content = JSON.parse(fs.readFileSync(path.join(boardDir, fileName), 'utf8'));
      boardDate = content.date || content.board_date;
      data = content;
    } else {
      const content = fs.readFileSync(path.join(boardDir, fileName), 'utf8');
      const match = content.match(/Date: (\d{4}-\d{2}-\d{2})/);
      if (match) boardDate = match[1];
    }
    return { file: fileName, data: data, boardDate };
  } catch (e) {
    log(`❌ Failed to read latest board: ${e.message}`);
    return null;
  }
}

async function runLightweightPipeline() {
  // Run a lightweight pipeline: only agents 1-4 (ingest through verification)
  // This avoids the heavy math/odds/execution agents for hourly refresh
  log('🔄 Running lightweight pipeline (agents 1-4) for upcoming fixtures...');

  const cmd = `cd "${path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv')}" && python olp_xdv_pipeline.py --only 4 --dry-run 2>&1`;
  const result = runCmd(cmd);

  if (!result.success) {
    log(`⚠️ Lightweight pipeline failed: ${result.output}`);
    if (result.error) log(`   stderr: ${result.error}`);
  } else {
    log(`✅ Lightweight pipeline completed`);
    if (result.output) {
      // Log key output lines
      const lines = result.output.split('\n').filter(l => l.trim());
      lines.slice(-20).forEach(l => log(`   ${l}`));
    }
  }

  return result;
}

async function runFullPipelineIfNeeded(lastState) {
  // Check if we need a full pipeline run (no board today, or significant time passed)
  const today = new Date().toISOString().split('T')[0];
  const lastBoardDate = lastState.lastBoardDate;

  if (!lastBoardDate || lastBoardDate !== today) {
    log('📅 No board for today yet — running full pipeline...');

    // --no-send/--no-whatsapp/--no-email ARE THE POINT OF THIS LINE.
    //
    // This is an HOURLY FIXTURE CHECK. It used to invoke run_daily.py with
    // delivery ENABLED, so every run BROADCAST A BOARD TO TELEGRAM. Worse, the
    // guard above is `lastBoardDate !== today` and the task exits rc=1, so
    // lastBoardDate never advanced — the pipeline re-ran and re-sent EVERY
    // HOUR, all day. That is the unsolicited "Phase 2 — paper calibration"
    // board the Architect reported receiving repeatedly on 2026-09-17 and had
    // tried several times to stop.
    //
    // It also explains the stale FORMAT and PHASE in those messages: with no
    // --date it looks for a Stage A artifact it does not find, falls back to
    // the legacy olp_xdv_pipeline path, and emits the old
    // render_telegram_board output (the five-league "DATA FLAGS /
    // RECOMMENDED — THE CALL" layout) rather than the ratified production
    // board.
    //
    // This script refreshes fixture state. Refreshing state must never
    // publish. The daily board has its own scheduled task; delivery belongs
    // there, not here.
    const cmd = `cd "${path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv')}" && python run_daily.py --season 2526 --fixtures-season 2627 --no-send --no-whatsapp --no-email 2>&1`;
    const result = runCmd(cmd);

    if (!result.success) {
      log(`❌ Full pipeline failed: ${result.output}`);
      if (result.error) log(`   stderr: ${result.error}`);
    } else {
      log(`✅ Full pipeline completed`);
      // Update state
      lastState.lastBoardDate = today;
      saveLastState(lastState);
    }

    return result;
  }

  log('✅ Board already exists for today — skipping full pipeline');
  return { success: true, output: 'Board exists, skipped' };
}

function filterUpcomingFixtures(fixtures) {
  // Filter to only fixtures that haven't kicked off yet
  // Since we only have match_date (no kickoff_time in predictions),
  // we assume matches kick off at some point during match_date.
  // If match_date is today or future, it's upcoming.
  // If match_date is past, it's kicked off.
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  const upcoming = [];
  const kickedOff = [];

  for (const fx of fixtures) {
    if (!fx.match_date) {
      // Unknown date — keep as conditional
      upcoming.push({ ...fx, kickoffStatus: 'UNKNOWN_DATE' });
      continue;
    }

    try {
      const matchDate = new Date(`${fx.match_date}T00:00:00Z`);
      const matchDateStr = fx.match_date;

      if (matchDateStr >= todayStr) {
        // Match is today or future - upcoming
        const hoursUntilMatch = (matchDate - now) / (1000 * 60 * 60);
        // Cap at 72 hours for display
        const displayHours = Math.max(0, hoursUntilMatch);
        upcoming.push({ ...fx, kickoffStatus: 'UPCOMING', hoursUntilKickoff: displayHours.toFixed(1) });
      } else {
        // Match date is in the past - already kicked off
        kickedOff.push({ ...fx, kickoffStatus: 'KICKED_OFF' });
      }
    } catch {
      upcoming.push({ ...fx, kickoffStatus: 'PARSE_ERROR' });
      continue;
    }
  }

  return { upcoming, kickedOff };
}

async function main() {
  log('═══════════════════════════════════════════════════════════');
  log('⏰ HOURLY FIXTURE CHECK — Upcoming matches only');
  log('═══════════════════════════════════════════════════════════');

  if (!fs.existsSync(DB_PATH)) {
    log(`❌ Database not found: ${DB_PATH}`);
    process.exit(1);
  }

  // Load state
  const lastState = loadLastState();
  log(`📌 Last run: ${lastState.lastRun || 'never'}`);
  log(`📌 Last board date: ${lastState.lastBoardDate || 'none'}`);

  // Get upcoming fixtures from predictions
  const allFixtures = await getUpcomingFixtures();
  log(`🔍 Found ${allFixtures.length} fixture predictions in DB (hit IS NULL)`);

  // Filter to upcoming only
  const { upcoming, kickedOff } = filterUpcomingFixtures(allFixtures);
  log(`📅 Upcoming (not kicked off): ${upcoming.length}`);
  log(`⚽ Already kicked off: ${kickedOff.length}`);

  if (upcoming.length > 0) {
    log('\n📋 Upcoming fixtures:');
    // Group by league
    const byLeague = {};
    upcoming.forEach(fx => {
      if (!byLeague[fx.league]) byLeague[fx.league] = [];
      byLeague[fx.league].push(fx);
    });

    Object.entries(byLeague).forEach(([league, fixtures]) => {
      log(`   ${league}: ${fixtures.length} fixture(s)`);
      fixtures.slice(0, 5).forEach(fx => {
        const status = fx.hoursUntilKickoff ? `${fx.hoursUntilKickoff}h` : fx.kickoffStatus;
        log(`      ${fx.fixture} @ ${fx.match_date} ${fx.kickoff_time || ''} (${status})`);
      });
      if (fixtures.length > 5) {
        log(`      ... and ${fixtures.length - 5} more`);
      }
    });
  }

  // Check latest board
  const latestBoard = await getLatestBoard();
  if (latestBoard) {
    log(`\n📋 Latest board: ${latestBoard.file}`);
    log(`   Board date: ${latestBoard.boardDate || 'unknown'}`);
    log(`   Fixtures on board: ${latestBoard.data.fixtures?.length || 0}`);
  } else {
    log('\n📋 No board found');
  }

  // Decide what to run
  const today = new Date().toISOString().split('T')[0];

  if (!latestBoard || latestBoard.boardDate !== today) {
    // No board for today — run full pipeline
    await runFullPipelineIfNeeded(lastState);
  } else if (upcoming.length > 0) {
    // Board exists but there are upcoming fixtures — run lightweight refresh
    await runLightweightPipeline();
  } else {
    log('\nℹ️ No upcoming fixtures and board exists — nothing to do');
  }

  // Save state
  saveLastState({
    lastRun: new Date().toISOString(),
    lastBoardDate: latestBoard?.boardDate || today,
    upcomingCount: upcoming.length,
    kickedOffCount: kickedOff.length
  });

  log('\n═══════════════════════════════════════════════════════════');
  log('✅ HOURLY FIXTURE CHECK COMPLETE');
  log('═══════════════════════════════════════════════════════════\n');
}

main().catch(err => {
  log(`\n❌ FATAL: ${err.message}`);
  process.exit(1);
});