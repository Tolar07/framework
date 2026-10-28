"""
CONTEXT FACTS — to-do #7 idea 4 (RECORDED ONLY). single["context"] = {"facts": [...], "unknown": [...]}

Each fact is structured: {"fact", "source", "side", "direction", "size"}
    side        the team it is about ("home" / "away" / None for the game)
    direction   +1 the fact helps the pick, -1 it hurts the pick, 0 it can't be signed for this
                market (a totals pick and an absence) — the other side of the line gets the
                opposite sign, so "yes" and "no" are both read
    size        0..1 (share of squad value missing; 1 / 0.5 for a news RISK / CAUTION)

Only facts the framework actually has a source for are written; the rest of the checklist
(rest, travel, motivation, weather, referee, new manager, derby) is listed under "unknown" until a
source is wired, never guessed (HR35).
"""
from __future__ import annotations

import re

from engine.records._common import num, singles

CHECKLIST = ("rest", "travel", "motivation", "weather", "referee", "new_manager", "derby")
_CUP = re.compile(r"\bcup\b|pokal|coupe|copa|coppa|taca|beker|fa trophy|league trophy", re.I)


def pick_side(s: dict) -> str | None:
    """'home' / 'away' when the pick backs one team (1X2, handicap, DNB, team goals), else None."""
    key = str(s.get("market") or "")
    outcome = key.rsplit("|", 1)[-1].lower() if key.startswith("SB:") else key.lower()
    text = f"{outcome} {str(s.get('pick') or '').lower()}"
    for side in ("home", "away"):
        team = str(s.get(side) or "").lower()
        if outcome.startswith(side) or (team and team in text):
            return side
    return None


def facts(s: dict) -> dict:
    out = []
    backed = pick_side(s)

    def sign(about: str | None, good_for_about: bool) -> int:
        if backed is None or about is None:
            return 0
        return (1 if good_for_about else -1) * (1 if about == backed else -1)

    for side, share in (s.get("missing") or {}).items():
        v = num(share)
        if v:
            out.append({"fact": "squad_value_missing", "source": "fotmob", "side": side,
                        "direction": sign(side, False), "size": round(min(v, 1.0), 3)})
    level = str(s.get("news_level") or "").upper()
    for word, size in (("RISK", 1.0), ("CAUTION", 0.5)):
        if word in level:
            out.append({"fact": f"team_news_{word.lower()}", "source": "news_check", "side": None,
                        "direction": -1, "size": size, "note": str(s.get("news_note") or "")[:120]})
            break
    if _CUP.search(str(s.get("league") or "")):
        out.append({"fact": "cup_rotation_risk", "source": "league_name", "side": None,
                    "direction": 0, "size": 0.5})
    return {"facts": out, "backs": backed, "unknown": list(CHECKLIST)}


def annotate_doc(doc: dict, target: str) -> str:
    n = 0
    for s in singles(doc):
        s["context"] = facts(s)
        n += len(s["context"]["facts"])
    return f"context facts {n}"
