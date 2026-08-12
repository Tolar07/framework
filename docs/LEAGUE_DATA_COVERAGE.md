# LEAGUE DATA COVERAGE MATRIX — OLP XDV
**Version:** 2026-08-10  
**Status:** Live reference — updated for 2026/27 season  
**Scope:** All 25 whitelisted leagues in `engine.leagues.WHITELISTED_LEAGUES` (unified pool — softness tiers fully removed 2026-08-11; UEFA Super Cup + 6 new European leagues added 2026-08-12)

---

## COVERAGE LEGEND
| Symbol | Meaning |
|--------|---------|
| ✅ **WIRED** | Source verified live, key/endpoint confirmed, data flows to engine |
| ⚠️ **PARTIAL** | Source works but has limitations (truncation, rate limits, free-tier gaps) |
| ❌ **GAP** | No free source available — needs paid plan or personal key |
| 🔧 **NEXT STEP** | Concrete action to close the gap |

---

## SUMMARY TABLE

| # | League | History (T1) | Fixtures (T2) | Live Odds (Sport Key) | xG (Understat) | Live Scores | Booking Map (SportyBet) |
|---|--------|--------------|---------------|----------------------|----------------|-------------|------------------------|
| 1 | Premier League | ✅ `E0` | ✅ thesportsdb (5558126822) | ✅ `soccer_epl` | ✅ `EPL` | ✅ | ✅ "England" / "Premier League" |
| 2 | La Liga | ✅ `SP1` | ✅ thesportsdb | ✅ `soccer_spain_la_liga` | ✅ `La_liga` | ✅ | ✅ "Spain" / "LaLiga" |
| 3 | Serie A | ✅ `I1` | ✅ thesportsdb | ✅ `soccer_italy_serie_a` | ✅ `Serie_A` | ✅ | ✅ "Italy" / "Serie A" |
| 4 | Bundesliga | ✅ `D1` | ✅ thesportsdb | ✅ `soccer_germany_bundesliga` | ✅ `Bundesliga` | ✅ | ✅ "Germany" / "Bundesliga" |
| 5 | Ligue 1 | ✅ `F1` | ✅ thesportsdb | ✅ `soccer_france_ligue_1` | ✅ `Ligue_1` | ✅ | ✅ "France" / "Ligue 1" |
| 6 | Champions League | ❌ (continental) | ✅ thesportsdb | ✅ `soccer_uefa_champs_league` | ❌ | ✅ | ✅ "Int'l Clubs" / "UEFA Champions League" |
| 7 | Europa League | ❌ (continental) | ✅ thesportsdb | ✅ `soccer_uefa_europa_league` | ❌ | ✅ | ✅ "Int'l Clubs" / "UEFA Europa League" |
| 8 | Scottish Premiership | ✅ `SC0` | ✅ thesportsdb | ✅ `soccer_scotland_premiership` | ❌ | ✅ | ✅ "Scotland" / "Premiership" |
| 9 | Belgian Pro League | ✅ `BE1` | ✅ thesportsdb | ✅ `soccer_belgium_first_div_a` | ❌ | ✅ | ✅ "Belgium" / "Pro League" |
| 10 | Eredivisie | ✅ `N1` | ✅ thesportsdb | ✅ `soccer_netherlands_eredivisie` | ❌ | ✅ | ✅ "Netherlands" / "Eredivisie" |
| 11 | Championship | ✅ `E1` | ✅ thesportsdb | ✅ `soccer_england_championship` | ❌ | ✅ | ✅ "England" / "Championship" |
| 12 | Primeira Liga | ✅ `P1` | ✅ thesportsdb | ✅ `soccer_portugal_primeira_liga` | ❌ | ✅ | ✅ "Portugal" / "Liga Portugal" |
| 13 | Danish Superliga | ✅ `DK1` | ✅ thesportsdb | ✅ `soccer_denmark_superliga` | ❌ | ✅ | ✅ "Denmark" / "Superliga" |
| 14 | Ekstraklasa | ✅ `POL` | ✅ thesportsdb (4422) | ✅ `soccer_poland_ekstraklasa` | ❌ | ✅ | ✅ "Poland" / "Ekstraklasa" |
| 15 | HNL | ❌ **GAP** | ✅ thesportsdb (4629) | ⚠️ `soccer_croatia_hnl` (unverified) | ❌ | ✅ | ✅ "Croatia" / "HNL" |
| 16 | Austrian Bundesliga | ❌ **GAP** | ✅ thesportsdb (4621) | ✅ `soccer_austria_bundesliga` | ❌ | ✅ | ⚠️ "Austria" / "Bundesliga" (TBC) |
| 17 | EFL Cup | ❌ **GAP** | ⚠️ odds-derived only | ✅ `soccer_england_efl_cup` | ❌ | ✅ | ✅ "England" / "EFL Cup" |

