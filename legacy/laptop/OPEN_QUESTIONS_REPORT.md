# Open Questions Report

Auto-compiled by open_questions_report.py — this is a scan, not a resolution. Each item below needs an actual decision (many are explicitly Architect-only) before it can be marked closed.

## API Keys
- [ ] [[Open Questions.md]] — item 3 (quota reset timing + backup key)

## Decisions Log
- [ ] | 2026-08-06 | **EVENTSDAY fallback (ID410)** — today's cup qualifiers reach the board | `data/` fixtures path (exact fn name unverified — see [[Open Questions.md]]) |
- [ ] Verified: `engine/acca.py:141-152` `_best_deployable_leg()` — every fixture evaluated across `mkt.EDGE_MARKETS` (1X2, O/U1.5, O/U2.5, BTTS, Double Chance); picks its OWN single best market by highest **EDGE = model_prob × price − 1**, tiebreak model_prob, then canonical order. → [[Rules.md]], [[Open Questions.md]]
- [ ] The **calibration-log league scope** question (did it widen with the softness cancellation?) is NOT resolved — see [[Open Questions.md]].
- [ ] [[Open Questions.md]] — Item 1 updated 25→61; new Item 9 (two vaults).
- [ ] 1. **Sign-off reaffirmed** — the Architect explicitly authorizes proceeding despite negative mean CLV (currently ≈ -10.21% across 42 legs). This reaffirms the 2026-08-21 HR59 gate-suspension (gate already `gate_met=True`), so it is NOT a protected-constant change — only a named Architect instruction on the record. Capital authority remains Architect-only; `config.assert_paper_only()` still enforces no real stake routed by code.
- [ ] Architect sign-off: REQUIRED & AFFIRMED this session (Architect-only capital authority intact)

## OLP XDV
- [ ] [[Open Questions.md]]** — unresolved items needing an explicit Architect
- [ ] 3. **Decisions Log.md** for what the Architect decided; **Open Questions.md** for
- [ ] 5. Update **Open Questions.md** (new uncertainties) and **Decisions Log.md** (new

## OLP_XDV_Framework_Index
- [ ] ├── Open Questions.md             # Unresolved items needing Architect

## Open Questions
- [ ] # Open Questions
- [ ] Needed next step:** Rerun `review current analyses to propose changes about the Open Questions file` in a normal turn or try again. If the developer returns context, re-open directly at this file.

## Protected Constants
- [ ] > in [[Open Questions.md]] — do not flip it. Verified 2026-08-11.
- [ ] ## 5. Related protections (smaller, but Architect-only too)
- [ ] `WHITELISTED_LEAGUES`** — league eligibility is Architect-only (HR34); the **authoritative file is `config/leagues.json`** (loaded by `engine/league_registry.py` at import; `engine/leagues.py` `WHITELISTED_LEAGUES` is a derived back-compat symbol). Current whitelist = **61 leagues** (2026-08-13 aggressive European expansion, retroactively ratified 2026-08-16). Historical sizes 18 (2026-08-10) → 25 (2026-08-12) → 61 are the SAME growing list; the union is 61. Adding a league means editing `config/leagues.json` (with per-source IDs) — never editing `engine/leagues.py` directly.
- [ ] Editing any of these without a named Architect instruction is a violation of HR35 spirit and the standing safety rules.** If you genuinely need one changed, surface it as an [[Open Questions.md]] item and wait.

## README
- [ ] `Open Questions.md` — unresolved items needing an Architect answer

## Rules
- [ ] | **HR34** | **Unratified leagues never scan/deploy-eligible** — only `WHITELISTED_LEAGUES` counts; whitelist changes are Architect-only | Active | `engine/leagues.py` (`is_deploy_eligible`) |
- [ ] | **ID405** | **Market gate** — which markets may carry (paper) capital. **OPENED 2026-08-10**, away-win scope **overridden 2026-08-11**: `BLOCKED = {}`, all markets deployable. Re-close by re-adding to `BLOCKED` (Architect-only) | **OPEN (all markets deployable)** | `engine/markets.py` (`BLOCKED`, `mkt.blocked()`) |
- [ ] 3. **ID410 (EVENTSDAY)** — named only in a test; the code function has a different name. Flagged in [[Open Questions.md]].
- [ ] 5. **Two vault copies, only one canonical.** This `docs/obsidian-vault/` copy (git-tracked, current home) is authoritative per Architect 2026-08-16. The mirror at `Documents/OLP_XDV_Vault` is **non-git-tracked** and drifted (e.g. its `Rules.md`/`Decisions Log.md` still say "25 leagues"). It must NOT be treated as source of truth, and is flagged for retirement/sync in [[Open Questions.md]] and [[Decisions Log.md]] 2026-08-16.

## Vault-Memory-Index
- [ ] `[[Open Questions.md]]` — Unresolved items needing explicit Architect answer
