"""Same-result price shopping (Architect 2026-10-12): outcomes that settle
identically on every scoreline are one bet; only the best price is kept."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import full_markets as fm  # noqa: E402

dc_1x = fm.rule_for(10, "", "Home/Draw")
ah_plus_half = fm.rule_for(16, "hcp=0.5", "Home (+0.5)")
dnb_home = fm.rule_for(11, "", "Home")
ah_zero = fm.rule_for(16, "hcp=0", "Home (0)")
home = fm.rule_for(1, "", "Home")
over15 = fm.rule_for(18, "total=1.5", "Over 1.5")

# the identities the catalogue lists
assert fm.settles_as(dc_1x) == fm.settles_as(ah_plus_half), "1X = Asian handicap Home +0.5"
assert fm.settles_as(dnb_home) == fm.settles_as(ah_zero), "Draw No Bet Home = Asian handicap Home 0"
assert fm.settles_as(home) != fm.settles_as(dnb_home), "a draw pushes DNB but loses the plain win"


def cand(key, price, win=0.8):
    return (win, win * price - 1, key, win, win, SimpleNamespace(price=price))


rules = {"SB:10||Home/Draw": dc_1x, "SB:16|hcp=0.5|Home (+0.5)": ah_plus_half,
         "SB:1||Home": home, "SB:18|total=1.5|Over 1.5": over15}
cands = [cand("SB:10||Home/Draw", 1.25), cand("SB:1||Home", 1.70, 0.6),
         cand("SB:16|hcp=0.5|Home (+0.5)", 1.29), cand("SB:18|total=1.5|Over 1.5", 1.30)]
kept, dropped = fm.best_price_per_result(cands, rules)
keys = [c[2] for c in kept]
assert dropped == 1, dropped
assert "SB:16|hcp=0.5|Home (+0.5)" in keys and "SB:10||Home/Draw" not in keys, "keeps the better price"
assert keys == ["SB:1||Home", "SB:16|hcp=0.5|Home (+0.5)", "SB:18|total=1.5|Over 1.5"], "order kept"

# a tie keeps the first one; an unknown key is never merged
kept, dropped = fm.best_price_per_result([cand("SB:10||Home/Draw", 1.29), cand("SB:16|hcp=0.5|Home (+0.5)", 1.29),
                                          cand("X", 1.5), cand("Y", 1.5)], rules)
assert [c[2] for c in kept] == ["SB:10||Home/Draw", "X", "Y"] and dropped == 1

print("same_result_test: OK")
