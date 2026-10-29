# Trading Agent -> Framework knowledge bridge

**Status: proposal, 2026-10-29.** Written by the trading-agent build session (private repo
`Tolar07/trading-agent`). Nothing here changes the framework's picks, stakes, the CLV gate or any
[[Protected Constants.md]] item. Each idea below goes into the framework only through its normal
PR path, and anything touching staking or gates needs the Architect.

The trading bot and the football/basketball framework solve the same problem: find a small edge
in a noisy market, prove it is real, then execute it without giving it away. These methods are
built and tested in trading-agent and map directly onto the framework, for football and NBA alike.

## 1. Count every attempt (deflated Sharpe)

- **Trading:** every parameter set tried (44 so far) counts in the deflated Sharpe
  (Bailey & Lopez de Prado 2014). A result only counts if it would beat the best you'd expect
  from luck across all those tries.
- **Framework:** every market, threshold, filter and league split studied is a "try". A
  both-sides study or a tactics study that tests 30 slices will find a "winner" by luck.
- **Proposed:** add a deflated-Sharpe/deflated-ROI check (per-bet returns) to
  `backtest/` studies and report the number of tries next to every headline result.

## 2. Walk-forward with a purge gap

- **Trading:** parameters are chosen only on data before each test fold, with a 21-day gap so
  nothing from the test period leaks in.
- **Framework:** `engine/tactics_study.py::walk_forward` already steps forward. **Proposed:** add a
  purge gap (e.g. one matchweek / 3 NBA days) between fit and test, so form and odds-move
  features computed over overlapping windows can't leak.

## 3. Challenger vs incumbent on the same events

- **Trading:** a new strategy replaces the live one only if it wins on the *same* out-of-sample
  days and a paired test (Jobson-Korkie with Memmel's correction) gives p < 0.10.
- **Framework:** compare a new model or filter with the current one on the *same fixtures*
  (paired), not on different samples. A paired test is far more sensitive and harder to fool.

## 4. Decision price, arrival price, fill (CLV split in two)

- **Trading:** each order records the decision price (last close), the live quote when sent
  (arrival) and the fill. Slippage = fill vs arrival (execution cost); gap = arrival vs decision
  (what the market did before we acted).
- **Framework:** odds when the pick was made -> odds when the code was booked or placed -> closing odds.
  Splitting CLV the same way shows whether value is lost *before* placement (too slow) or *after*
  (the market disagrees). That says what to fix: speed, or the model.

## 5. Shadow forward test before promotion

- **Trading:** the best new challenger (relative strength + trend, backtest Sharpe 1.06 vs 0.94)
  is NOT traded. It is recorded in shadow on every run and graded weekly on live data until the
  edge is proven.
- **Framework:** the same as the NBA player model's "record only until Architect OK". Use it for
  every new market or filter: shadow-record, grade weekly, promote only on evidence.

## 6. Grade by regime

- **Trading:** each run is labelled with the market regime (trend up/down/mixed, calm/normal/
  stressed volatility), so lessons say *when* a rule works.
- **Framework:** label fixtures by regime too: early/late season, congested schedule, heavy
  favourite slates, NBA back-to-backs. An edge that only exists in one regime should only be
  bet in that regime.

## 7. Size by risk, not by conviction alone

- **Trading:** volatility targeting and equal-risk-contribution weighting stop one asset from
  dominating the risk.
- **Framework:** stake sizing can use the same idea: fractional Kelly scaled down when recent
  per-bet return variance rises, and a cap so no single market (e.g. one league's overs) carries
  most of the variance. Staking is protected, so this is a study proposal for the Architect.

## 8. Watch for edge decay

- **Trading:** the backtest report shows a rolling 3-year Sharpe per strategy, so a fading edge is seen early.
- **Framework:** rolling ROI/CLV per market by season. Published or widely copied edges
  (tipster angles) decay, so retire markets whose rolling edge trends to zero.

## 9. Simple beats clever

- **Trading:** across 44 parameter sets, simple trend and relative-strength rules with
  one or two parameters held up out of sample; complex ones and short-term reversion did not.
- **Framework:** prefer few-parameter rules; every extra filter is another try (see 1).

## How the knowledge will flow (advanced stage)

1. trading-agent's weekly review writes its lessons to `ledger/reviews/` (live since 2026-10-29).
2. Next step (proposal): a short machine-readable `ledger/knowledge.json` with each method's
   status (tested / adopted / rejected, with evidence), which a framework study can read.
3. Framework adoption order (proposed): (1) count tries and deflate, (3) paired challenger tests,
   (4) split CLV into before and after placement. These are research-only, need no
   protected-constant change, and apply to football and NBA alike.

Related: [[Rules.md]], [[Protected Constants.md]], [[Betting-Market-Study-Guide.md]], [[Loops.md]]
