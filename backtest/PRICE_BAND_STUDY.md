# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-11-02 06:52Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 1149 graded board singles**: stated 79.0%, landed 77.1% (calibration error -1.9 points) at an average price of 1.251, which needs 79.9% to break even. Return -3.6% ± 1.6.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 631 | 77.5% | 79.9% | 82.2% | -5.7% ± 2.0 | LOSING |
| 1.25–1.30 | 347 | 79.3% | 78.9% | 78.9% | +0.5% ± 2.8 | no edge either way |
| 1.30–1.50 | 164 | 71.3% | 76.7% | 75.6% | -5.7% ± 4.7 | no edge either way |
| 1.50–2.00 | 7 | 71.4% | 56.2% | 54.3% | +30.0% ± 33.8 | no edge either way |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 3 | 100.0% | 76.1% | 80.0% | +25.0% ± 2.1 | ahead |
| BOOK | 24 | 75.0% | 77.7% | 79.3% | -6.3% ± 11.3 | no edge either way |
| MARKET | 218 | 78.0% | 80.0% | 80.7% | -3.4% ± 3.5 | no edge either way |
| SAFE | 896 | 76.9% | 79.0% | 80.1% | -4.1% ± 1.8 | LOSING |
| VALUE | 8 | 75.0% | 55.9% | 55.7% | +32.1% ± 29.4 | no edge either way |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 67 | 44.8% | 51.8% | 47.0% | -6.6% ± 13.3 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
