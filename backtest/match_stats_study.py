"""
MATCH STATS STUDY — how the covered matches were played (Architect
2026-10-07: learn "how these games are played ... the tactical profile").

Reads data/match_stats/*.jsonl (data/match_stats.py, FotMob post-match
stats of every fixture the board rated) and writes:
  backtest/MATCH_STATS_STUDY.md
    1. league styles: goals, expected goals, shots, shots on target, big
       chances, corners, cards per match; goals per shot on target;
    2. does the balance of play decide matches? — how often the side with
       more xG / shots on target / possession won;
    3. team profiles with 3+ matches: per-match for/against and finishing
       (goals minus xG — luck that tends not to last);
  data/match_stats/team_profiles.json — every team's profile, for a model.
A study, not a selector.

    python backtest/match_stats_study.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import match_stats as ms  # noqa: E402

OUT = ROOT / "backtest" / "MATCH_STATS_STUDY.md"
PROFILES = ms.STATS_DIR / "team_profiles.json"
MIN_TEAM = 3
PER_MATCH = ("xg", "shots", "sot", "big_chances", "corners", "yellow")


def _avg(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _fmt(x: float | None, d: int = 2) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def main() -> int:
    rows = [r for r in ms.load() if r.get("score") and None not in r["score"]]
    L = ["# MATCH STATS STUDY — how the covered matches were played", "",
         "Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats "
         "of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. "
         "A study, not a selector.", ""]
    if not rows:
        L.append("No match archived yet — NO DATA — PENDING.")
        OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
        print("\n".join(L))
        return 0
    L += [f"{len(rows)} matches, {min(r['date'] for r in rows)} to {max(r['date'] for r in rows)}.", "",
          "## League styles (per match, both teams together)", "",
          "| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    by_lg: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_lg[r["league"] or "?"].append(r)
    for lg, rs in sorted(by_lg.items(), key=lambda x: -len(x[1])):
        def tot(k: str, rs: list[dict] = rs) -> float | None:
            v = [sum(r["stats"][k]) for r in rs if k in r["stats"]]
            return _avg(v)
        goals = _avg([sum(r["score"]) for r in rs])
        sot_all = sum(sum(r["stats"]["sot"]) for r in rs if "sot" in r["stats"])
        g_sot = sum(sum(r["score"]) for r in rs if "sot" in r["stats"]) / sot_all if sot_all else None
        L.append(f"| {lg} | {len(rs)} | {_fmt(goals)} | {_fmt(tot('xg'))} | {_fmt(tot('shots'), 1)} | "
                 f"{_fmt(tot('sot'), 1)} | {_fmt(tot('big_chances'), 1)} | {_fmt(tot('corners'), 1)} | "
                 f"{_fmt(tot('yellow'), 1)} | {_fmt(g_sot)} |")
    L += ["", "## Does the balance of play decide the match?", "",
          "Every match where the two sides differed on the measure (draws included).", "",
          "| The side with more … | matches | won | drew | lost |", "|---|---|---|---|---|"]
    for k, name in (("xg", "expected goals"), ("sot", "shots on target"), ("big_chances", "big chances"),
                    ("possession", "possession")):
        w = d = lo = 0
        for r in rows:
            s = r["stats"].get(k)
            if not s or s[0] == s[1]:
                continue
            hi = 0 if s[0] > s[1] else 1
            g = r["score"]
            if g[0] == g[1]:
                d += 1
            elif (g[0] > g[1]) == (hi == 0):
                w += 1
            else:
                lo += 1
        n = w + d + lo
        if n:
            L.append(f"| {name} | {n} | {w / n:.0%} | {d / n:.0%} | {lo / n:.0%} |")
    teams: dict[str, dict] = defaultdict(lambda: {"n": 0, "league": None, "for": defaultdict(list),
                                                  "against": defaultdict(list), "goals": [], "conceded": []})
    for r in rows:
        for side, opp in ((0, 1), (1, 0)):
            t = teams[r["home"] if side == 0 else r["away"]]
            t["n"] += 1
            t["league"] = r["league"]
            t["goals"].append(r["score"][side])
            t["conceded"].append(r["score"][opp])
            for k, v in r["stats"].items():
                t["for"][k].append(v[side])
                t["against"][k].append(v[opp])
    prof = {}
    for name, t in teams.items():
        p = {"league": t["league"], "matches": t["n"],
             "goals": _avg(t["goals"]), "conceded": _avg(t["conceded"])}
        for k in PER_MATCH + ("possession",):
            p[f"{k}_for"] = _avg(t["for"].get(k, []))
            if k != "possession":
                p[f"{k}_against"] = _avg(t["against"].get(k, []))
        if p["xg_for"] is not None and p["goals"] is not None:
            p["finishing"] = p["goals"] - p["xg_for"]
        prof[name] = p
    ms.STATS_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES.write_text(json.dumps(prof, indent=1, sort_keys=True), encoding="utf-8")
    listed = sorted(((n, p) for n, p in prof.items() if p["matches"] >= MIN_TEAM and p.get("xg_for") is not None),
                    key=lambda x: -((x[1]["xg_for"] or 0) - (x[1]["xg_against"] or 0)))
    L += ["", f"## Team profiles ({MIN_TEAM}+ matches with xG), strongest xG balance first", "",
          "Finishing = goals minus xG per match: a big positive number is usually luck that fades.", "",
          "| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |",
          "|---|---|---|---|---|---|---|---|"]
    for n, p in listed[:40]:
        fin = "—" if p.get("finishing") is None else f"{p['finishing']:+.2f}"
        L.append(f"| {n} | {p['league']} | {p['matches']} | {_fmt(p['xg_for'])} | {_fmt(p['xg_against'])} | "
                 f"{_fmt(p['sot_for'], 1)}–{_fmt(p['sot_against'], 1)} | {_fmt(p['possession_for'], 0)}% | "
                 f"{fin} |")
    if not listed:
        L.append("| none yet | | | | | | | |")
    L += ["", f"All {len(prof)} teams' profiles: `data/match_stats/team_profiles.json`.", ""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
