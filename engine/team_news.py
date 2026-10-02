"""
TEAM NEWS ASSESSMENT — does a team's news hurt THIS pick?

For each pick we work out which team it depends on (its "side"): a home win,
"Home or draw", a home handicap or "home team over X goals" depend on the home
team; the mirror for away; a total-goals pick depends on neither. Then:

  * the side's MISSING SHARE = value of injured/suspended players divided by
    (value of the XI + value missing). Weighted by market value, so a missing
    star counts and a missing reserve barely does.
  * ROTATION (confirmed XI only): the confirmed XI is worth much less than the
    XI predicted when the board was built.

Levels: OK · CAUTION (side missing >= 12%, or rotated XI < 80% of predicted)
· RISK (side missing >= 25%, or rotated XI < 65%). The opponent's absences
are reported as support, never as risk. Nothing here changes a probability;
it flags, downgrades certainty, and alerts — the Architect decides.
"""
from __future__ import annotations

from typing import Optional

CAUTION_SHARE, RISK_SHARE = 0.12, 0.25
CAUTION_ROT, RISK_ROT = 0.80, 0.65


def pick_side(market: str) -> Optional[str]:
    """'home' / 'away' / None (total-goals or two-sided picks)."""
    m = market or ""
    fixed = {"1X2_HOME": "home", "1X2_AWAY": "away", "DC_1X": "home", "DC_X2": "away"}
    if m in fixed:
        return fixed[m]
    if not m.startswith("SB:"):
        return None
    try:
        mid, rest = m[3:].split("|", 1)
        spec, outcome = rest.rsplit("|", 1)
        mid = int(mid)
    except ValueError:
        return None
    o = outcome.lower()
    if mid in (1, 11, 14, 16):            # 1X2, DNB, European / Asian handicap
        if o.startswith("home"):
            return "home"
        if o.startswith("away"):
            return "away"
        return None
    if mid == 10:                          # double chance
        return {"home or draw": "home", "draw or away": "away"}.get(o)
    if mid in (19, 20):                    # team goals: over = that team, under = opponent
        team, other = ("home", "away") if mid == 19 else ("away", "home")
        return team if o.startswith("over") else other if o.startswith("under") else None
    if mid in (31, 32, 33, 34):            # clean sheet / win to nil for one team
        team, other = ("home", "away") if mid in (31, 33) else ("away", "home")
        return team if o == "yes" else other if o == "no" else None
    if mid in (546, 547, 37):              # 'Home/Draw & ...' combos
        head = o.split(" & ")[0]
        return {"home": "home", "away": "away", "home/draw": "home",
                "draw/away": "away"}.get(head)
    return None


def assess(market: str, news: Optional[dict],
           predicted_xi_value: Optional[dict] = None) -> dict:
    """{level, side, note}. `predicted_xi_value` = {'home': v, 'away': v} saved
    when the board was built, to detect rotation once the XI is confirmed."""
    if not news:
        return {"level": "NO NEWS", "side": None, "note": "no team news published"}
    side = pick_side(market)
    if side is None:
        return {"level": "OK", "side": None,
                "note": "pick does not depend on one team's lineup"}
    mine, theirs = news[side], news["away" if side == "home" else "home"]
    level, notes = "OK", []
    share = mine.get("missing_share")
    if share is not None and share >= CAUTION_SHARE:
        level = "RISK" if share >= RISK_SHARE else "CAUTION"
        names = ", ".join(m["name"] for m in mine["missing"][:3])
        notes.append(f"{mine['name']} missing {share:.0%} of value ({names})")
    if (news.get("lineup_type") == "confirmed" and predicted_xi_value
            and predicted_xi_value.get(side) and mine.get("xi_value")):
        ratio = mine["xi_value"] / predicted_xi_value[side]
        if ratio < CAUTION_ROT:
            rot = "RISK" if ratio < RISK_ROT else "CAUTION"
            level = "RISK" if "RISK" in (rot, level) else "CAUTION"
            notes.append(f"{mine['name']} rotated: confirmed XI worth {ratio:.0%} of predicted")
    o_share = theirs.get("missing_share")
    if o_share is not None and o_share >= CAUTION_SHARE:
        notes.append(f"support: {theirs['name']} missing {o_share:.0%}")
    return {"level": level, "side": side,
            "note": "; ".join(notes) or f"{mine['name']} at full strength"}
