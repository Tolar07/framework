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
| 7 | **Coverage:** 16 leagues + UEFA Nations League + League One, League Two, National League and FA Cup (2026-10-02), all priced from SportyBet. | `pipeline/odds_sportybet.py` |
| 8 | **Live match monitoring source: Flashscore.co.uk.** | (monitoring) |
| 9 | **Never fabricate** (HR35): no invented prices, scores or constants. Missing data shows as NO DATA — PENDING. | everywhere |
| 10 | **Every fixture gets production; nothing dropped** (2026-10-02). Alternative markets are open and bookable: Double Chance, Over/Under 1.5 / 2.5 / 3.5, BTTS. A fixture the model can't rate is priced MARKET-IMPLIED (SportyBet prices, margin removed, marked ᴹ, no edge claimed) instead of NO DATA. Every fixture's row shows its in-band pick, odds and an alternative market. | `engine/markets.py`, `engine/market_implied.py`, `orchestrator.py` |
| 11 | **Pick the outcome each match is most likely to produce — where the model AND the bookmaker agree.** Each fixture's pick is the in-band market with the highest consensus (model + de-vigged market). ★ BANKER = straight win, both agree ≥70% (backtest: ~82% won, ~+4% over 290 picks, two seasons). ✓ SAFE = both agree. ⚠ SPLIT = they disagree by >7pp — shown, never deployed. Singles and accas rank BANKER first. Evidence: `backtest/SELECTION_STUDY.md`. | `run_daily.py`, `engine/slate.py` |

_Last updated 2026-10-02._
