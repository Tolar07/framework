# OLP XDV — Team Briefing (All Agents)

> **Mandatory reading for every agent session** — native, plugin, gstack, and human-initiated.
> Loaded automatically by `.claude/scripts/hooks/session-init.js` on SessionStart.

---

## 1. Project Identity

| Field | Value |
|-------|-------|
| **Name** | OLP XDV — One League Prediction / Expected Value |
| **Type** | Football-betting calibration framework |
| **Phase** | **3 (Live Capital)** — Architect-deployed 2026-08-11 |
| **Status** | Daily pipeline running, board published to Telegram + web, no real stake routed by code |
| **Repo Root** | `C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\` (submodule on `elo-persistence`) |
| **Parent Repo** | `C:\Users\Motunrayo\omniroute test\` (git root, holds `.claude/`, `external/`, `claude-code-action/`) |
| **Key Config** | `.env` (ODDS_API_KEY, TELEGRAM_BOT_TOKEN, ARCHITECT_SIGNOFF=1) |
| **Python** | `py -3.12` (pinned), `PYTHONIOENCODING=utf-8` mandatory |
| **Daemons** | Daily Board (07:00), Health Monitor (2h), Run Watchdog, Dead Man's Switch, Data Steward (06:00/15:00), Telegram Poller (resident), Web Dashboard (resident :8088) |

---

## 2. Architecture Snapshot (2026-08-15)

| Layer | State |
|-------|-------|
| **Web = Telegram Board** | Single tier. `run_daily.py` builds `feed_text` once → persists `output/boards/telegram_<date>.txt` (byte-faithful) + stamps `feed_audit.jsonl`. Web reads `board_<date>.json` → `build_feed_payload()` → `render_v2.render_dashboard()`. |
| **Admin Tier** | **PAUSED** — `/admin*`, `/stats`, `/why`, `/api/admin/*`, `/api/trigger-board` → 404 (not 401/503). |
| **Auto-Feed = Auto-Publish** | No publish step, no Approve→Publish route. |
| **Booking-Codes Bug** | FIXED — no-booking-codes branch no longer unlinks `acca_<date>_codes.json`. |
| **Parity** | Pinned by `tests/webapp_feed_parity_test.py`. |

### Engine & Markets
- **Softness tiers GONE** — all 18 whitelisted leagues = ONE unified pool (`WHITELISTED_LEAGUES` in `engine/leagues.py`).
- **ID405 market gate OPEN** — `engine/markets.BLOCKED = {}` → all 5 markets deployable.
- **ID405 scope OVERRIDDEN at recommendation layer** (Architect directive 2026-08-11) — away wins may be **RECOMMENDED** (historical note: away measured −1.883%).
- **Multi-market edge selection** — each fixture evaluates 12 markets (9 canonical + 3 DC derivations); prices from same api-football payload.
- **Paid Odds API key = primary** (`ODDS_API_KEY` in `.env`, verified) — free backups: `ODDS_API_KEY_BACKUP` + `ODDS_API_KEY_TERTIARY`.
- **Publish gate** — `ARCHITECT_SIGNOFF=1` live; gate callout shows OVERRIDE (12/30 legs, mean CLV −1.631%).

### SportyBet Booking (Phase 2 Paper-Only)
- `booking/sportybet_client.py` — requests + BS4 (fixtures, odds from `__NEXT_DATA__`/DOM).
- `booking/sportybet_fixtures.py` — Playwright cache builder. CLI: `py -3.12 -m booking.sportybet_fixtures build [--leagues ...] [--days-ahead N]`. Writes `data/cache/sportybet/fixtures/{League}.json` (gitignored).
- `booking/bridge.py` — loads cached fixtures as `PipelineFixture`, attaches odds, verifies before paper-leg logging.
- **SPA click-through required** — football page → sidebar country → visible league → wait for match rows.
- **Sidebar naming ≠ OLP names** — LaLiga, Pro League (Belgium), Liga Portugal, Premiership (Scotland). Continental cups = "International Clubs".
- **HR35 hazard** — `team_map.resolve_team` at 0.6 threshold mis-mapped Coventry City→Exeter City, Alavés→Wolves. Fix: explicit self-mappings for promoted clubs + identity mappings for La Liga/Ligue 1.
- **Odds captured in CACHE, not live** — first `.market` cell → three `.m-outcome-odds` = H/D/A.
- **Booking codes CAN book** — `booking/booking_codes.py` drives acca payload into SportyBet betslip, clicks "Book Bet", reads code. Verified live: 10-leg acca across leagues = ONE slip (CODE TFS8TR).
- **Bright line**: never clicks Place Bet, never stakes. Code = pre-fill Architect pastes; they approve + stake.

### Design System
- **awesome-design-md** (73 brands) at `C:\Users\Motunrayo\Downloads\awesome-design-md-main\`.
- **Current palette** — pitch-night editorial pass (ratified 2026-08-12, supersedes Verge/Binance): canvas `#0e1a16`, surface `#142720`, hairline `#26392f`, ink `#f2efe4` / dim `#93ab9c` / faint `#5c7268`, **amber `#e8a33d`** (pick/deploy accent), **clay `#c05a4c`** (honest pending/missing).
- Type: Fraunces (display) / Inter (body) / IBM Plex Mono (micro-labels).
- Full spec: `docs/design-reference/OLP_XDV_PITCH_NIGHT_TOKEN_REFERENCE.md`.

---

## 3. Protected Constants — NEVER EDIT, NEVER SELF-APPROVE

| Constant / Logic | Location | Gatekeeper |
|-----------------|----------|------------|
| `ARCHITECT_SIGNOFF` flag + gating logic | `config.py`, `engine/publish_gate.py` | `code-reviewer-config` |
| CLV/legs publish gate (12/30 legs, mean CLV > 0) | `engine/publish_gate.py` | `code-reviewer-config` |
| Client-publish gating logic | `output/telegram_produce.py`, `webapp/schema.py` | `code-reviewer-config` |
| Capital-deployment logic / stake routing | `config.assert_paper_only()`, `booking/*` | `code-reviewer-config` |
| Softness-tier defaults (currently cancelled) | `engine/leagues.py`, `engine/softness.py` | `code-reviewer-config` |
| ID405 away-win exclusion scope (currently overridden) | `engine/markets.py`, `RATIFICATIONS.md` | `code-reviewer-config` |
| Calibration-log league-inclusion scope | `clv/calibration.py` | `code-reviewer-config` |

**Rule**: Any diff touching these is flagged by `code-reviewer-config` and stops. It becomes a named, explicit question back to the Architect — same shape as "I have killed engine softness" was. No agent consensus resolves it.

---

## 4. Team Roster — All Active Agents & Skills

### 4.1 Native OLP XDV Agents (`olp_xdv_agent/olp_xdv/.claude/agents/`)
| Agent | Role | When Invoked |
|-------|------|--------------|
| `planner` | Implementation planning | Complex features, refactoring |
| `architect` | System design (read-only for rule logic) | Architectural decisions on OLP rules |
| `backend-architect` | Full tools, generic build | Live-odds ingestion, services |
| `tdd-guide` | Test-driven development | New features, bug fixes |
| `code-reviewer` | General mandatory review | Every change, no exceptions |
| `code-reviewer-config` | Protected-constant gatekeeper | Diffs touching protected constants |
| `security-auditor` | Auth, data, external APIs | New odds feed, auth changes |
| `security-reviewer` | Retired → use security-auditor | — |
| `build-error-resolver` | Fix build failures | When build fails |
| `e2e-runner` | Playwright E2E testing | Critical user flows |
| `refactor-cleaner` | Dead code cleanup | Maintenance |
| `doc-updater` | Docs = code sync | After every merge |
| `conversation-auditor` | Transcript quality | Session audit |
| `league-steward` | League registry ops | Dynamic league registry |
| `fixtures-checker` | Fixtures integrity | Cache validation |
| `session-init` | Session boot protocol | Auto-run on SessionStart |
| **Pipeline agents (10)** | Production pipeline | `olp-xdv-01-ingestion` → `olp-xdv-10-ceo` |

### 4.2 Plugin Agents (Parent Repo `.claude/agents/`)
| Agent | Role | Context |
|-------|------|---------|
| `olp-xdv-specialist` | Full-stack OLP XDV specialist | Telegram/daemon/web, booking, feed parity, daily pipeline |
| `productivity-assistant` | Files, web forms (Playwright), Outlook SMTP | General productivity, form fill, email draft→confirm→send |

### 4.3 Plugin Skills (Parent Repo `.claude/skills/`)
| Skill | Purpose |
|-------|---------|
| `coding-standards`, `backend-patterns`, `frontend-patterns` | Universal code patterns |
| `continuous-learning`, `strategic-compact` | Session learning, context compression |
| `eval-harness`, `verification-loop` | Evaluation, self-check |
| `security-review` | Security audit skill |
| `tdd-workflow` | TDD discipline |
| `emil-design-eng`, `review-animations`, `improve-animations`, `find-animation-opportunities` | Motion-craft (Emil Kowalski) |
| `web-design-guidelines`, `brandkit`, `image-to-code` | Vercel guidelines, brand voice, screenshot→code |
| `impeccable`, `taste-skill`, `soft-skill`, `minimalist-skill`, `brutalist-skill`, `redesign-skill`, `stitch-skill`, `output-skill`, `image-to-code-skill`, `imagegen-frontend-web`, `imagegen-frontend-mobile`, `gpt-tasteskill` | Frontend design-quality pack (presentation only) |
| `sports-football-data`, `sports-betting`, `sports-markets`, `sports-polymarket` | Independent sports data inputs (honest-edge: verify-only) |
| `olp-xdv` | Read-only brain/CLV/board query surface |
| `clickhouse-io`, `extract-design-system`, `project-guidelines-example` | Specialty |

### 4.4 GStack Skills (Global `~/.claude/skills/gstack/`, slash commands)
| Slash Command | Role |
|---------------|------|
| `/office-hours` | YC Office Hours — reframe product idea |
| `/spec` | Turn vague intent → executable spec (5 phases, files GitHub issue) |
| `/plan-ceo-review` | CEO-level review: find 10-star product |
| `/plan-eng-review` | Eng manager review: lock architecture, data flow, edge cases, tests |
| `/plan-design-review` | Designer review: rate dimensions 0-10 |
| `/plan-devex-review` | DX review: TTHW, friction, persona traces |
| `/autoplan` | One command runs CEO → design → eng → DX |
| `/design-consultation` | Build complete design system from scratch |
| `/review` | Pre-landing PR review — finds bugs CI misses |
| `/codex` | Second opinion via OpenAI Codex |
| `/investigate` | Systematic root-cause debugging |
| `/design-review` | Live-site visual audit + fix loop |
| `/design-shotgun` | Multiple AI design variants + comparison board |
| `/design-html` | Production-quality Pretext HTML/CSS |
| `/devex-review` | Live DX audit (measured TTHW) |
| `/qa` | Real browser QA — finds bugs, fixes, re-verifies |
| `/qa-only` | Report-only QA |
| `/scrape` | Pull data from web page (prototype → codified) |
| `/skillify` | Codify successful `/scrape` into permanent browser-skill |
| `/ship` | Run tests, review, push, open PR (workspace-aware queue) |
| `/land-and-deploy` | Merge PR, wait CI+deploy, verify prod health |
| `/canary` | Post-deploy monitoring loop |
| `/landing-report` | Read-only ship queue dashboard |
| `/document-release` | Update all docs to match shipped code |
| `/document-generate` | Diataxis docs from code |
| `/setup-deploy` | One-time deploy config detection |
| `/gstack-upgrade` | Update gstack to latest |
| `/context-save` | Save working context (git state, decisions, remaining work) |
| `/context-restore` | Resume from saved context |
| `/learn` | Manage gstack learning across sessions |
| `/retro` | Weekly retro with shipping streaks |
| `/health` | Code quality dashboard (type check, linter, tests, dead code) |
| `/benchmark` | Performance regression (page load, CWV) |
| `/benchmark-models` | Cross-model benchmark (Claude, GPT, Gemini) |
| `/cso` | OWASP Top 10 + STRIDE security audit |
| `/setup-gbrain` | Set up gbrain for cross-machine session memory |
| `/sync-gbrain` | Keep gbrain current with repo code |
| `/browse` | Headless browser (~100ms/command) |
| `/open-gstack-browser` | Visible GStack Browser with sidebar + stealth |
| `/setup-browser-cookies` | Import cookies from real browser |
| `/pair-agent` | Pair remote AI agent (OpenClaw, Codex) with browser |
| `/freeze` / `/unfreeze` | Restrict/clear file edit boundary |

---

## 5. Cross-Team Dispatch Protocol

### 5.1 Communication Channels (Git-Only)
Sessions cannot message each other directly. All coordination happens via:

| Channel | Purpose |
|---------|---------|
| **Git commits** | Primary sync — conventional commits with session attribution |
| **GitHub Issues** | `/spec` files issues; `/ship` closes on merge |
| **PR Reviews** | `code-reviewer` + `/review` + `code-reviewer-config` |
| **Protected-Constant Flags** | `code-reviewer-config` blocks merge → explicit Architect question |
| **RATIFICATIONS.md** | Append-only Architect decisions (never edited by agents) |
| **Memory Notes** | `.claude/memory/*.md` — distilled facts, cross-session |
| **Obsidian Vault** | `C:\Users\Motunrayo\Documents\OLP_XDV_Vault\` — canonical docs, synced via hooks |

### 5.2 Escalation Paths
```
Implementation Agent
    ↓ (tests written, feature ready)
code-reviewer (mandatory)
    ↓
code-reviewer-config (if protected constants touched)
    ↓ (blocked)
Architect (explicit decision, recorded in RATIFICATIONS.md)
    ↓
doc-updater (syncs docs to decision)
```

### 5.3 Agent-to-Agent Handoff Rules
1. **Never duplicate work** — check `git status --short` + `git log --oneline -5` first (Safe-Move).
2. **Combine safe states** — if other session staged changes, use `git commit --only <paths>` to avoid sweeping.
3. **Tag handoffs** — commit message must state: `feat(scope): <what> — <from-agent> → <to-agent>`.
4. **Skill vs Agent** — use **skills** for repeatable workflows (`/qa`, `/review`), **agents** for open-ended reasoning (`planner`, `architect`).
5. **GStack for product/release ops** — `/spec`, `/ship`, `/qa`, `/review`, `/cso` are the release-engineering layer.
6. **Native agents for OLP domain logic** — pipeline, engine, booking, CLV, board rendering.

---

## 6. Safe-Move Protocol (Every Session)

```bash
# 1. Check what the other session left
git status --short
git log --oneline -5

# 2. If HEAD advanced or tree changed:
git diff              # or git show <new-head>
# Preserve their work — combine, don't overwrite

# 3. Commit combined state BEFORE new edits
git commit --only <paths...> -m 'reconcile: combine session work — <your-note>'
# NEVER bare 'git commit' — sweeps other session's staged files

# 4. Make your edits

# 5. Re-check after finishing
git status --short
```

---

## 7. Key Files to Read on Startup

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This repo's operating rules (this file's parent) |
| `ARCHITECTURE.md` | System architecture detail |
| `RATIFICATIONS.md` | Append-only Architect decisions |
| `PROJECT_STATUS.md` | Current sprint state |
| `TEAM_BRIEFING.md` | You are here |
| `DISPATCH_PROTOCOL.md` | Cross-team communication rules |
| `config.py` | PHASE, ARCHITECT_SIGNOFF, whitelist |
| `engine/markets.py` | `BLOCKED = {}`, market list |
| `engine/publish_gate.py` | CLV/legs gate logic |
| `output/telegram_produce.py` | Board production |
| `webapp/render_v2.py` | Web feed rendering |
| `booking/bridge.py` | SportyBet cache → pipeline |

---

## 8. Quick Reference — Common Commands

```bash
# Daily pipeline (runs at 07:00)
py -3.12 run_daily.py

# Health monitor (runs every 2h)
py -3.12 monitor/health_monitor.py

# Data steward (06:00 + 15:00)
py -3.12 steward/run_steward.py

# Web dashboard (resident)
py -3.12 webapp/server.py  # :8088

# Tests
py -3.12 tests/webapp_feed_parity_test.py
py -3.12 tests/<name>.py

# SportyBet cache build
py -3.12 -m booking.sportybet_fixtures build --leagues "Premier League,LaLiga" --days-ahead 3

# OLP-XDV skill query (read-only)
python -m olp_xdv <query>

# GStack skills (slash commands)
/office-hours
/spec
/qa https://staging.example.com
/review
/ship
/cso
```

---

## 9. Remember: The CLV Number Is the Truth

The mean CLV is the **only** metric that tells the Architect whether this framework works. Every protected constant exists to keep that number trustworthy. If you're unsure whether a change touches a protected constant, **stop and ask** — the cost of a false positive is a blocked PR; the cost of a false negative is a corrupted live test.

> **When in doubt, read `CLAUDE.md` section "PROTECTED — NO AGENT MAY EDIT OR SELF-APPROVE THESE, EVER" again.**

---

*Generated by session-init hook. Updated each session from git state and vault sync.*