# MARKET STUDY — soft bookmaker vs sharp close, price drift, our pick rule

Matches: 14580 · priced outcomes: 66458 · in the 1.20–2.00 band: 28988
bet365 opening = soft price we'd take; Pinnacle closing (margin removed) = truth.
sharpEV = soft price x sharp fair chance - 1. ROI = real profit at 1 unit.

## Benchmark: how good is each price as a probability (1X2 Brier, lower = better)
- bet365 opening (margin removed): 0.1953
- Pinnacle closing (margin removed): 0.1945

## Q1 · Where is the soft price generous? (market x odds band, 1.20–2.00)
| Segment | 23/24+24/25 (learn) | 25/26 (test) |
|---|---|---|
| AH away @1.20-1.35 | n=    1  sharpEV -33.2%  ROI  +33.0%  hit 100.0% | n=0 |
| AH away @1.35-1.50 | n=    2  sharpEV -26.8%  ROI  +44.0%  hit 100.0% | n=0 |
| AH away @1.50-1.75 | n=   53  sharpEV -11.8%  ROI   +2.5%  hit 60.4% | n=   19  sharpEV  -6.5%  ROI   -8.0%  hit 47.4% |
| AH away @1.75-2.00 | n= 3712  sharpEV  -4.1%  ROI   -3.3%  hit 48.2% | n= 1405  sharpEV  -4.4%  ROI   -0.8%  hit 49.0% |
| AH home @1.50-1.75 | n=   37  sharpEV -10.0%  ROI  +28.4%  hit 73.0% | n=   13  sharpEV  -9.5%  ROI  -10.8%  hit 38.5% |
| AH home @1.75-2.00 | n= 3639  sharpEV  -4.0%  ROI   -6.1%  hit 46.1% | n= 1392  sharpEV  -4.6%  ROI   -7.8%  hit 44.3% |
| Away win @1.20-1.35 | n=  138  sharpEV  -3.5%  ROI   +5.2%  hit 82.6% | n=   28  sharpEV  -4.7%  ROI  +18.5%  hit 92.9% |
| Away win @1.35-1.50 | n=  179  sharpEV  -4.1%  ROI   -7.9%  hit 65.4% | n=   41  sharpEV  -5.8%  ROI   +0.2%  hit 70.7% |
| Away win @1.50-1.75 | n=  443  sharpEV  -5.0%  ROI   +0.1%  hit 61.6% | n=   97  sharpEV  -5.8%  ROI   +6.9%  hit 66.0% |
| Away win @1.75-2.00 | n=  551  sharpEV  -5.7%  ROI   -1.0%  hit 52.6% | n=  141  sharpEV  -5.8%  ROI  -20.3%  hit 42.6% |
| Home win @1.20-1.35 | n=  430  sharpEV  -3.4%  ROI   -1.9%  hit 77.2% | n=   75  sharpEV  -4.7%  ROI   -2.1%  hit 77.3% |
| Home win @1.35-1.50 | n=  452  sharpEV  -4.4%  ROI   -2.7%  hit 69.2% | n=  132  sharpEV  -4.9%  ROI   +2.5%  hit 72.0% |
| Home win @1.50-1.75 | n= 1093  sharpEV  -4.8%  ROI   -1.4%  hit 60.7% | n=  319  sharpEV  -6.7%  ROI   -8.7%  hit 56.1% |
| Home win @1.75-2.00 | n= 1152  sharpEV  -5.5%  ROI   -6.8%  hit 49.7% | n=  444  sharpEV  -6.9%  ROI  -12.1%  hit 47.1% |
| Over 2.5 @1.20-1.35 | n=  185  sharpEV  -5.4%  ROI   -5.2%  hit 73.0% | n=   28  sharpEV  -7.6%  ROI   -7.4%  hit 71.4% |
| Over 2.5 @1.35-1.50 | n=  581  sharpEV  -4.7%  ROI   +0.4%  hit 70.7% | n=  103  sharpEV  -5.7%  ROI  -13.3%  hit 61.2% |
| Over 2.5 @1.50-1.75 | n= 2487  sharpEV  -5.2%  ROI   -2.4%  hit 59.9% | n=  666  sharpEV  -4.9%  ROI   -1.5%  hit 60.2% |
| Over 2.5 @1.75-2.00 | n= 2191  sharpEV  -4.3%  ROI   -2.8%  hit 51.4% | n=  808  sharpEV  -4.8%  ROI   -1.9%  hit 51.7% |
| Under 2.5 @1.20-1.35 | n=    4  sharpEV  -1.2%  ROI   -1.2%  hit 75.0% | n=    5  sharpEV  -5.6%  ROI  -20.8%  hit 60.0% |
| Under 2.5 @1.35-1.50 | n=  128  sharpEV  -3.7%  ROI   +1.8%  hit 71.1% | n=   50  sharpEV  -4.5%  ROI   -7.9%  hit 64.0% |
| Under 2.5 @1.50-1.75 | n= 1753  sharpEV  -4.2%  ROI   +0.9%  hit 61.3% | n=  775  sharpEV  -4.8%  ROI   -5.5%  hit 57.5% |
| Under 2.5 @1.75-2.00 | n= 2359  sharpEV  -3.4%  ROI   -5.8%  hit 49.6% | n=  877  sharpEV  -4.3%  ROI   -5.0%  hit 50.3% |

