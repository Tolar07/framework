# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-14 11:36Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 332 graded board singles**: stated 78.0%, landed 78.0% (calibration error +0.0 points) at an average price of 1.242, which needs 80.5% to break even. Return -3.4% ± 2.8.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 207 | 81.2% | 79.2% | 82.2% | -1.2% ± 3.3 | no edge either way |
| 1.25–1.30 | 94 | 78.7% | 77.1% | 79.2% | -0.6% ± 5.4 | no edge either way |
| 1.30–1.50 | 30 | 53.3% | 73.3% | 75.2% | -29.4% ± 12.3 | LOSING |
| 1.50–2.00 | 1 | 100.0% | 64.0% | 62.5% | +60.0% | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BOOK | 12 | 75.0% | 77.4% | 79.6% | -8.3% ± 16.0 | no edge either way |
| MARKET | 56 | 83.9% | 78.6% | 81.1% | +3.5% ± 6.1 | no edge either way |
| SAFE | 262 | 76.7% | 78.0% | 80.6% | -5.1% ± 3.2 | no edge either way |
| VALUE | 2 | 100.0% | 58.9% | 65.1% | +53.5% ± 6.5 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
