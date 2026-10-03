# OLP XDV — Sortable API / Data-Source Inventory
*Generated 2026-08-12 from live codebase audit. Every source confirmed by reading the module.*

---

## 1. Fixtures (Upcoming Match Schedule)

| Data Need | Source | Endpoint / Method | Key Required | Cost | League Coverage | Status | Notes / Recommendation |
|---|---|---|---|---|---|---|---|
| Primary fixtures | **TheSportsDB** | `eventsseason.php?id={league_id}&s={season}` | `THESPORTSDB_KEY` (free tier) | Free (shared key rate-limited; personal key 5558126822 in `.env`) | All 20 whitelisted + Champions/Europa/Conference/UEFA Super Cup | ✅ OK — but **season feed lags weeks** for UCL/EL qualifiers (July-only events visible in Aug) |
| Fallback 1 | **ESPN** (keyless) | `site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates=YYYYMMDD` | **None** | Free (unlimited) | All 20 whitelisted + UCL/UEL + AUT/HNL (slugs verified live 2026-08-07) | ✅ OK — T2 single-source, day-by-day fetch, reliable |
| Fallback 2 | **API-Football** | `/fixtures?league={id}&season={year}&from={date}&to={date}` | `API_FOOTBALL_KEY` | Free: 100 req/day | All whitelisted (IDs resolved live via `/leagues`) | ✅ OK — free plan **only today±1 window**; paid plan widens window |
| Fallback 3 | **The Odds API** (derived) | `/v4/sports/{sport_key}/odds?regions=uk&markets=h2h` | `ODDS_API_KEY` (paid) | Paid: 500 credits/mo | 15 leagues (SPORT_KEYS in pipeline/odds.py) | ✅ OK — fixture list is a by-product of odds pull; 6h cached |
| Placement-only | **SportyBet** (scraped) | `sportybet.com/ng/sport/football/{country}/{league}` | **None** (HTML scrape) | Free | Nigeria-bookable leagues only (subset of whitelist) | ✅ OK — used for CLV + actual placement verification |

**Gap**: No single source covers **all continental qualifiers in real time** — TheSportsDB lags, ESPN covers UCL/UEL but not Conference/early rounds reliably.

---

## 2. Results (Historical Played Matches — for Dixon-Coles Fit)

| Data Need | Source | Endpoint / Method | Key Required | Cost | League Coverage | Status | Notes / Recommendation |
|---|---|---|---|---|---|---|---|
| **Primary fit pool** | **football-data.co.uk** | Static CSVs (`/mmz4281/{season}/{league}.csv`) | **None** | Free | 11 EU leagues: E0, E1, E2, E3, SC0, D1, I1, SP1, F1, N1, P1, B1, T1 | ✅ OK — **primary fit source**, clean, 20+ seasons history |
| Continental / extras | **TheSportsDB** (played) | `eventsseason.php` (filter played) | `THESPORTSDB_KEY` | Free | HNL, UCL, EL, Conference, Austrian BL, others | ✅ OK — T2 reference, same single-source as fixtures |
| **Current-season results** | **API-Football** | `/fixtures?league={id}&season={year}&status=FT` | `API_FOOTBALL_KEY` | **Paid plan required** | All whitelisted + more | ❌ **BLOCKED** — key still resolves to "Free" on their side; free plan only serves seasons 2022-2024 |

**Gap**: Current-season results for **promoted clubs** (Cambuur, Beveren, Lommel, Horsens, Como, Parma, etc.) and any team with no 2022-24 top-flight history are **missing from the fit pool**. The DC model has zero data for them.

---

## 3. Live Odds / Prices (1X2, O/U 1.5, O/U 2.5, BTTS, Double Chance)

