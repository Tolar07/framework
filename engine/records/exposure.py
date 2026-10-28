"""
EXPOSURE — to-do #7 idea 5 (RECORDED ONLY). Correlation and concentration of one night's board.

single["exposure"] = {"league_n", "league_rank", "over_cap", "same_match"}
    league_rank     the pick's place among that league's singles by chance (1 = most likely)
    over_cap        league_rank > LEAGUE_CAP — the cap backtest/REASONING_IDEAS_STUDY.md chose on
                    its earlier half (4 a league a day: later half inside -1.6%, past it -13.1%)
doc["exposure"] = {"singles", "stake_pct", "leagues": {league: n}, "accas": [...]}
    accas[i]        legs, legs sharing a league (pairs) and a fixture, and the joint chance under
                    the measured same-league residual covariance (+0.0073 per pair) vs independence
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from engine.records._common import num, singles

LEAGUE_CAP = 4
PAIR_COV = 0.0073          # same league, same day residual covariance (REASONING_IDEAS_STUDY.md)


def annotate_doc(doc: dict, target: str) -> str:
    board = list(doc.get("singles") or [])
    by_league: dict[str, list[dict]] = defaultdict(list)
    by_fixture: dict[str, int] = defaultdict(int)
    for s in board:
        by_league[str(s.get("league") or "?")].append(s)
        by_fixture[str(s.get("fixture") or "?")] += 1
    for league, ss in by_league.items():
        for rank, s in enumerate(sorted(ss, key=lambda x: -(num(x.get("chance")) or 0)), 1):
            s["exposure"] = {"league": league, "league_n": len(ss), "league_rank": rank,
                             "over_cap": rank > LEAGUE_CAP,
                             "same_match": by_fixture[str(s.get("fixture") or "?")] - 1}
    league_of = {str(x.get("fixture")): str(x.get("league") or "?")
                 for x in [*singles(doc), *(doc.get("rated") or [])] if isinstance(x, dict)}
    accas = []
    for slot in ("accas", "safe3", "megas", "clv_accas"):
        for a in doc.get(slot) or []:
            legs = [str(x) for x in a.get("legs") or []] if isinstance(a, dict) else []
            if len(legs) < 2:
                continue
            pairs = [(league_of.get(x), league_of.get(y)) for x, y in combinations(legs, 2)]
            same_league = sum(1 for p, q in pairs if p and p == q)
            same_match = sum(1 for x, y in combinations(legs, 2) if x == y)
            chance = num(a.get("chance"))
            accas.append({"slot": slot, "name": a.get("name"), "legs": len(legs),
                          "same_league_pairs": same_league, "same_match_pairs": same_match,
                          "unknown_league_legs": sum(1 for x in legs if x not in league_of),
                          "chance_indep": chance,
                          "chance_corr": None if chance is None else round(chance + same_league * PAIR_COV, 4)})
    doc["exposure"] = {"singles": len(board), "league_cap": LEAGUE_CAP,
                       "over_cap": sum(1 for s in board if s.get("exposure", {}).get("over_cap")),
                       "stake_pct": round(sum(num(s.get("stake_pct")) or 0 for s in board), 3),
                       "leagues": {k: len(v) for k, v in sorted(by_league.items(), key=lambda kv: -len(kv[1]))},
                       "accas": accas}
    return f"exposure {len(board)} singles, {len(accas)} slips"
