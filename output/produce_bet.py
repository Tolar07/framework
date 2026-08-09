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
from typing import Optional

from engine.dixon_coles import FixtureProbabilities
from engine.consensus import Consensus
from engine.softness import DEPLOY_POOL_CAP, SOFTNESS_PAUSED
from engine.acca import render_acca_block
from engine import markets as mkt
from verification.id403 import VerificationResult, Tier, stamp
from bets.produced_bet import render_produced_bet as render_produced_bet_block


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
    softness_tier: str = "?"   # A/B/C/D
    on_deploy_shortlist: bool = False
    mes_trigger_price: Optional[float] = None
    rejection_reason: Optional[str] = None
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


def render_part0(mode: str, phase: str, leagues_scanned: list[str],
                  calibration_count: int, mean_clv: Optional[float],
                  data_flags: list[str]) -> str:
    lines = [
        f"PART 0 — HEADER",
        f"Date: {date.today().isoformat()} | Mode: {mode} | Phase: {phase}",
        f"Leagues scanned: {', '.join(leagues_scanned)}",
        f"Calibration: {calibration_count} legs logged, "
        f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None
        else f"Calibration: {calibration_count} legs logged, CLV logged: ZERO",
    ]
    if data_flags:
        lines.append("DATA FLAGS (surfaced first, per HR53/ID403):")
        lines.extend(f"  ⚠ {flag}" for flag in data_flags)
    lines.append("HONEST EDGE LINE: this is an excellent informed process but "
                  "NOT a demonstrated profitable edge.")
    return "\n".join(lines)


def _tier_words(tier: str) -> str:
    """HR53: no bare glyphs. A lone 'B' means nothing on a phone at 7am."""
    if SOFTNESS_PAUSED:
        return "Softness PAUSED — all whitelisted leagues deploy-eligible"
    return {
        "A": "Softness tier A — deploy-eligible",
        "B": "Softness tier B — deploy-eligible",
        "C": "Softness tier C — scan-only, never a capital pick",
        "D": "Softness tier D — scan-only, never a capital pick",
    }.get(tier, "Softness tier unrated — not on the ID401 whitelist")


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
    L.append(f"   {_tier_words(bf.softness_tier)}")
    L.append(f"   Data confidence: {_verification_words(bf.verification)}")

    if bf.probs is None:
        L.append("   Model: NO DATA — PENDING")
        if bf.rejection_reason:
            L.append(f"   Reason: {bf.rejection_reason}")
        return "\n".join(L)

    p = bf.probs
    L.append(f"   Match result (model probabilities):")
    L.append(f"      {p.home_team} to win .......... {round(p.p_home*100)}%")
    L.append(f"      Draw ......................... {round(p.p_draw*100)}%")
    L.append(f"      {p.away_team} to win .......... {round(p.p_away*100)}%")
    L.append(f"   Goals: {_side_words(p, 1.5, p.p_over_15)}"
             f" | {_side_words(p, 2.5, p.p_over_25)}")
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
        L.append(f"      Price captured from the-odds-api.com. Confirm on "
                 f"SportyBet/Bet365 before acting — Architect deploys, not this system.")
    elif bf.sb_home_odds is not None or bf.sb_draw_odds is not None or bf.sb_away_odds is not None:
        # SportyBet odds are available (Phase 2 CLV / Phase 3 live)
        from engine.mes import mes_numeric
        L.append(f"   SportyBet Nigeria odds (real-money bookmaker, margin included):")
        if bf.sb_home_odds is not None:
            ev = mes_numeric(p.p_home, bf.sb_home_odds)
            L.append(f"      {p.home_team} to win ....... {bf.sb_home_odds:.2f}  ->  EV {ev:+.2%}" if ev is not None
                     else f"      {p.home_team} to win ....... {bf.sb_home_odds:.2f}  ->  EV NO DATA")
        if bf.sb_draw_odds is not None:
            ev = mes_numeric(p.p_draw, bf.sb_draw_odds)
            L.append(f"      Draw ..................... {bf.sb_draw_odds:.2f}  ->  EV {ev:+.2%}" if ev is not None
                     else f"      Draw ..................... {bf.sb_draw_odds:.2f}  ->  EV NO DATA")
        if bf.sb_away_odds is not None:
            ev = mes_numeric(p.p_away, bf.sb_away_odds)
            L.append(f"      {p.away_team} to win ....... {bf.sb_away_odds:.2f}  ->  EV {ev:+.2%}" if ev is not None
                     else f"      {p.away_team} to win ....... {bf.sb_away_odds:.2f}  ->  EV NO DATA")
        if bf.sb_mes_ev is not None:
            L.append(f"      Best SportyBet MES ......... {bf.sb_mes_ev:+.2%} per unit staked")
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


