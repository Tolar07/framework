# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-21 20:53Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 628 graded board singles**: stated 79.1%, landed 78.3% (calibration error -0.7 points) at an average price of 1.248, which needs 80.1% to break even. Return -2.3% ± 2.1.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 350 | 78.0% | 79.8% | 82.1% | -5.1% ± 2.7 | no edge either way |
| 1.25–1.30 | 194 | 82.5% | 79.0% | 78.9% | +4.5% ± 3.5 | no edge either way |
| 1.30–1.50 | 82 | 69.5% | 76.6% | 75.6% | -8.2% ± 6.8 | no edge either way |
| 1.50–2.00 | 2 | 100.0% | 58.8% | 57.0% | +75.5% ± 15.5 | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 2 | 100.0% | 75.1% | 78.7% | +27.0% ± 1.0 | ahead |
| BOOK | 16 | 75.0% | 78.1% | 79.6% | -7.3% ± 13.8 | no edge either way |
| MARKET | 142 | 81.7% | 79.9% | 80.7% | +1.4% ± 4.0 | no edge either way |
| SAFE | 465 | 77.2% | 79.0% | 80.1% | -3.8% ± 2.4 | no edge either way |
| VALUE | 3 | 100.0% | 57.2% | 60.2% | +66.0% ± 13.1 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 23 | 43.5% | 52.3% | 47.7% | -11.7% ± 22.5 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
