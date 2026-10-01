# ARCHITECT'S STANDING ORDERS — OLP XDV (main)

These are the Architect's standing rules for the framework. They live on `main`
and are enforced by `tests/standing_orders_test.py`: if a merge, a combine, or a
new session ever reverts one of them, that test fails. **Read this file before
changing selection, delivery, phase or market logic.** Changing any order below
requires the Architect's explicit instruction — not an agent's own judgement,
and not "ratified on backtest evidence".

| # | Order | Where it lives |
|---|---|---|
| 1 | **Phase 3 — live capital, Architect-deployed.** No "Phase 2 / paper calibration" wording in anything the Architect reads. The system never places a stake; the Architect deploys. | `config.PHASE = 3` |
| 2 | **All markets open.** Home, Draw, Away, Over 2.5, Under 2.5 are all deployable. No market is blocked (Architect 2026-08-10; restored 2026-10-01 after the combine re-introduced the old ID405 block). | `engine/markets.py BLOCKED = {}`, `engine/slate.py BLOCKED_DEPLOY_MARKETS = {}` |
| 3 | **Deploy odds band: 1.20 – 2.00, safest 1.50.** Nothing above 2.00 is ever deployed; nothing below 1.20. | `engine/slate.py DEPLOY_ODDS_*` |
| 4 | **Winnable picks only.** A deploy pick must be one the model rates ≥ 50% to win — never a fallback the model expects to lose. | `engine/slate.py DEPLOY_MIN_MODEL_PROB` |
| 5 | **Canonical board** `##########OLP XDV#########` — TABLE 1–4 + ACCA route, real SportyBet booking codes, max 6 deploy singles (ID402). | `output/produce_bet.py` |
| 6 | **Telegram delivery twice daily:** ~10 PM Lagos for the NEXT day's fixtures, ~7 AM Lagos refresh for today. Production board on pick days + a heartbeat EVERY day. Failure alert on a broken run. | `.github/workflows/daily.yml` |
| 7 | **Coverage:** 16 leagues + UEFA Nations League, all priced from SportyBet. | `pipeline/odds_sportybet.py` |
| 8 | **Live match monitoring source: Flashscore.co.uk.** | (monitoring) |
| 9 | **Never fabricate** (HR35): no invented prices, scores or constants. Missing data shows as NO DATA — PENDING. | everywhere |

_Last updated 2026-10-01._
