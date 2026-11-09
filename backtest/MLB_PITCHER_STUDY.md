# MLB starting-pitcher model, shadow backtest

Made 2026-11-09 23:00 UTC by `backtest/mlb_pitcher_backtest.py` (framework#382). 15733 priced MLB games 2019-2025 (cached ESPN scoreboard: starters + first-five runs; closing moneyline). Tries counted: **27**. Chosen on 2019-2022, reported on **2023-2025 only**. 35 games had no starter on the scoreboard (league-average starter used, flagged, never invented).

Not loaded: 2019: 19 of 2470 games without a closing price (skipped); 2020: 9 of 953 games without a closing price (skipped); 2021: 15 of 2475 games without a closing price (skipped); 2022: 6 of 2472 games without a closing price (skipped); 2023: 1 of 2478 games without a closing price (skipped); 2024: 23 of 2476 games without a closing price (skipped)

## Full game moneyline vs the de-vigged close (held-out)

| Rule | Games | Brier | Log loss | Close Brier | Close log loss |
|---|---|---|---|---|---|
| Starter model alone: shrink 16, decay 0.98, market weight 0% | 7412 | 0.2467 | 0.6868 | 0.2416 | 0.6759 |
| Same model, starters blanked (team offence only) | 7412 | 0.2474 | 0.6879 | 0.2416 | 0.6759 |
| Best blended with the close: shrink 16, decay 0.95, market weight 50% | 7412 | 0.2432 | 0.6793 | 0.2416 | 0.6759 |

## First 5 innings (no F5 price in the free data)

6288 held-out games, ties after 5 dropped. Log loss: starter model **0.6907** vs the base rate 0.6914 (Brier 0.2485 vs 0.2491). F5 price test: PENDING (no F5 moneyline recorded yet; shadow it from Opening Day against the exchange).

## Reading

- Starters change log loss by -0.0011 vs team offence alone (help); model alone 0.6868 vs close 0.6759: the close is still the better chance.
- Blended best 0.6793 vs close 0.6759: no information beyond the price: price baseball off the exchange.
- 27 tries; held-out lines only. Starter rating = opponents' first-5 runs per start (a proxy, not FIP/xFIP); batter-hand splits and bullpen workload need data not in the free cache (PENDING).
- Record only: no stake, bar, threshold or live switch changes.
