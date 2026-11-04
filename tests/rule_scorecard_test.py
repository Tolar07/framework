"""Rule scorecard (#258): per bot x rule x market CLV with a 90% band, position, proposals, BH cut."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import rule_scorecard as rs  # noqa: E402


def bet(bot, kind, day, res, odds, clv=None, key="SB:1|2.5|Over"):
    return {"bot": bot, "kind": kind, "date": day, "result": res, "odds": odds, "paper": False,
            "clv": clv, "legs": [{"key": key}]}


T = "2026-11-04"
assert rs.flat_return({"result": "won", "odds": 2.5}) == 1.5
assert rs.flat_return({"result": "lost", "odds": 2.5}) == -1.0
assert rs.flat_return({"result": "void", "odds": 2.5}) is None and rs.flat_return({"result": None}) is None

assert rs.mean_band([0.1] * 4)["lo"] is None                       # too few readings: no band
b = rs.mean_band([0.02, 0.04, 0.03, 0.05, 0.01, 0.03])
assert b["lo"] > 0 and b["lo"] < b["mean"] < b["hi"] and rs.verdict(b) == "working"
assert rs.verdict(rs.mean_band([-0.05, -0.04, -0.06, -0.05, -0.03])) == "not working"
assert rs.verdict(rs.mean_band([0.1, -0.1, 0.12, -0.11, 0.0])) == "undecided"
assert rs.verdict({"n": 0, "mean": None, "lo": None, "hi": None}) == "PENDING"   # missing reads PENDING, not 0

bad = [bet("sportybet", "rule EDGE", "2026-11-02", "lost", 2.0, clv=-0.05 + 0.002 * (i % 5)) for i in range(40)]
good = [bet("matchbook", "steam", "2026-11-03", "won", 2.0, clv=0.04 + 0.002 * (i % 5)) for i in range(40)]
none = [bet("betfair", "rule X", "2026-11-03", "won", 1.8) for _ in range(40)]
old = [bet("sportybet", "rule EDGE", "2026-09-01", "lost", 2.0, clv=-0.9)]
paper = [dict(bet("sportybet", "steam (paper)", "2026-11-03", "won", 2.0, clv=0.5), paper=True)]
rows = rs.scorecard(bad + good + none + old + paper, T)
by = {(r["bot"], r["rule"]): r for r in rows}
assert len(rows) == 3, "bets older than 30 d and paper bets are not scored"
assert by[("sportybet", "rule EDGE")]["verdict"] == "not working" and by[("sportybet", "rule EDGE")]["flat_return"] == -1.0
assert by[("matchbook", "steam")]["verdict"] == "working"
assert by[("betfair", "rule X")]["verdict"] == "PENDING" and by[("betfair", "rule X")]["clv"]["mean"] is None

props = rs.proposals(rows)
kinds = {(p["kind"], p["who"]) for p in props}
assert ("stop", "sportybet / rule EDGE") in kinds and ("grow", "matchbook / steam") in kinds
assert not any("betfair" in p["who"] for p in props), "no CLV recorded: nothing proposed"
assert all(p["ev"] > 0 and p["needs"] for p in props)
few = rs.proposals(rs.scorecard(bad[:12], T))
assert [p["kind"] for p in few] == ["shrink"], "under 30 bets a losing rule is only shrunk, not stopped"
assert "OK" in props[0]["line"] or "Needs" in props[0]["line"]
# CLV positive but the price taken loses: timing
t = [bet("matchbook", "steam", "2026-11-03", "lost" if i % 4 else "won", 2.0, clv=0.03 + 0.002 * (i % 5)) for i in range(40)]
assert "timing" in {p["kind"] for p in rs.proposals(rs.scorecard(t, T))}
# a market bet by one bot only that works: test-market
assert "test-market" in {p["kind"] for p in rs.proposals(rs.scorecard(good, T))}

pos = rs.position(bad + good + none, T, [{"loop": "x", "ok": False}, {"loop": "y", "ok": True}])
assert pos["working"] and pos["not_working"] and pos["no_clv_yet"] == 1 and pos["stalled_loops"] == ["x"]
assert set(pos["bots"]["sportybet"]) == {"7d", "30d"}

# Benjamini-Hochberg: classic example
p = {"a": 0.001, "b": 0.008, "c": 0.039, "d": 0.041, "e": 0.6}
assert rs.bh_cut(p, 0.05) == {"a", "b"} and rs.bh_cut({"x": 0.2, "y": 0.5}, 0.1) == set()
assert rs.bh_cut({}) == set()
h = {"id": "H1", "result": "199 bets, hit 0.367, return +19.4% ± 14.1%; later half +28.5%, CLV +17.3%"}
assert abs(rs.hypothesis_z(h) - 19.4 / 14.1) < 1e-9
assert abs(rs.hypothesis_z({"result": "658 scored, gain +0.00380 ± 0.00165"}) - 0.0038 / 0.00165) < 1e-9
assert rs.hypothesis_z({"result": "0 bets, hit PENDING, return +0.0% ± 0.0%"}) is None
m = rs.multiplicity([h, {"id": "H3", "result": "x gain +0.0038 ± 0.00165"}],
                    {"formation": {"train_z": 2.18}, "weak": {"train_z": 1.0}, "n": 3})
assert m["tested"] == 4 and set(m["pass"]) | set(m["fail"]) == {"research H1", "research H3", "tactics formation", "tactics weak"}
assert "tactics weak" in m["fail"]

card = rs.build(bad + good, T, hypotheses=[h])
assert card["report_line"].startswith("Rule scorecard:") and "money" not in str(card)
assert rs.report_line([]).endswith("(PENDING).")
tmp = Path(__file__).parent / "_scorecard_tmp.json"
try:
    rs.save(card, tmp)
    assert rs.load(tmp)["rows"] == card["rows"]
finally:
    tmp.unlink(missing_ok=True)
assert rs.load(Path("nope.json")) == {}

from scripts import self_improve as si  # noqa: E402

pend = si.position([], {})
assert pend["status"] == "PENDING"
pos2 = si.position([{"loop": "a", "ok": False}], card)
assert pos2["stalled_loops"] == ["a"] and pos2["proposals"]
md = si.render([], [], [], T, pos2)
assert "## (d) Where am I" in md and "False-discovery cut" in md and "STOP sportybet / rule EDGE" in md
assert "PENDING" in si.render([], [], [], T, pend)
print("rule scorecard OK")