def render_part1_the_call(shortlist: list[BoardFixture]) -> str:
    """DEPLOY shortlist — TODAY'S fixtures only (standing rule 2026-08-09),
    softness A/B, <=6 pool. Frozen columns:
    Fixture | Pick | Model% | Deploy at (MES trigger) | Softness tier"""
    today = date.today().isoformat()
    shortlist = [bf for bf in shortlist if bf.kickoff_date == today]
    if not shortlist:
        return ("PART 1 — THE CALL — today's fixtures only\n"
                "NO DEPLOY-ELIGIBLE CALL this session — no deployable fixture "
                "kicks off today (a valid, honest result).")
    rows = ["PART 1 — THE CALL — today's fixtures only",
            "Fixture | Pick | Model% | Deploy at | Tier"]
    for bf in shortlist:
        if bf.probs is None:
            rows.append(f"{bf.fixture} | NO DATA — PENDING | — | — | {bf.softness_tier}")
            continue
        # Plain-language pick line (HR53 — no bare glyphs)
        pick_desc, prob = _best_market_desc(bf.probs)
        trigger = f"{bf.mes_trigger_price:.2f}+" if bf.mes_trigger_price else "NO DATA — PENDING"
        rows.append(f"{bf.fixture} | {pick_desc} | {round(prob*100)}% | {trigger} | {bf.softness_tier}")
    return "\n".join(rows)


