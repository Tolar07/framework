"""Weekly self-improvement review (2026-10-28): inputs audited, loops checked, proposals ranked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import self_improve as si  # noqa: E402

inputs = si.audit_inputs()
names = {r["input"]: r for r in inputs}
for k in ("team strength", "xG for / against", "recent form", "head-to-head", "rest days / congestion",
          "travel distance", "lineups / injuries", "motivation / table", "referee", "weather", "market moves"):
    assert k in names, k
assert names["team strength"]["status"] == "LIVE"
assert all(r["status"] in si.GAP for r in inputs)
loops = [{"loop": "tactics lessons", "what": "x", "ok": False, "note": "0 tested"},
         {"loop": "match study", "what": "y", "ok": True, "note": "fine"}]
props = si.proposals([{"input": "referee", "why": "", "value": 2, "status": "MISSING", "where": [],
                       "evidence": []},
                      {"input": "h2h", "why": "", "value": 1, "status": "TESTED", "where": [],
                       "evidence": ["no gain"]}], loops)
assert props[0]["title"] == "Learning loop stalled: tactics lessons" and props[0]["ev"] == 10.0
assert [p["title"] for p in props if p["kind"] not in ("promote", "build")][1] == "Model input: referee (missing)"
assert all(p["ev"] > 0.3 for p in props), "a tested input with no gain and low value is not proposed"
md = si.render(inputs, loops, props, "2026-10-28")
assert "## (a)" in md and "## (b)" in md and "## (c)" in md and "stalled" in md
note = si.architect_note(None, {"loops": loops, "inputs": [{"input": "referee", "status": "MISSING"}],
                               "proposals": props})
assert "what do I need to do better" in note and "STALLED — tactics lessons" in note and "referee" in note
assert "1. Learning loop stalled: tactics lessons" in note
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as t:
    f = Path(t) / "n.txt"
    f.write_text("Built #210 and merged it.", encoding="utf-8")
    assert si.architect_note(f).endswith("Built #210 and merged it.")
wf = (Path(__file__).parent.parent / ".github" / "workflows" / "self_improve.yml").read_text(encoding="utf-8")
assert "gh pr merge" in wf and "WebSearch" in wf and "--telegram" in wf, "search, merge on green, tell the Architect"
print("self-improvement review: inputs audited, stalled loop ranked first, proposals by EV: OK")

# bot-training plan (2026-11-01): an earned loop becomes a promotion proposal, nothing is promoted
import json as _json  # noqa: E402
import tempfile as _tf  # noqa: E402
_root = Path(_tf.mkdtemp())
(_root / "memory").mkdir()
(_root / "memory" / "learned_weights.json").write_text(_json.dumps({"walk_forward": {
    "n": 90, "learned_brier": 0.16, "market_brier": 0.17, "beats_market": True}, "weights": {"bias": {"w": 0.2}}}))
(_root / "memory" / "fact_record.json").write_text(_json.dumps({"facts": {
    "rotation (-)": {"n": 40, "won_rate": 0.5, "market_rate": 0.6, "residual": -0.1, "trusted": True},
    "derby (0)": {"n": 40, "won_rate": 0.6, "market_rate": 0.6, "residual": 0.0, "trusted": True},
    "rest_edge (+)": {"n": 5, "won_rate": 1.0, "market_rate": 0.5, "residual": 0.5, "trusted": False}}}))
_pro = [p["title"] for p in si.promotions(_root)]
assert _pro == ["Promotion ready: learned weights beat the market out of sample",
                "Promotion ready: fact 'rotation (-)' moves results beyond the market"], _pro
assert si.promotions(Path(_tf.mkdtemp())) == []
