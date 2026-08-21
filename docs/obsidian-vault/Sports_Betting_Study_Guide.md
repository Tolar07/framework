# Sports Betting Market Study Guide — Comprehensive Skill-Building Path

> **Purpose:** A practical, actionable curriculum for studying the entire sports betting market — from data sources to analytical frameworks to practical exercises. Built for educational/skill-building purposes.
>
> **Authoritative Location:** `olp_xdv_agent/olp_xdv/docs/obsidian-vault/Sports_Betting_Study_Guide.md` (git-tracked canonical vault)
>
> **Related:** `[[OLP XDV.md]]` | `[[Architecture.md]]` | `[[Protected Constants.md]]` | `[[Vault-Memory-Index.md]]`

---

## 1. MARKET STRUCTURE & ECOSYSTEM MAPPING

### Layers of the Market
| Layer | Participants | Characteristics | Information Advantage |
|-------|--------------|-----------------|----------------------|
| **Sharps / Originators** | Syndicates, professional bettors, model-driven funds | Move lines early; bet at limits; positive CLV | Private models, proprietary data, speed |
| **Sharp Books** | Pinnacle, Betfair Exchange, Bookmaker.eu | High limits, low margins, fast limits | Market-making risk management |
| **Recreational Books** | DraftKings, FanDuel, Bet365, William Hill, local books | Lower limits, higher margins, slower limits | Recreational flow, marketing spend |
| **Public / Retail** | Casual bettors, fans, tout followers | Bet late; follow narratives; negative CLV | None (disadvantaged) |

### Line Lifecycle
```
Opening Line (Sharp Books) 
    ↓ Sharp Action (steam moves, limits hit)
Adjusted Line (Sharp Books)
    ↓ Public Action (recreational flow)
Closing Line (All Books)
    ↓ Result
CLV Measurement
```

### Where Inefficiencies Exist

| Stage | Inefficiency | Exploitable? |
|-------|--------------|--------------|
| **Opening** | Books copy each other; slow to adjust for news | ✅ Yes — be first with info |
| **Sharp Action** | Limits prevent full correction; stale lines at slow books | ✅ Yes — line shopping |
| **Public Action** | Favorite-longshot bias; home bias; recency bias | ✅ Yes — fade public |
| **Closing** | Market efficient; CLV ≈ 0 for most | ❌ Hard — need better model |

### Key Metrics to Track
- **Hold %** = (Handle - Payouts) / Handle — book's actual margin
- **Handle** = Total dollars wagered — market depth indicator
- **Sharp %** = Sharp handle / Total handle — market quality
- **Limit Speed** = Time from open to limit hit — sharp respect
- **Margin by Market Type** — Moneyline vs Spread vs Total vs Props

---

## 2. DATA SOURCES & TOOLS

### Free / Low-Cost

| Category | Source | Access | Notes |
|----------|--------|--------|-------|
| **Odds Comparison** | OddsPortal, OddsChecker, Flashscore, BetBrain | Web | Historical archives limited |
| **Historical Odds** | Football-Data.co.uk | CSV download | 20+ seasons, major Euro leagues, free |
| **Historical Odds** | OddsPortal Archive | Web/CSV | Requires registration |
| **Team/Player Stats** | FBref (StatsBomb), Understat, FotMob, Sofascore, WhoScored | Web/API | xG, xA, progressive stats |
| **Team News** | Official club sites, beat reporters (Twitter), Fabrizio Romano, The Athletic | Web | Speed matters |
| **Line Movement** | Pinnacle line history (proxy for sharp action) | Web/API | Best sharp signal |
| **Prediction Markets** | Polymarket, Kalshi | API/Web | Public order books, different incentives |
| **Exchange Data** | Betfair API (free tier), Matchbook API | API | Real volume, lay prices |

### Paid / Professional

| Category | Source | Cost Tier | Use Case |
|----------|--------|-----------|----------|
| **Odds Feeds** | The Odds API, Sportradar, BetGenius, Betfair API (paid) | $100–$5000+/mo | Live odds, historical, settling |
| **Advanced Stats** | Opta, StatsBomb, StatsPerform, Second Spectrum | $10k–$1M+/yr | Event data, tracking data |
| **Historical DBs** | Betfair Historical, Pinnacle Closing Line Archive | Varies | Backtesting at scale |
| **Sharp Signals** | SportsInsights, BetStamp, VSIN, SharpSide | $50–$500/mo | Steam moves, reverse line movement |
| **Modeling Platforms** | R/Python (Poisson, Dixon-Coles, Elo, xG) | Free (dev time) | Build your own edge |

