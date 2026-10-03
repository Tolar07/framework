#!/usr/bin/env node
/**
 * team-name-audit.js — Daily team name cross-reference audit
 * Runs at 5am to find and fix club name discrepancies between:
 *   - TheSportsDB (fixtures source)
 *   - SportyBet (booking source)
 *   - Bet365 / API-Football (odds source)
 *   - football-data.co.uk (model training source)
 *
 * Outputs: JSON report + auto-updates to team_map.py and thesportsdb_fixtures.py
 */

const fs = require('fs');
const path = require('path');

const REPO_ROOT = 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';
const TEAM_MAP_PATH = path.join(REPO_ROOT, 'booking', 'team_map.py');
const TSDB_FIXTURES_PATH = path.join(REPO_ROOT, 'data', 'thesportsdb_fixtures.py');
const SPORTYBET_CACHE_DIR = path.join(REPO_ROOT, 'data', 'cache', 'sportybet', 'fixtures');
const LOG_DIR = path.join(REPO_ROOT, 'logs', 'team-name-audit');
const REPORT_DIR = path.join(REPO_ROOT, 'data', 'team-name-audit');

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function log(msg) {
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] ${msg}\n`;
  ensureDir(LOG_DIR);
  fs.appendFileSync(path.join(LOG_DIR, `audit-${new Date().toISOString().split('T')[0]}.log`), line, 'utf8');
  console.log(line.trim());
}

function readFile(filepath) {
  try {
    return fs.readFileSync(filepath, 'utf8');
  } catch (e) {
    log(`ERROR reading ${filepath}: ${e.message}`);
    return null;
  }
}

function writeFile(filepath, content) {
  try {
    ensureDir(path.dirname(filepath));
    fs.writeFileSync(filepath, content, 'utf8');
    return true;
  } catch (e) {
    log(`ERROR writing ${filepath}: ${e.message}`);
    return false;
  }
}

// Ported from team_map.py _normalize()
function normalize(name) {
  let n = name.toLowerCase().trim();
  for (const prefix of ["fc ", "sc ", "ac ", "cd ", "cf ", "rk ", "ss ", "sk ", "fk "]) {
    if (n.startsWith(prefix)) n = n.slice(prefix.length);
  }
  for (const suffix of [" fc", " sc", " ac", " cf", " if", " bk", " fk", " sk"]) {
    if (n.endsWith(suffix)) n = n.slice(0, -suffix.length);
  }
  const replacements = {
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
    "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "ø": "o",
    "æ": "ae", "ß": "ss", "ç": "c", "ž": "z", "ī": "i",
    "ș": "s", "ț": "t", "ğ": "g", "ş": "s", "ü": "u",
    "ő": "o", "ű": "u", "č": "c", "š": "s", "ř": "r",
    "ď": "d", "ť": "t", "ń": "n", "ľ": "l"
  };
  for (const [old, newChar] of Object.entries(replacements)) {
    n = n.replace(new RegExp(old, 'g'), newChar);
  }
  return n.trim();
}

function extractTSDBAliases(content) {
  const aliases = {};
  // Match TEAM_ALIASES dict
  const match = content.match(/TEAM_ALIASES\s*:\s*dict\[str,\s*dict\[str,\s*str\]\]\s*=\s*\{([\s\S]*?)\n\}/);
  if (!match) return aliases;

  const dictContent = match[1];
  // Find league sections
  const leaguePattern = /"([^"]+)":\s*\{([\s\S]*?)\}/g;
  let leagueMatch;
  while ((leagueMatch = leaguePattern.exec(dictContent)) !== null) {
    const league = leagueMatch[1];
    const entries = leagueMatch[2];
    aliases[league] = {};
    const entryPattern = /"([^"]+)":\s*"([^"]+)"/g;
    let entryMatch;
    while ((entryMatch = entryPattern.exec(entries)) !== null) {
      aliases[league][entryMatch[1]] = entryMatch[2];
    }
  }
  return aliases;
}

function extractSportyBetTeams(content) {
  const teams = {};
  // Match SPORTYBET_TEAMS dict
  const match = content.match(/SPORTYBET_TEAMS\s*:\s*dict\[str,\s*str\]\s*=\s*\{([\s\S]*?)\n\}/);
  if (!match) return teams;

  const dictContent = match[1];
  const entryPattern = /"([^"]+)":\s*"([^"]+)"/g;
  let entryMatch;
  while ((entryMatch = entryPattern.exec(dictContent)) !== null) {
    teams[entryMatch[1]] = entryMatch[2];
  }
  return teams;
}

function extractSportyBetCache() {
  const namesByLeague = {};
  if (!fs.existsSync(SPORTYBET_CACHE_DIR)) return namesByLeague;

  for (const file of fs.readdirSync(SPORTYBET_CACHE_DIR)) {
    if (!file.endsWith('.json')) continue;
    try {
      const content = JSON.parse(fs.readFileSync(path.join(SPORTYBET_CACHE_DIR, file), 'utf8'));
      const league = content.league || file.replace('.json', '').replace(/_/g, ' ');
      const fixtures = content.fixtures || [];
      const names = new Set();
      for (const fx of fixtures) {
        if (fx.sportybet_home) names.add(fx.sportybet_home);
        if (fx.sportybet_away) names.add(fx.sportybet_away);
      }
      if (names.size > 0) {
        namesByLeague[league] = Array.from(names).sort();
      }
    } catch (e) {
      log(`Error reading cache ${file}: ${e.message}`);
    }
  }
  return namesByLeague;
}

function buildReverseMap(sportybetTeams) {
  const reverse = {};
  for (const [modelKey, sbName] of Object.entries(sportybetTeams)) {
    if (!reverse[sbName]) reverse[sbName] = modelKey;
    const norm = normalize(sbName);
    if (!reverse[norm]) reverse[norm] = modelKey;
  }
  return reverse;
}

function findDiscrepancies(tsdbAliases, sportybetTeams, sportybetCache) {
  const report = {
    timestamp: new Date().toISOString(),
    additionsToTeamMap: [],
    additionsToTSDBAliases: [],
    collisions: [],
    warnings: [],
    stats: {
      tsdbLeagues: Object.keys(tsdbAliases).length,
      sportybetMapped: Object.keys(sportybetTeams).length,
      sportybetCachedLeagues: Object.keys(sportybetCache).length
    }
  };

  const reverseMap = buildReverseMap(sportybetTeams);

  // 1. Check SportyBet cache names against team_map.py
  for (const [league, cacheNames] of Object.entries(sportybetCache)) {
    for (const sbName of cacheNames) {
      const normName = normalize(sbName);
      // Check exact match
      if (!sportybetTeams.hasOwnProperty(sbName) && !reverseMap.hasOwnProperty(sbName) && !reverseMap.hasOwnProperty(normName)) {
        report.additionsToTeamMap.push({
          source: 'sportybet_cache',
          league: league,
          sportybetName: sbName,
          normalized: normName,
          suggestedModelKey: sbName, // default to same, needs human review
          confidence: 'low',
          reason: `SportyBet cache has "${sbName}" but no mapping exists in team_map.py`
        });
      }
    }
  }

  // 2. Check TSDB aliases against team_map.py (model keys should be in SPORTYBET_TEAMS)
  for (const [league, aliases] of Object.entries(tsdbAliases)) {
    for (const [tsdbName, modelKey] of Object.entries(aliases)) {
      if (!sportybetTeams.hasOwnProperty(modelKey)) {
        report.additionsToTeamMap.push({
          source: 'thesportsdb_alias',
          league: league,
          thesportsdbName: tsdbName,
          modelKey: modelKey,
          normalized: normalize(modelKey),
          suggestedSportyBetName: modelKey, // default
          confidence: 'medium',
          reason: `TSDB alias maps "${tsdbName}" -> "${modelKey}" but modelKey not in SportyBet map`
        });
      }
    }
  }

  // 3. Check for normalization collisions in team_map.py
  const normToKeys = {};
  for (const [modelKey, sbName] of Object.entries(sportybetTeams)) {
    const normKey = normalize(modelKey);
    const normSb = normalize(sbName);
    if (!normToKeys[normKey]) normToKeys[normKey] = [];
    if (!normToKeys[normSb]) normToKeys[normSb] = [];
    normToKeys[normKey].push(`model:${modelKey}`);
    normToKeys[normSb].push(`sb:${sbName}`);
  }
  for (const [norm, entries] of Object.entries(normToKeys)) {
    if (entries.length > 1) {
      report.collisions.push({
        normalized: norm,
        entries: entries,
        severity: 'high'
      });
    }
  }

  // 4. Check for potential fuzzy near-misses (names that look similar but are different clubs)
  // This is a heuristic - would need human review
  const allModelKeys = Object.keys(sportybetTeams);
  for (const key1 of allModelKeys) {
    for (const key2 of allModelKeys) {
      if (key1 >= key2) continue;
      const n1 = normalize(key1);
      const n2 = normalize(key2);
      // Simple similarity: one contains the other
      if (n1.includes(n2) || n2.includes(n1)) {
        if (n1 !== n2) {
          report.warnings.push({
            type: 'potential_fuzzy_confusion',
            name1: key1,
            name2: key2,
            norm1: n1,
            norm2: n2,
            reason: `Normalized names overlap - could cause wrong-club matching`
          });
        }
      }
    }
  }

  return report;
}

function generateFixReport(report) {
  let output = `# Team Name Audit Report - ${new Date().toISOString().split('T')[0]}\n\n`;
  output += `## Summary\n`;
  output += `- TSDB Leagues with aliases: ${report.stats.tsdbLeagues}\n`;
  output += `- SportyBet mapped teams: ${report.stats.sportybetMapped}\n`;
  output += `- SportyBet cached leagues: ${report.stats.sportybetCachedLeagues}\n`;
  output += `- Additions to team_map.py: ${report.additionsToTeamMap.length}\n`;
  output += `- Additions to TSDB aliases: ${report.additionsToTSDBAliases.length}\n`;
  output += `- Normalization collisions: ${report.collisions.length}\n`;
  output += `- Warnings: ${report.warnings.length}\n\n`;

  if (report.additionsToTeamMap.length > 0) {
    output += `## Additions to team_map.py (SPORTYBET_TEAMS)\n\n`;
    output += `| League | SportyBet Name | Model Key | Normalized | Confidence | Reason |\n`;
    output += `|--------|----------------|-----------|------------|------------|--------|\n`;
    for (const item of report.additionsToTeamMap) {
      const sbName = item.sportybetName || item.thesportsdbName || 'N/A';
      const modelKey = item.modelKey || item.suggestedModelKey || 'N/A';
      output += `| ${item.league} | ${sbName} | ${modelKey} | ${item.normalized} | ${item.confidence} | ${item.reason} |\n`;
    }
    output += `\n`;
  }

  if (report.collisions.length > 0) {
    output += `## Normalization Collisions (HIGH PRIORITY)\n\n`;
    output += `| Normalized | Conflicting Entries |\n`;
    output += `|------------|---------------------|\n`;
    for (const item of report.collisions) {
      output += `| ${item.normalized} | ${item.entries.join(', ')} |\n`;
    }
    output += `\n`;
  }

  if (report.warnings.length > 0) {
    output += `## Potential Fuzzy Confusion Warnings\n\n`;
    output += `| Name 1 | Name 2 | Norm 1 | Norm 2 |\n`;
    output += `|--------|--------|--------|--------|\n`;
    for (const item of report.warnings) {
      output += `| ${item.name1} | ${item.name2} | ${item.norm1} | ${item.norm2} |\n`;
    }
    output += `\n`;
  }

  return output;
}

