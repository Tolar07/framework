# Football Markets Catalogue — every market, its rules, and how to bet it

> Architect's lesson (2026-10-12): every market is a set of yes/no options.
> BTTS is "Yes" **or** "No"; Over 1.5 has an Under 1.5 twin; Double Chance has
> three overlapping options. Learn the whole menu, learn the house rules,
> then apply strategy to it.
>
> Related: [[Betting-Market-Study-Guide.md]] · [[Sports_Betting_Study_Guide.md]] · [[Rules.md]] · `engine/full_markets.py` (the ladder that already prices SportyBet IDs 1–548 below).
>
> Prices in the worked examples are **illustrative, not real games** (HR59).

---

## 0. The one idea that makes every market simple

1. A football match ends in one **final state** (a scoreline, plus events: cards, corners, scorers, times).
2. Each market **splits every possible state** into its options. Exactly one option wins (or the stake is returned: a **push / void**).
3. Every option is a **1 / 0 bet**: it happened or it didn't. "BTTS No" is a bet as much as "BTTS Yes".
4. The book prices **every** option. Add up `1 / price` across all options of one market: the excess above 100% is the **margin**.
5. Strip the margin (de-vig) to get the book's honest chance. Back an option **only** when your chance is above `1 / price`, never because "they must score".

Three shapes of market:

| Shape | Options | Example | Can it push? |
|---|---|---|---|
| **Two-way** | A or not-A | BTTS Yes/No, Over/Under 2.5, Odd/Even, Clean sheet Yes/No | Only on whole lines (Over/Under 2.0) |
| **Three-way** | A, B, C | 1X2, European handicap, HT result | Never |
| **Many-way** | One of N | Correct score, exact goals, HT/FT, first scorer | "No goalscorer" option instead |
| **Overlapping** | Options share states | Double Chance (1X, X2, 12): each covers two of the three 1X2 states | Never |

Worked de-vig (illustrative): BTTS Yes 1.80, No 1.95 → 0.556 + 0.513 = 1.069 → 6.9% margin → fair Yes = 0.556 / 1.069 = **52.0%**, fair No = **48.0%**. If your model says Yes 58%, Yes at 1.80 (needs 55.6%) is value. If it says Yes 45%, then No is 55%, which beats the 51.3% that No at 1.95 needs, so **No** is the bet.

---

## 1. House rules that settle everything (check each book's own page)

| Rule | Usual standard (SportyBet, bet365, Betway, 1xBet, Bet9ja, Pinnacle…) |
|---|---|
| **Regular time only** | Markets settle on 90 min + stoppage time. Extra time and penalties do **not** count, except markets that say so ("To Qualify", "To Lift Trophy", "Method of Victory"). |
| **Postponed / abandoned** | Void unless played/resumed within the book's window (commonly 24–48 h; Pinnacle uses the scheduled start). Markets **already decided** at abandonment stand (e.g. Over 1.5 already won at 2-0; BTTS Yes already won). |
| **Void leg in an acca** | Counts as price 1.00; the slip continues on the remaining legs. |
| **Own goals** | Count for the team's goal markets; **don't** count for any player scorer market. |
| **Player markets** | Player doesn't take part → void. Player comes on **after** the first goal → First Goalscorer **loses** (it's still in play for Anytime). Bet365/Paddy-style "early payout"/"sub" offers vary by book. |
| **Cards** | Booking points: yellow = 10, red = 25, a second-yellow red = yellow 10 + red 25 (most books cap 35 per player). Cards to managers/bench/after the final whistle usually don't count. |
| **Corners** | Awarded but not taken don't count; retaken corners count once. |
| **Asian lines** | Whole line → push on exact; half line → no push; quarter line → half the stake on each neighbour (§3). |
| **Palpable error / closed lines** | Books void obvious mispricing. SportyBet lines with **market status 2** show stale prices: the code loads but **can't be placed**; only status 0 counts ([[sportybet-closed-lines]]). |
| **Max payout / combos** | Each book caps winnings per slip; SportyBet "bet builder" and related-leg rules block some correlated combos. |
| **Dead heat** | Tied outright places (top scorer) split the stake. |

---

## 2. Full-match result family

