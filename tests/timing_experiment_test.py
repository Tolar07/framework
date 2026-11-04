"""Timing experiment (#259): Matchbook early v Betfair late on the same picks, judged by CLV."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import timing_experiment as tx  # noqa: E402

KO = "2026-11-04T20:00:00.000Z"


def bet(bot, odds, placed, home="RC Lens", away="Como", key="SB:10||Home or Away", clv=None, paper=False):
    return {"bot": bot, "date": "2026-11-04", "odds": odds, "placed_at": placed, "clv": clv, "paper": paper,
            "legs": [{"home": home, "away": away, "ko": KO, "key": key}]}


mb = bet("matchbook", 1.31, "2026-11-04T09:00:00+00:00", clv=0.0)           # close = 1.31
bf = bet("betfair", 1.28, "2026-11-04T17:00:00Z")
r = tx.row(mb, bf)
assert r["early_hours"] == 11.0 and r["late_hours"] == 3.0
assert r["early_clv"] == 0.0 and r["late_clv"] == round(1.28 / 1.31 - 1, 4)
assert r["clv_diff"] > 0, "early beat late here"

assert tx.row(bet("matchbook", 1.31, None), bf)["clv_diff"] is None        # no close: PENDING, not 0
assert tx.row(bet("matchbook", 1.31, None, clv="x"), bf)["early_clv"] is None

# pairing: same key + day + teams; paper, other fixtures, other selections and other bots never pair
other = bet("betfair", 2.0, "2026-11-04T17:00:00Z", home="Ajax", away="PSV")
other_key = bet("betfair", 2.0, "2026-11-04T17:00:00Z", key="SB:1||Home")
paper = bet("betfair", 1.3, "2026-11-04T17:00:00Z", paper=True)
assert tx.pairs([mb, other, other_key, paper]) == []
assert tx.pairs([mb, bf, dict(bf)]) == [(mb, bf)], "one Matchbook bet pairs once"
assert len(tx.pairs([mb, dict(mb), bf, dict(bf)])) == 2
assert tx.pairs([bet("sportybet", 1.3, None), bf]) == []

# empty input reads PENDING, no proposal
doc = tx.build([], "2026-11-04")
assert doc["pairs"] == 0 and doc["verdict"] == "PENDING" and doc["proposal"] is None
assert "PENDING" in doc["report_line"]


def pair_set(n, wiggle):
    bets = []
    for i in range(n):
        d = 0.02 + wiggle * ((i % 5) - 2)
        bets.append(bet("matchbook", 1.30, "2026-11-04T09:00:00Z", home=f"Home {i}", away=f"Away {i}", clv=d))
        bets.append(bet("betfair", 1.30 / (1 + d) / 1.02, "2026-11-04T17:00:00Z", home=f"Home {i}", away=f"Away {i}"))
    return bets


# a proposal needs n >= 100 AND a band that excludes 0
big = tx.build(pair_set(100, 0.002), "2026-11-04")
assert big["pairs"] == 100 and big["verdict"] == "early better"
assert big["proposal"] and big["proposal"]["kind"] == "timing" and "Architect" in big["proposal"]["needs"]
small = tx.build(pair_set(99, 0.002), "2026-11-04")
assert small["verdict"] == "early better" and small["proposal"] is None, "under 100 pairs: no proposal"
noisy = tx.build(pair_set(100, 0.5), "2026-11-04")
assert noisy["proposal"] is None, "band spanning 0: no proposal"

# public repo: only ratios, hours and prices are written; no stake, money or id
assert set(big["rows"][0]) == {"date", "early_hours", "late_hours", "early_price", "late_price",
                               "early_clv", "late_clv", "clv_diff"}

print("timing_experiment_test OK")