---

## DETAILED PER-LEAGUE MATRIX

---

### 1. Premier League
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `E0` | ✅ WIRED | Complete T1 source, daily refresh |
| **Fixtures** | TheSportsDB (personal key) | league_id TBC | ✅ WIRED | Season feed + eventsday |
| **Live Odds** | The Odds API | `soccer_epl` | ✅ WIRED | Bet365 UK, 2 markets (h2h, totals) |
| **xG** | Understat | `EPL` | ✅ WIRED | Big-5 coverage |
| **Live Scores** | Football-Data / TheSportsDB | — | ✅ WIRED | |
| **Booking** | SportyBet | "England" / "Premier League" | ✅ WIRED | Verified 2026-08-08 sidebar |

**Domestic cup sport keys (TBC — probe `/v4/sports`):**
- FA Cup: `soccer_england_fa_cup`
- EFL Cup: `soccer_england_efl_cup`

---

### 2. La Liga
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `SP1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_spain_la_liga` | ✅ WIRED | |
| **xG** | Understat | `La_liga` | ✅ WIRED | |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Spain" / "LaLiga" | ✅ WIRED | Verified |

**Domestic cup:**
- Copa del Rey: `soccer_spain_copa_del_rey` (TBC)

---

### 3. Serie A
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `I1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_italy_serie_a` | ✅ WIRED | |
| **xG** | Understat | `Serie_A` | ✅ WIRED | |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Italy" / "Serie A" | ✅ WIRED | Verified |

**Domestic cup:**
- Coppa Italia: `soccer_italy_coppa_italia` (TBC)

---

### 4. Bundesliga
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `D1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_germany_bundesliga` | ✅ WIRED | |
| **xG** | Understat | `Bundesliga` | ✅ WIRED | |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Germany" / "Bundesliga" | ✅ WIRED | Verified |

**Domestic cup:**
- DFB-Pokal: `soccer_germany_dfb_pokal` (TBC)

---

### 5. Ligue 1
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `F1` | ✅ WIRED | 18 clubs since 2023/24 |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_france_ligue_1` | ✅ WIRED | |
| **xG** | Understat | `Ligue_1` | ✅ WIRED | |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "France" / "Ligue 1" | ✅ WIRED | Verified |

**Domestic cup:**
- Coupe de France: `soccer_france_coupe_de_france` (TBC)

---

### 6. Champions League
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | — | — | ❌ **GAP** | Continental — no football-data. API-Football (paid) or TheSportsDB only |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_uefa_champs_league` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat covers domestic only |
| **Live Scores** | TheSportsDB | — | ✅ WIRED | |
| **Booking** | SportyBet | "Int'l Clubs" / "UEFA Champions League" | ✅ WIRED | Verified |

---

### 7. Europa League
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | — | — | ❌ **GAP** | Continental — no football-data |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_uefa_europa_league` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | |
| **Live Scores** | TheSportsDB | — | ✅ WIRED | |
| **Booking** | SportyBet | "Int'l Clubs" / "UEFA Europa League" | ✅ WIRED | Verified |

---

### 8. Scottish Premiership
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `SC0` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_scotland_premiership` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Scotland" / "Premiership" | ✅ WIRED | Verified |

**Domestic cups:**
- Scottish Cup: `soccer_scotland_scottish_cup` (TBC)
- League Cup: `soccer_scotland_league_cup` (TBC)

---

### 9. Belgian Pro League
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `BE1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_belgium_first_div_a` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Belgium" / "Pro League" | ✅ WIRED | Verified |

**Domestic cup:**
- Belgian Cup: `soccer_belgium_belgian_cup` (TBC)

---

### 10. Eredivisie
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `N1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_netherlands_eredivisie` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Netherlands" / "Eredivisie" | ✅ WIRED | Verified |