| Data Need | Source | Endpoint / Method | Key Required | Cost | Markets | Status | Notes / Recommendation |
|---|---|---|---|---|---|---|---|
| **Primary** | **The Odds API** (paid) | `/v4/sports/{sport_key}/odds?regions=uk,eu&markets=h2h,totals` | `ODDS_API_KEY` (paid, in `.env`) | Paid: 500 credits/mo (1 credit = 1 region × 1 market) | 1X2, O/U 2.5 (free tier); **O/U 1.5, BTTS, DC = paid only** | ✅ PRIMARY — but quota burns fast (~600/mo for full whitelist) |
| **Fallback** | **API-Football** (free) | `/odds?fixture={id}` | `API_FOOTBALL_KEY` | Free: 100 req/day | 1X2, O/U 2.5 only (free tier) | ✅ OK — serves same books (Bet365, Pinnacle, WH) but **no O/U 1.5, BTTS, DC** on free |
| **Placement / CLV** | **SportyBet** (scraped) | Fixture detail page HTML | **None** | Free | 1X2 only (NG) | ✅ OK — actual placement prices for paper-leg CLV |

**Gap**: **Multi-market odds (O/U 1.5, BTTS, DC) on sustainable quota**. Free tiers don't serve them. Paid Odds API 500/mo is tight for daily full-whitelist multi-market. API-Football paid plan serves them but key not yet active.

---

## 4. Team Strength Ratings (Elo / Attack-Defence for Fallback)

| Data Need | Source | Endpoint / Method | Key Required | Cost | Coverage | Status | Notes / Recommendation |
|---|---|---|---|---|---|---|---|
| **Primary (fitted)** | **football-data.co.uk → DC** | Static CSVs → Dixon-Coles fit | **None** | Free | 11 leagues (anchor leagues) | ✅ PRIMARY — but **only for clubs with ≥4 matches in fit window** |
| **Stretch fallback** | **ClubElo** (keyless) | `http://api.clubelo.com/{date}` (CSV) | **None** | Free | 594 clubs (all Europe + some Asia/SA) | ✅ OK — **drops provisional placeholders** (promoted clubs parked at shared Elo) → honest NO DATA |
| **Current-season fit** | **API-Football** | `/teams/statistics?league={id}&season={year}&team={id}` | `API_FOOTBALL_KEY` | **Paid plan required** | All current-season clubs | ❌ **BLOCKED** — same Free key; free plan only serves 2022-2024 seasons |

**Gap**: **Zero-history clubs (promoted, new to division)** cannot be rated by DC (needs ≥4 matches) and ClubElo drops them as shared placeholders. The only path to rate them *today* is API-Football paid current-season fit — which is blocked.

---

## 5. Bookmaker Placement Prices (SportyBet Nigeria)

| Data Need | Source | Endpoint / Method | Key Required | Cost | Coverage | Status | Notes |
|---|---|---|---|---|---|---|---|
| Placement / CLV | **SportyBet** (scraped) | `sportybet.com/ng` — requests + BS4 + Playwright cache builder | **None** | Free | Nigeria-bookable leagues | ✅ OK — 24h TTL cache; Playwright builder for SPA click-through verified |

**No gap** — this is complete for the deployment target.

---

## 6. Prediction-Market Cross-Check (Second Opinion)

| Data Need | Source | Endpoint / Method | Key Required | Cost | Coverage | Status | Notes |
|---|---|---|---|---|---|---|---|
| Polymarket odds | **sports-skills** (`sports-polymarket`) | Read-only order books via CLOB | **None** | Free | EPL, UCL, LaLiga, Serie A, Bundesliga, Ligue 1 | ✅ OK — genuine second opinion on moneyline |
| Kalshi odds | **sports-skills** (`sports-markets`) | Kalshi REST API | **None** | Free | EPL, UCL | ✅ OK — smaller markets, lower liquidity |

**No gap** — this is a verification input, not a gate.

---

## Recommended Changes (Priority Order)

### P0 — Unblock current-season ratings for promoted/new clubs (WITHOUT waiting for api-football paid activation)

