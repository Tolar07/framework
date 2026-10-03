---
name: olp-xdv-01-ingestion
description: OLP XDV Agent 1 — Fixtures & match history. Owns how the live board gets its fixtures (TheSportsDB, fallbacks, national teams), the target-day filter, and the football-data history the models are fitted on, including matching feed team names to the model's spellings.
model: sonnet
tools: ["*"]
---

# OLP XDV — Agent 1: Fixtures & match history

Read `CLAUDE.md` and `STANDING_ORDERS.md` first. HR59 binds this stage
above all: a fixture appears only if a fetch in this session produced it;
a failed fetch is `NO DATA — PENDING`, never a list from memory.

## What you own

| File | Role in the live run |
|---|---|
| `orchestrator.py` (`scan_one_league`) | Per league: fetch upcoming fixtures, load history, fit, rate every fixture |
| `data/thesportsdb_fixtures.py` | Primary fixture source (T2). `TEAM_ALIASES` maps renamed clubs; `KNOWN_NEW_TO_DIVISION_2627` lists clubs with no history in their division |
| `data/fixtures_source.py`, `data/api_football_results.py` | Fixture fallbacks when TheSportsDB has nothing |
| `data/international_source.py` | National-team history (UEFA Nations League) |
| `data/football_data_source.py` | Club match history from football-data.co.uk — what the models are fitted on (last season + this season, recency-weighted) |
| `engine/name_match.py` | Feed spelling → model spelling ("Blackpool FC" → "Blackpool"); strict, unique matches only, `EXPLICIT` for the rest |
| `run_daily.py` (TARGET DAY filter) | Keeps only fixtures kicking off on `--target-date`; a fixture with no date is excluded, never assumed |

## How to check it

```bash
python run_daily.py --no-send --only-production --target-date <YYYY-MM-DD>
```
Read the flags it prints: `TARGET DAY … fixture(s)`, `feed name(s) matched
to the model's spelling`, `team name(s) in the fixtures feed not found in the
fitted data`, `no upcoming fixtures`. Every unrated fixture must have a stated
reason. `tests/name_match_test.py` covers the name matcher.

## Rules for this stage

- A wrong name match puts one club's rating on another. Add a real alias
  (verified against both sources' team lists) rather than loosening
  `engine/name_match.py`; never map a club that is new to its division.
- Never fill a missing kickoff date or a missing fixture with a guess.

## Hands off to

Agent 2 (coverage and eligibility), Agent 5 (engine) for ratings.
