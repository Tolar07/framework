```
SELECTION STUDY — one pick per match, band 1.20-2.00, opening prices

rule        picks   hit%    ROI%
MODEL        3522   71.0   -6.84
MARKET       3522   73.1   -5.99
CONSENSUS    3522   72.3   -6.56
AGREE        2972   73.2   -5.95
AGREE70      2609   73.6   -6.65

By market (rule: share of picks, hit%, ROI%):
  MODEL: AWAY n=115 hit=71% roi=-2.2% | DC_12 n=1920 hit=73% roi=-7.8% | DC_1X n=475 hit=70% roi=-8.8% | DC_X2 n=332 hit=70% roi=-5.7% | HOME n=316 hit=74% roi=+0.1% | OVER25 n=236 hit=67% roi=-5.3% | UNDER25 n=128 hit=55% roi=-13.2%
  MARKET: AWAY n=114 hit=75% roi=+1.1% | DC_12 n=2046 hit=73% roi=-7.7% | DC_1X n=559 hit=75% roi=-5.7% | DC_X2 n=231 hit=76% roi=-4.8% | HOME n=359 hit=74% roi=+0.0% | OVER25 n=211 hit=68% roi=-5.5% | UNDER25 n=2 hit=100% roi=+36.0%
  CONSENSUS: AWAY n=111 hit=71% roi=-3.2% | DC_12 n=2120 hit=72% roi=-7.7% | DC_1X n=466 hit=73% roi=-7.8% | DC_X2 n=233 hit=72% roi=-8.1% | HOME n=348 hit=74% roi=-0.8% | OVER25 n=220 hit=70% roi=-2.5% | UNDER25 n=24 hit=71% roi=+0.8%
  AGREE: AWAY n=83 hit=75% roi=+2.2% | DC_12 n=2082 hit=73% roi=-7.7% | DC_1X n=317 hit=74% roi=-7.1% | DC_X2 n=128 hit=76% roi=-4.5% | HOME n=217 hit=78% roi=+5.6% | OVER25 n=139 hit=69% roi=-3.3% | UNDER25 n=6 hit=100% roi=+37.2%
  AGREE70: AWAY n=34 hit=79% roi=+1.7% | DC_12 n=1997 hit=73% roi=-7.8% | DC_1X n=309 hit=73% roi=-7.8% | DC_X2 n=124 hit=77% roi=-3.7% | HOME n=95 hit=85% roi=+8.3% | OVER25 n=46 hit=78% roi=+1.4% | UNDER25 n=4 hit=100% roi=+34.3%

By league (AGREE70 / CONSENSUS / MODEL  hit% roi%):
  Belgian Pro League 2526          AGREE70: n=200 74% -7.4% | CONSENSUS: n=299 72% -7.8% | MODEL: n=299 72% -5.2%
  Bundesliga 2526                  AGREE70: n=212 73% -8.2% | CONSENSUS: n=290 70% -9.7% | MODEL: n=290 69% -9.5%
  Championship 2526                AGREE70: n=432 76% -1.8% | CONSENSUS: n=511 76% -2.2% | MODEL: n=511 74% -2.6%
  Championship 2627                AGREE70: n=44 70% -10.2% | CONSENSUS: n=60 65% -16.4% | MODEL: n=60 68% -8.6%
  Eredivisie 2526                  AGREE70: n=197 71% -10.9% | CONSENSUS: n=285 72% -7.1% | MODEL: n=285 72% -6.1%
  La Liga 2526                     AGREE70: n=263 75% -4.3% | CONSENSUS: n=364 73% -5.2% | MODEL: n=364 70% -7.7%
  League One 2627                  AGREE70: n=43 74% -5.9% | CONSENSUS: n=46 74% -6.6% | MODEL: n=46 76% -1.4%
  League Two 2627                  AGREE70: n=46 63% -20.7% | CONSENSUS: n=56 62% -19.8% | MODEL: n=56 68% -10.3%
  Ligue 1 2526                     AGREE70: n=224 71% -10.3% | CONSENSUS: n=287 71% -8.9% | MODEL: n=287 70% -9.9%
  National League 2627             AGREE70: n=64 78% -4.1% | CONSENSUS: n=92 76% -0.2% | MODEL: n=92 75% -1.8%
  Premier League 2526              AGREE70: n=276 73% -7.1% | CONSENSUS: n=360 72% -7.2% | MODEL: n=360 69% -10.7%
  Primeira Liga 2526               AGREE70: n=192 75% -4.4% | CONSENSUS: n=293 73% -4.7% | MODEL: n=293 72% -4.9%
  Scottish Premiership 2526        AGREE70: n=167 71% -10.9% | CONSENSUS: n=216 69% -11.7% | MODEL: n=216 67% -13.4%
  Serie A 2526                     AGREE70: n=249 75% -4.9% | CONSENSUS: n=363 74% -4.0% | MODEL: n=363 72% -4.4%
```

## Validation (2026-10-02)

BANKER rule = straight win (1X2 home/away) or Over 2.5, in band, model and
market agree within 7pp, consensus >= 70%.

```
2025/26 (+ 2026/27 English lower tiers) — where the bucket was found
WIN_ONLY    n=186 hit=82.8% roi=+6.00%
    AWAY n=36 81% +3.2% | HOME n=95 85% +8.3% | OVER25 n=55 80% +3.9%

2024/25 — OUT OF SAMPLE (never seen when the rule was chosen)
MODEL     n=3259 hit=71.6% roi=-5.62%
AGREE70   n=2320 hit=74.0% roi=-5.53%
WIN_ONLY  n=227  hit=78.9% roi=+1.52%
    AWAY n=44 82% +5.1% | HOME n=115 80% +2.7% | OVER25 n=68 75% -2.9%
```

Decision: Over 2.5 failed out of sample, so BANKER = straight win only
(home/away). Two seasons combined: 290 picks, ~82% won, ~+4% ROI.

Every other rule wins ~71-74% of picks at 1.20-2.00 but LOSES ~6% — the
bookmaker margin is built into short prices. Model-only Under 2.5 picks hit
55% (-13%): the model under-predicts goals, so model and market must agree
before any pick is deployed (SPLIT = disagree > 7pp, never deployed).
