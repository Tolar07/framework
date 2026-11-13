---
name: multisport-markets
description: |
  How the betting markets of the multi-sport rollout work (ice hockey, American football, snooker, darts, volleyball,
  table tennis, cricket, rugby, tennis, baseball), what moves each price, which model fits each sport's scoring, and the
  record-only experiments that turn this into better framework prices. Built from practitioner videos, cross-checked,
  plus the framework's own NFL backtest (framework#373).
  Use when: improving or judging a multi-sport model (engine/multisport.py, engine/ice_hockey.py, backtest/*_backtest.py),
  adding a market for one of these sports, choosing how much weight the Elo gets against the exchange price, reading a
  multi-sport shadow result, or planning work on framework#352-#359.
  Don't use when: football (soccer) or NBA (use `sports-betting-edge`, which also holds the general CLV / edge / Kelly
  rules this skill relies on); stock or FX trading (`trading-bot-training`).
metadata:
  version: "1.0.0"
  built: "2026-11-06 with youtube-to-skill (autonomous research mode), Architect: understand the sports, the markets and the betting behind them so we can update our models"
  sources:
    - "Thomas Buckland — Building a 5.9% ROI Tennis Totals Model Live (Pinnacle Closing Lines) (https://www.youtube.com/watch?v=T0l9zEjGwHs), 2026-11-06, transcript + 12 frames checked"
    - "Unabated — Sports Betting Edges Explained & How to Identify Them (https://www.youtube.com/watch?v=CcxbQ58TVms), watched 2026-11-06"
    - "Unabated — Pro Sports Bettors Don't Pick Winners (https://www.youtube.com/watch?v=KpNwHBJikoM), 2026-11-06"
    - "Betting Talk — Exploiting bookie mistakes in NHL period moneyline splits (https://www.youtube.com/watch?v=tekaizJuE_M), 2026-11-06"
    - "OddsJam — How to Bet the NHL (https://www.youtube.com/watch?v=jk-Y8hSgezA), 2026-11-06"
    - "Sports Betting Education — Using line movement to figure out what the sharps are betting (https://www.youtube.com/watch?v=dH1aAt_6uM8), 2026-11-06"
    - "Pinnacle / Circles Off — How to Bet on Tennis, the complete introductory guide (https://www.youtube.com/watch?v=voh72lD6RDo), 2026-11-06"
    - "The Action Network — How To Bet Darts (https://www.youtube.com/watch?v=5laezeG01F8), 2026-11-06"
    - "Dumpster Darts — Matchplay 1st round betting tips using stats (https://www.youtube.com/watch?v=ddPmNW8bjCg), 2026-11-06"
    - "Caan Berry Pro Trader — The Cricket Betting Strategy That Actually Works (https://www.youtube.com/watch?v=eZvWUAgShAA), 2026-11-06"
    - "Outlier — The Sharp Way to Bet First 5 Innings Moneyline (https://www.youtube.com/watch?v=lWAail5Bj_8), 2026-11-06"
    - "OddsShopper — 5 Golden Rules for Betting MLB (https://www.youtube.com/watch?v=zMaZ0i1vp7s), 2026-11-06"
    - "Underdog Chance — How My MLB Betting Model Finds Value Bets (https://www.youtube.com/watch?v=vn4c7mSEtDk), 2026-11-06"
    - "Investor Bet — NRL margin bets (https://www.youtube.com/watch?v=iYhIFCK4v_0), 2026-11-06"
    - "Bet in Ireland — Snooker betting explained (https://www.youtube.com/watch?v=vA8piHgz0GY) and Rugby betting types (https://www.youtube.com/watch?v=K_qlNZEzC74), 2026-11-06"
---

# multisport-markets

The framework's multi-sport board prices every new sport the same way: one win-probability Elo (`engine/multisport.py`,
K 24, 8-game minimum) blended with the exchange's fair price. The videos and our own NFL backtest say that is the weakest
way to price most of these sports. This skill says what each market actually is and what to test instead.

## Activation rules

- Any change to `engine/multisport.py`, `engine/ice_hockey.py`, `engine/elo.py` as used by a rollout sport, or a new
  `backtest/<SPORT>_backtest.py`.
- Choosing the Elo-vs-price blend weight (`ANCHOR`) or an edge bar for a rollout sport.
- Adding a market for a rollout sport (periods, sets, frames, legs, handicaps, totals, props).
- Reading a multi-sport shadow scoreboard (`data/multisport/<sport>/scoreboard.json`) or a sport study.
- Work on framework#352-#359 (backtests, scout/reasoning, team news, experiments, grader, WhatsApp, live tracker).

## Step-by-step

1. **Start top-down, not bottom-up.** For every rollout sport the exchange price (Matchbook, Betfair) is the source of
   truth. The edge is a slow book (SportyBet) away from that truth, not our Elo beating the sharp price. Originating
   your own numbers is the hardest path, and practitioners say you can't expect to originate in more than one sport
   (Unabated "winners" @ 01:33, 02:03; "edges" @ 06:47). Our NFL backtest agrees: on 2016-26 held out, the live rule
   (25% Elo + 75% price, edge >= 4 pts) **loses 7.2% per bet** at NFL closing prices, and its Brier (0.2119) is worse
   than the closing price's own (0.2107).
   - So: before any Elo weight goes above 0 for a sport, it must beat the exchange price on held-out games (Brier and
     return), every try counted. Default the weight to the price.
2. **Price the format, not just the winner.** In set/leg/frame/point sports, a player's per-unit edge compounds over the
   format: the longer the match, the more often the better player wins.
   - Tennis: betting every Grand Slam (best-of-5) favourite since 2010 was profitable, while every underdog lost about
     14% (Pinnacle @ 01:32, citing their own blog study).
   - Darts: underdogs bark in short early-round formats, "in the longer formats those dogs don't bark as much"
     (Action Network @ 04:09).
   - Build per unit: p = chance to win one point/leg/frame (or hold/break on serve), then the exact match chance for
     that format. Best-of-n sets or first-to-n legs: P(win) = sum over k = 0..n-1 of C(n-1+k, k) p^n (1-p)^k for
     first-to-n. A tennis set needs the hold/break Markov chain with the tiebreak. Then compare with the price.
   - Applies to: tennis, table tennis (best-of-5/7 games to 11), volleyball (best-of-5 sets to 25/15), darts (legs and
     sets), snooker (first to n frames).
2b. **Tennis totals: an under bias, and model the hit rate, not the mean.** On Pinnacle's closing main line 2022-25,
   overs landed 48.5% at a ~50% no-vig price: blind overs -6.1%, blind unders -0.9% (Bo3 13,072 and Bo5 2,009
   matches) (Buckland frame @ 05:02, confirmed). The average total beats the line by ~1.2 games yet overs lose: a third
   set adds 8-13 games, so a few long matches lift the mean (frame @ 05:02, shown only). So grade totals by hit rate
   and ROI at the taken price, never by mean margin. Clay plays more overs (slower), indoor hard fewest; hot weather
   leans under vs the market (Buckland @ 06:30, 09:48, said).
   - **Method that survived a sealed hold-out:** seal the latest year before forming any theory; build theories on
     the rest; trust no cut under ~1,000 training bets (300-bet cuts at 12-15% ROI are noise); judge each theory
     against the blind baseline (e.g. blind unders), not zero; look at the hold-out 2-3 times at most (Buckland @ 04:09,
     09:19, 19:12). His overfit theory went +14% training -> -21% on 2026; the robust one +5.9% -> +6.9% on 272 bets
     (frame @ 15:05, confirmed). Challenger and WTA versions failed their hold-out (@ 16:24).
   - **Built (framework#386, `backtest/tennis_totals_study.py`, record only):** grades the shadow record's tennis
     totals by hit rate and ROI at the taken price against blind unders, holds `judge_cut` (the sealed hold-out gate:
     seal the latest year, >= 1,000 training bets, <= 3 looks, beat blind unders on the same hold-out bets), and shows
     the skew from free results (2019-25 ATP+WTA, 31.6k matches): Bo3 mean games 22.5-23.1 vs median 21-22; a deciding
     set (35.5% of Bo3 matches) adds ~10 games (19.0 -> 29.5); over 22.5 lands only ~42-44% in Bo3.
   - The point/serve Markov model "gives you exactly the market" (@ 07:50): use the format model of step 2 to price
     derived markets and to check slow books against the exchange, not as an edge on its own.
3. **Ice hockey periods are the reverse of other US sports.** In NFL, NBA, college basketball and MLB the favourite is
   the biggest favourite early (first half, first quarter, first innings). In the NHL the favourite is the **smallest**
   favourite in the first period and larger in periods 2 and 3 (Betting Talk @ 00:33-02:06, calculator samples: 57.3%
   home -> largest edge period 3; 62% -> 1st period only -122, 3rd period -184).
   - Books that copy the US rule overprice the 1st-period favourite. Example: Colorado -195 full game -> fair 1st-period
     underdog about +139, a book offered +150 (@ 02:37).
   - Test: derive the fair per-period price from the exchange's full-game price and grade SportyBet's period prices
     against it (shadow).
   - Built (framework#381): `engine/hockey_periods.py` turns a full-game 1X2 exchange price into fair per-period
     prices (Poisson rates fitted to the 60-min 1X2, assumed period goal shares 31/34.5/34.5%, an ASSUMPTION until
     period scores are recorded). SportyBet's feed carries no period market yet, so the grade reads PENDING.
4. **Baseball: price by the starting pitcher, weighted by his innings.**
   - First 5 innings (F5) is decided by the two starting pitchers and the top of the line-ups; the bullpen barely
     matters there (Outlier @ 02:33, 05:41).
   - Full game: the starter's quality for the innings he usually lasts (about 5-6 now), the bullpen for the rest, each
     against the opposing line-up's split by pitcher hand; blend the last 30 days with the season (Underdog Chance
     @ 10:29-14:08).
   - Park, weather, wind and umpire move totals, and books already price them in; the edge is a pitcher who suits
     the conditions better than his line implies (OddsShopper @ 01:34-03:06).
5. **Model margins, not just winners, for handicap and margin markets** (American football, rugby). A win chance
   says nothing about a -10.5 handicap. Fit the margin distribution (key numbers in the NFL: 3 and 7) and price each
   band from it. Team "margin trends" from one season are small samples (NRL video @ 01:01-06:15): treat them as
   hypotheses and count every try.
6. **Cricket is conditions-first.** Totals depend on venue, pitch type (green helps seam, dusty helps spin, flat
   helps batting, slow and low is hard to score on) and format (IPL first innings usually 170-190 by venue)
   (Caan Berry @ 00:35, 02:37-03:08). Price totals per venue and format; cricket is bowler-versus-batter, so the
   winner market moves on momentum in play.
   Built (framework#385, `backtest/cricket_venue_study.py`): a venue mean shrunk toward the format mean cuts the
   first-innings error 40.1 -> 39.3 runs held-out 2019+ (T20 35.3 -> 34.4, ODI 56.6 -> 56.1); small, so record-only.
   Pitch type, toss and line-ups are not in Cricsheet (PENDING). Best shrinkage sat at the grid edge (k=20): retry wider.
   Built (framework#589, `engine/cricket_events.py`, `backtest/cricket_events_study.py`): first-innings total, over-block runs (T20 1-6/7-15/16-20, ODI 1-10/11-40/41-50) and wickets,
   batting-for x bowling-against x venue rates plus the record's block shares. Held-out 2020-26, 5,842 innings: total runs and over-block runs beat the plain two-team average
   (log loss 0.5772 vs 0.5874, 0.6140 vs 0.6206); wickets do not (0.6292 vs 0.6273). No venue effect was chosen on the 2019 tuning year. Fixed lines under-predict the over in 2026 (scoring drifts up): use lines from the board, not fixed ones.
7. **Darts and snooker: form and stage.** Use recent averages across the last Players Championships (form) and
   per-player TV-stage vs floor performance; free data at DartsConnect and dartsoracle.com (Dumpster Darts @ 00:37-02:10,
   06:57). Snooker markets: match winner, frame handicap, total frames, century, first frame (Bet in Ireland @ 01:36).
   Both need the format conversion in step 2.
   Built (framework#591, `engine/volleyball_events.py`, `data/volleyball_sets.py`, `backtest/volleyball_events_study.py`): Elo win chance -> set-momentum ladder (the #380 rule) gives set score, sets over 3.5/4.5 and -1.5 handicap that agree with the board; total points = ladder chance of 3/4/5 sets mixed with earlier point totals for that many sets (a 5th set is to 15). ESPN NCAA women's, 8,656 held-out matches 2021-25 (one matchday purged, 4 momenta tried, 0.15 chosen): exact score log loss 1.527 vs 1.714 for earlier frequencies (+0.187, 37 s.e.); set markets +0.078; total points over five lines +0.018 (18 s.e.), well calibrated (predicted 0.1/0.3/0.5/0.7/0.9 -> 0.10/0.33/0.55/0.74/0.91). College data, no price, so accuracy not edge. YouTube search for volleyball points/set-model teaching found only tipster clips (none credible), so nothing was taken from video.
   Built (framework#594, `engine/table_tennis_events.py`, `data/table_tennis_games.py`, `backtest/table_tennis_events_study.py`): the volleyball best-of-5 ladder reused for table tennis games (win chance -> game score, games over 3.5/4.5, -1.5 handicap, agreeing with the board). Setka Cup, 7,847 matches in one month (an integrity-excluded league, accuracy only), 3,074 held out (one matchday purged, 4 momenta tried, 0.0 chosen): exact game score log loss 1.779 vs 1.790 for earlier frequencies (+0.010, 2 s.e.); game markets +0.004 (2 s.e.); total points over five lines -0.0007 (no gain, but well calibrated: predicted 0.1/0.3/0.5/0.7/0.9 -> 0.10/0.31/0.50/0.70/0.89). Table tennis games look close to independent: momentum added nothing. YouTube search found only tipster clips, nothing taken.
   Built (framework#590, `engine/snooker_events.py`, `backtest/snooker_events_study.py`): Elo win chance -> per-frame chance -> exact frame ladder gives correct score, total frames and handicap that agree with the board by construction.
   Held-out 2024-07+, 1,542 matches (one matchday purged): exact score log loss 2.2400 vs 2.2551 for earlier same-length matches (gain +0.015, 2 s.e.); total frames over 0.5415 vs 0.5403 (no gain). Shrinking the Elo chance did not help (1.0 chosen of 4). Centuries PENDING: no break record stored.
   Darts twin (framework#592, `engine/darts_events.py`, `backtest/darts_events_study.py`): same ladder per leg on Premier League first-to-6 matches; held-out 2025+, 195 matches: exact leg score gain +0.004 (0.2 s.e., nothing), total legs over -0.005 (worse than climatology). 180s / checkouts PENDING (DartsOrakel 403; no per-visit record).
   Rugby twin (framework#593, `engine/rugby_events.py`, `data/rugby_events.py`, `backtest/rugby_events_study.py`): ESPN's rugby scoreboard does carry a half split and try / penalty-goal / conversion counts (they rebuild the score), but the half split is real almost only for 2014-15 (later games put the whole score in period 2, so they read PENDING). Held-out 343 games (one matchday purged, 16 settings tried): first-half total points gap -0.001 (0.4 s.e., nothing), tries -0.003 (0.7 s.e., nothing), penalty goals -0.071 (7 s.e., WORSE than each team's own penalty average - penalties are a team style, not a share of points). Stays shadow. YouTube search for rugby model teaching found one calibration clip (Thomas Buckland, `_Dcm6TS5KPU`); captions were rate-limited (429) so nothing was taken from video.
8. **Timing.** Lines are least efficient early and most efficient at the close (OddsShopper @ 04:08). Sharp books move
   first; the slow book lags (line-movement video @ 01:02-02:38, a claim). For every rollout sport, record the price
   at decision, at placement and at close (the CLV split in `sports-betting-edge`). An edge that only exists against
   an early SportyBet price is a timing edge, and it is lost if the bot places late.
9. **Write the experiment as record-only.** Each idea above becomes a shadow column graded on the sport's shadow
   record: walk-forward, every try counted, held-out reporting, 2% commission, PENDING until the sample is big enough
   (HR35). Promotion follows the shadow-promotion rule; stakes and live switches stay with the Architect.

## Best practices

- Default to the exchange price; let the Elo earn weight on held-out games (Unabated "edges" @ 06:47; framework#373).
- Price the format: per-unit probability -> exact match probability (Pinnacle @ 01:32; Action Network @ 04:09).
- In the NHL, check 1st-period favourites at books that apply the US "biggest early" rule (Betting Talk @ 02:37).
- In MLB, F5 = starting pitchers; full game = innings-weighted starter + bullpen by hand (Outlier @ 02:33;
  Underdog Chance @ 13:07).
- Shop every price and record where each bet was available; most of a top-down edge is price (OddsShopper @ 05:40;
  OddsJam NHL @ 01:32).
- Small-sample "trends" (team margins, head-to-heads) are hypotheses, never rules (NRL video; Pinnacle @ 02:34 on
  head-to-head sample size).

## Common mistakes

- **One Elo for every sport.** A win-probability Elo ignores format, serve, pitchers, periods and margins. Spot it
  when a long-format favourite is priced the same as a short-format one, or when handicap prices are built from a
  win chance.
- **Blending in a model that loses to the close.** Spot it in the held-out Brier: model worse than price = weight 0.
- **Copying the US "biggest favourite early" rule to hockey.** Spot it on 1st-period prices.
- **Treating park/weather as an edge.** Books price them; only the pitcher-specific interaction is an edge.
- **Trusting tipster videos.** Most results for volleyball, table tennis and snooker were "99% accuracy" or "fixed
  match" channels: not sources. Several method videos also sell tools or courses (OddsJam, Outlier, OddsShopper,
  Underdog Chance, the line-movement tipster): their methods are kept, their claims of profit are not.

## Quality check before a multi-sport model change is trusted

- [ ] Compared with the exchange's fair price on held-out games (Brier and return at that price), not only with a
      baseline.
- [ ] Every setting tried is counted and reported; the tuning and test periods don't overlap.
- [ ] Format, periods, pitchers or margins handled where the sport has them (steps 2-6).
- [ ] Decision, placement and closing prices recorded (timing).
- [ ] Record-only until the sample is big enough; no stake, threshold or live switch changed (Architect).

## House rules (OLP XDV)

- Record-only / shadow first; promotion only under the pre-approved shadow-promotion rule with an undo switch.
- Stakes, edge bars, thresholds, live dates and money rules are the Architect's (the 12 Nov go-live stands; this
  skill improves the prices, it does not stop or start a sport).
- HR35 / HR59: a study without data reads PENDING; every number traces to a script run.
- No steam on money.

## Result: baseball starter model (framework#382, 2026-11-09)

`engine/mlb_pitcher.py` + `backtest/mlb_pitcher_backtest.py` (record-only). Held-out 2023-25, 7412 games: a starter model
(opponents' first-5 runs per start, shrunk) scores log loss 0.6868 vs 0.6879 with starters blanked vs 0.6759 for the
close; blended 50% with the close 0.6793. Starters help a hair, but nothing beats the price: price baseball off the
exchange. F5 grading vs the base rate only (0.6907 vs 0.6914); F5 price test PENDING until an F5 moneyline is recorded.
Needs real pitcher quality (FIP/xFIP, hand splits) to do better. Idea source: issue #382 (Outlier @ 02:33, 05:41;
Underdog Chance @ 10:29-14:08; OddsShopper @ 01:34-03:06). YouTube research this run: skipped (idea already sourced).

## Evidence table

| Claim | Source @ time | Status |
|---|---|---|
| Top-down (sharp source of truth vs slow books) is how most winners win; originating is the hardest | Unabated "winners" @ 02:03; "edges" @ 06:47 | said only (two videos, same channel) |
| Can't expect to originate in more than one sport | Unabated "winners" @ 01:33 | said only |
| Elo blend loses to the NFL close (-7.2%/bet, Brier 0.2119 vs 0.2107, 2016-26 held out) | framework#373 backtest | confirmed (our data) |
| NFL: does a learned correction on the closing price (rest-day gap, starting-QB change, divisional game, margin-Elo) beat the close? | own idea from the practitioner-model talks above (price first, add only what the price misses); YouTube search 2026-11-10 returned picks shows, one long talk (Circles Off https://www.youtube.com/watch?v=AUA7OJAuyD4 @ 01:09 (the close is the benchmark) and @ 15:15 (a starting-QB change moves the price; captions only, frames not checked)) | own test (`backtest/nfl_context_study.py`, framework#339, 3 tries, tuned 2008-15, held out 2016-26, 2884 games): NO. Log loss 0.6093 = the closing price 0.6093, only 11 bets at edge >= 2 pts; the price already holds these. Keep the price |
| Long-format favourites win more: Grand Slam favourites profitable since 2010, underdogs -14% | Pinnacle @ 01:32 | said only (cites a Pinnacle study) |
| Darts underdogs bark in short formats, less in long | Action Network @ 04:09 | said only; agrees with tennis (independent) ; own test (`backtest/darts_format_underdog_study.py`, 94 rated WC matches 2026-11-07): not yet shown, 3 of 4 length buckets under 30 matches (PENDING), the 4-set bucket has underdogs winning 0.40 vs Elo 0.43 |
| Darts: a dated results history exists after all (Premier League nights, real dates) | Wikipedia season pages, 2023-2026 (own feed `data/darts_pl_results.py`) | 443 matches, 62 dates. Own test (`backtest/darts_dated_study.py`, 2026-11-07): board Elo Brier 0.2372 over 365 scored, every season under the coin-flip 0.25 (0.234-0.240). Rating carries information; still NO closing price, so no edge claim |
| Darts: does a pair's own head-to-head add to the Elo? (closed field of ~10 meets again and again) | own idea, no video | own test (`backtest/darts_h2h_study.py`, 2026-11-07, 365 scored dated PL matches): NO. Weight picked on first half (b=1) made the sealed second half worse, Brier 0.2425 vs board 0.2373; the Elo already holds it |
| Darts: does the first-listed slot, or a long night (matches already thrown tonight), shift the Elo? | own idea, no video | own test (`backtest/darts_night_study.py`, 2026-11-07, 365 scored dated PL matches): NO. Slot shift s=0.106 and a fatigue grid picked on the first half made the sealed second half worse, Brier 0.2391 vs board 0.2373 |
| Darts: does a narrow last result (win or loss by 1-2 legs) carry into the next match? | own idea, no video (YouTube search for darts models returned nothing usable, 2026-11-07) | own test (`backtest/darts_close_study.py`, 2026-11-07, 365 scored dated PL matches, 8 tries): NO. M=2, w=0.4 picked on the first half made the sealed second half worse, Brier 0.2450 vs board 0.2373 |
| Darts: does a run of 2-3 straight wins or losses carry momentum beyond the Elo? | own idea, no video (YouTube search for darts models returned nothing usable, 2026-11-07) | own test (`backtest/darts_streak_study.py`, 2026-11-07, 365 scored dated PL matches, 8 tries): NO. S=3, w=0.4 picked on the first half made the sealed second half worse, Brier 0.2452 vs board 0.2373 |
| NHL 1st-period favourite is the smallest; books misapply the US rule | Betting Talk @ 01:04-02:37 | said with calculator numbers (frames not viewed) |
| F5 decided by starting pitchers; bullpen irrelevant for F5 | Outlier @ 02:33, 05:41 | said; agrees with Underdog Chance's innings weighting |
| Starter weighted by innings pitched, bullpen for the rest, split by hand, 30-day + season blend | Underdog Chance @ 10:29-14:08 | said only (sells the model) |
| Park/weather priced in; pitcher-condition fit is the edge; lines most efficient at close | OddsShopper @ 01:34-04:08 | said only (sells a tool) |
| IPL 1st innings usually 170-190 by venue; pitch type drives scoring | Caan Berry @ 00:35, 02:37 | said only (promotes a betting platform) |
| Team margin bands from one NRL season | Investor Bet @ 01:01-06:15 | said only, small samples (hypothesis) |
| Tennis totals under bias at the Pinnacle close (over -6.1%, under -0.9%, 2022-25) | Buckland frame @ 05:02 | confirmed (said + shown) |
| Mean total beats the line yet overs lose (skewed distribution: model hit rate) | Buckland frame @ 05:02 | shown only |
| Overfit cut +14% -> -21% on sealed 2026; robust cut +5.9% -> +6.9% (272 bets) | Buckland frame @ 15:05 | confirmed |
| Trust no cut under ~1,000 bets; compare to the blind baseline; 2-3 hold-out looks max | Buckland @ 09:19, 19:12 | said only |
| A point/serve Markov model reproduces the market | Buckland @ 07:50 | said only; **qualifies** step 2 (format model = pricing tool, not an edge by itself) |
| "Never devig a line" | Buckland @ 05:03 | **contradicted** by our practice of devigging for a fair chance: both hold. Judge a bet by its ROI at the price actually taken; devig only to read the market's chance |
| Volleyball / table tennis betting methods | (none credible found) | not used |

**Not checked in this version:** four method videos were blocked by YouTube rate limits (Circles Off "How Sharp
Bettors Turn a Projection Into a Price", OddsJam NFL models, Bet Angel tennis, Smart Betting Club with Ed Hawkins on
cricket). Frames were viewed only for the Buckland tennis video (12 frames); the others are transcript-only. Next
version: add the four and frame-check the NHL calculator numbers. Data sources named: bettingiscool (Pinnacle closing
lines, tennis), OnCourt (tennis database, paid), DartsConnect and dartsoracle.com (darts), Cricsheet (cricket), nflverse
(NFL closing lines), Retrosheet (MLB results).
