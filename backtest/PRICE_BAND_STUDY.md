# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-28 06:52Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 958 graded board singles**: stated 79.2%, landed 76.6% (calibration error -2.6 points) at an average price of 1.252, which needs 79.9% to break even. Return -4.2% ± 1.7.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 516 | 76.9% | 80.0% | 82.2% | -6.4% ± 2.3 | LOSING |
| 1.25–1.30 | 294 | 79.3% | 79.3% | 78.9% | +0.4% ± 3.0 | no edge either way |
| 1.30–1.50 | 142 | 70.4% | 77.0% | 75.6% | -7.0% ± 5.1 | no edge either way |
| 1.50–2.00 | 6 | 66.7% | 56.1% | 54.0% | +22.0% ± 38.9 | no edge either way |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 3 | 100.0% | 76.1% | 80.0% | +25.0% ± 2.1 | ahead |
| BOOK | 20 | 75.0% | 77.5% | 79.0% | -6.0% ± 12.5 | no edge either way |
| MARKET | 210 | 78.1% | 80.1% | 80.7% | -3.2% ± 3.6 | no edge either way |
| SAFE | 718 | 76.2% | 79.2% | 80.0% | -4.9% ± 2.0 | LOSING |
| VALUE | 7 | 71.4% | 55.7% | 55.6% | +25.6% ± 33.1 | no edge either way |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 45 | 46.7% | 51.4% | 46.4% | -3.2% ± 16.4 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
