# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-24 05:59Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 697 graded board singles**: stated 79.2%, landed 78.0% (calibration error -1.2 points) at an average price of 1.249, which needs 80.1% to break even. Return -2.6% ± 2.0.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 389 | 77.9% | 80.0% | 82.2% | -5.3% ± 2.6 | LOSING |
| 1.25–1.30 | 215 | 81.4% | 79.2% | 78.9% | +3.1% ± 3.4 | no edge either way |
| 1.30–1.50 | 90 | 70.0% | 76.8% | 75.6% | -7.6% ± 6.4 | no edge either way |
| 1.50–2.00 | 3 | 100.0% | 57.5% | 55.1% | +81.3% ± 10.7 | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 2 | 100.0% | 75.1% | 78.7% | +27.0% ± 1.0 | ahead |
| BOOK | 16 | 75.0% | 78.1% | 79.6% | -7.3% ± 13.8 | no edge either way |
| MARKET | 188 | 79.3% | 80.2% | 80.7% | -1.7% ± 3.7 | no edge either way |
| SAFE | 487 | 77.4% | 79.1% | 80.1% | -3.5% ± 2.4 | no edge either way |
| VALUE | 4 | 100.0% | 56.6% | 57.9% | +72.8% ± 11.4 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 23 | 43.5% | 52.3% | 47.7% | -11.7% ± 22.5 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
