---
name: football-absence-impact
description: >
  Judge whether an injured, suspended or rotated football player really weakens his team
  before any team-news flag (CAUTION / RISK) is raised or acted on. Use when: a line-up or
  team-news alert fires, a bot is about to cash out or exit on news, someone asks "does this
  absence matter?", or engine/squad_depth.py / engine/team_news.py is being changed. Don't use
  when: the question is about a player's form or price with no absence involved, or for NBA
  (different rotation rules).
metadata:
  sources:
    - "https://www.youtube.com/watch?v=G_mK5rmHglg — Pinnacle, 'How Injuries Change Soccer Betting Markets | Pinnacle FC Ep. 121' (watched 2026-11-04, local WhisperX transcript; frames: two-presenter studio, no slides)"
    - "https://www.youtube.com/watch?v=CRVoSe_Ueys — DWS News, 'FULL PRESSER: Mourinho Explains Squad Depth, Rotation, and Team Unity' (Spanish, watched 2026-11-04, local WhisperX transcript)"
    - "https://www.youtube.com/watch?v=K6KhzmxVWJc — Tifo Football by The Athletic, 'Why is football so hard to analyse?' (watched 2026-11-04, local WhisperX transcript)"
  trigger: "Architect 2026-11-04 16:42 — false LINEUP RISK on Real Madrid (25% 'missing') and Liverpool (31%)"
---

# Football absence impact

An absence matters only when it changes what the team can do in THIS match. The raw "share of
market value missing" overstates it whenever the player was already out, is a rotation player,
or has like-for-like cover. In this repo, `engine/squad_depth.py` and `engine/squad_profile.py`
apply the steps below.

## Activation rules

- A pre-kick-off line-up check or board-time team-news check would rate a pick CAUTION or RISK.
- A bot's cash-out or exit rule is about to act on a news level (SportyBet `cashout_rules.NEWS`,
  Matchbook / Betfair `exits.NEWS-*`).
- Someone edits `engine/team_news.py`, `engine/squad_depth.py`, `data/fotmob._side` or the levels.

## Step-by-step

1. **List the absentees** with FotMob ids and market values (`data/fotmob._side` → `missing`).
2. **Drop the priced-in ones.** For each, count starts in the team's last 5 matches, all
   competitions (`squad_depth.recent_match_ids` + `starters_of`). 0 of 5 → weight 0, reason
   "already out, priced in". The team's form and the market already carry it. Mourinho on
   Militão, Rodrygo and Asencio: "more complicated processes" (presser @ 16:57). They were long-term.
3. **Weigh by role.** Weight = starts / 5. A rotation player (≈ 2–3 of 5) counts partly.
   `squad_profile.role`: regular ≥ 70% of starts, rotation 30–70%, fringe < 30%.
4. **Find the cover** from players NOT in this match's XI, not injured, one cover per absence.
   Use the player's own position group first (GK, CB, FB, MID, AM, ATT; full-backs and
   centre-backs are separate). Failing that, a neighbouring group's player counts at half his
   value (makeshift). Loss factor = 1 − min(1, fit × cover value / player value).
5. **Effective share** = Σ(value × weight × loss) / (XI value + Σ). The level comes from this share
   (CAUTION ≥ 12%, RISK ≥ 25%, unchanged thresholds). Keep the raw share beside it.
6. **Read the manager's habit** (`data/players/`, `squad_profile.rotation`). XI changes per match,
   split by short rest (≤ 3.5 days) and long rest. A coach who changes 4–6 after midweek is
   resting players, not losing them. Note it in the reason.
