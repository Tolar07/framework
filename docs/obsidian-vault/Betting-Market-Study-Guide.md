# Practical Sports Betting Market Study Guide

> **Progressive curriculum from market structure to live implementation.**  
> Designed to be worked through sequentially; each level builds on the previous.

---

## 1. MARKET STRUCTURE & ECOSYSTEM MAPPING

| Layer | Participants | Role | Where Inefficiency Lives |
|-------|--------------|------|-------------------------|
| **Sharps** | Professional bettors, syndicates, originators | Move lines early with large, informed volume | Opening lines before sharp action |
| **Books** | Pinnacle, Bet365, SportyBet, etc. | Set opening lines, manage risk, balance books | Margin structure, limit speed, market-type pricing |
| **Exchanges** | Betfair, Matchbook | Peer-to-peer, no house margin (commission only) | Liquidity gaps, cross-exchange arbs |
| **Public** | Recreational bettors | Late money, bias-driven (favorites, home, recent form) | Closing line vs. true probability |

### Line Lifecycle
```
Opening → Sharp Action (steam/reverse) → Public Action → Closing → Post-Closing Adjustment
```

### Key Metrics to Track
- **Hold %** — Book's actual margin after settlement
- **Handle** — Total volume wagered
- **Sharp %** — Proportion of volume from identified sharps
- **Limit Speed** — How fast books cut winning players
- **Margin by Market Type** — 1X2 vs. totals vs. props vs. live

---

## 2. DATA SOURCES & TOOLS

### Free / Low-Cost
| Category | Sources | Notes |
|----------|---------|-------|
| **Odds Comparison** | OddsPortal, OddsChecker, Flashscore, BetBrain | Snapshot comparison, some historical |
| **Historical Odds** | Football-Data.co.uk (free CSVs), OddsPortal archive | Gold standard for backtesting |
| **Statistics** | FBref, Understat, FotMob, Sofascore, WhoScored | xG, shot maps, advanced metrics |
| **Team News** | Official club sites, beat reporters, Twitter lists | Lineup leaks, injuries, rotation |
| **Line Movement** | Pinnacle line history (proxy for sharp action) | Pinnacle = sharpest book globally |
| **Prediction Markets** | Polymarket, Kalshi | Public order books, different participant pool |
| **Exchange Data** | Betfair API (free tier), Matchbook API | Real-time liquidity, traded volume |

### Paid / Professional
| Category | Sources | Use Case |
|----------|---------|----------|
| **Odds Feeds** | The Odds API, Sportradar, BetGenius, Betfair API (paid) | Live automation, breadth |
| **Advanced Stats** | Opta, StatsBomb, StatsPerform, Second Spectrum | xG, tracking data, event streams |
| **Historical DBs** | Betfair historical, Pinnacle closing line archive | Rigorous backtesting |
| **Sharp Signals** | SportsInsights, BetStamp, VSIN, SharpSide | Line movement classification |
| **Modeling** | Python/R with Poisson, Dixon-Coles, Elo, xG, Ensembles | Custom model development |

---

## 3. ANALYTICAL FRAMEWORKS TO MASTER

### A. Probability Modeling
| Model | Core Idea | OLP XDV Implementation |
|-------|-----------|------------------------|
| **Dixon-Coles** | Bivariate Poisson with low-score correction | `engine/dixon_coles.py` — FIT_VERSION=4, BUG1-BUG8 fixes |
| **Elo Ratings** | Sequential skill updates from results | `engine/elo.py` — cross-league blend weight optimization |
| **xG / Expected Goals** | Chance quality from shot data | `data/xg_source.py` — Big-5 leagues only |
| **Ensemble / Consensus** | Weighted combination of independent models | `engine/consensus.py` — majority vote + CLV-weighted ensemble |
| **Calibration** | Platt scaling (logit), isotonic regression | `engine/recalibration.py` — flat nudge + Platt, evidence-gated |
| **Backtesting** | Walk-forward, out-of-sample, CLV verification | `clv/clv_logger.py` — CL-LIVE, CL-ARCHIVE, CL-PM |

### B. Market Analysis
- **De-vigging Methods**: Multiplicative, additive, Shin, power — each has bias trade-offs
- **Implied Probability**: `1 / decimal_odds` (canonical in OLP XDV per HR30)
- **Canonical Edge**: `model_prob - implied_prob` — selection metric for ID405
- **CLV Calculation**: `odds_taken / odds_closing - 1` — captured at multiple paths
- **Market Efficiency Tests**: Favorite-longshot bias, home bias, recency bias

### C. Portfolio / Bankroll
- **Kelly Criterion**: `f = (bp - q) / b` — fractional variants for safety
- **Correlated Bet Sizing**: Adjust for dependent outcomes
- **Drawdown Modeling**: Ruin probability via Monte Carlo
- **Multi-Book Optimization**: Net EV after commission/fees
- **Tax / Fee Impact**: Model on post-cost EV

---

## 4. PRACTICAL EXERCISES (Progressive Difficulty)

### Level 1: Observation (Weeks 1-2)
- [ ] Track opening vs. closing lines for 50 matches across 3 leagues
- [ ] Calculate implied probabilities and de-vig for each market
- [ ] Identify which markets move most/least (1X2, totals, Asian handicap)
- [ ] Log: sport, league, market, open, close, movement direction, magnitude

