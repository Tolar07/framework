const fs = require("fs");
const path = require("path");

function fileHash(filepath) {
  try {
    const content = fs.readFileSync(filepath, "utf8");
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      hash = ((hash << 5) - hash) + content.charCodeAt(i);
      hash |= 0;
    }
    return hash.toString(16);
  } catch {
    return null;
  }
}

const VAULT_ROOT = "docs/obsidian-vault";
const MEMORY_ROOT = "C:/Users/Motunrayo/.claude/projects/C--Users-Motunrayo-omniroute-test/memory";

const files = [
  { vault: "Agents.md", memory: "olp-xdv-agent.md" },
  { vault: "Open Questions.md", memory: "open-questions.md" },
  { vault: "Rules.md", memory: "rules.md" },
];

files.forEach(f => {
  const vaultPath = path.join(VAULT_ROOT, f.vault);
  const memoryPath = path.join(MEMORY_ROOT, f.memory);
  console.log(f.vault, ": vault=", fileHash(vaultPath), ", memory=", fileHash(memoryPath), ", equal=", fileHash(vaultPath) === fileHash(memoryPath));
});