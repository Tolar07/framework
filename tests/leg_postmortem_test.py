"""Leg-level post-mortems (engine/leg_postmortem.py): legs resolved per slip
kind, classes, the killer test, no look-ahead, and the experiment-engine rule."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import experiments as X  # noqa: E402
from engine import leg_postmortem as LP  # noqa: E402


def _s(fx: str, res: str, chance: float = 0.8, league: str = "L", price: float = 1.25) -> dict:
    return {"fixture": fx, "league": league, "market": "SB:1||Home", "price": price, "chance": chance,
            "closing_price": None, "result": res, "certainty": "HIGH", "news_level": "OK"}


# ── slips_of: main slips join singles, alts carry their own legs, combined spans a kind
doc = {"date": "2026-10-19",
       "singles": [_s("a", "won"), _s("b", "lost", league="Bad")],
       "accas": [{"name": "Acca A", "legs": ["a", "b"], "result": "lost"}],
       "safe3": [], "megas": [],
       "alts": [{"name": "Alt A", "result": "won",
                 "alt_legs": [{"fixture": "c", "league": "L", "market": "SB:10||Home or Away",
                               "price": 1.3, "chance": 0.8, "result": "won"}]}],
       "combined": [{"name": "ACCAS MEGA", "of": "accas", "result": "lost"}]}
sl = LP.slips_of(doc, {("b", "SB:1||Home"): "veto"})
assert [s["kind"] for s in sl] == ["accas", "alts", "combined"]
assert [lg["fixture"] for lg in sl[0]["legs"]] == ["a", "b"] and sl[1]["legs"][0]["family"] == "Double chance"
assert len(sl[2]["legs"]) == 2, "a combined code holds every leg of its kind"
b = sl[0]["legs"][1]
assert set(LP.classes(b)) >= {"league=Bad", "band=<1.30", "certainty=HIGH", "news=OK", "gemini=veto"}

pm = LP.build(sl)
assert pm["slips_graded"] == 3 and pm["slips_lost"] == 2
assert pm["legs"] == 3, "a leg counts once however many slips hold it"
bad = pm["classes"]["league=Bad"]
assert bad["lost"] == 1 and bad["slips_killed"] == 2 and not bad["killer"], "needs 50+ legs"

# ── the killer test: 60 legs said 80% but lost half ─────────────────────────
many = [{"kind": "accas", "name": f"A{i}", "day": f"2026-10-{1 + i % 9:02d}", "result": "lost" if i % 2 else "won",
         "legs": [X.leg(_s(f"x{i}", "lost" if i % 2 else "won", league="Leaky"))]} for i in range(60)]
many += [{"kind": "accas", "name": f"G{i}", "day": "2026-10-05", "result": "won",
          "legs": [X.leg(_s(f"g{i}", "won", league="Solid"))]} for i in range(60)]
pm = LP.build(many)
assert "league=Leaky" in pm["killers"] and "league=Solid" not in pm["killers"], pm["killers"]
assert pm["classes"]["league=Leaky"]["z"] >= LP.Z_BAR
assert (LP.MIN_LEGS, LP.Z_BAR) == (50, 2.0)
# no look-ahead: before the evidence exists, nothing is a killer
assert LP.build(many, before="2026-10-02")["killers"] == []
# the gemini dimension is reported, never used by the rule
assert LP.rule_killers({"killers": ["gemini=veto", "league=Leaky"]}) == {"league=Leaky"}

# ── the strategy: drops a slip holding a killer-class leg, in shadow first ──
st = {s.name: s for s in LP.strategies()}
ak = st["AK accas: no slip-killer leg"]
assert ak.slot == "accas" and ak.wireable and ak.since == X.WRITTEN
assert "TK 50%+ accas: no slip-killer leg" in st
assert all(n in {s.name for s in X.strategies()} for n in st), "registered in the experiment engine"
leaky = X.leg(_s("z", None, league="Leaky"))
assert not ak.keep(leaky, {"killers": {"league=Leaky"}}) and ak.keep(leaky, {"killers": set()})
assert ak.keep(leaky, {}), "no post-mortem yet: nothing is avoided"

# ── save / context_now / reports ─────────────────────────────────────────────
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "pm.json"
    LP.save(pm, p)
    assert LP.context_now(p)["killers"] == {"league=Leaky"}
    assert json.loads(p.read_text())["slips_graded"] == len(many)
assert LP.context_now(Path("/nonexistent")) == {"killers": set()}
assert "1 killer class(es)" in LP.line(pm) and "league=Leaky" in LP.line(pm)
assert any("KILLER" in x for x in LP.section(pm))
assert LP.line({}) == "post-mortem: no graded slips yet"

# ── NBA combined slips (Architect 2026-10-20: NBA treated as football), kept apart ─
import json as _json  # noqa: E402
import tempfile as _tf  # noqa: E402
from pathlib import Path as _P  # noqa: E402


def _np(mid: str, res: str | None, stage: str = "regular") -> dict:
    return {"home": f"H{mid}", "away": "A", "market_id": mid, "specifier": "total=110.5", "outcome": "Under 110.5",
            "price": 1.95, "chance": 0.6, "ev": 0.1, "result": res, "close_value": 0.02, "stage": stage}


with _tf.TemporaryDirectory() as _d:
    _p = _P(_d)
    (_p / "nba_2026-10-21.json").write_text(_json.dumps({"date": "2026-10-21", "picks": [_np("68", "won"), _np("219", "lost")]}))
    (_p / "nba_2026-10-22.json").write_text(_json.dumps({"date": "2026-10-22", "picks": [_np("68", "won"), _np("225", "won")]}))
    (_p / "nba_2026-10-23.json").write_text(_json.dumps({"date": "2026-10-23", "picks": [_np("68", "won")]}))
    (_p / "nba_2026-10-24.json").write_text(_json.dumps({"date": "2026-10-24", "picks": [_np("68", "won"), _np("219", None)]}))
    (_p / "nba_2026-10-07.json").write_text(_json.dumps({"date": "2026-10-07", "picks": [_np("68", "won", "preseason"), _np("219", "won", "preseason")]}))
    (_p / "reasoning_nba_2026-10-21.json").write_text(_json.dumps({"picks": [
        {"fixture": "H68 v A", "market": "NBA:68|total=110.5|Under 110.5", "verdict": "back"}]}))
    ns = LP.nba_slips(_p, _p)
assert [(x["day"], x["result"]) for x in ns] == [("2026-10-21", "lost"), ("2026-10-22", "won"), ("2026-10-24", None)], \
    "a combined slip needs 2+ regular-season legs; pending until every leg is graded"
assert ns[0]["legs"][0]["family"] == "NBA 1st half total" and ns[0]["legs"][0]["league"] == "NBA"
assert ns[0]["legs"][0]["verdict"] == "back" and ns[1]["legs"][0]["verdict"] is None
npm = LP.build(ns)
assert npm["slips_graded"] == 2 and npm["slips_lost"] == 1
assert "family=NBA winner" in npm["classes"] and "league=NBA" in npm["classes"]
sec = LP.section({**pm, "nba": npm})
assert any(x.startswith("NBA combined slips: 1 of 2 lost") for x in sec)
assert not any("NBA" in c for c in LP.rule_killers({**pm, "nba": npm})), "NBA never feeds football's killer rule"

print("leg_postmortem_test: OK")
