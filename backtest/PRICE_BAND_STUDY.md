# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-11-05 06:54Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 1198 graded board singles**: stated 78.9%, landed 77.0% (calibration error -1.8 points) at an average price of 1.255, which needs 79.7% to break even. Return -3.5% ± 1.5.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 633 | 77.4% | 79.9% | 82.2% | -5.8% ± 2.0 | LOSING |
| 1.25–1.30 | 363 | 79.3% | 79.0% | 78.9% | +0.6% ± 2.7 | no edge either way |
| 1.30–1.50 | 190 | 72.1% | 76.6% | 75.5% | -4.6% ± 4.3 | no edge either way |
| 1.50–2.00 | 12 | 66.7% | 58.1% | 56.8% | +16.9% ± 25.2 | no edge either way |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 3 | 100.0% | 76.1% | 80.0% | +25.0% ± 2.1 | ahead |
| BOOK | 26 | 76.9% | 76.9% | 78.4% | -2.4% ± 10.8 | no edge either way |
| MARKET | 237 | 78.5% | 79.8% | 80.2% | -2.2% ± 3.3 | no edge either way |
| SAFE | 924 | 76.6% | 78.9% | 79.9% | -4.2% ± 1.7 | LOSING |
| VALUE | 8 | 75.0% | 55.9% | 55.7% | +32.1% ± 29.4 | no edge either way |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 70 | 47.1% | 52.4% | 47.4% | -3.4% ± 12.9 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
