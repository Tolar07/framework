"""
ELO RATING SYSTEM — ID82, ported from DataEngine v277.1 and made auditable.

WHY A SECOND ENGINE
  Dixon-Coles rates attack and defence WITHIN a pool where everyone plays
  everyone. That is what makes its numbers comparable — and it is exactly why
  it cannot compare a Dutch club to an English one: the two scales were never
  linked. Pooling continental matches helps, but a club's 38 domestic results
  still swamp its 8 European ones, which is how Celtic ended up rated above
  Real Madrid.

  Elo has no such problem. A rating is a single number updated from results in
  ANY competition, so when a Dutch club beats an English one both ratings move
  on the same scale immediately. Cross-league comparability is structural, not
  something bolted on afterwards.

  It is also GENUINELY INDEPENDENT of Dixon-Coles — different inputs (results
  and margins, not goal counts), different mathematics (sequential updating,
  not maximum likelihood), different failure modes. Two engines that fail
  differently is what ID403 means by independent factors. Sixteen tipster
  sites that all price off the same public information are not.

LEAKAGE
  Elo is sequential by construction: a rating at time T is a function only of
  matches before T. `rate_through()` returns a snapshot at a cut date, so a
  prediction can never see its own result. This is a stronger guarantee than
  Dixon-Coles gets, where the fit window has to be policed by hand.

WHAT IT IS NOT
  Elo knows about results, not goals. It cannot price Over/Under or BTTS, and
  this module does not pretend otherwise — those markets return None. Its jobs
  are cross-league 1X2 and, more valuably, disagreeing with Dixon-Coles.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ID82 constants, as specified in DataEngine v277.1:
#   E(home) = 1/(1+10^((ELO_away - ELO_home - 65)/400))
#   New ELO = Old + 20 x GD_mod x (Result - E)
HOME_ADVANTAGE_ELO = 65.0
K_FACTOR = 20.0
BASE_RATING = 1500.0

# Fallback draw curve, P(draw) = a * exp(-b * gap). These are the coefficients
# actually FITTED on the 4,350-match pooled European dataset, reused as the
# default when a smaller sample can't support its own fit. A gap-dependent
# default matters: draws genuinely become rarer as a mismatch widens.
DEFAULT_DRAW_A = 0.322
DEFAULT_DRAW_B = 0.00155

# No football result is impossible. Publishing 0% would be a fabricated
# certainty, so every outcome carries this floor before renormalisation.
MIN_OUTCOME_PROB = 0.012


def goal_difference_modifier(gd: int) -> float:
    """Margin-of-victory weighting.

    ID82 specifies a `GD_mod` term without defining it, so this uses the
    standard World Football Elo ladder — stated here explicitly rather than
    silently chosen, because it materially affects how fast ratings move:

        GD 0-1 -> 1.00      GD 2 -> 1.50      GD 3 -> 1.75
        GD 4+  -> 1.75 + (GD - 3) / 8

    The taper matters: without it a 7-0 would move ratings absurdly, and a
    club that runs up scores against weak domestic opposition — precisely the
    Celtic problem this module exists to fix — would inflate all over again.
    """
    gd = abs(gd)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    if gd == 3:
        return 1.75
    return 1.75 + (gd - 3) / 8.0


STATE_VERSION = 1  # bumped whenever the on-disk shape changes


@dataclass
class EloModel:
    ratings: dict[str, float] = field(default_factory=dict)
    matches_seen: dict[str, int] = field(default_factory=dict)
    n_matches: int = 0
    last_date: Optional[str] = None
    # Empirical draw curve, fitted from real results rather than assumed.
    _draw_a: float = 0.0
    _draw_b: float = 0.0

    # ----- persistence ------------------------------------------------------
    def to_payload(self) -> dict:
        """The full on-disk state as a JSON-able dict (the single source of
        truth for persistence). The brain and save() both use this shape."""
        return {
            "version": STATE_VERSION,
            "n_matches": self.n_matches,
            "last_date": self.last_date,
            "draw_a": self._draw_a,
            "draw_b": self._draw_b,
            "ratings": self.ratings,
            "matches_seen": self.matches_seen,
        }

    @classmethod
    def from_payload(cls, blob: dict) -> "EloModel":
        """Restore an EloModel from a to_payload() dict.

        Refuses (rather than adapts) a snapshot from a different STATE_VERSION.
        HR35: adapting silently would mean guessing what the missing fields
        used to mean, and a wrong guess would then propagate into every
        rating computed against it."""
        if blob.get("version") != STATE_VERSION:
            raise ValueError(
                f"Elo snapshot has version {blob.get('version')!r}, this build "
                f"expects {STATE_VERSION}. Refusing to load rather than guess "
                f"what the missing fields used to mean.")
        m = cls()
        m.ratings = dict(blob["ratings"])
        m.matches_seen = {k: int(v) for k, v in blob["matches_seen"].items()}
        m.n_matches = int(blob["n_matches"])
        m.last_date = blob.get("last_date")
        m._draw_a = float(blob.get("draw_a", 0.0))
        m._draw_b = float(blob.get("draw_b", 0.0))
        return m

    def save(self, path: str | Path) -> None:
        """Write ratings and draw-curve state to disk as plain JSON.

        Whole file is rewritten; the state is small (a few hundred floats)
        and doing it atomically-ish beats risking a partial JSON on a crash
        mid-write. Version stamped so a future change to the on-disk shape
        can refuse to load an old snapshot instead of silently guessing."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_payload(), sort_keys=True, indent=2),
                     encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "EloModel":
        """Restore an EloModel from a `save()` snapshot (see from_payload)."""
        return cls.from_payload(json.loads(Path(path).read_text(encoding="utf-8")))

    def export_csv(self, path: str | Path) -> None:
        """Human-readable rating table, sorted strongest first.

        For the Architect's eyes, not for reloading. `save()` is the round-trip
        path; this is what you open in Excel to sanity-check the top of the
        table looks like the world actually is."""
        import csv
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["rank", "team", "elo", "matches_seen"])
            rows = sorted(self.ratings.items(), key=lambda kv: -kv[1])
            for i, (team, rating) in enumerate(rows, 1):
                w.writerow([i, team, round(rating, 2),
                             self.matches_seen.get(team, 0)])

    def rating(self, team: str) -> float:
        return self.ratings.get(team, BASE_RATING)

    def expected(self, home: str, away: str) -> float:
        """E(home) — expected SCORE (win=1, draw=0.5), not P(home win)."""
        gap = self.rating(away) - self.rating(home) - HOME_ADVANTAGE_ELO
        return 1.0 / (1.0 + 10 ** (gap / 400.0))

    def update(self, home: str, away: str, fthg: int, ftag: int,
               weight: float = 1.0) -> None:
        """Apply one match's result to both ratings (zero-sum, as Elo is).

        `weight` scales the update — 1.0 is the classic Elo move. A weight > 1
        makes a match speak louder than its neighbours, which is how the
        cross-league blend (engine/cross_league.py) lets a club's handful of
        European matches count more than its dozens of domestic ones when a
        continental fixture is being priced. The zero-sum property is
        preserved because the whole delta is scaled, home and away equally."""
        e = self.expected(home, away)
        result = 1.0 if fthg > ftag else (0.5 if fthg == ftag else 0.0)
        delta = K_FACTOR * weight * goal_difference_modifier(fthg - ftag) * (result - e)
        self.ratings[home] = self.rating(home) + delta
        self.ratings[away] = self.rating(away) - delta   # zero-sum
        self.matches_seen[home] = self.matches_seen.get(home, 0) + 1
        self.matches_seen[away] = self.matches_seen.get(away, 0) + 1
        self.n_matches += 1

    # ---------------- 1X2 ----------------

    def probabilities(self, home: str, away: str,
                       min_matches: int = 6) -> Optional[tuple[float, float, float]]:
        """(P_home, P_draw, P_away), or None if either club is too thin.

        Elo yields an expected SCORE, which conflates a win with two draws. To
        split it we need P(draw), and rather than assume a constant this uses a
        curve FITTED to real results as a function of the rating gap — draws
        genuinely become rarer as a mismatch widens, and a fixed 26% would
        misprice both ends of the range.
        After burn-in every club carries a seeded rating, so `matches_seen`
        counts only the final pass. A club is judged thin on either measure.
        ID414: a club with a CROSS-LEAGUE seed (rating != BASE_RATING) but fewer
        than min_matches in THIS division is NOT refused — the seed IS a rating,
        just from the pooled graph. This widens coverage for promoted/new clubs
        without fabricating ratings."""
        home_rated = self.rating(home) != BASE_RATING
        away_rated = self.rating(away) != BASE_RATING
        if not home_rated and self.matches_seen.get(home, 0) < min_matches:
            return None
        if not away_rated and self.matches_seen.get(away, 0) < min_matches:
            return None
        e = self.expected(home, away)
        gap = abs(self.rating(home) + HOME_ADVANTAGE_ELO - self.rating(away))
        # A gap-dependent default, used when there weren't enough matches to
        # fit the curve (a single league rarely reaches the sample floor).
        # A FLAT prior was the bug here: held at 0.26 through a big mismatch it
        # squeezed the underdog to 0%, which asserts impossibility.
        a = self._draw_a if self._draw_b else DEFAULT_DRAW_A
        b = self._draw_b if self._draw_b else DEFAULT_DRAW_B
        p_draw = min(max(a * math.exp(-b * gap), 0.05), 0.40)
        # E = P_home + 0.5 * P_draw  =>  P_home = E - 0.5 * p_draw
        p_home = e - 0.5 * p_draw
        p_away = 1.0 - p_home - p_draw
        # HR35: never publish a 0% — no football result is impossible. Each
        # outcome carries a floor, and the set is renormalised.
        p_home = max(p_home, MIN_OUTCOME_PROB)
        p_away = max(p_away, MIN_OUTCOME_PROB)
        p_draw = max(p_draw, MIN_OUTCOME_PROB)
        total = p_home + p_draw + p_away
        return p_home / total, p_draw / total, p_away / total


