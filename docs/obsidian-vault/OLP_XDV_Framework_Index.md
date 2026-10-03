# OLP XDV — Vault Navigation Index

**Canonical Vault:** `C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\docs\obsidian-vault\` (git-tracked, authoritative)
**Repo:** `C:\Users\Motunrayo\omniroute test` (live code — the source of truth)
**Note:** The deprecated mirror at `Documents/OLP_XDV_Vault/` was retired 2026-08-18. All unique content migrated here.
All paths below point at the real repo.

---

## Quick-Start Links (real repo paths)

| Area | Repo Path | Purpose |
|------|-----------|---------|
| **Core Agent** | `omniroute test/olp_xdv_agent/olp_xdv/` | Main package: orchestrator, models, markets, leagues |
| **Web App** | `…/olp_xdv_agent/olp_xdv/webapp/` | Single-tier feed page (Telegram board = web page) |
| **Brain / Persistence** | `…/olp_xdv_agent/olp_xdv/brain/` | SQLite store + migrations v1–v8, stats report |
| **CLI Entry** | `…/olp_xdv_agent/olp_xdv/agent_cli.py` | Query surface (`python -m olp_xdv.agent_cli "…"`) |
| **Config / Gates** | `…/olp_xdv_agent/olp_xdv/config.py` | Phase 3, capital gate, CLV thresholds |
| **Engine: Markets** | `…/olp_xdv_agent/olp_xdv/engine/markets.py` | Market IDs, ID405 override gate |
| **Engine: Leagues** | `…/olp_xdv_agent/olp_xdv/engine/leagues.py` | Dynamic league registry (ID401, from `config/leagues.json`) |
| **Tests** | `…/olp_xdv_agent/tests/` | Parity test: `webapp_feed_parity_test.py` |
| **Data / CSV** | `…/olp_xdv_agent/olp_xdv/data/` | Season CSVs (2526 completed, 2627 live) |
| **Design Reference** | `…/olp_xdv_agent/olp_xdv/design-reference/` | Mockup + pitch-night palette (proto.css) |

---

## Key Architecture Files (open first)

```text
omniroute test/olp_xdv_agent/olp_xdv/orchestrator.py       # Main loop: scan_one_league → acca builder
omniroute test/olp_xdv_agent/olp_xdv/webapp/render_v2.py   # Feed page renderer (the Telegram board)
omniroute test/olp_xdv_agent/olp_xdv/brain/store.py        # Brain SQLite: migrations, ledger, CLV
omniroute test/olp_xdv_agent/olp_xdv/config.py             # Phase, capital gate, thresholds
omniroute test/olp_xdv_agent/olp_xdv/engine/markets.py     # Market catalog + ID405 gate
omniroute test/olp_xdv_agent/olp_xdv/engine/leagues.py     # League registry (config/leagues.json)
omniroute test/olp_xdv_agent/olp_xdv/engine/acca.py        # Acca builder: EDGE selection, 12 markets
omniroute test/olp_xdv_agent/olp_xdv/booking/              # SportyBet: requests, Playwright, bridge
omniroute test/olp_xdv_agent/olp_xdv/conversation_auditor.py # Fabrication detection (FAB-001..004)
```

---

## Vault Files (canonical, git-tracked)

```text
docs/obsidian-vault/
├── OLP XDV.md                    # Entry point
├── Rules.md                      # All HR/ID rules + implementation refs
├── Decisions Log.md              # Dated Architect directives
├── Protected Constants.md        # Off-limits constants (ARCHITECT_SIGNOFF, CLV gate)
├── Agents.md                     # 16 agent roster + models/tools
├── Architecture.md               # Pipeline: SCAN → trigger → publish
├── Open Questions.md             # Unresolved items needing Architect
├── Loops.md                      # Autonomous agent loops
├── API Keys.md                   # Credential ref (sanitized, real in .env)
├── OLP_XDV_Framework_Index.md    # This file
├── Vault-Memory-Index.md         # Cross-ref: vault ↔ memory ↔ retired mirror
└── README.md                     # Vault overview
```

---

## Sync & Memory Integration

**Canonical Vault ↔ Agent Memory (bidirectional):**
- `vault-memory-sync.js` — runs on SessionEnd, auto-resolves conflicts (newest wins, backs up both)
- `memory-check.js` — HR54 check-in/out validates BOTH stores
- `sync-status.js` — SessionStart injection shows sync health

**Retired Mirror (Documents/OLP_XDV_Vault/):**
- Marked read-only, `DEPRECATED_NOTICE.md` in root
- No longer in `additionalDirectories` (removed from settings.json)
- Historical `Pipeline Runs/` preserved for reference only

---

## File Path Conventions (for Obsidian wikilinks)

| Source | WikiLink Prefix |
|--------|----------------|
| Canonical vault | `[[OLP XDV.md]]`, `[[Rules.md]]`, etc. |
| Agent memory | `[[olp-xdv-agent.md]]`, `[[safe-move-protocol.md]]`, etc. |
| Repo code | `file:///C:/Users/Motunrayo/omniroute%20test/olp_xdv_agent/olp_xdv/...` |

---

## Hook Wiring (from .claude/settings.json)

**SessionStart:**
1. `session-start.js` — context restore
2. `session-init.js` — safe-move + skill detect + obsidian-sync status
3. `memory-check.js check-in` — HR54 vault read + memory validation
4. `session-vault-inject.js` — HR58 vault digest to STDOUT
5. `sync-status.js` — sync health to STDOUT

**SessionEnd:**
1. `session-end.js` — persist session state
2. `evaluate-session.js` — continuous learning
3. `obsidian-sync.js push` — canonical → mirror (now retired, runs once more)
4. `audit-conversation.js` — fabrication detection
5. `archive-conversation.js` — transcript archive
6. `vault-memory-sync.js reconcile` — bidirectional vault↔memory sync
7. `memory-check.js check-out` — HR54 compliance log
