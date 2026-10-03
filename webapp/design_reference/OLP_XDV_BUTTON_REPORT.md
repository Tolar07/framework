# OLP XDV — BUTTON-BY-BUTTON FUNCTION REPORT (sign-off document)

**⚠ Reconciliation notice (same as `OLP_XDV_FUNCTION_MAP.md`):** this report describes
the **running code** in `webapp/` as of commit `HEAD`. Several items the function map
marked "confirmed requirement, not yet in prototype" have since been **built and tested** —
they are marked **✅ BUILT** below rather than as gaps. Where something is genuinely still
open, it is explicitly listed under **Still open** and is never silently assumed present.

Scope: the two-tier dashboard (public client + authed admin) rendered by `webapp/render_v2.py`,
served by `webapp/server.py`, interaction in `webapp/static/js/proto.js`. Phase 2 = **paper
only, zero capital** — an Architect bright line.

---

## 1. Client dashboard (`/dashboard/<date>`, public, trimmed payload only)

| # | Control | Function (from function map) | Status |
|---|---|---|---|
| C1 | Logo (top-left) | Returns to home / Call tab | ✅ links to `/` (302 → `/dashboard/<today>`) |
| C2 | Bottom tab **Call** | Today's (or selected day's) singles + one combined accumulator, each with SportyBet booking code | ✅ `data-panel="call"`, `#panel-call` |
| C3 | Bottom tab **Scan** | Full wide board, grouped by league, collapsible groups, date-filterable | ✅ `data-panel="scan"`, `#panel-scan` |
| C4 | Bottom tab **Analyst** | Read-only info panels, **no chat on client** (chat is admin-only per function map) | ✅ `data-panel="analyst"`, read-only panels |
| C5 | Call — single pick card | Tap expands to full market breakdown (all markets) | ✅ `.c-card-top[data-detail]` → `.c-detail.open` |
| C6 | Call — booking code **Copy** | Copies SportyBet code to clipboard; does NOT place a bet | ✅ `navigator.clipboard` + fallback; real codes via `booking/booking_codes.py`; honest **PENDING** when no code file |
| C7 | Call — accumulator card | Combined probability + its own separate booking code + copy | ✅ |
| C8 | Scan — date pills | View **today / tomorrow / day-after** (matches admin 2-day production) | ✅ pills `-1/0/+1/+2` link to `/dashboard/<iso>`; honest 404 on unpublished days |
| C9 | Scan — league group header | Tap expands/collapses that league's fixtures | ✅ `.c-league-head` → `.c-league-body.open` |
| C10 | Scan — search box | Live-filters visible fixtures by team/league as you type | ✅ `#scan-search`, `.scan-row[data-search]` |
| C11 | Scan — fixture row | Shows fixture + labeled pick on the row; tap expands to full market detail | ✅ `.c-fixture` + pick label; expand same pattern as Call |
| C12 | Scan — **live match state** | Kickoff → live score in real time (client self-verify) | ✅ **BUILT**: cards carry `data-fixture` + `[data-live-score]`; `proto.js` polls `POST /api/live-scores` every 60s and slots `LIVE <score>`. **Partial**: kickoff-time display before kickoff still needs a kickoff-time data source — see Still open #4 |
| C13 | Analyst — "Today's board" panel | Singles count, acca count, leagues scanned, no-data count | ✅ |
| C14 | Analyst — "Track record" panel | Phase, CLV legs logged, honest-edge status | ✅ |
| C15 | Analyst — "Explain a pick" panel | Points back to Call/Scan detail panels | ✅ |

Client **must not** expose model internals — verified: no `elo_probs`, `engine_divergence`,
`verification`, `best_mes_ev`, "Model Internals", "Honest edge", "zero capital", chat, trigger.
Enforced by `schema.trim_payload()` + asserted in `tests/webapp_server_test.py` §2.

---

## 2. Admin dashboard (`/admin/<date>`, full internals)

| # | Control | Function (from function map) | Status |
|---|---|---|---|
| A1 | Search bar (top) | Live-filters the dense grid by fixture/team/league | ✅ `#admin-search`, `.a-league-sep` visibility tracked |
| A2 | **Date selector** | Real date picker: **Today / Tomorrow / Day after** — not an auto-guess | ✅ `<input type="date">` (`#trigger-date`, value = board date); on change navigates to `/admin/<iso>` |
| A3 | **Trigger Production** | Runs orchestrator for the SELECTED date; loading state; disables during run (no double-trigger); updates grid/stats when done | ✅ `#trigger-btn` → `POST /api/trigger-board?date=`; spinner + disabled + "Running…"; reloads board on success. (In-place update is a full reload of the re-rendered board — see note below) |
| A4 | Stat pill **"N scanned"** | Click: full list of every scanned fixture | ✅ `data-chip="all"` → shows all |
| A5 | Stat pill **"N eligible"** | Click: filters to deploy-eligible (shortlist) fixtures | ✅ **BUILT**: `data-chip="eligible"` → `filterEligible()` hides non-shortlist rows (`data-short="1"`) |
| A6 | Stat pill **"CLV gate"** | Click: opens Phase 3 gate detail — legs logged, mean CLV, sign-off status | ✅ **BUILT**: `data-gate` → toggles `#gate-detail` (legs/req, mean CLV %, Architect sign-off, PASS/NOT-MET). Pill shows `warn` styling when not met |
| A7 | League filter chips | Each filters grid to that league; "All" resets | ✅ `.a-chip[data-league]` (generated from leagues actually on the board) |
| A8 | Dense grid row | Click: expands to full detail — every market + Model Internals | ✅ `.clickable[data-target]` → internals row (`_a_detail`) |
| A9 | Row internals | Elo second opinion, divergence %, MES verdict | ✅ `_internals()` |
| A10 | **Edit-before-publish** | Adjust the board before publishing (not just approve/reject) | ✅ **BUILT**: expanded row includes edit form (fixture, best market, best price, softness tier, on-shortlist) → `POST /api/admin/board-edit` patches the raw board |
| A11 | **Approve → Publish to Client** | Hard-gated; loading → success with timestamp | ✅ `#approve-btn` → `POST /api/admin/publish`; gate enforced server-side (`check_client_publish_gate`); timestamp in `#publish-status` |
| A12 | **AI Analyst chat** (admin) | REAL backend — Claude API + full board/CLV context, same as Telegram bot; no terminal needed | ✅ `#admin-chat-input`/`#admin-chat-send` → `POST /api/analyst` → `_analyst_reply()` (board context + `anthropic.messages.create`, model `claude-3-5-sonnet-20241022`, rate-limited 10/min/IP) |
| A13 | **Error/rejection log** | Visibility into failed/rejected attempts, not just successes | ✅ **BUILT**: `_admin_log()` — data flags + per-fixture rejection reasons, expand/collapse (`#log-toggle`) |

