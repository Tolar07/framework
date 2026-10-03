# OLP XDV — COMPLETE FUNCTION MAP (final iteration before sign-off)
### Every button, every trigger, every call-to-action, both dashboards — for Claude Code

**⚠ Same reconciliation notice as the earlier design report: Claude Code has upgraded since parts of this process began. Compare against current code, keep what's already better, flag conflicts rather than silently overwriting.**

**Architecture requirement, stated once here so it isn't missed:** admin's AI Analyst chat must call a REAL backend — the same analysis Claude Code itself would do — not a placeholder response. The Architect explicitly does not want to open a terminal/Claude Code session to get an answer; the web chat IS the interface to that analysis. Wire it to an actual endpoint that runs real queries against the live board/CLV/backtest data, using the Claude API with full status context, same as the Telegram bot's chat feature.

---

## CLIENT DASHBOARD

| Element | Function |
|---|---|
| Logo (top-left) | Returns to home / Call tab |
| Bottom tab: **Call** | Shows today's (or selected day's) singles + the one combined accumulator, each with SportyBet booking code |
| Bottom tab: **Scan** | Full wide board, grouped by league, collapsible groups, date-filterable |
| Bottom tab: **Analyst** | Read-only info panels (no chat) — see below |
| **Call — single pick card** | Tap: expands to full market breakdown for that fixture (all markets, not just the headlined pick) |
| **Call — booking code "Copy" button** | Copies the SportyBet booking code to clipboard; Architect pastes into SportyBet app to load the pre-built slip. Does NOT place a bet. |
| **Call — accumulator card** | Shows combined probability across all bundled singles + its own separate booking code + copy button |
| **Scan — date pills** | Filter the whole scan to that date. Client should be able to view **today, tomorrow, and the day after** — matching admin's 2-day-ahead production capability |
| **Scan — league group header** | Tap: expand/collapse that league's fixture list |
| **Scan — search box** | Live-filters visible fixtures by team/league name as you type |
| **Scan — fixture row** | Shows fixture + labeled pick (e.g. "Nijmegen to win — 66%") on the row itself; tap expands to full market detail, same pattern as Call |
| **Scan — live match state** (not yet in prototype, confirmed requirement) | If kickoff hasn't happened: show kickoff time instead of a score. Once kicked off: replace with live score in real time, so client can self-verify results as they happen. Needs a live-score data source wired in — flag to Architect which source, since this isn't yet confirmed. |
| **Analyst — "Today's board" panel** | Tap: expands to show singles count, acca count, leagues scanned, no-data count |
| **Analyst — "Track record" panel** | Tap: expands to show Phase, CLV legs logged, honest edge status |
| **Analyst — "Explain a pick" panel** | Tap: expands to explain that fixture detail panels ARE the explanation — points user back to Call/Scan |

---

## ADMIN DASHBOARD

| Element | Function |
|---|---|
| Search bar (top) | Filters the dense grid by fixture/team/league name, live as typed |
| **Date selector** (dropdown next to Trigger button) | Choose which date to produce: **Today / Tomorrow / Day after** — a real date picker, not an auto-detected "next matchday" guess |
| **Trigger Production button** | Runs the orchestrator on-demand for the SELECTED date. Shows loading state, disables itself during run (prevents double-trigger), updates the grid and stats in place when done. Backend: `POST /api/trigger-board?date=YYYY-MM-DD` |
| **Stat pill: "N scanned"** | Click: opens/filters to the full list of every scanned fixture |
| **Stat pill: "N eligible"** | Click: filters to only the deploy-eligible (Tier A/B) fixtures |
| **Stat pill: "CLV gate"** | Click: opens the Phase 3 gate detail — legs logged, mean CLV, sign-off status |
| League filter chips (all 15) | Each filters the grid to that league; "All" resets |
| Market/tier/status filter chips | Same pattern — filter the grid, don't hide from the list |
| Dense grid row | Click: expands to full detail — every market PLUS Model Internals (Elo second opinion, divergence %, MES verdict) |
| Sidebar: Search/Filter, The Call, The Scan, Data Flags, Verified — Yesterday | Each switches the main panel to that section |
| **Approve → Publish to Client button** | Hard-gated in code (mirrors capital gate pattern) until Phase 3 CLV gate is genuinely met. Shows loading → success confirmation with timestamp. Backend: `POST /api/publish-board` |
| **AI Analyst chat (admin, full functionality)** | Real backend call — see architecture requirement above. Must be able to answer questions about the live board, explain divergences, reference the CLV backtest, without the Architect needing to open Claude Code directly |
| **Error/rejection log** (confirmed requirement, not yet in prototype) | Admin needs visibility into failed/rejected attempts, not just successful output — flag to Claude Code as a required panel, not optional |
| **Edit-before-publish** (confirmed requirement, not yet in prototype) | Admin should be able to adjust the board before publishing, not just approve/reject as one binary action — flag as required, exact editing UI still to be designed |

---

## STILL OPEN — DO NOT BUILD BLIND, ASK THE ARCHITECT

1. **Hosting/reliability conflict** (own machine vs. guaranteed "every time" execution) — unresolved from the previous report, still needs an explicit Architect decision.
2. **SportyBet booking code generation** — needs verification: does SportyBet expose any way to generate a code from selections programmatically, or is it manual-only inside their app?
3. **Live score data source** — not yet chosen. Needs a real-time score feed distinct from the historical/fixtures sources already wired in.
4. **Error/rejection log and edit-before-publish UI** — requirements confirmed, exact interaction design not yet built. Propose a design and confirm with the Architect before building, rather than guessing the layout.

---

## SIGN-OFF

This is presented as the final iteration for Architect review. Once confirmed, Claude Code should treat this document (alongside the earlier `OLP_XDV_DESIGN_REPORT.md` and `OLP_XDV_PROTOTYPE.html`) as the complete design record of this process — but per the reconciliation notice at the top, always verify against current code state before implementing anything described here.