def _fit_draw_curve(model: EloModel, samples: list[tuple[float, bool]]) -> None:
    """P(draw) = a * exp(-b * gap), fitted by least squares on binned data.

    Measured, not assumed. If there aren't enough samples the curve is left
    off and probabilities() falls back to a flat prior, flagged by _draw_b=0."""
    if len(samples) < 200:
        return
    bins: dict[int, list[bool]] = {}
    for gap, drew in samples:
        bins.setdefault(int(gap // 50), []).append(drew)
    xs, ys = [], []
    for b, vals in sorted(bins.items()):
        if len(vals) < 25:
            continue
        rate = sum(vals) / len(vals)
        if rate <= 0:
            continue
        xs.append(b * 50 + 25)
        ys.append(math.log(rate))
    if len(xs) < 3:
        return
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    model._draw_a = math.exp(my - slope * mx)
    model._draw_b = -slope


BURN_IN_PASSES = 6


def rate_through(results: list, cut_date: Optional[str] = None,
                  fit_draws: bool = True,
                  burn_in: int = BURN_IN_PASSES,
                  seed_from: Optional["EloModel | str | Path"] = None,
                  match_weight: Callable | None = None,
                  scorer: Callable | None = None) -> EloModel:
    """Process matches in DATE ORDER up to (but excluding) `cut_date`.

    Phase 3.2 additions (both optional, both default to the classic engine):
      `match_weight` — a callable(match) -> float scaling each update (see
      EloModel.update). Used by the cross-league blend to let continental
      matches count `w`-fold in a pooled fit; None means 1.0 everywhere.
      `scorer` — a callable(model, match) invoked on the final sequential
      pass, immediately BEFORE the match is applied to the ratings. This is
      the leak-free out-of-sample hook (a prediction can never see its own
      result) that the blend-weight optimiser in cross_league.py uses to score
      each continental match from ratings that existed before it.

    Pass results from every competition together — that is the whole point.
    A continental match between clubs from different leagues updates both
    ratings on one scale, which is the cross-league link Dixon-Coles cannot
    make on its own.

    BURN-IN. Everyone starts at 1500, so on a single pass a club that dominates
    a weak league farms rating off opponents assumed to be average, and the
    league levels never separate. Re-running the same history with the previous
    pass's final ratings as the new starting point lets strength information
    propagate backwards through the season. Measured on the 2024 Champions
    League phase, predicting each match from ratings that existed BEFORE it:

        1 pass   Brier 0.5545   top-pick 57.3%
        3 passes Brier 0.4482   top-pick 68.1%
        6 passes Brier 0.4306   top-pick 67.4%

    (Uniform 1/3 guessing scores 0.667.) Burn-in only sets the starting point
    for the final sequential pass — it cannot leak a result into its own
    prediction, because that pass still walks the fixtures in date order.

    Incremental use (opt-in, ratified 2026-08-04):
      `seed_from` may be an existing EloModel, or a path to one saved with
      EloModel.save(). Only matches strictly newer than the snapshot's
      last_date are consumed, and burn-in is skipped — a fresh snapshot has
      already burned in.

      HONEST LIMIT — the incremental path is NOT identical to a fresh full
      run over the extended data. Burn-in re-plays the entire history 6 times
      so league-strength information propagates backwards; splitting the data
      across a save/load can't reproduce that. Two matched runs on the same
      final data can differ by tens of Elo points at the strongest clubs.
      That is expected mathematics, not a bug. What the incremental path
      buys is CHEAPNESS during the season, not parity with a scratch fit.
      Do a full cold refit periodically (~every 4 weeks) to reabsorb any
      drift; running one on demand is a matter of calling this function
      without seed_from.

      A snapshot passed in and no new matches to consume returns the snapshot
      unchanged (this IS a guaranteed invariant and is tested)."""
    # Resolve seed. Accepts a model, a path, or None (cold start).
    if isinstance(seed_from, (str, Path)):
        snap: Optional[EloModel] = EloModel.load(seed_from)
    else:
        snap = seed_from

    if snap is not None:
        # Incremental path: skip burn-in (snapshot has already converged) and
        # only ingest matches strictly after its cut-off. Using strict `>`
        # avoids double-counting a match played exactly on last_date.
        cut = snap.last_date
        ordered = sorted(
            (r for r in results
             if (not cut_date or r.date < cut_date)
             and (cut is None or r.date > cut)),
            key=lambda r: r.date)
        model = EloModel()
        model.ratings = dict(snap.ratings)
        model.matches_seen = dict(snap.matches_seen)
        model.n_matches = snap.n_matches
        model.last_date = snap.last_date
        model._draw_a, model._draw_b = snap._draw_a, snap._draw_b
    else:
        # Cold start: multi-pass burn-in so weak-league dominance doesn't
        # farm ratings from average-rated opponents.
        ordered = sorted(
            (r for r in results if not cut_date or r.date < cut_date),
            key=lambda r: r.date)
        seed: dict[str, float] = {}
        for _ in range(max(0, burn_in - 1)):
            warm = EloModel()
            warm.ratings = dict(seed)
            for r in ordered:
                _w = match_weight(r) if match_weight else 1.0
                warm.update(r.home_team, r.away_team, r.fthg, r.ftag, weight=_w)
            seed = dict(warm.ratings)
        model = EloModel()
        model.ratings = dict(seed)

    samples: list[tuple[float, bool]] = []
    for r in ordered:
        # Record the gap BEFORE updating, so the draw curve is fitted on
        # genuine out-of-sample predictions rather than hindsight.
        if model.matches_seen.get(r.home_team, 0) >= 6 and \
           model.matches_seen.get(r.away_team, 0) >= 6:
            gap = abs(model.rating(r.home_team) + HOME_ADVANTAGE_ELO
                      - model.rating(r.away_team))
            samples.append((gap, r.fthg == r.ftag))
        # The leak-free out-of-sample hook (Phase 3.2): same moment as the draw
        # sample, BEFORE the result touches the ratings.
        if scorer is not None:
            scorer(model, r)
        _w = match_weight(r) if match_weight else 1.0
        model.update(r.home_team, r.away_team, r.fthg, r.ftag, weight=_w)
        model.last_date = r.date
    if fit_draws and samples:
        # A short incremental slice can be too thin to refit the curve on its
        # own; only overwrite the inherited curve when the fresh fit succeeds.
        # If it doesn't, the snapshot's curve stays in place — a stale curve is
        # far better than reverting to the flat prior.
        prev_a, prev_b = model._draw_a, model._draw_b
        _fit_draw_curve(model, samples)
        if not model._draw_b:
            model._draw_a, model._draw_b = prev_a, prev_b
    return model


def divergence(elo_probs: Optional[tuple[float, float, float]],
                dc_probs, threshold_pp: float = 12.0) -> Optional[str]:
    """Where the two engines disagree materially, say so.

    This is the real payoff of a second engine. Dixon-Coles and Elo use
    different inputs and different mathematics, so agreement is meaningful and
    disagreement is a genuine warning — unlike sixteen prediction sites all
    reading the same public information, where agreement is guaranteed and
    tells you nothing (ID130's convergence model)."""
    if elo_probs is None or dc_probs is None:
        return None
    gaps = [
        ("home win", (elo_probs[0] - dc_probs.p_home) * 100),
        ("draw", (elo_probs[1] - dc_probs.p_draw) * 100),
        ("away win", (elo_probs[2] - dc_probs.p_away) * 100),
    ]
    worst = max(gaps, key=lambda g: abs(g[1]))
    if abs(worst[1]) < threshold_pp:
        return None
    return (f"ENGINE DIVERGENCE: Elo and Dixon-Coles differ by "
            f"{worst[1]:+.0f}pp on {worst[0]} (Elo "
            f"{elo_probs[0]:.0%}/{elo_probs[1]:.0%}/{elo_probs[2]:.0%} vs "
            f"Dixon-Coles {dc_probs.p_home:.0%}/{dc_probs.p_draw:.0%}/"
            f"{dc_probs.p_away:.0%}). Two independent engines disagreeing is a "
            f"REVIEW signal, not an edge — treat this fixture as lower "
            f"confidence until the disagreement is understood.")