| Market (SportyBet ID) | Options | Wins when | Pushes? |
|---|---|---|---|
| **1X2** (1) | Home / Draw / Away | final result | — |
| **Double Chance** (10) | 1X / X2 / 12 | result is either of the two | — |
| **Draw No Bet** (11) | Home / Away | that side wins | draw |
| **Home No Bet** (12) | Draw / Away | that result | home win |
| **Away No Bet** (13) | Home / Draw | that result | away win |
| **Winning margin** | Home by 1/2/3+, Draw (score draw / 0-0), Away by 1/2/3+ | exact margin band | — |
| **Win to nil** (33 home, 34 away) | Yes / No | win **and** clean sheet | — |
| **Win from behind / comeback** | Yes / No | team trails then wins | — |
| **Win either half / win both halves** | Yes / No | team wins ≥1 half / both halves | — |
| **Half-time result** | 1 / X / 2 | score at HT | — |
| **2nd-half result** | 1 / X / 2 | goals in 2H only | — |
| **HT/FT** | 9 options: 1/1, 1/X, 1/2, X/1, X/X, X/2, 2/1, 2/X, 2/2 | both match | — |
| **Highest scoring half** | 1st / 2nd / Equal | half goal counts | — |
| **To qualify / lift trophy** | Team A / Team B | **includes** ET & penalties | — |
| **Method of victory** | 90 min / ET / Pens (per team) | how they qualify | — |
| **1UP / 2UP** (SportyBet/bet365 early-payout 1X2) | Home / Draw / Away | normal 1X2 **or** that team goes 1 (2) goals up at any time | — |

Combos on the result:

| Market (ID) | Options | Wins when |
|---|---|---|
| **1X2 & Goals** (37) | Home/Draw/Away & Over/Under X.5 | both true |
| **DC & Goals** (547) | 1X/X2/12 & Over/Under X.5 | both true |
| **1X2 & BTTS** | Home/Draw/Away & Yes/No | both true |
| **DC & BTTS** (546) | 1X/X2/12 & Yes/No | both true |
| **Result & first scorer / scorecast** | Player & correct score or result | both true |

---

## 3. Handicaps

**European handicap (14)** — 3-way, whole goals, never pushes. `0:1` adds one goal to the away team: Home (0:1) wins only if home wins by 2+; Draw (0:1) wins if home wins by exactly 1; Away (0:1) wins on draw or away win.

**Asian handicap (16)** — 2-way, the draw is removed. Line is the home side's adjustment.

| Line | Home wins by… | Settlement |
|---|---|---|
| 0 | — | = **Draw No Bet** (push on draw) |
| −0.5 | 1+ | = Home win (1X2) |
| +0.5 | win or draw | = **1X** |
| −1.0 | 2+ win; **1 → push** | |
| −1.5 | 2+ | no push |
| −0.25 (0/−0.5) | half on 0, half on −0.5 | draw → half push, half loss |
| −0.75 (−0.5/−1) | win by 1 → half win, half push; 2+ → full win | |
| +0.25 / +0.75 | mirror images | |

The framework skips quarter lines (HR35) rather than approximating them.

**Asian totals** — same logic on goals: 2.0 (push on 2), 2.25 (half 2.0 / half 2.5), 2.75 (half 2.5 / half 3.0).

**Handicap on corners / cards** — same mechanics on the event count.

---

## 4. Goals family

| Market (ID) | Options | Wins when |
|---|---|---|
| **Over/Under total** (18) | lines 0.5 … 7.5 | total above / below line |
| **Home team Over/Under** (19), **Away** (20) | lines 0.5 … 4.5 | that team's goals |
| **1st-half / 2nd-half Over/Under** | 0.5, 1.5, 2.5 | goals in that half |
| **Exact total goals** (21) | 0, 1, 2, 3, 4, 5, 6+ | exact count |
| **Home / Away exact goals** (23 / 24) | 0, 1, 2, 3+ | |
| **Goal range** (25), **Multigoals** (548) | 1-2, 1-3, 2-3, 2-4, 3-5, 4-6, 7+ … | total inside the band |
| **Odd / Even** (26) | Odd / Even | 0 counts as even |
| **BTTS** (29) | Yes / No | both score / at least one doesn't |
| **Teams to score** (30) | None / Only Home / Only Away / Both | |
| **Clean sheet** (31 home, 32 away) | Yes / No | opponent scores 0 |
| **Goals & BTTS** (36) | Over/Under X.5 & Yes/No | both true |
| **BTTS 1st half / 2nd half / both halves** | Yes / No | |
| **Team to score in both halves** | Yes / No | |
| **Goal in both halves** | Yes / No | ≥1 goal in each half |
| **Both halves Over/Under 1.5** | Yes / No | |
| **First team to score / Last team to score** | Home / No goal / Away | |
| **Time of first goal** | 1–10, 11–20 … 81–90, No goal; or Before/After 27:00 | |
| **Interval markets** (10/15 min) | goal Yes/No, result per interval | |
| **Race to 2/3 goals** | Home / Away / Neither | |
| **Total goals + half** (e.g. 2H Over 1.5) | Yes / No | |

**Correct score family:** full-time correct score (every score + "Any other home/draw/away"), half-time correct score, HT/FT correct score, multi-scores ("1-0, 2-0 or 2-1").

