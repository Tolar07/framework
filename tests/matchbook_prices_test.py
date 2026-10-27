"""data/matchbook_prices.py + backtest/matchbook_price_study.py, offline
(Architect 2026-10-16: integrate Matchbook fully; bet365 retired)."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import matchbook_price_study as st  # noqa: E402

from data import matchbook_prices as mbp  # noqa: E402


def r(name, back, hcp=None, amount=50):
    return {"name": name, "status": "open", "handicap": hcp,
            "prices": [{"side": "back", "decimal-odds": back, "available-amount": amount},
                       {"side": "lay", "decimal-odds": back + 0.05, "available-amount": amount}]}


def mk(name, mtype, runners, hcp=None):
    return {"name": name, "market-type": mtype, "status": "open", "handicap": hcp, "runners": runners}


KO = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
FOOT = {"id": 1, "sport-id": 15, "name": "Everton vs Chelsea", "start": "2026-10-18T15:00:00.000Z", "markets": [
    mk("Match Odds", "one_x_two", [r("Everton", 3.25), r("Draw", 3.8), r("Chelsea", 2.3)]),
    mk("Total", "total", [r("OVER 2.5", 1.7, 2.5), r("UNDER 2.5", 2.38, 2.5)], 2.5),
    mk("Total", "total", [r("OVER 1.5", 1.23, 1.5), r("UNDER 1.5", 5.1, 1.5)], 1.5),
    mk("Home Team Total Goals", "total", [r("OVER 1.5", 2.6, 1.5), r("UNDER 1.5", 1.6, 1.5)], 1.5),
    mk("Both Teams To Score", "both_to_score", [r("Yes", 1.61), r("No", 2.58)]),
    mk("Double Chance", "other", [r("Everton or Draw", 1.75), r("Everton or Chelsea", 1.35),
                                  r("Draw or Chelsea", 1.43)])]}
NBA = {"id": 2, "sport-id": 4, "name": "Boston Celtics at Philadelphia 76ers", "start": "2026-10-18T23:30:00.000Z",
       "markets": [mk("Moneyline", "money_line", [r("Boston Celtics", 2.7), r("Philadelphia 76ers", 1.57)]),
                   mk("Handicap", "handicap", [r("Boston Celtics +5.5", 1.85, 5.5), r("Philadelphia 76ers -5.5", 2.02, -5.5),
                                               r("Boston Celtics +6.5", 1.75, 6.5), r("Philadelphia 76ers -6.5", 2.15, -6.5)]),
                   mk("Total", "total", [r("OVER 216.5", 1.9, 216.5), r("UNDER 216.5", 1.95, 216.5)], 216.5)]}

# names and matching
assert mbp.split_event("Boston Celtics at Philadelphia 76ers") == ("Philadelphia 76ers", "Boston Celtics")
assert mbp.alike("RC Deportivo de A Coruna", "Deportivo La Coruña") >= 0.5
row = {"sport": "football", "home": "Everton FC", "away": "Chelsea", "ko": "2026-10-18T15:10Z"}
assert mbp.match(row, [NBA, FOOT]) is FOOT
assert mbp.match({**row, "ko": "2026-10-18T16:00Z"}, [FOOT]) is None, "kick-off 1 h apart: not the game"
assert mbp.match({**row, "away": "Arsenal"}, [FOOT]) is None

# football quote: the universe's own market shape; the team total never passes for the match total
q = mbp.quote(FOOT, "football")
assert q == {"1x2": [3.25, 3.8, 2.3], "ou2.5": [1.7, 2.38], "ou1.5": [1.23, 5.1], "btts": [1.61, 2.58],
             "dc": [1.75, 1.35, 1.43]}, q
# basketball at SportyBet's own line only
qb = mbp.quote(NBA, "basketball", {"total": [216.5, 1.9, 1.9], "hcp": [-5.5, 1.9, 1.9]})
assert qb == {"win": [1.57, 2.7], "total": [216.5, 1.9, 1.95], "hcp": [-5.5, 2.02, 1.85]}, qb
assert "total" not in mbp.quote(NBA, "basketball", {"total": [218.5, 1.9, 1.9]}), "never a neighbouring line"

# NBA board lookups
pk = {"home": "Philadelphia 76ers", "away": "Boston Celtics", "tip": "2026-10-18T23:30:00+00:00"}
assert mbp.nba_back([NBA], {**pk, "market_id": "223", "specifier": "hcp=-5.5", "outcome": "Away (+5.5)"}) == 1.85
assert mbp.nba_back([NBA], {**pk, "market_id": "219", "specifier": "", "outcome": "Home"}) == 1.57
assert mbp.nba_back([NBA], {**pk, "market_id": "225", "specifier": "total=216.5", "outcome": "Under 216.5"}) == 1.95
assert mbp.nba_back([NBA], {**pk, "market_id": "227", "specifier": "total=111.5", "outcome": "Over 111.5"}) is None
# 1st-half totals (68): Matchbook's "1st Half Total" at SportyBet's own line (2026-10-21: the board
# said "not listed" while the bot was backing them)
H1 = {**NBA, "markets": NBA["markets"] + [mk("1st Half Total", "total", [r("OVER 112.5", 1.88, 112.5), r("UNDER 112.5", 1.9, 112.5),
                                                                         {"name": "OVER 114.5", "status": "open", "prices": []}], 112.5)]}
h1 = {**pk, "market_id": "68", "specifier": "total=112.5", "outcome": "Under 112.5"}
assert mbp.nba_back([H1], h1) == 1.9 and mbp.nba_listed([H1], h1)
assert mbp.nba_back([H1], {**h1, "specifier": "total=114.5", "outcome": "Over 114.5"}) is None
assert mbp.nba_listed([H1], {**h1, "specifier": "total=114.5", "outcome": "Over 114.5"}), "listed, no back price yet"
assert not mbp.nba_listed([H1], {**h1, "specifier": "total=116.5"}), "never a neighbouring line"
assert not mbp.nba_listed([NBA], h1)

# attach: only games not started; first kept, last replaced
pending = {"a": {**row, "last": {"p": {"1x2": [3.1, 3.7, 2.2]}}},
           "b": {**row, "ko": "2026-10-10T15:00Z", "last": {"p": {}}}}
note = mbp.attach(pending, KO - timedelta(hours=5), [FOOT])
assert note == "Matchbook: 1 events, 1 games matched, 1 priced", note
assert pending["a"]["mb_first"] == pending["a"]["mb_last"] and "mb_last" not in pending["b"]
assert mbp.attach(pending, KO, get=lambda u: (_ for _ in ()).throw(RuntimeError("down"))).startswith("Matchbook unavailable")

# the study: coverage, both-book returns, mismatches (SportyBet above Matchbook's fair)
graded = [{"sport": "football", "ko": "2026-10-18T15:00Z", "home": "Everton", "away": "Chelsea",
           "last": {"p": {"1x2": [3.6, 3.7, 2.2], "1up": [2.0, 3.7, 1.5], "btts": [1.6, 2.4]}},
           "mb_last": {"p": {"1x2": [3.25, 3.8, 2.3], "btts": [1.61, 2.58]}},
           "result": {"h": 2, "a": 1, "ht": [1, 0]}},
          {"sport": "football", "ko": "2026-10-18T15:00Z", "last": {"p": {"1x2": [2.0, 3.0, 4.0]}},
           "result": {"h": 0, "a": 0, "ht": [0, 0]}}]
games, missing = st.coverage(graded)
assert games["football"] == [2, 1] and missing["football 1up"] == [1, 0] and missing["football 1x2"] == [1, 1]
fam = st.compare(graded)
assert fam["football 1x2"]["n"] == 3 and fam["football btts"]["n"] == 2, dict(fam)
assert fam["football 1x2"]["mis_ret"] == [2.6], fam["football 1x2"]       # home 3.6 v Matchbook fair ~3.4: won
assert st.rows_since([{"ko": "2026-10-15T20:00Z"}]) == []
out = ROOT / "backtest" / "_mb_study_test.md"
text = st.write(graded, out)
out.unlink()
assert "## 3. Mismatches" in text and "| football 1x2 | 1 | 100% |" in text, text
print("matchbook prices + study: OK")
