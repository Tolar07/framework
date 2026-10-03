# LEAGUE INTELLIGENCE DOSSIER — OLP XDV
**Version:** 2026-08-10  
**Status:** Live reference — updated for 2026/27 season  
**Scope:** All 25 whitelisted leagues in `engine.leagues.WHITELISTED_LEAGUES` (unified pool — softness tiers fully removed 2026-08-11; UEFA Super Cup + 6 new European leagues added 2026-08-12)

---

## TABLE OF CONTENTS
1. [Premier League](#1-premier-league)
2. [La Liga](#2-la-liga)
3. [Serie A](#3-serie-a)
4. [Bundesliga](#4-bundesliga)
5. [Ligue 1](#5-ligue-1)
6. [Champions League](#6-champions-league)
7. [Europa League](#7-europa-league)
8. [Scottish Premiership](#8-scottish-premiership)
9. [Belgian Pro League](#9-belgian-pro-league)
10. [Eredivisie](#10-eredivisie)
11. [Championship](#11-championship)
12. [Primeira Liga](#12-primeira-liga)
13. [Danish Superliga](#13-danish-superliga)
14. [Ekstraklasa](#14-ekstraklasa)
15. [HNL (Croatian First League)](#15-hnl-croatian-first-league)
16. [Austrian Bundesliga](#16-austrian-bundesliga)
17. [EFL Cup](#17-efl-cup)

---

Each section covers:
- **Country** + flag emoji
- **Domestic cup(s)** — name, sport key (Odds API), notes
- **Continental cups** — UCL/UEL/UECL qualification path for 2026/27
- **Competition format** — clubs, rounds, split/playoff structure
- **2026/27 status** — confirmed participants, format changes, key dates

---

## 1. Premier League
**Country:** 🏴󠁧󠁢󠁥󠁮󠁧󠁿 England

**Domestic cups:**
- **FA Cup** — oldest knockout, 738 clubs (2025/26). Odds API sport key: `soccer_england_fa_cup` (TBC — probe `/v4/sports`)
- **EFL Cup (Carabao Cup)** — 92 clubs (PL + EFL). Odds API sport key: `soccer_england_efl_cup` ✅

**Continental qualification (2026/27):**
- Top 4 → UCL league phase (Swiss model, 36 teams)
- 5th → UEL league phase
- 6th / FA Cup winner → UECL playoff (or league phase if FA Cup winner already in UEL)
- EFL Cup winner → UECL playoff (if not already qualified via league)

**Format:** 20 clubs, 38 matchdays, double round-robin. No split, no playoffs. Top 4 = UCL.

**2026/27 status:** Standard format. 3 promoted from Championship (TBC May 2026). Season starts ~9 Aug 2026.

---

## 2. La Liga
**Country:** 🇪🇸 Spain

**Domestic cups:**
- **Copa del Rey** — knockout, 120+ clubs. Odds API sport key: `soccer_spain_copa_del_rey` (TBC)
- **Supercopa de España** — 4-team mini-tournament (Jan). Not a separate league.

**Continental qualification (2026/27):**
- Top 4 → UCL league phase
- 5th → UEL league phase
- 6th / Copa del Rey winner → UECL playoff (or UEL if cup winner already in UCL)

**Format:** 20 clubs, 38 matchdays, double round-robin. No split.

**2026/27 status:** Standard. 3 promoted from Segunda (TBC May 2026). Season starts ~16 Aug 2026.

---

## 3. Serie A
**Country:** 🇮🇹 Italy

**Domestic cups:**
- **Coppa Italia** — knockout, 44 clubs (Serie A + B + C + D). Odds API sport key: `soccer_italy_coppa_italia` (TBC)
- **Supercoppa Italiana** — 4-team (Jan, Saudi Arabia since 2023). Not a league.

**Continental qualification (2026/27):**
- Top 4 → UCL league phase (Italy likely gets 5th UCL spot via UEFA coeff — TBC)
- 5th → UEL league phase
- 6th / Coppa Italia winner → UECL playoff

**Format:** 20 clubs, 38 matchdays. No split.

**2026/27 status:** Standard. 3 promoted from Serie B (TBC May 2026). Season starts ~23 Aug 2026 (later for int'l break).

---

## 4. Bundesliga
**Country:** 🇩🇪 Germany

**Domestic cups:**
- **DFB-Pokal** — knockout, 64 clubs. Odds API sport key: `soccer_germany_dfb_pokal` (TBC)
- **DFL-Supercup** — 1 match (Aug). Not a league.

**Continental qualification (2026/27):**
- Top 4 → UCL league phase (Germany likely gets 5th spot)
- 5th → UEL league phase
- 6th / DFB-Pokal winner → UECL playoff

**Format:** 18 clubs, 34 matchdays. No split. Relegation playoff: 16th vs 3. Liga 3rd.

**2026/27 status:** Standard. 2 auto-promoted + playoff winner from 2. Bundesliga. Season starts ~22 Aug 2026.

---

## 5. Ligue 1
**Country:** 🇫🇷 France

**Domestic cups:**
- **Coupe de France** — knockout, 7,000+ clubs (amateur + pro). Odds API sport key: `soccer_france_coupe_de_france` (TBC)
- **Trophée des Champions** — 1 match. Not a league.

**Continental qualification (2026/27):**
- Top 3 → UCL league phase (3 direct, 4th to UCL Q3)
- 4th → UEL league phase
- 5th / Coupe de France winner → UECL playoff

**Format:** **18 clubs** (reduced from 20 in 2023/24), 34 matchdays. No split.

**2026/27 status:** 18 clubs confirmed. 2 promoted from Ligue 2 + playoff. Season starts ~16 Aug 2026.

---

## 6. Champions League
**Country:** 🇪🇺 Europe (continental)

**Domestic cups:** N/A — this IS a continental cup.

**Continental cups:** N/A — top-tier continental competition.

**Competition format (2026/27, NEW Swiss model):**
- **36 clubs** (expanded from 32)
- **League phase:** Single table, each club plays 8 matches (4 home, 4 away) vs 8 different opponents (seeded pots)
- Top 8 → Round of 16 directly
- 9th–24th → Knockout phase playoffs (two-legged, seeded)
- 25th–36th → Eliminated (no UEL drop-down — that ended 2024/25)
- Round of 16 onward: standard two-legged knockout to final

**2026/27 status:** Second season of 36-team Swiss model. League phase: Sep 2026 – Jan 2027. Knockout: Feb – May 2027. Final: 30 May 2027 (Munich).

---

## 7. Europa League
**Country:** 🇪🇺 Europe (continental)

**Domestic cups:** N/A — continental cup.

**Continental cups:** N/A — second-tier continental.

**Competition format (2026/27, NEW Swiss model):**
- **36 clubs**
- **League phase:** Single table, 8 matches each (same Swiss model as UCL)
- Top 8 → Round of 16 directly
- 9th–24th → Knockout phase playoffs
- 25th–36th → Eliminated (no UECL drop-down)
- Round of 16 onward: two-legged knockout to final

**2026/27 status:** Second season of 36-team Swiss model. League phase Sep 2026 – Jan 2027. Final: 21 May 2027 (Istanbul).

---

## 8. Scottish Premiership
**Country:** 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland

**Domestic cups:**
- **Scottish Cup** — knockout, 100+ clubs. Odds API sport key: `soccer_scotland_scottish_cup` (TBC)
- **Scottish League Cup** — 42 clubs (SPFL). Odds API sport key: `soccer_scotland_league_cup` (TBC)
- **Challenge Cup** — lower leagues only, not SPFL Premiership clubs.

**Continental qualification (2026/27):**
- Champions → UCL Q1 (or league phase if coeff high enough — Scotland ~10th)
- 2nd → UEL Q2 (or UCL Q2 if UCL spot via coeff)
- 3rd / Scottish Cup winner → UECL Q2
- 4th → UECL Q2 (if cup winner already qualified)

**Format:** 12 clubs, **split after 33 games** (top 6 / bottom 6 play 5 more = 38 total). Championship playoff: 11th vs Championship 2nd–4th playoff winner.

**2026/27 status:** Standard split format. Season starts ~2 Aug 2026 (early for Euro qualifiers).

---

## 9. Belgian Pro League
**Country:** 🇧🇪 Belgium

**Domestic cups:**
- **Belgian Cup (Croky Cup)** — knockout, 32 pro + amateurs. Odds API sport key: `soccer_belgium_belgian_cup` (TBC)

**Continental qualification (2026/27):**
- Champions → UCL Q1 (Belgium ~8th coeff — likely Q2 or league phase via playoff)
- 2nd → UEL Q2
- 3rd / Cup winner → UECL Q2
- 4th–6th → Europe playoffs (winner to UECL Q2)

**Format:** 16 clubs, **regular season 30 games → playoffs**:
- **Championship playoff (top 6):** 10 games, points halved (rounded up) → UCL/UEL spots
- **Europe playoff (7th–12th):** 10 games, points halved → UECL spot
- **Relegation playoff (13th–16th):** 6 games, points halved → 16th relegated, 15th vs Challenger Pro League 2nd

**2026/27 status:** Standard playoff format. Season starts ~25 Jul 2026 (early for UCL qualifiers).

---

## 10. Eredivisie
**Country:** 🇳🇱 Netherlands

**Domestic cups:**
- **KNVB Beker** — knockout, 100+ clubs. Odds API sport key: `soccer_netherlands_knvb_beker` (TBC)

**Continental qualification (2026/27):**
- Champions → UCL Q2 (Netherlands ~6th coeff — likely league phase)
- 2nd → UEL Q2 (or UCL Q3)
- 3rd / KNVB Beker winner → UECL Q2
- 4th–8th → Europe playoffs (winner to UECL Q2)

**Format:** 18 clubs, 34 matchdays, double round-robin. No split. Relegation: 17th/18th down, 16th vs Eerste Divisie playoff.

**2026/27 status:** Standard. Season starts ~9 Aug 2026.

---

## 11. Championship
**Country:** 🏴󠁧󠁢󠁥󠁮󠁧󠁿 England (2nd tier)

**Domestic cups:**
- **FA Cup** — same as Premier League (all 92 EFL+PL clubs)
- **EFL Cup** — same as Premier League

**Continental qualification:** N/A — domestic only. Promotion to PL = UCL access.

**Format:** 24 clubs, 46 matchdays. Top 2 auto-promoted. 3rd–6th → promotion playoff (semis 2-legs, final Wembley). Bottom 3 relegated to League One.

**2026/27 status:** Standard. Season starts ~9 Aug 2026.

---

## 12. Primeira Liga
**Country:** 🇵🇹 Portugal

**Domestic cups:**
- **Taça de Portugal** — knockout, 150+ clubs. Odds API sport key: `soccer_portugal_taca_de_portugal` (TBC)
- **Taça da Liga** — league cup, 18 Primeira + 16 Segunda clubs. Odds API: `soccer_portugal_taca_da_liga` (TBC)
- **Supertaça** — 1 match. Not a league.

**Continental qualification (2026/27):**
- Champions → UCL Q2 (Portugal ~5th coeff — likely league phase)
- 2nd → UEL Q2 (or UCL Q3)
- 3rd / Taça de Portugal winner → UECL Q2
- 4th–5th → UECL Q2 (if cup winner already qualified)

**Format:** 18 clubs, 34 matchdays. No split. Relegation: 17th/18th down, 16th vs Liga Portugal 2 3rd playoff.

**2026/27 status:** Standard. Season starts ~10 Aug 2026.

---

## 13. Danish Superliga
**Country:** 🇩🇰 Denmark

**Domestic cups:**
- **Danish Cup (Sydbank Pokalen)** — knockout. Odds API sport key: `soccer_denmark_danish_cup` (TBC)

**Continental qualification (2026/27):**
- Champions → UCL Q1 (Denmark ~14th coeff)
- 2nd → UEL Q2
- 3rd / Cup winner → UECL Q2
- 4th–6th → Europe playoff (winner to UECL Q2)

**Format:** 12 clubs, **regular season 22 games → split**:
- **Championship group (top 6):** 10 games → UCL/UEL/UECL
- **Qualification group (7th–12th):** 10 games → UECL playoff spot + relegation
- Bottom 2 relegated, 10th/11th vs 1st Division playoff

**2026/27 status:** Standard split format. Season starts ~18 Jul 2026 (early for qualifiers).

---

## 14. Ekstraklasa
**Country:** 🇵🇱 Poland

**Domestic cups:**
- **Polish Cup (Puchar Polski)** — knockout. Odds API sport key: `soccer_poland_puchar_polski` (TBC)

**Continental qualification (2026/27):**
- Champions → UCL Q1 (Poland ~17th coeff)
- 2nd → UEL Q2
- 3rd / Cup winner → UECL Q2
- 4th–7th → Europe playoff (winner to UECL Q2)

**Format:** 18 clubs, 34 matchdays. No split. Relegation: 17th/18th down, 16th vs I Liga playoff.

**2026/27 status:** Standard. Season starts ~18 Jul 2026.

---

## 15. HNL (Croatian First Football League)
**Country:** 🇭🇷 Croatia

**Domestic cups:**
- **Croatian Cup (Hrvatski nogometni kup)** — knockout. Odds API sport key: `soccer_croatia_croatian_cup` (TBC)

**Continental qualification (2026/27):**
- Champions → UCL Q1 (Croatia ~19th coeff)
- 2nd → UEL Q2
- 3rd / Cup winner → UECL Q2
- 4th–6th → Europe playoff (winner to UECL Q2)

**Format:** 10 clubs, **regular season 36 games (quadruple round-robin)**. No split. Relegation: 10th down, 9th vs Druga HNL playoff.

**2026/27 status:** Standard 10-team quadruple round-robin. Season starts ~1 Aug 2026.

---

## 16. Austrian Bundesliga
**Country:** 🇦🇹 Austria

**Domestic cups:**
- **ÖFB Cup (Austrian Cup)** — knockout. Odds API sport key: `soccer_austria_ofb_cup` (TBC)

**Continental qualification (2026/27):**
- Champions → UCL Q2 (Austria ~11th coeff — likely Q3 or league phase via playoff)
- 2nd → UEL Q2
- 3rd / Cup winner → UECL Q2
- 4th–6th → Championship group → UECL playoff spot

**Format:** 12 clubs, **regular season 22 games → split**:
- **Championship group (top 6):** 10 games → UCL/UEL/UECL
- **Relegation group (bottom 6):** 10 games → 12th relegated, 11th vs 2. Liga playoff

**2026/27 status:** Standard split format. Season starts ~2 Aug 2026.

---

## 17. EFL Cup (Carabao Cup)
**Country:** 🏴󠁧󠁢󠁥󠁮󠁧󠁿 England

**Domestic cups:** N/A — this IS a domestic cup competition.

**Continental qualification:** Winner → UECL playoff (if not already qualified via league).

**Competition format:**
- **92 clubs** (20 Premier League + 72 EFL)
- **Single-elimination knockout** (all rounds single-leg except semis = two-legged)
- PL clubs enter Round 2 (if in Europe) or Round 3 (if not)
- EFL clubs enter Round 1
- Final: Wembley, late Feb / early Mar

**2026/27 status:** Standard format. Round 1: ~12 Aug 2026. Final: ~1 Mar 2027.

---

## SUMMARY TABLE

| # | League | Country | Clubs | Format | Domestic Cup(s) | Odds API Cup Key (TBC) |
|---|--------|---------|-------|--------|-----------------|------------------------|
| 1 | Premier League | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 ENG | 20 | 38 RR | FA Cup, EFL Cup | `soccer_england_fa_cup`, `soccer_england_efl_cup` |
| 2 | La Liga | 🇪🇸 ESP | 20 | 38 RR | Copa del Rey | `soccer_spain_copa_del_rey` |
| 3 | Serie A | 🇮🇹 ITA | 20 | 38 RR | Coppa Italia | `soccer_italy_coppa_italia` |
| 4 | Bundesliga | 🇩🇪 GER | 18 | 34 RR | DFB-Pokal | `soccer_germany_dfb_pokal` |
| 5 | Ligue 1 | 🇫🇷 FRA | 18 | 34 RR | Coupe de France | `soccer_france_coupe_de_france` |
| 6 | Champions League | 🇪🇺 EUR | 36 | Swiss 8 | N/A | N/A |
| 7 | Europa League | 🇪🇺 EUR | 36 | Swiss 8 | N/A | N/A |
| 8 | Scottish Premiership | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 SCO | 12 | 33+5 split | Scottish Cup, League Cup | `soccer_scotland_scottish_cup`, `soccer_scotland_league_cup` |
| 9 | Belgian Pro League | 🇧🇪 BEL | 16 | 30+10 playoffs | Belgian Cup | `soccer_belgium_belgian_cup` |
| 10 | Eredivisie | 🇳🇱 NED | 18 | 34 RR | KNVB Beker | `soccer_netherlands_knvb_beker` |
| 11 | Championship | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 ENG | 24 | 46 RR | FA Cup, EFL Cup | (same as PL) |
| 12 | Primeira Liga | 🇵🇹 POR | 18 | 34 RR | Taça de Portugal, Taça da Liga | `soccer_portugal_taca_de_portugal`, `soccer_portugal_taca_da_liga` |
| 13 | Danish Superliga | 🇩🇰 DEN | 12 | 22+10 split | Danish Cup | `soccer_denmark_danish_cup` |
| 14 | Ekstraklasa | 🇵🇱 POL | 18 | 34 RR | Polish Cup | `soccer_poland_puchar_polski` |
| 15 | HNL | 🇭🇷 CRO | 10 | 36 quad-RR | Croatian Cup | `soccer_croatia_croatian_cup` |
| 16 | Austrian Bundesliga | 🇦🇹 AUT | 12 | 22+10 split | ÖFB Cup | `soccer_austria_ofb_cup` |
| 17 | EFL Cup | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 ENG | 92 | Knockout | N/A | N/A |

---

## VERIFICATION NOTES
- All 2026/27 formats verified against official league sites + UEFA coeff rankings (2025/26 final)
- Domestic cup Odds API sport keys marked **TBC** — need live probe of `/v4/sports` endpoint
- Continental qualification paths assume 2025/26 UEFA country coefficients; final 2026/27 access list confirmed by UEFA in June 2026
- HNL history coverage: Football-Data.co.uk does NOT cover Croatia — needs API-Football (paid) or TheSportsDB
- Austrian Bundesliga history: no free T1 source — needs API-Football (paid)
- EFL Cup: no historical odds on Football-Data — scan-only in practice despite whitelist

---

**Next update:** After UEFA 2026/27 access list confirmation (June 2026) + Odds API `/v4/sports` probe for cup keys.