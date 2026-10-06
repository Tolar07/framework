# NBA STUDY — can the football framework's method work on the NBA?

Data: every NBA regular-season game 2022-23 to 2025-26 from ESPN, with the closing ESPN BET moneyline, spread and total. 2022-23 warms the ratings up, 2023-24 learns the settings, **2024-25 and 2025-26 are the test** (never used to choose anything).

- 2022-23: 1231 games, 0 with a closing moneyline
- 2023-24: 1232 games, 1231 with a closing moneyline
- 2024-25: 1234 games, 1233 with a closing moneyline
- 2025-26: 1235 games, 1225 with a closing moneyline

## Q1 · The model next to the closing moneyline (test seasons)

Elo settings learned on 2023-24: K 20, home advantage 40 Elo points.

| Who predicts | Brier (lower = better) | log loss |
|---|---|---|
| Elo model alone | 0.2076 | 0.6020 |
| Closing line (margin removed) | 0.1966 | 0.5753 |

## Q2 · Football's recipe: chance = market + w × (model − market)

- best w on 2023-24: **0.00**
- test Brier: market alone 0.1966 · w = 0.25 (football's) 0.1974 · w = 0.00 0.1966

## Q3 · The football pick rule on NBA winners (price 1.20–2.00, chance 75%+)

Returns are at ESPN BET's closing price. SportyBet's price for the same side is usually a little lower, so treat these as the best case.

| Season | Picks | Return per £1 |
|---|---|---|
| 2024-25 | 132 picks · won 96 (72.7%) · avg chance 77.4% · avg price 1.24 | -10.2% |
| 2025-26 | 136 picks · won 104 (76.5%) · avg chance 77.4% · avg price 1.24 | -5.5% |
| **both** | 268 picks · won 200 (74.6%) · avg chance 77.4% · avg price 1.24 | **-7.8%** |

By price bracket (both test seasons):

| Price | Picks | Return per £1 |
|---|---|---|
| 1.20–1.25 | 155 picks · won 122 (78.7%) · avg chance 78.4% · avg price 1.22 | -4.0% |
| 1.25–1.30 | 113 picks · won 78 (69.0%) · avg chance 76.0% · avg price 1.26 | -13.0% |
| 1.30–1.36 | none | +0.0% |
| 1.36–2.00 | none | +0.0% |

Same rule on the market's chance alone (no model): 268 picks · won 200 (74.6%) · avg chance 77.4% · avg price 1.24 · return -7.8%.

## Q4 · 3-leg accas of those picks (order 40), same day, strongest first

21 accas · won 7 (33.3%) · return per £1 -37.3%

## Q5 · Totals: where the final score lands against the closing line

2463 test games. Final total minus the closing line: mean +0.6, spread (standard deviation) **18.0 points**.

| Line vs closing total | Over landed | Fair price (Over) |
|---|---|---|
| -12.5 | 75.0% | 1.33 |
| -9.5 | 69.5% | 1.44 |
| -6.5 | 63.5% | 1.57 |
| -3.5 | 57.0% | 1.75 |
| +0.0 | 51.0% | 1.96 |
| +3.5 | 41.6% | 2.40 |
| +6.5 | 35.1% | 2.85 |

The fair price on any line of SportyBet's points ladder follows from this table: a pick there is only worth it when SportyBet pays MORE than the fair price.

## Q6 · SportyBet's NBA prices today (6 Oct 2026, 21 regular-season games listed)

SportyBet lists the NBA (sr:tournament:132) with the winner (incl. overtime,
market 219), a points-total ladder of 11–18 lines per game (225) and
handicaps (223). Read against the 18-point spread above, the ladder is close
to fair once its real centre line is used. One apparent +20% "value" was a
stale centre line left inside a ladder (Miami v Minnesota: 236.5 at
1.89/1.89 while the rest of the ladder centres on 242.5), not value.

## What this says

- The closing NBA moneyline is sharper than an Elo model (Q1), and the best
  weight on the model is 0 (Q2): unlike football's lower leagues, the model
  adds nothing the market doesn't already know.
- The football pick rule finds well-calibrated NBA favourites (75% chance,
  74.6% won) but at 1.20–1.30 the bookmaker's margin is larger than any edge:
  −7.8% at the closing price, and SportyBet usually pays a little less (Q3).
  3-leg accas of them: −37% on a small sample (Q4).
- So the "pick the likeliest outcome" method would lose money on the NBA. The
  one route with a real chance is PRICE COMPARISON: a SportyBet price above
  the margin-free sharp price (DraftKings / ESPN BET) for the same outcome.
  That can't be backtested (no SportyBet price history); it has to be
  measured live, on paper, from the regular-season start (20 Oct 2026).
  Preseason games (starters rested) are not a fair test.
