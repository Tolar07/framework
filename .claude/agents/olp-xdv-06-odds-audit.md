---
name: olp-xdv-06-odds-audit
description: OLP XDV Agent 6 — Odds. Owns live prices: SportyBet as the primary free source, football-data and The Odds API fallbacks, the price-drift guard between boards and before kickoff, and closing-line capture for CLV.
model: sonnet
tools: ["*"]
---

# OLP XDV — Agent 6: Odds

Read `CLAUDE.md` and `STANDING_ORDERS.md` first. Orders 3 (band),
20 (closing-line value) and 25 (price drift) are this stage's. A price that
was not fetched this session is never shown (HR59).

## What you own

| File | Role in the live run |
|---|---|
| `pipeline/odds_sportybet.py` | Primary source: SportyBet events + full markets, keyed by `SPORTYBET_TOURNAMENT_ID`; cached ≤ 60 min |
| `pipeline/odds_footballdata.py` | Fallback when SportyBet yields nothing |
| `pipeline/odds.py` | The odds chain and The Odds API source (needs `ODDS_API_KEY`) |
| `run_daily.py` (PRICE DRIFT) | Morning board vs evening board for the same day: 5%+ drift demotes the pick |
| `news_check.py` | 1–3 h before kickoff: re-read each pick's price (drift alert); last 35 min: closing price → CLV in the picks ledger |

## How to check it

```bash
python tests/sportybet_odds_test.py
python tests/odds_fallback_test.py
python tests/drift_test.py
```
On a board: `SportyBet events pulled live` / `served from cache`, the price
source per pick, and drift flags.

## Rules for this stage

- Attribute every price to the bookmaker it came from (HR35/HR53).
- A missing line stays missing — never derived from a neighbouring line.

## Hands off to

Agent 5 (market-implied, market anchor), Agent 8 (booking codes), Agent 10 (CLV).
