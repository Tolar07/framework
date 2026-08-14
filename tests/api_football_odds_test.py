"""API-Football free-plan odds fallback tests. No network.

Proves the three things this module must hold (HR35 throughout):
  1. The /odds payload (bookmakers only, NO team names) parses into the
     FixtureOdds contract when joined with the /fixtures metadata — 1X2 and
     O/U2.5 prices land on the right sides.
  2. Team names that don't resolve pass through UNCHANGED (caller sees
     NO DATA — PENDING, never a guessed match).
  3. pipeline.odds.fetch_odds falls back to this module when the Odds API
     monthly quota is exhausted — the PRICE pull path, not fixture capture.
"""
import sys
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import api_football_odds as af
import engine.leagues as leagues
import engine.markets as mkt
import pipeline.odds as odds
from pipeline.odds import MarketQuote, FixtureOdds


# --- a realistic /odds?fixture= payload (bookmakers only, no teams) ---------
ODDS_PAYLOAD = {
    "get": "odds",
    "response": [{
        "fixture": {"id": 1552118, "date": "2026-08-08T14:30:00+00:00"},
        "league": {"id": 88, "name": "Eredivisie"},
        "update": "2026-08-08T05:54:18+00:00",
        "bookmakers": [
            {"name": "10Bet", "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.50"},
                    {"value": "Draw", "odd": "4.75"},
                    {"value": "Away", "odd": "5.80"}]},
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 2.5", "odd": "1.44"},
                    {"value": "Under 2.5", "odd": "2.75"}]}]},
            {"name": "Bet365", "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.46"},
                    {"value": "Draw", "odd": "4.70"},
                    {"value": "Away", "odd": "5.80"}]},
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 2.5", "odd": "1.45"},
                    {"value": "Under 2.5", "odd": "2.70"}]}]},
            {"name": "Pinnacle", "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.48"},
                    {"value": "Draw", "odd": "4.91"},
                    {"value": "Away", "odd": "6.01"}]},
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 2.5", "odd": "1.44"},
                    {"value": "Under 2.5", "odd": "2.84"}]}]},
        ],
    }],
}

# /fixtures metadata for that fixture (this is where team names actually live)
FIXTURE_META = {
    "home": "NEC Nijmegen",   # maps to model key 'Nijmegen' via odds.TEAM_ALIASES
    "away": "Telstar",        # maps to 'Telstar'
    "date": "2026-08-08T14:30:00+00:00",
}


# --- 1. payload + metadata parse into the FixtureOdds contract ---------------
fx = af._parse_odds_payload("Eredivisie", ODDS_PAYLOAD, FIXTURE_META)
assert isinstance(fx, FixtureOdds), "must return the shared FixtureOdds contract"
assert fx.home_team == "Nijmegen", f"alias not applied: {fx.home_team}"
assert fx.away_team == "Telstar", f"alias not applied: {fx.away_team}"
assert fx.kickoff_utc == "2026-08-08T14:30:00+00:00"
# Bet365 is the priority book — the price must be BET365's, not Pinnacle's
assert fx.home.price == 1.46, f"expected Bet365 1.46, got {fx.home.price}"
assert fx.draw.price == 4.70
assert fx.away.price == 5.80
# Over/Under 2.5 — Bet365 is also priority here
assert fx.over25.price == 1.45, f"expected Bet365 1.45, got {fx.over25.price}"
assert fx.under25.price == 2.70
assert fx.source == "api-football.com (free plan)"
assert fx.source_tier == "T1"
print("1. /odds payload + /fixtures metadata -> FixtureOdds, Bet365-priority: OK")

# --- 2. unknown team names pass through UNCHANGED (HR35) ----------------------
meta_unknown = {"home": "No Such Club FC", "away": "Telstar",
                "date": "2026-08-08T14:30:00+00:00"}
fx2 = af._parse_odds_payload("Eredivisie", ODDS_PAYLOAD, meta_unknown)
assert fx2.home_team == "No Such Club FC", "unmapped team must pass through"
assert fx2.away_team == "Telstar"
print("2. unmapped team name passes through unchanged (HR35): OK")

# --- 3. degenerate / non-numeric prices never count ---------------------------
_bad_payload = {
    "get": "odds",
    "response": [{
        "fixture": {"id": 1, "date": "2026-08-08T14:30:00+00:00"},
        "league": {"id": 88, "name": "Eredivisie"},
        "bookmakers": [{
            "name": "Bet365", "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.00"},   # degenerate
                    {"value": "Draw", "odd": "oops"},   # non-numeric
                    {"value": "Away", "odd": "3.10"}]},
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 2.5", "odd": "1.50"},
                    {"value": "Under 2.5", "odd": "2.60"}]}]}],
    }],
}
fx3 = af._parse_odds_payload("Eredivisie", _bad_payload, FIXTURE_META)
assert not fx3.home.available, "degenerate price must not count"
assert not fx3.draw.available, "non-numeric price must not count"
assert fx3.away.price == 3.10, "valid side must still price"
assert not any("1X2 not quoted" in n for n in fx3.notes), (
    "partial 1X2 (away priced) must NOT be reported as fully unquoted")
