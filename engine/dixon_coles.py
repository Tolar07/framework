"""
OLP XDV Engine v3.1 — Dixon & Coles (1997) bivariate Poisson goal model.

Auditable by design (framework identity requirement — NOT a black-box ML model):
every number here traces to a named parameter you can inspect.

Fixes carried over from the documented bug history (see /areas/olp-xdv.md):
  BUG1 — mismatch totals no longer inflate (95%-fav teams no longer get
         absurd 4.47 expected goals / 82% O2.5); lambdas are clamped to a
         sane range post-fit.
  BUG2 — malformed probabilities (NaN, negative, >1) are normalised, not
         silently accepted.
  BUG3 — per-league home-advantage term added; home/away no longer mirror.
  BUG4 — Dixon-Coles low-score correlation (rho) correction applied, lifting
         0-0/1-1 to realistic levels for U2.5/BTTS-No markets.

Engine finds candidates only. Only logged CLV (see clv/) proves edge.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

MAX_GOALS = 10          # matrix truncation — P(>10 goals) is negligible
LAMBDA_CLAMP = (0.15, 4.5)   # BUG1: sane expected-goals range post-fit
RHO_CLAMP = (-0.3, 0.1)      # Dixon-Coles rho is small; guards against a bad fit


@dataclass
class TeamStrength:
    attack: float
    defence: float


@dataclass
class DixonColesModel:
    league: str
    home_advantage: float
    rho: float
    teams: dict[str, TeamStrength] = field(default_factory=dict)
    n_matches_fit: int = 0
    # Populated only when fit(return_raw_x=True) — uncentred parameters for
    # seeding the next walk-forward block, plus the solver's iteration count
    # so the warm-start speedup is measurable rather than assumed.
    warm_seed: Optional[tuple] = None
    n_iterations: int = -1
    # Every team name seen in the fit data, and the subset dropped for having
    # too little history. Without these the caller cannot tell WHY a team is
    # unrated, and the board ends up asserting "insufficient data" about clubs
    # the model knows perfectly well under a different name.
    seen_teams: dict[str, int] = field(default_factory=dict)   # name -> match count
    thin_teams: dict[str, int] = field(default_factory=dict)   # name -> match count

    def lambdas(self, home: str, away: str) -> Optional[tuple[float, float]]:
        """Returns (lambda_home, lambda_away) or None if either team is unrated
        (HR35 — no team, no fabricated number; caller must emit NO DATA — PENDING
        or fall back to the promoted-club / data-sufficiency handler)."""
        if home not in self.teams or away not in self.teams:
            return None
        h, a = self.teams[home], self.teams[away]
        lam_h = math.exp(h.attack + a.defence + self.home_advantage)
        lam_a = math.exp(a.attack + h.defence)
        # BUG1 fix: clamp to a plausible range instead of trusting a possibly
        # mismatch-inflated raw exponential.
        lam_h = min(max(lam_h, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
        lam_a = min(max(lam_a, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
        return lam_h, lam_a


def _dc_tau(x: int, y: int, lam_h: float, lam_a: float, rho: float) -> float:
    """Dixon-Coles low-score adjustment factor tau(x,y)."""
    if x == 0 and y == 0:
        return 1 - lam_h * lam_a * rho
    elif x == 0 and y == 1:
        return 1 + lam_h * rho
    elif x == 1 and y == 0:
        return 1 + lam_a * rho
    elif x == 1 and y == 1:
        return 1 - rho
    return 1.0


def score_matrix(lam_h: float, lam_a: float, rho: float) -> np.ndarray:
    """Full P(home=i, away=j) matrix, i,j in [0, MAX_GOALS], with the
    low-score correlation correction applied and BUG2 normalisation."""
    rho = min(max(rho, RHO_CLAMP[0]), RHO_CLAMP[1])
    ph = poisson.pmf(np.arange(MAX_GOALS + 1), lam_h)
    pa = poisson.pmf(np.arange(MAX_GOALS + 1), lam_a)
    matrix = np.outer(ph, pa)

    for x in range(2):
        for y in range(2):
            matrix[x, y] *= _dc_tau(x, y, lam_h, lam_a, rho)

    # BUG2 fix: guard against negative cells (a badly-fit rho can, in principle,
    # push tau negative) and renormalise so probabilities sum to 1.
    matrix = np.clip(matrix, 0.0, None)
    total = matrix.sum()
    if total <= 0 or not np.isfinite(total):
        raise ValueError("Degenerate score matrix — refuse to output; NO DATA — PENDING")
    matrix /= total
    return matrix


def fit(results: list, min_matches_per_team: int = 4,
        x0_teams: Optional[dict] = None, x0_globals: Optional[tuple] = None,
        return_raw_x: bool = False, half_life_days: Optional[float] = None,
        ref_date: Optional[str] = None) -> DixonColesModel:
    """Fit attack/defence/home-advantage/rho by maximum likelihood on a list of
    MatchResult (from data.football_data_source). Time weighting is OFF by
    default (see half_life_days below); pass results already filtered to the
    window you want fit on.

    Warm start (optional, for the walk-forward backtest): pass `x0_teams` as
    {team: (attack, defence)} and `x0_globals` as (home_adv, rho) from a
    previous fit. Teams absent from the seed start at zero. A week of new
    matches barely moves the parameter vector, so L-BFGS-B converges in a
    fraction of the cold-start iterations — which is what makes refitting at
    every block boundary affordable. The seed only sets the STARTING point;
    it cannot change the optimum, so results are unaffected.

    Time decay (optional): pass `half_life_days` (e.g. 365) and `ref_date`
    (ISO) to weight each match by 0.5 ** (age_days / half_life_days), the
    standard Dixon-Coles treatment. DEFAULT IS OFF (None) so existing callers
    and calibration are unchanged — turning it on is a deliberate, visible
    model change, not a silent drift."""
    from collections import defaultdict
    from datetime import date as _date

    teams = sorted({r.home_team for r in results} | {r.away_team for r in results})
    n = len(teams)
    idx = {t: i for i, t in enumerate(teams)}

    # Drop teams below the data-sufficiency floor rather than fit garbage
    # (generalised promoted-club handler).
    counts = defaultdict(int)
    for r in results:
        counts[r.home_team] += 1
        counts[r.away_team] += 1
    thin_teams = {t for t in teams if counts[t] < min_matches_per_team}

    # Per-match weights. All 1.0 unless time decay is explicitly requested.
    weights = [1.0] * len(results)
    if half_life_days:
        anchor = _date.fromisoformat(ref_date) if ref_date else max(
            _date.fromisoformat(r.date) for r in results)
        for k, r in enumerate(results):
            age = (anchor - _date.fromisoformat(r.date)).days
            weights[k] = 0.5 ** (max(age, 0) / half_life_days)

    # x = [attack_1..attack_n, defence_1..defence_n, home_adv, rho]
    def unpack(x):
        return x[:n], x[n:2 * n], x[2 * n], x[2 * n + 1]

    # Pre-extract to arrays once, so the objective is pure numpy. The previous
    # Python loop over every match, on every objective evaluation, made a
    # cross-league pooled fit (~250 teams, ~5,000 matches) computationally
    # impossible. Same mathematics — verified identical in
    # tests/engine_regression_test.py.
    _hi = np.fromiter((idx[r.home_team] for r in results), dtype=np.intp, count=len(results))
    _ai = np.fromiter((idx[r.away_team] for r in results), dtype=np.intp, count=len(results))
    _hg = np.fromiter((r.fthg for r in results), dtype=np.int64, count=len(results))
    _ag = np.fromiter((r.ftag for r in results), dtype=np.int64, count=len(results))
    _w = np.asarray(weights, dtype=float)
    # Which matches the Dixon-Coles correction actually applies to: BOTH scores
    # in {0,1}. Everything else has tau == 1 and contributes log(1) == 0.
    _m00 = (_hg == 0) & (_ag == 0)
    _m01 = (_hg == 0) & (_ag == 1)
    _m10 = (_hg == 1) & (_ag == 0)
    _m11 = (_hg == 1) & (_ag == 1)

    def neg_log_likelihood_vec(x):
        attack, defence, home_adv, rho = unpack(x)
        lam_h = np.exp(attack[_hi] + defence[_ai] + home_adv)
        lam_a = np.exp(attack[_ai] + defence[_hi])
        ll = poisson.logpmf(_hg, lam_h) + poisson.logpmf(_ag, lam_a)
        tau = np.ones_like(lam_h)
        tau[_m00] = 1.0 - lam_h[_m00] * lam_a[_m00] * rho
        tau[_m01] = 1.0 + lam_h[_m01] * rho
        tau[_m10] = 1.0 + lam_a[_m10] * rho
        tau[_m11] = 1.0 - rho
        np.maximum(tau, 1e-6, out=tau)
        return -float(np.sum(_w * (ll + np.log(tau))))

    def neg_log_likelihood(x):
        attack, defence, home_adv, rho = unpack(x)
        # BUG6 fix: rho is NOT clamped here. Clamping inside the objective made
        # it constant in rho below RHO_CLAMP[0], so the gradient vanished and
        # L-BFGS-B halted wherever it happened to enter that flat region —
        # meaning the fitted rho depended on the STARTING POINT, not the data.
        # Two fits on identical data returned rho = -0.3000 and -0.2467.
        # rho is now bounded in the optimizer instead (see `bounds=` below),
        # which keeps a real gradient at the boundary and makes the fit
        # reproducible.
        ll = 0.0
        for k, r in enumerate(results):
            i, j = idx[r.home_team], idx[r.away_team]
            # NOTE: lambdas are deliberately NOT clamped inside the likelihood.
            # Clamping here is the same pathology as BUG6 — wherever a clamp
            # binds, the objective goes flat in those parameters and the
            # optimizer loses its gradient. The optimizer BOUNDS below keep the
            # parameters in a sane range instead, and lambdas.py still clamps
            # at PREDICTION time, which is where BUG1's guard actually belongs.
            lam_h = math.exp(attack[i] + defence[j] + home_adv)
            lam_a = math.exp(attack[j] + defence[i])
            # BUG8 fix: pass the ACTUAL scores. This previously passed
            # min(goals, 1), which collapses every scoreline onto {0,1}x{0,1} —
            # so a 3-2 was handed to tau as (1,1) and received the same
            # low-score correction as a real 1-1, and a 2-0 was treated as 1-0.
            # tau(x,y) is defined as 1.0 outside {0,1}x{0,1}; the correction was
            # being wrongly applied to 71% of matches in a typical season,
            # biasing rho and, through it, every fitted parameter.
            tau = _dc_tau(r.fthg, r.ftag, lam_h, lam_a, rho)
            tau = max(tau, 1e-6)
            ll += weights[k] * (poisson.logpmf(r.fthg, lam_h)
                                 + poisson.logpmf(r.ftag, lam_a)
                                 + math.log(tau))
        return -ll

    x0 = np.zeros(2 * n + 2)
    x0[2 * n] = 0.25   # initial home-advantage guess
    x0[2 * n + 1] = -0.1  # initial rho guess

    # Warm start: seed known teams from the previous fit, leave new teams at 0.
    if x0_teams:
        for t, i in idx.items():
            seed = x0_teams.get(t)
            if seed is not None:
                x0[i], x0[n + i] = seed
    if x0_globals:
        x0[2 * n], x0[2 * n + 1] = x0_globals

    # Constrain mean attack to 0 for identifiability (standard DC constraint)
    # via a simple post-hoc centering rather than a solver constraint, to keep
    # this auditable and dependency-light.
    # Bound the parameters in the OPTIMIZER, not inside the objective. Attack
    # and defence are loosely bounded (they are log-scale strengths; +/-3 is
    # far outside anything football produces) purely to keep lambdas in a sane
    # range; rho carries its documented Dixon-Coles range.
    # Attack/defence bounded at +/-2.0: with home advantage that caps a lambda
    # at exp(2+2+1) ~ 148, far outside anything football produces but tight
    # enough that poisson.logpmf stays numerically well behaved. Real fitted
    # values sit within about +/-0.7, so these never bind in practice — they
    # exist to stop the optimizer wandering, not to shape the answer.
    bounds = ([(-2.0, 2.0)] * (2 * n)
              + [(-1.0, 1.0)]        # home advantage
              + [RHO_CLAMP])         # rho
    res = minimize(neg_log_likelihood_vec, x0, method="L-BFGS-B",
                    bounds=bounds, options={"maxiter": 500})

    attack, defence, home_adv, rho = unpack(res.x)

    # BUG7 fix — identifiability centering must be SCORING-NEUTRAL.
    #
    # Previously this did `attack = attack - attack.mean()` and stopped there.
    # Because lambda = exp(attack_i + defence_j + home_adv), subtracting the
    # mean m from every attack multiplies EVERY lambda by exp(-m) — it shifts
    # the model's whole scoring level. With m = +0.047 on Scottish 2024/25
    # that scaled all expected goals by 0.954, and the model predicted 2.786
    # goals per game on data that actually produced 2.961.
    #
    # Downstream that understated every goals market and, by complement,
    # OVERSTATED Under 2.5 and BTTS-No — precisely the markets master doc
    # Section 5 says the Architect trades.
    #
    # Adding the same m back to every defence term leaves attack_i + defence_j
    # unchanged, so predictions are exactly invariant while attack is still
    # centred for interpretability.
    m_attack = attack.mean()
    attack = attack - m_attack
    defence = defence + m_attack
    rho = min(max(rho, RHO_CLAMP[0]), RHO_CLAMP[1])

    model = DixonColesModel(league=results[0].league if results else "unknown",
                             home_advantage=float(home_adv), rho=float(rho),
                             n_matches_fit=len(results))
    model.seen_teams = {t: counts[t] for t in teams}
    model.thin_teams = {t: counts[t] for t in thin_teams}
    for t in teams:
        if t in thin_teams:
            continue  # unrated — lambdas() will correctly return None for them
        model.teams[t] = TeamStrength(attack=float(attack[idx[t]]),
                                       defence=float(defence[idx[t]]))

    # Uncentred parameters for seeding the next warm start. Centring is applied
    # above for identifiability; seeding wants the raw solver output back.
    if return_raw_x:
        raw_attack, raw_defence, _, _ = unpack(res.x)
        model.warm_seed = ({t: (float(raw_attack[idx[t]]), float(raw_defence[idx[t]]))
                            for t in teams},
                           (float(home_adv), float(rho)))
        model.n_iterations = int(getattr(res, "nit", -1))
    return model


def unrated_reason(model: DixonColesModel, team: str,
                    min_matches_per_team: int = 4) -> Optional[str]:
    """Why is this team unrated? Returns None if it IS rated.

    `lambdas()` returns a bare None for three genuinely different situations,
    and the board used to render all three as "team unrated — insufficient
    data". For a club the model holds a full season on, that sentence is
    simply false — the real cause is usually that the fixtures feed spells the
    name differently. Reporting the wrong reason is its own HR35 failure: the
    board is asserting something untrue about its own state.

    The three cases are kept distinct, and the third is deliberately NOT
    guessed apart, because from inside the model an unmapped name and a
    genuinely new club look identical — so both are named, and the caller
    surfaces the roster so a human can see which it is at a glance."""
    if team in model.teams:
        return None
    if team in model.thin_teams:
        n = model.thin_teams[team]
        return (f"'{team}' has only {n} match{'es' if n != 1 else ''} in the fit "
                f"window, below the {min_matches_per_team}-match floor — rated on "
                f"too little data to trust")
    return (f"'{team}' does not appear in the fitted data at all — either the "
            f"fixtures source spells it differently from the results source "
            f"(a name-mapping gap, NOT missing data), or it is newly promoted "
            f"with no prior-season history")


@dataclass
class FixtureProbabilities:
    home_team: str
    away_team: str
    lambda_home: float
    lambda_away: float
    p_home: float
    p_draw: float
    p_away: float
    p_over_15: float
    p_over_25: float
    p_over_35: float
    p_btts_yes: float


def predict(model: DixonColesModel, home: str, away: str) -> Optional[FixtureProbabilities]:
    """Returns None (never a guessed number) if either team is unrated — HR35."""
    lambdas = model.lambdas(home, away)
    if lambdas is None:
        return None
    lam_h, lam_a = lambdas
    m = score_matrix(lam_h, lam_a, model.rho)

    p_home = float(np.tril(m, -1).sum())
    p_away = float(np.triu(m, 1).sum())
    p_draw = float(np.trace(m))

    goal_totals = np.add.outer(np.arange(MAX_GOALS + 1), np.arange(MAX_GOALS + 1))
    p_over = lambda line: float(m[goal_totals > line].sum())

    btts_no = float(m[0, :].sum() + m[:, 0].sum() - m[0, 0])
    p_btts_yes = 1 - btts_no

    # Probabilities are kept at FULL precision. Rounding them to 4dp here made
    # 1X2 sum to 0.9999 instead of 1.0 — a small BUG2 violation (probabilities
    # that don't sum to 1 being accepted silently), which previously escaped
    # the smoke test only because one particular set of numbers happened to
    # round cleanly. Rendering rounds for display; the model does not.
    # lambda_* stay rounded: they are reported figures, not inputs to anything.
    return FixtureProbabilities(
        home_team=home, away_team=away,
        lambda_home=round(lam_h, 3), lambda_away=round(lam_a, 3),
        p_home=p_home, p_draw=p_draw, p_away=p_away,
        p_over_15=p_over(1), p_over_25=p_over(2),
        p_over_35=p_over(3), p_btts_yes=p_btts_yes,
    )
