# OLP XDV — Ratification Log

Append-only, per HR33. Each entry is written **at the time of the change**
(HR44), not reconstructed afterwards. Authority is recorded per entry:
the Architect's bright lines (capital, staking, fabrication, verification,
honest-edge) are never auto-ratified — Section 12.

---

## 2026-08-04 · ID82 Elo Rating Engine — ratified by the ARCHITECT

**What:** A second, independent rating engine (`engine/elo.py`), ported from
DataEngine v277.1 sheet ELO RATINGS. It appears on the board as a **second
opinion beside Dixon-Coles**, never blended into it.

**Authority:** Architect. This changes what appears on the board, so it was not
taken under the auto-ratification grant.

**Formulas, as specified in ID82:**

```
E(home) = 1 / (1 + 10^((ELO_away − ELO_home − 65) / 400))
New ELO = Old + 20 × GD_mod × (Result − E)
```

Home advantage 65 Elo, K-factor 20, base 1500. `GD_mod` was undefined in ID82;
the standard World Football Elo taper is used and documented in the module.

**Why a second engine.** Dixon-Coles rates attack and defence within a pool
where everyone plays everyone — which is exactly why it cannot compare a Dutch
club to an English one. Elo updates a single number from results in any
competition, so cross-league comparability is structural.

It is also **genuinely independent**: different inputs (results and margins,
not goal counts), different mathematics (sequential updating, not maximum
likelihood), different failure modes. That is what ID403 means by independent
factors — and it is the opposite of ID130's convergence model, where sixteen
prediction sites reading the same public information agree by construction.

**Measured, 2024 Champions League league phase, each match predicted from
ratings that existed BEFORE it:**

| Configuration | Brier | Top-pick hit |
|---|---|---|
| Elo, 1 pass | 0.5545 | 57.3% |
| Elo, 3 burn-in passes | 0.4482 | 68.1% |
| **Elo, 6 burn-in passes** | **0.4306** | 67.4% |
| Dixon-Coles *(in-sample)* | 0.4247 | 69.4% |

Uniform guessing scores 0.667. Elo matches Dixon-Coles while being fully
out-of-sample; the Dixon-Coles figure is flattered by having been fitted on
those very matches.

**Known limit, stated rather than hidden.** Elo cannot separate leagues that
never meet. Championship clubs play no continental football, so Burnley and
Leeds still rate above Real Madrid in the pooled model. Ratings are comparable
only across leagues that actually play each other. This does not affect the
intended use (UCL/UEL, where every club has ≥8 continental matches).

**Scope of this ratification:**
- ✅ Elo shown as a second opinion on every board fixture
- ✅ `divergence()` raises a REVIEW flag when the engines differ by >12pp
- ❌ Does **not** change deploy gating (ID402 softness A/B, ≤6, unchanged)
- ❌ Does **not** feed MES, staking, or the Phase 3 gate

---

## 2026-08-03 · Sources ratified under the Section 12 grant

Functional, non-breaking source additions. Shown plainly, reversible in one word.

| Source | Tier | Role |
|---|---|---|
| **thesportsdb.com** | T2 | Upcoming fixtures. Community-editable, so fixtures stamp ○ SINGLE-SOURCE until a second source provides F2 quorum. |
| **the-odds-api.com** | T1 | Live entry prices — the missing piece for HR30 numerical MES and HR46 CLV logging. |
| **api-football.com** | T1 | Fallback history for competitions football-data.co.uk does not carry. Free tier stops at 2024, so anything sourced here is flagged STALE and is not calibration-grade (13.2). |

**Conference League (API-Football id 848)** is used as a cross-league
**calibration bridge only** — 108 league-phase matches that sharpen the shared
European scale. It is **not** ratified as a competition to bet; that would be
an HR34 whitelist change and remains Architect-only.

---

## Corrections to the source record

**`CRO` does not exist.** The framework's source table listed Croatia as
football-data.co.uk extra-league code `CRO`. Verified 2026-08-03: `/new/CRO.csv`
returns 404, and `/new/CRA.csv` is **Brazil**. Croatia is absent from
football-data.co.uk entirely. HNL history now comes from API-Football (stale-flagged).

**ID130 (v285.3) remains superseded.** Its Tier A list promotes Statarea to
PRIORITY, while master v303.15 §7.1 and `verification/id403.py` both mark it
REJECTED. Its convergence model (9+ of 16 sources agreeing ⇒ Ƈ-1 eligible)
treats correlated tipster sites as independent factors, which is the
self-certification failure ID403 exists to prevent — and it selects for public
consensus, which is where value is thinnest.