### OLP XDV Internal Sources
- `engine/dixon_coles.py` — Bivariate Poisson with tau correction
- `engine/elo.py` — Cross-league Elo with blend optimization
- `engine/consensus.py` — Majority vote + CLV-weighted ensemble
- `clv/clv_logger.py` — CL-LIVE, CL-ARCHIVE, CL-PM capture paths
- `sports-skills` package (4 skills: football-data, betting, markets, polymarket)

---

## 3. ANALYTICAL FRAMEWORKS TO MASTER

### A. Probability Modeling

#### Dixon-Coles / Bivariate Poisson (Goals-Based)
```python
# Core: P(X=x, Y=y) = Pois(x|λ₁) × Pois(y|λ₂) × τ(x,y)
# τ corrects for low-score dependence (0-0, 0-1, 1-0, 1-1)
# Parameters: attack/defense strength per team, home advantage, ρ
```
- **OLP XDV Implementation:** `engine/dixon_coles.py` — study BUG1-BUG8 fixes
- **Key Papers:** Dixon & Coles (1997), Rue & Salvesen (2000), Koopman & Lit (2015)

#### Elo Ratings (Result-History Based)
```python
# R_new = R_old + K × (S - E)
# S = actual result (1, 0.5, 0), E = expected from logistic curve
# Cross-league: blend domestic Elo with continental/global Elo
```
- **OLP XDV Implementation:** `engine/elo.py` — study blend weight optimization

#### Expected Goals / xG (Chance-Quality Based)
- Shot location, angle, body part, defensive pressure → probability
- Team xG for/against → attack/defense strength
- **Limitation:** Understat covers top-5 leagues only

#### Ensemble / Consensus Methods
- Combine independent models (DC, Elo, xG, market)
- Weight by out-of-sample CLV performance
- **OLP XDV:** `engine/consensus.py` — majority vote + CLV-weighted ensemble

#### Calibration
- **Platt Scaling:** `p_cal = sigmoid(a + b × logit(p_raw))`
- **Isotonic Regression:** Non-parametric, monotonic
- **OLP XDV:** `engine/recalibration.py` — flat nudge + Platt, evidence gates

#### Backtesting Protocol
- **Walk-forward:** Train on seasons 1-N, test on N+1, retrain
- **Out-of-sample:** Never peek at test period
- **CLV Verification:** Edge must persist to closing line

### B. Market Analysis

#### De-Vigging Methods
| Method | Formula | Best For |
|--------|---------|----------|
| **Multiplicative** | `p_i = p_i_raw / Σ(p_j_raw)` | Standard markets |
| **Additive** | `p_i = p_i_raw - margin/n` | High-margin props |
| **Shin** | Model insider proportion | Sharp-heavy markets |
| **Power** | `p_i = p_i_raw^k / Σ(p_j_raw^k)` | Flexible curvature |

#### Implied Probability Extraction
```python
# Decimal odds → implied prob
p_implied = 1 / odds_decimal
# Remove margin (de-vig) → true market probability
```

#### Line Movement Classification
| Type | Pattern | Signal |
|------|---------|--------|
| **Steam** | Synchronized move across sharp books | Sharp money |
| **Reverse** | Line moves opposite ticket % | Sharp on other side |
| **Drift** | Slow move one direction | Public/liquidity |
| **Late** | Move in final hour | Injury news, weather |

#### CLV Calculation
```
CLV = (odds_taken / odds_closing - 1) × 100
# Positive CLV = beat the close = long-term profit indicator
# Statistical significance: t-test on CLV series
```

#### Market Efficiency Tests
- Favorite-longshot bias: `implied_prob > true_prob` for longshots
- Home bias: Home teams overbet
- Recency bias: Last game overweighted

### C. Portfolio / Bankroll Management

#### Kelly Criterion
```
f* = (bp - q) / b = edge / odds
# Fractional Kelly: f = fraction × f* (0.25–0.5 typical)
```

#### Correlated Bets
- Same match markets (ML + O2.5 + BTTS) → correlation matrix
- Optimal sizing: solve quadratic program with covariance

#### Drawdown & Ruin
```
P(ruin) ≈ exp(-2 × edge × bankroll / variance)
# Track max drawdown, recovery time
```

#### Multi-Book Optimization
- Line shopping = free EV
- Account for limits, fees, tax, commission

---

## 4. PRACTICAL EXERCISES (Progressive Difficulty)

### Level 1: Observation (Weeks 1-2)
- [ ] Track opening vs closing lines for **50 matches** across **3 leagues** (e.g., EPL, La Liga, Bundesliga)
- [ ] Calculate implied probabilities and de-vig for each market (ML, Spread, Total)
- [ ] Identify which markets move most/least (record: sport, league, market, open, close, movement direction, magnitude)
- [ ] Classify each move: steam / reverse / drift / late
- [ ] Note: Which books move first? Which lag?

