#!/usr/bin/env node
/**
 * Archive Conversation Hook - Copies session transcript to memory/conversations/
 *
 * Runs on SessionEnd. Archives the full conversation transcript
 * for cross-session knowledge preservation.
 *
 * Cross-platform (Windows, macOS, Linux)
 */

const fs = require('fs');
const path = require('path');

const REPO_ROOT = process.env.OLP_XDV_ROOT
  || 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv';

const CONVERSATIONS_DIR = path.join(REPO_ROOT, 'memory', 'conversations');

function log(msg) {
  console.error(`[ArchiveConversation] ${msg}`);
}

function getTimestamp() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}-${minutes}-${seconds}`;
}

async function main() {
  // Get transcript path from environment (set by Claude Code)
  const transcriptPath = process.env.CLAUDE_TRANSCRIPT_PATH;

  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    log('No transcript path or file not found, skipping archive');
    process.exit(0);
  }

  try {
    // Ensure conversations directory exists
    if (!fs.existsSync(CONVERSATIONS_DIR)) {
      fs.mkdirSync(CONVERSATIONS_DIR, { recursive: true });
    }

    // Read transcript
    const transcriptContent = fs.readFileSync(transcriptPath, 'utf8');

    // Generate archive filename with timestamp
    const timestamp = getTimestamp();
    const archiveName = `conversation_${timestamp}.jsonl`;
    const archivePath = path.join(CONVERSATIONS_DIR, archiveName);

    // Write archive
    fs.writeFileSync(archivePath, transcriptContent, 'utf8');

    // Also create a summary markdown file for easy reading
    const summaryName = `conversation_${timestamp}.md`;
    const summaryPath = path.join(CONVERSATIONS_DIR, summaryName);
    const summary = `# Conversation Archive - ${timestamp.replace(/T/, ' ').replace(/-/g, ':')}

**Source:** \`${transcriptPath}\`
**Archived:** ${new Date().toISOString()}

\`\`\`json
${transcriptContent.slice(0, 2000)}${transcriptContent.length > 2000 ? '...' : ''}
\`\`\`

---
*Full transcript: [${archiveName}](${archiveName})*
`;
    fs.writeFileSync(summaryPath, summary, 'utf8');

    log(`Archived conversation to ${archivePath}`);
    log(`Created summary at ${summaryPath}`);

  } catch (e) {
    log(`Error archiving conversation: ${e.message}`);
  }

  process.exit(0);
}

main();