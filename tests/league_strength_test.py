"""
Offline test of data/league_strength.py: league ratings fitted from matches
between leagues, the gap between two leagues (0 inside one league, None when
a league isn't rated), and how the gap moves a cross-league profile read.
No network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import league_strength as ls
from data import team_profiles as tp

# league 1 beats league 2 by a goal on average, home or away; league 3 is
# only ever seen against itself (no bridge -> not rated)
league_of = {"a": [1, "Strong"], "b": [1, "Strong"], "c": [2, "Weak"], "d": [2, "Weak"],
             "e": [3, "Island"], "f": [3, "Island"]}
ms = []
for _ in range(10):
    ms += [{"h": "a", "a": "c", "hg": 2, "ag": 0, "w": 1.0}, {"h": "d", "a": "b", "hg": 1, "ag": 1, "w": 1.0},
           {"h": "e", "a": "f", "hg": 1, "ag": 0, "w": 1.0}]
fit = ls.fit(ms, league_of)
lg = fit["leagues"]
assert lg["1"]["rated"] and lg["2"]["rated"] and not lg["3"]["rated"], lg
g = ls.gap(fit, 1, 2)
assert 0.8 < g < 1.0, f"about a goal a game between the leagues (ridge shrinks a little): {g}"
assert ls.gap(fit, 2, 1) == -g and ls.gap(fit, 1, 1) == 0.0
assert ls.gap(fit, 1, 3) is None, "a league with no bridge isn't rated: PENDING"
assert ls.gap(fit, None, 1) is None
print("league ratings and gap: OK")


def team(xg, xga):
    return {"stats": {"xg_pm": {"value": xg}, "xga_pm": {"value": xga}},
            "style": {"attack": "strong", "defence": "strong"}}


home, away = team(1.6, 1.0), team(2.4, 0.9)      # a small-league leader v a big-league giant
same = tp.profile_read(home, away)
cross = tp.profile_read(home, away, gap=-1.0)    # the home side's league is a goal weaker
assert cross["home_goals_hint"] == round(same["home_goals_hint"] - 0.5, 2)
assert cross["away_goals_hint"] == round(same["away_goals_hint"] + 0.5, 2)
assert cross["league_gap"] == -1.0 and same["lean"].startswith("BTTS yes"), "two 'strong' attacks in their own leagues"
assert not cross["lean"].startswith("BTTS yes"), "against a much stronger league the small side's attack isn't strong"
assert tp.profile_read(home, away, gap=None)["lean"].startswith("PENDING")
print("cross-league profile read: OK")

print("ALL LEAGUE STRENGTH TESTS PASSED")
