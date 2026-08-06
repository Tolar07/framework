"""
ENGINE CONSENSUS — the ScoreGPT structure, fitted to OLP's real engines.

ScoreGPT runs five independent frontier LLMs over the same fixture, takes a
MAJORITY VOTE on the result, averages the rest, and grades every prediction
against the real result afterward. OLP has the same *structure* with real
engines instead of LLMs:

    Dixon-Coles (goals model)  -> probs       (FixtureProbabilities)
    Elo (result history)       -> elo_probs   (p_home, p_draw, p_away)
    xG (chance quality)        -> xg_probs    (p_home, p_draw, p_away)

compute_consensus() is a pure vote over whatever opinions exist for one
fixture. It does NOT blend the engines into one number — an averaged
probability would hide exactly the disagreement worth seeing (the same
reason render_fixture_block shows each engine beside the others). It reports
the majority result, the vote, and the averaged 1X2.

QUORUM (Architect, 2026-08-06): majority of AVAILABLE engines.
  2-of-2 or 2-of-3 agreement  -> consensus result
  1-of-1 (single opinion)     -> None  (a lone engine is not a consensus)
  1-1 split (no xG)           -> None  (tie)
  1-1-1                       -> None  (no majority)
  Any disagreement sets split=True — the divergence guardrail, extended to
  cover xG (the existing engine_divergence flag only compares Elo vs DC).

SCOPE (Architect): consensus is DISPLAY + BRAIN ONLY. It is shown on the
full board and persisted to the brain's predictions table for learning. It
does NOT change what is logged — DC stays canonical for paper legs, CLV,
and calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Outcome labels, in the same order as every engine's 1X2 tuple.
OUTCOMES = ("HOME", "DRAW", "AWAY")


@dataclass
class Consensus:
    """One fixture's cross-engine vote.

    `result` is the majority pick, or None when no majority exists.
    `votes` counts every available engine's pick. `avg_home/draw/away` are
    the arithmetic means of the available engines' probabilities — the
    ScoreGPT "averaged" analog, honest because the individual opinions stay
    visible beside it. `split` is True whenever the engines disagreed on the
    pick (a 2-1 vote IS a split — one engine dissented)."""
    result: Optional[str]
    votes: dict[str, int]
    n_engines: int
    agreeing: int
    avg_home: Optional[float]
    avg_draw: Optional[float]
    avg_away: Optional[float]
    split: bool


def _pick(p: tuple[float, float, float]) -> str:
    """An engine's vote = whichever 1X2 outcome it rates highest."""
    return OUTCOMES[max(range(3), key=lambda i: p[i])]


def compute_consensus(probs, elo_probs, xg_probs,
                      market_probs=None) -> Optional[Consensus]:
    """Vote over the available engines' 1X2 opinions for one fixture.

    `probs` is a FixtureProbabilities (or anything with p_home/p_draw/p_away)
    — the Dixon-Coles opinion; `elo_probs` and `xg_probs` are the
    (p_home, p_draw, p_away) tuples, or None when that engine had no opinion
    (xG is Big-5 only; Elo needs both clubs above its match floor).
    `market_probs` is the BOOKMAKER's devigged implied 1X2 (engine/markets.py
    implied_1x2) — the aggregate of real money, NOT a model. It is an equal
    fourth voter (ID413): with all four agreeing you get 4 of 4 engines. A
    fixture with no odds pulled (scan-only league) simply has no bookmaker
    opinion — never fabricated (HR35).

    Returns None when fewer than two engines had an opinion — a single
    opinion is not a consensus, and reporting one as such would fabricate an
    agreement that never happened (HR35)."""
    opinions: list[tuple[float, float, float]] = []
    if probs is not None:
        opinions.append((probs.p_home, probs.p_draw, probs.p_away))
    if elo_probs is not None:
        opinions.append(tuple(elo_probs))
    if xg_probs is not None:
        opinions.append(tuple(xg_probs))
    if market_probs is not None:
        opinions.append(tuple(market_probs))

    if len(opinions) < 2:
        return None

    votes: dict[str, int] = {}
    for p in opinions:
        pick = _pick(p)
        votes[pick] = votes.get(pick, 0) + 1

    result, agreeing = max(votes.items(), key=lambda kv: kv[1])
    # Majority requires strictly more than half the available engines.
    if agreeing <= len(opinions) / 2:
        result = None

    n = len(opinions)
    avg = [sum(p[i] for p in opinions) / n for i in range(3)]
    return Consensus(
        result=result,
        votes=votes,
        n_engines=n,
        agreeing=agreeing,
        avg_home=avg[0],
        avg_draw=avg[1],
        avg_away=avg[2],
        split=len(votes) > 1,
    )
