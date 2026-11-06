"""Record-only study: which hockey leagues beyond the NHL could get their own model (#338).

Reads the shadow board's graded record (output/ice_hockey/ih_*.json, via engine.ice_hockey.load_all)
and, per league, counts games seen/graded and compares the exchange's fair chance with the plain
league win rate (Brier). A league is READY for its own goals model only with MIN_GAMES graded games;
until then it reads PENDING (HR35). Changes no pick, stake, price or threshold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIN_GAMES = 300  # roughly one league season; below this a team-strength fit is noise


def study(docs: list[tuple[str, dict]]) -> dict:
    """docs = ice_hockey.load_all() output. Returns {league: stats}."""
    out: dict[str, dict] = {}
    for _day, doc in docs:
        for g in (doc.get("games") or {}).values():
            lg = g.get("comp") or g.get("country") or "?"
            b = out.setdefault(lg, {"seen": 0, "graded": 0, "fair_n": 0, "fair_brier": 0.0, "won": 0})
            b["seen"] += 1
            if not g.get("result"):
                continue
            b["graded"] += 1
            for s in (g.get("sides") or {}).values():
                fair = (s.get("first") or {}).get("fair")
                if s.get("won") is None or fair is None:
                    continue
                b["fair_n"] += 1
                b["won"] += s["won"]
                b["fair_brier"] += (fair - s["won"]) ** 2
    for b in out.values():
        n = b["fair_n"]
        b["fair_brier"] = round(b["fair_brier"] / n, 4) if n else None
        rate = b["won"] / n if n else None
        b["rate_brier"] = round(rate * (1 - rate), 4) if rate is not None else None
        b["status"] = "READY" if b["graded"] >= MIN_GAMES else "PENDING"
    return out


def render(res: dict) -> str:
    lines = ["# Hockey leagues beyond the NHL: can each get its own model? (record only)", "",
             f"READY needs {MIN_GAMES} graded games; fewer reads PENDING.", "",
             "| League | Seen | Graded | Sides with exchange price | Brier: exchange | Brier: league rate | Status |",
             "|---|---|---|---|---|---|---|"]
    for lg, b in sorted(res.items(), key=lambda kv: -kv[1]["graded"]):
        lines.append(f"| {lg} | {b['seen']} | {b['graded']} | {b['fair_n']} | "
                     f"{b['fair_brier'] if b['fair_brier'] is not None else 'PENDING'} | "
                     f"{b['rate_brier'] if b['rate_brier'] is not None else 'PENDING'} | {b['status']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    from engine import ice_hockey as ih
    res = study(ih.load_all())
    (ROOT / "backtest" / "ICE_HOCKEY_LEAGUES.md").write_text(render(res), encoding="utf-8")
    print(json.dumps({k: v["status"] for k, v in res.items()}))


if __name__ == "__main__":
    main()
