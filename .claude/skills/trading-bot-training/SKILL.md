---
name: trading-bot-training
description: |
  How to train, validate and judge a trading bot or strategy (rules, ML or reinforcement learning) so that
  in-sample luck is not mistaken for an edge. The four-step gate (in-sample excellence, in-sample Monte Carlo
  permutation test, walk-forward, walk-forward permutation test), the seven backtest sins, walk-forward design,
  RL pitfalls and position sizing.
  Use when: building, tuning, retraining, backtesting or promoting any trading strategy or bot (Tolar07/trading-agent:
  T212, Alpaca, IG), judging a backtest someone shows you, or the Architect asks "is this strategy any good?"
  Don't use when: the question is sports betting (use `sports-betting-edge`), or only live order mechanics or broker API.
metadata:
  version: "1.0.0"
  built: "2026-11-04 with youtube-to-skill from 5 videos (transcripts + frames, cross-checked)"
  sources:
    - "neurotrader — How I Develop Trading Strategies | Permutation Tests (https://www.youtube.com/watch?v=NLBXgSmRBgU)"
    - "Darwinex — What is Walk Forward Analysis (https://www.youtube.com/watch?v=WBZ_Vv-iMv4)"
    - "Data Science for Business & Finance — Lopez de Prado ch.11, The Dangers of Backtesting (https://www.youtube.com/watch?v=sGcov6tOQ7k)"
    - "CodeTrading — Reinforcement Learning Trading Bot in Python, EURUSD (https://www.youtube.com/watch?v=oW4hgB1vIoY)"
    - "Spectral Forge Labs — Two Reasons Why Making AI for Day Trading is Hard (https://www.youtube.com/watch?v=fP0PpfxQCMM)"
---

# trading-bot-training

A strategy is guilty until proven innocent. The null hypothesis is **"this strategy is worthless, and the
optimiser found noise"** (neurotrader @ 04:51). Every step below tries to reject that null. Nothing
goes live until all four steps pass.

## Activation rules

- Someone proposes, tunes, retrains or promotes a trading rule, model or bot.
- A backtest, equity curve or Sharpe or profit factor is shown as evidence.
- A strategy that passed before is being re-optimised (each re-use of test data adds selection bias).

## Step-by-step: the four-step gate

0. **Write the strategy as a position signal per bar.**
   - The signal is `1` long, `-1` short, `0` flat.
   - The strategy return per bar is `signal[t] * return[t+1]`, using next-bar returns (log returns, so they sum).
   - Score objective functions (profit factor, Sharpe) on **per-bar returns, not per-trade returns**: more data points
     and more stable estimates (neurotrader @ 00:32–01:04).
   - Costs and a next-bar fill go in from the start: signal at close t, fill at open t+1, spread, commission, funding.
1. **In-sample excellence.** Optimise on the development window only. Ask two questions:
   - Is it excellent? In-sample should look *very* good. Mediocre in-sample means stop or improve the idea now.
   - Is it obviously overfit? Suspiciously perfect results, such as a 100% win rate or a straight line, mean a future
     leak or overfitting. Fix the leak or cut the complexity (@ 03:13–04:18; decision-tree example @ 11:53).
