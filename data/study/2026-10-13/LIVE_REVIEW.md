# 13 Oct Champions League — live, minute by minute, against our calls

Source: `live_tracker.py`, FotMob's live page polled every 2 minutes, 19:51–20:56 UTC
(`live/<fotmob id>.jsonl`; the two 16:45 games were already over at the first poll, so only
their finals are in it). Pre-match calls: the live board's singles
(`output/picks/picks_2026-10-13.json`) and the study board's legs (`engine_board.json`, run
STUDY-412d9663). Goal hints are the team profiles (`data/team_profiles.py`), plain and
strength-adjusted (`data/league_strength.py`, built tonight; it was NOT on the board).

## Results

| Match | FT | xG | On target | Board single | Study leg |
|---|---|---|---|---|---|
| Lens v Sporting | 0–2 | 1.72–1.67 | 6–5 | Lens Over 0.5 @1.22 **lost** | BTTS Yes @1.51 **lost** |
| Sabah v Slavia | 2–0 | 1.47–2.04 | 6–8 | Either team wins @1.29 **won** | Under 4.5 @1.23 **won** |
| Arsenal v Lille | 3–0 | 1.85–0.38 | 8–0 | Under 4.5 @1.27 **won** | Arsenal-or-draw & Over 1.5 @1.20 **won** |
| Atlético v Man Utd | 2–0 | 1.42–0.98 | 5–4 (Utd red) | Either team wins @1.27 **won** | 2–5 goals @1.20 **won** |
| Galatasaray v Barcelona | 1–4 | 0.43–2.83 | 3–11 | Over 2.5 @1.20 **won** | Barcelona & Over 1.5 @1.32 **won** |
| Inter v Club Brugge | 3–4 | 3.93–4.47 | 12–8 | Brugge Under 1.5 @1.20 **lost** | Inter win @1.26 **lost** |
| RB Leipzig v PSV | 1–0 | 2.10–1.40 | 7–5 | Either team wins @1.21 **won** | Over 2.5 & BTTS @1.46 **lost** |
| Viking v Bayern | 3–3 | 0.56–3.51 | 5–8 (Bayern red) | Under 6.5 @1.22 **won (6 goals)** | Bayern 3+ goals @1.27 **won** |
| Villarreal v Napoli | 3–1 | 1.34–1.87 | 4–3 | Either team wins @1.30 **won** | Villarreal win to nil — No @1.21 **won** |

- **Board singles: 7 won, 2 lost — and −0.24 units at £1 each.** At 1.20–1.30 a single needs to win
  77–83% just to break even; 7 of 9 is 78%.
- **Study legs (Champions League): 6 won, 3 lost, −1.57 units.**

## Minute by minute — where each call was decided

- **Inter v Brugge** — the call that was wrong before kick-off. Brugge's profile said ~1.8–1.9
  goals; the board backed Brugge to score at most one. Brugge led 0-1 at 30', had 1.36 xG by half
  time, scored their 2nd at 63' (pick lost) and finished with 4.47 xG. Inter win (study) died at
  74' (1-3). The game had 7 goals; both teams' hints (≈2 each) were far too low, but the
  direction — both sides score plenty — was right.
- **Viking v Bayern** — Viking 2-0 at 38' on 0.31 xG against Bayern's 1.20: finishing that
  doesn't last. Bayern scored at 54', 60', 71' (Bayern 3+ won at 71'); a Bayern red card, then
  Viking's 3-3 at 90' took the game to 6 goals — one short of losing Under 6.5.
- **Galatasaray v Barcelona** — 1-1 at half time with Barcelona 6 shots on target to 2; the 3rd
  goal came at 50' (Over 2.5 won), Barcelona's lead at 50' and 53' settled the study leg.
- **Arsenal v Lille** — 0-0 at half time, Lille without a shot on target all night; three goals
  in 7 minutes (64', 67', 71'). Under 4.5 then needed no more than one more goal for 20 minutes.
- **Atlético v Man Utd** — 1-0 after 1 minute; 2-5 goals stayed one short until 79'.
- **Leipzig v PSV** — 0-0 until 75' with 3.5 xG between them: "either team wins" was losing
  for 75 minutes, Over 2.5 & BTTS never came.
- **Lens v Sporting** — Lens 1.72 xG and 6 on target, no goal: the pick was right on the
  numbers and lost to finishing.

## The profiles against the night

Average gap between a team's goal hint and its final xG (16 team-games; Sabah had no xG profile):

| | All games | Without Inter–Brugge |
|---|---|---|
| Plain profile | 0.73 | 0.52 |
| Strength-adjusted | **0.70** | **0.49** |

The adjustment helped a little and called who would create more right in Arsenal–Lille
(2.08 v 0.75; final xG 1.85 v 0.38), Leipzig–PSV (2.50 v 1.53; 2.10 v 1.40) and Viking–Bayern
(1.28 v 2.74; 0.56 v 3.51); it got Atlético–Man Utd backwards (1.27 v 1.73; 1.42 v 0.98).
One night is not evidence — it goes into the profile study's running count.

## What we could have done better

1. **Brugge Under 1.5 contradicted Brugge's own profile.** A team Under 1.5 on a side expected to
   score ~1.8 is a bet against our own read. Candidate check for the Architect (no rule ID —
   only the Architect assigns them): no team Under where that team's goal hint is above ~1.3.
2. **Short-priced singles barely pay even when they win.** 7 of 9 still lost money. The board's
   selection makes winners; the prices (1.20–1.30) give the edge back. The same lesson as the
   Unders (STATE item 31): the stated chance must clear the price by a margin we have measured.
3. **The tail risk of Unders in mismatches.** Under 6.5 survived Viking–Bayern by one goal after a
   red card and a 90th-minute equaliser; Arsenal's three goals in 7 minutes took Under 4.5 to the
   edge. A dominant side plus a team chasing the game is where the long tail lives.
4. **In play, the xG told the story before the score did.** At half time Viking led 2-0 on 0.31 xG
   against 1.20; Galatasaray–Barcelona was 1-1 with Barcelona 6 on target to 2; Inter–Brugge
   already had 3.26 xG. Each time the second half followed the xG, not the score. We had no live
   prices tonight, so whether SportyBet's in-play odds lagged the xG can't be measured yet — the
   next step is to save SportyBet's live prices beside the xG in the tracker.
