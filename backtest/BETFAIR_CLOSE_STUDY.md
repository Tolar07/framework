```
BETFAIR CLOSING-LINE STUDY — does the model know anything the market doesn't?
Source: football-data.co.uk (Betfair Exchange closing odds BFEC*, bet365 B365*,
Betfair Exchange early BFE*). Walk-forward production Dixon-Coles fit.

Matches rated by the model: 14167; with Betfair close 1X2: 13757; with bet365 1X2: 14147
By season (with Betfair close): 2425 6682, 2526 6245, 2627 830
Leagues: 2. Bundesliga, Belgian Pro League, Bundesliga, Championship, Eredivisie, Greek Super League, La Liga, La Liga 2, League One, League Two, Ligue 1, Ligue 2, National League, Premier League, Primeira Liga, Scottish Premiership, Serie A, Serie B, Turkish Super Lig

A. WHO FORECASTS RESULTS BEST — same matches for every row; lower is better
   (1X2: multi-class log loss and Brier; O/U 2.5: binary)

  1X2 — 13638 matches
    Betfair close                  log loss 0.9933   Brier 0.5933
    soft (bet365 early)            log loss 0.9978   Brier 0.5960
    anchored 75/25 (production)    log loss 0.9999   Brier 0.5976
    Betfair early                  log loss 1.0021   Brier 0.5994
    model                          log loss 1.0210   Brier 0.6116

  Over/Under 2.5 — 13208 matches
    Betfair close                  log loss 0.6754   Brier 0.4827
    soft (bet365 early)            log loss 0.6778   Brier 0.4850
    Betfair early                  log loss 0.6782   Brier 0.4854
    anchored 75/25 (production)    log loss 0.6790   Brier 0.4862
    model, O/U calibrated          log loss 0.6855   Brier 0.4924
    model                          log loss 0.6956   Brier 0.5013

B. DOES THE MODEL ADD ANYTHING TO THE CLOSE? p = close + w x (model - close),
   1X2 log loss on results by season. If w = 0 is best, the model carries
   nothing the closing price didn't already have.

       w            2425            2526            2627
     0.0 0.9935 (n=6682) 0.9934 (n=6245)  0.9887 (n=830)
    0.05 0.9938 (n=6682) 0.9938 (n=6245)  0.9895 (n=830)
     0.1 0.9942 (n=6682) 0.9943 (n=6245)  0.9903 (n=830)
     0.2 0.9953 (n=6682) 0.9955 (n=6245)  0.9923 (n=830)
     0.3 0.9968 (n=6682) 0.9971 (n=6245)  0.9947 (n=830)
     0.5 1.0012 (n=6682) 1.0016 (n=6245)  1.0010 (n=830)
     1.0 1.0208 (n=6682) 1.0202 (n=6245)  1.0260 (n=830)
  best w: 2425 -> 0.0, 2526 -> 0.0, 2627 -> 0.0

C. DOES THE MODEL KNOW WHERE THE LINE GOES? Every 1X2 and O/U 2.5 outcome,
   bucketed by the model's chance minus the soft (bet365 early) fair chance.
   move = Betfair close fair chance - soft fair chance, in points. If the
   model knows something, move has the same sign as the bucket.

  model - soft <..-10 pts          n=  3416  move +0.00 ± 0.06 pts
  model - soft -10..-5 pts         n=  9334  move +0.01 ± 0.03 pts
  model - soft -5..-2 pts          n= 12254  move -0.06 ± 0.02 pts
  model - soft -2..+2 pts          n= 19776  move +0.02 ± 0.02 pts
  model - soft +2..+5 pts          n= 10964  move +0.02 ± 0.03 pts
  model - soft +5..+10 pts         n=  9144  move -0.02 ± 0.03 pts
  model - soft +10..> pts          n=  3787  move +0.08 ± 0.05 pts
  slope: the close moves +0.003 pts per point of model disagreement (68675 outcomes)

D. VALUE AGAINST THE BETFAIR CLOSE — one bet per match at the soft (bet365
   early) price, band 1.20-2.00. EV close = Betfair close chance x price - 1:
   the expected return of the bet by the best final estimate. ROI = what
   the results actually paid (noisy). ± is one standard error.

  production: likeliest, 75/25 anchored
    2425: n= 6674  EV close  -5.69% ± 0.04  beat close   6.1%  ROI  -5.85% ± 0.70
    2526: n= 6224  EV close  -6.48% ± 0.04  beat close   3.9%  ROI  -5.94% ± 0.73
    2627: n=  830  EV close  -6.49% ± 0.14  beat close   5.9%  ROI  -5.08% ± 1.98
     ALL: n=13728  EV close  -6.10% ± 0.03  beat close   5.1%  ROI  -5.84% ± 0.49

  model edge >= 2%
    2425: n= 3215  EV close  -4.85% ± 0.11  beat close  17.5%  ROI  -4.97% ± 1.47
    2526: n= 2793  EV close  -5.32% ± 0.10  beat close  15.2%  ROI  -7.12% ± 1.61
    2627: n=  358  EV close  -6.51% ± 0.33  beat close  14.0%  ROI -15.60% ± 4.47
     ALL: n= 6366  EV close  -5.15% ± 0.07  beat close  16.3%  ROI  -6.51% ± 1.05

  model edge >= 5%
    2425: n= 2270  EV close  -4.93% ± 0.13  beat close  17.7%  ROI  -5.14% ± 1.77
    2526: n= 1883  EV close  -5.29% ± 0.13  beat close  16.4%  ROI  -6.90% ± 1.96
    2627: n=  239  EV close  -6.68% ± 0.42  beat close  13.8%  ROI -14.94% ± 5.49
     ALL: n= 4392  EV close  -5.18% ± 0.09  beat close  16.9%  ROI  -6.43% ± 1.28

  model edge >= 10%
    2425: n= 1218  EV close  -5.01% ± 0.18  beat close  18.6%  ROI  -8.04% ± 2.43
    2526: n=  853  EV close  -5.39% ± 0.21  beat close  17.5%  ROI  -9.05% ± 2.98
    2627: n=  122  EV close  -6.61% ± 0.62  beat close  13.9%  ROI -24.92% ± 7.64
     ALL: n= 2193  EV close  -5.25% ± 0.13  beat close  17.9%  ROI  -9.37% ± 1.83

  Betfair-early lag >= 2% (no model)
    2425: n=  324  EV close  -5.63% ± 0.38  beat close  17.0%  ROI  -6.53% ± 4.59
    2526: n=  247  EV close  -5.02% ± 0.40  beat close  16.6%  ROI  -1.39% ± 5.49
    2627: n=   24  EV close  -2.79% ± 1.52  beat close  25.0%  ROI -34.40% ± 17.77
     ALL: n=  595  EV close  -5.26% ± 0.27  beat close  17.1%  ROI  -5.52% ± 3.46

  Betfair-early lag >= 5% (no model)
    2425: n=  266  EV close  -5.89% ± 0.40  beat close  15.4%  ROI  -4.25% ± 5.09
    2526: n=  199  EV close  -5.33% ± 0.45  beat close  14.1%  ROI  +1.42% ± 6.18
    2627: n=   19  EV close  -2.52% ± 1.59  beat close  26.3%  ROI -24.70% ± 20.88
     ALL: n=  484  EV close  -5.53% ± 0.30  beat close  15.3%  ROI  -2.72% ± 3.87

  Betfair-early lag >= 10% (no model)
    2425: n=  172  EV close  -5.90% ± 0.55  beat close  18.0%  ROI  -4.91% ± 6.57
    2526: n=  138  EV close  -5.20% ± 0.59  beat close  15.2%  ROI  +6.46% ± 7.58
    2627: n=   12  EV close  -0.93% ± 2.35  beat close  41.7%  ROI -23.67% ± 27.33
     ALL: n=  322  EV close  -5.42% ± 0.40  beat close  17.7%  ROI  -0.74% ± 4.89

  Betfair lag >= 2% AND model edge >= 2%
    2425: n=   80  EV close  -7.28% ± 0.89  beat close  13.8%  ROI -10.07% ± 9.38
    2526: n=   42  EV close  -3.94% ± 1.19  beat close  28.6%  ROI  +3.24% ± 14.10
    2627: n=    3  EV close  +1.39% ± 6.10  beat close  33.3%  ROI -33.33% ± 66.67
     ALL: n=  125  EV close  -5.95% ± 0.72  beat close  19.2%  ROI  -6.16% ± 7.76

  Betfair lag >= 5% AND model edge >= 5%
    2425: n=   42  EV close  -7.97% ± 1.13  beat close   9.5%  ROI  -6.11% ± 13.52
    2526: n=   21  EV close  -4.48% ± 1.82  beat close  23.8%  ROI  +4.54% ± 20.43
    2627: n=    2  EV close  -4.69% ± 0.91  beat close   0.0%  ROI  +0.00% ± 100.00
     ALL: n=   65  EV close  -6.74% ± 0.95  beat close  13.8%  ROI  -2.48% ± 11.09

  Betfair lag >= 10% AND model edge >= 10%
    2425: n=   20  EV close  -6.02% ± 1.45  beat close  15.0%  ROI  +8.76% ± 20.52
    2526: n=    6  EV close  -5.48% ± 3.88  beat close  33.3%  ROI -36.07% ± 40.43
    2627: n=    2  EV close  -4.69% ± 0.91  beat close   0.0%  ROI  +0.00% ± 100.00
     ALL: n=   28  EV close  -5.81% ± 1.29  beat close  17.9%  ROI  -1.47% ± 17.76

```