### Level 2: Modeling (Weeks 3-6)
- [ ] Build **Dixon-Coles model** on 2+ seasons of one league (use Football-Data.co.uk)
- [ ] Build **Elo model** on same data (experiment with K, home advantage, blend weights)
- [ ] Compare model probabilities vs de-vigged market probabilities for every match
- [ ] Calculate edge: `model_prob - market_prob` for every match
- [ ] **Paper trade:** Log hypothetical bets where `edge > 2%` (Kelly fraction 0.25)
- [ ] Track **CLV for every paper bet** — record odds_taken, odds_closing, result

### Level 3: Market Making (Weeks 7-10)
- [ ] Simulate bookmaker: set opening lines, apply margin, adjust on "action"
- [ ] Implement sharp detection: flag accounts with positive CLV over 100+ bets
- [ ] Optimize margin structure by market type (ML: 2%, Spread: 4.5%, Props: 8%+)
- [ ] Stress test: What happens when sharps hit early lines? (Simulate limit speed)

### Level 4: Live Integration (Weeks 11+)
- [ ] Connect to live odds feed (**The Odds API free tier**: 500 req/day)
- [ ] Automate model retraining weekly (rolling window)
- [ ] Automate CLV logging at kickoff (capture closing line from Pinnacle)
- [ ] Build alerting: `edge > threshold` AND `line_not_moved > X%` (avoid stale lines)
- [ ] **Backtest full pipeline** on historical data — simulate live decisions

---

## 5. KEY CONCEPTS — FLASHCARD STYLE

Create Anki cards or notes for each:

| Concept | Formula / Definition |
|---------|---------------------|
| **Overround** | `Σ(1/odds_i) - 1` |
| **De-vig (Multiplicative)** | `p_i = (1/odds_i) / Σ(1/odds_j)` |
| **Kelly Fraction** | `f* = (p × b - q) / b = edge / odds` |
| **CLV** | `CLV = (odds_taken / odds_closing - 1) × 100` |
| **Poisson PMF** | `P(X=k) = λ^k × e^{-λ} / k!` |
| **Dixon-Coles τ** | `τ(0,0)=1-λ₁λ₂ρ`, `τ(0,1)=1+λ₁ρ`, `τ(1,0)=1+λ₂ρ`, `τ(1,1)=1-ρ`, else 1 |
| **Elo Update** | `R_new = R_old + K × (S - E)` where `E = 1/(1+10^((R_opp-R)/400))` |
| **Platt Scaling** | `p_cal = 1 / (1 + exp(a + b × logit(p_raw)))` |
| **Favorite-Longshot Bias** | Longshots: implied prob > true prob; Favorites: implied prob < true prob |
| **Reverse Line Movement** | Line moves toward Team A, but >60% tickets on Team B |
| **Steam Move** | Same line move at Pinnacle + Bookmaker + Betfair within 60 seconds |

---

## 6. RECOMMENDED READING / FOLLOWING

### Books (Foundational)
- [ ] **"Sharp Sports Betting"** — Stanford Wong
- [ ] **"The Logic of Sports Betting"** — Ed Miller & Matthew Davidow
- [ ] **"Risk Intelligence"** — Dylan Evans
- [ ] **"Fortune's Formula"** — William Poundstone (Kelly criterion history)
- [ ] **"Trading Bases"** — Joe Peta (market-making perspective)

### Blogs / Newsletters
- [ ] **Pinnacle Betting Resources** — pinnacle.com/en/betting-resources
- [ ] **Joseph Buchdahl** — Football-Data.co.uk blog
- [ ] **@PlusEVAnalytics** (Twitter/X)
- [ ] **@RufusPeabody** (sharp bettor)
- [ ] **@GingeBets** (market structure)
- [ ] **Sports Betting Analytics** (Substack)

### Academic / Technical Papers
- [ ] Dixon & Coles (1997) — "Modelling Association Football Scores"
- [ ] Maher (1982) — "Modelling Association Football Scores"
- [ ] Rue & Salvesen (2000) — "Prediction and Retrospective Analysis"
- [ ] Koopman & Lit (2015) — "A Dynamic Bivariate Poisson Model"
- [ ] Angelini & De Angelis (2019) — "Efficiency of Football Betting Markets"

---

## 7. OLP XDV SPECIFIC STUDY PATH

Since you have this framework, study IT as a case study:

### Core Engine
- [ ] Read `engine/dixon_coles.py` — **every line**, understand BUG1-BUG8 fixes
- [ ] Read `engine/elo.py` — understand cross-league blend weight optimization
- [ ] Read `engine/consensus.py` — majority vote + CLV-weighted ensemble
- [ ] Read `engine/mes.py` — canonical edge = `model_prob - implied_prob`

