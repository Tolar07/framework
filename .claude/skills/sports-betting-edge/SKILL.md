---
name: sports-betting-edge
description: |
  How to find, size and verify an edge in football and NBA betting: price not picks, expected value from a
  sharp "source of truth", when closing line value (CLV) can and can't be trusted (three tests), originating
  your own numbers in narrow markets, a Poisson goals model, NBA player-prop inputs and sharp-money signals,
  and fractional Kelly.
  Use when: building or judging a betting model, rule, market, bot (framework, Matchbook, Betfair, SportyBet) or tip
  source; deciding which markets to trust CLV in; adding a football or NBA model input; grading a bot's results.
  Don't use when: the question is stock or FX trading (use `trading-bot-training`, which also holds the validation
  tests every betting rule should pass).
metadata:
  version: "1.0.0"
  built: "2026-11-04 with youtube-to-skill from 6 videos (transcripts + frames, cross-checked)"
  sources:
    - "Unabated — Why Most Sports Bettors Never Win (https://www.youtube.com/watch?v=EQt2sq0_s64)"
    - "Unabated — You're Using Closing Line Value Wrong (https://www.youtube.com/watch?v=MIkpsiJzbcA)"
    - "Unabated — Find New Ways to Beat Sportsbooks by Originating (https://www.youtube.com/watch?v=Yol6yv6X3dM)"
    - "Kie Millett — Predict the Outcome of Football Matches Using this Model (https://www.youtube.com/watch?v=24e_Z4WHR48)"
    - "Billy Collins — How to Start Building Your Own NBA Betting Model (https://www.youtube.com/watch?v=hTbMIwItUhI)"
    - "OddsJam — NBA Betting Course Part 1: How to Follow Sharp Money (https://www.youtube.com/watch?v=5RuaIJvjKN0)"
---

# sports-betting-edge

Betting is **price, not picks**. A bet is good when its price is better than the true probability. Over
many bets the edge is ground out, sized by a fraction of Kelly (Unabated "Why most…" @ 00:00–02:12).

## Activation rules

- A new rule, market, league, model input or bot is proposed, or one is being graded.
- Someone quotes CLV, a win rate or a tipster's record as proof.
- A model's number is far from the market's.

## Step-by-step

1. **Get the true probability**, one of two ways:
   - **Top-down:** take a sharp book's or exchange's de-vigged price as the truth. Sharp books shape lines and
     recreational books copy them, so look for a recreational price that beats the sharp one.
     - No single book is sharpest at everything: one may be sharp for the NBA and not for the NFL ("Why most…" @ 03:18–04:24).
   - **Bottom-up (originate):** build your own number (steps 4–6). Pick **narrow** markets where the book has too much
     "surface area" to defend: first innings, first period, team or player sub-markets, small leagues. Avoid the most
     efficient markets, such as NFL or EPL full-game sides on match day ("Originating" @ 01:04–03:43).
2. **Compute EV** = p_true × (decimal price − 1) − (1 − p_true). Bet only when EV > 0 after commission.
   - Example: a fair 50/50 coin at +110 gives about 5% EV (@ 01:39).
3. **Size it with fractional Kelly.**
   - Full Kelly = edge ÷ (decimal price − 1). Use **¼ Kelly**, at most ½ Kelly, because your edge estimate is uncertain
     (@ 04:57–05:30; graphic "Kelly stake ÷ 4 / ÷ 2").
   - Tolar07: stakes, caps and staking modes are the Architect's. Record what Kelly *would* say; change nothing live.
