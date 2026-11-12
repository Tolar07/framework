"""
engine/africa_paper.py: AFCON / CAF qualifiers and the CAF club cups are rated and graded ON PAPER ONLY.
Offline: a stub model, no network. Also checks nothing is written where a bot reads.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import africa_paper as ap  # noqa: E402

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
P = {"1x2": [1.45, 4.1, 7.5], "dc": [1.1, 1.22, 2.6], "ou1.5": [1.36, 3.0], "ou2.5": [2.1, 1.7],
     "ou3.5": [3.9, 1.24], "btts": [2.2, 1.62]}


def row(i, comp, home, away, ko="2026-11-12T16:00Z", p=P):
    return {"sport": "football", "id": f"sr:match:{i}", "country": "International", "comp": comp, "ko": ko,
            "home": home, "away": away, "last": {"p": p}}


# which games are followed
assert ap.kind_of(row(1, "Africa Cup of Nations, Qualification, Group C", "A", "B")) == "national"
assert ap.kind_of(row(1, "FIFA World Cup, Qualification, CAF", "A", "B")) == "national"
assert ap.kind_of(row(1, "CAF Champions League", "A", "B")) == "club"
assert ap.kind_of(row(1, "CAF Confederations Cup", "A", "B")) == "club"
assert ap.kind_of(row(1, "CAF Champions League, Women", "A", "B")) is None
assert ap.kind_of(row(1, "CAF Olympic Qualification, Women", "A", "B")) is None
assert ap.kind_of(row(1, "UEFA Nations League", "A", "B")) is None, "the Nations League stays on the real board"
assert ap.kind_of(row(1, "Premiership", "A", "B")) is None

# names: SportyBet's spelling -> the dataset's, never a guess
model = SimpleNamespace(n={"Nigeria": 300, "Benin": 200, "Ivory Coast": 300, "DR Congo": 250, "Tiny": 3})
known = ap.known_teams(model)
assert ap.team_name("Cote d'Ivoire", known) == "Ivory Coast" and ap.team_name("Congo DR", known) == "DR Congo"
assert ap.team_name("Tiny", known) is None and ap.team_name("Narnia", known) is None


def predict(_m, h, a):
    return SimpleNamespace(p_home=0.72, p_draw=0.18, p_away=0.10, p_over_15=0.80, p_over_25=0.60, p_over_35=0.35,
                           p_btts_yes=0.40, lambda_home=2.2, lambda_away=0.6)


# a national game both sides of which the ratings know: a MODEL pick, anchored on the market
pk = ap.make_pick(row(1, "Africa Cup of Nations, Qualification, Group C", "Nigeria", "Benin"), model, known, predict)
assert pk["kind"] == "model" and pk["paper"] is True and ap.PRICE_MIN <= pk["price"] <= ap.PRICE_MAX
assert abs(pk["chance"] - (pk["market"] + ap.MODEL_WEIGHT * (pk["model"] - pk["market"]))) < 1e-3
assert pk["value"] == (pk["edge"] > 0) and "code" not in pk
# an unknown side, or a club cup: the bookmaker's favourite line, marked market, never "value"
mk = ap.make_pick(row(2, "Africa Cup of Nations, Qualification, Group D", "Narnia", "Benin"), model, known, predict)
assert mk["kind"] == "market" and mk["value"] is False and mk["price"] <= ap.SAFE_MAX
cl = ap.make_pick(row(3, "CAF Champions League", "Al Ahly", "Simba"), model, known, predict)
assert cl["kind"] == "market" and "club" in cl["why_market"]
assert ap.make_pick(row(4, "CAF Champions League", "A", "B", p={"1x2": [2.6, 3.0, 2.7]}), model, known, predict) is None

# settle rules
assert ap.settle("12", 1, 0) and not ap.settle("12", 1, 1) and ap.settle("O2.5", 2, 1) and ap.settle("U2.5", 1, 1)
assert ap.settle("BY", 1, 1) and ap.settle("BN", 2, 0) and ap.settle("1X", 0, 0) and not ap.settle("2", 0, 0)

# the book: picked once before kick-off, frozen, graded from the sweep's result
book: dict = {}
rows = [row(1, "Africa Cup of Nations, Qualification, Group C", "Nigeria", "Benin"),
        row(3, "CAF Champions League", "Al Ahly", "Simba"),
        row(5, "CAF Champions League", "Late", "Game", ko="2026-11-12T09:00Z"),      # already kicked off
        row(6, "Premiership", "X", "Y")]
assert ap.add_picks(book, rows, NOW, model, predict) == 2 and set(book) == {"sr:match:1", "sr:match:3"}
first = dict(book["sr:match:1"])
rows[0]["last"]["p"] = {**P, "1x2": [1.2, 5.0, 9.0]}
assert ap.add_picks(book, rows, NOW, model, predict) == 0 and book["sr:match:1"] == first, "never re-picked"
assert ap.grade(book, [{"id": "sr:match:1", "result": {"h": 3, "a": 0}}, {"id": "sr:match:9", "result": {"h": 1, "a": 0}}]) == 1
b = book["sr:match:1"]
assert b["result"] in ("won", "lost") and b["ft"] == "3-0" and (b["pnl"] == -1.0 or b["pnl"] == round(b["price"] - 1, 4))
rec = ap.record(book)
assert rec["all"]["picks"] == 2 and rec["all"]["graded"] == 1 and rec["all"].get("ready") is False

# files: only under data/africa_paper and output/africa_paper, never where a bot reads
with tempfile.TemporaryDirectory() as d:
    days = ap.write(book, NOW, Path(d) / "data" / "africa_paper" / "book.json", Path(d) / "output" / "africa_paper")
    assert days == ["2026-11-12"]
    doc = json.loads((Path(d) / "output" / "africa_paper" / "africa_2026-11-12.json").read_text(encoding="utf-8"))
    assert doc["paper"] is True and len(doc["picks"]) == 2 and all(p["paper"] for p in doc["picks"])
src = (ROOT / "engine" / "africa_paper.py").read_text(encoding="utf-8")
assert 'ROOT / "output" / "africa_paper"' in src and 'ROOT / "data" / "africa_paper"' in src
code = src.split('"""', 2)[2]
assert "multisport" not in code and "picks_" not in code and "share" not in code.lower().replace("shared", "")
sweep = (ROOT / "monitor" / "universe_sweep.py").read_text(encoding="utf-8")
assert "africa_paper.attach(pending, graded, now)" in sweep and '"output/africa_paper"' in sweep
print("africa_paper_test: ok")