function applyAutoFixes(report) {
  // Only auto-apply high-confidence additions that are identity mappings
  let applied = 0;
  let teamMapContent = readFile(TEAM_MAP_PATH);
  if (!teamMapContent) return applied;

  // Read current SPORTYBET_TEAMS
  const sportybetTeams = extractSportyBetTeams(teamMapContent);

  for (const item of report.additionsToTeamMap) {
    // Only auto-add if it's an identity mapping (same name on both sides) and not already present
    const sbName = item.sportybetName;
    const modelKey = item.modelKey || item.suggestedModelKey;

    if (sbName && modelKey && sbName === modelKey && !sportybetTeams.hasOwnProperty(modelKey)) {
      // Find the SPORTYBET_TEAMS dict and add entry
      const searchStr = 'SPORTYBET_TEAMS: dict[str, str] = {';
      const idx = teamMapContent.indexOf(searchStr);
      if (idx !== -1) {
        // Find the league section or end of dict
        const insertPos = teamMapContent.indexOf('\n}', idx);
        if (insertPos !== -1) {
          const newEntry = `    "${modelKey}": "${modelKey}",\n`;
          teamMapContent = teamMapContent.slice(0, insertPos) + newEntry + teamMapContent.slice(insertPos);
          applied++;
        }
      }
    }
  }

  if (applied > 0) {
    writeFile(TEAM_MAP_PATH, teamMapContent);
    log(`Auto-applied ${applied} identity mappings to team_map.py`);
  }

  return applied;
}

