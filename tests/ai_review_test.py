"""research/ai_review.py — step 6 of the bot-training plan (2026-11-01)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research import ai_review as A  # noqa: E402

KEYS = {"gemini": "g", "nvidia": "n", "openrouter": "o"}


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def get(url, **kw):
    return Resp({"data": [{"id": "gemini-3.5-flash-lite"}]})


def poster(hyps, fail_gemini=False):
    def post(url, json=None, **kw):
        if fail_gemini and "generativelanguage" in url:
            return Resp({}, 500)
        return Resp({"choices": [{"message": {"content": __import__("json").dumps({"hypotheses": hyps})}}]})
    return post


EXISTING = [{"id": "H007", "idea": "old", "status": "rejected",
             "test": {"kind": "bet_rule", "market": "1x2:home", "price_max": 1.3}}]


def test_valid_new_ideas_become_proposed_hypotheses_with_the_next_ids():
    new, who = A.propose(date(2026, 11, 2), EXISTING, poster([
        {"idea": "Unders priced 1.6-2.0 in covered leagues", "why": "Over/Under 1.50-2.00 lost 12%",
         "test": {"kind": "bet_rule", "market": "o/u2.5:under", "price_min": 1.6, "price_max": 2.0,
                  "covered": True, "exec": "import os"}},
        {"idea": "x", "test": {"kind": "bet_rule", "market": "btts:no"}}]), get, keys=KEYS)
    assert who.startswith("gemini:")
    assert [h["id"] for h in new] == ["H008", "H009"]
    assert new[0]["status"] == "proposed" and "exec" not in new[0]["test"]       # unknown keys dropped
    assert "ai-review 2026-11-02" in new[0]["source"]


def test_repeats_unrunnable_tests_and_extras_are_dropped():
    new, _ = A.propose(date(2026, 11, 2), EXISTING, poster([
        {"idea": "same as H007", "test": {"kind": "bet_rule", "market": "1x2:home", "price_max": 1.3}},
        {"idea": "no market", "test": {"kind": "bet_rule"}},
        {"idea": "code", "test": {"kind": "python", "src": "..."}},
        {"idea": "a", "test": {"kind": "bet_rule", "market": "dc:1x"}}]), get, keys=KEYS)
    assert new == []          # only the first MAX_NEW answers are read, and both were unusable


def test_falls_to_the_next_member_when_gemini_fails():
    new, who = A.propose(date(2026, 11, 2), [], poster(
        [{"idea": "a", "test": {"kind": "bet_rule", "market": "dc:1x"}}], fail_gemini=True), get, keys=KEYS)
    assert who.startswith("nvidia:") and len(new) == 1 and new[0]["id"] == "H001"


def test_feature_tests_must_name_a_known_feature():
    assert A.clean_test({"kind": "feature", "outcome": "home win", "feature": "no-such-feature-xyz"}) is None
    assert A.clean_test({"kind": "bet_rule", "market": "dc:1x", "price_min": 1.2})["price_min"] == 1.2
    assert "bet_rule" in A.spec_text()


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ai_review_test OK")


if __name__ == "__main__":
    main()
