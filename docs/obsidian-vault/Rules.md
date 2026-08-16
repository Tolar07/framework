# Rules.md — Every HR and ID as Coded

> Source of truth: **the code + `RATIFICATIONS.md`** (append-only per HR33), NOT
> any prose doc. Where a doc disagrees with the code, the code wins and the
> disagreement is flagged below. Verified 2026-08-11 from the working tree.
> This note cross-links to [[Decisions Log.md]] and [[Protected Constants.md]].

---

## HR rules (hard requirements — `HR###`)

| # | Meaning | Status | Implementing code |
|---|---------|--------|-------------------|
| **HR15** | **90-minute basis** — results settle on full-time (90-min) score, not ET/penalties | Active | `clv/clv_logger.py` (grading) |
| **HR30** | **Numerical MES required** — every capital pick carries a numerical Market Edge Score; MES = breakeven trigger price `1/model_prob`; no live price → explicit exception, never a silent blank | Active | `engine/mes.py` |
| **HR33** | **RATIFICATIONS append-only** — the ratification log is never rewritten | Active | `RATIFICATIONS.md` |
| **HR34** | **Unratified leagues never scan/deploy-eligible** — only `WHITELISTED_LEAGUES` counts; whitelist changes are Architect-only | Active | `engine/leagues.py` (`is_deploy_eligible`) |
| **HR35** | **No fabrication** — missing data renders `NO DATA — PENDING`; a gate never matches display text (canonical keys); CONFLICT/NO-DATA never silently resolved | Active (**most-cited rule**) | Everywhere; canonical example `booking/team_map.py` `resolve_team_to_model()` (exact+normalized only, **no fuzzy** — a wrong cross-club guess is worse than an honest gap) |
| **HR44** | **Ratify at time of change** — each RATIFICATIONS entry written when the change happens | Active | `RATIFICATIONS.md` |
| **HR46** | **CLV logging** — paper legs carry entry price (CL-LIVE) + closing line (CL-ARCHIVE) | Active | `clv/clv_logger.py`, `clv/closing_capture.py` |
| **HR48** | **Kickoff-date guard** — a leg with no recorded kickoff date is refused; a no-date fixture is NEVER assumed to be today | Active | `bets/produced_bet.py`, `clv/closing_capture.py` |
| **HR51** | **Capital phase** — Phase 2 = paper only, zero capital; Phase 3 (live capital) gated on ≥30 legs with CLV + positive mean CLV + Architect V7 sign-off; `assert_paper_only()` is a hard fail | Active — **PHASE = 3 as of 2026-08-11** (see [[Decisions Log.md]]); the statistical gate is NOT met (12/30, mean −1.631%) and is overridden by `ARCHITECT_SIGNOFF` | `config.py`, `clv/phase3_gate.py` |
| **HR52** | **Pro-rigor auto-ratification** — changes that add real data sources without weakening checks get ratified automatically | Active | `RATIFICATIONS.md` |
| **HR53** | **Full-detail-but-honest / plain-language mandate** — board uses full club names, markets in words; completeness never overrides honesty | Active | `output/produce_bet.py`, `engine/markets.py` (`display()`) |
| **HR56** | **Architect Directive Supremacy** — every Architect directive (chat / Claude Code / any channel) is binding law the moment given; cannot be superseded, silently reverted, overwritten, deprioritized, or treated as advisory without a LATER explicit Architect instruction. No directive expires by default; no silent reversion (report as a bug, HR56 r2); single source of truth per directive (HR56 r3); when in doubt ask, don't assume (HR56 r4); rule cannot be weakened by convenience (HR56 r5). Tasks have exactly two end states — implemented+confirmed, or explicitly reported blocked/failed to the Architect (HR56 r6); no silent discard; retroactive audit applies (HR56 r7). Formalized 2026-08-16 (see [[Decisions Log.md]]). | Active | Everywhere; reinforced by [[Protected Constants.md]] #5 (whitelist) |

