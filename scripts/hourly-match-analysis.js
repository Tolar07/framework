#!/usr/bin/env node
/**
 * hourly-match-analysis.js — Continuous learning from match results
 *
 * Runs every hour to:
 * 1. Find newly settled matches in brain/olp.db
 * 2. Extract full match data (scores, markets, odds, lineups, etc.)
 * 3. Compare predictions vs actuals across all engines/markets
 * 4. Calculate CLV, calibration, miss patterns
 * 5. Update learning weights / recalibration data
 * 6. Log insights for next production cycle
 *
 * This is the "teach the framework" loop — turns outcomes into better predictions.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const sqlite3 = require('sqlite3').verbose();

const REPO_ROOT = 'c:/Users/Motunrayo/omniroute test';
const DB_PATH = path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv', 'brain', 'olp.db');
const LOG_DIR = path.join(REPO_ROOT, 'logs', 'hourly-analysis');
const LEARNING_DIR = path.join(REPO_ROOT, 'olp_xdv_agent', 'olp_xdv', 'data', 'learning');
const STATE_FILE = path.join(LEARNING_DIR, 'last-analysis-state.json');

function ensureDirs() {
  [LOG_DIR, LEARNING_DIR].forEach(d => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  });
}

function log(msg) {
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] ${msg}\n`;
  ensureDirs();
  fs.appendFileSync(path.join(LOG_DIR, `hourly-${new Date().toISOString().split('T')[0]}.log`), line, 'utf8');
  console.log(line.trim());
}

function runCmd(cmd, cwd = REPO_ROOT) {
  try {
    const output = execSync(cmd, { cwd, encoding: 'utf8', stdio: 'pipe', timeout: 60000 });
    return { success: true, output: output.trim() };
  } catch (e) {
    return { success: false, output: e.stdout?.toString() || e.message, error: e.stderr?.toString() };
  }
}

function runSQL(query) {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, sqlite3.OPEN_READONLY, (err) => {
      if (err) return reject(err);
    });
    db.all(query, [], (err, rows) => {
      db.close();
      if (err) return reject(err);
      resolve({ success: true, rows });
    });
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
  return { lastProcessedRunId: '', lastRun: null };
}

function saveLastState(state) {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
  } catch (e) {
    log(`Warning: Could not save state: ${e.message}`);
  }
}

async function getNewSettledRuns(lastRunId) {
  // Get runs that have settled predictions since last run
  // We use run_id as the ordering key since there's no fixture_id in predictions table
  const query = `
    SELECT DISTINCT p.run_id
    FROM predictions p
    WHERE p.hit IS NOT NULL
    ${lastRunId ? `AND p.run_id > '${lastRunId}'` : ''}
    ORDER BY p.run_id ASC
  `;
  try {
    const result = await runSQL(query);
    return result.rows.map(row => row.run_id);
  } catch (e) {
    log(`❌ Failed to query settled runs: ${e.message}`);
    return [];
  }
}

async function getSettledPredictionsForRun(runId) {
  // Get all settled predictions for a specific run
  const query = `
    SELECT p.id, p.run_id, p.predicted_at, p.league, p.fixture, p.match_date,
           p.market, p.model_engine, p.model_prob, p.entry_odds, p.bookmaker,
           p.ev, p.on_deploy_shortlist, p.cal_adjustment, p.ft_result, p.hit
    FROM predictions p
    WHERE p.run_id = '${runId}' AND p.hit IS NOT NULL
    ORDER BY p.league, p.fixture, p.market
  `;
  try {
    const result = await runSQL(query);
    return result.rows.map(row => ({
      id: row.id,
      run_id: row.run_id,
      predicted_at: row.predicted_at,
      league: row.league,
      fixture: row.fixture,
      match_date: row.match_date,
      market: row.market,
      engine: row.model_engine,
      probability: parseFloat(row.model_prob),
      odds: row.entry_odds ? parseFloat(row.entry_odds) : null,
      bookmaker: row.bookmaker,
      ev: row.ev ? parseFloat(row.ev) : null,
      on_deploy_shortlist: row.on_deploy_shortlist,
      cal_adjustment: row.cal_adjustment ? parseFloat(row.cal_adjustment) : null,
      ft_result: row.ft_result,
      hit: row.hit
    }));
  } catch (e) {
    log(`❌ Failed to query predictions for run ${runId}: ${e.message}`);
    return [];
  }
}

async function getLegsForRun(runId) {
  // Get legs data for CLV analysis - legs are keyed by date_logged, need to correlate
  const query = `
    SELECT l.leg_id, l.date_logged, l.league, l.fixture, l.market, l.model_prob,
           l.match_date, l.entry_odds, l.closing_odds, l.clv_pct, l.ft_result, l.hit,
           l.stake, l.phase
    FROM legs l
    WHERE l.hit IS NOT NULL
    ORDER BY l.date_logged ASC
  `;
  try {
    const result = await runSQL(query);
    return result.rows.map(row => ({
      leg_id: row.leg_id,
      date_logged: row.date_logged,
      league: row.league,
      fixture: row.fixture,
      market: row.market,
      model_prob: parseFloat(row.model_prob),
      match_date: row.match_date,
      entry_odds: row.entry_odds ? parseFloat(row.entry_odds) : null,
      closing_odds: row.closing_odds ? parseFloat(row.closing_odds) : null,
      clv_pct: row.clv_pct ? parseFloat(row.clv_pct) : null,
      ft_result: row.ft_result,
      hit: row.hit,
      stake: row.stake ? parseFloat(row.stake) : null,
      phase: row.phase
    }));
  } catch (e) {
    log(`❌ Failed to query legs: ${e.message}`);
    return [];
  }
}

async function getMatchResults() {
  // Get actual match results from full_slate_results
  const query = `
    SELECT fsr.id, fsr.league, fsr.fixture_date, fsr.home_team, fsr.away_team,
           fsr.fthg, fsr.ftag, fsr.ftr, fsr.kickoff_time
    FROM full_slate_results fsr
    ORDER BY fsr.fixture_date DESC, fsr.id DESC
  `;
  try {
    const result = await runSQL(query);
    return result.rows.map(row => ({
      id: row.id,
      league: row.league,
      fixture_date: row.fixture_date,
      home_team: row.home_team,
      away_team: row.away_team,
      fthg: row.fthg,
      ftag: row.ftag,
      ftr: row.ftr,
      kickoff_time: row.kickoff_time
    }));
  } catch (e) {
    log(`❌ Failed to query match results: ${e.message}`);
    return [];
  }
}

function analyzeRun(runId, predictions, legs, matchResults) {
  const analysis = {
    run_id: runId,
    predictions_count: predictions.length,
    engines: {},
    markets: {},
    clv: { values: [], mean: 0, positive: 0 },
    calibration: { bins: {} },
    miss_patterns: [],
    leagues: {}
  };

  // Build a map of legs for CLV lookup by fixture+market
  const legsMap = new Map();
  legs.forEach(l => {
    const key = `${l.fixture}|${l.market}`;
    legsMap.set(key, l);
  });

  // Group by engine
  predictions.forEach(p => {
    if (!analysis.engines[p.engine]) {
      analysis.engines[p.engine] = { total: 0, won: 0, lost: 0, clv_sum: 0, clv_count: 0 };
    }
    analysis.engines[p.engine].total++;
    if (p.hit === 1) analysis.engines[p.engine].won++;
    else if (p.hit === 0) analysis.engines[p.engine].lost++;

    // Try to get CLV from legs
    const legKey = `${p.fixture}|${p.market}`;
    const leg = legsMap.get(legKey);
    if (leg && leg.clv_pct !== null) {
      analysis.engines[p.engine].clv_sum += leg.clv_pct;
      analysis.engines[p.engine].clv_count++;
      analysis.clv.values.push(leg.clv_pct);
      if (leg.clv_pct > 0) analysis.clv.positive++;
    }

    // Group by market
    if (!analysis.markets[p.market]) {
      analysis.markets[p.market] = { total: 0, won: 0, lost: 0 };
    }
    analysis.markets[p.market].total++;
    if (p.hit === 1) analysis.markets[p.market].won++;
    else if (p.hit === 0) analysis.markets[p.market].lost++;

    // Group by league
    if (!analysis.leagues[p.league]) {
      analysis.leagues[p.league] = { total: 0, won: 0, lost: 0 };
    }
    analysis.leagues[p.league].total++;
    if (p.hit === 1) analysis.leagues[p.league].won++;
    else if (p.hit === 0) analysis.leagues[p.league].lost++;

    // Calibration bins
    const bin = Math.floor(p.probability * 10) / 10; // 0.0, 0.1, 0.2...
    const binKey = `${bin.toFixed(1)}-${(bin+0.1).toFixed(1)}`;
    if (!analysis.calibration.bins[binKey]) {
      analysis.calibration.bins[binKey] = { predictions: 0, hits: 0, avg_prob: 0 };
    }
    analysis.calibration.bins[binKey].predictions++;
    analysis.calibration.bins[binKey].avg_prob += p.probability;
    if (p.hit === 1) analysis.calibration.bins[binKey].hits++;
  });

  // Compute engine hit rates and avg CLV
  Object.keys(analysis.engines).forEach(e => {
    const eng = analysis.engines[e];
    eng.hit_rate = eng.total > 0 ? (eng.won / eng.total * 100).toFixed(1) : 0;
    eng.avg_clv = eng.clv_count > 0 ? (eng.clv_sum / eng.clv_count).toFixed(3) : 0;
  });

  // Compute market hit rates
  Object.keys(analysis.markets).forEach(m => {
    const mkt = analysis.markets[m];
    mkt.hit_rate = mkt.total > 0 ? (mkt.won / mkt.total * 100).toFixed(1) : 0;
  });

  // Compute league hit rates
  Object.keys(analysis.leagues).forEach(l => {
    const lg = analysis.leagues[l];
    lg.hit_rate = lg.total > 0 ? (lg.won / lg.total * 100).toFixed(1) : 0;
  });

  // Overall CLV
  if (analysis.clv.values.length > 0) {
    analysis.clv.mean = (analysis.clv.values.reduce((a,b) => a+b, 0) / analysis.clv.values.length).toFixed(3);
    analysis.clv.positive_rate = (analysis.clv.positive / analysis.clv.values.length * 100).toFixed(1);
  } else {
    analysis.clv.mean = 0;
    analysis.clv.positive_rate = 0;
  }

  // Calibration: compute hit rate per bin
  Object.keys(analysis.calibration.bins).forEach(bin => {
    const b = analysis.calibration.bins[bin];
    b.avg_prob = b.predictions > 0 ? (b.avg_prob / b.predictions).toFixed(3) : 0;
    b.hit_rate = b.predictions > 0 ? (b.hits / b.predictions * 100).toFixed(1) : 0;
    b.calibration_error = (b.hit_rate - b.avg_prob * 100).toFixed(1);
  });

  // Detect miss patterns
  // 1. Draw market failures
  if (analysis.markets['1X2_DRAW'] && analysis.markets['1X2_DRAW'].hit_rate < 30) {
    analysis.miss_patterns.push({ type: 'draw_market', severity: 'high', detail: `1X2_DRAW hit rate ${analysis.markets['1X2_DRAW'].hit_rate}%` });
  }
  // 2. League-specific failures
  Object.entries(analysis.leagues).forEach(([league, data]) => {
    if (data.total >= 3 && data.hit_rate < 30) {
      analysis.miss_patterns.push({ type: 'league_weak', severity: 'high', detail: `${league}: ${data.hit_rate}% hit rate (${data.won}/${data.total})` });
    }
  });
  // 3. Engine-specific failures
  Object.entries(analysis.engines).forEach(([engine, data]) => {
    if (data.total >= 3 && data.hit_rate < 30) {
      analysis.miss_patterns.push({ type: 'engine_weak', severity: 'medium', detail: `${engine}: ${data.hit_rate}% hit rate (${data.won}/${data.total})` });
    }
  });
  // 4. Negative CLV
  if (analysis.clv.mean < 0) {
    analysis.miss_patterns.push({ type: 'negative_clv', severity: 'high', detail: `Mean CLV ${analysis.clv.mean}% (${analysis.clv.positive_rate}% positive)` });
  }

  return analysis;
}

async function updateLearningWeights(allAnalyses) {
  // Aggregate across all runs this session
  const engineStats = {};
  const marketStats = {};
  const leagueStats = {};
  const calibrationBins = {};

  allAnalyses.forEach(a => {
    // Engine aggregation
    Object.entries(a.engines).forEach(([engine, data]) => {
      if (!engineStats[engine]) engineStats[engine] = { total: 0, won: 0, clv_sum: 0, clv_count: 0 };
      engineStats[engine].total += data.total;
      engineStats[engine].won += data.won;
      engineStats[engine].clv_sum += data.clv_sum;
      engineStats[engine].clv_count += data.clv_count;
    });

    // Market aggregation
    Object.entries(a.markets).forEach(([market, data]) => {
      if (!marketStats[market]) marketStats[market] = { total: 0, won: 0 };
      marketStats[market].total += data.total;
      marketStats[market].won += data.won;
    });

    // League aggregation
    Object.entries(a.leagues).forEach(([league, data]) => {
      if (!leagueStats[league]) leagueStats[league] = { total: 0, won: 0 };
      leagueStats[league].total += data.total;
      leagueStats[league].won += data.won;
    });

    // Calibration aggregation
    Object.entries(a.calibration.bins).forEach(([bin, data]) => {
      if (!calibrationBins[bin]) calibrationBins[bin] = { predictions: 0, hits: 0, avg_prob_sum: 0 };
      calibrationBins[bin].predictions += data.predictions;
      calibrationBins[bin].hits += data.hits;
      calibrationBins[bin].avg_prob_sum += data.avg_prob * data.predictions;
    });
  });

  // Compute recommended weights
  const engineWeights = {};
  Object.entries(engineStats).forEach(([engine, data]) => {
    const hitRate = data.total > 0 ? data.won / data.total : 0;
    const avgClv = data.clv_count > 0 ? data.clv_sum / data.clv_count : 0;
    // Weight = hit_rate * (1 + max(0, avg_clv/100)) — reward positive CLV
    const weight = hitRate * (1 + Math.max(0, avgClv / 100));
    engineWeights[engine] = { hitRate: (hitRate * 100).toFixed(1), avgClv: avgClv.toFixed(3), recommendedWeight: weight.toFixed(3) };
  });

  const marketWeights = {};
  Object.entries(marketStats).forEach(([market, data]) => {
    const hitRate = data.total > 0 ? data.won / data.total : 0;
    marketWeights[market] = { hitRate: (hitRate * 100).toFixed(1), total: data.total, recommend: hitRate > 0.35 ? 'keep' : 'reduce' };
  });

  const leagueWeights = {};
  Object.entries(leagueStats).forEach(([league, data]) => {
    const hitRate = data.total > 0 ? data.won / data.total : 0;
    leagueWeights[league] = { hitRate: (hitRate * 100).toFixed(1), total: data.total, recommend: hitRate > 0.35 ? 'keep' : 'quarantine' };
  });

  const calibrationCurve = {};
  Object.entries(calibrationBins).forEach(([bin, data]) => {
    const hitRate = data.predictions > 0 ? data.hits / data.predictions : 0;
    const avgProb = data.predictions > 0 ? data.avg_prob_sum / data.predictions : 0;
    calibrationCurve[bin] = { predictions: data.predictions, hitRate: (hitRate * 100).toFixed(1), avgProb: (avgProb * 100).toFixed(1), error: ((hitRate - avgProb) * 100).toFixed(1) };
  });

  const learning = {
    timestamp: new Date().toISOString(),
    runs_analyzed: allAnalyses.length,
    engine_weights: engineWeights,
    market_weights: marketWeights,
    league_weights: leagueWeights,
    calibration_curve: calibrationCurve,
    summary: {
      total_predictions: Object.values(engineStats).reduce((s, e) => s + e.total, 0),
      overall_hit_rate: (Object.values(engineStats).reduce((s, e) => s + e.won, 0) / Object.values(engineStats).reduce((s, e) => s + e.total, 0) * 100).toFixed(1),
      overall_clv: allAnalyses.length > 0 ? (allAnalyses.reduce((s, a) => s + parseFloat(a.clv.mean), 0) / allAnalyses.length).toFixed(3) : 0
    }
  };

  // Save learning data
  const learningFile = path.join(LEARNING_DIR, `learning-${new Date().toISOString().split('T')[0]}.json`);
  fs.writeFileSync(learningFile, JSON.stringify(learning, null, 2), 'utf8');
  log(`💾 Learning data saved: ${learningFile}`);

  // Also save latest for quick access
  fs.writeFileSync(path.join(LEARNING_DIR, 'latest-learning.json'), JSON.stringify(learning, null, 2), 'utf8');

  return learning;
}

async function generateReport(allAnalyses, learning) {
  const report = {
    timestamp: new Date().toISOString(),
    run_type: 'hourly-continuous-learning',
    runs_analyzed: allAnalyses.length,
    executive_summary: {
      total_predictions: learning.summary.total_predictions,
      overall_hit_rate: `${learning.summary.overall_hit_rate}%`,
      overall_clv: `${learning.summary.overall_clv}%`,
      critical_issues: allAnalyses.flatMap(a => a.miss_patterns.filter(p => p.severity === 'high')).length
    },
    engine_performance: learning.engine_weights,
    market_performance: learning.market_weights,
    league_performance: learning.league_weights,
    calibration: learning.calibration_curve,
    run_details: allAnalyses.map(a => ({
      run_id: a.run_id,
      predictions: a.predictions_count,
      engines: Object.fromEntries(Object.entries(a.engines).map(([k,v]) => [k, { hit_rate: v.hit_rate, avg_clv: v.avg_clv }])),
      markets: Object.fromEntries(Object.entries(a.markets).map(([k,v]) => [k, { hit_rate: v.hit_rate }])),
      leagues: Object.fromEntries(Object.entries(a.leagues).map(([k,v]) => [k, { hit_rate: v.hit_rate }])),
      clv: a.clv,
      miss_patterns: a.miss_patterns
    }))
  };

  const reportFile = path.join(LOG_DIR, `report-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2), 'utf8');
  log(`📊 Report saved: ${reportFile}`);

  return report;
}

async function main() {
  log('═══════════════════════════════════════════════════════════');
  log('🧠 HOURLY MATCH ANALYSIS — CONTINUOUS LEARNING');
  log('═══════════════════════════════════════════════════════════');

  if (!fs.existsSync(DB_PATH)) {
    log(`❌ Database not found: ${DB_PATH}`);
    process.exit(1);
  }

  // Load last state
  const lastState = loadLastState();
  log(`📌 Last processed run_id: ${lastState.lastProcessedRunId || 'none'}`);
  log(`📌 Last run: ${lastState.lastRun || 'never'}`);

  // Get new settled runs
  const newRunIds = await getNewSettledRuns(lastState.lastProcessedRunId);
  log(`🔍 Found ${newRunIds.length} newly settled run(s)`);

  if (newRunIds.length === 0) {
    log('ℹ️  No new settled runs — nothing to learn');
    log('═══════════════════════════════════════════════════════════\n');
    return;
  }

  // Get all legs data once for CLV correlation
  const allLegs = await getLegsForRun('');
  log(`📋 Loaded ${allLegs.length} settled legs for CLV correlation`);

  // Get match results
  const matchResults = await getMatchResults();
  log(`📋 Loaded ${matchResults.length} match results from full_slate_results`);

  const allAnalyses = [];
  let maxRunId = lastState.lastProcessedRunId;

  for (const runId of newRunIds) {
    log(`\n📋 Analyzing run: ${runId}`);

    const predictions = await getSettledPredictionsForRun(runId);
    if (predictions.length === 0) {
      log(`   ⚠️  No settled predictions for this run`);
      continue;
    }

    const analysis = analyzeRun(runId, predictions, allLegs, matchResults);

    allAnalyses.push(analysis);
    if (runId > maxRunId) maxRunId = runId;

    // Log key findings
    log(`   📊 ${predictions.length} settled predictions | Engines: ${Object.keys(analysis.engines).join(', ')}`);
    log(`   🎯 Hit rates: ${Object.entries(analysis.engines).map(([e,v]) => `${e}=${v.hit_rate}%`).join(', ')}`);
    log(`   💰 CLV: mean=${analysis.clv.mean}%, positive=${analysis.clv.positive_rate}%`);
    if (analysis.miss_patterns.length > 0) {
      analysis.miss_patterns.forEach(mp => log(`   ⚠️  ${mp.type}: ${mp.detail}`));
    }
  }

  // Update learning weights
  log('\n🧮 Updating learning weights...');
  const learning = await updateLearningWeights(allAnalyses);

  // Generate report
  log('\n📝 Generating report...');
  const report = await generateReport(allAnalyses, learning);

  // Save state
  saveLastState({
    lastProcessedRunId: maxRunId,
    lastRun: new Date().toISOString(),
    runsProcessed: newRunIds.length,
    predictionsAnalyzed: allAnalyses.reduce((s, a) => s + a.predictions_count, 0)
  });

  // Summary
  log('\n═══════════════════════════════════════════════════════════');
  log('✅ HOURLY ANALYSIS COMPLETE');
  log(`   Runs: ${allAnalyses.length} | Predictions: ${learning.summary.total_predictions}`);
  log(`   Hit rate: ${learning.summary.overall_hit_rate}% | CLV: ${learning.summary.overall_clv}%`);
  log(`   Engine weights updated: ${Object.keys(learning.engine_weights).length}`);
  log(`   Market recommendations: ${Object.values(learning.market_weights).filter(m => m.recommend === 'reduce').length} to reduce`);
  log(`   League recommendations: ${Object.values(learning.league_weights).filter(l => l.recommend === 'quarantine').length} to quarantine`);
  log('═══════════════════════════════════════════════════════════\n');
}

main().catch(err => {
  log(`\n❌ FATAL: ${err.message}`);
  process.exit(1);
});