### CLV & Publish Gate
- [ ] Read `clv/clv_logger.py` — CL-LIVE, CL-ARCHIVE, CL-PM capture paths
- [ ] Read `clv/phase3_gate.py` — **30 legs + positive mean CLV + Architect sign-off**
- [ ] Read `engine/recalibration.py` — flat nudge + Platt scaling, evidence gates

### Operations
- [ ] Run `orchestrator_DEPRECATED.py --all --season 2526` weekly
- [ ] Compare framework output vs your own manual analysis
- [ ] Study `data/` pipeline: ingestion → features → models → consensus → MES → CLV log

### Protected Constants (Never Modify — Study Only)
- `ARCHITECT_SIGNOFF` logic — `clv/phase3_gate.py`
- CLV gate thresholds (12/30 legs, positive mean) — `clv/phase3_gate.py`
- Capital deployment logic — `config/assert_paper_only()`
- Softness tier defaults (currently open) — `engine/softness.py`
- ID405 override (away wins deployable) — `engine/filters.py`

---

## 8. RED FLAGS — AVOID THESE RABBIT HOLES

| ❌ Avoid | Why |
|----------|-----|
| "Guaranteed profit" systems / arbitrage services | Limits hit fast; not scalable |
| Tipster subscriptions | Survivorship bias; no verifiable track record |
| Martingale / progression staking | Mathematical certainty of ruin |
| Single-season backtests | Insufficient sample; overfitting risk |
| Ignoring CLV / only tracking win/loss | Win% ≠ profit; CLV is the truth |
| Betting without de-vigging | Edge calculation wrong by margin amount |
| Overfitting models | Too many parameters, no out-of-sample test |
| Emotional attachment to teams/leagues | Bias destroys edge |
| Chasing losses | Tilt = negative EV |
| Betting markets you don't model | Information asymmetry against you |

---

## 9. WEEKLY REVIEW TEMPLATE

Every Sunday, log:

```markdown
## Week N Review

### Models
- Dixon-Coles log-loss: ___
- Elo log-loss: ___
- Consensus log-loss: ___
- Best model this week: ___

### Paper Trading
- Bets placed: ___
- Avg edge: ___%
- CLV (mean): ___%
- CLV (+ve count): ___/___
- P&L (units): ___

### Market Observations
- Biggest line move: ___ (league, match, magnitude)
- Sharp action detected: ___ matches
- Public bias observed: ___

### Adjustments for Next Week
- Model retrain: [ ] Yes / [ ] No
- Parameter change: ___
- New data source: ___
```

---

## 10. PROGRESSION CHECKLIST

| Milestone | Target | Status |
|-----------|--------|--------|
| Understand market structure | Explain sharp→book→public flow | ☐ |
| De-vig any market | Calculate true probs from odds | ☐ |
| Build working Dixon-Coles | Log-loss < market baseline | ☐ |
| Build working Elo | Log-loss < market baseline | ☐ |
| Ensemble beats components | Consensus log-loss < min(DC, Elo) | ☐ |
| Positive CLV paper trading | 100+ bets, mean CLV > 0 | ☐ |
| Statistically significant CLV | t-test p < 0.05 on CLV series | ☐ |
| Live pipeline operational | Auto-retrain, auto-CLV, alerts | ☐ |
| Beat closing line consistently | 500+ bets, positive CLV | ☐ |
| Framework audit complete | Understand every OLP XDV module | ☐ |

---

## Appendix: Quick Commands Reference

```bash
# OLP XDV Pipeline
cd olp_xdv_agent/olp_xdv
python -m olp_xdv                    # Run agent
python orchestrator_DEPRECATED.py --all --season 2526  # Full pipeline
pytest                               # Run tests

# Sports Skills (installed in .claude/skills/)
py -3.12 -m sports_skills football get_competitions
py -3.12 -m sports_skills betting devig --odds "2.10 3.40 3.60"
py -3.12 -m sports_skills betting kelly --prob 0.55 --odds 2.10
py -3.12 -m sports_skills markets arbitrage --event "Man City vs Arsenal"
py -3.12 -m sports_skills polymarket odds --league "EPL"

# Data
# Football-Data.co.uk: https://www.football-data.co.uk/downloadm.php
# The Odds API: https://the-odds-api.com/ (free tier: 500 req/day)

# Sync
node scripts/vault-memory-sync.js    # Bidirectional vault↔memory sync
git add -A && git commit -m "msg"    # Commit (sweeps other session's staged)
```

---

*Last updated: 2026-08-21*  
*Canonical vault: `olp_xdv_agent/olp_xdv/docs/obsidian-vault/Sports_Betting_Study_Guide.md`*