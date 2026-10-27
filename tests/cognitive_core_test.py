"""engine/cognitive_core.py — the five-stage cognitive core (to-do #3). No network: post is a fake."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import cognitive_core as CC  # noqa: E402
from engine import reasoning as R  # noqa: E402

FULL = {"price": 1.5, "base_prob": 0.7, "market_prob": 0.66, "news_level": "OK", "profile_lean": 0.68,
        "league": "Premier League", "family": "1X2", "domain": "football"}


class Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def gemini(obj):
    return Resp({"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]})


def tmp() -> Path:
    return Path(tempfile.mkdtemp())


def test_regime_and_missing_detection():
    flags, missing = CC.detect_regime_flags(FULL)
    assert flags == [] and missing == []
    ctx = {**FULL, "market_prob": None, "news_level": "PENDING", "profile_lean": "", "league": "DFB Pokal",
           "rest_days_home": 3, "rest_days_away": 5, "post_international_window": True,
           "elo_prob": 0.55, "dc_prob": 0.70, "volatility": 0.45, "rsi": 70}
    flags, missing = CC.detect_regime_flags(ctx)
    assert missing == ["market_prob", "news_level", "profile_lean"], missing
    assert flags == ["SHORT_REST_HOME", "FIFA_VIRUS_WINDOW", "DOMESTIC_CUP_ROTATION_RISK",
                     "ELO_DC_ENGINE_DIVERGENCE", "HIGH_VOLATILITY_REGIME", "OVERBOUGHT_EXTENSION"], flags
    assert CC.detect_regime_flags({**FULL, "news_level": "RISK: keeper out"})[0] == ["TEAM_NEWS_RISK"]
    assert CC.detect_regime_flags({**FULL, "news_level": "caution"})[0] == ["TEAM_NEWS_CAUTION"]
    assert CC.detect_regime_flags({**FULL, "league": "Copa del Rey"})[0] == ["DOMESTIC_CUP_ROTATION_RISK"]
    assert CC.detect_regime_flags({**FULL, "league": "Copenhagen derby"})[0] == []


def test_firewall_clamps():
    assert CC.firewall("BACK", 0.30, 0.7) == (0.08, 0.78)
    assert CC.firewall("BACK", -0.5, 0.7) == (-0.08, 0.62)
    assert CC.firewall("VETO", 0.05, 0.7) == (-0.03, 0.67)
    assert CC.firewall("LOWER", 0.0, 0.7) == (-0.01, 0.69)
    assert CC.firewall("BACK", 0.08, 0.95) == (0.08, 0.98)
    assert CC.firewall("VETO", -0.08, 0.05) == (-0.08, 0.02)
    assert CC.firewall("BACK", 0.02, None) == (0.02, None)


def test_debate_uses_header_key_schema_and_lessons():
    les = tmp() / "l.json"
    les.write_text(json.dumps({"cognitive": [{"domain": "football", "family": "1X2", "failure_mode": "LINEUP_OR_FATIGUE",
                                              "lesson": "check rotation before cup ties"}]}), encoding="utf-8")
    seen = {}

    def post(url, json=None, headers=None, params=None, **kw):
        seen.update(url=url, headers=headers, params=params, body=json)
        return gemini({"picks": [{"id": 0, "blue_team_thesis": "b", "red_team_attack": "r",
                                  "cio_verdict": "VETO", "prob_adjustment": 0.2}]})

    out = CC.evaluate([dict(FULL)], key="K", post=post, record_path=tmp() / "r.json", lessons_path=les)[0]
    assert seen["headers"] == {"x-goog-api-key": "K"} and seen["params"] is None and "K" not in seen["url"]
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent")
    gc = seen["body"]["generationConfig"]
    assert gc["temperature"] == 0.15 and gc["responseMimeType"] == "application/json" and gc["responseSchema"]
    assert "check rotation before cup ties" in seen["body"]["contents"][0]["parts"][0]["text"]
    assert out["cio_verdict"] == "VETO" and out["prob_adjustment"] == -0.03 and out["cognitive_prob"] == 0.67
    assert out["source"] == "gemini"


def test_fallback_on_api_failure():
    def boom(*a, **k):
        raise RuntimeError("503")
    risky, calm = CC.evaluate([{**FULL, "news_level": "RISK"}, dict(FULL)], key="K", post=boom,
                              record_path=tmp() / "r.json", lessons_path=tmp() / "l.json")
    assert (risky["cio_verdict"], risky["prob_adjustment"], risky["source"]) == ("LOWER", -0.02, "fallback")
    assert (calm["cio_verdict"], calm["prob_adjustment"]) == ("BACK", 0.0)
    # no key: no call at all, the same fallback
    assert CC.evaluate([dict(FULL)], key="", post=boom, record_path=tmp() / "r.json")[0]["source"] == "fallback"


def _history(n: int, cog_better: bool) -> list[dict]:
    rows = []
    for i in range(n):
        won = i % 3 != 0
        verdict = "VETO" if not won and i % 2 == 0 else "BACK"
        base = 0.7
        cog = (0.8 if won else 0.6) if cog_better else (0.6 if won else 0.8)
        rows.append({"id": f"x{i}", "domain": "football", "family": "1X2", "verdict": verdict, "won": won,
                     "base_prob": base, "cognitive_prob": cog,
                     "base_brier": CC._brier(base, won), "cog_brier": CC._brier(cog, won)})
    return rows


def test_shadow_mode_under_30_graded_rows():
    rec = tmp() / "r.json"
    rec.write_text(json.dumps({"cognitive_history": _history(29, True)}), encoding="utf-8")
    def post(*a, **k):
        return gemini({"picks": [{"id": 0, "blue_team_thesis": "", "red_team_attack": "", "cio_verdict": "BACK",
                                  "prob_adjustment": 0.05}]})
    out = CC.evaluate([dict(FULL)], key="K", post=post, record_path=rec, lessons_path=tmp() / "l.json")[0]
    assert out["authority"]["n"] == 29 and not out["authority"]["earned"]
    assert out["mode"] == "shadow" and out["effective_prob"] == 0.7 and out["cognitive_prob"] == 0.75
    assert out["stake_multiplier"] == 1.0 and out["advised_stake_multiplier"] == 1.0


def test_authority_earned_after_32_rows_where_cognitive_beats_base():
    rec = tmp() / "r.json"
    rec.write_text(json.dumps({"cognitive_history": _history(32, True)}), encoding="utf-8")
    a = CC.earned_authority("football", "1X2", CC.load_history(rec))
    assert a["earned"] and a["n"] == 32 and a["cog_brier"] + CC.BRIER_MARGIN <= a["base_brier"]
    assert a["veto_loss_rate"] >= CC.VETO_LOSS_MIN
    assert not CC.earned_authority("football", "BTTS", CC.load_history(rec))["earned"]   # per family
    assert not CC.earned_authority("nba", "1X2", CC.load_history(rec))["earned"]         # per domain
    worse = tmp() / "w.json"
    worse.write_text(json.dumps({"cognitive_history": _history(32, False)}), encoding="utf-8")
    assert not CC.earned_authority("football", "1X2", CC.load_history(worse))["earned"]

    def post(*a, **k):
        return gemini({"picks": [{"id": 0, "blue_team_thesis": "", "red_team_attack": "", "cio_verdict": "BACK",
                                  "prob_adjustment": 0.05}]})
    os.environ["COGNITIVE_STAKES"] = "0"                       # the off switch
    out = CC.evaluate([dict(FULL)], key="K", post=post, record_path=rec, lessons_path=tmp() / "l.json")[0]
    assert out["mode"] == "authority" and out["effective_prob"] == 0.75
    assert out["advised_stake_multiplier"] == 1.15 and out["stake_multiplier"] == 1.0   # COGNITIVE_STAKES off
    os.environ.pop("COGNITIVE_STAKES", None)                   # default ON (standing order 48)
    try:
        out = CC.evaluate([dict(FULL)], key="K", post=post, record_path=rec, lessons_path=tmp() / "l.json")[0]
        assert out["stake_multiplier"] == 1.15
    finally:
        os.environ.pop("COGNITIVE_STAKES", None)


def test_grade_and_learn_appends_once_and_writes_postmortem():
    rec, les = tmp() / "r.json", tmp() / "l.json"
    rec.write_text(json.dumps({"graded": 5}), encoding="utf-8")
    v = {"id": "football|2026-10-27|A v B|SB:1||Home", "date": "2026-10-27", "fixture": "A v B", "domain": "football",
         "family": "1X2", "cio_verdict": "BACK", "base_prob": 0.7, "cognitive_prob": 0.72, "flags": []}
    def post(*a, **k):
        return gemini({"failure_mode": "LINEUP_OR_FATIGUE", "lesson": " ".join(["word"] * 40)})
    row = CC.grade_and_learn(v, False, {"ft": "0-1"}, key="K", post=post, record_path=rec, lessons_path=les)
    assert row["base_brier"] == 0.49 and row["cog_brier"] == 0.5184 and row["postmortem"]["failure_mode"] == "LINEUP_OR_FATIGUE"
    assert len(row["postmortem"]["lesson"].split()) == 25
    assert json.loads(rec.read_text(encoding="utf-8"))["graded"] == 5          # other keys kept
    assert CC.grade_and_learn(v, False, key="K", post=post, record_path=rec, lessons_path=les) is None   # once per id
    assert CC.relevant_lessons("football", "1X2", lessons_path=les)[0].startswith("[LINEUP_OR_FATIGUE]")
    assert CC.relevant_lessons("football", "BTTS", lessons_path=les) == []
    # a won BACK, or a low-probability BACK that lost: no post-mortem call
    def never(*a, **k):
        raise AssertionError("no post-mortem expected")
    assert "postmortem" not in CC.grade_and_learn({**v, "id": "w"}, True, key="K", post=never, record_path=rec, lessons_path=les)
    assert "postmortem" not in CC.grade_and_learn({**v, "id": "l", "base_prob": 0.5}, False, key="K", post=never,
                                                  record_path=rec, lessons_path=les)
    # lessons kept to the last 200
    allx = json.loads(les.read_text(encoding="utf-8"))
    allx["cognitive"] = allx["cognitive"] * 250
    les.write_text(json.dumps(allx), encoding="utf-8")
    CC.grade_and_learn({**v, "id": "z"}, False, key="K", post=post, record_path=rec, lessons_path=les)
    assert len(json.loads(les.read_text(encoding="utf-8"))["cognitive"]) == 200


def test_reasoning_carries_the_cognitive_block_and_grades_it():
    d = tmp()
    out_dir, ledger = d / "out", d / "picks"
    out_dir.mkdir()
    ledger.mkdir()
    picks = {"date": "2026-10-20", "generated_at": "g", "singles": [
        {"fixture": "A v B", "league": "FA Cup", "market": "SB:1||Home", "pick": "A", "price": 1.4, "chance": 0.72,
         "sharp_p": 0.7, "news_level": "OK"}]}
    doc = R.reason(picks, key="")            # no key: reasoning PENDING, the core falls back
    c = doc["picks"][0]["cognitive"]
    assert c["flags"] == ["DOMESTIC_CUP_ROTATION_RISK"] and c["missing"] == ["profile_lean"]
    assert c["source"] == "fallback" and c["mode"] == "shadow" and doc["picks"][0]["stake_factor"] == 1.0
    assert doc["cognitive"]["fallback"] == 1
    (out_dir / "reasoning_2026-10-20.json").write_text(json.dumps(doc), encoding="utf-8")
    picks["singles"][0]["result"] = "lost"
    (ledger / "picks_2026-10-20.json").write_text(json.dumps(picks), encoding="utf-8")
    rec = d / "rec.json"
    def never(*a, **k):
        raise AssertionError("no key, no call")
    assert R.grade_cognitive(out_dir, ledger, rec, d / "les.json", key="", post=never) == 1
    assert R.grade_cognitive(out_dir, ledger, rec, d / "les.json", key="", post=never) == 0
    full = R.record(out_dir, ledger, rec)
    assert len(full["cognitive_history"]) == 1 and full["cognitive_authority"]["football | 1X2"]["n"] == 1


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