## ID rules (design IDs / ratified components — `ID###`)

| # | Meaning | Status | Implementing code |
|---|---------|--------|-------------------|
| **ID82** | **Elo rating engine** — built from the same match data as Dixon-Coles; shown beside DC | Active | `engine/elo.py` |
| **ID130** | **Statarea convergence model** — Tier A list promoting Statarea to PRIORITY; convergence = 9+ of 16 sites agreeing ⇒ eligible | **SUPERSEDED / REJECTED** — master doc + `verification/id403.py` both mark it rejected; its Tier A promotes a REJECTED source | `verification/id403.py` |
| **ID401** | **League whitelist = unified pool** — **61 leagues** (current, from `config/leagues.json` via `engine/league_registry.py`; `engine/leagues.py` `WHITELISTED_LEAGUES` is a derived back-compat symbol — do not edit directly). Historical sizes 18 (2026-08-10) → 25 (2026-08-12) → 61 (2026-08-13 aggressive European expansion) are the SAME growing list, not disjoint sets; the union is 61. Every whitelisted league is scan- AND deploy-eligible | Active | `config/leagues.json` (authoritative) → `engine/league_registry.py` → `engine/leagues.py` `WHITELISTED_LEAGUES` |
| **ID402** | **Softness tiers** (A/B/C/D ranking, deploy cap, scan-only class) | **FULLY REMOVED 2026-08-11** — `engine/softness.py` deleted; nothing left that could re-enable tiers (see [[Decisions Log.md]]) | `engine/leagues.py` (only league-eligibility home) |
| **ID403** | **Multi-factor verification tiers** — VERIFIED / SINGLE-SOURCE / CONFLICT / NO-DATA / DERIVED; CONFLICT & NO-DATA never silently resolved | Active | `verification/id403.py` |
| **ID404** | **Source trust register** — ratified sources; trust tier sets corroboration requirement | Active | `RATIFICATIONS.md`, `data/` |
| **ID405** | **Market gate** — which markets may carry (paper) capital. **OPENED 2026-08-10**, away-win scope **overridden 2026-08-11**: `BLOCKED = {}`, all markets deployable. Re-close by re-adding to `BLOCKED` (Architect-only) | **OPEN (all markets deployable)** | `engine/markets.py` (`BLOCKED`, `mkt.blocked()`) |
| **ID406** | **WhatsApp delivery** (official Meta Cloud API) | **KILLED 2026-08-06** by Architect — token expiry + template approval pain; web dashboard replaced it. Credentials commented out in `.env` so it CANNOT send even if the flag flips | `output/whatsapp_deliver.py` (dead), `.env` |
| **ID407** | **Email copy channel + recalibration SHADOW mode** | Active (best-effort, never fails a run) | `output/email_deliver.py`, `engine/recalibration.py` |
| **ID408** | **Operational upgrades** — run watchdog, gate telemetry, team-alias suggestions, auto-retry | Active | `monitor/run_watchdog.py`, `monitor/`, `engine/cross_league.py` (`suggest_aliases`), `data/retry.py` |
| **ID409** | **EFL Cup on board + odds-quota override + fixtures never dropped** | Active | `pipeline/odds.py` (quota floor/override), `data/fixtures_source.py` |
| **ID410** | **EVENTSDAY fallback** — today's cup qualifiers reach the board when the standard fixtures feed misses them | Active — ⚠ exact function location **not pinned**; only `tests/eventsday_fallback_test.py` references the name. Implementation is in the fixtures/data path (`data/fixtures_source.py` / `data/multi_source_concrete.py`); see [[Open Questions.md]] | `data/` fixtures path + `tests/eventsday_fallback_test.py` |
| **ID412** | **Cross-engine consensus vote** — majority across available engines, persisted to brain | Active | `engine/consensus.py` |
| **ID413** | **Devigged implied probability** — market's devigged 1X2 as the EV anchor | Active | `engine/markets.py` (`MARKETS_1X2`), `run_daily.py` |
| **ID414** | **Market-anchored display probability / true modal scoreline** — Poisson modal scoreline for display + EV | Active | `engine/dixon_coles.py`, `webapp/schema.py` |