**Domestic cup:**
- KNVB Beker: `soccer_netherlands_knvb_beker` (TBC)

---

### 11. Championship
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `E1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_england_championship` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "England" / "Championship" | ✅ WIRED | Verified |

---

### 12. Primeira Liga
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `P1` | ✅ WIRED | |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_portugal_primeira_liga` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Portugal" / "Liga Portugal" | ✅ WIRED | Verified |

**Domestic cups:**
- Taça de Portugal: `soccer_portugal_taca_de_portugal` (TBC)
- Taça da Liga: `soccer_portugal_taca_da_liga` (TBC)

---

### 13. Danish Superliga
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `DK1` | ✅ WIRED | Split format |
| **Fixtures** | TheSportsDB | league_id TBC | ✅ WIRED | |
| **Live Odds** | The Odds API | `soccer_denmark_superliga` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Denmark" / "Superliga" | ✅ WIRED | Verified |

**Domestic cup:**
- Danish Cup: `soccer_denmark_danish_cup` (TBC)

---

### 14. Ekstraklasa
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | Football-Data.co.uk | `POL` | ✅ WIRED | Polish feed |
| **Fixtures** | TheSportsDB (personal key) | `4422` | ✅ WIRED | Resolved 2026-08-08 |
| **Live Odds** | The Odds API | `soccer_poland_ekstraklasa` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | — | — | ✅ WIRED | |
| **Booking** | SportyBet | "Poland" / "Ekstraklasa" | ✅ WIRED | Verified |

**Domestic cup:**
- Polish Cup: `soccer_poland_puchar_polski` (TBC)

---

### 15. HNL (Croatian First League) — **HISTORY GAP**
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | — | — | ❌ **GAP** | football-data.co.uk does NOT cover Croatia. API-Football (paid) needed for T1 history |
| **Fixtures** | TheSportsDB (personal key) | `4629` | ✅ WIRED | Resolved 2026-08-08 |
| **Live Odds** | The Odds API | `soccer_croatia_hnl` | ⚠️ UNVERIFIED | Standard Odds API name but not probed at add time (no key in build env); probe `/v4/sports` with a live key before trusting |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | TheSportsDB | — | ✅ WIRED | |
| **Booking** | SportyBet | "Croatia" / "HNL" | ✅ WIRED | Verified |

**Domestic cup:**
- Croatian Cup: `soccer_croatia_croatian_cup` (TBC)

---

### 16. Austrian Bundesliga — **HISTORY GAP**
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | — | — | ❌ **GAP** | football-data.co.uk does NOT cover Austria. API-Football (paid) needed |
| **Fixtures** | TheSportsDB (personal key) | `4621` | ✅ WIRED | Resolved 2026-08-08 |
| **Live Odds** | The Odds API | `soccer_austria_bundesliga` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Understat Big-5 only |
| **Live Scores** | TheSportsDB | — | ✅ WIRED | |
| **Booking** | SportyBet | "Austria" / "Bundesliga" | ⚠️ PARTIAL | Needs live verification |

**Domestic cup:**
- ÖFB Cup: `soccer_austria_ofb_cup` (TBC)

---

### 17. EFL Cup — **HISTORY GAP**
| Data Type | Source | Code/Key | Status | Notes |
|-----------|--------|----------|--------|-------|
| **History** | — | — | ❌ **GAP** | football-data.co.uk has NO domestic cups. No free T1 source for cup history |
| **Fixtures** | Odds API (fixtures_from_odds) | `soccer_england_efl_cup` | ⚠️ PARTIAL | Only works when odds feed has ECL Cup fixtures; no standalone fixtures source |
| **Live Odds** | The Odds API | `soccer_england_efl_cup` | ✅ WIRED | |
| **xG** | — | — | ❌ **GAP** | Cup competition — xG not meaningful |
| **Live Scores** | — | — | ✅ WIRED | Via SportyBet cache |
| **Booking** | SportyBet | "England" / "EFL Cup" | ✅ WIRED | Verified |

---

## DOMESTIC CUP SPORT KEYS — PROBE STATUS

| Cup | League | Odds API Sport Key (to probe) | Status |
|-----|--------|-------------------------------|--------|
| FA Cup | Premier League | `soccer_england_fa_cup` | 🔧 Probe `/v4/sports` |
| EFL Cup | Premier League / Championship | `soccer_england_efl_cup` | ✅ Confirmed in SPORT_KEYS |
| Copa del Rey | La Liga | `soccer_spain_copa_del_rey` | 🔧 Probe `/v4/sports` |
| Coppa Italia | Serie A | `soccer_italy_coppa_italia` | 🔧 Probe `/v4/sports` |
| DFB-Pokal | Bundesliga | `soccer_germany_dfb_pokal` | 🔧 Probe `/v4/sports` |
| Coupe de France | Ligue 1 | `soccer_france_coupe_de_france` | 🔧 Probe `/v4/sports` |
| KNVB Beker | Eredivisie | `soccer_netherlands_knvb_beker` | 🔧 Probe `/v4/sports` |
| Scottish Cup | Scottish Premiership | `soccer_scotland_scottish_cup` | 🔧 Probe `/v4/sports` |
| Scottish League Cup | Scottish Premiership | `soccer_scotland_league_cup` | 🔧 Probe `/v4/sports` |
| Belgian Cup | Belgian Pro League | `soccer_belgium_belgian_cup` | 🔧 Probe `/v4/sports` |
| Taça de Portugal | Primeira Liga | `soccer_portugal_taca_de_portugal` | 🔧 Probe `/v4/sports` |
| Taça da Liga | Primeira Liga | `soccer_portugal_taca_da_liga` | 🔧 Probe `/v4/sports` |
| Danish Cup | Danish Superliga | `soccer_denmark_danish_cup` | 🔧 Probe `/v4/sports` |
| Polish Cup | Ekstraklasa | `soccer_poland_puchar_polski` | 🔧 Probe `/v4/sports` |
| Croatian Cup | HNL | `soccer_croatia_croatian_cup` | 🔧 Probe `/v4/sports` |
| ÖFB Cup | Austrian Bundesliga | `soccer_austria_ofb_cup` | 🔧 Probe `/v4/sports` |

---

## GAPS REQUIRING PAID / PERSONAL KEYS

| Gap | Leagues Affected | Solution | Cost/Action |
|-----|-----------------|----------|-------------|
| **No T1 history (football-data.co.uk)** | HNL, Austrian Bundesliga, EFL Cup | API-Football paid plan (current season history) | ~€150–200/mo for full coverage |
| **No xG beyond Big-5** | 12 of 17 leagues | FootyStats / fbref / FotMob API (paid) or custom scraper | €50–100/mo or dev time |
| **EFL Cup standalone fixtures** | EFL Cup | TheSportsDB eventsday (free key works) or API-Football | Free personal key or paid |
| **Second-division codes (promoted clubs)** | All 17 — promoted clubs enter with NO history | `SECOND_DIVISION_CODES` empty; needs API-Football history for 2. Bundesliga, Championship, etc. | API-Football paid |
| **Europa League odds sport key** | Europa League | Confirm `soccer_uefa_europa_league` active on Odds API | Probe `/v4/sports` |

---

## NEXT STEPS (Phase 3 — Data Sourcing)

1. **Probe Odds API `/v4/sports`** with live key → confirm all domestic cup sport keys above AND the unverified HNL league key `soccer_croatia_hnl` (mark ✅ or ❌; nothing stays WIRED without the probe)
2. **Verify Austrian Bundesliga SportyBet sidebar name** — live check
3. **Add confirmed cup keys to `pipeline/odds.py` SPORT_KEYS** — only keys returning `active=True`
4. **Document any cup keys that are INACTIVE** as permanent gaps
5. **Cost analysis** for API-Football paid plan to close HNL + Austrian history gaps
6. **Evaluate FootyStats/fbref** for xG beyond Understat's 5 leagues

---

## SOURCE CODE REFERENCES
- `data/football_data_source.py` — `LEAGUE_CODES`, `EXTRA_CODES`, `UNCOVERED_LEAGUES`
- `pipeline/odds.py` — `SPORT_KEYS`, `fixtures_from_odds`
- `data/xg_source.py` — `UNDERSTAT_SLUGS`
- `booking/league_map.py` — `SPORTYBET_LEAGUES`
- `data/thesportsdb_fixtures.py` — `LEAGUE_IDS` (personal key resolved)
- `data/multi_source_concrete.py` — failover chain for fixtures

---

**Next update:** After Odds API `/v4/sports` probe + UEFA 2026/27 access list (June 2026).