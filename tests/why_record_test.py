"""
Why record + why-weighted learning shadow (2026-10-28).

1. Classes: RIGHT-WON / LUCKY-WON / RIGHT-UNLUCKY / OUTPLAYED / GAME-CHANGED,
   UNCLASSED when the match is not studied or the market isn't settled on goals.
2. deserved(): the pick's chance on a Poisson grid of the actual xG.
3. The shadow blends outcomes with deserved; it is judged walk-forward and
   promoted only past MIN_DAYS / MIN_PICKS / z 1.645.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import learning  # noqa: E402
from engine import why_learning as wl  # noqa: E402
from engine import why_record as wr  # noqa: E402


def team(name, goals, xg, reds=(), trail=0.0, lvl=(30.0, 0.5, 0.4), shots=10):
    return {"id": hash(name) % 1000, "name": name, "goals": goals, "xg": xg, "reds": list(reds),
            "shots": shots, "sot": 4, "big_chances": 1,
            "state": {"level": {"min": lvl[0], "xg_for": lvl[1], "xg_against": lvl[2]},
                      "trailing": {"min": trail, "xg_for": 0.0, "xg_against": 0.0},
                      "leading": {"min": 0.0, "xg_for": 0.0, "xg_against": 0.0}}}


def row(fid, h, a):
    return {"fotmob_id": fid, "ko": "2026-10-20T15:00", "league": "L", "home": h, "away": a}


def single(fid, market, result, ft, chance=0.7, **kw):
    s = {"fixture": f"H{fid} v A{fid}", "home": f"H{fid}", "away": f"A{fid}", "kickoff": "2026-10-20",
         "league": "L", "market": market, "pick": market, "price": 1.5, "chance": chance,
         "result": result, "ft": ft, "fotmob_id": fid}
    s.update(kw)
    return s


assert wr.deserved("1X2_HOME", 3.0, 0.3) > 0.85 and wr.deserved("1X2_AWAY", 3.0, 0.3) < 0.1
assert wr.deserved("OVER_2_5", 0.2, 0.2) < 0.05
assert wr.deserved("SB:18|total=1.5|Over 1.5", 2.0, 2.0) > 0.85
print("deserved(): the pick's chance on the actual xG: OK")

c = wr.classify(single(1, "1X2_HOME", "won", "2-0"), row(1, team("H", 2, 2.4), team("A", 0, 0.4)))
assert c["class"] == "RIGHT-WON" and c["side"] == "home", c
c = wr.classify(single(2, "1X2_HOME", "won", "1-0"), row(2, team("H", 1, 0.3), team("A", 0, 2.1)))
assert c["class"] == "LUCKY-WON", c
c = wr.classify(single(3, "1X2_HOME", "lost", "0-1"), row(3, team("H", 0, 2.6), team("A", 1, 0.4)))
assert c["class"] == "RIGHT-UNLUCKY", c
c = wr.classify(single(4, "1X2_HOME", "lost", "0-2"), row(4, team("H", 0, 0.4), team("A", 2, 2.2)))
assert c["class"] == "OUTPLAYED" and "xG" in c["evidence"][0], c
c = wr.classify(single(5, "1X2_HOME", "lost", "0-1"), row(5, team("H", 0, 0.5, reds=[20]), team("A", 1, 1.6)))
assert c["class"] == "GAME-CHANGED" and any("red card for H" in e for e in c["evidence"]), c
c = wr.classify(single(6, "1X2_HOME", "lost", "0-1"), row(6, team("H", 0, 0.5), team("A", 1, 1.6, reds=[20])))
assert c["class"] == "OUTPLAYED", "a red for the OTHER side doesn't excuse a home pick"
c = wr.classify(single(7, "1X2_HOME", "lost", "0-1"),
                row(7, team("H", 0, 0.9, trail=75, lvl=(15.0, 0.3, 0.1)), team("A", 1, 1.4)))
assert c["class"] == "GAME-CHANGED" and any("behind early" in e for e in c["evidence"]), c
c = wr.classify(single(8, "1X2_HOME", "lost", "0-2", lineup_check={"level": "RISK", "note": "striker out"}),
                row(8, team("H", 0, 0.4), team("A", 2, 2.2)))
assert c["class"] == "GAME-CHANGED", c
assert wr.classify(single(9, "1X2_HOME", "lost", "0-1"), None)["class"] == "UNCLASSED"
c = wr.classify(single(10, "SB:166|total=9.5|Over 9.5", "lost", "3-0"), row(10, team("H", 3, 2.0), team("A", 0, 0.5)))
assert c["class"] == "UNCLASSED", "corners: the goals score can't settle it"
print("why classes: right-won, lucky-won, unlucky, outplayed, game-changed, unclassed: OK")

with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    (t / "picks").mkdir()
    (t / "study").mkdir()
    rows = [row(3, team("H3", 0, 2.6), team("A3", 1, 0.4)), row(4, team("H4", 0, 0.4), team("A4", 2, 2.2))]
    for r in rows:
        r["home"]["name"], r["away"]["name"] = r["home"]["name"], r["away"]["name"]
    (t / "study" / "2026-10.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    doc = {"date": "2026-10-20", "singles": [single(3, "1X2_HOME", "lost", "0-1"), single(4, "1X2_HOME", "lost", "0-2"),
                                            single(99, "1X2_HOME", None, "")]}
    (t / "picks" / "picks_2026-10-20.json").write_text(json.dumps(doc))
    out = wr.build(t / "picks", t / "study", t / "why.jsonl")
    assert [r["class"] for r in out] == ["RIGHT-UNLUCKY", "OUTPLAYED"], out
    assert len(wr.load(t / "why.jsonl")) == 2
    L = wr.summary_lines(out)
    assert L[0].startswith("🔎 WHY (2026-10-20") and "1 outplayed v 1 unlucky" in L[-1], L
    m = wl.why_map(out)
    assert m[("2026-10-20", "H3 v A3", "1X2_HOME")] > 0.5 > m[("2026-10-20", "H4 v A4", "1X2_HOME")]
print("why record built from the ledger + the debrief block: OK")

# the shadow's blend: an unlucky miss counts about half, an outplayed miss nearly in full
docs = [{"date": f"2026-09-{d:02d}", "singles": [
    {"fixture": f"F{d}-{i}", "market": "1X2_HOME", "league": "L", "chance": 0.7, "price": 1.4,
     "result": "lost" if i % 2 else "won", "kickoff": f"2026-09-{d:02d}"} for i in range(10)], "rated": []}
    for d in range(1, 21)]
why_un = {(x["date"], s["fixture"], s["market"]): 0.9 for x in docs for s in x["singles"]}
plain = learning.learn(None, today="2026-10-01", docs=docs)["family"]
blend = learning.learn(None, today="2026-10-01", why=why_un, docs=docs)["family"]
fam = learning.family("1X2_HOME")
assert blend[fam]["wins"] > plain[fam]["wins"], (plain, blend)
assert plain[fam]["shift"] < 0 and blend[fam]["shift"] >= plain[fam]["shift"]
print("why-weighted shadow: unlucky misses count less than outplayed ones: OK")

base = {"days": 40, "picks": 900, "z": 2.0, "evaluated_at": "2026-12-01"}
assert wl.decide(base)["status"] == "promoted"
assert wl.decide(dict(base, z=1.0))["status"] == "shadow"
assert wl.decide(dict(base, days=10))["status"] == "shadow", "too few days to judge"
assert wl.decide(dict(base, z=-2.0), {"status": "promoted"})["status"] == "shadow", "demoted"
assert wl.decide(dict(base, z=0.0), {"status": "promoted"})["status"] == "promoted"
print("shadow promoted only past 30 days / 300 picks / z 1.645, demoted when it falls behind: OK")
print("why_record_test: ALL OK")
