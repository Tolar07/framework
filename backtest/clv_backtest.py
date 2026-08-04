"""
CLV BACKTEST — the validation gate the automation blueprint (Section 4.1) puts
before everything else: *"If it can't show positive CLV on a season that
already happened, automation changes nothing."*

WHAT THIS DOES
  Runs the framework's OWN engine (engine/dixon_coles.py — not a
  reimplementation) walk-forward over a completed season, selects paper legs
  where the model disagrees with the opening price by more than a pre-declared
  threshold, and compares that entry price to the closing price.

WHAT IT DOES NOT DO
  It does not stake. It does not prove an edge. It reports a measurement with
  its coverage and its caveats attached, and a large part of this file exists
  to stop that measurement from flattering itself.

THE FOUR WAYS A CLV BACKTEST LIES, AND WHAT IS DONE ABOUT EACH
  1. LOOK-AHEAD. Fitting on a season then "predicting" inside it leaks
     outcomes. Here a match on date T is predicted by a model fitted strictly
     on matches BEFORE the block cut, and the leakage assertion is a test.
  2. CROSS-BOOK PAIRING. Pairing one book's opening price with another's close
     manufactures CLV out of a book-to-book spread nobody could trade. The
     parser (data/football_data_source.py) resolves each line all-or-nothing
     from a single book.
  3. SILENT DROPOUT. Quietly skipping legs whose closing price is missing
     biases the mean, because closes are likeliest to be missing exactly where
     the line moved. Every exclusion is counted and reported (HR35).
  4. MARGIN DRIFT. If bookmaker overround shrinks from open to close, every
     leg shows positive CLV with zero model skill. Overround is measured at
     both ends, and a random-selection placebo run is available as the control.

HR35 throughout: a missing price is NO DATA — PENDING and is counted, never
estimated, never filled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from scipy.optimize import brentq
from scipy.stats import poisson

from data.football_data_source import load_league, MatchResult, DEFAULT_BOOK_PREFERENCE
from engine.dixon_coles import fit, predict, DixonColesModel, TeamStrength
from engine.mes import mes_numeric
from engine.softness import softness_tier
from clv.clv_logger import LoggedLeg, CLVLog, compute_clv, BACKTEST_PHASE, DEFAULT_LOG_PATH

RESULTS_DIR = Path(__file__).parent / "results"
MODEL_CACHE_DIR = Path(__file__).parent / "cache" / "models"

# Bumped whenever engine behaviour changes, so cached models fitted under old
# behaviour are never silently reused. 2 = rho bounded in optimizer (BUG6).
FIT_VERSION = 4  # 4 = BUG8 tau fix + lambda clamp out of the likelihood

MARKETS_1X2 = ("1X2_H", "1X2_D", "1X2_A")
MARKETS_OU = ("O2.5", "U2.5")
MARKET_O15_DERIVED = "O1.5_DERIVED"


@dataclass(frozen=True)
class BacktestConfig:
    leagues: tuple[str, ...]
    carry_in_season: str            # fits start with this completed season
    test_season: str                # the season legs are placed in
    refit_every_days: int = 7
    min_history_matches: int = 60
    max_history_matches: int = 400
    min_matches_per_team: int = 6
    markets: tuple[str, ...] = MARKETS_1X2 + MARKETS_OU + (MARKET_O15_DERIVED,)
    min_mes: float = 0.02           # PRE-DECLARED. See note in candidate_legs.
    book_preference: tuple[str, ...] = DEFAULT_BOOK_PREFERENCE
    # "model" | "random_placebo" | "always_favourite" | "always_over"
    #
    # The three non-model selectors are the baselines the MD2 Pressure Test
    # RULE 3 demands: "if the framework can't out-CLV those, the 43 directives
    # are decoration." random_placebo is the WEAKEST of them — favourite-
    # longshot drift makes random selection look bad almost for free, so
    # beating it proves little. always_favourite is the demanding one: short
    # prices are where the market is sharpest and where drift helps least.
    selector: str = "model"
    random_seed: int = 390          # ID390, the open question this tests
    warm_start: bool = True
    half_life_days: Optional[float] = None   # None = no time decay (default)

    def fingerprint(self) -> str:
        """Short hash of every knob. Printed in the report so a run with
        different settings is visibly a different experiment, not a revision
        of this one."""
        return hashlib.sha1(json.dumps(asdict(self), sort_keys=True,
                                        default=str).encode()).hexdigest()[:12]


@dataclass
class PaperLeg:
    league: str
    date: str
    fixture: str
    market: str
    softness_tier: str
    model_prob: Optional[float] = None
    entry_odds: Optional[float] = None
    closing_odds: Optional[float] = None
    book: Optional[str] = None
    entry_column: Optional[str] = None
    closing_column: Optional[str] = None
    mes_at_entry: Optional[float] = None
    clv_pct: Optional[float] = None
    derived: bool = False
    status: str = "OK"              # OK | NO_ENTRY | NO_CLOSE | NO_MODEL
    hit: Optional[bool] = None
    fthg: Optional[int] = None
    ftag: Optional[int] = None
    overround_open: Optional[float] = None
    overround_close: Optional[float] = None
    model_cut_date: Optional[str] = None
    model_n_matches: Optional[int] = None


# --------------------------------------------------------------------------
# Walk-forward machinery
# --------------------------------------------------------------------------

def refit_cut_dates(match_dates: list[str], every_days: int) -> list[str]:
    """Block boundaries, anchored to the first match date.

    A model fitted at cut C predicts every match in [C, C + every_days). The
    model is therefore up to (every_days - 1) days stale. That staleness biases
    AGAINST the model — it always has strictly less information than a
    same-day refit would — so a positive result under it is a lower bound, not
    an inflated one. This is the compromise that makes the run affordable, and
    it is stated in the report rather than buried here."""
    if not match_dates:
        return []
    start = date.fromisoformat(min(match_dates))
    end = date.fromisoformat(max(match_dates))
    cuts, cur = [], start
    while cur <= end:
        cuts.append(cur.isoformat())
        cur += timedelta(days=every_days)
    return cuts


def fit_window(history: list[MatchResult], cut_date: str,
                cfg: BacktestConfig) -> list[MatchResult]:
    """Matches STRICTLY BEFORE cut_date, most recent `max_history_matches`.

    The strict `<` is the whole leakage guard. Anything played on or after the
    cut is invisible to the model that predicts it."""
    prior = [r for r in history if r.date < cut_date]
    prior.sort(key=lambda r: r.date)
    return prior[-cfg.max_history_matches:]


def _model_cache_key(league: str, cut_date: str, window: list[MatchResult],
                      cfg: BacktestConfig) -> str:
    """Cache identity covers everything that affects the FIT, and nothing that
    doesn't. A model fitted under different fit settings can never be silently
    reused — that is the invisible corruption HR35 exists to prevent.

    Deliberately EXCLUDES selection-side knobs (selector, min_mes, markets,
    random_seed): those change which legs are taken, not what the model is. So
    the placebo run reuses the model run's fits instead of spending another
    ~13 minutes per league refitting identical models — which also makes the
    comparison exact, since both arms then run against the same models."""
    payload = "|".join([league, cut_date, str(len(window)),
                        window[0].date if window else "-",
                        window[-1].date if window else "-",
                        str(cfg.min_matches_per_team), str(cfg.max_history_matches),
                        str(cfg.min_history_matches), str(cfg.half_life_days),
                        str(cfg.warm_start), str(FIT_VERSION)])
    return hashlib.sha1(payload.encode()).hexdigest()[:20]


def _save_model(path: Path, model: DixonColesModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "league": model.league, "home_advantage": model.home_advantage,
        "rho": model.rho, "n_matches_fit": model.n_matches_fit,
        "teams": {t: [s.attack, s.defence] for t, s in model.teams.items()},
        "warm_seed": model.warm_seed,
    }), encoding="utf-8")


def _load_model(path: Path) -> Optional[DixonColesModel]:
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    m = DixonColesModel(league=d["league"], home_advantage=d["home_advantage"],
                         rho=d["rho"], n_matches_fit=d["n_matches_fit"])
    m.teams = {t: TeamStrength(attack=a, defence=df) for t, (a, df) in d["teams"].items()}
    seed = d.get("warm_seed")
    if seed:
        m.warm_seed = ({k: tuple(v) for k, v in seed[0].items()}, tuple(seed[1]))
    return m


def get_model(league: str, cut_date: str, history: list[MatchResult],
               cfg: BacktestConfig, warm_seed=None
               ) -> tuple[Optional[DixonColesModel], Optional[str]]:
    """Returns (model, reason_if_none). Cached on disk by config-aware key."""
    window = fit_window(history, cut_date, cfg)
    if len(window) < cfg.min_history_matches:
        return None, (f"insufficient history at {cut_date}: {len(window)} matches "
                      f"< {cfg.min_history_matches} required")

    cache_path = MODEL_CACHE_DIR / f"{league.replace(' ', '_')}_{_model_cache_key(league, cut_date, window, cfg)}.json"
    cached = _load_model(cache_path)
    if cached is not None:
        return cached, None

    kwargs = {}
    if cfg.warm_start and warm_seed:
        kwargs["x0_teams"], kwargs["x0_globals"] = warm_seed
    model = fit(window, min_matches_per_team=cfg.min_matches_per_team,
                 return_raw_x=True, half_life_days=cfg.half_life_days,
                 ref_date=cut_date, **kwargs)
    _save_model(cache_path, model)
    return model, None


# --------------------------------------------------------------------------
# Price maths
# --------------------------------------------------------------------------

def overround(prices: list[Optional[float]]) -> Optional[float]:
    """Bookmaker margin on a line: sum(1/odds) - 1. Reported at BOTH open and
    close because if margin systematically shrinks toward the close, every leg
    shows positive CLV with no model skill involved."""
    if any(p is None or p <= 0 for p in prices):
        return None
    return round(sum(1.0 / p for p in prices) - 1.0, 5)


def devig_two_way(price_a: float, price_b: float) -> tuple[float, float]:
    """Proportional de-vig of a two-way line -> fair probabilities summing to 1."""
    ia, ib = 1.0 / price_a, 1.0 / price_b
    total = ia + ib
    return ia / total, ib / total


def derive_o15_prob(p_over25_fair: float) -> Optional[float]:
    """Fair P(Over 1.5) implied by the market's fair P(Over 2.5), via Poisson
    total goals.

    HR30 allows deriving the O1.5 implied probability when it isn't quoted —
    and it never is in this source — provided it is LABELLED DERIVED. Solve
    P(X > 2) = p_over25_fair for lambda, then return P(X > 1).

    Deliberately returns a PROBABILITY, not a price. Converting back to odds
    would require inventing a bookmaker margin, and an invented number is
    exactly what HR35 forbids."""
    if not (0.0 < p_over25_fair < 1.0):
        return None
    f = lambda lam: (1.0 - poisson.cdf(2, lam)) - p_over25_fair
    try:
        lam = brentq(f, 0.05, 12.0, xtol=1e-8)
    except ValueError:
        return None
    return float(1.0 - poisson.cdf(1, lam))


def derived_clv_pct(p_open_fair: float, p_close_fair: float) -> float:
    """CLV in PROBABILITY space for derived markets.

    Algebraically the same quantity as compute_clv() on margin-free prices,
    but NOT the same as raw-price CLV, which also contains margin drift. Kept
    under a separate name so the two can never be averaged together by
    accident at a call site."""
    return round((p_close_fair / p_open_fair - 1.0) * 100, 3)


def settle(market: str, fthg: int, ftag: int) -> Optional[bool]:
    """Did the leg win? HR15 90-minute basis (football-data.co.uk FT columns
    are 90 minutes; ET/pens are not included)."""
    total = fthg + ftag
    return {
        "1X2_H": fthg > ftag,
        "1X2_D": fthg == ftag,
        "1X2_A": ftag > fthg,
        "O2.5": total > 2,
        "U2.5": total <= 2,
        MARKET_O15_DERIVED: total > 1,
    }.get(market)


# --------------------------------------------------------------------------
# Leg selection
# --------------------------------------------------------------------------

def _select(cfg: BacktestConfig, market: str, mes, price, odds, rng) -> bool:
    """Should this leg be taken? One rule per selector.

    The baselines exist so the model's number has something to be measured
    AGAINST. A mean CLV of -0.4% is meaningless in isolation; it only means
    something next to what a rule with no model in it achieves on the very
    same fixtures (MD2 Pressure Test, RULE 3)."""
    if cfg.selector == "model":
        return mes is not None and mes >= cfg.min_mes
    if cfg.selector == "random_placebo":
        return rng.random() < 0.5
    if cfg.selector == "always_favourite":
        # Back the shortest of the three 1X2 prices, every match. This is the
        # hardest baseline: short prices are where the book is sharpest, so a
        # model that cannot out-CLV it is adding nothing where it matters.
        if market not in ("1X2_H", "1X2_D", "1X2_A"):
            return False
        line = [(o_.open, n) for n, o_ in
                (("1X2_H", odds.home), ("1X2_D", odds.draw), ("1X2_A", odds.away))
                if o_.open is not None]
        return bool(line) and min(line)[1] == market
    if cfg.selector == "always_over":
        return market == "O2.5"
    raise ValueError(f"unknown selector {cfg.selector!r}")


def candidate_legs(match: MatchResult, probs, cfg: BacktestConfig,
                    rng: Optional[random.Random] = None) -> list[PaperLeg]:
    """Enumerate every market in scope for one fixture and keep those the model
    likes enough.

    `min_mes` is the p-hacking surface of this whole exercise: sweep it and you
    will find a value that produces a positive headline. It is PRE-DECLARED in
    BacktestConfig, printed in the report, and if it is ever swept the report
    must emit every value tried, not the best one."""
    tier = softness_tier(match.league)
    fixture = f"{match.home_team} v {match.away_team}"
    o = match.odds
    legs: list[PaperLeg] = []

    def base(market: str, **kw) -> PaperLeg:
        return PaperLeg(league=match.league, date=match.date, fixture=fixture,
                         market=market, softness_tier=tier, fthg=match.fthg,
                         ftag=match.ftag, **kw)

    if o is None:
        return [base(m, status="NO_ENTRY") for m in cfg.markets]

    or_open = overround([o.home.open, o.draw.open, o.away.open])
    or_close = overround([o.home.close, o.draw.close, o.away.close])

    pairs = [
        ("1X2_H", o.home, probs.p_home if probs else None),
        ("1X2_D", o.draw, probs.p_draw if probs else None),
        ("1X2_A", o.away, probs.p_away if probs else None),
        ("O2.5", o.over25, probs.p_over_25 if probs else None),
        ("U2.5", o.under25, (1 - probs.p_over_25) if probs else None),
    ]

    for market, price, model_p in pairs:
        if market not in cfg.markets:
            continue
        common = dict(book=price.book, entry_column=price.open_column,
                       closing_column=price.close_column,
                       overround_open=or_open, overround_close=or_close)
        if price.open is None:
            legs.append(base(market, status="NO_ENTRY", model_prob=model_p, **common))
            continue
        if model_p is None:
            legs.append(base(market, status="NO_MODEL", entry_odds=price.open, **common))
            continue

        mes = mes_numeric(model_p, price.open)
        if not _select(cfg, market, mes, price, o, rng):
            continue

        if price.close is None:
            # Selected, but unmeasurable. Recorded and counted — dropping it
            # silently is how a backtest flatters itself, because closes go
            # missing preferentially where the line moved most.
            legs.append(base(market, status="NO_CLOSE", model_prob=model_p,
                              entry_odds=price.open, mes_at_entry=mes,
                              hit=settle(market, match.fthg, match.ftag), **common))
            continue

        legs.append(base(market, status="OK", model_prob=model_p,
                          entry_odds=price.open, closing_odds=price.close,
                          mes_at_entry=mes,
                          clv_pct=compute_clv(price.open, price.close),
                          hit=settle(market, match.fthg, match.ftag), **common))

    # Derived O1.5 — probability space only, never averaged with raw CLV.
    if MARKET_O15_DERIVED in cfg.markets and probs is not None:
        legs.extend(_derived_o15_leg(match, probs, cfg, base, rng))

    return legs


def _derived_o15_leg(match, probs, cfg, base, rng) -> list[PaperLeg]:
    o = match.odds
    if o.over25.open is None or o.under25.open is None:
        return [base(MARKET_O15_DERIVED, status="NO_ENTRY", derived=True,
                      model_prob=probs.p_over_15)]
    p_open_fair, _ = devig_two_way(o.over25.open, o.under25.open)
    p_o15_open = derive_o15_prob(p_open_fair)
    if p_o15_open is None:
        return [base(MARKET_O15_DERIVED, status="NO_ENTRY", derived=True,
                      model_prob=probs.p_over_15)]

    edge = probs.p_over_15 - p_o15_open
    if cfg.selector == "model":
        selected = edge >= cfg.min_mes
    elif cfg.selector == "random_placebo":
        selected = rng.random() < 0.5
    elif cfg.selector == "always_over":
        selected = True          # the overs baseline takes this market too
    else:
        selected = False         # always_favourite is a 1X2-only rule
    if not selected:
        return []

    if o.over25.close is None or o.under25.close is None:
        return [base(MARKET_O15_DERIVED, status="NO_CLOSE", derived=True,
                      model_prob=probs.p_over_15, mes_at_entry=round(edge, 4),
                      book=o.over25.book,
                      hit=settle(MARKET_O15_DERIVED, match.fthg, match.ftag))]

    p_close_fair, _ = devig_two_way(o.over25.close, o.under25.close)
    p_o15_close = derive_o15_prob(p_close_fair)
    if p_o15_close is None:
        return [base(MARKET_O15_DERIVED, status="NO_CLOSE", derived=True,
                      model_prob=probs.p_over_15, mes_at_entry=round(edge, 4))]

    return [base(MARKET_O15_DERIVED, status="OK", derived=True,
                  model_prob=probs.p_over_15, mes_at_entry=round(edge, 4),
                  book=o.over25.book,
                  entry_column=o.over25.open_column,
                  closing_column=o.over25.close_column,
                  clv_pct=derived_clv_pct(p_o15_open, p_o15_close),
                  hit=settle(MARKET_O15_DERIVED, match.fthg, match.ftag))]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def run_league_backtest(league: str, cfg: BacktestConfig
                         ) -> tuple[list[PaperLeg], list[str], dict]:
    """Returns (legs, flags, coverage) for one league."""
    flags: list[str] = []
    coverage = {"n_fixtures_in_scope": 0, "n_excluded_warmup": 0, "n_no_model": 0}

    try:
        carry, _ = load_league(league, cfg.carry_in_season,
                               book_preference=cfg.book_preference)
    except Exception as e:
        carry = []
        flags.append(f"{league}: no carry-in season {cfg.carry_in_season} ({e})")
    try:
        test, _ = load_league(league, cfg.test_season,
                              book_preference=cfg.book_preference)
    except Exception as e:
        flags.append(f"{league}: test season {cfg.test_season} unavailable ({e}) "
                     f"— NO DATA — PENDING")
        return [], flags, coverage

    if not test:
        flags.append(f"{league}: test season {cfg.test_season} returned no matches")
        return [], flags, coverage

    if test[0].odds and test[0].odds.schema == "extra":
        flags.append(f"{league}: CLOSING PRICES ONLY in this source (Extra schema) — "
                     f"no opening price exists, so entry-vs-close CLV is UNDEFINED. "
                     f"This league cannot be backtested here. NO DATA — PENDING.")
        return [], flags, coverage

    history = sorted(carry + test, key=lambda r: r.date)
    test_sorted = sorted(test, key=lambda r: r.date)
    coverage["n_fixtures_in_scope"] = len(test_sorted)

    cuts = refit_cut_dates([r.date for r in test_sorted], cfg.refit_every_days)
    rng = random.Random(cfg.random_seed)
    legs: list[PaperLeg] = []
    warm_seed = None

    for ci, cut in enumerate(cuts):
        block_end = (date.fromisoformat(cut) + timedelta(days=cfg.refit_every_days)).isoformat()
        block = [r for r in test_sorted if cut <= r.date < block_end]
        if not block:
            continue

        model, reason = get_model(league, cut, history, cfg, warm_seed)
        if model is None:
            coverage["n_excluded_warmup"] += len(block)
            if ci == 0 or len(cuts) < 4:
                flags.append(f"{league}: {reason}")
            continue
        if getattr(model, "warm_seed", None):
            warm_seed = model.warm_seed

        n_fit = model.n_matches_fit
        for m in block:
            probs = predict(model, m.home_team, m.away_team)
            if probs is None:
                coverage["n_no_model"] += 1
            produced = candidate_legs(m, probs, cfg, rng)
            for lg in produced:
                lg.model_cut_date = cut
                lg.model_n_matches = n_fit
            legs.extend(produced)

    return legs, flags, coverage


def run_backtest(cfg: BacktestConfig) -> tuple[list[PaperLeg], list[str], dict]:
    all_legs: list[PaperLeg] = []
    all_flags: list[str] = []
    coverage: dict[str, dict] = {}
    for league in cfg.leagues:
        print(f"  backtesting {league}...", flush=True)
        legs, flags, cov = run_league_backtest(league, cfg)
        all_legs.extend(legs)
        all_flags.extend(flags)
        coverage[league] = cov
    return all_legs, all_flags, coverage


# --------------------------------------------------------------------------
# Persistence — isolated from the Phase 3 capital gate
# --------------------------------------------------------------------------

def write_to_clv_log(legs: list[PaperLeg], run_id: str,
                      path: Optional[Path] = None) -> int:
    """Persist backtest legs, with TWO independent guards against them ever
    counting toward the Phase 3 capital gate:

      1. phase = "backtest_<run_id>" — phase2_status() matches PAPER_PHASE
         exactly, so these are excluded by construction.
      2. a separate file, and a hard refusal to write to the production log
         even if the path is repointed later.
    """
    path = Path(path or (RESULTS_DIR / "backtest_clv_log.json"))
    if path.resolve() == Path(DEFAULT_LOG_PATH).resolve():
        raise RuntimeError(
            "Refusing to write backtest legs into the production CLV log — "
            "they would contaminate the Phase 3 capital gate.")
    path.parent.mkdir(parents=True, exist_ok=True)

    phase = f"{BACKTEST_PHASE}_{run_id}"
    logged = [
        LoggedLeg(
            leg_id=f"{lg.fixture.replace(' ', '_')}_{lg.market}_{lg.date}",
            date_logged=lg.date, league=lg.league, fixture=lg.fixture,
            market=lg.market, model_prob=lg.model_prob or 0.0,
            entry_odds=lg.entry_odds, entry_capture_path="CL-ARCHIVE",
            closing_odds=lg.closing_odds, closing_capture_path="CL-ARCHIVE",
            clv_pct=lg.clv_pct, hit=lg.hit, stake=None, phase=phase,
            notes=(f"book={lg.book} open_col={lg.entry_column} "
                   f"close_col={lg.closing_column} cut={lg.model_cut_date} "
                   f"n_fit={lg.model_n_matches} status={lg.status}"
                   + (" DERIVED" if lg.derived else "")),
        )
        for lg in legs if lg.status in ("OK", "NO_CLOSE")
    ]
    log = CLVLog(path=path)
    return log.log_batch(logged)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

# Measurable deploy-eligible leagues. Denmark and Poland are deliberately
# absent: their source schema carries closing prices only, so entry-vs-close
# cannot be computed for them at all (reported, not silently skipped).
DEFAULT_AB = ("Eredivisie", "Belgian Pro League", "Scottish Premiership")
DEFAULT_CONTROL = ("Premier League", "La Liga", "Bundesliga")


def main() -> None:
    from backtest.backtest_report import render_report

    ap = argparse.ArgumentParser(description="OLP XDV CLV backtest")
    ap.add_argument("--test-season", default="2425")
    ap.add_argument("--carry-in", default="2324")
    ap.add_argument("--leagues", nargs="+", default=list(DEFAULT_AB + DEFAULT_CONTROL))
    ap.add_argument("--refit-days", type=int, default=7)
    ap.add_argument("--min-mes", type=float, default=0.02)
    ap.add_argument("--selector", choices=["model","random_placebo","always_favourite","always_over"], default="model")
    ap.add_argument("--half-life-days", type=float, default=None)
    ap.add_argument("--markets", nargs="+", default=None,
                     help="restrict to these markets, e.g. 1X2_H 1X2_D O2.5 U2.5")
    ap.add_argument("--no-write", action="store_true", help="skip writing the leg log")
    args = ap.parse_args()

    cfg = BacktestConfig(
        leagues=tuple(args.leagues), carry_in_season=args.carry_in,
        test_season=args.test_season, refit_every_days=args.refit_days,
        min_mes=args.min_mes, selector=args.selector,
        half_life_days=args.half_life_days,
        markets=tuple(args.markets) if args.markets else BacktestConfig.markets,
    )
    run_id = f"{cfg.test_season}_{cfg.selector}_{cfg.fingerprint()}"
    print(f"CLV backtest — fit {cfg.carry_in_season} -> legs in {cfg.test_season} "
          f"| selector={cfg.selector} | run {run_id}")

    legs, flags, coverage = run_backtest(cfg)
    report = render_report(legs, flags, coverage, cfg, run_id)
    print()
    print(report)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"report_{run_id}.txt").write_text(report, encoding="utf-8")
    if not args.no_write:
        n = write_to_clv_log(legs, run_id,
                             path=RESULTS_DIR / f"backtest_clv_log_{run_id}.json")
        print(f"\n{n} legs written to backtest log (phase '{BACKTEST_PHASE}_*', "
              f"excluded from the Phase 3 capital gate by construction).")


if __name__ == "__main__":
    main()
