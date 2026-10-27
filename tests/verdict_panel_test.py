"""engine/verdict_panel.py — the free-model verdict panel (to-do #5). No network: get/post are fakes."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import verdict_panel as VP  # noqa: E402


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.body


FREE = {"data": [{"id": "google/gemma-4-31b-it:free", "pricing": {"prompt": "0", "completion": "0"}},
                 {"id": "openai/gpt-paid", "pricing": {"prompt": "0.000002", "completion": "0.000008"}}]}
CTX = {"fixture": "A v B", "league": "Premier League", "pick": "Home", "family": "1X2", "domain": "football",
       "price": 1.80, "base_prob": 0.66, "market_prob": 0.55}


def tmp() -> Path:
    return Path(tempfile.mkdtemp()) / "panel_record.json"


def get(url, **kw):
    if "openrouter" in url:
        return Resp(FREE)
    return Resp({"data": [{"id": "meta/llama-3.3-70b-instruct"}, {"id": "gemini-2.5-flash"}]})


def answers(probs: dict, cost=None, status=None):
    """A fake post: each member answers prob for id 0; optionally a cost or a status per member."""
    sent = []

    def post(url, json=None, **kw):
        name = "openrouter" if "openrouter" in url else "nvidia" if "nvidia" in url else "gemini"
        sent.append((name, json["model"]))
        if status and name in status:
            return Resp({}, status[name])
        body = {"choices": [{"message": {"content": __import__("json").dumps(
            {"picks": [{"id": 0, "prob": probs[name], "why": "x"}]})}}]}
        if cost and name in cost:
            body["usage"] = {"cost": cost[name]}
        return Resp(body)
    post.sent = sent
    return post


KEYS = {"gemini": "g", "nvidia": "n", "openrouter": "o"}


def test_openrouter_guard_refuses_any_non_free_id():
    for bad in ("openai/gpt-paid", "google/gemma-4-31b-it", "", None, "x:free-ish"):
        try:
            VP.openrouter_guard(bad)
        except VP.PaidModelError:
            continue
        raise AssertionError(f"{bad!r} was allowed")
    assert VP.openrouter_guard("google/gemma-4-31b-it:free").endswith(":free")


def test_ask_raises_before_any_paid_openrouter_call():
    post = answers({"openrouter": 0.5})
    try:
        VP.ask("openrouter", "openai/gpt-paid", "o", [{"id": 0}], post)
    except VP.PaidModelError:
        assert post.sent == []                      # refused BEFORE the request
        return
    raise AssertionError("paid model was sent")


def test_openrouter_only_picks_listed_free_models(monkeypatch=None):
    import os
    os.environ["PANEL_OPENROUTER_MODEL"] = "openai/gpt-paid"   # an override that isn't free is ignored
    try:
        assert VP.pick_model("openrouter", get, "o") == "google/gemma-4-31b-it:free"
    finally:
        del os.environ["PANEL_OPENROUTER_MODEL"]
    assert VP.pick_model("openrouter", lambda u, **k: Resp({"data": []}), "o") is None


def test_a_charge_switches_openrouter_off_for_the_run():
    post = answers({"gemini": 0.56, "nvidia": 0.54, "openrouter": 0.70}, cost={"openrouter": 0.0001})
    res = VP.evaluate([dict(CTX)], keys=KEYS, get=get, post=post, record_path=tmp())
    assert res["members"]["openrouter"]["status"].startswith("off for this run")
    assert "openrouter" not in res["picks"][0]["members"]
    assert res["weights"]["openrouter"]["weight"] == 0.0


def test_anchor_is_the_market_and_shift_is_clamped():
    post = answers({"gemini": 0.95, "nvidia": 0.95, "openrouter": 0.95})
    p = VP.evaluate([dict(CTX)], keys=KEYS, get=get, post=post, record_path=tmp())["picks"][0]
    assert p["anchor"] == 0.55 and p["anchor_source"] == "market"
    assert p["panel_prob"] == 0.63                     # 0.55 + MAX_SHIFT
    assert p["edge"] == round(0.63 * 1.80 - 1, 4)
    assert p["mode"] == "shadow" and p["stake_factor"] is None


def test_missing_secret_runs_with_the_others_and_says_which():
    post = answers({"gemini": 0.57, "nvidia": 0.53})
    res = VP.evaluate([dict(CTX)], keys={"gemini": "g", "nvidia": "n", "openrouter": ""}, get=get, post=post,
                      record_path=tmp())
    assert res["members"]["openrouter"]["status"] == "missing secret OPENROUTER_API_KEY"
    assert res["picks"][0]["panel_prob"] == 0.55        # +0.02 and -0.02 cancel
    assert all(n != "openrouter" for n, _ in post.sent)


def test_rate_limited_member_is_dropped_for_the_run():
    post = answers({"gemini": 0.60, "nvidia": 0.40, "openrouter": 0.60}, status={"nvidia": 429})
    res = VP.evaluate([dict(CTX)], keys=KEYS, get=get, post=post, record_path=tmp())
    assert res["weights"]["nvidia"]["weight"] == 0.0
    assert res["picks"][0]["panel_prob"] == 0.60


def _hist(n, panel, live, clv_panel_right=True, member_probs=None):
    rows = []
    for i in range(n):
        won = i % 2 == 0
        rows.append({"id": str(i), "domain": "football", "family": "1X2", "stage": "board", "anchor": 0.5,
                     "members": member_probs(won) if member_probs else {"gemini": 0.5},
                     "panel_prob": panel(won), "live_prob": live(won), "edge": 0.05 if won else -0.05,
                     "live_back": True, "clv": (1.0 if won else -1.0) if clv_panel_right else 1.0, "won": won})
    return rows


def test_authority_needs_brier_and_clv_against_the_live_verdict():
    good = _hist(32, lambda w: 0.7 if w else 0.3, lambda w: 0.6)
    a = VP.earned_authority("football", "1X2", good)
    assert a["earned"] and a["panel_clv_hit"] > a["live_clv_hit"]
    assert not VP.earned_authority("football", "1X2", good[:29])["earned"]            # too few
    worse = _hist(32, lambda w: 0.3 if w else 0.7, lambda w: 0.6)
    assert not VP.earned_authority("football", "1X2", worse)["earned"]               # Brier worse
    no_clv = _hist(32, lambda w: 0.7 if w else 0.3, lambda w: 0.6, clv_panel_right=False)
    assert not VP.earned_authority("football", "1X2", no_clv)["earned"]              # CLV first


def test_stake_from_edge_only_with_authority():
    assert VP.edge_factor(-0.01) == 0.5 and VP.edge_factor(0.01) == 1.0 and VP.edge_factor(0.06) == 1.15
    rec = tmp()
    rec.write_text(json.dumps({"history": _hist(32, lambda w: 0.7 if w else 0.3, lambda w: 0.6)}))
    post = answers({"gemini": 0.60, "nvidia": 0.60, "openrouter": 0.60})
    p = VP.evaluate([dict(CTX)], keys=KEYS, get=get, post=post, record_path=rec)["picks"][0]
    # anchor 0.55 + 0.05 = 0.60; edge 0.60 x 1.80 - 1 = 0.08 >= EDGE_STRONG -> x1.15
    assert p["mode"] == "authority" and p["edge"] == 0.08 and p["stake_factor"] == 1.15
    import os
    os.environ["COGNITIVE_STAKES"] = "0"                                # the off switch
    try:
        p = VP.evaluate([dict(CTX)], keys=KEYS, get=get, post=post, record_path=rec)["picks"][0]
        assert p["stake_factor"] is None and p["advised_stake_factor"] == 1.15
    finally:
        del os.environ["COGNITIVE_STAKES"]


def test_member_that_never_beats_the_others_is_dropped():
    hist = _hist(40, lambda w: 0.6, lambda w: 0.6,
                 member_probs=lambda w: {"gemini": 0.8 if w else 0.2, "nvidia": 0.2 if w else 0.8})
    w = VP.member_weights(hist, ["gemini", "nvidia"])
    assert w["gemini"]["weight"] > 0 and w["nvidia"]["weight"] == 0.0 and w["nvidia"]["dropped"]


def test_lineup_pass_and_grading_round_trip():
    root = Path(tempfile.mkdtemp())
    out, led = root / "reasoning", root / "picks"
    out.mkdir(), led.mkdir()
    now = datetime(2026, 10, 27, 14, 0, tzinfo=UTC)
    ko = (now + timedelta(minutes=60)).isoformat()
    single = {"fixture": "A v B", "market": "1X2|Home", "pick": "Home", "price": 1.8, "chance": 0.66,
              "sharp_p": 0.55, "league": "Premier League", "kickoff_utc": ko,
              "lineup_check": {"level": "OK", "note": "both XIs as predicted"}}
    (led / "picks_2026-10-27.json").write_text(json.dumps({"singles": [single]}))
    (out / "reasoning_2026-10-27.json").write_text(json.dumps({"date": "2026-10-27", "picks": [
        {"fixture": "A v B", "market": "1X2|Home", "pick": "Home", "verdict": "back", "ai_chance": 0.64,
         "model_chance": 0.66, "stake_factor": 1.0, "panel": {"stage": "board", "panel_prob": 0.56}}]}))
    post = answers({"gemini": 0.58, "nvidia": 0.58, "openrouter": 0.58})
    msg = VP.lineup_pass(now, out, led, keys=KEYS, get=get, post=post, record_path=root / "rec.json")
    assert "1 pick" in msg
    doc = json.loads((out / "reasoning_2026-10-27.json").read_text())
    x = doc["picks"][0]
    assert x["panel_lineup"]["stage"] == "lineup" and x["panel_lineup"]["panel_prob"] == 0.58
    assert x["panel"]["panel_prob"] == 0.56 and x["stake_factor"] == 1.0        # board block untouched
    assert "nothing due" in VP.lineup_pass(now, out, led, keys=KEYS, get=get, post=post, record_path=root / "rec.json")
    single["result"], single["clv"] = "won", 2.0
    (led / "picks_2026-10-27.json").write_text(json.dumps({"singles": [single]}))
    assert VP.grade(out, led, root / "rec.json", now=now) == 2                  # board + line-up rows
    assert VP.grade(out, led, root / "rec.json", now=now) == 0                  # once each
    rec = json.loads((root / "rec.json").read_text())
    assert {r["stage"] for r in rec["history"]} == {"board", "lineup"}
    assert rec["history"][0]["live_prob"] == 0.64 and rec["history"][0]["clv"] == 2.0