7. **Write the reason per player** into the note ("Rodrygo: already out, priced in; Gravenberch:
   rotation 3/5, cover Wirtz 100%"), so the Architect and the bots see why.
8. **Check the structural question last.** Does the absence force a shape change (no fit
   full-back, no striker, a third keeper)? If so, say so in the note even when the share is small.

## Best practices

- Rotation is planned, not a weakness: players are rested before a key match (Pinnacle @ 12:05,
  "he'll get a rest today so he's fit for the weekend"). Mourinho rotates Cucurella and Carreras,
  with Álvaro to come on at 70–75' (presser @ 00:48–01:17).
- Like-for-like swaps are not dramatic. Structural changes are (Mourinho @ 22:39–23:09: "the
  difference between Carreras and Cucurella is not dramatic"; three centre-backs would be).
- Position matters more than value: a makeshift left-back against a winger in form is the real
  risk (Pinnacle @ 12:05–12:34).
- Depth shows on the bench: a bench full of youth players means changes hurt (Pinnacle @ 23:14,
  20:15: Liverpool "made so many changes" and were 2-0 down until "the big boys" came on).
- A side's second string still beats a weak opponent (Pinnacle @ 19:48, Conference League).
  Rotation risk depends on the opponent's strength.
- One star can matter: "your best player, a huge blow" (Pinnacle @ 23:14). Cover ratio, not
  head count, decides.
- Fixture congestion raises injury risk: "the more minutes you play, the higher chance of getting
  injured" (Pinnacle @ 01:02). Injuries cluster after international breaks (Mourinho @ 19:44).

## Common mistakes

- **Counting every unavailable player as a starter.** This was the 4 Nov fault: Real Madrid read
  25% missing, but it was 6–8% after depth. Spot it: an absentee with 0 recent starts in the
  reason list.
- **Picking a starter as the cover.** Bellingham can't cover Güler if both start. Exclude the XI.
- **Treating one player as cover for two absences.** Use one cover per absence.
- **Trusting the injury list blindly.** A player listed doubtful turns up fit (Pinnacle @ 02:57).
  Prefer the confirmed XI when it exists.
- **Acting on news the market already moved on.** Markets can overreact to absences ("numbers
  pushed out too far just because of the suspensions", Pinnacle @ 28:13). Test this against the
  edge book's exchange close before letting news sell a bet.

## Quality check

- [ ] Every absentee has a starts count over the last 5 and a reason.
- [ ] No cover is in tonight's XI; no cover is used twice.
- [ ] The level comes from the adjusted share; the raw share is shown beside it.
- [ ] The manager's rotation habit is quoted when data/players/ has the team.
- [ ] Any structural gap (no fit full-back / keeper / striker) is named.
- [ ] Nothing here changed a stake or a threshold (House rules).

## Incident: a wrong flag is about to trigger actions

When the Architect corrects a false flag shortly before kick-off:

1. List who acts on the flag (three bots exit on RISK/CAUTION).
2. Correct tonight's live records on main first, with the same function and the originals kept in `*_raw` fields.
   CI takes about 12 minutes and the news loop skips picks it already checked, so a code PR first would miss kick-off.
3. Then ship the code fix and any research as PRs.

Correcting a record is not changing a rule: House rules below still apply.

## House rules (OLP XDV)

- RECORDED ONLY beyond the level itself. Stake sizes, thresholds (12% / 25%) and whether bots
  cash out on news are the Architect's decisions.
- HR35 / HR59: no invented players, starts or values. If FotMob has no team page, the raw rule
  applies and the note says so.
- Open hypotheses for the edge book, not rules: (a) do markets overreact to absences (Pinnacle
  @ 28:13)? (b) does rotation against a weak opponent still win? Measure them first.

## Evidence table

| Claim | Source @ time | Status |
|---|---|---|
| Long-term absentees ("more complicated processes": Militão, Rodrygo, Asencio) | Mourinho @ 16:57 | said only (Spanish) |
| Like-for-like rotation not dramatic; structural change worries | Mourinho @ 22:39–23:09 | said only |
| Strong squad "with solutions to compensate"; planned sub at 70–75' | Mourinho @ 00:48–01:17 | said only |
| Players rested midweek so they're fit for the weekend | Pinnacle @ 12:05 | said only |
| Makeshift left-back vs a winger in form is the real risk | Pinnacle @ 12:05–12:34 | said only |
| Thin squad: many changes → 2-0 down, starters brought on | Pinnacle @ 20:15–20:37 | said only |
| Second string still wins vs weak opponent | Pinnacle @ 19:48 | said only |
| Markets can overreact to suspensions | Pinnacle @ 28:13 | said only (hypothesis) |
| More minutes → more injuries; post-break injuries | Pinnacle @ 01:02; Mourinho @ 19:44 | said only, two sources agree |
| Data in football is hardest to use for tactics; best for recruitment ("better players play better") | Tifo @ 05:00 | said + shown (animated) |
| Frames | Pinnacle frames @ 13:02, 26:35: studio, match graphics only | shown only (no slides) |

Not checked: the presenters' betting records (they claim +5 / +8 units, no sample or out-of-sample
test, so it's an anecdote); Mourinho's statements are pre-season 2026/27 context, not a dataset.
Caption tracks were rate-limited (HTTP 429), so all three transcripts are local WhisperX "small".
Names and numbers were cross-read against FotMob, not trusted from the audio.
