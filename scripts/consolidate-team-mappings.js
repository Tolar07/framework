#!/usr/bin/env node
/**
 * consolidate-team-mappings.js — Analyze normalization collisions in team_map.py
 * and propose canonical mappings to resolve them.
 *
 * Reads the team-name-audit report, groups collisions by pattern, and outputs
 * a suggested consolidated SPORTYBET_TEAMS dictionary.
 */

const fs = require('fs');
const path = require('path');

const REPO_ROOT = 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';
const TEAM_MAP_PATH = path.join(REPO_ROOT, 'booking', 'team_map.py');
const REPORT_PATH = path.join(REPO_ROOT, 'data', 'team-name-audit', 'report-2026-08-21.json');

function readFile(filepath) {
  try {
    return fs.readFileSync(filepath, 'utf8');
  } catch (e) {
    console.error(`ERROR reading ${filepath}: ${e.message}`);
    return null;
  }
}

function writeFile(filepath, content) {
  try {
    fs.writeFileSync(filepath, content, 'utf8');
    return true;
  } catch (e) {
    console.error(`ERROR writing ${filepath}: ${e.message}`);
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

function extractSportyBetTeams(content) {
  const teams = {};
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

function analyzeCollisions(sportybetTeams) {
  const normToEntries = {};

  for (const [modelKey, sbName] of Object.entries(sportybetTeams)) {
    const normModel = normalize(modelKey);
    const normSb = normalize(sbName);

    if (!normToEntries[normModel]) normToEntries[normModel] = { modelKeys: [], sbNames: [] };
    normToEntries[normModel].modelKeys.push(modelKey);

    if (!normToEntries[normSb]) normToEntries[normSb] = { modelKeys: [], sbNames: [] };
    normToEntries[normSb].sbNames.push(sbName);
  }

  const collisions = {};
  for (const [norm, entries] of Object.entries(normToEntries)) {
    const allEntries = [...new Set([...entries.modelKeys, ...entries.sbNames])];
    if (allEntries.length > 1) {
      collisions[norm] = allEntries.sort();
    }
  }

  return collisions;
}

function categorizeCollisions(collisions) {
  const categories = {
    prefix_suffix: [],      // e.g., "Telstar" vs "SC Telstar"
    diacritic_variant: [],  // e.g., "Lillestrøm" vs "Lillestrom"
    duplicate_identity: [], // e.g., "Alkmaar" appears twice
    true_conflict: [],      // genuinely different clubs
    case_only: [],          // only case difference
    model_sb_conflict: []   // model key normalizes to same as different sb name
  };

  for (const [norm, entries] of Object.entries(collisions)) {
    // Check if it's just prefix/suffix variation of same club
    const hasModelPrefix = entries.some(e => e.startsWith('model:'));
    const hasSbPrefix = entries.some(e => e.startsWith('sb:'));

    // Check for diacritic variants
    const uniqueNames = entries.map(e => e.replace(/^(model|sb):/, ''));
    const diacriticPairs = [
      ['lillestroem', 'lillestrom'],
      ['fenerbahce', 'fenerbahce'],
      ['bodoe/glimt', 'bodo/glimt'],
      ['kobenhavn', 'københavn']
    ];

    let isDiacritic = false;
    for (const [a, b] of diacriticPairs) {
      if (uniqueNames.some(n => n.includes(a)) && uniqueNames.some(n => n.includes(b))) {
        isDiacritic = true;
        break;
      }
    }

    // Check for duplicate identity entries (same name, different prefix)
    const normalizedNames = uniqueNames.map(n => n);
    const hasDuplicateIdentity = new Set(normalizedNames).size < normalizedNames.length;

    // Check if it's prefix/suffix (SC, FC, etc.)
    let isPrefixSuffix = false;
    const prefixes = ['sc ', 'fc ', 'ac ', 'sk ', 'fk '];
    for (const name of uniqueNames) {
      for (const p of prefixes) {
        if (name.startsWith(p) && uniqueNames.some(n => n === name.slice(p.length))) {
          isPrefixSuffix = true;
          break;
        }
      }
      for (const p of prefixes.map(p => p.replace(' ', ''))) {
        if (name.endsWith(' ' + p) && uniqueNames.some(n => n === name.slice(0, -p.length - 1))) {
          isPrefixSuffix = true;
          break;
        }
      }
    }

    if (isDiacritic) {
      categories.diacritic_variant.push({ norm, entries });
    } else if (hasDuplicateIdentity) {
      categories.duplicate_identity.push({ norm, entries });
    } else if (isPrefixSuffix) {
      categories.prefix_suffix.push({ norm, entries });
    } else {
      // Check if model key conflicts with different sb name
      const modelKeys = entries.filter(e => e.startsWith('model:')).map(e => e.slice(6));
      const sbNames = entries.filter(e => e.startsWith('sb:')).map(e => e.slice(3));
      if (modelKeys.length > 0 && sbNames.length > 0 && !modelKeys.some(m => sbNames.includes(m))) {
        categories.model_sb_conflict.push({ norm, entries, modelKeys, sbNames });
      } else {
        categories.true_conflict.push({ norm, entries });
      }
    }
  }

  return categories;
}

function suggestCanonicalMapping(collisions, sportybetTeams) {
  const suggestions = {};

  for (const [norm, entries] of Object.entries(collisions)) {
    // Find the "canonical" model key (prefer football-data.co.uk style)
    const modelKeys = entries.filter(e => e.startsWith('model:')).map(e => e.slice(6));
    const sbNames = entries.filter(e => e.startsWith('sb:')).map(e => e.slice(3));

    // Heuristic: prefer shorter name without prefix/suffix as canonical
    let canonical = null;

    // First, try to find a model key that matches a sb name exactly (identity)
    const exactMatch = modelKeys.find(m => sbNames.includes(m));
    if (exactMatch) {
      canonical = exactMatch;
    } else if (modelKeys.length > 0) {
      // Prefer model key (football-data style is usually shorter)
      canonical = modelKeys.sort((a, b) => a.length - b.length)[0];
    } else if (sbNames.length > 0) {
      // No model key, pick shortest sb name
      canonical = sbNames.sort((a, b) => a.length - b.length)[0];
    }

    if (canonical) {
      suggestions[norm] = {
        canonical,
        allEntries: entries,
        action: 'consolidate',
        note: `Map all to "${canonical}"`
      };
    }
  }

  return suggestions;
}

function generateReport(categories, suggestions, sportybetTeams) {
  let output = '# Team Mapping Consolidation Analysis\n\n';
  output += `Generated: ${new Date().toISOString()}\n\n`;
  output += `Total collisions: ${Object.keys(suggestions).length}\n\n`;

  for (const [catName, items] of Object.entries(categories)) {
    if (items.length === 0) continue;
    output += `## ${catName.replace('_', ' ').toUpperCase()} (${items.length})\n\n`;

    for (const item of items) {
      const sugg = suggestions[item.norm];
      output += `### ${item.norm}\n`;
      output += `- Entries: ${item.entries.join(', ')}\n`;
      if (sugg) {
        output += `- **Suggested canonical**: \`${sugg.canonical}\`\n`;
        output += `- Action: ${sugg.note}\n`;
      }
      output += `\n`;
    }
  }

  return output;
}

function generateConsolidatedTeamMap(sportybetTeams, suggestions) {
  // Build a new dictionary with consolidated mappings
  const consolidated = {};
  const seenNormalized = new Set();

  // First pass: add all non-colliding entries
  for (const [modelKey, sbName] of Object.entries(sportybetTeams)) {
    const normModel = normalize(modelKey);
    const normSb = normalize(sbName);

    if (!suggestions[normModel] && !suggestions[normSb]) {
      if (!consolidated[modelKey]) {
        consolidated[modelKey] = sbName;
      }
    }
  }

  // Second pass: apply canonical mappings for collisions
  for (const [norm, sugg] of Object.entries(suggestions)) {
    const canonical = sugg.canonical;
    // Add the canonical mapping if not already present
    if (!consolidated[canonical]) {
      // Find what the SportyBet name should be for this canonical key
      let sbName = sportybetTeams[canonical] || canonical;
      consolidated[canonical] = sbName;
    }
  }

  return consolidated;
}

function formatAsPythonDict(teams) {
  let output = 'SPORTYBET_TEAMS: dict[str, str] = {\n';
  for (const [key, value] of Object.entries(teams).sort()) {
    output += `    "${key}": "${value}",\n`;
  }
  output += '}\n';
  return output;
}

async function main() {
  console.log('🔍 Loading team_map.py and audit report...');

  const teamMapContent = readFile(TEAM_MAP_PATH);
  const reportContent = readFile(REPORT_PATH);

  if (!teamMapContent || !reportContent) {
    console.error('Failed to load required files');
    process.exit(1);
  }

  const sportybetTeams = extractSportyBetTeams(teamMapContent);
  console.log(`Loaded ${Object.keys(sportybetTeams).length} team mappings`);

  const report = JSON.parse(reportContent);
  console.log(`Report shows ${report.collisions.length} collisions`);

  console.log('\n📊 Analyzing collisions...');
  const collisions = analyzeCollisions(sportybetTeams);
  console.log(`Found ${Object.keys(collisions).length} unique normalized collisions`);

  console.log('\n🏷️ Categorizing...');
  const categories = categorizeCollisions(collisions);

  for (const [cat, items] of Object.entries(categories)) {
    if (items.length > 0) {
      console.log(`  ${cat}: ${items.length}`);
    }
  }

  console.log('\n💡 Generating suggestions...');
  const suggestions = suggestCanonicalMapping(collisions, sportybetTeams);

  console.log('\n📝 Generating report...');
  const reportMd = generateReport(categories, suggestions, sportybetTeams);
  const reportPath = path.join(REPO_ROOT, 'data', 'team-name-audit', 'consolidation-report.md');
  writeFile(reportPath, reportMd);
  console.log(`Report written to: ${reportPath}`);

  console.log('\n🔧 Generating consolidated team map...');
  const consolidated = generateConsolidatedTeamMap(sportybetTeams, suggestions);
  const consolidatedMd = formatAsPythonDict(consolidated);
  const consolidatedPath = path.join(REPO_ROOT, 'data', 'team-name-audit', 'consolidated-team-map.py');
  writeFile(consolidatedPath, consolidatedMd);
  console.log(`Consolidated map written to: ${consolidatedPath}`);

  console.log('\n✅ Done!');
  console.log(`Original entries: ${Object.keys(sportybetTeams).length}`);
  console.log(`Consolidated entries: ${Object.keys(consolidated).length}`);
  console.log(`Reduction: ${Object.keys(sportybetTeams).length - Object.keys(consolidated).length}`);
}

main().catch(err => {
  console.error('FATAL:', err);
  process.exit(1);
});