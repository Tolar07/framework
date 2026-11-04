"""
Offline tests of the CLV reliability tiers (backtest/clv_tiers_study.py, issue #295) and the permutation test
of the edge rule (backtest/permutation_study.py, issue #297): tiers follow the three tests, missing CLV stays
PENDING (HR35), a pick tier resting on tier-C CLV is flagged, the market-odds null gives a rule with no edge
an unremarkable p, a rule that really knows the result a small p, and thin data reads PENDING.
"""
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import clv_tiers_study as T  # noqa: E402
import permutation_study as P  # noqa: E402


def test_tiers_follow_the_three_tests():
    assert T.tier("SB:1||Home", "Premier League") == "A"
    assert T.tier("SB:18|total=2.5|Over 2.5", "Eredivisie") == "B"
    assert T.tier("SB:60||Home", "Premier League") == "C"          # first half: hidden information
    assert T.tier("SB:548||2-5", "Premier League") == "C"          # multigoals: not sharp-shaped
    assert T.tier("NBA:225|total=220.5|Over 220.5", None) == "A"
    assert T.tier("NBA:68|total=110.5|Over 110.5", None) == "C"
    assert T.tier(None, "Premier League") == "PENDING"


def _ledger(d: Path, singles: list[dict], day: str = "2026-10-01") -> None:
    (d / f"picks_{day}.json").write_text(json.dumps({"date": day, "singles": singles}), encoding="utf-8")


def test_missing_clv_is_pending_and_weak_rules_flagged():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        _ledger(d, [{"market": "SB:548||2-5", "league": "Serie A", "tier": "VALUE", "price": 2.0,
                     "result": "won" if i % 2 else "lost", "clv": 1.0} for i in range(12)]
                + [{"market": "SB:1||Home", "league": "Serie A", "tier": "SAFE", "price": 1.5,
                    "result": "won", "clv": None}])
        rec = T.build(T.collect(d))
    assert rec["tiers"]["A"]["clv_n"] == 0 and rec["tiers"]["A"]["mean_clv_pct"] is None
    assert "PENDING" in T.report(rec)
    assert [f["rule"] for f in rec["weak_evidence_rules"]] == ["VALUE"]
    assert rec["recorded_only"] is True


def _fixtures(n: int, knows: bool, seed: int = 5) -> list[dict]:
    rng = random.Random(seed)  # noqa: S311 — seeded test data
    out = []
    for i in range(n):
        fh = rng.uniform(0.3, 0.6)
        fair = {"home": fh, "draw": 0.25, "away": 0.75 - fh}
        px = {k: round(1 / (v * 1.05), 2) for k, v in fair.items()}
        u = rng.random()
        res = "home" if u < fh else ("draw" if u < fh + 0.25 else "away")
        p = dict(fair)
        if knows:
            p["home"] = 0.95 if res == "home" else 0.05
        y = {"home": int(res == "home"), "draw": int(res == "draw"), "away": int(res == "away"),
             "over 2.5": 0, "under 2.5": 1, "btts yes": 0, "btts no": 1}
        out.append({"stratum": f"L{i % 3}|2627", "p": p, "px": px, "y": y})
    return out


def test_market_null_separates_knowledge_from_noise():
    noise = P.test(_fixtures(300, knows=False), shuffles=200)
    assert noise["fixed"]["bets"] == 0 or noise["fixed"]["p"] > 0.05
    sharp = P.test(_fixtures(300, knows=True), shuffles=200)
    assert sharp["fixed"]["p"] < 0.05 and sharp["verdict"] == "BEATS NOISE"


def test_thin_data_pending_and_block_shuffle_keeps_strata():
    assert P.test(_fixtures(20, knows=True))["verdict"] == "PENDING"
    recs = _fixtures(60, knows=False)
    ys = P.shuffled(recs, random.Random(1))  # noqa: S311
    for s in {r["stratum"] for r in recs}:
        real = sorted(r["y"]["home"] for r in recs if r["stratum"] == s)
        mixed = sorted(y["home"] for r, y in zip(recs, ys, strict=True) if r["stratum"] == s)
        assert real == mixed
