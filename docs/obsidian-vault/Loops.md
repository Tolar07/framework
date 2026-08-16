# Loops.md — Autonomous Agent Loops Running Against This Repo

> What runs unattended against the OLP XDV codebase, which agents it calls,
> and what it may never touch without an explicit Architect instruction.
> Written 2026-08-15. Cross-links: [[Agents.md]], [[Rules.md]], [[Protected Constants.md]].

---

## PR / code-review babysitting loop

**What it does:** monitors open PRs and review comments on the OLP XDV repo,
routes every PR through the mandatory review chain below, auto-fixes what's
safe to auto-fix, and merges only when every gate passes AND the PR does not
touch a protected file (see below). Protected-file PRs are flagged with an
explaining comment and left open for the Architect — never merged automatically.

**The command:**
```
/loop babysit PRs and review comments on the OLP XDV repo.
Route every PR through code-reviewer first (mandatory, per project convention).
Auto-fix build/lint failures via build-error-resolver (minimal diffs only).
Gate on tdd-guide coverage and e2e-runner test results.
Run security-auditor on any PR touching auth, credentials, or booking/.
Merge only when all of the above pass AND the PR does not touch any file in
the protected list below — protected-file PRs get flagged with a comment
explaining why and left open for the Architect, never merged automatically.
```

## Agent roles in this loop

| Role in loop | Agent | Why this one |
|---|---|---|
| Mandatory reviewer, every PR | **code-reviewer** (plugin, opus) | Already marked "MUST be used for all code changes" in its own frontmatter — this loop doesn't create that requirement, it enforces an existing one |
| Build/lint auto-fix | **build-error-resolver** (plugin, opus) | Explicitly scoped to minimal diffs, no architectural edits — safe for unattended use |
| Test enforcement | **tdd-guide** (plugin, opus) | Gates on 80%+ coverage before merge is allowed |
| E2E gate | **e2e-runner** (plugin, opus) | Runs the Playwright suite, quarantines flaky tests rather than blocking the loop on them |
| Security pass | **security-auditor** (chusri, opus) | Per [[Agents.md]]'s resolved-overlaps note, `security-reviewer` is retired in favor of this one for OWASP/auth/JWT/CORS work |
| Dead-code/refactor | **refactor-cleaner** (plugin, opus) | Fine for unattended use EXCEPT inside the protected-file list below |
| Docs upkeep | **doc-updater** (plugin, opus) | Should be the agent updating `Decisions Log.md` / `Open Questions.md` as work proceeds, per the vault's own "how to start a session" instructions |
| Escalation only, never auto-invoked by this loop | **architect**, **planner** | Structural/system-design decisions stay human-triggered — explicitly outside loop scope |

## Protected files — flag, never auto-merge

Pulled directly from [[Protected Constants.md]], not a generic list. A PR touching any of these gets a comment explaining why it wasn't merged, stays open, and is reported to the Architect:

- `webapp/schema.py` (`_gate_state`, `check_client_publish_gate`, `write_published`) — the CLV/publish gate
- `clv/phase3_gate.py`, `clv/clv_logger.py`, `clv/closing_capture.py` — CLV logging/gating
- `config.py` (`PHASE`, `CAPITAL_ENABLED`) — the paper→real-money boundary
- `booking/booking_codes.py` — must stay read-only by construction, never gains stake-submission logic
- `engine/leagues.py` (`WHITELISTED_LEAGUES`) — league eligibility, Architect-only per HR34
- `engine/markets.py` (`BLOCKED`) — the ID405 market gate
- `RATIFICATIONS.md` — append-only per HR33, never rewritten
- `.env` / `ARCHITECT_SIGNOFF` — the publish override

## Known issue to resolve before this loop runs unattended

[[Open Questions.md]] item 8 — `security-reviewer` and `security-auditor` both still physically exist in `.claude/agents/`, even though project convention says use `security-auditor`. If this loop's security step isn't pinned to one explicitly, it could invoke either inconsistently across runs. **Resolve by deleting or renaming the dead `security-reviewer.md` before enabling this loop**, not by leaving it as an unenforced convention — an autonomous loop needs a deterministic choice, not a convention it might not read.

## Gating mechanism (Stop hook)

The prompt wording above is not what actually enforces the protected-file boundary — a Stop hook is. Before the loop is allowed to consider a PR "done" and mergeable:
1. Diff the changed files against the protected list above.
2. If any protected file is touched, block auto-completion and force the flag-for-review path — regardless of how clean tests/lint/coverage look.
3. Only if no protected file is touched does the loop proceed to merge on green.

This mirrors the same design principle as [[Protected Constants.md]] itself: these boundaries are enforced by code, not by trusting the prompt to remember them every time.

## Related notes
- **[[OLP XDV.md]]** — vault home / entry point
- **[[Agents.md]]** — the full agent roster this loop draws from
- **[[Rules.md]]** — the HR/ID rules this loop must respect (HR34, HR35, HR51 in particular)
- **[[Protected Constants.md]]** — the source of the protected-file list above
- **[[Open Questions.md]]** — item 8, the security-reviewer/security-auditor duplication this loop depends on resolving
- **[[Decisions Log.md]]** — record this loop's activation here once turned on
- **[[Architecture.md]]** — the pipeline this loop babysits changes to

---

## Addendum — enforced protected superset (2026-08-15)

The standing instruction for this loop (session 2026-08-15, confirmed via the
"Both ID lists merged" choice) requires the protected gate to also cover the
betting-logic files the ID labels in the repo's own `Rules.md` do not name
directly. The loop's **enforced** set is therefore the union of the list above
AND:

- `engine/acca.py` — `EDGE = model_prob × price − 1` (the "edge calculation"),
  `MAX_ODDS_CAP = 2.00` (the "odds ceiling"), and the acca cap / staking shape
  (Section 6a / production intent).
- `verification/id403.py` — ID403 fabrication / verification tiers.
- `output/produce_bet.py` — ID409 frozen output contract (table format + ordering).
- `booking/team_map.py` — the canonical HR35 reverse resolver (exact-only, no fuzzy).

Rationale: in `Rules.md`, ID406 = WhatsApp (killed), ID412 = cross-engine
consensus vote, ID409 = EFL Cup / odds-quota override — so the user's phrasing
("ID406 edge calc", "ID412 odds ceiling", "ID409 table format") maps to the
**code targets** above, not to the bare ID rows. The loop matches on **file
path**, not on the ID number.

## Item 8 status

The loop prompt pins `security-auditor` explicitly on every security-relevant
PR, so the determinism concern (invoking `security-reviewer` vs
`security-auditor` inconsistently) is resolved at the prompt level. Physical
deletion/renaming of the dead `security-reviewer.md` is intentionally left
pending an explicit go-ahead, because it is a tracked file in a two-session
live repo (Safe Move protocol: do not discard the other session's tree state
without confirmation).

## Gating note

No dedicated Stop hook yet enforces the protected boundary (the harness hooks
list has no protected-file gate). The boundary is enforced by the loop
prompt's own discipline above. If a real Stop hook is later added, it should
diff changed files against the union list and block auto-completion on any
match.
