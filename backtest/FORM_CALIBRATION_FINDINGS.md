# Form-weighting calibration backtest — findings

**Date:** 2026-09-30
**Harness:** `backtest/form_calibration.py` (reproducible)
**Question:** Does weighting recent form more heavily (Dixon-Coles time-decay,
`half_life_days`) make the model's probabilities sharper out-of-sample?

## Verdict: NO. Keep time-decay OFF (the current default).

Time-decay weighting did **not** improve calibration. Brier score and log-loss
were flat-to-worse at every half-life, and got **monotonically worse as the
decay shortened** (more form-reactive), on **both** leagues tested. No setting
beat the equal-weight baseline on Brier **and** log-loss, so per the
pre-declared decision rule, nothing ships.

## Results (walk-forward, out-of-sample, no look-ahead)

Two completed seasons each (2024/25 + 2025/26), lookback window 550 days.

### Eredivisie (521 matches scored)
| half-life | Brier ↓ | LogLoss ↓ | Acc | vs baseline |
|-----------|---------|-----------|------|-------------|
| **off (baseline)** | **0.5933** | **0.9951** | 50.5% | — |
| 365 | 0.5932 | 0.9951 | 51.1% | −0.0001 (tie) |
| 180 | 0.5942 | 0.9966 | 51.1% | +0.0009 worse |
| 90  | 0.5984 | 1.0027 | 50.1% | +0.0052 worse |

### Ekstraklasa (519 matches scored)
| half-life | Brier ↓ | LogLoss ↓ | Acc | vs baseline |
|-----------|---------|-----------|------|-------------|
| **off (baseline)** | **0.6569** | **1.0906** | 43.9% | — |
| 365 | 0.6583 | 1.0926 | 43.5% | +0.0014 worse |
| 180 | 0.6612 | 1.0968 | 43.7% | +0.0043 worse |
| 90  | 0.6701 | 1.1104 | 43.0% | +0.0132 worse |

## Why

Dixon-Coles needs enough matches per team to estimate attack/defence. Down-
weighting older matches shrinks the effective sample, so the ratings get noisier.
The recent-form signal gained is smaller than the variance added — a bias–
variance loss. Season-long ratings already capture team strength; over-weighting
the last few games mostly adds noise. This is why the current default (equal
weighting) is correct, and it is now evidenced rather than assumed.

## Scope & caveats (HR35)

- Measures **calibration** (probability sharpness), the necessary condition for
  edge — not CLV/ROI directly. But if the probabilities don't sharpen, no CLV
  can come from this change, so it is a sound basis to not ship.
- Two leagues, ~520 scored matches each. The signal (monotonic worsening on
  both) is consistent, but re-running on more leagues/seasons is cheap:
  `python backtest/form_calibration.py --leagues "Danish Superliga" "Belgian Pro League"`.
- Only tests **time-decay** form. It does **not** test xG-weighting (no free xG
  for these leagues) or a form covariate on λ (higher overfit risk) — separate
  experiments if ever pursued.

## What this does NOT overturn

The standings/recent-form **context** feature (`engine/form.py`) stays. It is a
ranking + caution signal, not a probability change, so this result — which is
purely about probability weighting — does not contradict it.
