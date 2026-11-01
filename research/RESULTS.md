# RESEARCH RESULTS — every hypothesis and its walk-forward verdict

Written by `research/runner.py` from `memory/hypotheses.jsonl`. Bet rules: £1 paper bets on every graded universe game at the first price, earlier half vs later half, closing-line value against the last price. Features: walk-forward against the model (`backtest/FEATURES_STUDY.md`). **accepted** means queued as a SHADOW strategy for the experiment engine (`memory/strategy_queue.jsonl`) — paper only until the engine promotes it on 100+ graded bets. Nothing here stakes money.

| id | idea | test | status | result | tested |
|---|---|---|---|---|---|
| H001 | Back any 1X2 side SportyBet prices 3%+ above Matchbook's fair price (margin removed) at first look | bet_rule: 1x2:home, 1x2:draw, 1x2:away | accepted | 199 bets, hit 0.367, return +19.4% ± 14.1%; later half +28.5%, CLV +17.3% | 2026-10-20 |
| H002 | Favourite-longshot bias: short home favourites (1.20-1.50) return more per unit than the margin implies | bet_rule: 1x2:home | rejected | 840 bets, hit 0.712, return -3.2% ± 2.1%; later half -4.4%, CLV -0.1% | 2026-11-01 |
| H003 | SportyBet's closing Over 2.5 price knows something the model doesn't — lean the model's Over 2.5 toward it | feature: over 2.5 / soft close gap | accepted | 658 scored, gain +0.00380 ± 0.00165 | 2026-11-01 |