def _best_market_desc(p: FixtureProbabilities) -> tuple[str, float]:
    """Placeholder selection logic for which market to headline — a real deploy
    decision needs the full ID402/softness/ID389 gating; this just picks the
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


def render_part3_rejected(board: list[BoardFixture]) -> str:
    rejected = [bf for bf in board if bf.rejection_reason]
    if not rejected:
        return "PART 3 — REJECTED / WATCHLIST\nNone."
    rows = ["PART 3 — REJECTED / WATCHLIST"]
    for bf in rejected:
        rows.append(f"{bf.fixture}: {bf.rejection_reason}")
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


def render_produce_bet(mode: str, phase: str, leagues_scanned: list[str],
                        calibration_count: int, mean_clv: Optional[float],
                        data_flags: list[str], board: list[BoardFixture],
                        stacked: bool = True,
                        produced_bet: Optional[dict] = None,
                        accas: Optional[list] = None) -> str:
    """`stacked=True` renders the HR53-preferred per-fixture blocks for PART 1
    (the decision-first section you actually act on) while PART 2 keeps the
    frozen wide table as the reference board. Set stacked=False for the
    original all-tables v303.11 layout. Optional produced_bet is the day's
    produced-bet record (ID415) for the saved board block.

    THE CALL is TODAY'S fixtures only (standing rule 2026-08-09) — the wider
    scan stays the 3-day reference, the call is today's slate. `accas` (the
    day's 4-leg accumulator set, optional) renders the acca block at the end
    of production; computed from `board` when not provided."""
    today = date.today().isoformat()
    shortlist = [bf for bf in board
                 if bf.on_deploy_shortlist and bf.kickoff_date == today]
    if accas is None:
        from engine.acca import build_accas
        accas = build_accas(board)

    if stacked:
        if shortlist:
            call = ["PART 1 — THE CALL — today's fixtures only"]
            if SOFTNESS_PAUSED:
                call.append(f"{len(shortlist)} deploy-eligible fixture(s) kicking off today, softness PAUSED (all whitelisted leagues, no cap).")
            else:
                call.append(f"{len(shortlist)} deploy-eligible fixture(s) kicking off today, softness A/B only, capped at {DEPLOY_POOL_CAP} (ID402).")
            call.append("MARKED PAPER — Phase 2, zero capital. Nothing here is a live bet.")
            call.append("")
            call += [render_fixture_block(bf, i) + "\n"
                     for i, bf in enumerate(shortlist, 1)]
            part1 = "\n".join(call).rstrip()
        else:
            part1 = ("PART 1 — THE CALL — today's fixtures only\n"
                     "NO DEPLOY-ELIGIBLE CALL this session — no deployable "
                     "fixture kicks off today. That is a valid, honest result — "
                     "the framework's value is disciplined filtering, and "
                     "near-zero approvals is correct behaviour, not failure.")
    else:
        part1 = render_part1_the_call(shortlist)

    parts = [
        render_part0(mode, phase, leagues_scanned, calibration_count, mean_clv, data_flags),
        "",
        part1,
        "",
        render_part2_the_scan(board),
        "",
        render_part3_rejected(board),
        "",
        render_part4_data_integrity(board),
    ]
    if produced_bet is not None:
        parts += ["", render_produced_bet_block(produced_bet)]
    # The 4-leg acca set, named at the end of production (standing rule
    # 2026-08-09). Before the sign-off so the sign-off stays the final word.
    parts += ["", render_acca_block(accas, today)]
    parts += ["", render_part5_signoff()]
    return "\n".join(parts)


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


RECOMMEND_MAX_LEGS = 4  # Architect 2026-08-05: the day's pick is a 2-4 leg parlay


def _result_pick(bf: BoardFixture) -> tuple[str, float, bool]:
    """The model's predicted RESULT for this fixture (Architect 2026-08-05:
    'the prediction without the markets'). Returns (name, probability,
    is_away) where name is the predicted winner in words — the home club, the
    away club, or 'Draw'. is_away flags a predicted away win: the scan table
    may show it honestly as the prediction, but the recommendation never
    recommends it (ID405 — away is a proven-negative market)."""
    p = bf.probs
    prob, side = max(
        (p.p_home, "home"), (p.p_draw, "draw"), (p.p_away, "away"),
        key=lambda t: t[0])
    if side == "home":
        return p.home_team, prob, False
    if side == "away":
        return p.away_team, prob, True
    return "Draw", prob, False


def render_daily_recommendation(board: list[BoardFixture]) -> str:
    """The day's picks as a 2-4 leg parlay, drawn ONLY from fixtures kicking
    off TODAY (standing rule 2026-08-09: the product bet is today's slate and
    nothing else) — not the 3-day window. A fixture with no kickoff date is
    never assumed to be today (HR35), so it cannot be a pick.

    Legs are today's highest-probability predicted results, capped at
    RECOMMEND_MAX_LEGS. A predicted AWAY win is never recommended (ID405 —
    proven-negative market). Two or more legs become a parlay; its combined
    chance is the product of the legs, stated honestly as the chance ALL of
    them win — a parlay's legs are not independent, so the combined number is
    information, not encouragement to stack everything."""
    today = date.today().isoformat()
    legs: list[tuple] = []
    for bf in board:
        if bf.kickoff_date != today:
            continue  # standing rule: today's fixtures only
        if bf.probs is None:
            continue
        name, prob, is_away = _result_pick(bf)
        if is_away:
            continue
        legs.append((bf, name, prob))
    legs.sort(key=lambda t: t[2], reverse=True)   # strongest picks first
    legs = legs[:RECOMMEND_MAX_LEGS]

    if not legs:
        return ("⭐ TODAY'S PICKS\n"
                "NO DATA — no eligible pick today.")

    n = len(legs)
    head = (f"⭐ TODAY'S PICKS — {n}-leg parlay" if n >= 2 else
            "⭐ TODAY'S PICKS — 1 pick (not enough for a 2-leg parlay)")
    lines = [head]
    for i, (bf, name, prob) in enumerate(legs, 1):
        lines.append(f"{i}. {_short_fixture(bf)} → {name} {round(prob*100)}%")
    if n >= 2:
        combined = 1.0
        for _, _, prob in legs:
            combined *= prob
        lines.append(f"Combined: ~{round(combined*100)}% if every leg wins — "
                     f"parlay risk, legs are not independent")
    return "\n".join(lines)


def _engine_chip(bf: BoardFixture) -> list[str]:
    """One chip per engine that priced this fixture: the predicted side + the
    agreed/missing marker. ScoreGPT shows each model's pick under the match;
    here the chips are ✓ for agreement with the consensus pick, ✗ for dissent,
    ? when that engine had no data. Honest: an engine that could not price the
    fixture shows '—' not a fabricated pick (HR35)."""
    out: list[str] = []
    side = None
    if bf.probs is not None:
        side = _result_pick(bf)[0]
    # DC / cross is the goals engine that owns bf.probs
    if bf.probs is not None:
        agreed = side is not None and side == _result_pick(bf)[0]
        out.append(f"DC {round(max(bf.probs.p_home, bf.probs.p_draw, bf.probs.p_away)*100)}%")
    else:
        out.append("DC —")
    if bf.elo_probs:
        eh, ed, ea = bf.elo_probs
        elo_side = max((eh, "home"), (ed, "draw"), (ea, "away"), key=lambda t: t[0])[1]
        elo_name = {"home": bf.probs.home_team if bf.probs else "home",
                    "draw": "Draw", "away": bf.probs.away_team if bf.probs else "away"}[elo_side]
        agreed = side is not None and (elo_side == "home" or elo_side == "away") \
            and elo_name == side
        out.append(f"Elo {round(max(eh, ed, ea)*100)}%")
    else:
        out.append("Elo —")
    if bf.xg_probs:
        xh, xd, xa = bf.xg_probs
        xg_side = max((xh, "home"), (xd, "draw"), (xa, "away"), key=lambda t: t[0])[1]
        xg_name = {"home": bf.probs.home_team if bf.probs else "home",
                   "draw": "Draw", "away": bf.probs.away_team if bf.probs else "away"}[xg_side]
        out.append(f"xG {round(max(xh, xd, xa)*100)}%")
    else:
        out.append("xG —")
    if bf.market_probs:
        mh, md, ma = bf.market_probs
        mk_side = max((mh, "home"), (md, "draw"), (ma, "away"), key=lambda t: t[0])[1]
        mk_name = {"home": bf.probs.home_team if bf.probs else "home",
                   "draw": "Draw", "away": bf.probs.away_team if bf.probs else "away"}[mk_side]
        out.append(f"Book {round(max(mh, md, ma)*100)}%")
    else:
        out.append("Book —")
    return out


def render_scan_tables(board: list[BoardFixture]) -> tuple[str, bool]:
    """ScoreGPT-style per-league match cards (ID414): one card per fixture with
    the AI pick, the predicted scoreline (modal), the consensus count, and the
    per-engine chips. Shows ALL fixtures across ALL leagues (not just deploy
    eligible). Accumulator candidates (Tier A/B, on_deploy_shortlist) are marked
    with ★ at the top of each league section. This REPLACES the old two-column
    `Fixture | Prediction` table — the Architect's total-restructure order. An
    unrated fixture keeps its card as NO DATA — PENDING rather than being
    dropped (HR35).

    Returns (text, any_away_pick) — the bool tells render_telegram_board
    whether the 'away is never recommended' footnote is needed."""
    by_league: dict[str, list[BoardFixture]] = {}
    for bf in board:
        by_league.setdefault(_league_of(bf), []).append(bf)

    out: list[str] = []
    any_away = False
    for league, fixtures in by_league.items():
        league_blocks: list[str] = [league.upper()]

        # Separate accumulator candidates (Tier A/B + on_deploy_shortlist) from others
        if SOFTNESS_PAUSED:
            acc_candidates = [bf for bf in fixtures if bf.on_deploy_shortlist]
            other_fixtures = [bf for bf in fixtures if not bf.on_deploy_shortlist]
        else:
            acc_candidates = [bf for bf in fixtures
                             if bf.softness_tier in ("A", "B") and bf.on_deploy_shortlist]
            other_fixtures = [bf for bf in fixtures
                             if not (bf.softness_tier in ("A", "B") and bf.on_deploy_shortlist)]

        # Show accumulator candidates first, marked with ★
        if acc_candidates:
            if SOFTNESS_PAUSED:
                league_blocks.append("  ⭐ ACCUMULATOR CANDIDATES (softness PAUSED, all whitelisted deploy-eligible):")
            else:
                league_blocks.append("  ⭐ ACCUMULATOR CANDIDATES (Tier A/B, deploy-eligible):")
            for bf in acc_candidates:
                if bf.probs is None:
                    league_blocks.append(f"  · {_short_fixture(bf)}\n    NO DATA — PENDING")
                    continue
                name, prob, is_away = _result_pick(bf)
                any_away = any_away or is_away
                sl = getattr(bf.probs, "modal_scoreline", None)
                score = f"{sl[0]}–{sl[1]}" if sl else "—"
                pick_line = f"AI pick: {name} — predicted {score}"
                if bf.consensus and bf.consensus.n_engines:
                    agree = f"{bf.consensus.agreeing} of {bf.consensus.n_engines} models agree"
                else:
                    agree = "consensus unavailable"
                chips = " · ".join(_engine_chip(bf))
                tier_label = f"[Tier {bf.softness_tier}]"
                league_blocks.append(
                    f"  ★ {_short_fixture(bf)} {tier_label}\n"
                    f"    {pick_line} ({round(prob*100)}%)\n"
                    f"    {agree}\n"
                    f"    {chips}")

        # Then show all other fixtures
        for bf in other_fixtures:
            if bf.probs is None:
                league_blocks.append(f"· {_short_fixture(bf)}\n  NO DATA — PENDING")
                continue
            name, prob, is_away = _result_pick(bf)
            any_away = any_away or is_away
            sl = getattr(bf.probs, "modal_scoreline", None)
            score = f"{sl[0]}–{sl[1]}" if sl else "—"
            pick_line = f"AI pick: {name} — predicted {score}"
            if bf.consensus and bf.consensus.n_engines:
                agree = f"{bf.consensus.agreeing} of {bf.consensus.n_engines} models agree"
            else:
                agree = "consensus unavailable"
            chips = " · ".join(_engine_chip(bf))
            tier_label = f"[Tier {bf.softness_tier}]" if bf.softness_tier != "?" else ""
            if tier_label:
                tier_label += " "
            league_blocks.append(
                f"· {_short_fixture(bf)} {tier_label}\n"
                f"  {pick_line} ({round(prob*100)}%)\n"
                f"  {agree}\n"
                f"  {chips}")
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


def render_telegram_board(mode: str, phase: str, leagues_scanned: list[str],
                           calibration_count: int, mean_clv: Optional[float],
                           data_flags: list[str], board: list[BoardFixture],
                           yesterday_graded: Optional[list] = None,
                           rolling_7d: Optional[dict] = None,
                           produced_bet: Optional[dict] = None,
                           accas: Optional[list] = None) -> str:
    """The Telegram push — ScoreGPT format (ID414). Header, one-line flag count,
    the day's picks (parlay), the day's 4-leg acca set, league-grouped match
    cards with AI pick + predicted scoreline + N-of-N consensus + per-engine
    chips, then 'Yesterday — graded' and the 7-day rolling bar. Detail lives in
    the saved file board and /board, /why; the phone gets the picks. Optional
    yesterday_graded / rolling_7d come from the brain (ID414); produced_bet is
    the day's produced-bet record (ID415); accas is the day's 4-leg acca set
    (standing rule 2026-08-09), computed from the board when not provided.
    None renders the honest empty block."""
    clv = f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None else "CLV logged: ZERO"
    scan_txt, any_away = render_scan_tables(board)
    leagues_with_fixtures = len({_league_of(bf) for bf in board})
    parts = [
        f"OLP XDV — DAILY BOARD\n{date.today().isoformat()}  |  {phase}\n"
        f"Leagues: {len(leagues_scanned)} · {leagues_with_fixtures} with "
        f"fixtures\n"
        f"Calibration: {calibration_count} legs logged, {clv}",
    ]
    if data_flags:
        parts.append(f"⚠ {len(data_flags)} data flag(s) — see /board or the "
                     f"saved board for full detail")
    parts.append(render_daily_recommendation(board))
    parts.append(render_produced_bet_block(produced_bet))
    if accas is None:
        from engine.acca import build_accas
        accas = build_accas(board)
    parts.append(render_acca_block(accas))
    parts.append(scan_txt)
    if any_away:
        # A predicted away win may appear as a card pick, but is never a Pick —
        # the framework measured away wins as a proven-negative market (ID405).
        parts.append("Away wins are never recommended (ID405 — proven negative "
                     "market); a card may still show one as the prediction")
    parts.append(_render_yesterday_graded(yesterday_graded))
    parts.append(_render_rolling_7d(rolling_7d))
    parts.append("HONEST EDGE LINE: an excellent informed process but NOT a "
                 "demonstrated profitable edge.\nCapital authority: THE "
                 "ARCHITECT. Nothing here is live until you deploy it.")
    return "\n\n".join(parts)
