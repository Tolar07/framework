"""
STAT LISTS 7-21 - fifteen more statistics lists for the app, and the index the live list test picks from.

The Architect, 2026-11-12: "I need you to build 1 to 21 ... we are going to test it ... identify the teams and the
club that does what, pick one each from the list ... if it means expanding our coverage to some other leagues to
test it, yes." Lists 1-6 are framework #581-#584 (league profiles, first-half home scorers, steady corners, the
lower-league paper board). This module adds:

   7 ou_leagues        goals over 0.5 ... 4.5, by league             test: Over 2.5 in the league
   8 clean_sheets      clean sheets / failed to score, by team        test: BTTS No in the team's game
   9 second_half       second half busier than the first, by league   test: 1st half Under 1.5
  10 early_goal        a goal before the 30th minute, by league       test: 1st half Over 0.5
  11 comebacks         teams that avoid defeat after going behind     test: the team on double chance
  12 draws             draw-heavy teams (0-0 and 1-1 rates)           test: the draw in the team's game
  13 team_corners      most corners in a team's games, for + against  test: corners Over, SportyBet's main line
  14 cards             card-heavy teams                               test: bookings Over, main line
  15 fouls             most fouls in a team's games                   test: bookings Over, main line
  16 fh_corners        first-half corners, by team                    PENDING: no source keeps first-half corners yet
  17 shots_on_target   shots on target for + against, by team         test: Over 2.5 in the team's game
  18 luck              unlucky teams: goals well under their shots    test: the team to win
  19 us_totals         US sports: teams' record against the total     test: Over the main total (basketball)
  20 tennis            players' record against the closing price      PENDING: the sweep keeps no tennis price
  21 wb_totals         world basketball leagues against the total     test: Over the main total in the league

Football source: data/espn_matches (data/espn_history.py): every competition ESPN lists, this season only (a
league's latest season year), leagues with a match in the last ACTIVE_DAYS. A figure whose input is missing for a
match is left out of that match's count, never read as 0 (HR35).

Writes output/stat_lists/latest.json (the lists, ready for the app) and output/stat_lists/pick_index.json (per
list the ranked teams or leagues and each league's team names, for engine/list_picks.py).
RECORD ONLY: nothing here picks, stakes or blocks. Every earlier price test of such trends found no profit
(backtest/TREND_ATLAS_STUDY.md); the live list test is how each list earns or loses its place.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "stat_lists"
ACTIVE_DAYS = 40
LEAGUE_MIN = 30
TEAM_MIN = 8
ROWS = 30          # rows shown in the app
CANDS = 25         # ranked entries the live test may pick from
_SKIP = ("friendly", "friendlies")
# competitions that are not a league table: cup rounds, group phases, qualifiers (kept in the team lists)
_CUP = re.compile(r"cup|copa|coupe|coppa|pokal|beker|trophy|troph|shield|round|group|qualif|playoff|play-off|"
                  r"final|wwcq|wcq|ncaa|supercopa|super cup|taça|taca|phase|uefa|conmebol|concacaf|libertadores|"
                  r"sudamericana|champions|\bafc\b|\bcaf\b", re.I)
# women's, youth and college competitions: listed, but never offered to the live test (SportyBet names those teams
# like the senior men's side, so a pick could land on the wrong team)
_NOTEST = re.compile(r"women|femen|frauen|vrouwen|f[eé]min|nwsl|\bwsl\b|w-league|damallsvenskan|toppserien|liga f\b|"
                     r"usl super league|premi[eè]re ligue|ncaa|\bu-?\d\d\b|youth|reserve|shebelieves|arkema", re.I)


def _pct(x) -> str:
    return "PENDING" if x is None else f"{x * 100:.0f}%"


def _avg(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _r(x, d=2):
    return None if x is None else round(x, d)


# ---------------------------------------------------------------- football: this season's games per league and team
def season_rows(rows: list[dict], now: datetime) -> list[dict]:
    """The current season of every league that is being played now."""
    latest, last_seen = {}, {}
    for m in rows:
        lk = m.get("lid")
        if lk is None or any(s in (m.get("league") or "").lower() for s in _SKIP):
            continue
        y = m.get("year") or 0
        if y > latest.get(lk, 0):
            latest[lk] = y
        if m["date"] > last_seen.get(lk, ""):
            last_seen[lk] = m["date"]
    cut = (now - timedelta(days=ACTIVE_DAYS)).strftime("%Y-%m-%d")
    return [m for m in rows if m.get("lid") in latest and (m.get("year") or 0) == latest[m["lid"]]
            and last_seen[m["lid"]] >= cut and not any(s in (m.get("league") or "").lower() for s in _SKIP)]


def _teams(rows: list[dict]) -> dict:
    """(lid, team id) -> {"team", "league", "games": [(match, side)]}"""
    out: dict = {}
    for m in rows:
        for side, tid, name in ((0, m.get("hid"), m.get("home")), (1, m.get("aid"), m.get("away"))):
            t = out.setdefault((m["lid"], tid), {"team": name, "league": m.get("league"), "lid": m["lid"], "games": []})
            t["team"] = name
            t["games"].append((m, side))
    return out


def _leagues(rows: list[dict]) -> dict:
    out: dict = {}
    for m in rows:
        if _CUP.search(m.get("league") or ""):
            continue
        lg = out.setdefault(m["lid"], {"league": m.get("league"), "lid": m["lid"], "games": []})
        lg["games"].append(m)
    return out


def _went(m: dict, side: int) -> tuple[bool, bool] | None:
    """(was behind at some point, was ahead at some point) for one side, from the goal minutes."""
    g = m.get("goals")
    if g is None:
        return None
    sc, behind, ahead = [0, 0], False, False
    for _minute, s in sorted(g, key=lambda x: x[0]):
        sc[s] += 1
        behind |= sc[side] < sc[1 - side]
        ahead |= sc[side] > sc[1 - side]
    return behind, ahead


def _cand_team(t: dict) -> dict:
    return {"team": t["team"], "league": t["league"], "lid": t["lid"]}


def _cand_league(lg: dict) -> dict:
    return {"league": lg["league"], "lid": lg["lid"]}


def _mk(lid, title, population, rule, cols, ranked, row, note, test, cand) -> tuple[dict, list]:
    lst = {"id": lid, "title": title, "population": population, "rule": rule, "cols": cols,
           "rows": [row(x) for x in ranked[:ROWS]], "note": note, "test": test}
    testable = [x for x in ranked if not _NOTEST.search(x.get("league") or "")]
    return lst, [cand(x) for x in testable[:CANDS]]


def football_lists(rows: list[dict], now: datetime) -> tuple[list[dict], dict]:
    cur = season_rows(rows, now)
    teams, leagues = _teams(cur), _leagues(cur)
    lists, cands = [], {}

    def add(pair):
        lists.append(pair[0])
        cands[pair[0]["id"]] = pair[1]

    # 7 goals over/under, by league
    L = []
    for lg in leagues.values():
        n = len(lg["games"])
        if n < LEAGUE_MIN:
            continue
        tot = [m["ft"][0] + m["ft"][1] for m in lg["games"]]
        L.append({**lg, "n": n, "o": {ln: sum(t > ln for t in tot) / n for ln in (0.5, 1.5, 2.5, 3.5, 4.5)},
                  "gpg": sum(tot) / n})
    L.sort(key=lambda x: -x["o"][2.5])
    add(_mk("ou_leagues", "Goals over and under, by league", f"{len(L)} leagues", f"{LEAGUE_MIN}+ games this season",
            ["League", "Games", "Over 0.5", "Over 1.5", "Over 2.5", "Over 3.5", "Over 4.5", "Goals a game"], L,
            lambda x: [x["league"], x["n"], *[_pct(x["o"][ln]) for ln in (0.5, 1.5, 2.5, 3.5, 4.5)], _r(x["gpg"])],
            "Under is the other side of each figure. League goal rates carry over, and the price already has them.",
            "Over 2.5 in a game of the league", _cand_league))

    # 8 clean sheets and failures to score, by team
    T = []
    for t in teams.values():
        n = len(t["games"])
        if n < TEAM_MIN:
            continue
        cs = sum(m["ft"][1 - s] == 0 for m, s in t["games"]) / n
        fts = sum(m["ft"][s] == 0 for m, s in t["games"]) / n
        nb = sum(m["ft"][0] == 0 or m["ft"][1] == 0 for m, s in t["games"]) / n
        T.append({**t, "n": n, "cs": cs, "fts": fts, "nb": nb})
    T.sort(key=lambda x: (-x["nb"], -x["n"]))
    add(_mk("clean_sheets", "Clean sheets and blanks, by team", f"{len(T)} teams", f"{TEAM_MIN}+ games this season",
            ["Team", "League", "Games", "Clean sheets", "Failed to score", "One side blank"], T,
            lambda x: [x["team"], x["league"], x["n"], _pct(x["cs"]), _pct(x["fts"]), _pct(x["nb"])],
            "'One side blank' is the No side of both teams to score.", "BTTS No in the team's game", _cand_team))

    # 9 second half busier than the first, by league
    L = []
    for lg in leagues.values():
        g = [m for m in lg["games"] if m.get("ht") and m.get("goals") is not None]
        if len(g) < LEAGUE_MIN:
            continue
        h1 = sum(m["ht"][0] + m["ht"][1] for m in g)
        if not h1:
            continue
        tot = sum(m["ft"][0] + m["ft"][1] for m in g)
        busy = sum((m["ft"][0] + m["ft"][1] - m["ht"][0] - m["ht"][1]) > (m["ht"][0] + m["ht"][1]) for m in g) / len(g)
        L.append({**lg, "n": len(g), "busy": busy, "share": (tot - h1) / tot if tot else None,
                  "fh15": sum(m["ht"][0] + m["ht"][1] < 1.5 for m in g) / len(g)})
    L.sort(key=lambda x: -x["fh15"])
    add(_mk("second_half", "Quiet first halves, busier second halves, by league", f"{len(L)} leagues",
            f"{LEAGUE_MIN}+ games with a half-time score",
            ["League", "Games", "0 or 1 goal by half-time", "2nd half has more goals", "Goals after half-time"], L,
            lambda x: [x["league"], x["n"], _pct(x["fh15"]), _pct(x["busy"]), _pct(x["share"])],
            "About 55% of all goals come after half-time everywhere.", "1st half Under 1.5 in a game of the league",
            _cand_league))

    # 10 a goal before the 30th minute, by league
    L = []
    for lg in leagues.values():
        g = [m for m in lg["games"] if m.get("goals") is not None]
        if len(g) < LEAGUE_MIN:
            continue
        firsts = [min(x[0] for x in m["goals"]) for m in g if m["goals"]]
        L.append({**lg, "n": len(g), "e30": sum(f <= 30 for f in firsts) / len(g),
                  "fh": sum(any(x[0] <= 45 for x in m["goals"]) for m in g) / len(g),
                  "first": _avg(firsts)})
    L.sort(key=lambda x: -x["fh"])
    add(_mk("early_goal", "Early goals, by league", f"{len(L)} leagues", f"{LEAGUE_MIN}+ games with every goal's minute",
            ["League", "Games", "A goal by the 30th minute", "A goal by half-time", "Average minute of the first goal"], L,
            lambda x: [x["league"], x["n"], _pct(x["e30"]), _pct(x["fh"]), _r(x["first"], 0)],
            "A goal comes before half-time in about 70% of games anyway.", "1st half Over 0.5 in a game of the league",
            _cand_league))

    # 11 comebacks and dropped leads, by team
    T = []
    for t in teams.values():
        b = a = saved = dropped = 0
        for m, s in t["games"]:
            w = _went(m, s)
            if w is None:
                continue
            if w[0]:
                b += 1
                saved += m["ft"][s] >= m["ft"][1 - s]
            if w[1]:
                a += 1
                dropped += m["ft"][s] <= m["ft"][1 - s]
        if b >= 5:
            T.append({**t, "b": b, "saved": saved / b, "a": a, "dropped": dropped / a if a else None,
                      "n": len(t["games"])})
    T.sort(key=lambda x: (-x["saved"], -x["b"]))
    add(_mk("comebacks", "Comebacks and dropped leads, by team", f"{len(T)} teams", "behind in 5+ games this season",
            ["Team", "League", "Times behind", "Avoided defeat", "Times ahead", "Failed to win from ahead"], T,
            lambda x: [x["team"], x["league"], x["b"], _pct(x["saved"]), x["a"], _pct(x["dropped"])],
            "Small counts: a team is behind in only a handful of games a season.",
            "the team on double chance (win or draw)", _cand_team))

    # 12 draws, by team
    T = []
    for t in teams.values():
        n = len(t["games"])
        if n < TEAM_MIN:
            continue
        T.append({**t, "n": n, "d": sum(m["ft"][0] == m["ft"][1] for m, s in t["games"]) / n,
                  "d00": sum(m["ft"] == [0, 0] for m, s in t["games"]) / n,
                  "d11": sum(m["ft"] == [1, 1] for m, s in t["games"]) / n})
    T.sort(key=lambda x: (-x["d"], -x["n"]))
    add(_mk("draws", "Draw-heavy teams", f"{len(T)} teams", f"{TEAM_MIN}+ games this season",
            ["Team", "League", "Games", "Draws", "0-0", "1-1"], T,
            lambda x: [x["team"], x["league"], x["n"], _pct(x["d"]), _pct(x["d00"]), _pct(x["d11"])],
            "About 1 game in 4 is a draw; a team's draw rate barely carries over (trend atlas).",
            "the draw in the team's game", _cand_team))

    # 13 corners, 14 cards, 15 fouls, 17 shots on target, 18 luck: per team
    def per_team(key, both=True):
        out = []
        for t in teams.values():
            g = [(m, s) for m, s in t["games"] if m.get(key) and None not in m[key]]
            if len(g) < TEAM_MIN:
                continue
            f = [m[key][s] for m, s in g]
            a = [m[key][1 - s] for m, s in g]
            tot = [x + y for x, y in zip(f, a, strict=True)]
            out.append({**t, "n": len(g), "for": sum(f) / len(g), "ag": sum(a) / len(g), "tot": sum(tot) / len(g),
                        "sd": statistics.pstdev(tot), "last": tot[-10:], "g": g})
        return out

    T = sorted(per_team("corners"), key=lambda x: -x["tot"])
    add(_mk("team_corners", "Most corners in a team's games", f"{len(T)} teams", f"{TEAM_MIN}+ games with corner counts",
            ["Team", "League", "Games", "Corners for", "Corners against", "Total a game", "Last 10"], T,
            lambda x: [x["team"], x["league"], x["n"], _r(x["for"], 1), _r(x["ag"], 1), _r(x["tot"], 1),
                       " ".join(str(v) for v in x["last"])],
            "A team's corner count carries over from one half-season to the next (correlation 0.62), the strongest "
            "team trend in the atlas. Whether SportyBet's line already has it is what the test measures.",
            "corners Over SportyBet's main line in the team's game", _cand_team))

    T = []
    for t in teams.values():
        g = [(m, s) for m, s in t["games"] if m.get("cards") is not None]
        if len(g) < TEAM_MIN:
            continue
        own = [sum(1 for c in m["cards"] if c[1] == s) for m, s in g]
        tot = [len(m["cards"]) for m, s in g]
        T.append({**t, "n": len(g), "own": sum(own) / len(g), "tot": sum(tot) / len(g),
                  "sd": statistics.pstdev(tot), "last": tot[-10:]})
    T.sort(key=lambda x: -x["tot"])
    add(_mk("cards", "Card-heavy teams", f"{len(T)} teams", f"{TEAM_MIN}+ games with card records",
            ["Team", "League", "Games", "Own cards a game", "Cards in its games", "Spread", "Last 10"], T,
            lambda x: [x["team"], x["league"], x["n"], _r(x["own"], 1), _r(x["tot"], 1), _r(x["sd"], 1),
                       " ".join(str(v) for v in x["last"])],
            "Card counts carry over (correlation 0.5). Yellow and red cards both count here; SportyBet's bookings "
            "line is graded only in games without a red card.",
            "bookings Over SportyBet's main line in the team's game", _cand_team))

    T = sorted(per_team("fouls"), key=lambda x: -x["tot"])
    add(_mk("fouls", "Most fouls in a team's games", f"{len(T)} teams", f"{TEAM_MIN}+ games with foul counts",
            ["Team", "League", "Games", "Fouls committed", "Fouls suffered", "Total a game"], T,
            lambda x: [x["team"], x["league"], x["n"], _r(x["for"], 1), _r(x["ag"], 1), _r(x["tot"], 1)],
            "Fouls lead to cards, so this list is tested on the bookings line too.",
            "bookings Over SportyBet's main line in the team's game", _cand_team))

    lists.append({"id": "fh_corners", "title": "First-half corners, by team", "population": "PENDING",
                  "rule": "needs first-half corner counts", "cols": ["Team", "League", "Games", "1st-half corners"],
                  "rows": [], "note": "PENDING: ESPN keeps corners for the whole match only. The Flashscore detail "
                  "archive has kept each half since 12 Nov 2026; the list fills in when teams reach 8 games.",
                  "test": "PENDING: no first-half corner counts yet"})
    cands["fh_corners"] = []

    T = sorted(per_team("sot"), key=lambda x: -x["tot"])
    add(_mk("shots_on_target", "Most shots on target in a team's games", f"{len(T)} teams",
            f"{TEAM_MIN}+ games with shot counts",
            ["Team", "League", "Games", "On target for", "On target against", "Total a game"], T,
            lambda x: [x["team"], x["league"], x["n"], _r(x["for"], 1), _r(x["ag"], 1), _r(x["tot"], 1)],
            "Open games at both ends.", "Over 2.5 in the team's game", _cand_team))

    conv = {}
    for lid, lg in leagues.items():
        g = [m for m in lg["games"] if m.get("sot") and None not in m["sot"]]
        s = sum(m["sot"][0] + m["sot"][1] for m in g)
        if s:
            conv[lid] = sum(m["ft"][0] + m["ft"][1] for m in g) / s
    T = []
    for t in per_team("sot"):
        if t["lid"] not in conv:
            continue
        goals = sum(m["ft"][s] for m, s in t["g"])
        exp = t["for"] * t["n"] * conv[t["lid"]]
        T.append({**t, "goals": goals, "exp": exp, "gap": (goals - exp) / t["n"]})
    T.sort(key=lambda x: x["gap"])
    add(_mk("luck", "Unlucky teams: goals well under their shots", f"{len(T)} teams",
            f"{TEAM_MIN}+ games with shot counts",
            ["Team", "League", "Games", "Goals", "Goals its shots were worth", "Gap a game"], T,
            lambda x: [x["team"], x["league"], x["n"], x["goals"], _r(x["exp"], 1), _r(x["gap"])],
            "'Worth' = the team's shots on target at its league's goals-per-shot rate. The claim: finishing evens "
            "out, so these teams' results should improve. The bottom of the full table is the lucky teams.",
            "the team to win", _cand_team))

    rosters = {}
    for (lid, _tid), t in teams.items():
        rosters.setdefault(str(lid), {"league": t["league"], "teams": []})["teams"].append(t["team"])
    return lists, {"cands": cands, "rosters": rosters}


# ---------------------------------------------------------------- other sports
def us_list(folder: Path) -> tuple[dict, list]:
    try:
        from engine import sport_atlas as sa
        rows = sa.us_rows(folder) if folder.exists() else []
    except Exception:  # noqa: BLE001 - history not there yet: PENDING
        rows = []
    latest = {}
    for m in rows:
        latest[m["lk"]] = max(latest.get(m["lk"], ""), m["sk"])
    rec = defaultdict(lambda: {"n": 0, "over": 0, "cov_n": 0, "cov": 0})
    names = {}
    for m in rows:
        if m["sk"] != latest[m["lk"]]:
            continue
        pr = m.get("prices") or {}
        tot = m["ft"][0] + m["ft"][1]
        for s, k, nm in ((0, m["hk"], m["home"]), (1, m["ak"], m["away"])):
            names[k] = (nm, m["lk"])
            if pr.get("total") is not None and tot != pr["total"]:
                rec[k]["n"] += 1
                rec[k]["over"] += tot > pr["total"]
            if pr.get("spread") is not None:
                d = m["ft"][0] - m["ft"][1] + pr["spread"]
                if d != 0:
                    rec[k]["cov_n"] += 1
                    rec[k]["cov"] += (d > 0) == (s == 0)
    T = [{"team": names[k][0], "league": names[k][1].upper(), "n": v["n"], "over": v["over"] / v["n"],
          "cov": v["cov"] / v["cov_n"] if v["cov_n"] else None} for k, v in rec.items() if v["n"] >= 8]
    T.sort(key=lambda x: (-x["over"], -x["n"]))
    lst = {"id": "us_totals", "title": "US sports: teams against the posted total", "population": f"{len(T)} teams"
           if T else "PENDING", "rule": "8+ games with a posted total this season",
           "cols": ["Team", "League", "Games", "Went over the total", "Covered the spread"],
           "rows": [[x["team"], x["league"], x["n"], _pct(x["over"]), _pct(x["cov"])] for x in T[:ROWS]],
           "note": "PENDING until the US sports history backfill is saved." if not T else
           "A record against the line is mostly luck: over 3 seasons it did not repeat (SPORT_ATLAS_STUDY).",
           "test": "Over the main total in the team's game (basketball)"}
    return lst, [{"team": x["team"], "league": x["league"]} for x in T[:CANDS] if x["league"] in ("NBA", "WNBA")]


def wb_list(folder: Path) -> tuple[dict, list]:
    try:
        from engine import sport_atlas as sa
        rows = [r for r in sa.sportybet_rows(folder) if r["sport"] == "sportybet basketball"] if folder.exists() else []
    except Exception:  # noqa: BLE001
        rows = []
    lg = defaultdict(lambda: {"n": 0, "pts": 0, "ln": 0, "over": 0})
    for m in rows:
        pr = m.get("prices") or {}
        tot = m["ft"][0] + m["ft"][1]
        if pr.get("total") is None or tot == pr["total"]:
            continue
        x = lg[m["lk"]]
        x["n"] += 1
        x["pts"] += tot
        x["ln"] += pr["total"]
        x["over"] += tot > pr["total"]
    L = [{"lk": k, "league": k[3:].replace("|", ": "), "n": v["n"], "pts": v["pts"] / v["n"], "ln": v["ln"] / v["n"],
          "over": v["over"] / v["n"]} for k, v in lg.items() if v["n"] >= 15]
    L.sort(key=lambda x: (-x["over"], -x["n"]))
    lst = {"id": "wb_totals", "title": "World basketball: leagues against SportyBet's total", "population":
           f"{len(L)} leagues" if L else "PENDING", "rule": "15+ graded games with a total since 8 Oct 2026",
           "cols": ["League", "Games", "Points a game", "SportyBet's line", "Went over"],
           "rows": [[x["league"], x["n"], _r(x["pts"], 1), _r(x["ln"], 1), _pct(x["over"])] for x in L[:ROWS]],
           "note": "The bottom of the full table is the leagues that stay under. Small counts so far.",
           "test": "Over the main total in a game of the league"}
    return lst, [{"sb_league": x["league"]} for x in L[:CANDS]]


def tennis_list() -> dict:
    try:
        from engine import sport_atlas as sa
        rows = sa.tennis_rows()
    except Exception:  # noqa: BLE001 - source down: PENDING
        rows = []
    last = max((m["date"] for m in rows), default="")
    cut = (datetime.fromisoformat(last[:10]) - timedelta(days=365)).strftime("%Y-%m-%d") if last else ""
    rec = defaultdict(lambda: {"n": 0, "w": 0, "exp": 0.0})
    for m in rows:
        pr = m.get("prices") or {}
        if m["date"] < cut or not pr.get("ml_home") or not pr.get("ml_away"):
            continue
        q = (1 / pr["ml_home"]) / (1 / pr["ml_home"] + 1 / pr["ml_away"])
        hw = m["ft"][0] > m["ft"][1]
        for name, won, ch in ((m["home"], hw, q), (m["away"], not hw, 1 - q)):
            rec[name]["n"] += 1
            rec[name]["w"] += won
            rec[name]["exp"] += ch
    T = [{"p": k, "n": v["n"], "w": v["w"] / v["n"], "exp": v["exp"] / v["n"], "gap": (v["w"] - v["exp"]) / v["n"]}
         for k, v in rec.items() if v["n"] >= 25]
    T.sort(key=lambda x: -x["gap"])
    return {"id": "tennis", "title": "Tennis: players against the closing price", "population":
            f"{len(T)} players" if T else "PENDING", "rule": f"25+ priced matches in the year to {last[:10]}" if last
            else "25+ priced matches in a year",
            "cols": ["Player", "Matches", "Won", "The price expected", "Gap"],
            "rows": [[x["p"], x["n"], _pct(x["w"]), _pct(x["exp"]), f"{x['gap'] * 100:+.0f} pts"] for x in T[:ROWS]],
            "note": "A player's record against the price did not repeat from one period to the next "
            "(correlation +0.01, SPORT_ATLAS_STUDY)." if T else "PENDING: tennis-data.co.uk not read this run.",
            "test": "PENDING: the SportyBet sweep keeps no tennis price yet"}


def build(root: Path = ROOT, now: datetime | None = None, tennis: bool = True) -> dict:
    from data import espn_history
    now = now or datetime.now(UTC)
    lists, index = football_lists(espn_history.load(root / "data" / "espn_matches"), now)
    us, us_c = us_list(root / "data" / "sports_history")
    lists.append(us)
    index["cands"]["us_totals"] = us_c
    lists.append(tennis_list() if tennis else {"id": "tennis", "title": "Tennis: players against the closing price",
                                               "population": "PENDING", "rule": "", "cols": [], "rows": [],
                                               "note": "PENDING", "test": "PENDING"})
    index["cands"]["tennis"] = []
    wb, wb_c = wb_list(root / "data" / "universe")
    lists.append(wb)
    index["cands"]["wb_totals"] = wb_c
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    return {"lists": {"generated_at": stamp, "record_only": True, "lists": lists},
            "index": {"generated_at": stamp, **index}}


def write(doc: dict, out: Path = OUT) -> str:
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(doc["lists"], ensure_ascii=False), encoding="utf-8")
    (out / "pick_index.json").write_text(json.dumps(doc["index"], ensure_ascii=False), encoding="utf-8")
    filled = sum(1 for x in doc["lists"]["lists"] if x["rows"])
    return f"stat lists 7-21: {filled} of {len(doc['lists']['lists'])} filled"


if __name__ == "__main__":
    print(write(build()))