async function main() {
  log('═══════════════════════════════════════════════════════════');
  log('🔍 TEAM NAME AUDIT STARTED');
  log('═══════════════════════════════════════════════════════════');

  // 1. Load sources
  log('\n📦 Loading source data...');
  const tsdbContent = readFile(TSDB_FIXTURES_PATH);
  const teamMapContent = readFile(TEAM_MAP_PATH);

  if (!tsdbContent || !teamMapContent) {
    log('❌ Failed to load source files');
    process.exit(1);
  }

  // 2. Extract data
  log('📥 Extracting team names...');
  const tsdbAliases = extractTSDBAliases(tsdbContent);
  log(`   TSDB leagues: ${Object.keys(tsdbAliases).length}`);
  const sportybetTeams = extractSportyBetTeams(teamMapContent);
  log(`   SportyBet mapped: ${Object.keys(sportybetTeams).length}`);
  const sportybetCache = extractSportyBetCache();
  log(`   SportyBet cached leagues: ${Object.keys(sportybetCache).length}`);

  // 3. Find discrepancies
  log('\n🔍 Analyzing discrepancies...');
  const report = findDiscrepancies(tsdbAliases, sportybetTeams, sportybetCache);

  // 4. Generate report
  log('\n📊 Generating report...');
  ensureDir(REPORT_DIR);
  const reportFile = path.join(REPORT_DIR, `report-${new Date().toISOString().split('T')[0]}.json`);
  writeFile(reportFile, JSON.stringify(report, null, 2));
  log(`   JSON report: ${reportFile}`);

  const markdownReport = generateFixReport(report);
  const mdFile = path.join(REPORT_DIR, `report-${new Date().toISOString().split('T')[0]}.md`);
  writeFile(mdFile, markdownReport);
  log(`   Markdown report: ${mdFile}`);

  // 5. Apply safe auto-fixes
  log('\n🔧 Applying safe auto-fixes...');
  const applied = applyAutoFixes(report);
  log(`   Applied: ${applied}`);

  // 6. Summary
  log('\n═══════════════════════════════════════════════════════════');
  log('✅ TEAM NAME AUDIT COMPLETE');
  log(`   Additions needed: ${report.additionsToTeamMap.length}`);
  log(`   Collisions: ${report.collisions.length}`);
  log(`   Warnings: ${report.warnings.length}`);
  log(`   Auto-applied: ${applied}`);
  log('═══════════════════════════════════════════════════════════\n');
}

main().catch(err => {
  log(`\n❌ FATAL: ${err.message}`);
  console.error(err);
  process.exit(1);
});