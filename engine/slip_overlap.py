"""
ONE OUTCOME, ONE SLIP (Architect 2026-11-03 10:04): "two accas should not have the same match and the same
outcome. If two accas have the same match, the outcomes should be different ... so one outcome does not kill
four or five accas."

After the board's slips are built, they are walked strongest-record first (ORDER). A multi-leg slip whose
(match, outcome) legs are all new keeps its place; one that repeats a leg an earlier slip already holds is
marked `overlap` (with the repeated legs). Overlap slips stay on the board and are graded like any slip, but
no bot stakes them. The same match on a DIFFERENT outcome is allowed. One-leg slips (BTTS singles, value
singles) are not accas and are left alone. The combined megas join whole slips, so they always repeat legs
and are marked too.
"""
from __future__ import annotations

# 50+ 3-leg first (+7% graded 24 Oct-1 Nov), then positive-CLV accas (+3%), then the main accas, then the rest
ORDER = ("safe3", "clv_accas", "accas", "value", "btts", "alts", "short3", "megas")


def leg_keys(slip: dict) -> set:
    """{(match, outcome)} of a slip, from its leg detail (alt-style slips: alt_legs)."""
    out = set()
    for leg in (slip.get("leg_detail") or []) + (slip.get("alt_legs") or []):
        fx, mk = leg.get("fixture"), leg.get("market") or leg.get("key") or leg.get("pick")
        if fx and mk:
            out.add((fx.split(" (")[0], mk))
    return out


def apply(doc: dict) -> str:
    """Mark the repeating slips in a picks doc in place; returns the board note."""
    used: set = set()
    marked: dict = {}
    for sec in ORDER:
        for s in doc.get(sec) or []:
            keys = leg_keys(s)
            if len(keys) < 2:
                continue
            rep = keys & used
            if rep:
                s["overlap"] = sorted(f"{fx}: {mk}" for fx, mk in rep)
                marked[sec] = marked.get(sec, 0) + 1
            else:
                used |= keys
    for s in doc.get("combined") or []:
        s["overlap"] = ["joins whole slips"]
        marked["combined"] = marked.get("combined", 0) + 1
    if not marked:
        return "one outcome, one slip: no acca repeats a match + outcome"
    return ("one outcome, one slip: " + ", ".join(f"{n} {k}" for k, n in marked.items())
            + " slip(s) repeat a match + outcome already on a stronger slip, so they are graded on paper, not staked")
