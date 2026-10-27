"""
MATCH STUDY — how every match in the covered competitions was played, side
by side, so each team's TACTICAL PROFILE can update after every game it plays,
bet on or not (Architect 2026-10-26: "the framework needs to study each match.
The ones that we bet and the one that we do not bet ... understand the tactics,
understand the formation, understand how each tactics interacts with each other").

Source: FotMob (free, no key). Each covered competition's FotMob league page
lists its season's matches; every finished one gets its match page read once
into one row per match (data/match_study/<month>.jsonl):

  formation + coach of each side, goals, xG (and FotMob's open-play / set-play
  split), the SHOT MAP by situation — open play, fast break (counter), set
  piece (corners, free kicks, throw-ins), penalty, headers (the cross/aerial
  proxy) — possession, field tilt (share of the passes played in the
  opponent's half), a PPDA proxy (opponent passes in their own half per
  defensive action: tackles + interceptions + fouls; low = pressing), the
  defensive-line proxy (opponents caught offside), crosses, long balls, box
  touches, big chances, corners, red cards with the minute, and GAME STATE:
  minutes and xG for / against while level, leading and trailing (from the
  goal times and the shot map).

FotMob doesn't publish true PPDA or line height: the proxies above are named
as proxies everywhere they are shown. A stat FotMob doesn't publish is absent,
never 0 (HR35). Nothing here selects: engine/tactics.py builds the profiles.

    python data/match_study.py                # every covered competition, new matches only
    python data/match_study.py "La Liga"      # one competition
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

STUDY_DIR = ROOT / "data" / "match_study"
_LEAGUE = "https://www.fotmob.com/api/data/leagues?id={lid}"

SET_PIECE = {"FromCorner", "SetPiece", "FreeKick", "ThrowInSetPiece"}
COUNTER = {"FastBreak"}
PENALTY = {"Penalty"}


def _num(v) -> float | None:
    """'369 (83%)' -> 369, '1.42' -> 1.42, None stays None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(v))
    return float(m.group(1)) if m else None


def _stats(details: dict) -> dict[str, list[float]]:
    """Every FotMob stat key -> [home, away] (both present only)."""
    out: dict[str, list[float]] = {}
    groups = ((details.get("content") or {}).get("stats") or {}).get("Periods", {}).get("All", {}).get("stats", [])
    for grp in groups:
        for s in grp.get("stats", []):
            vals = s.get("stats") or []
            if s.get("type") == "title" or len(vals) != 2 or s.get("key") in out:
                continue
            h, a = _num(vals[0]), _num(vals[1])
            if h is not None and a is not None:
                out[s["key"]] = [h, a]
    return out