print("3. degenerate/non-numeric prices rejected, valid side still priced: OK")

# --- 3b. whole 1X2 unquoted -> flagged ---------------------------------------
_whole_missing = {
    "get": "odds",
    "response": [{
        "fixture": {"id": 1, "date": "2026-08-08T14:30:00+00:00"},
        "league": {"id": 88, "name": "Eredivisie"},
        "bookmakers": [{
            "name": "Bet365", "bets": [
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 2.5", "odd": "1.50"},
                    {"value": "Under 2.5", "odd": "2.60"}]}]}],
    }],
}
fx3b = af._parse_odds_payload("Eredivisie", _whole_missing, FIXTURE_META)
assert not fx3b.home.available and not fx3b.draw.available \
    and not fx3b.away.available
assert any("1X2 not quoted" in n for n in fx3b.notes), "whole-1X2 must flag"
print("3b. whole 1X2 unquoted -> flagged: OK")

# --- 4. missing odds for a fixture is not an error ---------------------------
_no_odds = {"get": "odds", "response": []}
try:
    fx4 = af._parse_odds_payload("Eredivisie", _no_odds, FIXTURE_META)
    assert fx4.home.price is None and fx4.away.price is None
    print("4. empty odds response -> all NO DATA, no crash: OK")
except Exception as e:
    raise AssertionError(f"empty odds response should parse to NO DATA: {e}")

# --- 5. pipeline.odds falls back when the Odds API quota is exhausted --------
# Simulate: Odds API reports 4 remaining (below the 40 floor), so fetch_odds
# must route through api_football_odds instead of raising.
_priced = [FixtureOdds(
    league="Eredivisie", home_team="Nijmegen", away_team="Telstar",
    kickoff_utc="2026-08-08T14:30:00+00:00",
    home=MarketQuote(price=1.46, bookmaker="Bet365"),
    draw=MarketQuote(price=4.70, bookmaker="Bet365"),
    away=MarketQuote(price=5.80, bookmaker="Bet365"),
    over25=MarketQuote(price=1.45, bookmaker="Bet365"),
    under25=MarketQuote(price=2.70, bookmaker="Bet365"),
    source="api-football.com (free plan)")]
with mock.patch.object(odds, "_resolve_key", side_effect=odds.QuotaExhausted("quota spent")), \
     mock.patch.object(odds, "_read_cache", return_value=None), \
     mock.patch.object(af, "fetch_odds", return_value=(_priced, ["af served"])):
    fixtures, flags = odds.fetch_odds("Eredivisie", use_cache=False)
assert len(fixtures) == 1, f"expected 1 fallback fixture, got {len(fixtures)}"
assert fixtures[0].home_team == "Nijmegen"
assert fixtures[0].home.price == 1.46
assert any("api-football free fallback" in f for f in flags), (
    f"fallback must be visible in flags: {flags}")
print("5. Odds API quota exhausted -> transparent api-football fallback: OK")

# --- 6. fallback does NOT trigger on fixture capture --------------------------
with mock.patch.object(odds, "_resolve_key", side_effect=odds.QuotaExhausted("quota spent")), \
     mock.patch.object(odds, "_read_cache", return_value=None), \
     mock.patch.object(af, "check_quota", return_value=(51, 49)):
    try:
        odds.fetch_odds("Eredivisie", use_cache=False, fixture_capture=True)
        raise AssertionError("fixture capture must NOT fall back to prices")
    except odds.QuotaExhausted:
        pass  # expected — fixture capture keeps its cache discipline
print("6. fixture capture does NOT fall back to the price feed: OK")

# --- 7. fallback serves EVERY whitelisted league (unified pool, ID401) --------
# When the Odds API quota is spent, this module is the only full multi-market
# price source (the free tier does not serve O/U1.5, BTTS or Double Chance). A
# league the fallback refuses therefore prices 1X2-only and its acca legs can
# never diversify — so the gate must be open for the WHOLE whitelist, not a
# hardcoded 5-league deploy set (multi-market selection, Architect 2026-08-11).
_missing = sorted(set(leagues.WHITELISTED_LEAGUES) - set(af.DEPLOY_LEAGUES))
assert not _missing, f"fallback gate excludes whitelisted leagues: {_missing}"
print(f"7. fallback gate covers all {len(leagues.WHITELISTED_LEAGUES)} "
      f"whitelisted leagues (unified pool): OK")

