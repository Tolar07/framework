"""
Offline test of the research harness (research/runner.py, autonomy plan item 4):
hypotheses validated (a bad line is marked invalid, never run), bet rules
filtered as written (band, covered, country, sharp gap vs Matchbook fair),
verdicts written back, an accepted rule queued ONCE as a shadow strategy for
the experiment engine, final verdicts not retested, a feature hypothesis read
from the features study rows, the results file, and the weekly brief present.
"""
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from research import runner  # noqa: E402

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def game(i, home_px, h, a, covered=True, mb=None, country="England", last_px=None):
    r = {"sport": "football", "id": f"sr:{i}", "country": country, "comp": "League", "covered": covered,
         "ko": f"2026-10-{1 + i % 28:02d}T15:00Z", "home": f"H{i}", "away": f"A{i}",
         "first": {"p": {"1x2": [home_px, 3.6, 4.5]}},
         "last": {"p": {"1x2": [last_px or home_px, 3.6, 4.5]}},
         "result": {"h": h, "a": a, "after_90": False}}
    if mb:
        r["mb_first"] = {"p": {"1x2": mb}}
    return r


def test_validate():
    assert runner.validate({"id": "X", "idea": "i", "source": "s",
                            "test": {"kind": "bet_rule", "market": "1x2:home"}}) == []
    assert "test.kind" in " ".join(runner.validate({"id": "X", "idea": "i", "source": "s",
                                                    "test": {"kind": "python", "code": "import os"}}))
    assert runner.validate({"test": {"kind": "feature"}})          # missing everything


def test_rule_filters():
    rows = [game(1, 1.4, 2, 0), game(2, 1.6, 2, 0), game(3, 1.3, 0, 1, covered=False),
            game(4, 1.45, 1, 1, country="Spain"), game(5, 2.2, 1, 0, mb=[1.9, 3.8, 4.4]),
            game(6, 2.2, 1, 0, mb=[2.3, 3.4, 3.2])]
    b = runner.rule_bets({"market": "1x2:home", "price_min": 1.2, "price_max": 1.5}, rows)
    assert sorted(x[2] for x in b) == [1.3, 1.4, 1.45]
    b = runner.rule_bets({"market": "1x2:home", "price_max": 1.5, "covered": True, "country_has": "eng"}, rows)
    assert [x[2] for x in b] == [1.4]
    b = runner.rule_bets({"market": "1x2:home", "sharp_ev_min": 0.03}, rows)
    assert [x[2] for x in b] == [2.2] and b[0][1] == 1        # only where SportyBet beat Matchbook's fair
    b = runner.rule_bets({"market": ["1x2:home", "1x2:away"], "price_max": 1.5}, rows[:1])
    assert len(b) == 1
    rows.append({"sport": "football", "ko": "2026-10-09T15:00Z", "first": {"p": {"1x2": [1.4, 4, 6]}}})
    assert len(runner.rule_bets({"market": "1x2:home", "price_max": 1.5}, rows)) == 3   # ungraded skipped


def test_run_queue_and_results():
    good = [game(i, 2.2, 1 if i % 2 == 0 else 0, 0 if i % 2 == 0 else 1, last_px=2.0) for i in range(120)]
    hyps = [
        {"id": "H1", "idea": "back home at 2.2", "source": "test", "status": "proposed",
         "test": {"kind": "bet_rule", "market": "1x2:home", "price_min": 2.0, "price_max": 2.5}},
        {"id": "H2", "idea": "tiny", "source": "test", "status": "proposed",
         "test": {"kind": "bet_rule", "market": "1x2:away", "price_min": 100}},
        {"id": "H3", "idea": "bad", "source": "test", "status": "proposed", "test": {"kind": "shell"}},
        {"id": "H4", "idea": "feature", "source": "test", "status": "proposed",
         "test": {"kind": "feature", "outcome": "over 2.5", "feature": "soft close gap"}},
        {"id": "H5", "idea": "old", "source": "test", "status": "rejected",
         "test": {"kind": "bet_rule", "market": "1x2:home"}},
    ]
    feats = {"over 2.5": {"soft close gap": [("2026-10-01", 0.5, 1, 0.1)] * 10}}
    with tempfile.TemporaryDirectory() as t:
        hp, qp = Path(t) / "h.jsonl", Path(t) / "q.jsonl"
        runner.save(hyps, hp)
        out = {h["id"]: h for h in runner.run(now=NOW, hyp_path=hp, queue_path=qp, urows=good, feature_rows=feats)}
        assert out["H1"]["status"] == "accepted", out["H1"]
        assert out["H2"]["status"] == "pending-data"
        assert out["H3"]["status"] == "invalid"
        assert out["H4"]["status"] == "pending-data" and "scored" in out["H4"]["result"]
        assert out["H5"]["status"] == "rejected" and "tested_at" not in out["H5"]     # final: not retested
        q = [json.loads(x) for x in qp.read_text().splitlines()]
        assert len(q) == 1 and q[0]["strategy_id"] == "research:H1" and q[0]["mode"] == "shadow"
        assert q[0]["kind"] == "shadow_strategy" and q[0]["rule"]["market"] == "1x2:home"
        runner.run(only="H1", now=NOW, hyp_path=hp, queue_path=qp, urows=good, feature_rows=feats)
        assert len(qp.read_text().splitlines()) == 1                                  # queued once
        assert len(runner.load(hp)) == 5                                              # nothing lost
        text = runner.report(runner.load(hp))
        assert "| H1 |" in text and "accepted" in text and "SHADOW" in text
        assert "NO DATA — PENDING" in runner.report([])
        uk = runner.run_feature({"outcome": "over 2.5", "feature": "nope"}, feats)
        assert uk[0] == "inconclusive" and uk[1]["verdict"] == "UNKNOWN FEATURE"


def test_summary_line():
    line = runner.summary_line([{"id": "H1", "status": "accepted", "tested_at": "2026-10-20"},
                                {"id": "H2", "status": "rejected", "tested_at": "2026-10-19"}], "PR #9")
    assert "2 hypotheses" in line and "accepted 1 (H1)" in line and "PR #9" in line and "shadow" in line
    assert "\n" not in line and "PENDING" in runner.summary_line([])


def test_seed_hypotheses_and_brief():
    hyps = runner.load()
    assert hyps, "memory/hypotheses.jsonl is empty"
    for h in hyps:
        assert runner.validate(h) == [], (h.get("id"), runner.validate(h))
    assert len({h["id"] for h in hyps}) == len(hyps)
    brief = (ROOT / "research" / "WEEKLY_BRIEF.md").read_text(encoding="utf-8")
    for must in ("memory/hypotheses.jsonl", "research/runner.py", "never", "PR", "Telegram"):
        assert must in brief, must


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