def _goal_minutes(details: dict) -> list[tuple[float, bool]]:
    """[(minute, scored_by_home)] in order, from FotMob's match events."""
    ev = (((details.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
    out = []
    for e in ev:
        if e.get("type") == "Goal":
            mins = (e.get("time") or 0) + (e.get("overloadTime") or 0) / 100
            out.append((float(mins), bool(e.get("isHome"))))
    return sorted(out)


def _red_minutes(details: dict) -> list[tuple[int, bool]]:
    ev = (((details.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
    return [(int(e.get("time") or 0), bool(e.get("isHome"))) for e in ev
            if e.get("type") == "Card" and str(e.get("card", "")).lower() in ("red", "yellowred")]


def _state_at(minute: float, goals: list[tuple[float, bool]]) -> int:
    """Home goal difference just before `minute`."""
    return sum(1 if home else -1 for m, home in goals if m < minute)


def game_state(details: dict, home_id) -> dict:
    """Per side: minutes and xG for / against while level, leading, trailing."""
    goals = _goal_minutes(details)
    end = 90.0
    cuts = [0.0] + [m for m, _ in goals if m < end] + [end]
    mins = {"home": {"level": 0.0, "leading": 0.0, "trailing": 0.0},
            "away": {"level": 0.0, "leading": 0.0, "trailing": 0.0}}
    for a, b in zip(cuts, cuts[1:]):
        d = _state_at((a + b) / 2, goals)
        hs = "level" if d == 0 else "leading" if d > 0 else "trailing"
        as_ = "level" if d == 0 else "trailing" if d > 0 else "leading"
        mins["home"][hs] += b - a
        mins["away"][as_] += b - a
    xg = {s: {st: {"for": 0.0, "against": 0.0} for st in ("level", "leading", "trailing")} for s in ("home", "away")}
    shots = ((details.get("content") or {}).get("shotmap") or {}).get("shots") or []
    for sh in shots:
        if sh.get("isOwnGoal"):
            continue
        minute = float(sh.get("min") or 0) + float(sh.get("minAdded") or 0) / 100
        d = _state_at(minute, goals)
        is_home = str(sh.get("teamId")) == str(home_id)
        x = float(sh.get("expectedGoals") or 0.0)
        hs = "level" if d == 0 else "leading" if d > 0 else "trailing"
        as_ = "level" if d == 0 else "trailing" if d > 0 else "leading"
        if is_home:
            xg["home"][hs]["for"] += x
            xg["away"][as_]["against"] += x
        else:
            xg["away"][as_]["for"] += x
            xg["home"][hs]["against"] += x
    return {s: {st: {"min": round(mins[s][st], 1), "xg_for": round(xg[s][st]["for"], 3),
                     "xg_against": round(xg[s][st]["against"], 3)} for st in mins[s]} for s in mins}


def shot_types(details: dict, team_id) -> dict | None:
    """xG and shots of one side by situation; None without a shot map."""
    shots = ((details.get("content") or {}).get("shotmap") or {}).get("shots")
    if not shots:
        return None
    out = {k: 0.0 for k in ("open", "counter", "set_piece", "penalty", "header")}
    n = {k: 0 for k in out}
    for sh in shots:
        if str(sh.get("teamId")) != str(team_id) or sh.get("isOwnGoal"):
            continue
        x = float(sh.get("expectedGoals") or 0.0)
        sit = sh.get("situation") or ""
        kind = ("penalty" if sit in PENALTY else "set_piece" if sit in SET_PIECE
                else "counter" if sit in COUNTER else "open")
        out[kind] += x
        n[kind] += 1
        if sh.get("shotType") == "Header":
            out["header"] += x
            n["header"] += 1
    return {"xg": {k: round(v, 3) for k, v in out.items()}, "shots": n}


def parse_match(details: dict) -> dict | None:
    """One FotMob match page -> the study row (None when the lineup or score
    is missing — never a half-read row)."""
    content = details.get("content") or {}
    lu = content.get("lineup") or {}
    ht, at = lu.get("homeTeam") or {}, lu.get("awayTeam") or {}
    header = details.get("header") or {}
    teams = header.get("teams") or []
    if len(teams) != 2 or teams[0].get("score") is None:
        return None
    gen = details.get("general") or {}
    hid, aid = teams[0].get("id") or ht.get("id"), teams[1].get("id") or at.get("id")
    st = _stats(details)
    reds = _red_minutes(details)
    gs = game_state(details, hid)

    def side(i: int, team: dict, tid, opp_i: int) -> dict:
        def v(key):
            x = st.get(key)
            return x[i] if x else None

        def ov(key):
            x = st.get(key)
            return x[opp_i] if x else None
        opp_half, opp_opp_half = v("opposition_half_passes"), ov("opposition_half_passes")
        tilt = (round(opp_half / (opp_half + opp_opp_half), 3)
                if opp_half is not None and opp_opp_half and opp_half + opp_opp_half > 0 else None)
        def_actions = [v("matchstats.headers.tackles"), v("interceptions"), v("fouls")]
        opp_build = ov("own_half_passes")
        ppda = (round(opp_build / sum(def_actions), 2)
                if opp_build is not None and None not in def_actions and sum(def_actions) > 0 else None)
        coach = (team.get("coach") or {}).get("name") if isinstance(team.get("coach"), dict) else None
        return {"id": tid, "name": teams[i].get("name"), "formation": team.get("formation"), "coach": coach,
                "goals": teams[i].get("score"), "xg": v("expected_goals"),
                "xg_open": v("expected_goals_open_play"), "xg_set": v("expected_goals_set_play"),
                "shot_types": shot_types(details, tid), "possession": v("BallPossesion"), "field_tilt": tilt,
                "ppda_proxy": ppda, "opp_offsides": ov("Offsides"), "crosses": v("accurate_crosses"),
                "long_balls": v("long_balls_accurate"), "box_touches": v("touches_opp_box"),
                "big_chances": v("big_chance"), "shots": v("total_shots"), "sot": v("ShotsOnTarget"),
                "corners": v("corners"), "reds": [m for m, home in reds if home == (i == 0)],
                "state": gs["home" if i == 0 else "away"]}
    return {"fotmob_id": gen.get("matchId"), "league_id": gen.get("parentLeagueId") or gen.get("leagueId"),
            "league": gen.get("leagueName"), "ko": (gen.get("matchTimeUTCDate") or "")[:16],
            "home": side(0, ht, hid, 1), "away": side(1, at, aid, 0)}


def league_matches(lid: int) -> list[dict]:
    """[{id, ko, finished}] of a FotMob competition's current season."""
    from data import fotmob as fm
    d = fm._get(_LEAGUE.format(lid=lid))
    out = []
    for m in (d.get("fixtures") or {}).get("allMatches") or []:
        s = m.get("status") or {}
        out.append({"id": str(m.get("id")), "ko": s.get("utcTime") or "",
                    "finished": bool(s.get("finished")) and not s.get("cancelled") and not s.get("awarded")})
    return out


def seen_ids(folder: Path = STUDY_DIR) -> set[str]:
    ids: set[str] = set()
    for p in folder.glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.add(str(json.loads(line).get("fotmob_id")))
    return ids


def append(rows: list[dict], folder: Path = STUDY_DIR) -> None:
    by_month: dict[str, list[dict]] = {}
    for r in rows:
        by_month.setdefault((r.get("ko") or "0000-00")[:7], []).append(r)
    folder.mkdir(parents=True, exist_ok=True)
    for month, rs in by_month.items():
        with (folder / f"{month}.jsonl").open("a", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")


def collect(leagues: list[str] | None = None, folder: Path = STUDY_DIR, budget: int = 4000,
            pause: float = 0.25) -> tuple[int, list[str]]:
    """Read every finished, not-yet-studied match of the covered competitions.
    Returns (rows written, notes). Saved per competition, so a cut-off run
    keeps what it read; the next run carries on."""
    from data import fotmob as fm
    from data.team_profiles import FOTMOB_LEAGUE
    seen, notes, total = seen_ids(folder), [], 0
    for league in leagues or list(FOTMOB_LEAGUE):
        try:
            todo = [m for m in league_matches(FOTMOB_LEAGUE[league]) if m["finished"] and m["id"] not in seen]
        except Exception as e:  # noqa: BLE001 — one competition failing never stops the rest
            notes.append(f"{league}: FotMob league page unavailable ({str(e)[:60]})")
            continue
        rows, failed = [], 0
        for m in todo:
            if total + len(rows) >= budget:
                break
            try:
                row = parse_match(fm.match_details(m["id"]))
            except Exception:  # noqa: BLE001 — retried next run
                row = None
            if row is None:
                failed += 1
            else:
                row["competition"] = league
                row["fotmob_id"] = str(row.get("fotmob_id") or m["id"])
                row["ko"] = row.get("ko") or m["ko"][:16]
                rows.append(row)
                seen.add(m["id"])
            time.sleep(pause)
        append(rows, folder)
        total += len(rows)
        if failed:
            notes.append(f"{league}: {failed} match page(s) unread — retried next run")
        print(f"{league}: {len(rows)} new match(es) studied", flush=True)
    return total, notes


def load(folder: Path = STUDY_DIR) -> list[dict]:
    rows: list[dict] = []
    for p in sorted(folder.glob("*.jsonl")):
        rows += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r.get("ko") or ""):
        if r["fotmob_id"] not in seen:
            seen.add(r["fotmob_id"])
            out.append(r)
    return out


if __name__ == "__main__":
    n, notes = collect(sys.argv[1:] or None)
    print(f"{n} match(es) studied")
    for x in notes:
        print(" ", x)
