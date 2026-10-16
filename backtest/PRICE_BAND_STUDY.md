# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-16 11:56Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 374 graded board singles**: stated 78.2%, landed 79.9% (calibration error +1.7 points) at an average price of 1.242, which needs 80.5% to break even. Return -0.9% ± 2.6.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 231 | 82.3% | 79.3% | 82.1% | +0.1% ± 3.1 | no edge either way |
| 1.25–1.30 | 108 | 81.5% | 77.5% | 79.1% | +2.9% ± 4.7 | no edge either way |
| 1.30–1.50 | 34 | 58.8% | 73.8% | 75.3% | -22.1% ± 11.4 | no edge either way |
| 1.50–2.00 | 1 | 100.0% | 64.0% | 62.5% | +60.0% | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BOOK | 12 | 75.0% | 77.4% | 79.6% | -8.3% ± 16.0 | no edge either way |
| MARKET | 93 | 88.2% | 79.2% | 80.7% | +9.4% ± 4.2 | ahead |
| SAFE | 267 | 77.2% | 78.1% | 80.6% | -4.6% ± 3.2 | no edge either way |
| VALUE | 2 | 100.0% | 58.9% | 65.1% | +53.5% ± 6.5 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 2 | 50.0% | 57.1% | 54.8% | +2.5% ± 102.5 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
