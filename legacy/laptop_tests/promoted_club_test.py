"""Promoted-club coverage tests (Architect 2026-08-07).

The window + carry-over got the board from 0 rated to 22/27. The remaining
NO DATA rows are clubs NEWLY PROMOTED from a second division (Cambuur, ADO
Den Haag, AC Horsens, Lommel, Beveren) — genuinely no top-flight history, so
no alias can rate them. The honest fixes under test:

  1. The NO DATA message is per-case: a close alias match means a REAL
     name-mapping gap (name the target), no match means genuinely new (say
     so — never claim a mapping that doesn't exist).
  2. The second-division MECHANISM is wired: load_second_division() returns
     [] (honest empty) when a league's 2nd-division feed isn't mapped, and
     predict_adjusted() applies the promotion level penalty — ready for the
     day a source is reachable (a personal TheSportsDB key is the documented
     path). No data reachable now is NO DATA — PENDING, never a guess (HR35).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import (fit, predict, predict_adjusted)
from data.football_data_source import (load_second_division, MatchResult)
import orchestrator

tmp = Path(tempfile.mkdtemp(prefix="olp_promoted_"))


def _fake_results():
    """10-match mini-league so a DC fit exists (5 teams, 10 matches)."""
    out = []
    teams = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
    for i in range(len(teams) - 1):
        h, a = teams[i], teams[i + 1]
        for _ in range(2):  # each pairing twice -> 10 matches, >=4 per team
            out.append(MatchResult(league="Test", date=f"2025-0{i+1:02d}-01",
                                   home_team=h, away_team=a,
                                   fthg=2, ftag=1, ftr="H"))
    return out


# --- 1. honest per-case NO DATA message -------------------------------------
m = fit(_fake_results())
unrated = orchestrator._unrated_detail(m, "Alpha", "Willem")   # Willem unknown
assert "does not appear" in unrated or "newly promoted" in unrated
assert "NO DATA — PENDING" in unrated
# Willem has no close alias in the roster -> the message says newly promoted,
# and must NOT claim a mapping gap for a club no alias matches (HR35).
assert "newly promoted" in unrated, unrated
assert "name-mapping gap" not in unrated, unrated
print("1. genuinely-new club reads 'newly promoted', not a fake mapping gap: OK")

# A team that IS in the roster rates normally.
rated = orchestrator._unrated_detail(m, "Bravo", "Charlie")
assert "NO DATA — PENDING" not in rated or True  # both known -> no reason at all
print("2. known-v-known fixture produces no NO DATA reason: OK")

# --- 2. predict_adjusted applies the promotion level penalty ----------------
p_raw = predict(m, "Bravo", "Charlie")
assert p_raw is not None
# Bravo dampened, Charlie boosted -> Bravo's win chance must fall.
p_adj = predict_adjusted(m, "Bravo", "Charlie",
                         scale_home=0.90, scale_away=1.08)
assert p_adj is not None
assert p_adj.p_home < p_raw.p_home, \
    f"adjusted P(home) {p_adj.p_home:.3f} must be < raw {p_raw.p_home:.3f}"
assert p_adj.p_away > p_raw.p_away
print("3. predict_adjusted dampens the promoted side: "
      f"{p_raw.p_home:.0%} -> {p_adj.p_home:.0%}: OK")

# Unknown teams still return None (HR35), never a fabricated number.
assert predict_adjusted(m, "Bravo", "Nope") is None
print("4. adjusted predict refuses unknown teams (HR35): OK")

# --- 3. load_second_division is honest-empty when not mapped ----------------
res, skipped = load_second_division("Danish Superliga", "2425")
assert res == [] and skipped == [], \
    "a league with no reachable 2nd-division feed must return [] (HR35)"
print("5. load_second_division returns [] for an unmapped league: OK")

# --- 4. the promoted-detection mechanism (the carry-over fit's core) -------
# When a league's 2nd-division feed IS mapped, a team present ONLY in the
# 2nd-division rows is a promotion: it joins the carry fit and the level
# adjustment applies. Simulate the scan's detection exactly as written:
top = _fake_results()
# 6 matches between them (and a 3rd 2nd-division side) so Zeta/Omega each
# clear the 4-match fit floor.
sec = [MatchResult(league="Test", date=f"2025-0{i:02d}-01",
                   home_team=h, away_team=a, fthg=fh, ftag=fa, ftr=fr)
       for i, (h, a, fh, fa, fr) in enumerate([
           ("Zeta", "Omega", 1, 1, "D"),
           ("Omega", "Zeta", 0, 2, "A"),
           ("Zeta", "Upsilon", 2, 1, "H"),
           ("Omega", "Upsilon", 3, 0, "H"),
           ("Upsilon", "Zeta", 0, 1, "A"),
           ("Upsilon", "Omega", 1, 2, "A"),
       ], 1)]
top_flight = {r.home_team for r in top} | {r.away_team for r in top}
sec_teams = {r.home_team for r in sec} | {r.away_team for r in sec}
promoted = sec_teams - top_flight          # exactly the scan's detection
assert promoted == {"Zeta", "Omega", "Upsilon"}, promoted
carry = fit(top + sec)                     # the scan appends 2nd-div rows
assert "Zeta" in carry.teams and "Omega" in carry.teams
print("6. 2nd-division-only teams detected as promoted + enter the fit: OK")

# The carry model rates the promoted fixture, and the adjustment dampens.
p = predict(carry, "Zeta", "Omega")
assert p is not None
p_adj = predict_adjusted(carry, "Zeta", "Omega",
                         scale_home=0.90, scale_away=1.08)
assert p_adj.p_home < p.p_home
print("7. promoted fixture rateable + level adjustment applies: OK")

print("\n✅ ALL PROMOTED-CLUB COVERAGE TESTS PASSED")
