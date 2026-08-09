# Acca Verification Summary — 2026-08-09

**Generated:** 2026-08-09 (same-day rule 2026-08-09)  
**Source commits:** `d7ccbdd` (rule) → `f353208` (booking fix) → `d27cd99` (docs)  
**Board:** `board_2026-08-09.json` / `board_2026-08-09.txt`

---

## Acca 1 — BOOKED ✅
**Code:** `HBVCXA`  
**Combined odds:** 390.84 | **Combined prob:** ≈0.3% (legs not independent)

| Leg | Fixture (League) | Market | SportyBet Price | Model Prob | EV |
|-----|------------------|--------|-----------------|------------|-----|
| 1 | Kilmarnock v Celtic (Scottish Premiership) | Draw | 5.51 | 21.9% | **+20.8%** |
| 2 | Rangers v Hibernian (Scottish Premiership) | Draw | 4.58 | 24.5% | **+12.2%** |
| 3 | Charleroi v OH Leuven (Belgian Pro League) | Draw | 3.67 | 27.7% | **+1.6%** |
| 4 | Sparta Rotterdam v Feyenoord (Eredivisie) | Draw | 4.22 | 23.4% | −1.2% |

**Booking status:** All 4 legs BOOKED → code `HBVCXA` captured.  
Paste `HBVCXA` into SportyBet → slip pre-filled, you review + stake.

---

## Acca 2 — MANUAL ⚠️
**Code:** *none* (could not be driven)  
**Combined odds:** 51.40 | **Combined prob:** ≈1.5%

| Leg | Fixture (League) | Market | SportyBet Price | Model Prob | EV |
|-----|------------------|--------|-----------------|------------|-----|
| 1 | Anderlecht v RAAL La Louviere (Belgian Pro League) | Draw | 3.74 | 26.0% | −4.1% |
| 2 | Gent v Mechelen (Belgian Pro League) | Draw | 3.57 | 27.0% | −5.0% |
| 3 | Motherwell v Falkirk (Scottish Premiership) | Draw | 3.85 | 23.0% | −12.5% |

**Booking status:** SportyBet SPA threw a promo dialog mask over the Belgian league page; 48 click retries failed. **Every leg MANUAL** — add by hand if you want this acca.

---

## Honest Edge Line (from the framework)

> The accas are a **product shape**, not a demonstrated edge. The backtest is negative; the deployable book's positive residual is drift, not skill. An acca multiplies the variance of legs that are **not independent** — the combined odds are information about the product, not a promise. Acca1's best leg is +20.8% EV and the framework names it anyway, which is exactly what a set of choices should do: give you ranked options with the honest line attached. Booking codes are conveniences, not permission to stake.

---

## Files for Deep Verification

| File | Purpose |
|------|---------|
| `acca_2026-08-09.json` | Machine-readable acca payload (full EV, prob, softness_tier, market_key) |
| `acca_2026-08-09.txt` | Human-readable acca block + booking codes (appended) |
| `acca_2026-08-09_codes.json` | Booking code result with per-leg BOOKED/MANUAL + reasons |
| `board_2026-08-09.json` | Full daily board (includes `accas` + `produced_bet` + all fixtures) |

---

## Standing Rule Reference

- **Rule date:** 2026-08-09 (Architect direct instruction)
- **Product bet scope:** TODAY's fixtures only (`kickoff_date == today`)
- **Acca legs:** Capital-cleared only (`mkt.DEPLOYABLE` = Draw + Under 2.5; ID405)
- **Max accas:** 3 | **Legs per acca:** 4 | **Ranking:** EV desc, prob tiebreak
- **Shortened accas:** Never padded with non-today fixtures (HR35)
- **Phase:** 2 — paper only, zero capital, Architect-only deployment