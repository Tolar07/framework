# Fixture Gathering Method — CONFIRMED

> **Status:** Confirmed by the Architect, 2026-09-16.
> **This is the method for answering "what are today's fixtures".**
> Implementation: `verification/collaborative_fixtures.py` (`gather()`).
> Name reconciliation: `verification/fixture_matcher.py`.
> Trust tiers: `verification/id403.py` (`SOURCE_TRUST`) — the single authority.

Related: [[Rules.md]] · [[Protected Constants.md]] · [[STATE.md]] · [[Architecture.md]]

---

## The principle

**Every source collaborates on one slate.** No single source is asked to be
correct on its own. Where one is weak or absent for a competition, the others
cover it; where several agree, that agreement *is* the verification.

This replaces the previous approach of asking one source at a time and treating
whatever came back as the answer.

## The four steps

### 1. Ask every source, for every whitelisted competition

Sources are queried independently through adapters in
`collaborative_fixtures.SOURCES`:

| Source | Tier | Role |
|---|---|---|
| ESPN | T1 | Structured, reliable; 28/29 whitelisted competitions mapped |
| FlashScore | T1 | Curated local feed; best coverage of cups and minor leagues |
| TheSportsDB | T2 | `eventsday` endpoint; fills continental ties the others miss |
| SportyBet | untiered | Odds and corroboration only — **never verifies alone** |

The competition list comes from `config/leagues.json` (`deploy_eligible=true`).

### 2. A failing source never fails the slate

Each adapter is isolated. An exception, a missing league mapping, or an empty
return is recorded as a source-level flag and the slate continues on the rest.
Absence is always reported, never silently filled (HR35).

This is the collaboration doing its job: on 2026-09-16 TheSportsDB initially
failed outright and the slate still produced a full verified set from the
others.

### 3. Reconcile club names across sources

Sources name the same club differently. Without reconciliation a corroborated
fixture splits into two single-source records and the quorum rule can never
fire — which is precisely why verification had collapsed.

`fixture_matcher.normalize_team_name` applies, in order: accent folding →
punctuation stripping → club-type token stripping (`FC`, `NK`, `SK`, `AZ`, …)
→ alias lookup → whole-token abbreviation expansion (`Utd`→`United`,
`Sheff`→`Sheffield`, `Atl`→`Atletico`, `Din`→`Dinamo`, `Lok`→`Lokomotiv`) →
alias lookup again.

`names_match` then allows a **token-subset** match, which reconciles the very
common case where one source qualifies a club with its city and another does
not — `Olympiacos` / `Olympiacos Piraeus`, `Zenit` / `Zenit St Petersburg`,
`Leverkusen` / `Bayer Leverkusen`.

**Guard rails.** The shorter name must contribute a non-generic token of length
≥ 4, so `Real Madrid`/`Real Sociedad` and `Manchester United`/`Manchester City`
can never collapse. A fixture merges only when **both teams, the league and the
kickoff** agree, so one loose team comparison cannot merge distinct fixtures.

Genuine synonyms — different names, not different spellings — need explicit
aliases: `Deportivo`/`A Coruña`, `Rennes`/`Stade Rennais`,
`Krylia Sovetov`/`Samara`, `Athletic Club`/`Ath. Bilbao`.

### 4. Verify by agreement — never by assertion

| Tier | Meaning |
|---|---|
| **VERIFIED** | Two or more independent sources agree, **or** one T1 source carries it |
| **SINGLE-SOURCE** | Carried by one non-T1 source — reported honestly, not deployed |
| **CONFLICT** | Sources disagree on kickoff beyond tolerance — surfaced, never silently resolved |

**The verification rule is never weakened to raise the verified count.** If the
number is low, the fix is more sources or better name reconciliation — never a
looser gate.

---

## Two failure modes this method exists to prevent

**1. A gate that always passes.** `_apply_verification` once read
"at least ONE source", which is trivially true of every row, so every fixture
was stamped `verified` unconditionally. A gate that emits the same signal
whether or not it is enforcing is indistinguishable from no gate. **Test any
verification change with a case that MUST fail.**

**2. Unbounded history.** `fetch_flashscore` once unioned every scrape file on
disk. FlashScore's `match_datetime` carries no year, so any historical scrape
holding that day/month lands on the target date — one corrupt scrape from
2026-08-29 injected four Celje fixtures that did not exist, and re-running only
compounded it. Feed files are now bounded to the week before the match day.

---

## Verification results — 2026-09-16 (the run that confirmed this method)

| Source | Fixtures | Leagues |
|---|---|---|
| ESPN (T1) | 17 | 4 |
| FlashScore (T1) | 23 | 5 |
| TheSportsDB (T2) | 19 | 4 |
| SportyBet | 446 | 7 |

**Merged: 472 → 23 VERIFIED** across 5 competitions. Most carry three
independent sources.

Before this method: 4 verified, and 163 fabricated fixtures stamped verified —
29 teams "playing" more than once on the same day, Celje in 7 simultaneous
matches.

Collaboration demonstrably covering gaps:

- **EFL Cup** — ESPN had no slug at all; FlashScore carried it; after mapping
  `eng.league_cup`, all 4 confirmed by both.
- **Ararat-Armenia, Omonia** — ESPN missed both; FlashScore + TheSportsDB
  verified them.
- **Swiss Super League** — ESPN returned 0; FlashScore + TheSportsDB verified
  both fixtures.

---

## Running it

```bash
python -c "from verification.collaborative_fixtures import gather; s=gather('YYYY-MM-DD'); print(len(s.verified),'verified')"
```

Every run carries a `run_id` and fetch timestamp (HR59). A fixture may only
appear in output if it came from a fetch in that session.

## Adding a source

Write one adapter returning `list[SourceFixture]`, add it to `SOURCES`, and add
its trust key to `_T1_SOURCE_KEYS`. Nothing else changes — more sources means
more corroboration, which is the point.

## Known gaps

- **Taça de Portugal** has no working ESPN slug (`por.taca_de_portugal` → HTTP
  400). Deliberately left unmapped: a guessed slug converts a loud "not mapped"
  error into a silent empty result.
- **SportyBet cache is stale** and its league mapping is wrong (Chelsea v
  Bournemouth filed under Ligue 2). Its rows are correctly held at
  SINGLE-SOURCE and never reach the verified slate, but the cache itself needs
  repair.
- **API-Football is not yet an adapter.** It is a paid T1 source and should be
  added — it would raise corroboration depth across every competition.
