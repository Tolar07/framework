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
const CLAUDE_PROJECTS_DIR = path.join(process.env.USERPROFILE || process.env.HOME || '', '.claude', 'projects', 'C--Users-Motunrayo-omniroute-test');

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

function findTranscriptBySessionId(sessionId) {
  // First check CLAUDE_TRANSCRIPT_PATH env var
  if (process.env.CLAUDE_TRANSCRIPT_PATH && fs.existsSync(process.env.CLAUDE_TRANSCRIPT_PATH)) {
    return process.env.CLAUDE_TRANSCRIPT_PATH;
  }

  // Fallback: look in the project directory for a transcript with this session ID
  if (fs.existsSync(CLAUDE_PROJECTS_DIR)) {
    const files = fs.readdirSync(CLAUDE_PROJECTS_DIR).filter(f => f.endsWith('.jsonl'));
    for (const file of files) {
      const filepath = path.join(CLAUDE_PROJECTS_DIR, file);
      try {
        const content = fs.readFileSync(filepath, 'utf8');
        const lines = content.split('\n').filter(l => l.trim());
        // Check first few lines for sessionId
        for (const line of lines.slice(0, 10)) {
          try {
            const entry = JSON.parse(line);
            if (entry.sessionId === sessionId) {
              return filepath;
            }
          } catch (e) {
            // Skip non-JSON lines
          }
        }
      } catch (e) {
        // Skip unreadable files
      }
    }
  }

  return null;
}

async function main() {
  // Get transcript path from environment (set by Claude Code) or find by session ID
  const sessionId = process.env.CLAUDE_SESSION_ID;
  let transcriptPath = process.env.CLAUDE_TRANSCRIPT_PATH;

  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    if (sessionId) {
      log(`Searching for transcript with session ID: ${sessionId}`);
      transcriptPath = findTranscriptBySessionId(sessionId);
    }
  }

  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    log('No transcript path found or file not found, skipping archive');
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