# --- 7b. off-whitelist leagues are still refused (HR34) -----------------------
with mock.patch.object(af, "check_quota", return_value=(51, 49)):
    try:
        af.fetch_odds("Fake League XYZ", days_ahead=0)
        raise AssertionError("off-whitelist league must not get the fallback")
    except af.SourceNoData:
        pass
print("7b. off-whitelist league refused by the fallback (HR34): OK")

# --- 8. market constants the pricing path touches actually exist -------------
# The fallback is the FIRST source to make odds present after weeks of quota
# exhaustion — and pricing fixtures exposed two latent AttributeErrors that
# were masked while no odds ever reached the EV loop (MARKETS_1X2 and
# OVER_2_5/UNDER_2_5). Guard them so that path can never rot silently again.
import engine.markets as mkt
for const in ("MARKETS_1X2", "OVER_25", "UNDER_25", "OVER_15", "UNDER_15",
              "HOME", "DRAW", "AWAY"):
    assert hasattr(mkt, const), f"engine.markets.{const} missing"
# MARKETS_1X2 must index into implied_1x2's (home, draw, away) tuple order
assert mkt.MARKETS_1X2 == {mkt.HOME: 0, mkt.DRAW: 1, mkt.AWAY: 2}
# run_daily and webapp use these exact attribute paths — import must resolve
import run_daily  # noqa: F401  (import-time constant access)
import webapp.produce  # noqa: F401
print("8. market constants for the odds path all resolve (no latent AttrError): OK")

# --- 8b. full multi-market parse — REAL api-football value names --------------
# The multi-market selection (2026-08-11) needs a real price on every market a
# fixture is scored on (1X2, O/U1.5, O/U2.5, BTTS, DC), or the acca leg is stuck
# on 1X2 and can never diversify. api-football names Double Chance outcomes
# "Home/Draw"/"Draw/Away"/"Home/Away" (NOT our canonical 1X/X2/12) — this used
# to silently return None for all three DC markets on every fixture. The value
# names below are copied from the LIVE /odds payload (verified 2026-08-11).
_FULL_PAYLOAD = {
    "get": "odds",
    "response": [{
        "fixture": {"id": 1552118, "date": "2026-08-08T14:30:00+00:00"},
        "league": {"id": 88, "name": "Eredivisie"},
        "bookmakers": [{
            "name": "Bet365", "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.90"},
                    {"value": "Draw", "odd": "3.60"},
                    {"value": "Away", "odd": "4.10"}]},
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 1.5", "odd": "1.30"},
                    {"value": "Under 1.5", "odd": "3.40"},
                    {"value": "Over 2.5", "odd": "1.85"},
                    {"value": "Under 2.5", "odd": "1.95"}]},
                {"name": "Both Teams Score", "values": [
                    {"value": "Yes", "odd": "1.70"},
                    {"value": "No", "odd": "2.10"}]},
                {"name": "Double Chance", "values": [
                    {"value": "Home/Draw", "odd": "1.25"},
                    {"value": "Draw/Away", "odd": "1.85"},
                    {"value": "Home/Away", "odd": "1.30"}]}]}],
    }],
}
fx_full = af._parse_odds_payload("Eredivisie", _FULL_PAYLOAD, FIXTURE_META)
assert fx_full.over15.price == 1.30, f"O/U1.5 not priced: {fx_full.over15.price}"
assert fx_full.under15.price == 3.40
assert fx_full.btts_yes.price == 1.70, f"BTTS not priced: {fx_full.btts_yes.price}"
assert fx_full.btts_no.price == 2.10
assert fx_full.dc_1x.price == 1.25, \
    f"DC 1X must price from 'Home/Draw': {fx_full.dc_1x.price}"
assert fx_full.dc_x2.price == 1.85, \
    f"DC X2 must price from 'Draw/Away': {fx_full.dc_x2.price}"
assert fx_full.dc_12.price == 1.30, \
    f"DC 12 must price from 'Home/Away': {fx_full.dc_12.price}"
# every one of the 11 selection markets must be priceable off this payload
_quoted = [mk for mk in mkt.EDGE_MARKETS
           if (q := mkt.quote(mk, fx_full)) is not None and q.available]
assert set(_quoted) == set(mkt.EDGE_MARKETS), \
    f"multi-market parse must price all 11 selection markets, got {_quoted}"
print("8b. full multi-market parse prices all 11 selection markets "
      "(real api-football DC value names): OK")

print()
print("✅ ALL API-FOOTBALL ODDS FALLBACK TESTS PASSED")
