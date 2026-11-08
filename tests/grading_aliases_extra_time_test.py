"""
Grade everything (order 53). On 8 Nov 2026 the 7 Nov board still had two
singles, three BTTS slips, two value picks and three accas open after the
morning run:

  * 'Paderborn v Ein Frankfurt' and 'Paris SG v Troyes': football-data /
    SportyBet spellings that Flashscore ('Eintracht Frankfurt', 'PSG') and
    FotMob ('Paris Saint-Germain') write differently, scored 0.81 / 0.55, under
    the 0.85 bar. The same names (and "M'gladbach", 'Kuopion Palloseura') kept
    picks of 24 Oct - 6 Nov ungraded. Fixed by explicit aliases, not a looser
    matcher.
  * Two FA Cup ties that went to extra time (Hornchurch v Blackpool aet,
    Altrincham v Notts County on penalties) read "no 90-min result" for ever,
    holding two accas open, although the feed carries the 90-minute score
    (AT/AU): 1-1 and 2-2 (BBC: Hornchurch v Blackpool 1-1 after 90).
  * A postponed game (stage 4, no score) read "no 90-min result" too, and would
    tie with its replayed fixture; it now stays pending until it is played.

The feed rows below are the real 7 Nov Flashscore blocks, trimmed.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import flashscore_results as fs
from engine import picks_ledger as pl

S, E = "¬", "÷"     # the feed's field and key/value separators


def block(**kv):
    return S.join(f"{k}{E}{v}" for k, v in kv.items())


FEED = "~".join([
    block(ZA="GERMANY: Bundesliga"),
    block(AA="4jZfvCEN", AD=1794061800, AB=3, AC=3, AE="Paderborn", AF="Eintracht Frankfurt",
          AG=2, AT=2, BC=1, AH=2, AU=2, BD=1),
    block(ZA="FRANCE: Ligue 1"),
    block(AA="x1", AD=1794081900, AB=3, AC=3, AE="PSG", AF="Troyes", AG=1, AT=1, BC=0, AH=0, AU=0, BD=0),
    block(AA="x2", AD=1794074400, AB=3, AC=3, AE="Auxerre", AF="Paris FC", AG=0, AT=0, BC=0, AH=1, AU=1, BD=1),
    block(ZA="ENGLAND: FA Cup"),
    block(AA="jD0Xf8a4", AD=1794063600, AB=3, AC=10, AE="Hornchurch", AF="Blackpool",
          AG=1, AT=1, BC=0, AH=2, AU=1, BD=1),
    block(AA="WYr2Jnh5", AD=1794072600, AB=3, AC=11, AE="Altrincham", AF="Notts County",
          AG=2, AT=2, BC=1, RPA=2, AH=3, AU=2, BD=1, RPB=3),
    block(ZA="PORTUGAL: Liga Portugal"),
    block(AA="pp", AD=1794065400, AB=3, AC=4, AE="Nacional", AF="Academico Viseu"),   # postponed
])
EVENTS = fs.parse_feed(FEED)
ev = {e["home"]: e for e in EVENTS}

# the 90-minute score and the half-time after extra time
assert (ev["Hornchurch"]["ft90_home"], ev["Hornchurch"]["ft90_away"]) == (1, 1)
assert (ev["Hornchurch"]["fh_home"], ev["Hornchurch"]["fh_away"]) == (1, 0)       # BBC: 1-0 at HT
assert (ev["Altrincham"]["ft90_home"], ev["Altrincham"]["ft90_away"]) == (2, 2)
assert (ev["Paderborn"]["ft90_home"], ev["Paderborn"]["ft90_away"]) == (2, 2)
assert ev["Hornchurch"]["finished_other"] and not ev["Hornchurch"]["finished_regular"]
# postponed: neither finished, and never chosen as the match
assert not ev["Nacional"]["finished_other"] and not ev["Nacional"]["finished_regular"]
assert fs.find_result(EVENTS, "Nacional", "Academico de Viseu FC", "2026-11-07") is None

# a pens game whose AT/AU is missing or above the final gives no 90-minute score
bad = fs.parse_feed(block(ZA="X") + "~" + block(AA="b", AD=1794072600, AB=3, AC=11, AE="A", AF="B",
                                                AG=1, AH=0, AT=2, AU=0))
assert bad[0]["ft90_home"] is None and bad[0]["finished_other"]

# explicit aliases: exact matches, and nothing looser
for ours, theirs in [("Ein Frankfurt", "Eintracht Frankfurt"), ("Paris SG", "PSG"),
                     ("Paris SG", "Paris Saint-Germain"), ("M'gladbach", "B. Monchengladbach"),
                     ("M'gladbach", "Borussia Mönchengladbach"), ("Kuopion Palloseura", "KuPS"),
                     ("Halide Edip Adivarspor", "Beyoğlu Yeni Çarşı Futbol Kulubu"),
                     ("Eskisehir Anadolu Spor Faaliyetleri AS", "Anadolu Üniversitesi")]:
    assert fs._sim(ours, theirs) == 1.0, (ours, theirs)
assert fs.find_result(EVENTS, "Paris SG", "Troyes", "2026-11-07")["home"] == "PSG"
assert fs._sim("Ein Frankfurt", "FSV Frankfurt") < fs.MATCH_MIN
assert fs._sim("M'gladbach", "Bergisch Gladbach") < fs.MATCH_MIN


def single(home, away, market):
    return {"fixture": f"{home} v {away}", "home": home, "away": away, "market": market,
            "kickoff": "2026-11-07", "fotmob_id": None, "result": None}


with tempfile.TemporaryDirectory() as tmp:
    pl.LEDGER_DIR, pl.SUPERSEDED_DIR = Path(tmp), Path(tmp) / "superseded"
    doc = {"date": "2026-11-07", "singles": [
        single("Paderborn", "Ein Frankfurt", "SB:10||Home or Away"),
        single("Paris SG", "Troyes", "SB:37|total=4.5|Home & Under 4.5"),
        single("AFC Hornchurch", "Blackpool FC", "SB:10||Home or Away"),
        dict(single("Altrincham FC", "Notts County", "SB:10||Home or Away"), result="no-90min-result"),
        dict(single("Nacional", "Academico de Viseu FC", "SB:10||Home or Away"), result="no-90min-result"),
    ], "accas": [
        {"name": "Acca R", "legs": ["AFC Hornchurch v Blackpool FC", "Paris SG v Troyes"], "result": None},
        {"name": "Acca C", "legs": ["Paderborn v Ein Frankfurt", "Nacional v Academico de Viseu FC"],
         "result": None},
    ], "btts": [{"name": "BTTS 50", "result": None, "alt_legs": [
        {"fixture": "Paderborn v Ein Frankfurt", "home": "Paderborn", "away": "Ein Frankfurt",
         "kickoff": "2026-11-07", "market": "BTTS_YES", "result": None}]}]}
    path = pl.LEDGER_DIR / "picks_2026-11-07.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    pl.grade_all(EVENTS, today="2026-11-08")
    out = json.loads(path.read_text(encoding="utf-8"))
    res = {s["fixture"]: (s["result"], s.get("ft")) for s in out["singles"]}
    assert res["Paderborn v Ein Frankfurt"] == ("lost", "2-2"), res          # a draw: 'Home or Away' loses
    assert res["Paris SG v Troyes"] == ("won", "1-0"), res
    assert res["AFC Hornchurch v Blackpool FC"] == ("lost", "1-1"), res       # level after 90
    assert res["Altrincham FC v Notts County"] == ("lost", "2-2"), res
    assert res["Nacional v Academico de Viseu FC"][0] == "no-90min-result", res  # untouched until played
    accas = {a["name"]: a["result"] for a in out["accas"]}
    assert accas == {"Acca R": "lost", "Acca C": "lost"}, accas
    assert out["btts"][0]["result"] == "won" and out["btts"][0]["alt_legs"][0]["ft"] == "2-2", out["btts"]

print("grading_aliases_extra_time_test: OK")
