# BTTS STUDY — 2026-10-05

**Question (Architect, 5 Oct):** both teams to score was "quite obvious" in
several recent games, yet the board has never picked it. Is BTTS a market the
model can call, and how sure can a BTTS pick be?

**Method:** `backtest/btts_study.py`. Walk-forward over the same 14 leagues and
two seasons as `SELECTION_STUDY.md` (Dixon-Coles refitted every 14 days on
earlier matches only). 3,550 matches. football-data.co.uk has no BTTS prices,
so this measures how often each call landed and the fair odds it needs — not
profit.

## Results

BTTS landed in 55.0% of all matches.

| Model says BTTS | Matches | Landed | Fair odds needed |
|---|---|---|---|
| under 40% | 476 | 48.3% ±2.3 | 2.07 |
| 40–50% | 1,132 | 52.6% ±1.5 | 1.90 |
| 50–55% | 739 | 55.2% ±1.8 | 1.81 |
| 55–60% | 605 | 59.2% ±2.0 | 1.69 |
| 60–65% | 378 | 60.8% ±2.5 | 1.64 |
| 65–70% | 168 | 58.3% ±3.8 | 1.71 |
| 70% and over | 52 | 67.3% ±6.5 | 1.49 |

Same table for goals lines (model's chance → landed):
Over 1.5 at 70%+: 2,504 matches, 79.6%. Over 2.5 at 70%+: 212 matches, 72.2%.

BTTS where the model says 60%+, by league: Championship 70% (56), National
League 70% (43), Eredivisie 66% (86), La Liga 64% (33), Bundesliga 62% (123),
Premier League 58% (91), Belgian Pro League 53% (43), Ligue 1 51% (70).

Live record (3–4 Oct, 12 graded rated fixtures): BTTS landed 7 of 12; the
model's average BTTS chance was 45%.

## What it means

1. **The model under-rates BTTS.** Where it says 40–50% BTTS lands 52.6%;
   overall it lands 55%. The live days show the same gap (45% said, 58% landed).
   A recalibration of the BTTS line is a model fix worth making.
2. **BTTS is never near-certain.** Even the model's strongest calls (70%+, only
   52 matches in two seasons) landed 67%. A strong BTTS call is a 60–67% bet
   that needs a price of about 1.50–1.65 or better to pay.
3. **Why the board never picks it:** each fixture's pick is the in-band outcome
   most likely to WIN (orders 11, 12, 24). A 75–80% Double Chance or Over 1.5
   always outranks a 60% BTTS, so BTTS can only appear as the alternative
   market. Picking BTTS would lower the hit rate and is only worth it where its
   price is better than fair — that is a selection change for the Architect.
4. Leagues differ: Championship, National League, Eredivisie and Bundesliga
   hold their BTTS calls; Ligue 1 and Belgium do not.
