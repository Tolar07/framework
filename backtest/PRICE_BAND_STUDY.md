# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-18 21:00Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 574 graded board singles**: stated 79.0%, landed 78.9% (calibration error -0.1 points) at an average price of 1.247, which needs 80.2% to break even. Return -1.7% ± 2.1.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 320 | 79.4% | 79.7% | 82.2% | -3.4% ± 2.8 | no edge either way |
| 1.25–1.30 | 180 | 81.7% | 79.0% | 79.0% | +3.4% ± 3.7 | no edge either way |
| 1.30–1.50 | 72 | 69.4% | 76.5% | 75.7% | -8.5% ± 7.2 | no edge either way |
| 1.50–2.00 | 2 | 100.0% | 58.8% | 57.0% | +75.5% ± 15.5 | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 2 | 100.0% | 75.1% | 78.7% | +27.0% ± 1.0 | ahead |
| BOOK | 15 | 73.3% | 77.6% | 79.4% | -9.2% ± 14.7 | no edge either way |
| MARKET | 128 | 84.4% | 79.9% | 80.7% | +4.7% ± 4.0 | no edge either way |
| SAFE | 426 | 77.2% | 79.0% | 80.3% | -3.9% ± 2.5 | no edge either way |
| VALUE | 3 | 100.0% | 57.2% | 60.2% | +66.0% ± 13.1 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 22 | 45.5% | 53.0% | 48.6% | -7.6% ± 23.1 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