2. **In-sample Monte Carlo permutation test (MCPT).**
   - Permute the bars: shuffle each bar's intrabar moves relative to its open (high/low/close minus open) and,
     separately, the open-to-previous-close gaps. Rebuild prices from the first real bar.
   - This keeps the start/end price, mean, std, skew and kurtosis but destroys real patterns (@ 06:28–09:10).
   - Re-run the **whole optimiser** on each permutation; ≥1,000 permutations (100 is a hard floor).
   - p = (# permutations with objective ≥ real) / N. **Pass: p < 1%.**
   - The worked example passed with p = 0.003, profit factor 1.08 vs a permutation bell centred near 1.03. Seen on
     the histogram frame @ 11:32.
3. **Walk-forward test.** Re-optimise on a rolling training window and trade the next unseen block, then step forward.
   - The example used 4 years of training and re-optimised every 30 days (@ 15:45).
   - Expect worse than in-sample, because no data-mining bias helps it here.
   - Ask whether it is worth trading after costs.
   - Purge or embargo between train and test when labels overlap in time (Lopez de Prado @ 13:37).
4. **Walk-forward permutation test.** Permute only the data *after* the first training fold. Walk forward on each
   permutation and compare.
   - **Pass: p ≤ 5% on one year out of sample, ≤ 1% on two or more years** (@ 19:01).
   - Example: walk-forward profit factor 1.04 with p = 0.22, so **REJECT**. Seen on the frame @ 18:01.
5. **Decide and record.**
   - Write the verdict (KEEP / REJECT), every trial run, the number of parameter sets tried and the p-values to the
     repo's report.
   - Deflate the Sharpe by the number of trials (Lopez de Prado @ 12:00–12:32).
   - A REJECT is final for that idea. Start over; don't tweak until it passes (@ 09:19, 13:04).

## Walk-forward design (Darwinex)

- Classic split: optimisation window ≈ 3× the walk-forward window (frame @ 06:42: ~7.5 y optimisation, ~2.5 y
  walk-forward). It depends on the number of parameters; more parameters need more data.
- A long optimisation window gives many trades and covers every regime (bull, bear, range, high and low volatility).
  But the parameters are a compromise that excels in none of them. A short window is more current but less
  significant. Walk-forward *analysis* means repeated optimise-then-test stages, so you get both (@ 05:07–08:24).
- A short walk-forward block has few trades and weak significance. Judge the joined-up out-of-sample record across
  all folds, never one block.

## The seven backtest sins (check every one; slide @ 02:03)

1. Survivorship bias: today's universe ignores delisted or bankrupt names.
2. Look-ahead bias: using data before it was published (revisions, statement dates, the close you trade at).
3. Storytelling: inventing a reason for a random pattern afterwards.
4. Data mining / snooping: fitting on, or repeatedly peeking at, the test set.
5. Transaction costs ignored (spread, commission, slippage, overnight funding).
6. Outliers: an edge that rests on a few extreme days.
7. Shorting costs ignored (borrow, funding, availability).

## Reinforcement-learning bots (CodeTrading + Spectral Forge)

- Set it up as an env (gym) and an agent (PPO, stable-baselines3):
  - observation = the last N bars × features (30 in the example);
  - actions = flat / long / short × stop-loss and take-profit distance (60/90/120 pips there);
  - reward = trade P&L.
- **If one bar touches both stop-loss and take-profit, count it as a loss.** Bar data can't tell you which hit first
  (@ 08:58–09:30).
- The example's training equity rose but the out-of-sample equity (EURUSD H1, 2023–25) did not hold up. Fewer
  timesteps (10k vs 50k) changed the result. That is overfitting to one history (@ 15:54–17:59).
- Why RL struggles in markets (@ 02:48–12:30):
  - The agent can't affect the next bar, and you can't replay the same day afresh. Each pass over history
    re-learns the same path, so more epochs just mean overfitting.
  - The state space is undefined. OHLC alone and OHLC plus 15 indicators gave the same results.
  - Markets drift, unlike a fixed game board.
- Treat any RL agent as a strategy: it goes through all four steps above, with the trained policy as "the optimiser".

## Position sizing

- Size by fractional Kelly. Full Kelly over-bets when the edge is overestimated; ¼–½ Kelly is the professional norm
  (Unabated, frame "Kelly stake ÷ 4 / ÷ 2").
- In Tolar07 bots, caps and stake rules are the Architect's. This skill never changes them.

## Best practices

- Prefer a **stable plateau** of parameters: pick a reasonable value inside a broad good region and stick with it.
  Optimised look-backs rarely generalise (neurotrader @ 20:07).
- Backtest only after research is finished. A backtest is for **discarding** models, not improving them
  ("backtesting while researching is like drinking and driving", @ 06:34–09:19).
- Use the validation (walk-forward) data sparingly. Every comparison of strategies on the same out-of-sample data
  adds selection bias (@ 14:05–15:11).
- Prefer general models (an asset-class model over one tuned to a single ticker), and bagging (@ 11:27).
- A p-value is a measure; don't make it a target. Fiddling until a test passes defeats it (@ 13:32).

## Common mistakes

- Judging by the in-sample equity curve. A smooth line there is a warning, not a result.
- Re-running walk-forward after every tweak, until the out-of-sample data is effectively in-sample.
- Per-trade metrics from few trades, which are noisy. Use per-bar returns.
- Forgetting the permutation destroys volatility clustering and long memory. A strategy that depends on those can
  pass with an optimistic bias, so treat a pass there as weaker (@ 09:41).
- Auto-captions and screenshots disagree on numbers. Here the transcript said "RSI4" and the code on screen was
  `rsi_14`. Check the code.

## Quality check before calling a strategy KEEP

- [ ] Signal is per bar with a next-bar fill; costs, spread and funding are included.
- [ ] In-sample is excellent and not obviously overfit (no leak).
- [ ] In-sample MCPT p < 1% with ≥ 1,000 permutations (or ≥ 100, stated).
- [ ] Walk-forward is positive after costs and beats the benchmark (buy and hold or the relevant index).
- [ ] Walk-forward MCPT p ≤ 5% (1 y) / ≤ 1% (≥ 2 y).
- [ ] Number of trials recorded; deflated Sharpe ≥ 0.95, or the gap is stated.
- [ ] None of the seven sins present.
- [ ] Verdict and numbers written to the repo report. Live use is the Architect's decision (Tolar07 house rule).

## Evidence table

| Claim | Source @ time | Status |
|---|---|---|
| 4-step process; p < 1% in-sample | neurotrader 00:00, 11:20 | confirmed (histogram frame p = 0.003) |
| WF permutation p 0.22 → reject | neurotrader 18:29 | confirmed (frame: WF profit factor 1.04, 2020) |
| Per-bar returns over per-trade | neurotrader 01:04 | said only (cites *Testing and Tuning Market Trading Systems*) |
| Optimisation ≈ 3× walk-forward | Darwinex 02:54 | confirmed (timeline frame 7.5 y : 2.5 y) |
| Seven sins list | Lopez de Prado ch.11 talk 02:41 | confirmed (slide) |
| Backtest is not a research tool | same 06:34 | said only |
| Ambiguous bar = loss; PPO setup | CodeTrading 08:58, 10:37 | confirmed (code frame); captions were an auto-translation |
| Indicator RSI length | CodeTrading 03:42 | **contradicted**: captions "RSI4", code shows `rsi_14` (length = 14) |
| RL limits: non-interactive env, undefined state | Spectral Forge 02:48, 09:05 | said only (talking head) |
| ¼ Kelly | Unabated 05:30 | confirmed (graphic) |

**Tolar07 note:** trading-agent already does walk-forward with a 21-day purge, costs and deflated Sharpe
(`docs/backtest-report.md`). The gaps this skill adds are the two permutation tests and the parameter-plateau
check. They are proposed as record-only issues; promotion and stakes stay the Architect's.