Admin is light theme, Basic-auth-gated (default). Dev escape hatch: `OLP_REQUIRE_ADMIN_AUTH=0`
lifts the wall for the prototype — **default stays ON** and must remain ON on any
phone-reachable/deployed host (`/admin` exposes full internals).

---

## 3. Backend endpoints (wired, tested)

| Endpoint | Method | Auth | Function |
|---|---|---|---|
| `/` | GET | — | 302 → `/dashboard/<today>` |
| `/dashboard/<date>` | GET | — | New client view (trimmed) or honest 404 |
| `/admin[/<date>]` | GET | admin | New admin view (full internals) |
| `/static/*` | GET | — | proto.css/js/fonts; traversal → 404 |
| `/api/board.json`, `/api/board/<date>.json` | GET | — | **Published-only** (gate-bounded); never an unapproved board |
| `/api/admin/board.json`, `/api/admin/board/<date>.json` | GET | admin | Full raw board, any date |
| `/api/stats.json`, `/stats`, `/why` | GET | admin | Admin diagnostics |
| `/api/trigger-board?date=` | POST | admin | Real orchestrator run (sends forced off) |
| `/api/admin/publish` | POST | admin | Approve → write published (hard-gated) |
| `/api/admin/board-edit` | POST | admin | Edit-before-publish patch of the raw board |
| `/api/analyst` | POST | — (rate-limited) | Real Claude API analyst reply |
| `/api/live-scores` | POST | — | `{fixture_key: score}` from multi-source current_results |
| `/history` | GET | — | Public board history |

---

## 4. The four "confirmed requirement, not yet in prototype" items — reconciled

| Item | Function-map marking | Actual status |
|---|---|---|
| Error/rejection log | not yet in prototype | ✅ **BUILT + tested** (A13) |
| Edit-before-publish | not yet in prototype, exact UI to design | ✅ **BUILT** (A10) — design confirmed with Architect (inline row edits) |
| Live match state (kickoff → live score) | not yet in prototype, source not confirmed | ⚠️ **LIVE SCORE built + tested** (C12, `POST /api/live-scores`). Kickoff-time display + the *source* need Architect sign-off (Still open #3/#4) |
| 2–3 day client view (Scan date pills) | — | ✅ **BUILT** (C8) — today/tomorrow/day-after pills match admin 2-day production |

So the draft's "four items not in prototype" is **stale as of HEAD** — three are fully built,
the live-match item is built except for the kickoff-time/source confirmation.

---

## 5. Still open (from the function map — do NOT build blind)

1. **Hosting/reliability conflict** — own machine vs. guaranteed "every time" execution.
   Needs an explicit Architect decision.
2. **SportyBet code generation** — partially resolved: real codes were captured for
   2026-08-09 via the Playwright click-through bridge (`booking/booking_codes.py`); whether
   SportyBet offers a programmatic API is still unconfirmed.
3. **Live-score data source** — currently the in-repo `multi_source` `current_results`
   registry (`_fetch_live_scores`). Architect to confirm this source or choose another.
4. **Kickoff-time display** (part of C12) — needs kickoff-time data on fixtures; none is
   reliably present yet, so it is **not fabricated** (HR35) and stays flagged.

---

## 6. Evidence

- `tests/webapp_server_test.py` — 15 sections, all passing (client surface + leak checks,
  admin surface, auth on/off, unpublished-board gate, board-edit, trigger guard, read-only
  server). Run: `python tests/webapp_server_test.py`.
- `tests/webapp_schema_test.py`, `webapp_render_test.py`, `webapp_export_test.py`,
  `webapp_run_daily_test.py`, `webapp_produce_test.py` — all passing.
- Live: `python webapp/server.py --port 8089` → `/dashboard/2026-08-07` (client),
  `/admin/2026-08-10` (admin).

---
*Sign-off artifacts: this report + `OLP_XDV_FUNCTION_MAP.md` + `OLP_XDV_PROTOTYPE.html`.*
