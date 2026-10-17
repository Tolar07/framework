# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-17 11:13Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 395 graded board singles**: stated 78.3%, landed 79.2% (calibration error +0.9 points) at an average price of 1.244, which needs 80.4% to break even. Return -1.6% ± 2.5.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 241 | 82.2% | 79.3% | 82.1% | -0.0% ± 3.0 | no edge either way |
| 1.25–1.30 | 114 | 79.8% | 77.7% | 79.1% | +0.8% ± 4.8 | no edge either way |
| 1.30–1.50 | 38 | 57.9% | 74.4% | 75.3% | -23.4% ± 10.7 | LOSING |
| 1.50–2.00 | 2 | 100.0% | 58.8% | 57.0% | +75.5% ± 15.5 | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BOOK | 12 | 75.0% | 77.4% | 79.6% | -8.3% ± 16.0 | no edge either way |
| MARKET | 94 | 88.3% | 79.2% | 80.7% | +9.5% ± 4.1 | ahead |
| SAFE | 286 | 76.2% | 78.3% | 80.6% | -5.7% ± 3.1 | no edge either way |
| VALUE | 3 | 100.0% | 57.2% | 60.2% | +66.0% ± 13.1 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 4 | 25.0% | 53.9% | 50.9% | -48.8% ± 51.2 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