Segments positive in sharp EV in BOTH periods (n>=100 learn, >=50 test): **none**

## Q1b · Favourite vs underdog, by league (1X2 + O/U + AH in band)
| League | learn | test |
|---|---|---|
| 2. Bundesliga | n=0 | n=  223  sharpEV  -4.9%  ROI   -3.5%  hit 53.4% |
| Belgian Pro League | n= 1692  sharpEV  -4.9%  ROI   -5.1%  hit 53.2% | n=  290  sharpEV  -5.4%  ROI   -8.5%  hit 49.0% |
| Bundesliga | n= 1532  sharpEV  -4.6%  ROI   -2.8%  hit 56.6% | n=  410  sharpEV  -4.8%  ROI   -5.9%  hit 52.4% |
| Championship | n= 3073  sharpEV  -4.1%  ROI   -3.0%  hit 52.9% | n=  793  sharpEV  -4.7%  ROI   -6.2%  hit 50.2% |
| Eredivisie | n= 1548  sharpEV  -4.5%  ROI   -3.1%  hit 56.5% | n=  365  sharpEV  -5.4%  ROI   -3.2%  hit 56.2% |
| La Liga | n= 1951  sharpEV  -4.0%  ROI   -0.7%  hit 57.2% | n=  537  sharpEV  -4.4%  ROI   -0.3%  hit 55.9% |
| La Liga 2 | n=0 | n=  571  sharpEV  -5.6%  ROI   -6.2%  hit 51.1% |
| League One | n= 1635  sharpEV  -4.7%  ROI   -3.8%  hit 52.0% | n=  470  sharpEV  -4.8%  ROI   -3.4%  hit 51.7% |
| League Two | n= 1654  sharpEV  -4.7%  ROI   -6.8%  hit 49.8% | n=  501  sharpEV  -5.0%  ROI   -4.0%  hit 51.5% |
| Ligue 1 | n= 1609  sharpEV  -4.1%  ROI   -4.7%  hit 53.3% | n=  435  sharpEV  -4.6%  ROI   -1.2%  hit 54.7% |
| Ligue 2 | n=0 | n=  290  sharpEV  -5.6%  ROI   -4.7%  hit 51.0% |
| National League | n=0 | n=  549  sharpEV  -5.3%  ROI   -3.7%  hit 51.7% |
| Premier League | n= 1950  sharpEV  -4.5%  ROI   -4.2%  hit 55.5% | n=  614  sharpEV  -4.7%  ROI   -5.4%  hit 52.1% |
| Primeira Liga | n= 1558  sharpEV  -4.4%  ROI   -1.6%  hit 55.7% | n=  387  sharpEV  -4.7%  ROI   -3.7%  hit 54.0% |
| Scottish Premiership | n= 1279  sharpEV  -4.4%  ROI   -3.6%  hit 54.0% | n=  167  sharpEV  -4.6%  ROI  -10.8%  hit 49.1% |
| Serie A | n= 2089  sharpEV  -4.0%  ROI   -0.9%  hit 54.9% | n=  583  sharpEV  -4.3%  ROI   -5.8%  hit 51.1% |
| Serie B | n=0 | n=  233  sharpEV  -5.3%  ROI   -9.5%  hit 48.5% |

Leagues where the soft price is near or above the sharp close in both periods: none

## Q2 · Price movement before kickoff (bet365 open -> close, in band)
| Move | n | won | opening implied | ROI at opening price |
|---|---|---|---|---|
| shortened 5%+ | 4546 | 56.6% | 53.5% | +2.6% |
| shortened 2-5% | 4872 | 57.1% | 55.1% | +0.2% |
| steady (±2%) | 8654 | 54.9% | 54.5% | -2.4% |
| drifted 2-5% | 4969 | 51.9% | 54.3% | -6.5% |
| drifted 5%+ | 5947 | 48.4% | 53.5% | -10.9% |

## Q3 · Our pick rule on these markets (one pick per match)
| Rule | learn | test |
|---|---|---|
| Likeliest in-band outcome | n= 7995  sharpEV  -4.7%  ROI   -2.1%  hit 60.8% | n= 2596  sharpEV  -5.2%  ROI   -4.7%  hit 58.4% |
| Value-aware (within 4 pts, best price) | n= 7995  sharpEV  -4.5%  ROI   -2.0%  hit 59.6% | n= 2596  sharpEV  -5.1%  ROI   -6.0%  hit 56.4% |

