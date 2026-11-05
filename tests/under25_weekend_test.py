"""Under 2.5 singles + 2-3 leg accas on the weekend dates only (Architect 2026-11-05)."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import markets as mkt  # noqa: E402
from engine import slip_overlap  # noqa: E402
from engine.calibration import over  # noqa: E402
from output import produce_bet as pb  # noqa: E402

assert pb.UNDER25_MIN == 0.55
assert pb.UNDER25_DATES == frozenset({"2026-11-07", "2026-11-08"}), "this weekend only, by default"
assert "under25" in slip_overlap.ORDER


def bf(name, raw_over25, day="2026-11-07", price=1.75, src="model"):
    return SimpleNamespace(fixture=f"{name} (Test League)", kickoff_date=day, prob_source=src, under25_price=price,
                           probs=SimpleNamespace(p_over_25=raw_over25, home_team=name, away_team="B"))


def raw_for(under):   # the raw over-2.5 that calibrates to a given under-2.5 chance
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if 1 - over(2.5, mid) > under:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


board = [bf("Strong", raw_for(0.66)), bf("Bar", raw_for(0.56)), bf("Thin", raw_for(0.52)),
         bf("Friday", raw_for(0.70), day="2026-11-06"),              # not a weekend date: never
         bf("Market", raw_for(0.70), src="market"),                    # market-only probs: never
         bf("Long", raw_for(0.70), price=2.30),                        # outside the deploy band
         bf("Unpriced", raw_for(0.70), price=None),
         bf("Sunday", raw_for(0.60), day="2026-11-08")]
singles = pb._build_under25(board)
assert [s[1][0][0].probs.home_team for s in singles] == ["Strong", "Sunday", "Bar"], singles
assert [n for n, _, _ in singles] == ["U2.5 1", "U2.5 2", "U2.5 3"]
leg = singles[0][1][0]
assert leg[1] == "Under 2.5 goals" and leg[3] == mkt.UNDER_25 and leg[4] == 1.75
assert abs(leg[2] - 0.66) < 1e-6

accas = pb._build_under25_accas(singles)
assert [n for n, _, _ in accas] == ["U2.5 acca 1"] and len(accas[0][1]) == 3

pb.UNDER25_DATES = frozenset()          # "" in the env turns it off
assert pb._build_under25(board) == []
print("under25_weekend_test: OK")
