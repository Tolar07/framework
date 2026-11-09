"""monitor/settlement_audit.py: counts settled vs pending legs, the mislabel rate, PENDING when empty."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from monitor import settlement_audit as sa  # noqa: E402

tmp = Path(tempfile.mkdtemp())
g = tmp / "repo" / "graded"
g.mkdir(parents=True)


def leg(res, src):
    return {"event": "A v B", "key": "SB:1||Home", "result": res, "source": src}


(g / "2026-11-01.json").write_text(json.dumps({"bets": {
    "a": {"legs": [leg("won", "universe"), leg("lost", "sportybet (universe said won)"), leg(None, "no game found")]},
    "b": {"legs": [leg("void", "sportybet"), leg("won", "universe")]}}}))
(g / "paper_2026-11-01.json").write_text(json.dumps({"bets": {"p": {"legs": [leg("won", "universe")]}}}))

r = sa.audit_bot(g)
assert (r["legs"], r["settled"], r["pending"]) == (5, 4, 1), r
assert (r["won"], r["lost"], r["void"]) == (2, 1, 1), r
assert r["overruled_by_bookmaker"] == 1 and r["by_framework"] == 2 and r["by_bookmaker"] == 1, r
assert r["mislabel_rate"] == round(1 / 3, 4) and r["rejects_grader"] is True, r
assert r["paper_bets"] == 1, "paper counted apart, never in legs"
assert len(sa.settled_legs({"legs": [leg("won", "x"), leg(None, "y")]})) == 1
assert sa.audit_bot(tmp / "nope")["status"] == "PENDING", "missing data reads PENDING"
out = tmp / "o.json"
sa.save({"bot": r}, out)
assert json.loads(out.read_text())["bots"]["bot"]["settled"] == 4
print("settlement_audit_test OK")
