"""
Offline tests for order 34: the draw guard's draw-loss rule, team profiles
(no look-ahead, sane shares) and the national Elo (updates, scoreline grid).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import run_daily as rd
from engine import national_elo as ne
from engine import profiles as prof

# Draw guard: which picks lose on every draw.
for k, want in [("SB:10||Home or Away", True), ("SB:1||Away", True), ("DC_12", True),
                ("SB:10||Draw or Away", False), ("SB:11||Home", False),
                ("SB:16|hcp=0.5|Home (+0.5)", False), ("SB:18|total=2.5|Over 2.5", False),
                ("UNDER_2_5", False)]:
    assert rd._loses_on_draw(k) == want, k
print("draw guard rule: OK")

# Profiles: only games BEFORE the date count; shares are right.
rows = [prof.Row(f"2026-0{m}-0{d}", "A", "B", hg, ag)
        for m, d, hg, ag in [(1, 1, 1, 1), (1, 2, 2, 0), (1, 3, 0, 0), (1, 4, 3, 2),
                             (1, 5, 1, 1), (1, 6, 0, 1), (1, 7, 2, 2), (1, 8, 4, 0)]]
book = prof.ProfileBook(rows)
p = book.profile("A", before="2026-01-08")
assert p.n == 7 and abs(p.draw - 4 / 7) < 1e-9 and abs(p.btts - 4 / 7) < 1e-9, p
assert book.profile("A", before="2026-01-04") is None, "fewer than 6 games -> no profile"
mp = prof.match_profile(book, "A", "B", before="2026-01-09")
assert mp.draw_tendency is not None and "both draw-prone" in mp.line()
print("team profiles: OK")

# National Elo: a win moves ratings; margins and competitions weigh in.
e = ne.NationalElo()
e.update(ne.Match("2024-01-01", "X", "Y", 3, 0, "UEFA Nations League", False))
assert e.r["X"] > ne.START > e.r["Y"]
assert ne.margin_mult(3) > ne.margin_mult(2) > ne.margin_mult(1) == 1.0
m = ne.score_matrix(1.5, 1.0)
assert abs(m.sum() - 1) < 1e-9 and m[1, 0] > m[0, 1]
assert ne.predict(e, "X", "Y") is None, "fewer than 10 games -> not rated (HR35)"
real = ne.build(through="2025-01-01")
pp = ne.predict(real, "France", "Gibraltar")
assert pp is not None and pp.p_home > 0.85 and abs(pp.p_home + pp.p_draw + pp.p_away - 1) < 1e-6
print("national Elo: OK")

print("\n✅ ALL DRAW / PROFILE / NATIONAL TESTS PASSED")
