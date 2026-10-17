# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-17 20:58Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 515 graded board singles**: stated 78.9%, landed 77.7% (calibration error -1.2 points) at an average price of 1.246, which needs 80.2% to break even. Return -3.3% ± 2.3.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 293 | 79.2% | 79.7% | 82.2% | -3.6% ± 2.9 | no edge either way |
| 1.25–1.30 | 163 | 79.8% | 78.8% | 79.0% | +0.9% ± 4.0 | no edge either way |
| 1.30–1.50 | 57 | 63.2% | 75.9% | 75.6% | -16.6% ± 8.5 | no edge either way |
| 1.50–2.00 | 2 | 100.0% | 58.8% | 57.0% | +75.5% ± 15.5 | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 2 | 100.0% | 75.1% | 78.7% | +27.0% ± 1.0 | ahead |
| BOOK | 13 | 69.2% | 77.8% | 79.8% | -15.3% ± 16.3 | no edge either way |
| MARKET | 126 | 84.1% | 79.9% | 80.7% | +4.3% ± 4.1 | no edge either way |
| SAFE | 371 | 75.5% | 78.8% | 80.3% | -6.2% ± 2.8 | LOSING |
| VALUE | 3 | 100.0% | 57.2% | 60.2% | +66.0% ± 13.1 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 12 | 41.7% | 52.5% | 48.2% | -11.3% ± 33.4 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
