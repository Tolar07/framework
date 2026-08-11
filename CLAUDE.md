# OLP XDV — working protocol for Claude sessions

---

## OPERATING RULES — OLP XDV Operating Rules for All Agents

This file governs every agent working in this repo — plugin agents (planner, architect, tdd-guide, code-reviewer, security-reviewer, build-error-resolver, e2e-runner, refactor-cleaner, doc-updater) and chusri agents (backend-architect, frontend-developer, ui-ux-designer, security-auditor, code-reviewer-config, devops-troubleshooter, database-admin). Read this file completely before touching any code.

### MANDATORY: READ BEFORE YOU WORK

No agent may write, edit, or run anything in this repo until it has read and can demonstrate understanding of:

1. **This file, in full** — the rules and the protected-constants list below.
2. **The full HR/ID rule set** — every hard rule and numbered protocol, current status (active/superseded/shelved), and where each is implemented in code.
3. **The current framework architecture** — the SCAN → trigger production → publish pipeline, the admin dashboard, the CLV/calibration logging, the Telegram/client board output.
4. **Recent Architect decisions on record**, specifically:
   - Softness/deploy-eligibility gate (Tier A/B league restriction, FIX 3) was cancelled 11 Aug 2026 — the market is intentionally open to all leagues now. This was a deliberate, explicit discipline reduction, not a bug to be "fixed" by re-adding the restriction.
   - ID405 scope was **overridden 2026-08-11** (Architect directive, named): "ID four zero five should be ignored. All markets remains open." Away wins may now be **recommended**, not just shown — the recommendation-layer exclusions were removed (RATIFICATIONS 2026-08-11). The market gate was already open (`BLOCKED = {}`). The `blocked()` structural backstop stays so a future gate can be re-engaged by adding keys back. Calibration-log league scope remains unchanged.
5. **The `olp-xdv` skill** (read-only brain/CLV/board query surface) — this is the correct way to check current gate status, legs logged, and mean CLV. Don't query raw tables directly if this surface covers it.

If an agent's task touches a part of the system it hasn't read about, it stops and reads that part first. "I didn't know that mattered" is not an acceptable reason for touching a protected constant — see below.

### HOW THE TEAM WORKS TOGETHER