**Key identities (use them to catch mispriced lines — the ladder's LINE_TOLERANCE guard):**
- Over 0.5 = "not 0-0"; Under 0.5 = 0-0 = Teams to score "None".
- BTTS Yes ⊂ Over 1.5. So **Under 1.5 & BTTS Yes is impossible**; BTTS Yes can never be priced shorter than Over 1.5.
- Win to nil sits inside both Win and Clean sheet, so it can never be priced shorter than either.
- Home Win = AH −0.5; 1X = AH +0.5; DNB = AH 0.
- P(1X) = P(1) + P(X). If DC prices disagree with the 1X2 after margin, one of them is stale.
- Exact goals 0 + 1 = Under 1.5; Goal range 2-3 = Over 1.5 minus Over 3.5.

---

## 5. Corners, cards, and match-stats markets

| Family | Markets |
|---|---|
| **Corners** | Total O/U, team O/U, corner handicap, 1H corners, race to 3/5/7/9, first/last corner, most corners (1X2), odd/even, corner in time band |
| **Cards** | Total cards O/U, booking points O/U, team cards, most cards, red card Yes/No, first card team/player, player to be carded/sent off, card in both halves |
| **Shots/stats** | Team shots, shots on target, offsides, fouls, throw-ins, goal kicks, possession bands, saves |
| **Specials** | Penalty awarded / scored / missed, own goal Yes/No, VAR overturn, substitute to score, goal from header / outside box / free kick |

Cards and corners depend heavily on the **referee**, the **matchup** (pressing vs. deep block) and the **game state** (a team chasing wins corners) — none of which is in a scoreline model. The framework does **not** price them; treat any pick here as unmodelled.

---

## 6. Player markets

Anytime / first / last goalscorer; to score 2+ / hat-trick; score or assist; to assist; shots and shots on target O/U; tackles, fouls, passes, saves (goalkeeper); to be carded; man of the match. Settlement: void if the player doesn't play; own goals never count; first-scorer **loses** if the player comes on after the first goal.

---

## 7. Long-term (outright) markets

League winner, top 2/4/6, relegation, to stay up, without the favourite, top goalscorer (dead heat rules), group winner, to reach the final / round, straight forecast (1st & 2nd), season points / wins O/U, manager sack. Margins here are large (often 20%+ summed) and the money is tied up for months.

---

## 8. Live (in-play) markets

Next goal (Home / No goal / Away), rest-of-match 1X2 (scores from now only), live Asian lines, next corner/card, goal in next 10 min, live correct score. Prices move every few seconds and books **suspend** on danger; a delay protects the book. Cash-out is the book buying your bet back at its price + margin.

---

## 9. Exchanges (Betfair, Matchbook)

Every option can be **backed** (it happens) or **laid** (it doesn't). Laying Home = backing X2, but at a peer price with commission (2–5% of winnings) instead of a built-in margin. Exchange prices are the cleanest "true price" reference after Pinnacle.

---

## 10. Strategy — what our own data says, applied to the menu

From 1,434 graded games (10–11 Oct 2026), the main singles since 3 Oct, and X tipster legs ([[worldwide-results-oct-10-11]]):

1. **Our chances are honest; the price is the leak.** Singles won 191/246 against 192 expected yet lost −9.9u. Winning more picks doesn't fix that — getting a better price does. Target: **beat the closing price** (CLV), not a high hit rate.
2. **Always check both sides.** For every pick, also price its twin (No, Under, X2). Pick whichever side clears `1/price` by the most — sometimes it's the "No".
3. **Low-margin markets first.** Measure the margin (sum of `1/price` − 1) on each market at SportyBet. 1X2, main totals and Asian lines are usually thinnest; correct score, scorers, combos, corners/cards and outrights are fattest.
4. **Favourite–longshot bias is real.** 60%+ chances landed 3–7 pts above stated; ~20% chances landed 18%. Least bad: favourites 1.50–2.00, Over 1.5, Under 3.5. Worst: Over 3.5, Under 1.5, BTTS No, DC X2.
5. **Don't pile up sub-1.30 legs.** Tipster legs under 1.30 landed 78% vs 83% implied — that is what kills their accas. Legs at 1.30–2.00 beat implied.
6. **Respect price drift.** Prices that drifted 5%+ before kickoff won 27% (−12.7%): the market knew something (order 25).
7. **Use the identities.** If BTTS Yes is shorter than Over 1.5, or DC disagrees with 1X2, one line is stale or closed — don't pick it; check market status.
8. **Correlated combos are priced for it.** "Home & Over 2.5" is not P(home) × P(over); books know that, and they add margin. Combine legs from **different games**, not correlated legs from one game, unless the bet builder price beats your joint chance.
9. **League context:** draws ran far below the market in high-scoring leagues (Sweden, Czechia, Norway, Poland, Belgium, Greece, Germany) and above it in Spain, China, Brazil, USA — small samples, a hint, not a rule. The league alone was no edge in the 149k-match draw study.
10. **Unmodelled markets stay unmodelled.** Corners, cards, players and live lines need data we don't have; picks there are opinions until a study proves otherwise.

Any rule built from this goes through the paper book's **100+ bet** bar and the Architect's approval before it selects anything.
