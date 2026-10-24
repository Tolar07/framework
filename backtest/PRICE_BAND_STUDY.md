# PRICE BAND STUDY — the board's record by the price it took

Generated 2026-10-24 21:02Z from `output/picks/picks_*.json` (graded board singles only; study picks and the parallel sharp list are reported separately below).

**All 807 graded board singles**: stated 79.2%, landed 77.2% (calibration error -2.0 points) at an average price of 1.251, which needs 79.9% to break even. Return -3.5% ± 1.9.

The prediction is not the problem. The price is.

## By price band

| band | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| 1.00–1.25 | 440 | 76.8% | 80.0% | 82.2% | -6.6% ± 2.5 | LOSING |
| 1.25–1.30 | 246 | 81.3% | 79.3% | 78.9% | +3.0% ± 3.2 | no edge either way |
| 1.30–1.50 | 117 | 69.2% | 77.0% | 75.6% | -8.6% ± 5.7 | no edge either way |
| 1.50–2.00 | 4 | 100.0% | 57.0% | 54.6% | +83.0% ± 7.7 | ahead |
| 2.00+ | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |

## By tier

| tier | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| BANKER | 3 | 100.0% | 76.1% | 80.0% | +25.0% ± 2.1 | ahead |
| BOOK | 17 | 76.5% | 78.1% | 79.4% | -5.2% ± 13.2 | no edge either way |
| MARKET | 189 | 79.4% | 80.2% | 80.7% | -1.6% ± 3.7 | no edge either way |
| SAFE | 593 | 76.2% | 79.2% | 80.0% | -4.8% ± 2.2 | LOSING |
| VALUE | 5 | 100.0% | 56.3% | 56.9% | +75.8% ± 9.4 | ahead |

## The other two populations

| list | n | landed | stated | break-even | return / unit | reading |
|---|---|---|---|---|---|---|
| study picks (demoted, not sent) | 8 | 75.0% | 78.0% | 78.1% | -2.6% ± 21.9 | no edge either way |
| sharp value list (parallel test) | 31 | 41.9% | 51.6% | 46.9% | -15.8% ± 19.0 | no edge either way |

The sharp list takes a price only when SportyBet pays MORE than the Betfair Exchange's fair odds (`engine/sharp_value.py`), with no most-likely-outcome and no 50% floor. It is the control for the price question: same days, same fixtures, same grader.

## What this does and does not establish

A band's return is evidence only when it is outside ± 2 standard errors of zero; the table says so per row. Nothing here is a demonstrated edge, and a row marked PENDING has no graded pick yet (HR35).
