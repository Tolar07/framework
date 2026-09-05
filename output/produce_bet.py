"""
PRODUCE BET / VERIFY RESULTS — FROZEN CONTRACT v303.11, HR53 full-detail mandate.

Table layout is treated as binding (memory is editable, so "frozen" means
treated-as-binding here too — any change to these formats should be a
deliberate, visible decision, not a silent drift).

HR35 hard guardrail carried through: completeness never overrides honesty.
A missing datum renders as "NO DATA — PENDING", never filled to look complete.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import re
from typing import Optional

from engine.dixon_coles import FixtureProbabilities
from engine.consensus import Consensus
from engine.acca import build_production_bets, render_production_block
from engine.mes import edge_diff, mes_numeric_ev, trigger_price
from engine import markets as mkt
from verification.id403 import VerificationResult, Tier, stamp
from bets.produced_bet import render_produced_bet as render_produced_bet_block
from output.board_validator import validate_the_call


# The authoritative SportyBet Playwright cache the orchestrator reads
# (booking/bridge.py _cache_path). Carries real ISO `kickoff_utc`.
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"


def _hhmm_from_utc(utc: Optional[str]) -> Optional[str]:
    """Extract 'HH:MM' from an ISO timestamp; None if absent/garbled."""
    if not utc or len(utc) < 16:
        return None
    m = re.match(r"\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})", utc)
    return m.group(1) if m else None


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize_name(name: str) -> str:
    """Lowercase, strip SRL/fc/fc suffixes and non-alphanum for matching."""
    n = name.lower()
    n = re.sub(r'\b(srl|fc|afc|cf|sc|ac)\b', '', n)
    return re.sub(r'[^a-z0-9]', '', n)


def _cache_kickoff(board_home: str, board_away: str) -> Optional[str]:
    """FALLBACK: find a kickoff TIME by matching home/away names ACROSS all
    cache files (league label ignored). Returns 'HH:MM' or None. Only used when
    the board fixture's own `kickoff_utc` is missing.

    Reads the real SportyBet Playwright cache (`data/cache/sportybet/fixtures/`),
    which stores `home_team`/`away_team` and a real ISO `kickoff_utc`
    (e.g. "2026-08-28T19:30:00Z"). Matches by name across every file; the time
    is the only thing taken — never the (unreliable) league label."""
    norm_h = _normalize_name(board_home)
    norm_a = _normalize_name(board_away)
    if not norm_h or not norm_a:
        return None
    for p in CACHE_DIR.glob("*.json"):
        data = _load_cache(p)
        for fx in data.get("fixtures", []):
            # Cache keys are home_team/away_team (bridge.py write path).
            ch = _normalize_name(fx.get("home_team", "") or fx.get("home", ""))
            ca = _normalize_name(fx.get("away_team", "") or fx.get("away", ""))
            # Direct match or cross-match (handles home/away swapped)
            if (ch == norm_h and ca == norm_a) or \
               (ch == norm_a and ca == norm_h):
                ko = _hhmm_from_utc(fx.get("kickoff_utc", "") or fx.get("kickoff", ""))
                if ko:
                    return ko
            # Containment: one name contains the other both ways
            h_contains = (norm_h in ch or ch in norm_h)
            a_contains = (norm_a in ca or ca in norm_a)
            if h_contains and a_contains:
                ko = _hhmm_from_utc(fx.get("kickoff_utc", "") or fx.get("kickoff", ""))
                if ko:
                    return ko
    return None


def _kickoff_for(bf, board_home: str, board_away: str) -> str:
    """Resolve a kickoff time for a fixture.

    1. PREFERRED: the board fixture's own `kickoff_utc` (resolved at scan time).
    2. FALLBACK: cross-cache name match for the time only.
    3. DEFAULT: '??:??' (HR35 — never fabricate a time)."""
    utc = getattr(bf, "kickoff_utc", None)
    hhmm = _hhmm_from_utc(utc)
    if hhmm:
        return hhmm
    return _cache_kickoff(board_home, board_away) or "??:??"


def _lean(p_over: Optional[float], line_label: str) -> str:
    """BUG5 fix carried over: always show whichever side is >=50%, never force 'O'."""
    if p_over is None:
        return "NO DATA — PENDING"
    if p_over >= 0.5:
        return f"O{round(p_over*100)}"
    return f"U{round((1-p_over)*100)}"


@dataclass
class BoardFixture:
    fixture: str  # "Home v Away"
    probs: Optional[FixtureProbabilities]
    verification: VerificationResult
    on_deploy_shortlist: bool = False
    mes_trigger_price: Optional[float] = None
    rejection_reason: Optional[str] = None
    # Provenance of this fixture's probability: None = primary fitted DC fit,
    # "carry" = prior-season carry-over fit, "clubelo" = ClubElo stretch (a
    # real keyless current-season rating — bookable per Architect 2026-08-12,
    # but labeled so it is never mistaken for a fitted rating).
    rating_source: Optional[str] = None
    # Live market side (populated when an odds source is wired in). HR30 wants
    # a NUMERICAL Market Edge Score on every capital-relevant pick; without a
    # real price the best the board could do was a breakeven trigger and an
    # HR30 exception note. With a price it can state the actual EV.
    best_market: Optional[str] = None        # named in words, e.g. "Over 2.5 goals"
    best_price: Optional[float] = None       # decimal odds actually quoted
    best_bookmaker: Optional[str] = None
    best_n_books: int = 0
    best_mes_ev: Optional[float] = None      # model_prob * price - 1
    best_model_prob: Optional[float] = None
    # SportyBet odds (for Phase 2 CLV + Phase 3 live pricing)
    sb_home_odds: Optional[float] = None
    sb_draw_odds: Optional[float] = None
    sb_away_odds: Optional[float] = None
    sb_mes_ev: Optional[float] = None        # best EV across 1X2 markets on SportyBet
    # CLV-gated recalibration delta actually applied to this pick's EV
    # probability (0.0 = no evidence). The ledger still records the RAW
    # model_prob above — no feedback loop.
    cal_adjustment: Optional[float] = None
    # Kickoff date (ISO) of THIS fixture. Carried so a logged leg can be
    # settled against the right match rather than a same-pairing meeting from
    # an earlier season.
    kickoff_date: Optional[str] = None
    # Kickoff UTC timestamp (ISO, e.g. "2026-08-24T19:00:00Z") of THIS fixture,
    # when the source provided it. Carries the TIME, not just the date — the
    # /fixtures renderer reads this first so it never has to fuzzy-match the
    # cross-contaminated SportyBet cache for a kickoff time. None when no
    # source supplied a time (HR35 — never fabricated).
    kickoff_utc: Optional[str] = None
    # Second opinion from the Elo engine (ID82, ratified 2026-08-04) and the
    # flag raised when the two engines disagree materially. Elo is independent
    # of Dixon-Coles — different inputs, different mathematics, different
    # failure modes — so its agreement is informative and its disagreement is
    # a warning. It does NOT gate deployment.
    elo_probs: Optional[tuple] = None
    engine_divergence: Optional[str] = None
    # Third opinion from the xG engine (Understat, free). Reads the quality of
    # chances, not the goals they produced — a genuinely independent signal
    # from DC (score patterns) and Elo (result history). Only present for
    # Big-5 leagues where a free xG source exists; omitted elsewhere (never
    # fabricated, HR35).
    xg_probs: Optional[tuple] = None
    # xG's goals-market read (O1.5, O2.5, O3.5, BTTS-yes) from the SAME xG
    # prediction as xg_probs — chance quality applied to the goals markets,
    # not just 1X2 (Phase 3.4). DC's goals markets stay canonical for what is
    # logged; this independent opinion is shown beside them, never blended.
    xg_goals: Optional[tuple] = None
    # Raised when DC's goals read and xG's disagree materially (>=20 points
    # on a market). A warning the board surfaces, never a gate — the pick
    # stays DC-canonical (HR35: missing data is never flagged or passed).
    goals_divergence: Optional[str] = None
    # Fourth opinion — the BOOKMAKER's devigged implied 1X2 (ID413). The
    # aggregate of real money, not a model; computed from the full home/draw/
    # away odds by proportional margin removal (engine/markets.py implied_1x2).
    # Only present for leagues where odds are pulled (A/B deploy leagues) —
    # scan-only leagues honestly have no bookmaker opinion (HR35). It is an
    # equal fourth voter in the consensus but NEVER changes what is logged.
    market_probs: Optional[tuple] = None
    # Market-anchored probability: blend_toward_market pulled the model's
    # p_home/p_draw/p_away toward the market's devigged implied by an amount
    # proportional to DISAGREEMENT. This is the probability the board DISPLAYS
    # when it says "Win chance" — the honest number when the model and market
    # disagree (ID414). Ledger stores raw model_prob (best_model_prob); this
    # is display + EV only. None when the fixture has no live odds to anchor to.
    blend_probs: Optional[tuple] = None
    # Cross-engine vote (DC · Elo · xG · bookmaker), ID412: the majority result across
    # whatever opinions exist, plus their averaged 1X2. DISPLAY + BRAIN ONLY —
    # it never changes what is logged (DC stays canonical for legs/CLV).
    # None when fewer than two engines had an opinion (a lone engine is not
    # a consensus); result=None on a split with no majority.
    consensus: Optional[Consensus] = None
    # Which goals model priced this fixture: 'dc' (single-league Dixon-Coles)
    # or 'cross' (the pooled European graph). Carried so the brain can record
    # which engine produced each prediction.
    model_engine: str = "dc"
    # The canonical market key (1X2_HOME / 1X2_DRAW / 1X2_AWAY / OVER_1_5 /
    # OVER_2_5 / BTTS_YES) of the priced best-market row, when one exists.
    best_market_key: Optional[str] = None
    # Tactical engine action (ID417): team-state intelligence applied as a goal
    # expectancy nudge. None = no tactical signal, "tactical" = a formation and/or
    # squad-change adjustment was applied to this fixture's Lambdas (via
    # predict_adjusted). The board labels it so a tactically-adjusted rating is
    # never mistaken for a pure fitted rating (HR35: honest provenance). The
    # adjustment is a small, conservative nudge — never a re-rating.
    tactical_provenance: Optional[str] = None


def render_part0(mode: str, phase: str, leagues_scanned: list[str],
                  calibration_count: int, mean_clv: Optional[float],
                  data_flags: list[str],
                  include_data_flags: bool = True) -> str:
    # ARCHITECT 2026-08-29: data flags are NEVER surfaced in delivered output.
    # They remain in memory (agent payloads / logs) for audit, but the board,
    # Telegram and web push show only verified, produced selections. Setting
    # include_data_flags=True is now a no-op — the section is intentionally
    # gone so a produced board can never carry an unreviewed gap flag.
    lines = [
        f"PART 0 — HEADER",
        f"Date: {date.today().isoformat()} | Mode: {mode} | Phase: {phase}",
        f"Leagues scanned: {', '.join(leagues_scanned)}",
        f"Calibration: {calibration_count} legs logged, "
        f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None
        else f"Calibration: {calibration_count} legs logged, CLV logged: ZERO",
    ]
    lines.append("HONEST EDGE LINE: this is an excellent informed process but "
                  "NOT a demonstrated profitable edge.")
    # ID409 frozen-contract supersession — RATIFIED 2026-08-15 (Architect
    # sign-off): the board renders Detail (PART 2) → Call (PART 1), reversing
    # the v303.11 frozen order. Logged, not a runtime warning anymore.
    lines.append("ID409 RATIFIED 2026-08-15 — board order: "
                 "Detail(PART 2) → Call(PART 1) → Acca Route → THE PICK.")
    return "\n".join(lines)




def _verification_words(v: VerificationResult) -> str:
    """Spell out the ID403 tier and its provenance, rather than a bare mark."""
    domains = v.factors.get("independent_domains") or []
    src = f" (source: {', '.join(domains)})" if domains else ""
    return {
        Tier.VERIFIED: f"VERIFIED — independent factors agree{src}",
        Tier.SINGLE_SOURCE: f"SINGLE-SOURCE — one source only, no capital on this alone{src}",
        Tier.CONFLICT: f"CONFLICT — sources disagree, Architect must adjudicate{src}",
        Tier.NO_DATA: "NO DATA — PENDING",
        Tier.DERIVED: f"DERIVED — model output, not an observed fact{src}",
    }[v.tier]


def _side_words(p: FixtureProbabilities, line: float, p_over: float) -> str:
    """BUG5: name whichever side is favoured, and say what the number measures."""
    if p_over >= 0.5:
        return f"Over {line} goals {round(p_over*100)}% (model)"
    return f"Under {line} goals {round((1-p_over)*100)}% (model)"


V5_DIVERGENCE_PP = 15.0   # ID403.1 V5 threshold, as ratified
V5_DIVERGENCE_EV = 0.15   # EXTENSION — see note below


def _divergence(bf: BoardFixture) -> Optional[str]:
    """ID403.1 V5 market-alignment check, with an EV-magnitude extension.

    V5 as ratified keys on an absolute gap in percentage points. That is the
    right instrument at mid-range probabilities but goes BLIND at long odds,
    where a tiny absolute gap is an enormous relative edge:

        model 17% vs a 9.00 price (implied 11.1%)
          -> gap is only 5.9pp, so ratified V5 stays silent
          -> yet the EV is +57%, the single most suspicious number on the board

    So a second trigger fires on EV magnitude. Both are DIVERGENCE flags for
    review; neither auto-fails a fixture, and nothing is silently dropped —
    this only ever ADDS caution.

    Why an eye-catching EV is a warning rather than an opportunity: a genuine
    edge in a liquid market is 1-5%. Anything approaching +20% almost always
    means the model is miscalibrated, not that a room full of bookmakers has
    mispriced the game. This framework's own backtest returned NEGATIVE mean
    CLV, which is direct evidence the model currently overstates its edge.

    NOTE FOR THE ARCHITECT: the EV trigger is an extension beyond ID403.1 as
    written. It is deliberately one-directional (more caution, never less), so
    it is offered under the Section 12 auto-ratification grant — reversible in
    one word if you disagree."""
    if bf.best_price is None or bf.best_model_prob is None:
        return None
    implied = 1.0 / bf.best_price
    gap_pp = (bf.best_model_prob - implied) * 100
    ev = bf.best_mes_ev

    trips = []
    if abs(gap_pp) >= V5_DIVERGENCE_PP:
        trips.append(f"a {gap_pp:+.0f}pp probability gap")
    if ev is not None and abs(ev) >= V5_DIVERGENCE_EV:
        trips.append(f"an implausible {ev:+.0%} expected value")
    if not trips:
        return None

    return (f"DIVERGENCE FLAG (ID403.1 V5): model says "
            f"{round(bf.best_model_prob*100)}%, this price implies "
            f"{round(implied*100)}% — {' and '.join(trips)}. Treat as a REVIEW "
            f"item, NOT an edge. A discrepancy this size is far more often the "
            f"model being miscalibrated than the market being wrong. Do not "
            f"deploy without independent corroboration.")


def render_fixture_block(bf: BoardFixture, index: int = 0) -> str:
    """HR53 per-fixture STACKED block.

    The frozen v303.11 tables are still rendered below for the wide board, but
    HR53 explicitly prefers this shape for readability: every number carries
    what it measures and which team/market it belongs to, club names are never
    truncated, and a missing datum stays visible as NO DATA — PENDING rather
    than being dropped to make the block look tidy."""
    L = []
    head = f"{index}. {bf.fixture}" if index else bf.fixture
    L.append(head)
    L.append(f"   Data confidence: {_verification_words(bf.verification)}")

    if bf.probs is None:
        L.append("   Model: NO DATA — PENDING")
        if bf.rejection_reason:
            L.append(f"   Reason: {bf.rejection_reason}")
        return "\n".join(L)

    p = bf.probs
    # A STRETCH 1X2-only rating (ClubElo fallback) has no goals opinion — its
    # goals markets stay honestly unpriced (None, HR35), never guessed.
    if bf.rating_source == "clubelo":
        L.append(f"   Rating source: ClubElo stretch (keyless current-season Elo)"
                 f" — bookable, labeled")
    elif bf.rating_source == "carry":
        L.append(f"   Rating source: previous-season carry-over fit "
                 f"(promoted clubs)")
    L.append(f"   Match result (model probabilities):")
    L.append(f"      {p.home_team} to win .......... {round(p.p_home*100)}%")
    L.append(f"      Draw ......................... {round(p.p_draw*100)}%")
    L.append(f"      {p.away_team} to win .......... {round(p.p_away*100)}%")
    if p.p_over_15 is not None:
        L.append(f"   Goals: {_side_words(p, 1.5, p.p_over_15)}"
                 f" | {_side_words(p, 2.5, p.p_over_25)}")
    else:
        L.append(f"   Goals: NO DATA — stretch 1X2 rating has no goals opinion")
    if p.p_btts_yes is not None:
        btts = ("Both teams to score YES" if p.p_btts_yes >= 0.5 else "Both teams to score NO")
        btts_p = p.p_btts_yes if p.p_btts_yes >= 0.5 else 1 - p.p_btts_yes
        L.append(f"   {btts} {round(btts_p*100)}% (model)")
    L.append(f"   Expected goals (model): {p.home_team} {p.lambda_home}, "
             f"{p.away_team} {p.lambda_away}")

    # Second opinion — ID82 Elo, ratified 2026-08-04. Shown beside Dixon-Coles
    # rather than blended into it: two engines that agree is evidence, and an
    # averaged number would hide exactly the disagreement worth seeing.
    if bf.elo_probs:
        eh, ed, ea = bf.elo_probs
        L.append(f"   Second opinion — Elo rating engine (ID82), independent of "
                 f"the goals model:")
        L.append(f"      {p.home_team} to win {round(eh*100)}% · Draw "
                 f"{round(ed*100)}% · {p.away_team} to win {round(ea*100)}%")
        if bf.engine_divergence:
            L.append(f"      {bf.engine_divergence}")
        else:
            L.append(f"      Both engines agree within tolerance — no divergence "
                     f"flag. Agreement is not proof of a good bet, only of a "
                     f"consistent read.")
    else:
        L.append("   Second opinion (Elo): NO DATA — PENDING (one or both clubs "
                 "below the Elo match floor)")

    # Third opinion — xG via Understat (free). Reads the quality of chances,
    # not the goals they produced. Only present for Big-5 leagues where a free
    # xG source exists; the board never fabricates one (HR35).
    if bf.xg_probs:
        xh, xd, xa = bf.xg_probs
        L.append(f"   Third opinion — xG (Understat, quality-adjusted), "
                 f"independent of goals + results:")
        L.append(f"      {p.home_team} to win {round(xh*100)}% · Draw "
                 f"{round(xd*100)}% · {p.away_team} to win {round(xa*100)}%")
        # Phase 3.4: xG's goals-market read — chance quality applied to the
        # goals markets. DC's goals markets above stay canonical for what is
        # logged; this is the independent second opinion on the goals side,
        # shown beside it and never blended.
        if bf.xg_goals:
            xo15, xo25, xo35, xb = bf.xg_goals
            L.append(f"      Goals (chance quality): O1.5 {round(xo15*100)}% · "
                     f"O2.5 {round(xo25*100)}% · O3.5 {round(xo35*100)}% · "
                     f"BTTS yes {round(xb*100)}%")
            if bf.goals_divergence:
                L.append(f"      ⚠ {bf.goals_divergence}")
    else:
        L.append("   Third opinion (xG): NO DATA — PENDING (no free xG source "
                 "covers this league — xG covers Big-5 + RFPL only)")

    # Fourth opinion — the BOOKMAKER (ID413). Real money, not a model: its
    # devigged implied 1X2 is the sharpest single calibration source in
    # football. Only present where odds are pulled (A/B deploy leagues);
    # scan-only leagues show NO DATA rather than fabricating a market.
    if bf.market_probs:
        mh, md, ma = bf.market_probs
        L.append(f"   Fourth opinion — bookmaker (real-money aggregate, "
                 f"margin removed):")
        L.append(f"      {p.home_team} to win {round(mh*100)}% · Draw "
                 f"{round(md*100)}% · {p.away_team} to win {round(ma*100)}%")
    else:
        L.append("   Fourth opinion (bookmaker): NO DATA — PENDING (no odds "
                 "pulled for this league — bookmaker covers deploy leagues only)")

    # Cross-engine CONSENSUS (ID412) — the ScoreGPT structure: a majority
    # vote over the available engines' 1X2 picks, plus their averaged
    # probabilities. Shown as its own line, never blended into the engines.
    # A lone opinion renders nothing (it IS the engine above); a split with
    # no majority renders NO CONSENSUS in full view — never smoothed over.
    if bf.consensus is not None:
        c = bf.consensus
        if c.result:
            labels = {"HOME": p.home_team, "AWAY": p.away_team}
            winner = labels.get(c.result, c.result)
            L.append(f"   CONSENSUS (ID412) — {winner}, "
                     f"{c.agreeing} of {c.n_engines} engines"
                     + (" (one engine dissents)" if c.split else "")
                     + (" — CLV-WEIGHTED" if c.weighted else ""))
            L.append(f"      averaged 1X2: {p.home_team} "
                     f"{round(c.avg_home*100)}% · Draw {round(c.avg_draw*100)}% "
                     f"· {p.away_team} {round(c.avg_away*100)}%")
            if c.weighted and c.weight_used:
                wstr = ", ".join(f"{k} {v:.2f}" for k, v in sorted(c.weight_used.items()))
                L.append(f"      CLV-weighted by engine (dc/elo/xg/bookmaker): {wstr}")
            if c.split:
                L.append(f"      engines split on the result: "
                         f"{', '.join(f'{k} {v}' for k, v in sorted(c.votes.items()))}")
        else:
            L.append(f"   CONSENSUS (ID412) — NO CONSENSUS: "
                     f"{c.n_engines} engines disagree "
                     f"({', '.join(f'{k} {v}' for k, v in sorted(c.votes.items()))})")

    if bf.best_market and bf.best_price is not None:
        ev = bf.best_mes_ev
        verdict = ("POSITIVE expected value against this price"
                   if ev is not None and ev > 0 else
                   "NEGATIVE expected value — the price does not clear the model")
        L.append(f"   Best available market: {bf.best_market}")
        L.append(f"      Model probability .......... {round((bf.best_model_prob or 0)*100)}%")
        L.append(f"      Best quoted price .......... {bf.best_price:.2f} decimal "
                 f"({bf.best_bookmaker}, best of {bf.best_n_books} books)")
        if bf.mes_trigger_price:
            L.append(f"      Breakeven trigger price .... {bf.mes_trigger_price:.2f} or longer")
        L.append(f"      HR30 numerical MES ......... {ev:+.2%} expected value per unit "
                 f"staked — {verdict}" if ev is not None
                 else "      HR30 numerical MES ......... NO DATA — PENDING")
        # ID403.1 V5 — market alignment. A large model-vs-market gap is a
        # DIVERGENCE flag for review, not an opportunity. The market is the
        # sharper instrument far more often than the model is, so an
        # eye-catching EV is usually the model being wrong, not the price.
        div = _divergence(bf)
        if div:
            L.append(f"      {div}")
        # SportyBet odds are available (Phase 2 CLV / Phase 3 live)
        if bf.sb_home_odds is not None or bf.sb_draw_odds is not None or bf.sb_away_odds is not None:
            L.append(f"   SportyBet Nigeria odds (real-money bookmaker, margin included):")
        if bf.sb_home_odds is not None:
            edge = edge_diff(p.p_home, bf.sb_home_odds)
            ev = mes_numeric_ev(p.p_home, bf.sb_home_odds)
            L.append(f"      {p.home_team} to win ....... {bf.sb_home_odds:.2f}  ->  edge {edge:+.2%} | EV {ev:+.2%}" if edge is not None
                     else f"      {p.home_team} to win ....... {bf.sb_home_odds:.2f}  ->  edge NO DATA")
        if bf.sb_draw_odds is not None:
            edge = edge_diff(p.p_draw, bf.sb_draw_odds)
            ev = mes_numeric_ev(p.p_draw, bf.sb_draw_odds)
            L.append(f"      Draw ..................... {bf.sb_draw_odds:.2f}  ->  edge {edge:+.2%} | EV {ev:+.2%}" if edge is not None
                     else f"      Draw ..................... {bf.sb_draw_odds:.2f}  ->  edge NO DATA")
        if bf.sb_away_odds is not None:
            edge = edge_diff(p.p_away, bf.sb_away_odds)
            ev = mes_numeric_ev(p.p_away, bf.sb_away_odds)
            L.append(f"      {p.away_team} to win ....... {bf.sb_away_odds:.2f}  ->  edge {edge:+.2%} | EV {ev:+.2%}" if edge is not None
                     else f"      {p.away_team} to win ....... {bf.sb_away_odds:.2f}  ->  edge NO DATA")
        if bf.sb_mes_ev is not None:
            L.append(f"      Best SportyBet edge ......... {bf.sb_mes_ev:+.2%} per unit staked")
        if bf.mes_trigger_price:
            L.append(f"      Breakeven trigger price .... {bf.mes_trigger_price:.2f} or longer")
    elif bf.mes_trigger_price:
        L.append(f"   HR30 MES trigger price: back only at decimal odds "
                 f"{bf.mes_trigger_price:.2f} or longer (breakeven vs the model).")
        L.append("      Numerical MES: NO DATA — PENDING (HR30 exception — no live "
                 "price available for this fixture)")
    else:
        L.append("   HR30 MES trigger price: NO DATA — PENDING")

    if bf.rejection_reason:
        L.append(f"   Not deploy-eligible: {bf.rejection_reason}")
    return "\n".join(L)


def _fmt_eng(cell: Optional[tuple]) -> str:
    """Format a (home, draw, away) probability tuple as 'H/D/A' percentages,
    or '—' when no opinion exists (HR35 — never fabricated)."""
    if not cell:
        return "—"
    h, d, a = cell
    if h is None:
        return "—"
    return f"{round(h*100)}/{round(d*100)}/{round(a*100)}"


def _fmt_consensus(bf: BoardFixture) -> str:
    """Compact consensus cell: the winning side + 'k/n engines', or NO CONS /
    — when there is none (HR35 — never smoothed over)."""
    c = bf.consensus
    if c is None:
        return "—"
    if not c.result:
        return "NO CONS"
    label = {"HOME": bf.probs.home_team, "AWAY": bf.probs.away_team}.get(c.result, c.result)
    return f"{label[:10]} {c.agreeing}/{c.n_engines}"


def _fmt_ev(ev: Optional[float]) -> str:
    """Format an MES expected-value figure as a signed percentage, or '—'."""
    if ev is None:
        return "—"
    return f"{ev:+.2%}"


def render_part1_the_call(shortlist: list[BoardFixture]) -> str:
    """DEPLOY shortlist — TODAY'S fixtures only (standing rule 2026-08-09),
    unified pool (no tiers, no cap). FULL DETAIL TABLE (ID409 + HR53): every
    fixture one row, all probability/opinion/edge columns inline — no stacked
    prose blocks. Columns:
    Fixture | H% | D% | A% | O1.5 | O2.5 | BTTS | Elo H/D/A | xG H/D/A |
    Mkt H/D/A | Cons | BestMkt | Price | MES EV | Trig | Src | Notes"""
    today = date.today().isoformat()
    shortlist = [bf for bf in shortlist if bf.kickoff_date == today]
    # Apply "wide eyes, narrow hands" filter — only positive-EV, non-divergence picks
    shortlist = validate_the_call(shortlist)
    if not shortlist:
        return ("PART 1 — THE CALL — today's fixtures only\n"
                "NO DEPLOY-ELIGIBLE CALL this session — no deployable fixture "
                "kicks off today (a valid, honest result).")
    header = ("PART 1 — THE CALL (full detail) — today's fixtures only\n"
              f"{len(shortlist)} deploy-eligible fixture(s) kicking off today "
              "(unified pool — all whitelisted leagues, no cap).\n"
              "MARKED PAPER — Phase 2, zero capital. Nothing here is a live bet.\n")
    cols = ["Fixture", "H%", "D%", "A%", "O1.5", "O2.5", "BTTS",
            "Elo H/D/A", "xG H/D/A", "Mkt H/D/A", "Cons",
            "BestMkt", "Price", "MES EV", "Trig", "Src", "Notes"]
    rows = [" | ".join(cols)]
    for bf in shortlist:
        if bf.probs is None:
            rows.append(" | ".join([
                bf.fixture, "—", "—", "—", "—", "—", "—", "—", "—", "—", "—",
                "NO DATA — PENDING", "—", "—", "—", stamp(bf.verification),
                (bf.rejection_reason or "")]))
            continue
        p = bf.probs
        # Goals: Honest-edge — a stretch 1X2-only rating has no goals opinion
        # (None, HR35); report it, never guess.
        o15 = _lean(p.p_over_15, '1.5') if p.p_over_15 is not None else "—"
        o25 = _lean(p.p_over_25, '2.5') if p.p_over_25 is not None else "—"
        if p.p_btts_yes is None:
            btts = "—"
        else:
            btts = (f"Y{round(p.p_btts_yes*100)}"
                    if p.p_btts_yes >= 0.5
                    else f"N{round((1-p.p_btts_yes)*100)}")
        # Best market + price + MES EV: prefer the priced best-market row,
        # fall back to SportyBet odds (Phase 2 CLV / Phase 3 live).
        best_mkt = bf.best_market or "—"
        if bf.best_price is not None:
            price = f"{bf.best_price:.2f}"
            mes_ev = _fmt_ev(bf.best_mes_ev)
        elif bf.sb_home_odds is not None or bf.sb_draw_odds is not None or bf.sb_away_odds is not None:
            # Single best SportyBet leg price isn't stored per-fixture; show the
            # best MES EV we have (sb_mes_ev) and 'SB' as the price source tag.
            price = "SB"
            mes_ev = _fmt_ev(bf.sb_mes_ev)
        else:
            price = "—"
            mes_ev = _fmt_ev(bf.best_mes_ev)
        trig = f"{bf.mes_trigger_price:.2f}+" if bf.mes_trigger_price else "—"
        # Notes: carry the textual divergence/verdict flags so the table stays
        # FULL — nothing important is dropped to a separate prose block.
        notes = []
        if bf.engine_divergence:
            notes.append("ELO DIV")
        if bf.goals_divergence:
            notes.append("xG GOALS DIV")
        if bf.best_mes_ev is not None and bf.best_mes_ev < 0:
            notes.append("NEG EV")
        if bf.rating_source == "clubelo":
            notes.append("CLUBELO STRETCH")
        rows.append(" | ".join([
            bf.fixture,
            f"{round(p.p_home*100)}", f"{round(p.p_draw*100)}", f"{round(p.p_away*100)}",
            o15, o25, btts,
            _fmt_eng(bf.elo_probs), _fmt_eng(bf.xg_probs), _fmt_eng(bf.market_probs),
            _fmt_consensus(bf),
            best_mkt, price, mes_ev, trig,
            stamp(bf.verification),
            " ".join(notes),
        ]))
    return header + "\n".join(rows)


def _best_market_desc(p: FixtureProbabilities) -> tuple[str, float]:
    """Placeholder selection logic for which market to headline — a real deploy
    decision needs the full market-gate (ID405) gating; this just picks the
    highest-confidence market to make the table renderable end to end."""
    # Only markets that are APPROVED for display/scan may be headlined.
    # DEPLOYABLE is the capital gate (ID405); APPROVED_MARKETS is the
    # full list the Architect approved for board visibility.
    candidates = [(mkt.display(k, p.home_team, p.away_team), mkt.model_prob(k, p))
                  for k in mkt.APPROVED_MARKETS]
    candidates = [(name, prob) for name, prob in candidates if prob is not None]
    if not candidates:
        return ("NO DATA — PENDING", 0.0)
    return max(candidates, key=lambda c: c[1])


def _dc_cell(p: FixtureProbabilities) -> str:
    """Double-chance / BTTS merged cell, per frozen example 'DC/BTTS (e.g. 1X82 / Y58)'.
    DC options: 1X (home-or-draw), X2 (draw-or-away), 12 (home-or-away)."""
    dc_options = [
        ("1X", p.p_home + p.p_draw),
        ("X2", p.p_draw + p.p_away),
        ("12", p.p_home + p.p_away),
    ]
    label, prob = max(dc_options, key=lambda t: t[1])
    # A STRETCH 1X2-only rating has no BTTS opinion (None, HR35) — the cell
    # reports DC with a missing BTTS half rather than crashing.
    if p.p_btts_yes is None:
        return f"{label}{round(prob*100)} / —"
    btts_label, btts_prob = (("Y", p.p_btts_yes) if p.p_btts_yes >= 0.5
                              else ("N", 1 - p.p_btts_yes))
    return f"{label}{round(prob*100)} / {btts_label}{round(btts_prob*100)}"


def render_part2_the_scan(board: list[BoardFixture]) -> str:
    """Wide board — every scanned fixture, one row each. Frozen columns:
    Fixture | 1X2 (pick.prob%) | O1.5/O2.5 | DC/BTTS | Src"""
    rows = ["PART 2 — THE SCAN",
            "Fixture | 1X2 | O1.5/O2.5 | DC/BTTS | Src"]
    for bf in board:
        src = stamp(bf.verification)
        if bf.probs is None:
            rows.append(f"{bf.fixture} | NO DATA — PENDING | — | — | {src}")
            continue
        p = bf.probs
        one_x_two = max(
            (f"{p.home_team[:10]}\u00b7{round(p.p_home*100)}%", p.p_home),
            (f"Draw\u00b7{round(p.p_draw*100)}%", p.p_draw),
            (f"{p.away_team[:10]}\u00b7{round(p.p_away*100)}%", p.p_away),
            key=lambda t: t[1],
        )[0]
        goals_cell = f"{_lean(p.p_over_15,'1.5')} / {_lean(p.p_over_25,'2.5')}"
        rows.append(f"{bf.fixture} | {one_x_two} | {goals_cell} | {_dc_cell(p)} | {src}")
    return "\n".join(rows)


def render_part2_compact(board: list[BoardFixture],
                         codes: Optional[dict] = None) -> str:
    """HR57 compact Layer 2 fast-scan: just Fixture | Selected Pick | Booking
    Code — sitting ABOVE the full Layer 2 grid (render_part2_the_scan), not
    replacing it. Same booking code across the whole layer (ID409 — one code
    for the Layer 2 scan, not per fixture). If the booking bridge has not
    produced a Layer 2 aggregate code, the column renders the honest
    NO DATA — PENDING (HR35), never a fabricated code.

    'Selected Pick' is the fixture's best-EV market in words when priced
    (best_market), else the 1X2 result pick; an unrated fixture keeps its row
    as NO DATA — PENDING so the fast-scan shows the real matchday."""
    L2_CODE_LABEL = "Layer 2"
    layer_code = None
    if codes:
        for r in codes.get("results") or []:
            if r.get("label") == L2_CODE_LABEL and r.get("code"):
                layer_code = r["code"]
                break
    code_cell = layer_code or "NO DATA — PENDING"

    rows = ["PART 2 — COMPACT (fast-scan)",
            "Fixture | Selected Pick | Booking Code"]
    for bf in board:
        if bf.probs is None:
            rows.append(f"{bf.fixture} | NO DATA — PENDING | {code_cell}")
            continue
        if bf.best_market:
            pick = bf.best_market
        else:
            # _result_pick returns (name, prob, is_away); name is the predicted
            # winner or 'Draw' — render faithfully.
            name, _prob, _is_away = _result_pick(bf)
            pick = name if name == "Draw" else f"{name} to win"
        rows.append(f"{bf.fixture} | {pick} | {code_cell}")
    return "\n".join(rows)


def render_part3_rejected(board: list[BoardFixture],
                          production: Optional[object] = None) -> str:
    """Render rejected fixtures + ID420 watchlist (odds > 2.00)."""
    rejected = [bf for bf in board if bf.rejection_reason]
    rows = ["PART 3 — REJECTED / WATCHLIST"]
    if not rejected:
        rows.append("None.")
    else:
        for bf in rejected:
            rows.append(f"{bf.fixture}: {bf.rejection_reason}")

    # ID420 watchlist: legs with odds > 2.00 (not capital-eligible)
    if production is not None and hasattr(production, 'watchlist') and production.watchlist:
        if rejected:
            rows.append("")  # blank line separator
        rows.append("  ⚠ WATCHLIST (ID420 — odds > 2.00) — NOT CAPITAL, review only")
        for leg in production.watchlist:
            rows.append(f"    {leg.fixture} ({leg.league}) — {leg.market_name} "
                        f"@ {leg.price:.2f}  edge {leg.edge:+.2%}  "
                        f"{getattr(leg, 'verification_stamp', '') or ''}")
    return "\n".join(rows)


def render_part4_data_integrity(board: list[BoardFixture]) -> str:
    counts = {t: 0 for t in Tier}
    for bf in board:
        counts[bf.verification.tier] += 1
    rows = ["PART 4 — DATA INTEGRITY (ID403 counts)"]
    for t in Tier:
        rows.append(f"{t.value}: {counts[t]}")
    return "\n".join(rows)


def render_part5_signoff(hard_rules_note: str = "") -> str:
    return ("PART 5 — HARD RULES + SIGN-OFF\n"
            f"{hard_rules_note}\n"
            "Honest edge statement: the framework is an excellent informed "
            "process but NOT a demonstrated profitable edge.\n"
            "Capital authority: THE ARCHITECT. Nothing here is live until "
            "the Architect deploys it.")


def _sanitize_phone_output(text: str) -> str:
    """Post-process the rendered board for Telegram/phone delivery.

    Strips debug-heavy markers that belong on-disk for audit, not on the phone:
    - "NO DATA — PENDING" → "—"
    - "PENDING" (standalone) → "—"
    - "NO DATA" (standalone) → "—"

    This runs ONLY when only_rated=True (phone mode). The on-disk file
    retains all markers for audit/debug per HR35."""
    # Replace the verbose debug markers with clean dashes
    # Order matters: longest patterns first to avoid partial overlaps
    text = text.replace("NO DATA — PENDING", "—")
    text = text.replace("NO DATA", "—")
    text = text.replace("PENDING", "—")
    return text


def render_blended_output(mode: str, phase: str, leagues_scanned: list[str],
                           calibration_count: int, mean_clv: Optional[float],
                           data_flags: list[str], board: list[BoardFixture],
                           production: Optional[object] = None,
                           codes: Optional[dict] = None,
                           odds_index: Optional[dict] = None,
                           only_rated: bool = False) -> str:
    """BLENDED TELEGRAM OUTPUT (compact=False) — Architect 2026-08-28 design.

    Four-table structure with AI Pick per fixture in TABLE 1:
    TABLE 1 — LAYER 2 FULL GRID: Every fixture × every market probability
    with Selected Pick column and AI Pick shown directly under each fixture.
    One shared booking code for the entire layer.

    TABLE 2 — LAYER 1 COMPACT: Deploy-eligible singles (on_deploy_shortlist),
    one row each with its own booking code.

    TABLE 3 — ACCA ROUTE: Capital-eligible fixtures grouped into accas,
    each acca with its own booking code.

    TABLE 4 — THE PICK: Primary single + Acca A recommendation.

    Booking codes marked PENDING throughout — placeholder structure maintained
    so nothing needs re-laying-out once read_betslip_combined_odds is fixed.

    only_rated=True drops unrated fixtures and strips debug markers
    ("NO DATA — PENDING", "PENDING", "NO DATA") for clean phone delivery.
    The on-disk board retains full markers for audit.
    """
    from collections import defaultdict
    today = date.today().isoformat()

    # League to country mapping for display
    LEAGUE_COUNTRY = {
        "Premier League": "England",
        "Championship": "England",
        "League One": "England",
        "League Two": "England",
        "FA Cup": "England",
        "EFL Cup": "England",
        "La Liga": "Spain",
        "La Liga 2": "Spain",
        "Copa del Rey": "Spain",
        "Serie A": "Italy",
        "Serie B": "Italy",
        "Coppa Italia": "Italy",
        "Bundesliga": "Germany",
        "2. Bundesliga": "Germany",
        "DFB-Pokal": "Germany",
        "Ligue 1": "France",
        "Ligue 2": "France",
        "Coupe de France": "France",
        "Eredivisie": "Netherlands",
        "KNVB Beker": "Netherlands",
        "Primeira Liga": "Portugal",
        "Belgian Pro League": "Belgium",
        "Scottish Premiership": "Scotland",
        "Turkish Super Lig": "Turkey",
        "Russian Premier League": "Russia",
        "Swiss Super League": "Switzerland",
        "Austrian Bundesliga": "Austria",
        "Danish Superliga": "Denmark",
        "Norwegian Eliteserien": "Norway",
        "Swedish Allsvenskan": "Sweden",
        "Polish Ekstraklasa": "Poland",
        "Greek Super League": "Greece",
        "Ukrainian Premier League": "Ukraine",
        "Croatian HNL": "Croatia",
        "Romanian Liga 1": "Romania",
        "Czech First League": "Czech Republic",
        "Slovak Super Liga": "Slovakia",
        "Slovenian PrvaLiga": "Slovenia",
        "Hungarian NB I": "Hungary",
        "Bulgarian First League": "Bulgaria",
        "Serbian SuperLiga": "Serbia",
        "Finnish Veikkausliiga": "Finland",
        "Estonian Meistriliiga": "Estonia",
        "Latvian Virsliga": "Latvia",
        "Lithuanian A Lyga": "Lithuania",
        "Champions League": "Europe",
        "Europa League": "Europe",
        "Conference League": "Europe",
    }

    if production is None:
        production = build_production_bets(board)

    # Filter to only fixtures with probabilities when only_rated=True (phone mode)
    if only_rated:
        board = [bf for bf in board if bf.probs is not None]

    # Get Layer 2 booking code (shared across all fixtures)
    L2_CODE_LABEL = "Layer 2"
    layer2_code = "NO DATA — PENDING"
    if codes and codes.get("results"):
        for r in codes["results"]:
            if r.get("label") == L2_CODE_LABEL and r.get("code"):
                layer2_code = r["code"]
                break

    lines = [
        "##########OLP XDV#########",
        "==================================",
        "",
        f"📅  {date.today().strftime('%a %d %b %Y')}   (PICK · win %  ·  alt markets)",
        "",
    ]

    # Filter board to only fixtures with probs (rated fixtures only)
    rated_board = [bf for bf in board if bf.probs is not None]

    # ========== TABLE 1: LAYER 2 FULL GRID WITH AI PICK ==========
    lines.append("──────────────────────────────────")
    lines.append("TABLE 1 · LAYER 2 — FULL MARKET GRID + AI PICK")
    lines.append("──────────────────────────────────")

    # Group by league
    by_league: dict[str, list[BoardFixture]] = defaultdict(list)
    for bf in rated_board:
        league = _league_of(bf)
        by_league[league].append(bf)

    for league in sorted(by_league.keys()):
        fixtures = by_league[league]
        country = LEAGUE_COUNTRY.get(league, "")
        header = f"⚽ {league}" + (f" ({country})" if country else "")
        lines.append(header)
        for bf in fixtures:
            fx_name = _short_fixture(bf)
            # Resolve kickoff time
            home_team = ""
            away_team = ""
            if " v " in fx_name:
                home_team, away_team = fx_name.split(" v ", 1)
                home_team = home_team.strip()
                away_team = away_team.strip()
            ko = _kickoff_for(bf, home_team, away_team)

            lines.append(f"   {ko}   {fx_name}")

            p = bf.probs
            # Show all market probabilities
            alt = []
            if p.p_over_15 is not None:
                alt.append(f"O1.5 {round(p.p_over_15*100)}%")
            if p.p_over_25 is not None:
                alt.append(f"O2.5 {round(p.p_over_25*100)}%")
            if p.p_over_35 is not None:
                alt.append(f"O3.5 {round(p.p_over_35*100)}%")
            if p.p_btts_yes is not None:
                alt.append(f"BTTS {round(p.p_btts_yes*100)}%")

            if alt:
                lines.append(f"       {'  ·  '.join(alt)}")

            # AI Pick: highest-probability market for this fixture
            best_market_name, model_prob, _, _ = _get_fixture_best_market(bf, odds_index)
            if best_market_name != "NO DATA — PENDING" and model_prob is not None:
                lines.append(f"       AI pick = {best_market_name} {round(model_prob*100)}%")
            else:
                # Fallback to 1X2 result pick
                name, prob, _ = _result_pick(bf)
                lines.append(f"       AI pick = {name} {round(prob*100)}%")

    lines.append("")
    lines.append(f"Board code: {layer2_code} (booking-code read postponed — technical issue,")
    lines.append("tracked internally, not blocking pipeline output)")
    lines.append("")

    # ========== TABLE 2: LAYER 1 COMPACT ==========
    lines.append("──────────────────────────────────")
    lines.append("TABLE 2 · LAYER 1 — DEPLOY-ELIGIBLE SINGLES")
    lines.append("(fixtures that clear the deploy threshold, one row each, own code)")
    lines.append("──────────────────────────────────")

    shortlist = [bf for bf in board if bf.on_deploy_shortlist and bf.kickoff_date == today and bf.probs is not None]
    if not shortlist:
        lines.append("No deploy-eligible fixtures kicking off today.")
    else:
        for bf in shortlist:
            fx_name = _short_fixture(bf)

            best_market_name, model_prob, price, bookmaker = _get_fixture_best_market(bf, odds_index)
            if best_market_name != "NO DATA — PENDING" and model_prob is not None:
                lines.append(f"📈 {fx_name} — {best_market_name} — {round(model_prob*100)}%")
            else:
                name, prob, _ = _result_pick(bf)
                lines.append(f"📈 {fx_name} — {name} — {round(prob*100)}%")

            # Get fixture-specific booking code
            fixture_code = "NO DATA — PENDING"
            if codes and codes.get("results"):
                for r in codes["results"]:
                    if bf.fixture in r.get("label", "") and r.get("code"):
                        fixture_code = r["code"]
                        break
            lines.append(f"    Code: {fixture_code}")

    lines.append("")

    # ========== TABLE 3: ACCA ROUTE ==========
    lines.append("──────────────────────────────────")
    lines.append("TABLE 3 · ACCA ROUTE")
    lines.append("(capital-eligible grouped accumulators, own code per acca)")
    lines.append("──────────────────────────────────")

    if not hasattr(production, 'accas') or not production.accas:
        lines.append("No capital-eligible accas generated.")
    else:
        for acca in production.accas:
            label = acca.get("label", "Acca")
            combined_odds = acca.get("combined_odds", 0)
            combined_prob = acca.get("combined_prob", 0)
            n_legs = acca.get("n_legs", 0)
            legs = acca.get("legs", [])

            # Get acca-specific booking code
            acca_code = "NO DATA — PENDING"
            if codes and codes.get("results"):
                for r in codes["results"]:
                    if label in r.get("label", "") and r.get("code"):
                        acca_code = r["code"]
                        break

            lines.append(f"{label} ({n_legs}-fold):")
            for i, leg in enumerate(legs, 1):
                fixture = leg.get("fixture", "?")
                market_name = leg.get("market_name", "?")
                prob = leg.get("prob", 0)
                lines.append(f"  {i}. {fixture} — {market_name} — {prob:.2%}")

            lines.append(f"  Combined odds: {combined_odds:.2f}")
            lines.append(f"  Code: {acca_code}")
            lines.append("")

    # ========== TABLE 4: THE PICK ==========
    lines.append("──────────────────────────────────")
    lines.append("TABLE 4 · THE PICK")
    lines.append("(primary single + Acca A recommendation)")
    lines.append("──────────────────────────────────")

    if shortlist:
        # Apply "wide eyes, narrow hands" filter for THE PICK as well
        validated_shortlist = validate_the_call(shortlist)
        if not validated_shortlist:
            lines.append("NO VALIDATED PICK — all fixtures fail EV>0 or divergence gates")
        else:
            # Primary single: highest EV from validated shortlist
            best_single = None
            best_ev = None
            for bf in validated_shortlist:
                if bf.probs is None or bf.best_mes_ev is None:
                    continue
                if best_ev is None or bf.best_mes_ev > best_ev:
                    best_ev = bf.best_mes_ev
                    best_single = bf

        if best_single:
            p = best_single.probs
            lines.append(f"🎯 Primary single: {best_single.fixture}")
            lines.append(f"  Market: {best_single.best_market}")
            lines.append(f"  Price: {best_single.best_price:.2f} ({best_single.best_bookmaker})")
            lines.append(f"  Model Prob: {round((best_single.best_model_prob or 0)*100)}%")
            lines.append(f"  MES EV: {best_single.best_mes_ev:+.2%}")
            lines.append(f"  Verification: {stamp(best_single.verification)}")
            # Get booking code for this pick
            pick_code = "NO DATA — PENDING"
            if codes and codes.get("results"):
                for r in codes["results"]:
                    if best_single.fixture in r.get("label", "") and r.get("code"):
                        pick_code = r["code"]
                        break
            lines.append(f"  Code: {pick_code}")

    # Acca recommendation
    if production and hasattr(production, 'accas') and production.accas:
        acca = production.accas[0]  # Acca A is the headline
        label = acca.get("label", "Acca A")
        combined_odds = acca.get("combined_odds", 0)
        combined_prob = acca.get("combined_prob", 0)
        n_legs = acca.get("n_legs", 0)

        acca_code = "NO DATA — PENDING"
        if codes and codes.get("results"):
            for r in codes["results"]:
                if label in r.get("label", "") and r.get("code"):
                    acca_code = r["code"]
                    break

        lines.append("")
        lines.append(f"🎯 Acca {label} recommendation: {n_legs} legs")
        lines.append(f"  Combined Odds: {combined_odds:.2f} | Combined Prob: {combined_prob:.2%}")
        lines.append(f"  Code: {acca_code}")

    lines.append("")
    lines.append("==================================")
    lines.append("Honest edge: not a demonstrated edge · Capital: Architect only.")
    lines.append("Booking codes: PENDING pipeline-wide — technical issue under repair,")
    lines.append("tracking resumes once read_betslip_combined_odds is fixed.")
    lines.append("==================================")

    full_text = "\n".join(lines)

    # Post-process for phone delivery: strip debug markers
    if only_rated:
        full_text = _sanitize_phone_output(full_text)

    return full_text


def render_produce_bet(mode: str, phase: str, leagues_scanned: list[str],
                        calibration_count: int, mean_clv: Optional[float],
                        data_flags: list[str], board: list[BoardFixture],
                        stacked: bool = True,
                        produced_bet: Optional[dict] = None,
                        production: Optional[object] = None,
                        codes: Optional[dict] = None,
                        include_data_flags: bool = True,
                        only_rated: bool = False,
                        compact: bool = True) -> str:
    """FOUR-TABLE OUTPUT STRUCTURE (Architect 2026-08-21):

    TABLE 1 — LAYER 2 FULL GRID: Every fixture × every market probability with
    Selected Pick column, one shared booking code for the entire layer.

    TABLE 2 — LAYER 1 COMPACT: One row per fixture with its own booking code.

    TABLE 3 — ACCA ROUTE: Only capital-eligible fixtures grouped into accas,
    each acca with its own booking code.

    TABLE 4 — THE PICK: Final recommendation after all three tables.

    All markets considered (ID405 gate open per Architect 2026-08-11).
    Alternative markets (BTTS, Double Chance, Over/Under 1.5, Over/Under 2.5,
    Draw No Bet, Over/Under 3.5, Over/Under 0.5, HT/FT, Correct Score) are
    evaluated for every fixture and the best-EV market is selected per fixture.

    include_data_flags=False omits the DATA FLAGS section from the output
    (Architect 2026-08-28: flags live on disk/web, not in the phone message).
    only_rated=True drops unrated fixtures (those rendering as NO DATA — PENDING)
    from the phone push so the message shows only priced, scored fixtures;
    the on-disk board keeps the full scan for audit.

    When only_rated=True (phone mode), the output is post-processed to strip
    debug markers ("NO DATA — PENDING", "PENDING", "NO DATA") for a clean
    mobile message. The on-disk board retains full markers for audit.

    compact=False (new, 2026-08-28): Uses the blended Telegram output design
    with AI Pick per fixture shown directly in TABLE 1, matching the mockup
    format requested by the Architect."""
    # compact=False: use the new blended output design
    if not compact:
        # Build odds index for market pricing
        odds_index = None
        try:
            from data.multi_source_concrete import get_odds as multi_get_odds
            import pipeline.odds as odds_mod
            from booking.bridge import load_all_sportybet_fixtures
            odds_index = {}
            odds_leagues = set(fx["league"] for fx in board if hasattr(fx, "fixture"))
            for lg in sorted(odds_leagues):
                try:
                    fixtures = multi_get_odds(lg)
                    odds_index.update(odds_mod.index_by_fixture(fixtures))
                except Exception:
                    pass
            # Merge SportyBet cache odds
            sb_fixtures_by_league = load_all_sportybet_fixtures(days_ahead=3, leagues=list(odds_leagues))
            for lg, sb_fixtures in sb_fixtures_by_league.items():
                for sb_fx in sb_fixtures:
                    if sb_fx.home_odds and sb_fx.draw_odds and sb_fx.away_odds:
                        key = (sb_fx.home_team, sb_fx.away_team)
                        if key not in odds_index:
                            sb_odds = odds_mod.FixtureOdds(
                                league=lg, home_team=sb_fx.home_team, away_team=sb_fx.away_team,
                                kickoff_utc=sb_fx.kickoff_utc,
                                home=odds_mod.MarketQuote(price=sb_fx.home_odds, bookmaker="SportyBet Nigeria", n_books=1, captured_at=sb_fx.kickoff_utc),
                                draw=odds_mod.MarketQuote(price=sb_fx.draw_odds, bookmaker="SportyBet Nigeria", n_books=1, captured_at=sb_fx.kickoff_utc),
                                away=odds_mod.MarketQuote(price=sb_fx.away_odds, bookmaker="SportyBet Nigeria", n_books=1, captured_at=sb_fx.kickoff_utc),
                                source="sportybet-cache", source_tier="T2"
                            )
                            odds_index[key] = sb_odds
        except Exception:
            odds_index = None

        return render_blended_output(mode, phase, leagues_scanned, calibration_count,
                                      mean_clv, data_flags, board, production, codes, odds_index, only_rated)

    # compact=True: original four-table output
    today = date.today().isoformat()
    # only_rated: phone push shows priced fixtures only; unrated rows stay on disk
    if only_rated:
        board = [bf for bf in board if bf.probs is not None]
    shortlist = [bf for bf in board
                 if bf.on_deploy_shortlist and bf.kickoff_date == today]
    if production is None:
        production = build_production_bets(board)

    # Build odds index for market pricing (same as Agent 5)
    odds_index = None
    try:
        from data.multi_source_concrete import get_odds as multi_get_odds
        import pipeline.odds as odds_mod
        from booking.bridge import load_all_sportybet_fixtures
        odds_index = {}
        odds_leagues = set(fx["league"] for fx in board if hasattr(fx, "fixture"))
        for lg in sorted(odds_leagues):
            try:
                fixtures = multi_get_odds(lg)
                odds_index.update(odds_mod.index_by_fixture(fixtures))
            except Exception:
                pass
        # Merge SportyBet cache odds
        sb_fixtures_by_league = load_all_sportybet_fixtures(days_ahead=3, leagues=list(odds_leagues))
        for lg, sb_fixtures in sb_fixtures_by_league.items():
            for sb_fx in sb_fixtures:
                if sb_fx.home_odds and sb_fx.draw_odds and sb_fx.away_odds:
                    key = (sb_fx.home_team, sb_fx.away_team)
                    if key not in odds_index:
                        sb_odds = odds_mod.FixtureOdds(
                            league=lg, home_team=sb_fx.home_team, away_team=sb_fx.away_team,
                            kickoff_utc=sb_fx.kickoff_utc,
                            home=odds_mod.MarketQuote(price=sb_fx.home_odds, bookmaker="SportyBet Nigeria", n_books=1, captured_at=sb_fx.kickoff_utc),
                            draw=odds_mod.MarketQuote(price=sb_fx.draw_odds, bookmaker="SportyBet Nigeria", n_books=1, captured_at=sb_fx.kickoff_utc),
                            away=odds_mod.MarketQuote(price=sb_fx.away_odds, bookmaker="SportyBet Nigeria", n_books=1, captured_at=sb_fx.kickoff_utc),
                            source="sportybet-cache", source_tier="T2"
                        )
                        odds_index[key] = sb_odds
    except Exception:
        odds_index = None

    parts = [
        render_part0(mode, phase, leagues_scanned, calibration_count, mean_clv, data_flags, include_data_flags=include_data_flags),
        "",
        # TABLE 1: LAYER 2 FULL GRID
        render_layer2_full_grid(board, codes=codes, odds_index=odds_index),
        "",
        # TABLE 2: LAYER 1 COMPACT
        render_layer1_compact(board, codes=codes, odds_index=odds_index),
        "",
        # TABLE 3: ACCA ROUTE
        render_acca_route(board, production, codes=codes, odds_index=odds_index),
        "",
        # TABLE 4: THE PICK
        render_the_pick(board, production, shortlist, codes=codes),
        "",
        render_part5_signoff(),
    ]
    full_text = "\n".join(parts)

    # Post-process for phone delivery: strip debug markers
    if only_rated:
        full_text = _sanitize_phone_output(full_text)

    return full_text


def _get_fixture_best_market(bf: BoardFixture, odds_index: Optional[dict]) -> tuple[str, Optional[float], Optional[float], Optional[str]]:
    """Get the best market for a fixture based on EV (model_prob * price - 1).
    Returns (market_name, model_prob, price, bookmaker) or (NO DATA, None, None, None)."""
    if bf.probs is None:
        return ("NO DATA — PENDING", None, None, None)

    p = bf.probs
    best_ev = None
    best_market = None
    best_price = None
    best_bookmaker = None
    best_model_prob = None

    # Get fixture odds from index
    fixture_key = None
    if odds_index:
        # Find matching fixture in odds index
        for key, fx_odds in odds_index.items():
            if key[0] == p.home_team and key[1] == p.away_team:
                fixture_key = key
                break

    if not fixture_key:
        # Fall back to stored best_market on BoardFixture
        if bf.best_market and bf.best_price is not None:
            return (bf.best_market, bf.best_model_prob, bf.best_price, bf.best_bookmaker)
        # Fall back to SportyBet odds
        if bf.sb_home_odds is not None or bf.sb_draw_odds is not None or bf.sb_away_odds is not None:
            # Find best EV among SportyBet 1X2
            if bf.sb_home_odds:
                ev = mes_numeric_ev(p.p_home, bf.sb_home_odds)
                if best_ev is None or (ev is not None and ev > best_ev):
                    best_ev = ev
                    best_market = f"{p.home_team} to win"
                    best_price = bf.sb_home_odds
                    best_bookmaker = "SportyBet Nigeria"
                    best_model_prob = p.p_home
            if bf.sb_draw_odds:
                ev = mes_numeric_ev(p.p_draw, bf.sb_draw_odds)
                if best_ev is None or (ev is not None and ev > best_ev):
                    best_ev = ev
                    best_market = "Draw"
                    best_price = bf.sb_draw_odds
                    best_bookmaker = "SportyBet Nigeria"
                    best_model_prob = p.p_draw
            if bf.sb_away_odds:
                ev = mes_numeric_ev(p.p_away, bf.sb_away_odds)
                if best_ev is None or (ev is not None and ev > best_ev):
                    best_ev = ev
                    best_market = f"{p.away_team} to win"
                    best_price = bf.sb_away_odds
                    best_bookmaker = "SportyBet Nigeria"
                    best_model_prob = p.p_away
            if best_market:
                return (best_market, best_model_prob, best_price, best_bookmaker)
        return ("NO DATA — PENDING", None, None, None)

    fx_odds = odds_index[fixture_key]

    # Check ALL EDGE_MARKETS for best EV
    for key in mkt.EDGE_MARKETS:
        model_p = mkt.model_prob(key, p)
        if model_p is None:
            continue
        quote_obj = mkt.quote(key, fx_odds)
        if quote_obj is None or quote_obj.price is None:
            continue
        price = quote_obj.price
        ev = model_p * price - 1
        if best_ev is None or ev > best_ev:
            best_ev = ev
            best_market = mkt.display(key, p.home_team, p.away_team)
            best_price = price
            best_bookmaker = quote_obj.bookmaker
            best_model_prob = model_p

    if best_market:
        return (best_market, best_model_prob, best_price, best_bookmaker)
    return ("NO DATA — PENDING", None, None, None)


def _get_all_market_probs(bf: BoardFixture, odds_index: Optional[dict]) -> dict[str, tuple[Optional[float], Optional[float], Optional[str]]]:
    """Get all market probabilities, prices, and bookmakers for a fixture.
    Returns dict: market_key -> (model_prob, price, bookmaker)."""
    if bf.probs is None:
        return {}

    p = bf.probs
    result = {}

    fixture_key = None
    if odds_index:
        for key, fx_odds in odds_index.items():
            if key[0] == p.home_team and key[1] == p.away_team:
                fixture_key = key
                break

    if not fixture_key:
        return {}

    fx_odds = odds_index[fixture_key]

    for key in mkt.EDGE_MARKETS:
        model_p = mkt.model_prob(key, p)
        quote_obj = mkt.quote(key, fx_odds)
        price = quote_obj.price if quote_obj else None
        bookmaker = quote_obj.bookmaker if quote_obj else None
        result[key] = (model_p, price, bookmaker)

    return result


def _format_prob_cell(prob: Optional[float]) -> str:
    """Format a probability as percentage or '—' if None."""
    if prob is None:
        return "—"
    return f"{round(prob * 100)}%"


def _format_price_cell(price: Optional[float]) -> str:
    """Format a price or '—' if None."""
    if price is None:
        return "—"
    return f"{price:.2f}"


def render_layer2_full_grid(board: list[BoardFixture],
                             codes: Optional[dict] = None,
                             odds_index: Optional[dict] = None) -> str:
    """TABLE 1 — LAYER 2 FULL GRID: Every fixture × every market probability
    with Selected Pick column, one shared booking code for the entire layer."""

    L2_CODE_LABEL = "Layer 2"
    layer_code = None
    if codes:
        for r in codes.get("results") or []:
            if r.get("label") == L2_CODE_LABEL and r.get("code"):
                layer_code = r["code"]
                break
    code_cell = layer_code or "NO DATA — PENDING"

    # Build header with all EDGE_MARKETS
    market_headers = [mkt.display(k, "Home", "Away") for k in mkt.EDGE_MARKETS]
    header_cols = ["Fixture", "Selected Pick"] + market_headers + ["Booking Code"]

    rows = ["TABLE 1 — LAYER 2 FULL GRID",
            " | ".join(header_cols)]

    for bf in board:
        if bf.probs is None:
            row = [bf.fixture, "NO DATA — PENDING"] + ["—"] * len(mkt.EDGE_MARKETS) + [code_cell]
            rows.append(" | ".join(row))
            continue

        p = bf.probs
        # Get best market for Selected Pick
        best_market_name, _, _, _ = _get_fixture_best_market(bf, odds_index)

        # Get all market probabilities
        market_probs = _get_all_market_probs(bf, odds_index)

        # Build row: Fixture | Selected Pick | market1_prob | market2_prob | ... | Booking Code
        prob_cells = []
        for key in mkt.EDGE_MARKETS:
            model_p, price, bookmaker = market_probs.get(key, (None, None, None))
            # Show probability if available, else price if available, else —
            if model_p is not None:
                prob_cells.append(_format_prob_cell(model_p))
            elif price is not None:
                prob_cells.append(f"@{_format_price_cell(price)}")
            else:
                prob_cells.append("—")

        row = [bf.fixture, best_market_name] + prob_cells + [code_cell]
        rows.append(" | ".join(row))

    return "\n".join(rows)


def render_layer1_compact(board: list[BoardFixture],
                           codes: Optional[dict] = None,
                           odds_index: Optional[dict] = None) -> str:
    """TABLE 2 — LAYER 1 COMPACT: One row per fixture with its own booking code.
    Only deploy-eligible fixtures (on_deploy_shortlist) kicking off TODAY."""

    today = date.today().isoformat()
    shortlist = [bf for bf in board if bf.on_deploy_shortlist and bf.kickoff_date == today]
    if not shortlist:
        return ("TABLE 2 — LAYER 1 COMPACT\n"
                "No deploy-eligible fixtures kicking off today.")

    rows = ["TABLE 2 — LAYER 1 COMPACT",
            "Fixture | Selected Pick | Model Prob | Price | Bookmaker | EV | Booking Code"]

    for bf in shortlist:
        if bf.probs is None:
            rows.append(f"{bf.fixture} | NO DATA — PENDING | — | — | — | — | NO DATA — PENDING")
            continue

        p = bf.probs
        best_market_name, model_prob, price, bookmaker = _get_fixture_best_market(bf, odds_index)

        # Calculate EV
        ev_str = "—"
        if model_prob is not None and price is not None:
            ev = model_prob * price - 1
            ev_str = f"{ev:+.2%}"

        # Get fixture-specific booking code
        fixture_code = "NO DATA — PENDING"
        if codes and codes.get("results"):
            for r in codes["results"]:
                # Try to match by fixture name in label
                if bf.fixture in r.get("label", "") and r.get("code"):
                    fixture_code = r["code"]
                    break

        prob_str = _format_prob_cell(model_prob)
        price_str = _format_price_cell(price)
        bookmaker_str = bookmaker or "—"

        rows.append(f"{bf.fixture} | {best_market_name} | {prob_str} | {price_str} | {bookmaker_str} | {ev_str} | {fixture_code}")

    return "\n".join(rows)


def render_acca_route(board: list[BoardFixture],
                       production: Optional[object] = None,
                       codes: Optional[dict] = None,
                       odds_index: Optional[dict] = None) -> str:
    """TABLE 3 — ACCA ROUTE: Only capital-eligible fixtures grouped into accas,
    each acca with its own booking code."""

    if production is None:
        from engine.acca import build_production_bets
        production = build_production_bets(board)

    rows = ["TABLE 3 — ACCA ROUTE"]

    if not hasattr(production, 'accas') or not production.accas:
        rows.append("No capital-eligible accas generated.")
        return "\n".join(rows)

    for acca in production.accas:
        label = acca.get("label", "Acca")
        combined_odds = acca.get("combined_odds", 0)
        combined_prob = acca.get("combined_prob", 0)
        n_legs = acca.get("n_legs", 0)
        legs = acca.get("legs", [])

        # Get acca-specific booking code
        acca_code = "NO DATA — PENDING"
        if codes and codes.get("results"):
            for r in codes["results"]:
                if label in r.get("label", "") and r.get("code"):
                    acca_code = r["code"]
                    break

        rows.append(f"")
        rows.append(f"{label} — Combined Odds: {combined_odds:.2f} | Combined Prob: {combined_prob:.2%} | Legs: {n_legs} | Booking Code: {acca_code}")
        # ID407 — acca compounding disclosure
        if n_legs > 1:
            rows.append(f"  Combined prob {combined_prob:.1%} (product of {n_legs} legs — compounding is arithmetic, not a weakness)")
        rows.append("Fixture | Market | Price | Model Prob | EV | Verification")

        for leg in legs:
            fixture = leg.get("fixture", "?")
            market_name = leg.get("market_name", "?")
            price = leg.get("price", 0)
            prob = leg.get("prob", 0)
            ev = leg.get("ev", 0)
            verification = leg.get("verification_stamp", "")

            rows.append(f"{fixture} | {market_name} | {price:.2f} | {prob:.2%} | {ev:+.2%} | {verification}")

    return "\n".join(rows)


def render_the_pick(board: list[BoardFixture],
                     production: Optional[object] = None,
                     shortlist: Optional[list[BoardFixture]] = None,
                     codes: Optional[dict] = None) -> str:
    """TABLE 4 — THE PICK: Final recommendation after all three tables."""

    rows = ["TABLE 4 — THE PICK"]

    if shortlist is None:
        today = date.today().isoformat()
        shortlist = [bf for bf in board if bf.on_deploy_shortlist and bf.kickoff_date == today]

    if not shortlist:
        rows.append("No deploy-eligible fixtures kicking off today — no pick.")
        return "\n".join(rows)

    # Primary recommendation: highest EV single from shortlist
    best_single = None
    best_ev = None

    for bf in shortlist:
        if bf.probs is None or bf.best_mes_ev is None:
            continue
        if best_ev is None or bf.best_mes_ev > best_ev:
            best_ev = bf.best_mes_ev
            best_single = bf

    if best_single:
        p = best_single.probs
        rows.append(f"PRIMARY SINGLE: {best_single.fixture}")
        rows.append(f"  Market: {best_single.best_market}")
        rows.append(f"  Price: {best_single.best_price:.2f} ({best_single.best_bookmaker})")
        rows.append(f"  Model Prob: {round((best_single.best_model_prob or 0)*100)}%")
        rows.append(f"  MES EV: {best_single.best_mes_ev:+.2%}")
        rows.append(f"  Verification: {stamp(best_single.verification)}")
        if best_single.engine_divergence:
            rows.append(f"  ⚠ Elo divergence: {best_single.engine_divergence}")
        if best_single.goals_divergence:
            rows.append(f"  ⚠ xG goals divergence: {best_single.goals_divergence}")

        # Get booking code for this pick
        pick_code = "NO DATA — PENDING"
        if codes and codes.get("results"):
            for r in codes["results"]:
                if best_single.fixture in r.get("label", "") and r.get("code"):
                    pick_code = r["code"]
                    break
        rows.append(f"  Booking Code: {pick_code}")

    # Acca recommendation if available
    if production and hasattr(production, 'accas') and production.accas:
        acca = production.accas[0]  # Acca A is the headline
        label = acca.get("label", "Acca A")
        combined_odds = acca.get("combined_odds", 0)
        combined_prob = acca.get("combined_prob", 0)
        n_legs = acca.get("n_legs", 0)

        acca_code = "NO DATA — PENDING"
        if codes and codes.get("results"):
            for r in codes["results"]:
                if label in r.get("label", "") and r.get("code"):
                    acca_code = r["code"]
                    break

        rows.append(f"")
        rows.append(f"ACCA RECOMMENDATION: {label} ({n_legs} legs)")
        rows.append(f"  Combined Odds: {combined_odds:.2f} | Combined Prob: {combined_prob:.2%}")
        rows.append(f"  Booking Code: {acca_code}")
        # ID407 — acca compounding disclosure
        if n_legs > 1:
            rows.append(f"  Combined prob {combined_prob:.1%} (product of {n_legs} legs — compounding is arithmetic, not a weakness)")
        rows.append(f"  Legs:")
        for leg in acca.get("legs", []):
            rows.append(f"    · {leg.get('fixture','?')} — {leg.get('market_name','?')} @ {leg.get('price',0):.2f} (EV {leg.get('ev',0):+.2%})")

    
    return "\n".join(rows)


def render_verify_results(rows: list[dict]) -> str:
    """VERIFY RESULTS frozen table. Each row dict:
    {fixture, ft, market_hits: {market: (pick, result, hit_bool)}, tally}
    HR15: 90-minute basis. ID48: FT confirmed by direct URL, else NO DATA — PENDING."""
    lines = ["VERIFY RESULTS",
             "Fixture | FT | 1X2/DC | O1.5/O2.5 | BTTS | Hit"]
    for r in rows:
        ft = r.get("ft") or "NO DATA — PENDING"
        lines.append(f"{r['fixture']} | {ft} | {r.get('onextwo','—')} | "
                     f"{r.get('goals','—')} | {r.get('btts','—')} | {r.get('tally','—')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TELEGRAM TABLE BOARD  (Architect 2026-08-05)
# ---------------------------------------------------------------------------
# The phone board is deliberately lean: the day's 2-4 leg recommendation, then
# one table per league — every fixture as a row, the pick in words + chance.
# No market columns, no xG/DC lines, no EV text on the phone: those live in the
# saved file board and behind /board and /why (the depth, not the decision).
#
# HR35 preserved, not traded away:
#   - full club names, never truncated (leagues become section headers so the
#     "(League)" suffix leaves the fixture cell)
#   - an unrated fixture KEEPS its row, marked NO DATA — PENDING, so the table
#     shows the real matchday rather than an edited subset
#   - every league with fixtures that day gets a table; the header names the
#     league count, and the full list lives in the saved board and /board

FENCE = "```"


def _col(rows: list[list[str]], headers: list[str]) -> str:
    """Fixed-width table. Widths come from the content, so nothing is cut."""
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))
    def line(cells):
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()
    return "\n".join([line(headers)] + [line(r) for r in rows])


def _short_fixture(bf: BoardFixture) -> str:
    """'Home v Away (League)' -> 'Home v Away'. The league is a section header,
    so repeating it on every row wastes the width full club names need."""
    return bf.fixture.split(" (")[0]


def _league_of(bf: BoardFixture) -> str:
    return bf.fixture.split(" (")[-1].rstrip(")") if " (" in bf.fixture else "—"


def render_compact_heartbeat(board: list[BoardFixture], target_date: str = None) -> str:
    """Compact heartbeat format for Telegram — clean, kickoff + pick + alt markets.

    CLEAN FORMAT (Architect 2026-08-29 directive):
    - ONLY fixtures with model probabilities (bf.probs is not None)
    - NO "NO DATA — PENDING" entries ever
    - League grouped with kickoff time
    - Alt markets line: O1.5 86%  ·  O2.5 66%  ·  O3.5 44%  ·  BTTS 58%
    - AI Pick line: AI pick = [market] [pct]%
    - Double Chance format: "Team A or Team B (double chance) 82%"

    ##########OLP XDV#########
    ==================================

    📅  Thu 27 Aug 2026   (PICK · win %  ·  alt markets)

    ⚽  Conference League
       17:00   Maccabi Tel Aviv v FC Lugano
           O1.5 86%  ·  O2.5 66%  ·  O3.5 44%  ·  BTTS 58%
           AI pick = Maccabi Tel Aviv or FC Lugano (double chance) 82%
       17:00   Qarabag v Twente
           O1.5 85%  ·  O2.5 65%  ·  O3.5 43%  ·  BTTS 56%
           AI pick = Qarabag or Twente (double chance) 82%
       17:45   Monaco v Gornik Zabrze
           O1.5 74%  ·  O2.5 48%  ·  O3.5 26%  ·  BTTS 50%
           AI pick = Over 2.5 goals 48%

    ==================================
    """
    from collections import defaultdict
    import re

    if target_date is None:
        target_date = date.today().isoformat()

    y, m, d = map(int, target_date.split('-'))
    dt = date(y, m, d)
    _WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    _MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    date_label = f'{_WEEKDAYS[dt.weekday()]} {dt.day:02d} {_MONTHS[dt.month-1]} {dt.year}'

    # League to country mapping for display
    LEAGUE_COUNTRY = {
        "Premier League": "England",
        "Championship": "England",
        "League One": "England",
        "League Two": "England",
        "FA Cup": "England",
        "EFL Cup": "England",
        "La Liga": "Spain",
        "La Liga 2": "Spain",
        "Copa del Rey": "Spain",
        "Serie A": "Italy",
        "Serie B": "Italy",
        "Coppa Italia": "Italy",
        "Bundesliga": "Germany",
        "2. Bundesliga": "Germany",
        "DFB-Pokal": "Germany",
        "Ligue 1": "France",
        "Ligue 2": "France",
        "Coupe de France": "France",
        "Eredivisie": "Netherlands",
        "KNVB Beker": "Netherlands",
        "Primeira Liga": "Portugal",
        "Belgian Pro League": "Belgium",
        "Scottish Premiership": "Scotland",
        "Turkish Super Lig": "Turkey",
        "Russian Premier League": "Russia",
        "Swiss Super League": "Switzerland",
        "Austrian Bundesliga": "Austria",
        "Danish Superliga": "Denmark",
        "Norwegian Eliteserien": "Norway",
        "Swedish Allsvenskan": "Sweden",
        "Polish Ekstraklasa": "Poland",
        "Greek Super League": "Greece",
        "Ukrainian Premier League": "Ukraine",
        "Croatian HNL": "Croatia",
        "Romanian Liga 1": "Romania",
        "Czech First League": "Czech Republic",
        "Slovak Super Liga": "Slovakia",
        "Slovenian PrvaLiga": "Slovenia",
        "Hungarian NB I": "Hungary",
        "Bulgarian First League": "Bulgaria",
        "Serbian SuperLiga": "Serbia",
        "Finnish Veikkausliiga": "Finland",
        "Estonian Meistriliiga": "Estonia",
        "Latvian Virsliga": "Latvia",
        "Lithuanian A Lyga": "Lithuania",
        "Champions League": "Europe",
        "Europa League": "Europe",
        "Conference League": "Europe",
    }

    # Group by league - ONLY fixtures with model probabilities
    leagues: dict[str, list[BoardFixture]] = defaultdict(list)
    for bf in board:
        fx = getattr(bf, "fixture", "")
        if "(" not in fx:
            continue
        # ONLY include fixtures that have model probabilities
        if getattr(bf, "probs", None) is None:
            continue
        league = fx.rsplit('(', 1)[-1].rstrip(')')
        leagues[league].append(bf)

    lines: list[str] = []
    lines.append("##########OLP XDV#########")
    lines.append("==================================")
    lines.append("")
    lines.append(f"📅  {date_label}   (PICK · win %  ·  alt markets)")
    lines.append("")

    def _best_ev_pick(p, bf) -> tuple[str, float]:
        """Return (market_label, prob) for the best market for this fixture.
        Uses the board fixture's best_market if available, otherwise falls back
        to the highest-probability market from the model's probabilities.
        """
        # Check if BoardFixture already has a priced best_market with positive EV
        if getattr(bf, "best_market", None) and getattr(bf, "best_mes_ev", None) is not None:
            if bf.best_mes_ev > 0:
                label = bf.best_market
                prob = bf.best_model_prob or 0
                return label, prob

        # Fallback: use best_market from board fixture if available
        if getattr(bf, "best_market", None):
            label = bf.best_market
            prob = bf.best_model_prob or max(p.p_home, p.p_draw, p.p_away)
            return label, prob

        # Final fallback: find highest probability across ALL model markets
        # Check goals markets
        markets = []
        if p.p_over_15 is not None:
            markets.append((f"Over 1.5 goals", p.p_over_15))
        if p.p_over_25 is not None:
            markets.append((f"Over 2.5 goals", p.p_over_25))
        if p.p_over_35 is not None:
            markets.append((f"Over 3.5 goals", p.p_over_35))
        if p.p_btts_yes is not None:
            markets.append((f"BTTS Yes", p.p_btts_yes))
        # Check 1X2
        markets.append((f"{p.home_team} to win", p.p_home))
        markets.append(("Draw", p.p_draw))
        markets.append((f"{p.away_team} to win", p.p_away))
        # Check Double Chance - format as "Team A or Team B (double chance)"
        dc_1x = p.p_home + p.p_draw
        dc_x2 = p.p_draw + p.p_away
        dc_12 = p.p_home + p.p_away
        markets.append((f"{p.home_team} or {p.away_team} (double chance)", dc_1x))
        markets.append((f"Draw or {p.away_team} (double chance)", dc_x2))
        markets.append((f"{p.home_team} or Draw (double chance)", dc_12))

        if markets:
            label, prob = max(markets, key=lambda x: x[1])
            return label, prob

        return "No pick", 0.0

    for league in sorted(leagues.keys()):
        entries = leagues[league]
        if not entries:
            continue
        country = LEAGUE_COUNTRY.get(league, "")
        header = f"⚽  {league}" + (f" ({country})" if country else "")
        lines.append(header)

        for bf in entries:
            fx = getattr(bf, "fixture", "")
            match = fx.rsplit('(', 1)[0].strip()

            p = getattr(bf, "probs", None)
            if not p:
                continue  # Skip fixtures without probabilities

            # Get AI pick
            label, prob = _best_ev_pick(p, bf)

            # Alt markets - always show all available
            alt = []
            if p.p_over_15 is not None: alt.append(f"O1.5 {round(p.p_over_15*100)}%")
            if p.p_over_25 is not None: alt.append(f"O2.5 {round(p.p_over_25*100)}%")
            if p.p_over_35 is not None: alt.append(f"O3.5 {round(p.p_over_35*100)}%")
            if p.p_btts_yes is not None: alt.append(f"BTTS {round(p.p_btts_yes*100)}%")

            # Resolve kickoff time with cache fallback
            home_team = getattr(p, "home_team", "")
            away_team = getattr(p, "away_team", "")
            ko = _kickoff_for(bf, home_team, away_team)

            lines.append(f"   {ko}   {match}")
            if alt:
                lines.append(f"       {'  ·  '.join(alt)}")
            lines.append(f"       AI pick = {label} {round(prob*100)}%")

    lines.append("")
    lines.append("==================================")
    return '\n'.join(lines)


def _result_pick(bf: BoardFixture) -> tuple[str, float, bool]:
    """The model's predicted RESULT for this fixture (Architect 2026-08-05:
    'the prediction without the markets'). Returns (name, probability,
    is_away) where name is the predicted winner in words — the home club, the
    away club, or 'Draw'. is_away flags a predicted away win (ID405 scope
    overridden 2026-08-11, Architect directive): away may now be RECOMMENDED,
    not just shown — the honest historical note (away measured negative) stays
    with it, but it no longer carries an exclusion."""
    p = bf.probs
    prob, side = max(
        (p.p_home, "home"), (p.p_draw, "draw"), (p.p_away, "away"),
        key=lambda t: t[0])
    if side == "home":
        return p.home_team, prob, False
    if side == "away":
        return p.away_team, prob, True
    return "Draw", prob, False



def render_scan_tables(board: list[BoardFixture]) -> tuple[str, bool]:
    """LEAN per-league fixture cards (Architect 2026-08-11: "reduce the amount
    of information"): one card per fixture with the AI pick only — no model
    agreement count, no per-engine chips, no scoreline. Shows ALL fixtures
    across ALL leagues (not just deploy eligible). Accumulator candidates
    (on_deploy_shortlist) are marked with ★ at the top of each league section.
    An unrated fixture keeps its card as NO DATA — PENDING rather than being
    dropped (HR35). Full model detail lives on the saved board / /board.

    Returns (text, any_away_pick) — the bool tells render_telegram_board
    whether the 'away may be recommended' footnote is needed."""
    by_league: dict[str, list[BoardFixture]] = {}
    for bf in board:
        by_league.setdefault(_league_of(bf), []).append(bf)

    out: list[str] = []
    any_away = False
    for league, fixtures in by_league.items():
        league_blocks: list[str] = [league.upper()]

        # Separate accumulator candidates (on the deploy shortlist) from others
        acc_candidates = [bf for bf in fixtures if bf.on_deploy_shortlist]
        other_fixtures = [bf for bf in fixtures if not bf.on_deploy_shortlist]

        # Show accumulator candidates first, marked with ★
        if acc_candidates:
            league_blocks.append("  ⭐ ACCUMULATOR CANDIDATES (deploy-eligible):")
            for bf in acc_candidates:
                if bf.probs is None:
                    league_blocks.append(f"  · {_short_fixture(bf)}\n    NO DATA — PENDING")
                    continue
                name, prob, is_away = _result_pick(bf)
                any_away = any_away or is_away
                league_blocks.append(
                    f"  ★ {_short_fixture(bf)}\n"
                    f"    AI pick: {name} ({round(prob*100)}%)")

        # Then show all other fixtures
        for bf in other_fixtures:
            if bf.probs is None:
                league_blocks.append(f"· {_short_fixture(bf)}\n  NO DATA — PENDING")
                continue
            name, prob, is_away = _result_pick(bf)
            any_away = any_away or is_away
            league_blocks.append(
                f"· {_short_fixture(bf)}\n"
                f"  AI pick: {name} ({round(prob*100)}%)")
        out.append(f"{FENCE}\n" + "\n".join(league_blocks) + f"\n{FENCE}")
    return "\n".join(out), any_away


def render_pick_detail(shortlist: list[BoardFixture]) -> str:
    """MES, Elo second opinion and DIVERGENCE for the recommended picks only.

    These are the safety warnings — an implausible EV, or the two engines
    disagreeing. Dropping them to keep the message tidy would remove exactly
    the lines that stop a miscalibrated number being read as an edge."""
    if not shortlist:
        return ""
    out = ["DETAIL — recommended picks only"]
    for i, bf in enumerate(shortlist, 1):
        L = [f"{i}. {_short_fixture(bf)}"]
        if bf.best_price is not None and bf.best_mes_ev is not None:
            verdict = "POSITIVE" if bf.best_mes_ev > 0 else "NEGATIVE"
            L.append(f"   {bf.best_market} at {bf.best_price:.2f} "
                     f"({bf.best_bookmaker}) — HR30 MES {bf.best_mes_ev:+.2%} "
                     f"expected value, {verdict}")
        else:
            L.append("   HR30 MES: NO DATA — PENDING (no live price)")
        if bf.elo_probs and bf.probs:
            eh, ed, ea = bf.elo_probs
            L.append(f"   Elo second opinion: {bf.probs.home_team} "
                     f"{round(eh*100)}% / Draw {round(ed*100)}% / "
                     f"{bf.probs.away_team} {round(ea*100)}%")
        div = _divergence(bf)
        if div:
            L.append(f"   ⚠ {div}")
        if bf.engine_divergence:
            L.append(f"   ⚠ {bf.engine_divergence}")
        out.append("\n".join(L))
    return "\n\n".join(out)


def _render_yesterday_graded(yesterday_graded: Optional[list]) -> str:
    """ScoreGPT's 'Yesterday — graded' block (ID414): each settled fixture with
    its result and per-engine hit/miss. Built from the brain's graded_yesterday
    query; empty when there is nothing settled — shown honestly, never filled."""
    if not yesterday_graded:
        return "YESTERDAY — GRADED\nNo settled predictions to grade yet."
    lines = ["YESTERDAY — GRADED"]
    for g in yesterday_graded:
        fix = g.get("fixture") or "?"
        outcome = g.get("outcome") or "?"
        marks = []
        for engine, markets in (g.get("engines") or {}).items():
            # A hit is recorded per market; the 1X2_HOME row is the result pick
            row = markets.get("1X2_HOME") or markets.get("1X2_DRAW") \
                or markets.get("1X2_AWAY")
            if row and row.get("hit") is not None:
                marks.append(f"{engine} {'✓' if row['hit'] else '✗'}")
        marks_txt = "  ".join(marks) if marks else "no engine pick recorded"
        lines.append(f"· {fix} — {outcome}\n  {marks_txt}")
    return "\n".join(lines)


def _render_rolling_7d(rolling: Optional[dict]) -> str:
    """ScoreGPT's rolling-stats bar (ID414): per-engine hit rates over the last
    7 days plus CLV capture. Numbers come from the brain; nothing fabricated."""
    if not rolling:
        return "7-DAY ROLLING\nNo run history yet."
    engines = rolling.get("engines") or {}
    rates = []
    for eng in ("dc", "cross", "elo", "xg", "bookmaker"):
        st = engines.get(eng)
        if st and st.get("hit_rate") is not None:
            rates.append(f"{eng} {round(st['hit_rate']*100)}%")
    rates_txt = " · ".join(rates) if rates else "no settled predictions in 7d"
    legs = rolling.get("legs_logged", 0)
    with_clv = rolling.get("legs_with_clv", 0)
    avg = rolling.get("avg_clv_pct")
    clv_txt = f"avg CLV {avg:+.2f}%" if avg is not None else "CLV: ZERO"
    gate = (rolling.get("gate") or {})
    gate_txt = (f" · gate {gate.get('legs_with_clv', 0)}/"
                f"{gate.get('gate_requirement', 30)} legs") if gate else ""
    return (f"7-DAY ROLLING\n{rates_txt}\n"
            f"{legs} legs logged · {with_clv} with CLV ({clv_txt}){gate_txt}")


def render_live_matches_section(board: list[BoardFixture]) -> str:
    """Render the LIVE MATCHES section showing all FlashScore fixtures for live tracking.

    This section shows ALL fixtures that have FlashScore data (verified or unverified)
    so users can see which matches are available for live updates when production
    is running late. Fixtures without SportyBet odds appear as 'kept UNVERIFIED'.
    """
    # Find fixtures that have FlashScore provenance
    live_matches = []
    for bf in board:
        # Check if this fixture has FlashScore as a source
        if bf.verification:
            for vr in bf.verification:
                if vr.source == "FlashScore":
                    live_matches.append(bf)
                    break
        # Also check verification_raw if available
        if not live_matches or live_matches[-1] != bf:
            if hasattr(bf, 'verification_raw') and bf.verification_raw:
                for vr in bf.verification_raw:
                    if vr.source == "FlashScore":
                        live_matches.append(bf)
                        break

    if not live_matches:
        return "LIVE MATCHES (FlashScore)\nNo FlashScore fixtures available for live tracking."

    lines = ["LIVE MATCHES (FlashScore)"]
    lines.append("(Fixtures with FlashScore data — kept UNVERIFIED without SportyBet corroboration)")
    lines.append("")

    # Group by league
    from collections import defaultdict
    by_league: dict[str, list[BoardFixture]] = defaultdict(list)
    for bf in live_matches:
        league = _league_of(bf)
        by_league[league].append(bf)

    for league in sorted(by_league.keys()):
        fixtures = by_league[league]
        lines.append(f"  {league}")
        for bf in fixtures:
            # Get kickoff time
            home_team = bf.probs.home_team if bf.probs else ""
            away_team = bf.probs.away_team if bf.probs else ""
            ko = _kickoff_for(bf, home_team, away_team)

            # Determine verification status
            status = "kept UNVERIFIED"
            for vr in (bf.verification or []):
                if vr.source == "FlashScore" and vr.tier == Tier.T2:
                    status = "kept UNVERIFIED"
                    break

            lines.append(f"    {ko}  {_short_fixture(bf)}  [{status}]")
        lines.append("")

    return "\n".join(lines)


def render_telegram_board(mode: str, phase: str, leagues_scanned: list[str],
                           calibration_count: int, mean_clv: Optional[float],
                           data_flags: list[str], board: list[BoardFixture],
                           yesterday_graded: Optional[list] = None,
                           rolling_7d: Optional[dict] = None,
                           produced_bet: Optional[dict] = None,
                           production: Optional[object] = None,
                           codes: Optional[dict] = None,
                           compact: bool = False,
                           target_date: str = None) -> str:
    """The Telegram push. Two modes:

    compact=True  →  render_compact_heartbeat: minimal kickoff+pick+altmarkets
                     (Architect-approved heartbeat format, 2026-08-25).
    compact=False →  full ScoreGPT board (ID414): header, flag count, full scan
                     table, production block, yesterday graded, rolling bar.

    All other parameters are passed through for the full-format path but
    ignored when compact=True (only board + target_date matter there)."""
    if compact:
        return render_compact_heartbeat(board, target_date=target_date)

    clv = f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None else "CLV logged: ZERO"
    scan_txt, any_away = render_scan_tables(board)
    leagues_with_fixtures = len({_league_of(bf) for bf in board})
    parts = [
        f"OLP XDV — DAILY BOARD  [HEARTBEAT {date.today().isoformat()}]\n{date.today().isoformat()}  |  {phase}\n"
        f"Leagues: {len(leagues_scanned)} · {leagues_with_fixtures} with "
        f"fixtures\n"
        f"Calibration: {calibration_count} legs logged, {clv}",
    ]
    # data_flags intentionally omitted from Telegram push per Architect request
    # (2026-08-28): flags live on disk/web, not in the phone message
    parts.append(render_produced_bet_block(produced_bet))
    parts.append(scan_txt)
    if production is None:
        production = build_production_bets(board)
    parts.append(render_production_block(production, codes=codes))
    if any_away:
        parts.append("Away picks may now be recommended (ID405 overridden "
                     "2026-08-11, Architect directive); away was historically "
                     "measured negative — the brain learns from live legs")
    parts.append(_render_yesterday_graded(yesterday_graded))
    parts.append(_render_rolling_7d(rolling_7d))
    # LIVE MATCHES SECTION - Show all FlashScore fixtures for live tracking
    parts.append(render_live_matches_section(board))
    # Honest edge / capital authority removed from Telegram per Architect 2026-08-31
    # The on-disk board retains the full sign-off for audit.
    return "\n\n".join(parts)
