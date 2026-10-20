"""Experiment engine (engine/experiments.py): shadow scoring, the promotion
test, the switch, the ledger record of dropped picks, and the board hook."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import experiments as X  # noqa: E402


def _single(fx: str, price: float, res: str, close: float | None, cert: str = "HIGH",
            market: str = "SB:1||Home", chance: float = 0.7) -> dict:
    return {"fixture": fx, "league": "L", "market": market, "price": price, "chance": chance,
            "closing_price": close, "result": res, "certainty": cert, "news_level": "OK"}


def _days(n_days: int, start: int = 20) -> list[dict]:
    """HIGH legs win at 1.60 and close shorter; LOW legs lose and drift."""
    out = []
    for k in range(n_days):
        day = f"2026-10-{start + k:02d}" if start + k <= 31 else f"2026-11-{start + k - 31:02d}"
        legs = []
        for i in range(12):
            hi = i % 2 == 0
            legs.append(X.leg(_single(f"{day}-{i}", 1.60,
                                      "won" if (hi and i != 10) or (not hi and i % 3 == 0) else "lost",
                                      1.50 if hi else 1.70, "HIGH" if hi else "LOW")))
        out.append({"day": day, "legs": legs, "slips": {"accas": [], "safe3": []}})
    return out


# ── leg shape and bets ───────────────────────────────────────────────────────
lg = X.leg(_single("A v B", 1.5, "won", 1.4, market="SB:10||Home or Away"))
assert lg["family"] == "Double chance" and lg["certainty"] == "HIGH"
b = X.single_bet(lg, "2026-10-20")
assert b is not None and b["won"] == 1 and abs(b["pnl"] - 0.5) < 1e-9 and abs(b["clv"] - (1.5 / 1.4 - 1)) < 1e-9
assert X.single_bet(X.leg(_single("A v B", 1.5, None, None)), "d") is None, "ungraded legs are not bets"
assert X.single_bet(X.leg(_single("A v B", 1.5, "no-90min-result", None)), "d") is None
assert X.band(1.25) == "<1.30" and X.band(1.99) == "1.75-2.00" and X.band(None) == "?"

slip = {"name": "Acca A", "odds": 2.5, "result": "won",
        "legs": [X.leg(_single("a", 1.5, "won", 1.4)), X.leg(_single("b", 1.6667, "won", 1.6667))]}
sb = X.slip_bet(slip, "d")
assert sb is not None and abs(sb["pnl"] - 1.5) < 1e-9 and abs(sb["clv"] - (1.5 * 1.6667 / (1.4 * 1.6667) - 1)) < 1e-9
slip["legs"][1]["close"] = None
assert X.slip_bet(slip, "d")["clv"] is None, "a slip's CLV needs every leg's close"

# ── registry: defaults, every rule unique, protected things untouched ────────
names = [s.name for s in X.strategies()]
assert len(names) == len(set(names)), "strategy names are unique"
for slot, d in X.DEFAULT.items():
    assert d in names and next(s for s in X.strategies() if s.name == d).slot == slot
assert all(not s.wireable for s in X.strategies() if s.universe), "paper rules are never wired"
assert all(not s.wireable for s in X.strategies() if "Gemini" in s.name), "Gemini runs after the board"
assert all(s.since == X.WRITTEN for s in X.strategies()
           if not s.universe and s.name not in X.DEFAULT.values() and s.extra.get("kind") != "killer"), \
    "board rules written today count from today"
assert (X.MIN_BETS, X.Z_BAR, X.COOLDOWN_DAYS) == (100, 1.645, 7)

# ── the promotion test ───────────────────────────────────────────────────────
good = [{"day": "d", "won": 1, "pnl": 0.3 if i % 5 else -1.0, "clv": 0.03} for i in range(150)]
bad = [{"day": "d", "won": 0, "pnl": -0.2 if i % 2 else 0.1, "clv": -0.02 + (i % 3) * 0.001} for i in range(150)]
ok, why, z = X.beats(good, bad)
assert ok and z["z_return"] >= X.Z_BAR and z["z_clv"] >= X.Z_BAR, why
assert not X.beats(good[:99], bad)[0], "needs 100 graded bets"
assert not X.beats(bad, good)[0]
noclv = [{**g, "clv": None} for g in good]
assert not X.beats(noclv, bad)[0], "no CLV, no promotion — both tests are required"
better_return_only = [{**g, "clv": -0.05} for g in good]
assert not X.beats(better_return_only, bad)[0], "return alone is not enough"

# ── evaluate: S1 (HIGH only) wins in shadow and is promoted after its window ─
os.environ.pop("OLP_EXPERIMENTS", None)
days = _days(20)
reg, events = X.evaluate(days, {}, X.load_registry(Path("/nonexistent")), "2026-11-09")
assert reg["live"]["singles"] == "S1 HIGH certainty only", reg["live"]
ev = [e for e in events if e["event"] == "promote"]
assert len(ev) == 1 and ev[0]["demoted"] == "S0 board singles" and ev[0]["n"] >= 100
assert "Stakes unchanged" in X.telegram_line(ev[0])
assert reg["standings"]["S0 board singles"]["status"] == "shadow"
# cool-down: the next day no further change in that slot
reg2, ev2 = X.evaluate(days, {}, reg, "2026-11-10")
assert not [e for e in ev2 if e["slot"] == "singles"]
# results before `since` are in-sample, never counted
early = X.evaluate(_days(20, start=1), {}, X.load_registry(Path("/nonexistent")), "2026-10-21")[0]
assert early["live"]["singles"] == "S0 board singles", "evidence before a rule was written can't promote it"
assert early["standings"]["S1 HIGH certainty only"]["counted"]["n"] < 100
assert early["standings"]["S1 HIGH certainty only"]["in_sample"]["n"] > 100

# switch off: scored, flagged, nothing swapped
os.environ["OLP_EXPERIMENTS"] = "off"
reg_off, ev_off = X.evaluate(days, {}, X.load_registry(Path("/nonexistent")), "2026-11-09")
assert reg_off["live"]["singles"] == "S0 board singles" and not [e for e in ev_off if e["event"] == "promote"]
assert X.live_rules(Path("/nonexistent")) == {}
os.environ.pop("OLP_EXPERIMENTS")

# a non-wireable qualifier is flagged once, never swapped in
uni = {"U:F1 short favourite": [{"day": "2026-10-20", "won": 1, "pnl": 0.4, "clv": 0.05 + (i % 3) * 0.01}
                                for i in range(200)]}
flat = [{"day": "2026-10-20", "legs": [X.leg(_single(f"x{i}", 1.6, "lost" if i % 2 else "won", 1.6,
                                                    cert="LOW")) for i in range(120)],
         "slips": {"accas": [], "safe3": []}}]
r3, e3 = X.evaluate(flat, uni, X.load_registry(Path("/nonexistent")), "2026-10-21")
assert r3["live"]["singles"] == "S0 board singles"
assert [e["event"] for e in e3 if e["strategy"] == "U:F1 short favourite"] == ["qualifies-not-wireable"]
assert not [e for e in X.evaluate(flat, uni, r3, "2026-10-22")[1] if e["strategy"] == "U:F1 short favourite"]

# ── save + live_rules round trip ─────────────────────────────────────────────
with tempfile.TemporaryDirectory() as d:
    p, log = Path(d) / "s.json", Path(d) / "log.jsonl"
    X.save(reg, events, p, log)
    assert json.loads(log.read_text().splitlines()[0])["strategy"] == "S1 HIGH certainty only"
    rules = X.live_rules(p)
    assert set(rules) == {"singles"} and rules["singles"].keep(X.leg(_single("a", 1.5, None, None)), {})
    assert not rules["singles"].keep(X.leg(_single("a", 1.5, None, None, cert="LOW")), {})
    assert "singles: S1 HIGH certainty only" in X.brief(reg)

# ── board hook: a slip rule drops whole slips, raw builds are untouched ──────
from output import produce_bet as pbt  # noqa: E402

groups = [("Acca A", [("bf1", "p", 0.8), ("bf2", "p", 0.8)], 0.64), ("Acca B", [("bf3", "p", 0.8)], 0.8)]
pbt.SLIP_RULES["accas"] = lambda bfs: "bf3" not in bfs
pbt.ENGINE_DROPPED.clear()
kept = pbt._engine_keep("accas", groups)
assert [g[0] for g in kept] == ["Acca A"] and list(pbt.ENGINE_DROPPED["accas"]) == ["Acca B"]
assert pbt._engine_keep("safe3", groups) == groups, "no rule, no change"
pbt.SLIP_RULES.clear()
pbt.ENGINE_DROPPED.clear()
assert pbt._build_accas([]) == [] and pbt._build_safe3([], raw=True) == []

# ── ledger: dropped singles and slips are graded, not counted as board picks ─
from engine import picks_ledger as PL  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    old = PL.LEDGER_DIR, PL.SUPERSEDED_DIR
    PL.LEDGER_DIR, PL.SUPERSEDED_DIR = Path(d), Path(d) / "superseded"
    base = {"home": "H", "away": "A", "kickoff": "2026-10-19", "market": "SB:1||Home", "price": 1.5,
            "result": None, "ft": None}
    doc = {"date": "2026-10-19", "singles": [{**base, "fixture": "H v A"}],
           "singles_dropped": [{**base, "fixture": "H2 v A2", "home": "H2", "away": "A2"}],
           "accas": [], "safe3": [],
           "accas_dropped": [{"name": "Acca B", "legs": ["H2 v A2"], "result": None}]}
    (Path(d) / "picks_2026-10-19.json").write_text(json.dumps(doc))
    import data.flashscore_results as fr  # noqa: E402
    real = fr.find_result
    fr.find_result = lambda _e, h, a, _d: {"finished_regular": True, "finished_other": False,
                                            "fthg": 2, "ftag": 0}
    try:
        flags = PL.grade_all([], today="2026-10-20")
    finally:
        fr.find_result = real
        PL.LEDGER_DIR, PL.SUPERSEDED_DIR = old
    out = json.loads((Path(d) / "picks_2026-10-19.json").read_text())
    assert out["singles_dropped"][0]["result"] == "won"
    assert out["accas_dropped"][0]["result"] == "won"
    assert "1 graded, 0 pending" in flags[0], flags

# ── research queue (memory/strategy_queue.jsonl): each id registered once, in shadow ─
with tempfile.TemporaryDirectory() as d:
    q = Path(d) / "q.jsonl"
    e = {"strategy_id": "research:H9", "kind": "shadow_strategy", "mode": "shadow", "idea": "test",
         "queued_at": "2026-10-20T09:00:00Z", "rule": {"market": "1x2:home", "price_min": 1.5}}
    q.write_text(json.dumps(e) + "\n" + json.dumps({**e, "idea": "dup"}) + "\nnot json\n")
    rr = X._research_rules(q)
    assert [r.name for r in rr] == ["R:research:H9"] and rr[0].desc == "research — test"
    assert rr[0].since == "2026-10-20" and not rr[0].wireable and rr[0].slot == "singles"
assert X.queued(Path("/nonexistent")) == []

print("experiment_engine_test: OK")
