"""
13 Oct — every football game FotMob lists, covered or not, with its full
post-match team stats (Architect: "the fixtures we were not involved in ...
look at their stats ... ball recovery, every other thing"). FotMob publishes
no ball recoveries or distance covered — those read PENDING, never guessed.

    python data/study/2026-10-13/day_stats.py   → day_stats.jsonl
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2]))

from data import fotmob as fm  # noqa: E402

WANT = {"Ball possession": "possession", "Expected goals (xG)": "xg", "xG on target (xGOT)": "xgot",
        "xG open play": "xg_open", "xG set play": "xg_set", "Total shots": "shots", "Shots on target": "sot",
        "Shots inside box": "shots_box", "Big chances": "big", "Big chances missed": "big_missed",
        "Touches in opposition box": "box_touches", "Corners": "corners", "Accurate passes": "passes",
        "Accurate long balls": "long_balls", "Accurate crosses": "crosses", "Tackles": "tackles",
        "Interceptions": "interceptions", "Blocks": "blocks", "Clearances": "clearances", "Keeper saves": "saves",
        "Duels won": "duels_won", "Ground duels won": "ground_duels", "Aerial duels won": "aerials",
        "Successful dribbles": "dribbles", "Fouls committed": "fouls", "Yellow cards": "yellows", "Red cards": "reds"}


def num(x) -> float | None:
    try:
        return float(str(x).split()[0].rstrip("%"))
    except (ValueError, IndexError):
        return None


def main() -> None:
    out = HERE / "day_stats.jsonl"
    done = {json.loads(x)["id"] for x in out.read_text().splitlines()} if out.exists() else set()
    games = [m for m in fm.matches_on("2026-10-13") if m["finished"] and m["id"] not in done]
    with out.open("a", encoding="utf-8") as f:
        for m in games:
            try:
                d = fm.match_details(m["id"])
            except Exception:  # noqa: BLE001, S112 — a page that won't load is left out
                continue
            stats: dict = {}
            for grp in (((d.get("content") or {}).get("stats") or {}).get("Periods", {}).get("All", {}).get("stats") or []):
                for s in grp.get("stats") or []:
                    k = WANT.get(s.get("title"))
                    if k and k not in stats and s.get("stats") and len(s["stats"]) == 2:
                        stats[k] = [num(v) for v in s["stats"]]
            goals = [e for e in (((d.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
                     if e.get("type") == "Goal"]
            ht = [sum(1 for e in goals if e.get("isHome") and (e.get("time") or 99) <= 45),
                  sum(1 for e in goals if not e.get("isHome") and (e.get("time") or 99) <= 45)]
            f.write(json.dumps({"id": m["id"], "league": m["league"], "home": m["home"], "away": m["away"],
                                "home_id": m["home_id"], "away_id": m["away_id"], "ko": m["kickoff_utc"],
                                "ft": m["score"], "ht": ht if len(goals) == sum(m["score"]) else None,
                                "stats": stats, "recoveries": "PENDING", "distance": "PENDING",
                                "fetched": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")}) + "\n")
            time.sleep(0.25)


if __name__ == "__main__":
    main()
