"""Team-alias resolution tests.

suggest_aliases() finds likely pool matches for an unknown fixtures-feed name:
an exact accent/case-folded match wins, fuzzy difflib candidates follow, and a
genuinely unknown team yields nothing. Results are SUGGESTIONS — never applied
automatically (an unverified alias is a silent mis-rating)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.cross_league import suggest_aliases

POOL = ["Fenerbahçe", "Sturm Graz", "Aarhus", "AGF Aarhus", "Ath Madrid",
        "Milan", "Man City", "Kilmarnock", "Sociedad", "Copenhagen"]

# --- 1. exact match after accent/case folding -------------------------------
hits = suggest_aliases("Fenerbahce", POOL)
assert hits == [("Fenerbahçe", 1.0)], hits
print("1. accent-folded exact match ('Fenerbahce'->Fenerbahçe): OK")

# --- 2. plain exact match ----------------------------------------------------
assert suggest_aliases("Kilmarnock", POOL) == [("Kilmarnock", 1.0)]
print("2. plain exact match: OK")

# --- 3. fuzzy: prefix + minor spelling ---------------------------------------
hits = suggest_aliases("SK Sturm Graz", POOL)
assert hits and hits[0][0] == "Sturm Graz" and 0.5 < hits[0][1] < 1.0, hits
hits = suggest_aliases("Atletico Madrid", POOL)
assert hits and hits[0][0] == "Ath Madrid", hits
print("3. fuzzy candidates found (prefix + alternate spelling): OK")

# --- 4. genuinely unknown team -> empty, no fabricated match -----------------
assert suggest_aliases("Sabah FK", POOL) == []
assert suggest_aliases("FK 100 Miles", POOL) == []
print("4. unknown team -> empty (no fabrication): OK")

# --- 5. short/weak strings don't match on noise ------------------------------
# A two-letter token is almost never a real club name in the pool.
assert suggest_aliases("FK", POOL) == []
print("5. noise string matches nothing: OK")

print("\n✅ ALL TEAM ALIAS TESTS PASSED")
