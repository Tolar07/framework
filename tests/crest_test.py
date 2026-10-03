"""Test league flags and club crests rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp import render

# Test _initials function
print("Testing _initials...")
assert render._initials("Manchester United") == "MU"
assert render._initials("FC Barcelona") == "B"
assert render._initials("Real Madrid CF") == "RM"
assert render._initials("AC Milan") == "M"
assert render._initials("AS Roma") == "R"
assert render._initials("Ajax") == "AJA"
assert render._initials("PSV Eindhoven") == "PE"
print("  _initials: OK")

# Test _LEAGUE_COUNTRY mapping
print("Testing _LEAGUE_COUNTRY...")
assert render._LEAGUE_COUNTRY.get("Premier League") == "GB"
assert render._LEAGUE_COUNTRY.get("Bundesliga") == "DE"
assert render._LEAGUE_COUNTRY.get("Serie A") == "IT"
assert render._LEAGUE_COUNTRY.get("La Liga") == "ES"
assert render._LEAGUE_COUNTRY.get("Eredivisie") == "NL"
assert render._LEAGUE_COUNTRY.get("Champions League") == "EU"
print("  _LEAGUE_COUNTRY: OK")

# Test _flag_html
print("Testing _flag_html...")
flag_html = render._flag_html("Premier League")
assert "flagcdn.com" in flag_html
assert "GB" in flag_html
assert 'class="flag"' in flag_html

eu_flag = render._flag_html("Champions League")
assert 'class="flag placeholder"' in eu_flag
assert "EU" in eu_flag

unknown_flag = render._flag_html("Unknown League")
assert 'class="flag placeholder"' in unknown_flag
assert "?" in unknown_flag
print("  _flag_html: OK")

# Test _crest_html fallback
print("Testing _crest_html fallback...")
crest = render._crest_html("Manchester United", "Premier League")
assert 'class="crest placeholder"' in crest
assert "MU" in crest  # initials
assert 'style="background:' in crest
print("  _crest_html fallback: OK")

# Test _fixture_teams_with_badges
print("Testing _fixture_teams_with_badges...")
bf = {"fixture": "Manchester United v Liverpool (Premier League)", "probs": None}
home_badged, away_badged, league = render._fixture_teams_with_badges(bf)
assert "MU" in home_badged
assert "LI" in away_badged  # Liverpool -> LI
assert league == "Premier League"
print("  _fixture_teams_with_badges: OK")

# Test _fixture_teams_with_badges_admin
print("Testing _fixture_teams_with_badges_admin...")
home_badged, away_badged, league_badged = render._fixture_teams_with_badges_admin(bf)
assert "MU" in home_badged
assert "LI" in away_badged
assert "GB" in league_badged  # flag
assert "Premier League" in league_badged
print("  _fixture_teams_with_badges_admin: OK")

# Test _pick_confidence
print("Testing _pick_confidence...")
p = {"p_home": 0.56, "p_draw": 0.24, "p_away": 0.20}
bf_rated = {"probs": p}
assert render._pick_confidence(bf_rated) == 0.56

bf_unrated = {"probs": None}
assert render._pick_confidence(bf_unrated) == 0.0
print("  _pick_confidence: OK")

print("\n[OK] ALL CREST/FLAG TESTS PASSED")