1. `planner` scopes the task — steps, dependencies, risk.
2. `architect` (read-only, for anything touching OLP XDV's own rule logic) or `backend-architect` (full tools, for generic build work like the live-odds ingestion service) designs the approach.
3. Implementation agents build it, `tdd-guide`-style — tests first.
4. `code-reviewer` reviews every change, no exceptions.
5. `code-reviewer-config` is the specific gatekeeper for anything touching a protected constant (see below) — production-outage prevention and magic-number skepticism is exactly its job.
6. `security-auditor` reviews anything touching auth, data handling, or external APIs (e.g. a new odds feed).
7. `doc-updater` keeps this file and the master documentation current after every merge — the docs must always match the actual code, not the other way around.

Duplicate-role note: `code-reviewer` and `code-reviewer-config` are not run redundantly — `code-reviewer` is the general mandatory pass, `code-reviewer-config` is the specific check for protected-constant diffs. `security-reviewer` (plugin) is retired in favor of `security-auditor` (chusri, opus) for this repo.

### WHAT AGENTS CAN DO FREELY

Everything that isn't on the protected list below: build the live-odds ingestion path, fix bugs, refactor, write tests, update docs, improve the pipeline, run the operations loop autonomously, propose architecture changes. Move fast here.

### PROTECTED — NO AGENT MAY EDIT OR SELF-APPROVE THESE, EVER

- `ARCHITECT_SIGNOFF` flag and any logic gating it
- The CLV/legs-required publish gate (currently 12/30 legs, mean CLV must be positive) — the threshold values, the count logic, or what it blocks
- Client-publish gating logic generally
- Capital-deployment logic or anything that could route real stake
- Softness-tier defaults (currently open/cancelled — do not silently restore Tier A/B restriction)
- ID405 (away-win exclusion) scope — currently **overridden** (2026-08-11 Architect directive: all markets deployable, away may be recommended; recorded in RATIFICATIONS.md). Do not silently restore the exclusion — the override is the Architect's, not inferred.
- Calibration-log league-inclusion scope

Any diff touching these is flagged by `code-reviewer-config` and stops. It does not get merged, auto-approved, or resolved by agent consensus. It becomes a named, explicit question back to the Architect — same shape as "I have killed engine softness" was: stated plainly, on the record, decided by the Architect, not inferred by the team.

### WHY THIS MATTERS

The CLV number is the only thing that tells the Architect whether this framework actually works. If agents can edit how it's measured or gated while doing unrelated "improvement" work, that number stops being trustworthy — which defeats the entire purpose of going live to let the framework learn. Protecting these constants is not bureaucracy; it's the mechanism that makes the live test meaningful.

---

This repo is worked by **more than one Claude session at a time**. Sessions
cannot message each other. **Git is the only sync mechanism** — the other
session edits the same files and commits independently, and it may do so
while you are mid-task.

## The Safe Move — the DEFAULT opening move for EVERY task

Applies to **everything** done in this repo (board/Telegram output, engine,
tests, config, docs, anything) — not just board work. Treat it as the standing
way of working in a two-session tree, not a special case:

1. `git status --short` — see what is dirty and whether the other session left
   changes.
2. `git log --oneline -5` — see whether the other session committed since your
   last check.
3. If HEAD advanced or the working tree changed since your last check:
   - inspect the diff (`git diff`, `git show <new-head>`),
   - **preserve the other session's work** — combine it with yours rather than
     overwriting it,
   - commit the combined safe state **before** making new edits.
4. Only then edit.
5. Re-check `git status` after finishing — the other session may have written
   again; combine and commit rather than leaving a divergent tree.

## Combining safe states

- Never discard the other session's committed work or uncommitted changes.
- A reconciliation commit that captures BOTH sessions' changes is the expected
  way to sync (see `b506631` for the pattern).
- If the working tree has changes you did not make, treat them as the other
  session's in-flight work: check, combine, commit, then proceed.
- After combining, re-check `git status` before trusting the tree is stable —
  the other session may still be writing.

## Commit conventions

- Commit with a clear message stating which session contributed what.
- End every commit message with:
  `Co-Authored-By: Claude <noreply@anthropic.com>`

## Architecture context

Board format, the Brain, caching, the WhatsApp copy channel, and daemon wiring
are recorded in the Claude memory note `olp-xdv-agent`. Board decisions are
ratified in `RATIFICATIONS.md` (append-only). The honest-edge statement and the
capital block (Phase 2 = paper only, zero capital) are Architect bright lines —
never bypassed.

## everything-claude-code integration

This repo uses the **everything-claude-code** plugin (installed at `.claude/` from
`C:\Users\Motunrayo\Downloads\everything-claude-code-main\everything-claude-code-main`).
All agents, skills, commands, rules, hooks, and contexts are available in every session.Key components now available:
- **Agents**: planner, architect, tdd-guide, code-reviewer, security-reviewer, build-error-resolver, e2e-runner, refactor-cleaner, doc-updater
- **Skills**: coding-standards, backend-patterns, frontend-patterns, continuous-learning, strategic-compact, tdd-workflow, security-review, eval-harness, verification-loop
- **Motion-craft skills** (Emil Kowalski pack, added 2026-08-10): `emil-design-eng`, `review-animations`, `improve-animations`, `find-animation-opportunities`. Run `improve-animations` for a prioritized motion audit → plans in `plans/`; `review-animations` for a strict diff pass on motion. Motion is decor, never data-hiding (honest-edge).
- **Design skills** (added 2026-08-11, presentation-layer only): `web-design-guidelines` (Vercel Web Interface Guidelines review — audits UI/accessibility), `brandkit` (taste-skill — brand voice/style), `image-to-code` (taste-skill — screenshot → code), `ui-ux-pro-max` (wrapper → 24MB CLI toolkit at `external/design-skills/ui-ux-pro-max-skill`), `extract-design-system` (wrapper → token-extraction tool at `external/design-skills/extract-design-system`). All are **reference/tooling for UI work only** — they never touch prediction logic, and they never silently swap the ratified Binance palette (a design-language change needs Architect ratification).
- **Commands**: /plan, /tdd, /e2e, /code-review, /build-fix, /refactor-clean, /learn, /checkpoint, /verify, /setup-pm
- **Rules**: security, coding-style, testing, git-workflow, agents, performance, patterns, hooks
- **Hooks**: tmux reminders, git push review, doc blocking, PR logging, prettier, TypeScript check, console.log audit, session persistence, continuous learning extraction
- **Contexts**: dev, review, research modes for dynamic system prompt injection

**Use these proactively** — e.g., `tdd-guide` for new features, `code-reviewer` after writing code, `planner` for complex tasks.

## Design reference — awesome-design-md (standing)

Dashboard/UI styling uses **awesome-design-md** — a design-token library at
`C:\Users\Motunrayo\Downloads\awesome-design-md-main\awesome-design-md-main`
(`design-md/<brand>/DESIGN.md` for 73 brands). The current web dashboard
(`webapp/static/css/proto.css`) is a **Binance DESIGN.md token pass** (ratified
2026-08-10): canvas dark `#0b0e11`, surface `#1e2329`, hairline `#2b3139`,
amber primary `#FCD535`, trading up `#0ecb81` / down `#f6465d`.

When changing or extending the web UI, keep the Binance tokens in `proto.css`
(they are the ratified palette). If a new design language is ever chosen, pull
it from the awesome-design-md collection and ratify the swap — tokens are a
skin, never a reason to hide data (honest-edge + data-density stay intact).

## Sports-data skills (installed 2026-08-11)

Four skills from the **machina-sports/sports-skills** repo are installed at
`.claude/skills/sports-*` (source clone at `external/sports-skills`, sibling of
`olp_xdv_agent/`). They use the `sports-skills` Python package — installed for
`py -3.12` and the default `python` — invoked as `python -m sports_skills <skill>
<command>` (the `sports-skills` console script is NOT on PATH in this shell).

| Skill | What it adds to OLP XDV |
|-------|-------------------------|
| `sports-football-data` | ESPN scores/standings/schedules for **all leagues** (independent of TheSportsDB — closes F2 cross-source gaps), H2H via football-data.co.uk (11 European leagues), ClubElo team strength + short-horizon match forecasts, Transfermarkt player values. Zero API keys. |
| `sports-betting` | Pure-compute odds math: convert, de-vig, find_edge, evaluate_bet, Kelly, arbitrage, parlay, line_movement classification. No network. Useful to sanity-check CLV/consensus outputs. |
| `sports-markets` | Orchestrates ESPN schedules with Kalshi + Polymarket prediction markets — odds comparison, entity search, arbitrage detection across venues. |
| `sports-polymarket` | Read-only Polymarket prediction-market odds/order books for EPL, UCL, La Liga etc. — a genuine second opinion on the Odds API's moneyline. |

Quick check a skill is live:
```bash
py -3.12 -m sports_skills football get_competitions
```

**Honest-edge:** these are independent *inputs* to verification, not an
automatic override — anything they say still passes through the publish gate
(ID403 multi-factor verify) like any other source. xG remains top-5-only
(Understat limitation, same as the existing `data/xg_source.py`).

## External reference repos (clone, not integrated)

Cloned into `external/` at the workspace root (sibling of `olp_xdv_agent/`),
available for study — **not** wired into the pipeline:

- `external/sports-skills` — the source of the installed skills above (upstream
  for `git pull` updates).
- `external/sports-betting-claude` — methodology skills: edge detection
  (de-vig → implied prob → Kelly → anti-bias checklist), bankroll management,
  performance/ROI tracking, sport-specific NFL/NBA/MLB/NHL/NCAA. The
  `skills/shared/anti-bias-checklist.md` is a useful red-team pass against the
  brain's own narratives. Mostly US-sports; football coverage is thin.
- `external/betting-odds-tracker` — real-time line-movement snapshots across
  books + reverse-line-movement (sharp money) flags via The Odds API + SHIPP.
  Requires those two API keys; a candidate future *input feeder* if sharp-money
  signalling is ever ratified, not a current data source.
- `external/betting-app-skill` — Next.js14 + Supabase pari-mutuel app patterns
  (atomic `place_bet`, RLS, force-dynamic anti-stale-financials). The webapp is
  stdlib-only Python, so only the *patterns* transfer, not the code.
- `external/design-skills/` — six design-skill sources (emilkowalski `skills/`,
  `ui-ux-pro-max-skill`, vercel `agent-skills` (web-design-guidelines),
  `taste-skill` (brandkit + image-to-code), `extract-design-system`). Emils' pack
  is copied into `.claude/skills/` (motion-craft); three single-file skills are
  copied (web-design-guidelines, brandkit, image-to-code); the two heavy tools
  (ui-ux-pro-max 24MB, extract-design-system) are thin wrappers pointing at the
  clone. Presentation-layer only — no prediction-logic involvement.
- `external/football-prediction/` — four **reference-only** repos: `penaltyblog`
  (read for scrapers + backtest utils; do NOT adopt its Cython model as our
  engine — ours stays hand-rolled/auditable), `soccerstan` + `Dixon-Coles-Football-Predictor`
  (independent cross-checks of our DC math), `MatchOutcomeAI` (read for its
  calibration-vs-bookmaker-odds approach vs our MES/EV). None are merged.
- `external/nba-patterns/` — `NBA_Betting` + `nba-prediction` (architecture
  patterns for daily scrape→predict→deploy only; NBA markets are banned in our
  hard rules, so the prediction models are never borrowed).
- `external/low-priority/soccer_xg` — filed away; only relevant once/if we get
  real event-level data (we don't, per the xG coverage conclusion).
