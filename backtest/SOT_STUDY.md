# SOT STUDY — 2026-10-05

**Question (Architect, 5 Oct):** expected goals only exist for the top 5
leagues (Understat). Can shots on target stand in for xG elsewhere?

**Method:** `backtest/sot_study.py`, `engine/sot_model.py`. Each shot on target
is worth the league's goals per shot on target; a time-weighted rating on those
"shot goals" gives a Poisson grid, averaged 50/50 with Dixon-Coles exactly like
Understat xG. Walk-forward like production (ridge 3, 240-day half-life, refit
every 14 days), 14 league-seasons, 2,356 matches with shots data.

| League | Matches | 1X2 log loss: DC → blend | Over 2.5 Brier: DC → blend |
|---|---|---|---|
| **All** | 2,356 | 1.0196 → **1.0156** | 0.2495 → **0.2474** |
| Championship | 598 | 1.0643 → 1.0590 | 0.2572 → 0.2560 |
| Belgian Pro League | 354 | 1.0217 → 1.0168 | 0.2603 → 0.2557 |
| Primeira Liga | 353 | 0.9354 → 0.9368 | 0.2427 → 0.2418 |
| Eredivisie | 344 | 0.9947 → 0.9833 | 0.2307 → 0.2280 |
| Scottish Premiership | 256 | 1.0059 → 1.0049 | 0.2535 → 0.2532 |
| National League | 82 | 1.0015 → 0.9845 | 0.2339 → 0.2315 |
| League Two | 74 | 1.1040 → 1.1113 | 0.2373 → 0.2362 |
| League One | 62 | 1.1195 → 1.1187 | 0.2507 → 0.2526 |
| La Liga 2 | 60 | 1.0159 → 1.0253 | 0.2757 → 0.2738 |
| Ligue 2 | 45 | 1.0613 → 1.0508 | 0.2552 → 0.2415 |
| Turkish Super Lig | 43 | 1.0592 → 1.0438 | 0.2370 → 0.2318 |
| 2. Bundesliga | 32 | 1.0786 → 1.0889 | 0.2543 → 0.2545 |
| Greek Super League | 27 | 0.9410 → 0.9672 | 0.2540 → 0.2618 |
| Serie B | 26 | 1.0277 → 1.0161 | 0.2478 → 0.2339 |

## Decision

Adopted (`sot_model.SOT_LEAGUES`) where the blend improved BOTH measures over
250+ matches: Championship, Belgian Pro League, Eredivisie, Scottish
Premiership. Primeira Liga was mixed and stays on Dixon-Coles. The smaller
samples (under 100 matches, this season only) are too noisy to call either
way; rerun as the season adds matches. Extra-file leagues (Denmark, Poland,
Austria, Switzerland, Norway, Sweden) carry no shots data.
