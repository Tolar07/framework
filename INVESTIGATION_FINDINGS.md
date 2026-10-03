# OLP XVD Pipeline Investigation Findings

## Issue Summary
The OLP XDV pipeline was producing truncated Telegram output (only header) due to:
1. Dry-run mode using incorrect league name "English Premier League" (not in whitelist)
2. Missing ESPN SLUGS mappings for three cup competitions

## Root Cause Analysis

### 1. League Name Mismatch in Dry-Run Fixtures
**File**: `olp_xdv_pipeline.py:174`
- **Problem**: Hardcoded `"English Premier League"` in dry-run fixtures
- **Reality**: Whitelist/registry contains `"Premier League"` (from config/leagues.json)
- **Impact**: When dry-run tries to process this league, it fails silently and produces no fixtures

### 2. Missing ESPN SLUGS Mappings
**File**: `data/espn_source.py`
**Missing mappings**:
- `"Copa del Rey"` → should map to `"copa_del_rey"`
- `"Coppa Italia"` → should map to `"coppa_italia"`  
- `"Coupe de France"` → should map to `"coupe_de_france"`

**Current behavior**: ESPN source raises `SourceNoData` for these leagues, triggering HR35

## Data Availability Verification

### API-Football (Paid Plan Active)
✅ **Coppa Italia** (ID 137): Has fixtures for 2026-09-01 to 2026-09-03
- Parma vs Cremonese on 2026-09-01
- Torino vs Monza on 2026-09-01  
- Sassuolo vs Frosinone on 2026-09-02
- Udinese vs Venezia on 2026-09-02
- Palermo vs Mantova on 2026-09-03
- Cagliari vs Hellas Verona on 2026-09-03

### ESPN API (Direct Tests)
✅ All three competitions return data when queried with correct slugs and dates:
- **Copa del Rey**: Atl�tico Madrid vs Real Sociedad on 2026-04-18
- **Coppa Italia**: Parma vs Cremonese and Torino vs Monza on 2026-09-01
- **Coupe de France**: Lens vs Nice on 2026-05-22

## Current ESPN SLUGS (Incomplete)
```python
SLUGS = {
    "Champions League": "uefa-champions-league",
    "Europa League": "uefa-europa-league", 
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    # ... missing the three cup competitions
}
```

## WHITELISTED_LEAGUES Source
- Comes from `config/leagues.json` (dynamic registry)
- Correctly lists `"Premier League"` (not "English Premier League")
- Contains 29 leagues including all three cup competitions:
  - Copa del Rey
  - Coppa Italia  
  - Coupe de France
  - DFB-Pokal
  - FA Cup
  - EFL Cup (as "League Cup")

## HR35 Compliance
The system correctly followed HR35 (Honest Gap Rule):
- When data sources fail, it reports "NO DATA — PENDING" rather than guessing
- This is the correct behavior per the framework's honest-edge principle

## Recommended Fixes

### 1. Fix Dry-Run League Name
**File**: `olp_xdv_pipeline.py:174`
```diff
-            {"match_id": "FX-26001", "sport": "football", "league": "English Premier League",
+            {"match_id": "FX-26001", "sport": "football", "league": "Premier League",
```

### 2. Add Missing ESPN SLUGS
**File**: `data/espn_source.py` (around line 65)
```python
SLUGS = {
    "Champions League": "uefa-champions-league",
    "Europa League": "uefa-europa-league", 
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    # Add missing cup competitions:
    "Copa del Rey": "copa_del_rey",
    "Coppa Italia": "coppa_italia", 
    "Coupe de France": "coupe_de_france",
    # ... rest of existing mappings
}
```

## Expected Outcome After Fixes
1. Dry-run mode will properly process "Premier League" fixtures
2. ESPN source will successfully fetch data for the three cup competitions
3. Pipeline will generate complete fixture data instead of triggering HR35
4. Telegram output will show actual match listings rather than just header

## Verification Steps
1. Run: `TELEGRAM_BOARD_DELIVERY_ENABLED=1 python olp_xdv_pipeline.py --dry-run`
2. Check `telegram_YYYY-MM-DD.txt` for complete fixture listings
3. Verify ESPN source works for target competitions
4. Confirm no more "NO DATA — PENDING" messages for these leagues