### Level 2: Modeling (Weeks 3-6)
- [ ] Build Dixon-Coles model on 2+ seasons of one league (`dixon_coles.py`)
- [ ] Build Elo model on same data (`elo.py`)
- [ ] Compare model probabilities vs. de-vigged market probabilities
- [ ] Calculate edge (`edge_diff`) for every match
- [ ] Paper trade: log hypothetical bets where edge > 2%
- [ ] Track CLV for every paper bet (`clv_logger.py`)

### Level 3: Market Making (Weeks 7-10)
- [ ] Simulate bookmaker: set opening lines, apply margin, adjust on "action"
- [ ] Test sharp detection: flag accounts with positive CLV
- [ ] Optimize margin structure by market type
- [ ] Stress test: what happens when sharps hit early lines?

### Level 4: Live Integration (Weeks 11+)
- [ ] Connect to live odds feed (The Odds API free tier)
- [ ] Automate model retraining weekly
- [ ] Automate CLV logging at kickoff
- [ ] Build alerting: edge > threshold + line not moved > X%
- [ ] Backtest full pipeline on historical data

---

## 5. KEY CONCEPTS TO INTERNALIZE (Flashcard Style)

| Concept | Formula / Definition |
|---------|---------------------|
| **Overround** | `sum(1/odds_i) - 1` |
| **De-vig (Multiplicative)** | `p_i = (1/odds_i) / sum(1/odds_j)` |
| **Kelly Fraction** | `f = (p*b - q) / b` where `b = odds - 1` |
| **CLV** | `(odds_taken / odds_closing - 1) * 100` |
| **Poisson PMF** | `P(X=k) = λ^k e^{-λ} / k!` |
| **Dixon-Coles Tau** | Correction for 0-0, 0-1, 1-0, 1-1 scores |
| **Elo Update** | `R_new = R_old + K * (S - E)` |
| **Platt Scaling** | `p_cal = sigmoid(a + b * logit(p_raw))` |
| **Fav-Longshot Bias** | Implied prob > true prob for longshots |
| **Reverse Line Move** | Line moves opposite to ticket % |
| **Steam Move** | Synchronized line movement across multiple books |

---

## 6. RECOMMENDED READING / FOLLOWING

### Books (Foundational)
- **"Sharp Sports Betting"** — Stanford Wong
- **"The Logic of Sports Betting"** — Ed Miller & Matthew Davidow
- **"Risk Intelligence"** — Dylan Evans
- **"Fortune's Formula"** — William Poundstone (Kelly criterion)
- **"Trading Bases"** — Joe Peta (market making perspective)

### Blogs / Newsletters
- [Pinnacle Betting Resources](https://pinnacle.com/en/betting-resources)
- [Joseph Buchdahl — Football-Data.co.uk blog](https://www.football-data.co.uk/blog.php)
- [@PlusEVAnalytics](https://twitter.com/PlusEVAnalytics) (Twitter/X)
- [@RufusPeabody](https://twitter.com/RufusPeabody) (sharp bettor)
- [@GingeBets](https://twitter.com/GingeBets) (market structure)
- Sports Betting Analytics substack

### Academic / Technical
- Dixon & Coles (1997) — "Modelling Association Football Scores"
- Maher (1982) — "Modelling Association Football Scores"
- Rue & Salvesen (2000) — "Prediction and Retrospective Analysis"
- Koopman & Lit (2015) — "A Dynamic Bivariate Poisson Model"
- Angelini & De Angelis (2019) — "Efficiency of Football Betting Markets"

---

## 7. OLP XDV SPECIFIC STUDY PATH

Since you have this framework, study IT as a case study:

- [ ] Read `engine/dixon_coles.py` — every line, understand BUG1-BUG8 fixes
- [ ] Read `engine/elo.py` — understand cross-league blend weight optimization
- [ ] Read `engine/consensus.py` — majority vote + CLV-weighted ensemble
- [ ] Read `engine/mes.py` — canonical edge = `model_prob - implied_prob`
- [ ] Read `clv/clv_logger.py` — CL-LIVE, CL-ARCHIVE, CL-PM capture paths
- [ ] Read `clv/phase3_gate.py` — 30 legs + positive mean CLV + Architect sign-off
- [ ] Read `engine/recalibration.py` — flat nudge + Platt scaling, evidence gates
- [ ] Run `orchestrator_DEPRECATED.py --all --season 2526` weekly
- [ ] Compare framework output vs. your own manual analysis

---

## 8. RED FLAGS — AVOID THESE RABBIT HOLES

| ❌ Anti-Pattern | Why It Fails |
|----------------|--------------|
| "Guaranteed profit" systems / arbitrage services | Limits hit fast, not scalable |
| Tipster subscriptions | Survivorship bias, no edge verification |
| Martingale / progression staking | Mathematical ruin guaranteed |
| Single-season backtests | Insufficient sample, overfitting |
| Ignoring CLV / only tracking win/loss | Win% ≠ EV; CLV is the truth |
| Betting without de-vigging | Edge calculation systematically wrong |
| Overfitting models | Too many parameters, no out-of-sample test |
| Emotional attachment to teams/leagues | Bias destroys objectivity |

---

## How to Use This Guide

1. **Start at Level 1** — Do not skip observation. You cannot model what you haven't watched.
2. **One league at a time** — Master EPL or Bundesliga before expanding.
3. **Paper trade for 100+ bets** before any real money. Track CLV religiously.
4. **Use OLP XDV as your laboratory** — It embodies professional architecture (CLV gate, evidence-gated recalibration, Architect sign-off). Compare your manual analysis against its output.
5. **Review weekly** — What moved? What did the model miss? What did the market know?

> **The market teaches those who listen. The framework encodes what the market taught.**  
> Your job is to close the gap between the two.