"""
DARTS EVENTS (framework #592, Event models #13): exact leg score (correct score), total legs and leg handicap for a
first-to-t-legs match. Total 180s, most 180s and checkouts are PENDING. RECORD-ONLY / SHADOW. Picks nothing, stakes nothing.

Idea: the board's darts win chance p (Elo) -> per-leg win chance f solving P(win a first-to-t race) = p, then the exact
negative-binomial ladder at f. Every event number is a sum over that one ladder, so it agrees with the board by
construction (the ladder's win chance IS p; test). The throw-first alternation is ignored here (a constant f); the
alternating-throw model is backtest/darts_format_study.py. Re-implemented from the idea, not copied; the ladder maths is
shared with engine/snooker_events.py.

180s and checkouts need a per-visit record (DartsOrakel returned 403 on 2026-11-12; PDC stats pages / dartsconnect are the
candidates). None is stored in the framework, so they read PENDING (HR35) and nothing is invented (HR59).
"""
from __future__ import annotations

from engine import snooker_events as se

LEG_LINES_HANDICAP = (-1.5, 1.5, 2.5)


def predict(p: float | None, legs: int | None) -> dict | None:
    """Event numbers for the side p is for in a first-to-`legs` match; None (PENDING) for missing/out-of-range input."""
    r = se.predict(p, legs)
    if r is None:
        return None
    return {"shadow": True, "target": legs, "leg_win": r["frame_win"], "match_win": r["match_win"], "score": r["score"],
            "total_legs_over": r["total_over"], "leg_handicap_cover": r["handicap_cover"],
            "total_180s": None, "most_180s": None, "checkouts": None}     # PENDING: no per-visit record is stored
