# TIPSTER STUDY — slips posted on X, graded

Written by `backtest/tipster_study.py` from graded slips (`engine/tipsters.py`). Implied chance = 1 / price with the bookmaker's margin included — a fairly priced leg lands ~5% more often than that. Nothing is trusted before 100+ graded slips; nothing is promoted without the Architect. Paper only.

58 slips looked at: 58 graded, 0 ungradable (a leg's result or market couldn't be read).

## Per poster

| Poster | slips | slips landed | legs landed | £1 a slip: return ± se | verdict |
|---|---|---|---|---|---|
| site:statarea | 34 (34 graded) | 25/34 landed vs 100.0% implied | 25/34 legs | -26% ± 8% | learning |
| site:vitibet | 24 (24 graded) | 16/24 landed vs 100.0% implied | 16/24 legs | -33% ± 10% | learning |

## Legs by market

| Market | legs | landed | implied (avg) |
|---|---|---|---|

## Legs by price band

| Price | legs | landed | implied (avg) |
|---|---|---|---|

## Consensus — a game on several slips the same day

| Slips carrying the game | legs | landed | implied (avg) |
|---|---|---|---|

## Legs by class — aligned vs risky add-ons

aligned = a plain market at 60%+ implied (≤ 1.67, the kind of leg our F8/F1/F2/B1 rules bet); special = a SportyBet special we grade (1UP/2UP early payout, "or Over 2.5", win either half, 3 in a row) at 2.00 or shorter; risky = a price over 2.00 or a market we can't read; middle = the rest.

| Class | legs | landed | implied (avg) | ungradable |
|---|---|---|---|---|
| middle | 58 | — | — | 58 |

## Official Top Picks vs everyone else

| Source | slips | slips landed | legs landed | £1 a slip: return ± se | verdict |
|---|---|---|---|---|---|
| official (@SportyBet / @SportyBetNG) | 0 | — | — | — | — |
| tipsters | 58 (58 graded) | 41/58 landed vs 100.0% implied | 41/58 legs | -29% ± 6% | learning |

A bookmaker's margin of ~5% a leg compounds on an acca: 6 legs at fair prices still return about −26% on average, so a long acca slip must beat that just to break even.

## Closing-line value — did the price move towards the tip?

Each leg is looked up in the universe sweep (`data/universe/`; every SportyBet football and basketball game, first and last price before kick-off, swept every 3 h) and compared with SportyBet's LAST price there. CLV = entry price / closing price − 1 (positive = the price shortened after the tip, as for our own picks, order 20). EV vs close = the closing price's margin-free chance × the entry price − 1 (a fair bet reads 0; the bookmaker's margin makes the average leg about −5%). Move = how many points of margin-free chance the market moved TOWARDS the leg between the sweep's first and last look — it doesn't depend on when the entry price was read. Entry price: a SportyBet leg's price when its code was DECODED (SportyBet's share API gives today's price, not the price at posting — decode soon after collecting), a bet365 leg's price as posted. A leg whose entry price was read after the sweep's last look has no close and is left out, as is a market the sweep doesn't keep (handicaps, team totals, specials other than 1UP/2UP). 1UP/2UP legs get a CLV but no EV or move: both teams can go a goal up in the same game, so that row's chances don't add up to one.

0 of 58 legs measured against the close.

| Group | legs | CLV ± se · beat close | EV vs close ± se | moved towards the leg | median entry → kick-off |
|---|---|---|---|---|---|
| all legs | 0 | — | — | — | — |
| sportybet slips | 0 | — | — | — | — |
| bet365 slips | 0 | — | — | — | — |
| official Top Picks | 0 | — | — | — | — |
| class: aligned | 0 | — | — | — | — |
| class: middle | 0 | — | — | — | — |
| class: special | 0 | — | — | — | — |
| class: risky | 0 | — | — | — | — |

Per poster (nothing trusted before 100+ legs measured):

| Poster | legs | CLV ± se · beat close | EV vs close ± se | moved towards the leg | median entry → kick-off |
|---|---|---|---|---|---|

Reading it: a poster with a CLV and a 'moved towards' clearly above zero over 100+ legs is spotting prices before the market corrects them — the one sign of real skill. Near zero with a high landing rate means they pick favourites the price already describes.

