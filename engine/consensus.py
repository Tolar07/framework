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
    `votes` counts every available engine's pick (weighted tallies when
    engine_weights are active — floats, not integers). `avg_home/draw/away`
    are the means of the available engines' probabilities (weighted when
    weights are active) — the ScoreGPT "averaged" analog, honest because the
    individual opinions stay visible beside it. `split` is True whenever the
    engines disagreed on the pick (a 2-1 vote IS a split — one engine
    dissented).

    Phase 3.3: when engine_weights are passed, each engine's say is scaled by
    its historical performance (clv/clv_logger.ensemble_weights). `weighted`
    is True then and `weight_used` records the exact weights, so the board can
    say so — nothing is weighted silently. With no weights (or all 1.0) this
    is bit-identical to the classic equal-vote consensus."""
    result: Optional[str]
    votes: dict[str, float]
    n_engines: int
    agreeing: int
    avg_home: Optional[float]
    avg_draw: Optional[float]
    avg_away: Optional[float]
    split: bool
    weighted: bool = False
    weight_used: dict | None = None
    unweighted_result: str | None = None


def _pick(p: tuple[float, float, float]) -> str:
    """An engine's vote = whichever 1X2 outcome it rates highest."""
    return OUTCOMES[max(range(3), key=lambda i: p[i])]


def compute_consensus(probs, elo_probs, xg_probs,
                      market_probs=None,
                      engine_weights: dict | None = None) -> Optional[Consensus]:
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

    `engine_weights` (Phase 3.3) is the {engine: weight} map from
    clv/clv_logger.ensemble_weights(). When at least one available engine
    carries a weight other than 1.0, votes and the averaged 1X2 are WEIGHTED
    by it and `weighted=True` — the CLV-proven engine's opinion counts more,
    the losing one's less. A missing key is treated as weight 1.0. When every
    weight is 1.0 (or the map is None) the result is bit-identical to the
    classic equal-vote consensus — evidence-gated, so an unproven record never
    moves it.

    Returns None when fewer than two engines had an opinion — a single
    opinion is not a consensus, and reporting one as such would fabricate an
    agreement that never happened (HR35)."""
    opinions: list[tuple[str, tuple[float, float, float]]] = []
    if probs is not None:
        opinions.append(("dc", (probs.p_home, probs.p_draw, probs.p_away)))
    if elo_probs is not None:
        opinions.append(("elo", tuple(elo_probs)))
    if xg_probs is not None:
        opinions.append(("xg", tuple(xg_probs)))
    if market_probs is not None:
        opinions.append(("bookmaker", tuple(market_probs)))

    if len(opinions) < 2:
        return None

    # Weighting is active only when at least one available engine earned it.
    use_weights = engine_weights is not None and any(
        engine_weights.get(name, 1.0) != 1.0 for name, _ in opinions)
    weights = ({name: engine_weights.get(name, 1.0) for name, _ in opinions}
               if use_weights else None)

    # The plain (unweighted) majority, recorded for honesty so the board can
    # say when CLV weighting flips the pick.
    plain_votes: dict[str, float] = {}
    votes: dict[str, float] = {}
    for name, p in opinions:
        pick = _pick(p)
        w = weights[name] if weights else 1
        plain_votes[pick] = plain_votes.get(pick, 0) + 1
        votes[pick] = votes.get(pick, 0) + w
    unweighted_result, plain_majority = max(plain_votes.items(), key=lambda kv: kv[1])
    if plain_majority <= len(opinions) / 2:
        unweighted_result = None

    result, majority = max(votes.items(), key=lambda kv: kv[1])
    total_say = sum(weights.values()) if weights else len(opinions)
    if majority <= total_say / 2:
        result = None

    # `agreeing` keeps the classic meaning: the number of engines on the
    # plurality outcome (the top tally). On a tie result is None but agreeing
    # is still the plurality count. When weighted, it is the engine COUNT on
    # the weighted plurality, so "N of M engines" stays a plain count.
    plurality = max(votes.items(), key=lambda kv: kv[1])[0]
    if weights:
        agreeing = sum(1 for name, p in opinions if _pick(p) == plurality)
    else:
        agreeing = int(votes[plurality])

    n = len(opinions)
    if weights:
        denom = sum(weights.values())
        avg = [sum(weights[name] * p[i] for name, p in opinions) / denom
               for i in range(3)]
    else:
        avg = [sum(p[i] for name, p in opinions) / n for i in range(3)]
    return Consensus(
        result=result,
        votes=votes,
        n_engines=n,
        agreeing=agreeing,
        avg_home=avg[0],
        avg_draw=avg[1],
        avg_away=avg[2],
        split=len(votes) > 1,
        weighted=use_weights,
        weight_used=dict(weights) if weights else None,
        unweighted_result=unweighted_result,
    )
