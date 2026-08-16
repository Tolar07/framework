# Open Questions.md — Needs an Explicit Architect Answer

> Everything here is unresolved **and must not be assumed either way**. Each item
> either changes behavior if answered one direction or blocks a reliable
> feature until answered. Verified 2026-08-11. Cross-links: [[Rules.md]],
> [[Decisions Log.md]], [[Architecture.md]], [[Protected Constants.md]].

---

## 1. Did calibration-log league scope widen with the softness cancellation?
- **Context:** the softness-removal ratification (2026-08-11) said
  "calibration-log league scope … **UNCHANGED**" — i.e. it was explicitly NOT
  widened. But the unified **61-league pool** (ID401, per `config/leagues.json`; historical 18→25→61) and the new **edge-based
  market selection** ([[Decisions Log.md]] directive #4) assume wide coverage.
- **Open:** should the calibration log (which CLV statistics the Phase-3 gate is
  built from) now cover all **61** leagues (aggressive European expansion ratified 2026-08-12, now retroactively ratified 2026-08-16), or stay on the original deploy set? This
  directly affects whether the 12/30-leg CLV tally is even measuring the right
  population.
- **Impact:** answers whether the current −1.631% mean CLV is meaningful.

## 2. Does per-market price data exist to support edge-based (not just probability-based) market selection?
- **Context:** selection is now **EDGE = model_prob × price − 1** across ALL
  markets (1X2, O/U1.5, O/U2.5, BTTS, DC) per fixture — `engine/acca.py`
  `_best_deployable_leg()`. EDGE needs a *price* per market. Current fill:
  SportyBet 1X2 attrs, api-football (O1.5/BTTS/DC, 5 deploy leagues), Odds API
  free tier (the rest).
- **Open:** when the Odds API quota is spent (it is — 1/500), **does every
  deploy fixture actually have a real price on every market**, or does
  edge-based selection silently degrade to "the one market that happened to be
  priced"? If the latter, a leg picked as "best edge" may actually be the only
  priceable market, not the strongest signal.
- **Impact:** the correctness of the new market-selection rule under quota
  pressure. See [[Architecture.md]] Stage 2.

## 3. Odds API quota — reset timing and backup key
- **Context:** primary key at **1/500** (below the hard floor of 5). The monthly
  reset is the accepted resolution ([[Decisions Log.md]]); `ODDS_API_KEY_BACKUP`
  is an empty slot for a fresh free-tier key.
- **Open:** when exactly does the primary reset? Is a backup key going to be
  pasted before then? Until answered, non-deploy leagues will keep rendering
  `NO DATA — PENDING` (HR35).

## 4. What happens when `ARCHITECT_SIGNOFF` is unset?
- **Context:** the override is set (`1`) and the board is published live
  side-by-side with paper until mean CLV turns positive.
- **Open:** at what signal does the Architect flip it back to `0`? A date, a CLV
  threshold, or a leg-count? This is a **client-publish / [[Protected Constants.md]]**
  decision only the Architect can make.

## 5. Conference League fixtures — sourcing gap
- **Context:** Conference League is whitelisted (18th league) and SportyBet/Bet365
  mapped, but football-data.co.uk does NOT carry it. Current-season FIXTURES need
  a verified TheSportsDB id or ESPN slug; HR35 forbids guessing.
- **Open:** which verified source will feed its fixtures?

## 6. HNL odds sport key unverified
- **Context:** `soccer_croatia_hnl` is added to the Odds API sport map but was
  never verified against a live `/v4/sports` response (no quota when it was
  added).
- **Open:** confirm the key exists before trusting HNL odds (HR35).

## 7. EVENTSDAY fallback (ID410) — exact implementation location
- **Context:** only `tests/eventsday_fallback_test.py` references the name; the
  code function has a different name. Verified present in the data/fixtures path.
- **Open:** pin the exact function so the rule table ([[Rules.md]]) points at the
  right line.

## 8. security-reviewer retirement is convention, not deletion
- **Context:** `security-reviewer` is "retired in favor of `security-auditor`"
  per project convention, but **both** `.md` files still exist in `.claude/agents/`.
- **Open:** should the dead one be deleted, or kept for reference? Affects
  [[Agents.md]] accuracy and which reviewer an agent actually invokes.

## 9. Two vault copies — which is canonical? (2026-08-16)
- **Context:** the governance vault exists in two places:
  - **Canonical (git-tracked):** `olp_xdv_agent/olp_xdv/docs/obsidian-vault/` — committed, part of repo history.
  - **Drifted mirror (non-git):** `Documents/OLP_XDV_Vault/` — NOT a git repo, has more lines (e.g. `Decisions Log.md` 125 vs 50, `Rules.md` 73 vs 63) and stale numbers (still says "25 leagues").
- **Architect 2026-08-16 ruled:** the git-tracked repo copy is authoritative; the `Documents` mirror is deprecated and must not be treated as source of truth.
- **Open:** retire the `Documents/OLP_XDV_Vault` mirror (delete or symlink to repo copy)? Or establish a one-way sync (repo → mirror only)? Until resolved, **all agents must read/write the repo copy only**.

---

## 9. Team-Intelligence-Layer proposal — two source gaps + ID-numbering block (2026-08-15)
- **Context:** a proposed *Team-Intelligence-Layer* spec (full-slate result scrape
  + team-state intelligence) was pasted for Architect review. Read-only check
  (2026-08-15) found it sound *as a proposal* but **not buildable yet**:
  - **Idea 1 (full-slate scrape):** `data/football_data_source.py` already
    captures full-time scores (`MatchResult.fthg/ftag/ftr`) and has
    `load_league`/`save_results_json`. **Half-time scores (HTHG/HTAG/HTR) are
    NOT parsed** — `MatchResult` has no HT fields. football-data.co.uk carries
    them, so this is an additive parser change only. `brain/store.py` is the
    natural (currently unused) home for a `full_slate_results` table.
  - **Idea 2 (team-state):** engine has a promoted-club handler
    (`engine/dixon_coles.py`) but **no slots** for low-block / absentees /
    tier-drop / manager-bounce. These are *new* engine adjustments → pure
    Architect decision. The two stated data gaps are **absent from the current
    source stack** and need ID404 trust-tiering before any capital use.
- **Open (gaps to source before any ingestion):**
  1. **HT / score feed** — source exists upstream (football-data.co.uk), parser
     not yet wired to HT columns.
  2. **Team-state sources** (lineup / formation / coach / tactical profile) —
     **no current source feeds these**; must be found and ID404 trust-tiered.
  3. **ID numbering is blocked:** spec says "confirm IDs against
     `OLP_XDV_ID_RECONCILIATION_15AUG2026.md`" but **that doc does not exist**,
     and it references **ID418 (manager bounce) which is NOT a defined ID**.
     `Rules.md` tops out at **ID414**; **ID415 is already taken** (Produced-bet
     verification, `bets/produced_bet.py`). Free IDs: 416, 417, 419, 421+.
- **Impact:** proposal must NOT be built until (a) the two sources are sourced
  and ID404-tiered, (b) the engine action per field is decided by Architect, and
  (c) ID numbering is reconciled. No silent engine changes to live capital picks
  (HR51 / HR35). Per spec, Idea 1 score-only ingestion is the lowest-risk first
  build — but still requires Architect go-ahead.
- **Status (2026-08-15 HR52 sourcing directive EXECUTED):** the two source gaps
  are **resolved** — every clean source needed is already ratified in
  `SOURCE_TRUST` (api-football T1 is the workhorse for all six needs; the
  ~11/65 football-data.co.uk coverage gap and the Transfermarkt ToS exposure are
  the real findings). Full sourcing findings + ingestion design + proposed
  ID416/417/419/421/422 are in [[Decisions Log.md]] (2026-08-15 entry). The
  remaining gating items are **Architect decisions** (Transfermarkt ToS demotion,
  confirm api-football as Idea-1 primary, engine-action per field) — NOT sourcing.

---

## How to use this file
- **If you are an agent and something here blocks you:** surface the question
  again rather than picking an answer yourself (HR35 — no fabrication, no
  assumed defaults on Architect decisions).
- **If you are the Architect:** answer items by appending to [[Decisions Log.md]];
  when answered, mark the item here **Answer:** + date and link the decision.
