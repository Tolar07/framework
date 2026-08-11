# Open Questions.md — Needs an Explicit Architect Answer

> Everything here is unresolved **and must not be assumed either way**. Each item
> either changes behavior if answered one direction or blocks a reliable
> feature until answered. Verified 2026-08-11. Cross-links: [[Rules.md]],
> [[Decisions Log.md]], [[Architecture.md]], [[Protected Constants.md]].

---

## 1. Did calibration-log league scope widen with the softness cancellation?
- **Context:** the softness-removal ratification (2026-08-11) said
  "calibration-log league scope … **UNCHANGED**" — i.e. it was explicitly NOT
  widened. But the unified 18-league pool (ID401) and the new **edge-based
  market selection** ([[Decisions Log.md]] directive #4) assume wide coverage.
- **Open:** should the calibration log (which CLV statistics the Phase-3 gate is
  built from) now cover all 18 leagues, or stay on the original deploy set? This
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

---

## How to use this file
- **If you are an agent and something here blocks you:** surface the question
  again rather than picking an answer yourself (HR35 — no fabrication, no
  assumed defaults on Architect decisions).
- **If you are the Architect:** answer items by appending to [[Decisions Log.md]];
  when answered, mark the item here **Answer:** + date and link the decision.