4. **Football model (Poisson; the framework's Dixon-Coles is the stronger version of this).**
   - Use separate home and away tables, per-game goals for and against, and the league averages (frame: avg home
     goals 1.53).
   - home attack = team home goals scored per game ÷ league home average;
   - away defence = team away goals conceded per game ÷ league home average; mirror these for away attack and home
     defence.
   - λ_home = home attack × away defence × league home average; λ_away likewise.
   - P(score i–j) = Pois(i; λ_home) × Pois(j; λ_away) for 0–8 goals. Sum the cells for 1X2, totals and correct score;
     fair price = 1/p (Kie Millett @ 10:18–16:52).
   - Run a **goals version and an xG version** and several form windows (season vs last N). Their disagreement is
     information. Older data is less relevant, and fewer games give a noisier number (@ 03:17, 18:28–19:34).
5. **NBA player-prop model (Billy Collins).**
   - Start with **one market and 8–12 players**, e.g. assists for the top ball-dominant playmakers (@ 04:42, 08:53).
   - Core inputs: minutes, usage rate, pace, opponent defence (scheme matters), back-to-backs and injuries (@ 05:45).
   - **Teammate on/off:** how a player's usage or assists move when a key teammate sits, is in foul trouble or is
     out. Example: Brunson with and without Towns (@ 07:51–08:22).
   - Prefer players on the same team as last season. A trade resets the history (@ 07:20).
   - Clean data first: player names differ across sources (initials, nicknames, full names), so match them before
     any formula (@ 03:07).
6. **Calibrate against the sharp market before trusting the model.**
   - A brand-new model whose number is miles from Pinnacle, Circa or FanDuel is **probably wrong**, not
     sitting on a huge edge. The first goal is to land *close to* the sharp books, then find the few spots where they
     are off (Billy Collins @ 10:29–11:31).
7. **NBA timing and sharp-money signals (OddsJam).**
   - NBA injury news lands late in the afternoon (US Eastern time), and players rest without notice. Let the market
     mature; liquidity days before tip-off is thin (@ 08:09–08:39, 11:43).
   - A good spot has both signals: **exchange liquidity backs your side** (large resting orders on exchanges or
     prediction markets) **and sharp books are moving toward you** (e.g. −102 → −128) (@ 09:40–10:11).
   - If the move is against you but the market has settled at fair and you still beat it, the bet can still be fine
     (@ 11:12).
8. **Verify with CLV, but only where CLV is meaningful.** Run the **three tests** ("CLV wrong" @ 03:20–07:42):
   1. *Hidden information:* is there information nobody can know before close that decides the bet? Part-game
      derivatives (first quarter, first half) fail this.
   2. *Sharp shaping:* do sharp bettors actually shape this line? Props and obscure markets often don't. Books move
      them to protect liability and touts move them. Rule of thumb: if Pinnacle or Circa don't list it, CLV barely matters.
   3. *Liquidity* (the most important): how much is matched or traded? Exchange and prediction-market volume is a
      proxy. Example: $1M on an NBA game vs $10k on a WNBA game.
   - Strong CLV markets: major-league sides and totals (NFL, NBA, **EPL**). Weaker: minor leagues and college. Weakest:
     props and obscure sports.
   - Track CLV on **every** projection, bet or not, over 500–2,000 samples. Beating the close on less than 50% is a
     problem; 30–40% means the model is broken. Aim for 60% or more on props (Billy Collins @ 12:34–13:06).
   - Where CLV fails the tests, judge by graded outcomes against the model's probabilities (Brier or log-loss) on a
     large sample, not by CLV alone.

## Best practices

- Know **why** a line moved, not just that it did. That separates chasing steam from understanding the market
  ("CLV wrong" @ 08:46).
- Work like a scientist: observation → hypothesis → collect data → test → only then bet. The weather and home-run
  model started as one observation ("Originating" @ 04:15–05:51).
- Treat any model as one input among several; "all models are wrong, some are useful" (Kie Millett @ 00:34–01:07).
- Use AI to clean data and write formulas, **not** to judge whether a number is sensible. It agrees with whatever you
  propose (Billy Collins @ 08:53–09:57).
- Crowds hitting the same stale line get limited fast. Originated bets look like one ordinary bettor. Less-liquid
  markets are more beatable but have lower limits (Originating @ 07:25–09:01).

## Common mistakes

- Picking winners instead of pricing. A 70% favourite at a bad price is a losing bet.
- Full Kelly on an overestimated edge, which over-bets the bankroll.
- Trusting CLV on props, half markets or minor leagues as if they were EPL or NBA full-game lines.
- Believing a big early model edge. It is almost always a model bug or a missing input.
- Following tipsters' records without sample size or losses. Selling picks or courses is a bias. Here OddsJam and
  the prop tipster are selling tools or subscriptions.
- Fixed thresholds across leagues. A league's liquidity changes how much a price can be trusted.

## Quality check before a rule, market or input is trusted

- [ ] True probability source named: a sharp book or exchange (de-vigged), or our own model checked against it.
- [ ] EV > 0 after commission at the price actually available.
- [ ] Market tiered by the three CLV tests, and CLV only used as proof in markets that pass.
- [ ] ≥ 500 graded projections (bet or not), with CLV rate and Brier against the close reported.
- [ ] The rule passed the permutation and walk-forward gates in `trading-bot-training`, with outcomes shuffled.
- [ ] Kelly fraction recorded; live stakes untouched (Architect's decision).
- [ ] Figures come from a fetch in this session (HR59); anything missing reads PENDING (HR35).

## Evidence table

| Claim | Source @ time | Status |
|---|---|---|
| EV, price not picks; ¼ Kelly | Unabated "Why most" 01:39, 05:30 | confirmed (Kelly ÷4 / ÷2 graphic) |
| Sharp books shape lines; copy-cat recreational books | Unabated "Why most" 03:18 | said only |
| CLV three tests; props weakest; EPL strong | Unabated "CLV wrong" 03:20–08:15 | said only (B-roll frames) |
| Originate in narrow markets; scientific method | Unabated "Originating" 01:36–05:51 | said only (captions were an auto-translation) |
| Poisson attack/defence formulas | Kie Millett 10:18–12:00 | confirmed (spreadsheet frame: league averages and attack/defence cells) |
| NBA: one market, 8–12 players, on/off, CLV ≥ 60% | Billy Collins 04:42–13:06 | said only (captions auto-translated) |
| Exchange liquidity + sharp-book move | OddsJam 09:40–10:11 | confirmed (Sharp Money tool frame: Wiggins o12.5, $800) |
| **Contradiction:** CLV on props | Unabated says largely meaningless; Billy Collins says track it, beat ≥ 60% | Reconciled: track it against the sharpest prop books, but treat it as a weak signal and require outcome grading too |

## Timing is testable on the same picks

Placement time is an A/B test when two bots hold one selection: `monitor/timing_experiment.py` pairs Matchbook (early)
with Betfair (about 3 h before kick-off) and reports early-minus-late CLV with a 90% band against one shared close.
Record-only; a `timing` proposal opens only at 100+ pairs with a band that excludes 0. Re-watched Unabated "CLV wrong"
(https://www.youtube.com/watch?v=MIkpsiJzbcA @ 00:28 "CLV is more guidepost than gospel") on 2026-11-04: it adds nothing
beyond the three tests above, so the table is unchanged.
