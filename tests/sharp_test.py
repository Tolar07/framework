"""Sharp price check (pipeline/sharp.py): Betfair Exchange fair odds. Offline."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import sharp  # noqa: E402

ROW = {"Div": "E0", "HomeTeam": "Arsenal", "AwayTeam": "Chelsea",
       "BFEH": "2.0", "BFED": "4.0", "BFEA": "4.0", "BFE>2.5": "1.9", "BFE<2.5": "2.1"}


def test_fair_book_and_markets() -> None:
    fair, _ = sharp.fair_book([ROW, {"Div": "E0", "HomeTeam": "X", "AwayTeam": "Y", "BFEH": ""}])
    f = fair[("E0", "Arsenal", "Chelsea")]
    assert abs(f["h"] - 0.5) < 1e-9 and abs(f["d"] - 0.25) < 1e-9 and abs(f["a"] - 0.25) < 1e-9
    assert abs(f["o25"] + f["u25"] - 1) < 1e-9
    assert ("E0", "X", "Y") not in fair, "no prices -> no number (HR35)"
    mp = sharp.market_prob
    assert abs(mp("DC_1X", f) - 0.75) < 1e-9
    assert abs(mp("SB:10||Home or Away", f) - 0.75) < 1e-9
    assert abs(mp("SB:1||Home", f) - 0.5) < 1e-9 and mp("1X2_DRAW", f) == f["d"]
    assert mp("SB:18|total=2.5|Over 2.5", f) == f["o25"] == mp("OVER_2_5", f)
    for k in ("SB:18|total=1.5|Over 1.5", "SB:29||Yes", "BTTS_YES", "SB:16|hcp=-1|Home", None):
        assert mp(k, f) is None, k


def test_check_sets_values_on_deploy_picks_only() -> None:
    def bf(key, price, deploy=True, src="model"):
        return NS(fixture="Arsenal v Chelsea (Premier League)", on_deploy_shortlist=deploy,
                  probs=NS(home_team="Arsenal", away_team="Chelsea"), best_market_key=key,
                  best_price=price, prob_source=src)
    good, bad, off, mkt = (bf("SB:1||Home", 2.1), bf("DC_1X", 1.25),
                           bf("SB:1||Home", 2.1, deploy=False), bf("SB:1||Home", 2.1, src="market"))
    n, above, _ = sharp.check([good, bad, off, mkt], rows=[ROW])
    assert (n, above) == (2, 1)
    assert abs(good.sharp_ev - 0.05) < 1e-9 and good.sharp_p == 0.5
    assert bad.sharp_ev < 0
    assert off.sharp_ev is None and mkt.sharp_ev is None


if __name__ == "__main__":
    test_fair_book_and_markets()
    test_check_sets_values_on_deploy_picks_only()
    print("sharp check: OK")