| Option | What it gives | Cost | Implementation effort | Verdict |
|---|---|---|---|---|
| **1. football-data.org API** (free tier) | Current-season results/standings for 100+ competitions; 10 req/min, 100/day | Free (register) | Low — add `data/football_data_org_source.py` mirroring `fixtures_source.py` pattern | ✅ **Best immediate fix** — keyless-ish, covers promoted clubs once they play |
| **2. Sportmonks free plan** | Livescore + fixtures + standings; 2000 req/day on free | Free (register) | Medium — new provider, need team mapping | Viable backup |
| **3. SofaScore public API** (unofficial) | Fixtures, results, stats, lineups; no key | Free (scrape) | Medium — reverse-engineered, may break | Risky long-term |
| **4. RapidAPI: API-Football mirror** | Same data as api-football but different key/quota | Freemium | Low — same response shape | If api-football paid doesn't activate |

**Recommended**: Add **football-data.org** as a *results-only* source for current season. It serves promoted clubs' matches as they happen (no history needed — just current results). Wire it into `orchestrator.py` as a *fourth* results fallback (after football-data.co.uk CSV, TheSportsDB played, API-Football current season). This solves the promoted-club rating gap **today**, independent of api-football's activation lag.

### P1 — Sustainable multi-market odds quota

| Option | What it gives | Cost | Verdict |
|---|---|---|---|
| **The Odds API paid plan upgrade** | 500 → 2000 or 10000 credits/mo; adds O/U 1.5, BTTS, DC | $20–$100/mo | If budget allows — simplest, already integrated |
| **API-Football paid plan (Standard/Pro)** | 100 → 1000 req/day; full market set (O/U 1.5, BTTS, DC, Asian lines) | $10–$20/mo | **Best value** — same key, wider window, multi-market, already coded with plan gate |
| **Pinnacle API (via broker)** | Sharpest lines, full markets | Requires account + volume | Overkill for Phase 2 |

**Recommended**: **API-Football paid plan** is the correct architectural fit — the code is already plan-gated (`api_football_plan.is_paid_plan()`), the free fallback is in place, and it serves *all* markets the framework needs. Once the key activates on their side (check dashboard), everything flips automatically. If activation takes >48h, open a support ticket with api-football (payment confirmed, account email: omotolar12@gmail.com).

### P2 — Continental qualifiers real-time fixtures

| Option | What it gives | Cost | Verdict |
|---|---|---|---|
| **UEFA official API** (if accessible) | Authoritative UCL/UEL/UECL fixtures + results | Unknown / likely restricted | Investigate |
| **SofaScore / FlashScore scrape** | Real-time all continental rounds | Free (fragile) | Only if ESPN + TheSportsDB leave gaps |
| **Sportmonks / football-data.org** | Continental fixtures in their coverage | Free tier | Add as 5th fixture fallback |

**Recommended**: Monitor the ESPN + TheSportsDB combo for 2026-08-13/14 UCL/UEL qualifier rounds. If gaps persist, add football-data.org fixtures as 5th fallback.

---

## Quick-Start: Add football-data.org (P0 fix)

1. **Register free** at [football-data.org](https://www.football-data.org/client/register) → get API token.
2. **Add to `.env`**: `FOOTBALL_DATA_ORG_KEY=<token>`
3. **Create** `data/football_data_org_source.py` — mirrors `fixtures_source.py` pattern:
   - `fetch_current_season_results(league, season)` → returns `MatchResult` list
   - `fetch_standings(league, season)` → for promoted-club context
   - 10 req/min, 100/day quota → cache 6h like other sources
4. **Wire** into `orchestrator.py` results fallback chain (after TheSportsDB played, before giving up).
5. **Test**: Run on a league with promoted clubs (Eredivisie → Cambuur, Willem II, ADO Den Haag) — confirm results flow into the fit.

This unblocks the promoted-club rating gap **today**, without waiting for api-football.