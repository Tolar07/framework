"""Kickoff-cohort accas (engine/cohorts.py, Architect 2026-10-26). Offline.

A simulated 57-fixture day from 12:00 to 00:00 UK: no acca's legs are more than
30 minutes apart (a merged sparse window: its next window starts at most 60
minutes later), a sparse window with no window within 60 minutes stays singles,
and a 14:45 leg never shares a slip with a 20:00 leg."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import cohorts
from engine import picks_ledger as pl
from output import produce_bet as pb

DAY = datetime(2026, 10, 27, tzinfo=timezone.utc)     # GMT: UK time == UTC
# (UK kickoff, games) — 57 fixtures from 12:00 to 23:45
SLOTS = [("12:00", 3), ("12:30", 2), ("13:00", 1), ("14:00", 6), ("14:45", 2), ("15:00", 10),
         ("16:30", 1), ("17:30", 5), ("18:40", 1), ("19:45", 8), ("20:00", 9), ("21:00", 4),
         ("22:00", 2), ("23:30", 1), ("23:45", 2)]
assert sum(n for _t, n in SLOTS) == 57


def fixture(i, hhmm, ko=True):
    h, m = map(int, hhmm.split(":"))
    p = 0.76 + (i * 7 % 17) / 100                       # 0.76 .. 0.92
    price = round(1.0 / p * (1.02 + (i % 5) / 100), 2)  # some legs above fair, some under
    key = ("OVER_1_5", "UNDER_3_5", "HOME", "DC_1X")[i % 4]
    alt = ("DC_X2", "BTTS_YES", "HOME", "OVER_1_5")[i % 4]
    return NS(fixture=f"H{i} v A{i} (La Liga)", best_market=f"pick {i}", best_market_key=key,
              best_model_prob=p, best_price=price, certainty=("HIGH", "MEDIUM", "LOW")[i % 3],
              kickoff_utc=(DAY + timedelta(hours=h, minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ") if ko else None,
              prob_source="model", team_news=None, sb_event_id=f"sr:match:{i}", sb_tid=None,
              btts_price=1.6, kickoff_date="2026-10-27",
              probs=NS(home_team=f"H{i}", away_team=f"A{i}", p_btts_yes=0.80),
              cand_pool=[(0.80, 0.03, alt, 0.80, 0.79, NS(price=1.30))])


board, i = [], 0
for hhmm, n in SLOTS:
    for _ in range(n):
        board.append(fixture(i, hhmm))
        i += 1
by_name = {b.fixture.split(" (")[0]: b for b in board}


def ko(leg):
    return cohorts.kickoff_dt(leg[0])


accas = pb._build_accas(board)
safe3 = pb._build_safe3(board)
alts = pb._build_alt_accas(board)
values = [s for s in pb._build_value(board) if s[0] == "Value acca"]
megas = pb._build_megas(board)
btts = pb._build_btts(board)
kinds = {"accas": accas, "safe3": safe3, "alts": alts, "value acca": values, "megas": megas, "btts": btts}
for kind in ("accas", "safe3", "alts", "megas", "btts"):
    assert kinds[kind], f"the simulated day builds {kind}"

spread, gap = cohorts.MAX_BUCKET_SPREAD_MINUTES, cohorts.MAX_FALLBACK_GAP_MINUTES
for kind, slips in kinds.items():
    for name, legs, _c in slips:
        f = pl._cohort(legs)
        assert f["cohort_id"] and f["cohort_id"].startswith("COHORT_20261027_"), (kind, name, f["cohort_id"])
        assert len(f["leg_detail"]) == len(legs) and all(d["sb_event_id"] and d["kickoff_utc"]
                                                       for d in f["leg_detail"]), "rebookable legs"
        if f["cohort_merged"]:
            assert f["spread_minutes"] <= gap + spread, (kind, name, f)
        else:
            assert f["spread_minutes"] <= spread, f"{kind} {name}: legs {f['spread_minutes']} min apart"

# a 14:45 leg never shares a slip with a 20:00 leg; nothing spans 3 hours
for kind, slips in kinds.items():
    for name, legs, _c in slips:
        assert max(map(ko, legs)) - min(map(ko, legs)) < timedelta(minutes=gap + spread + 1), (kind, name)

# SPARSE RULE: 18:40 is alone and 19:45 starts 65 min later -> it stays a single
lone = "H" + str([b.fixture for b in board].index(next(b.fixture for b in board
                  if b.kickoff_utc.endswith("18:40:00Z")))) + " v "
for kind, slips in kinds.items():
    assert not any(leg[0].fixture.startswith(lone) for _n, legs, _c in slips for leg in legs), \
        f"the lone 18:40 game is pushed into a later {kind} slip"

# the existing rules still hold inside each cohort
for name, legs, _c in accas:
    assert 2 <= len(legs) <= pb.TABLE3_MAX_LEGS and pb._acca_odds(legs) <= pb.TABLE3_ODDS_MAX + 1e-9, name
    assert all(leg[2] >= pb.ACCA_LEG_MIN for leg in legs), "75%+ legs only"
    assert sum(pb._leg_direction(l) == "under" for l in legs) <= 1, "acca mix (order 42)"
for name, legs, c in safe3:
    assert len(legs) == 3 and c >= pb.SAFE3_MIN_CHANCE and all(l[0].certainty != "LOW" for l in legs), name
held = [pb._canon_short(l[0].fixture) for k in ("accas", "safe3", "alts", "value acca")
        for _n, legs, _c in kinds[k] for l in legs]
assert len(held) == len(set(held)), "a match is in one acca at most (order 40)"
assert all(len(legs) <= pb.MEGA_MAX_LEGS for _n, legs, _c in megas)
assert pb._build_megas(board)[0][0] == "Mega 1"
value = lambda l: l[2] * l[0].best_price                                     # noqa: E731
assert [n for n, _l, _c in accas][0] == "Acca A" and value(accas[0][1][0]) == max(
    value(g[1][0]) for g in accas), "Acca A is still the best value"

# the ledger shape the live ticket monitor reads
s = pl._slip(*accas[0], "CODE1")
for k in ("cohort_id", "cohort_merged", "earliest_kickoff_utc", "latest_kickoff_utc",
          "spread_minutes", "leg_detail"):
    assert k in s, k
assert set(s["leg_detail"][0]) >= {"fixture", "kickoff_utc", "sb_event_id", "market", "sb_market",
                                   "pick", "price"}
a = pl._alt_slip(*alts[0], "CODE2")
assert a["cohort_id"] and a["leg_detail"][0]["market"] == alts[0][1][0][3], "alt legs carry their own market"

# combined codes only within one window
assert not cohorts.same_cohort(accas) and cohorts.same_cohort(accas[:1])

# --- buckets() unit checks ------------------------------------------------
def legs_at(*times):
    return [(fixture(100 + n, t), "p", 0.8) for n, t in enumerate(times)]


two = lambda b: len(b) >= 2                                                  # noqa: E731
b = cohorts.buckets(legs_at("14:45", "20:00", "20:10"), two)
assert [len(x[2]) for x in b] == [1, 2], "14:45 never joins 20:00"
b = cohorts.buckets(legs_at("14:00", "15:00", "15:20"), two)
assert [len(x[2]) for x in b] == [3] and b[0][1], "sparse window merges with one starting 60 min later"
assert b[0][0] == "COHORT_20261027_1400"
b = cohorts.buckets(legs_at("14:00", "15:01", "15:20"), two)
assert [len(x[2]) for x in b] == [1, 2], "61 min later: no merge, the 14:00 game stays a single"
b = cohorts.buckets(legs_at("14:00", "14:30", "14:31"), two)
assert [len(x[2]) for x in b] == [2, 1], "30 min earliest to latest, not 31"
b = cohorts.buckets(legs_at("14:00", "14:50", "15:40", "15:45"), two)
assert [len(x[2]) for x in b] == [2, 2], "a sparse window merges with the NEXT window only, once"
nk = [(fixture(200, "15:00", ko=False), "p", 0.9)] + legs_at("15:00", "15:05")
assert sum(len(x[2]) for x in cohorts.buckets(nk, two)) == 2, "no kickoff: stays a single"
b = cohorts.buckets(list(reversed(legs_at("15:00", "15:05", "15:10"))), two)
assert [l[0].kickoff_utc[11:16] for l in b[0][2]] == ["15:10", "15:05", "15:00"], "caller's ranking kept"

print(f"cohort accas: OK ({len(accas)} accas, {len(safe3)} 50+, {len(alts)} alt, "
      f"{len(megas)} megas, BTTS {len(btts[0][1])} legs)")