## Standing rules (not HR/ID-numbered)

| Rule | Status | Recorded |
|------|--------|----------|
| **Same-day product bet** (replaces 3-day rolling window) — THE CALL, produced bet, accas, singles draw ONLY from fixtures kicking off today; the 3-day window stays the scan reference | Active | `RATIFICATIONS.md` §1437, 2026-08-10 |
| **Production intent** — Acca A = top 4–5 highest-confidence fixtures, each leg the fixture's own single highest-probability market; no forced diversity; a fixture never appears in two bets; remainder → split accas + singles, each with its own booking code | Active | `engine/acca.py`, `.claude/OLP_XDV_PRODUCTION_INTENT.md` |
| **Ranking by confidence** — legs ranked by model probability (was EV) | **SUPERSEDED 2026-08-11 by Multi-market selection (EDGE = model_prob × price − 1)**; the "ranking by confidence" directive in this log is overridden by the EDGE-ranking directive of the same date | `engine/acca.py` `_best_deployable_leg()` (EDGE), [[Decisions Log.md]] 15-Aug reconciliation |
| **Architect publish override** — `ARCHITECT_SIGNOFF=1` bypasses the statistical client-publish gate; override is never silent (stamped in `publish_audit.jsonl`, honest-edge statement stays on the client view) | Active | `webapp/schema.py` |
| **Multi-market selection** — every fixture evaluated across ALL markets (1X2, O/U1.5, O/U2.5, BTTS, Double Chance); picks its own single best market by highest **EDGE = model_prob × price − 1**, tiebreak prob, then canonical order | Active | `engine/acca.py` `_best_deployable_leg()` |

---

## Doc-vs-code disagreements (flagged honestly)

1. **The config.py go-live comment lied.** `config.py` said "Recorded in RATIFICATIONS.md (2026-08-11)" but **no entry existed** until 2026-08-11, when it was retroactively appended (commit `76216e0`). See [[Decisions Log.md]].
2. **Master doc vs code drift is tracked in `docs/OLP_XDV_MASTER_DOCUMENTATION_2026-08-11.md` §1.4** (12 items). As of 2026-08-11 most are closed: ID405 OPEN vs docs "closed", softness removed vs "paused", 18 vs 17 leagues, single-day vs 3-day window, 12/30 vs 0/30 gate, `ARCHITECT_SIGNOFF` set vs unset.
3. **ID410 (EVENTSDAY)** — named only in a test; the code function has a different name. Flagged in [[Open Questions.md]].
4. **ID406 (WhatsApp)** — the ID is archived/killed but `output/whatsapp_deliver.py` still exists in the tree (dead code, env-commented). A `WHATSAPP_ENABLED=0` flag protects against re-enable without Architect approval.
5. **Two vault copies, only one canonical.** This `docs/obsidian-vault/` copy (git-tracked, current home) is authoritative per Architect 2026-08-16. The mirror at `Documents/OLP_XDV_Vault` is **non-git-tracked** and drifted (e.g. its `Rules.md`/`Decisions Log.md` still say "25 leagues"). It must NOT be treated as source of truth, and is flagged for retirement/sync in [[Open Questions.md]] and [[Decisions Log.md]] 2026-08-16.
6. **`config/leagues.json` is the runtime authority for the whitelist** (loaded by `engine/league_registry.py` at import; `engine/leagues.py` `WHITELISTED_LEAGUES` is derived). The 18/25/61 figures in older docs are historical sizes of the same list; consolidated to **61** 2026-08-16. The 61 was originally added by an agent "fix(data)" commit (`811eefb`, 2026-08-13) with no dated Architect directive — a breach of HR34/Protected-Constants #5 now retroactively ratified by Architect 2026-08-16 (HR56 r7).
