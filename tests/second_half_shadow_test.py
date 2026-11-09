"""Second-half stakes shadow (#494): late-season tag, record-only, PENDING when nothing is tagged."""
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import second_half_shadow as sh  # noqa: E402

assert sh.season_code("2026-11-09") == "2627" and sh.season_code("2027-03-01") == "2627"

teams = list("ABCDEFGHIJ")
rows, d = [], date(2026, 8, 10)
for rnd in range(2):                     # double round robin: all draws, except J loses every game (dead)
    for i, h in enumerate(teams):
        for j, a in enumerate(teams):
            if i != j and (i < j) == (rnd == 0):
                d += timedelta(days=1)
                hg, ag = (0, 2) if h == "J" else (2, 0) if a == "J" else (1, 1)
                odds = NS(home=NS(open=2.0, close=1.9), away=NS(open=3.0, close=3.1))
                rows.append(NS(date=d.isoformat(), home_team=h, away_team=a, fthg=hg, ftag=ag, odds=odds))


def load(lg, s):
    if lg != "Premier League":
        raise FileNotFoundError(lg)
    return rows, []


with tempfile.TemporaryDirectory() as tmp:
    day = (d + timedelta(days=1)).isoformat()
    Path(tmp, f"picks_{day}.json").write_text(json.dumps({"rated": [
        {"fixture": "A v J", "league": "Premier League", "home": "A", "away": "J"}]}), encoding="utf-8")
    card = sh.build(day, load=load, picks_dir=Path(tmp))
    assert card["summary"]["tagged"] >= 1, card["summary"]
    assert all(r["side"] in ("home", "away") for r in card["rows"])
    assert card["today"] == [{"fixture": "A v J", "league": "Premier League", "side": "home"}], card["today"]
    assert "record-only" in card["report_line"] and "Premier League" not in card["skipped"]
    assert len(card["skipped"]) == len(sh.LEAGUES) - 1
    early = sh.build("2026-08-20", load=load, picks_dir=Path(tmp))
    assert early["summary"]["tagged"] == 0 and "no tagged games yet" in early["report_line"]
print("second-half stakes shadow: late tags only, priced, record-only, PENDING early: OK")
