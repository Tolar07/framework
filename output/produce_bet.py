"""
PRODUCE BET / VERIFY RESULTS — FROZEN CONTRACT v303.11, HR53 full-detail mandate.

Table layout is treated as binding (memory is editable, so "frozen" means
treated-as-binding here too — any change to these formats should be a
deliberate, visible decision, not a silent drift).

HR35 hard guardrail carried through: completeness never overrides honesty.
A missing datum renders as "NO DATA — PENDING", never filled to look complete.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Optional

from engine.dixon_coles import FixtureProbabilities
from engine.slate import (DEPLOY_POOL_CAP, DEPLOY_ODDS_MIN, DEPLOY_ODDS_MAX,
                          DEPLOY_ODDS_SAFE, DEPLOY_MIN_MODEL_PROB)
from engine import markets as mkt
from engine import competitions as comp
from verification.id403 import VerificationResult, Tier, stamp


def _pct(p: Optional[float]) -> str:
    return f"{round(p * 100):d}%" if p is not None else "NO DATA — PENDING"


def _lean(p_over: Optional[float], line_label: str) -> str:
    """BUG5 fix carried over: always show whichever side is >=50%, never force 'O'."""
    if p_over is None:
        return "NO DATA — PENDING"
    if p_over >= 0.5:
        return f"O{round(p_over*100)}"
    return f"U{round((1-p_over)*100)}"


_TIER_MARK = {"BANKER": "★ ", "SAFE": "✓ ", "VALUE": "$ ", "BOOK": "ᴮ ", "SPLIT": "⚠ ", "MARKET": ""}


@dataclass
class BoardFixture:
    fixture: str  # "Home v Away"
    probs: Optional[FixtureProbabilities]
    verification: VerificationResult
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
    # The mkt.* KEY of the in-band deploy pick (the market actually chosen for
    # TABLE 2 / the booking code), set by run_daily's band-aware selection. Kept
    # separate from best_market (the display string) so the booked outcome and
    # the headlined single are guaranteed the same market.
    best_market_key: Optional[str] = None
    # Where the probabilities came from: "model" (Dixon-Coles) or "market"
    # (de-vigged SportyBet prices, for a fixture the model has no history on —
    # engine.market_implied). A market-implied fixture carries no model edge.
    prob_source: str = "model"
    # Second-best in-band market (the board's alternative pick) and its price.
    alt_market: Optional[str] = None
    alt_price: Optional[float] = None
    # Pick tier (engine.slate: BANKER / SAFE / SPLIT / MARKET) and the two
    # probabilities behind the consensus shown as the pick's win %.
    tier: Optional[str] = None
    pick_model_prob: Optional[float] = None
    pick_market_prob: Optional[float] = None
    # CERTAINTY — how sure we are that the pick's % is RIGHT (not how likely
    # the pick is): HIGH = model and bookmaker within 3pp; MEDIUM = within
    # 7pp; LOW = they disagree, or only one source (market-implied/BOOK).
    certainty: Optional[str] = None
    # TEAM NEWS (engine.team_news): OK / CAUTION / RISK / NO NEWS + reason; the
    # FotMob match id, kickoff time and predicted XI values for the
    # pre-kickoff confirmed-lineup check.
    news_level: Optional[str] = None
    # SWITCHED (order 32): the shaky pick this one replaced, and why.
    switched_from: Optional[str] = None
    news_note: Optional[str] = None
    fotmob_id: Optional[int] = None
    kickoff_utc: Optional[str] = None
    predicted_xi: Optional[dict] = None
    # Suggested stake, % of bankroll (engine.staking), and why.
    stake_pct: Optional[float] = None
    stake_why: Optional[str] = None
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
    # Standings + recent-form context (engine.form), derived from the same
    # results the model is fit on. A ranking/flagging signal only — it never
    # changes a probability, EV or CLV. form_support is the bounded [-1,1] tilt
    # of recent form toward the market side the model likes; a clearly negative
    # value is surfaced as a caution, never an auto-reject.
    form_summary: Optional[str] = None
    form_support: Optional[float] = None
    # Real SportyBet booking code for this fixture's headlined pick (a shareable
    # slip, NOT a placed bet). Populated by run_daily via pipeline.sportybet_booking
    # when the fixture resolves on the SportyBet feed; stays None (board shows
    # PENDING) when it can't be resolved — never fabricated (HR35).
    booking_code: Optional[str] = None
    # PRICE CHECK (pipeline/odds_verify.py): VERIFIED / CONFLICT / SINGLE-SOURCE
    # — does an independent book (bet365 via football-data, DraftKings via
    # ESPN) agree with this fixture's SportyBet prices once margins are
    # removed. None = not checked. A label only; it never changes a pick.
    price_check: Optional[str] = None
    price_note: Optional[str] = None
    booking_url: Optional[str] = None


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
    if bf.price_check:
        L.append(f"   Price check: {bf.price_check}"
                 + (f" — {bf.price_note}" if bf.price_note else ""))
    if bf.form_summary:
        tilt = ("" if bf.form_support is None
                else f"  (recent-form tilt {bf.form_support:+.2f})")
        L.append(f"   Standings/{bf.form_summary}{tilt}")

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
    if p.lambda_home is None:
        L.append("   Probabilities: MARKET-IMPLIED (SportyBet prices, margin removed) — "
                 "the model has no history on this fixture; no model edge is claimed")
    else:
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
        src = bf.best_bookmaker or "the odds feed"
        L.append(f"      Price captured from {src}. Confirm the live price before "
                 f"acting — the Architect deploys, not this system.")
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
    """DEPLOY shortlist — top model conviction, <=6 pool. Frozen columns:
    Fixture | Pick | Model% | Deploy at (MES trigger)"""
    if not shortlist:
        return "PART 1 — THE CALL\nNO DEPLOY-ELIGIBLE CALL this session."
    rows = ["PART 1 — THE CALL",
            "Fixture | Pick | Model% | Deploy at"]
    for bf in shortlist:
        if bf.probs is None:
            rows.append(f"{bf.fixture} | NO DATA — PENDING | — | —")
            continue
        # Plain-language pick line (HR53 — no bare glyphs)
        pick_desc, prob = _best_market_desc(bf.probs)
        trigger = f"{bf.mes_trigger_price:.2f}+" if bf.mes_trigger_price else "NO DATA — PENDING"
        rows.append(f"{bf.fixture} | {pick_desc} | {round(prob*100)}% | {trigger}")
    return "\n".join(rows)


def _best_market_key(p: FixtureProbabilities) -> tuple[Optional[str], float]:
    """The highest-confidence DEPLOYABLE market KEY (mkt.*) for this fixture,
    with its model probability. (None, 0.0) if nothing is deployable. Booking-
    code resolution keys on this so the code books exactly what the board
    headlines — presentation and identity can never drift (see engine.markets)."""
    candidates = [(k, mkt.model_prob(k, p)) for k in mkt.DEPLOYABLE]
    candidates = [(k, prob) for k, prob in candidates if prob is not None]
    if not candidates:
        return (None, 0.0)
    return max(candidates, key=lambda c: c[1])


def _best_market_desc(p: FixtureProbabilities) -> tuple[str, float]:
    """Plain-language name + probability of the market the board headlines.

    Only markets that could actually carry capital may be headlined (mkt.DEPLOYABLE
    excludes the ID405-blocked ones). Derived from _best_market_key so the words
    and the booked outcome are always the same market."""
    key, prob = _best_market_key(p)
    if key is None:
        return ("NO DATA — PENDING", 0.0)
    return (mkt.display(key, p.home_team, p.away_team), prob)


def _deploy_pick(bf: "BoardFixture") -> tuple[str, Optional[float]]:
    """The market a fixture actually DEPLOYS: the in-band pick run_daily chose
    (best_market/best_model_prob — priced inside the 1.20–2.00 band), when set.
    Falls back to the model's best deployable market for previews rendered
    without attached prices (e.g. tests). This is what TABLE 2 / TABLE 4 / the
    ACCA show, so the single, the booking code and the displayed pick agree."""
    if bf.best_market and bf.best_model_prob is not None:
        return bf.best_market, bf.best_model_prob
    if bf.probs is not None:
        return _best_market_desc(bf.probs)
    return ("NO DATA — PENDING", None)


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
    checked = [bf.price_check for bf in board if bf.price_check]
    if checked:
        rows.append("PRICE CHECK (SportyBet vs bet365/DraftKings, margin removed): "
                    + " · ".join(f"{t} {checked.count(t)}"
                                 for t in ("VERIFIED", "CONFLICT", "SINGLE-SOURCE")))
    return "\n".join(rows)


def _price_check_lines(picks: list[BoardFixture]) -> list[str]:
    """One summary line for the singles' price check, plus each pick whose
    SportyBet prices an independent book disagrees with (shown, never hidden;
    it does not change the pick)."""
    from pipeline.odds_verify import PRICE_CHECK_TOLERANCE_PP as tol
    checked = [bf for bf in picks if bf.price_check]
    if not checked:
        return []
    ok = sum(bf.price_check == "VERIFIED" for bf in checked)
    differ = [bf for bf in checked if bf.price_check == "CONFLICT"]
    alone = len(checked) - ok - len(differ)
    line = (f"Price check: {ok} of {len(checked)} picks' SportyBet prices agree with an "
            f"independent book (bet365 via football-data / DraftKings via ESPN, margin "
            f"removed, within {tol:g} pts)")
    if differ:
        line += f" · {len(differ)} differ (below)"
    if alone:
        line += f" · {alone} quoted by no second book"
    out = ["", line + "."]
    for bf in differ:
        out.append(f"   • ⚠ {comp.where(bf.fixture)} — {bf.price_note}")
    return out


def _sharp_lines(picks: list[BoardFixture]) -> list[str]:
    """One line: how many picks are priced above the Betfair Exchange's fair
    odds (pipeline/sharp.py). A label only; it never changes a pick."""
    checked = [bf for bf in picks if getattr(bf, "sharp_ev", None) is not None]
    if not checked:
        return []
    above = [bf for bf in checked if bf.sharp_ev > 0]
    avg = 100 * sum(bf.sharp_ev for bf in checked) / len(checked)
    out = [f"Sharp check: {len(above)} of {len(checked)} picks priced above the Betfair "
           f"Exchange's fair odds (margin removed; average {avg:+.1f}% vs fair). "
           f"Above fair = real value; below = the bookmaker's margin."]
    for bf in sorted(above, key=lambda b: -b.sharp_ev)[:5]:
        out.append(f"   • {comp.where(bf.fixture)} — {bf.best_market} @{bf.best_price:.2f}: "
                   f"{bf.sharp_ev * 100:+.1f}% vs fair")
    return out


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
                        stacked: bool = True) -> str:
    """`stacked=True` renders the HR53-preferred per-fixture blocks for PART 1
    (the decision-first section you actually act on) while PART 2 keeps the
    frozen wide table as the reference board. Set stacked=False for the
    original all-tables v303.11 layout."""
    shortlist = [bf for bf in board if bf.on_deploy_shortlist]

    if stacked:
        if shortlist:
            call = ["PART 1 — THE CALL",
                    f"{len(shortlist)} deploy-eligible fixture(s), top model "
                    f"conviction, capped at {DEPLOY_POOL_CAP} (ID402).",
                    "MARKED PAPER — Phase 2, zero capital. Nothing here is a live bet.",
                    ""]
            call += [render_fixture_block(bf, i) + "\n"
                     for i, bf in enumerate(shortlist, 1)]
            part1 = "\n".join(call).rstrip()
        else:
            part1 = ("PART 1 — THE CALL\nNO DEPLOY-ELIGIBLE CALL this session.\n"
                     "That is a valid, honest result — the framework's value is "
                     "disciplined filtering, and near-zero approvals is correct "
                     "behaviour, not failure.")
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
        "",
        render_part5_signoff(),
    ]
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
# TELEGRAM TABLE BOARD
# ---------------------------------------------------------------------------
# The stacked per-fixture blocks above satisfy HR53's detail mandate but make a
# 45-fixture board a wall of text on a phone — the recommendations end up
# buried, and the message splits into eight parts. This renders the same
# information as fixed-width tables inside Telegram code fences, which keep
# column alignment and scroll horizontally rather than wrapping.
#
# HR53 is preserved, not traded away:
#   - full club names, never truncated (leagues become section headers so the
#     "(League)" suffix leaves the fixture cell, which is what buys the width)
#   - unrated fixtures KEEP their row, marked NO DATA — PENDING, so the table
#     shows the real matchday rather than an edited subset
#   - MES, the Elo second opinion and any DIVERGENCE flag follow the
#     RECOMMENDED table as plain text. Those are the safety warnings; they must
#     reach the phone, but only for the <=6 picks that could be acted on.

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


def render_recommended_table(shortlist: list[BoardFixture]) -> str:
    if not shortlist:
        return ("RECOMMENDED — THE CALL\n"
                "NO DEPLOY-ELIGIBLE CALL this session.\n"
                "That is a valid, honest result: the framework's value is "
                "disciplined filtering, and near-zero approvals is correct.")
    rows = []
    for bf in shortlist:
        # Prefer the market chosen on live EV. With no price available, still
        # NAME the model's strongest deployable market and let the price be the
        # thing that reads NO DATA — a blank Pick column hides a view the model
        # genuinely holds, which is unhelpful without being any more honest.
        if bf.best_market and bf.best_model_prob is not None:
            pick, prob = bf.best_market, bf.best_model_prob
        elif bf.probs is not None:
            pick, prob = _best_market_desc(bf.probs)
        else:
            pick, prob = "NO DATA — PENDING", None
        model = f"{round(prob*100)}%" if prob else "—"
        trig = f"{bf.mes_trigger_price:.2f}+" if bf.mes_trigger_price else "NO DATA"
        rows.append([_short_fixture(bf), pick, model, trig])
    table = _col(rows, ["Fixture", "Pick", "Model%", "Deploy at"])
    return (f"RECOMMENDED — THE CALL  (top model conviction, capped at "
            f"{DEPLOY_POOL_CAP}, ID402)\nMARKED PAPER — Phase 2, zero capital.\n"
            f"{FENCE}\n{table}\n{FENCE}")


def render_scan_tables(board: list[BoardFixture]) -> str:
    """Every fixture, grouped by league. Unrated ones keep their row."""
    by_league: dict[str, list[BoardFixture]] = {}
    for bf in board:
        by_league.setdefault(_league_of(bf), []).append(bf)

    out = ["ALL FIXTURES SCANNED"]
    for league, fixtures in by_league.items():
        rows = []
        for bf in fixtures:
            if bf.probs is None:
                rows.append([_short_fixture(bf), "NO DATA — PENDING", "—", "—",
                             stamp(bf.verification)])
                continue
            p = bf.probs
            best = max((f"{p.home_team}·{round(p.p_home*100)}%", p.p_home),
                       (f"Draw·{round(p.p_draw*100)}%", p.p_draw),
                       (f"{p.away_team}·{round(p.p_away*100)}%", p.p_away),
                       key=lambda t: t[1])[0]
            rows.append([
                _short_fixture(bf), best,
                f"{_lean(p.p_over_15,'1.5')}/{_lean(p.p_over_25,'2.5')}",
                _dc_cell(p), stamp(bf.verification),
            ])
        table = _col(rows, ["Fixture", "1X2", "O1.5/O2.5", "DC/BTTS", "Src"])
        out.append(f"{league}\n{FENCE}\n{table}\n{FENCE}")
    return "\n\n".join(out)


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


# ---------------------------------------------------------------------------
# CANONICAL BOARD — the Architect's ##########OLP XDV######### layout
# ---------------------------------------------------------------------------
# Reconstructed to the saved-artifact spec (board_2026-09-04.txt,
# telegram_2026-09-08.txt): a four-table board — full market grid + AI pick,
# deploy-eligible singles, the ACCA route, and THE PICK — under the
# ##########OLP XDV######### header, with a compact honest footer.
#
# HR35 is carried through unchanged: booking codes render PENDING rather than
# fabricated, because the SportyBet booking-code bridge is not wired into THIS
# framework yet. A missing datum stays visible; it is never filled to look
# complete. Everything the model actually computes (picks, win %, alt markets,
# deploy triggers) is shown for real.

_CANON_HEAD = "##########OLP XDV#########"
_CANON_BAR = "=" * 34
_CANON_RULE = "─" * 34


def render_heartbeat(phase: str, leagues_scanned: list[str],
                      calibration_count: int, mean_clv: Optional[float],
                      board: list[BoardFixture], board_delivered: bool,
                      board_date: Optional[str] = None,
                      scorecard: Optional[str] = None) -> str:
    """The daily HEARTBEAT — a short 'system alive' ping sent every day, even on
    dry days. It carries no picks itself (the board does that); it confirms the
    run happened and summarises health, so silence never looks like a dead
    system. All counts are real (HR35)."""
    day = (date.fromisoformat(board_date) if board_date
           else date.today()).strftime("%a %d %b %Y")
    rated = sum(1 for b in board if b.probs is not None)
    priced = sum(1 for b in board if b.best_price is not None)
    picks = sum(1 for b in board if b.on_deploy_shortlist)
    clv = f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None else "CLV logged: ZERO"
    if picks:
        tail = ("Board delivered above." if board_delivered
                else f"{picks} deploy-eligible pick(s) today (see saved board).")
    else:
        tail = "No deploy-eligible picks in the 1.20–2.00 band today — nothing to bet."
    return (
        f"\U0001FAC0 OLP XDV heartbeat — {day}\n"
        f"System: ALIVE · {phase}\n"
        f"Scanned {len(leagues_scanned)} league(s): {rated} fixture(s) rated, "
        f"{priced} priced.\n"
        f"Deploy-eligible (odds 1.20–2.00): {picks} pick(s).\n"
        f"Phase 3 gate: CLV ledger {calibration_count}/30 legs with CLV, {clv}.\n"
        f"{tail}"
        + (f"\n\n{scorecard}" if scorecard else ""))


def _canon_short(fixture: str) -> str:
    """'Home v Away (League)' -> 'Home v Away' (league is a grouping detail)."""
    return fixture.split(" (")[0]


# Architect 2026-10-06 (order 40), after Monday's board: 7 of 9 singles won
# but every acca lost. At ~78% a leg, a 5-leg acca wins about 1 time in 3 and
# one surprise result sank 2-3 slips at once because the same matches sat in
# every acca. So: accas of 3 legs; only picks of 75%+ go into an acca; and no
# match is in more than one acca (the megas are the one place everything is
# combined). Fixtures are handed out in order: 50+ accas, main accas, alt
# accas, value acca — each takes only matches no earlier acca used.
ACCA_MIN, ACCA_MAX = 3, 3
ACCA_LEG_MIN = 0.75
# Architect 2026-10-08/09: a TABLE 3 acca is "meaningful": its combined SportyBet
# odds are 2.00 at least ("I don't want it to be less than 2 odds") and 3.00 at
# most ("2.1 ... or 2.5"), so fewer, longer accas ("collapse it from 6 to like
# 4"). Each acca takes the strongest remaining legs until it reaches 2.00, never
# passing 3.00 or TABLE3_MAX_LEGS. Applies to TABLE 3 only; 3A/3B/3C keep 3 legs.
TABLE3_ODDS_MIN = 2.00
TABLE3_ODDS_MAX = 3.00
TABLE3_MAX_LEGS = 6
MEGA_MAX_LEGS = 26             # SportyBet won't take 78 on one slip: split into parts


def _split_sizes(n: int, lo: int, hi: int) -> list[int]:
    """Near-equal sizes summing to n, NEVER above hi (more legs = more risk);
    as few groups as possible. A group may fall below lo only when n forces it
    (e.g. 11 -> 4, 4, 3)."""
    if n < 2:
        return []
    k = -(-n // hi)                       # ceil(n / hi) groups
    base, extra = divmod(n, k)
    return [base + 1] * extra + [base] * (k - extra)


def _acca_name(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return f"Acca {s}"


def _ranked_legs(shortlist: list[BoardFixture]) -> list[tuple]:
    legs = []
    for bf in shortlist:
        if bf.probs is None:
            continue
        pick, prob = _deploy_pick(bf)
        if prob:
            legs.append((bf, pick, prob))
    return sorted(legs, key=lambda t: t[2], reverse=True)


def _acca_legs(shortlist: list[BoardFixture]) -> list[tuple]:
    """Ranked deploy legs strong enough for an acca (order 40: 75%+)."""
    return [l for l in _ranked_legs(shortlist) if l[2] >= ACCA_LEG_MIN]


def _used(slips: list[tuple]) -> set[str]:
    """Matches already in these slips ('Home v Away')."""
    return {_canon_short(leg[0].fixture) for _n, legs, _c in slips for leg in legs}


def _build_accas(shortlist: list[BoardFixture]) -> list[tuple]:
    """Deploy picks of 75%+ grouped into accumulators of up to 3 legs,
    strongest legs first (Acca A = the top legs, then B, C, ...), leaving out
    the matches a 50+ acca already holds — a match is in one acca at most
    (order 40). Combined model probability = PRODUCT of the legs (an explicit
    independence assumption, stated on the board). [] if < 2 legs."""
    taken = _used(_build_safe3(shortlist))
    legs = [l for l in _acca_legs(shortlist) if _canon_short(l[0].fixture) not in taken]
    if len(legs) < 2:
        return []
    out = _table3_groups(legs)
    named = []
    for n, g in enumerate(out):
        combo = 1.0
        for _, _, prob in g:
            combo *= prob
        named.append((_acca_name(n), g, combo))
    return named


def _table3_groups(legs: list[tuple]) -> list[list]:
    """Ranked legs (strongest first) -> TABLE 3 accas of TABLE3_ODDS_MIN to
    TABLE3_ODDS_MAX combined odds. An acca keeps taking the next leg that fits
    under the max until it reaches the min (or TABLE3_MAX_LEGS). Legs left over
    that can't make a 2.00 acca of their own join the last acca while it stays
    within the max; any still left stay singles (Table 2).

    A leg without a quoted price can't be measured against the odds band, so
    a slate with one keeps the plain 3-leg grouping (order 40)."""
    if any(getattr(leg[0], "best_price", None) is None for leg in legs):
        out, i = [], 0
        for size in _split_sizes(len(legs), ACCA_MIN, ACCA_MAX):
            out.append(legs[i:i + size])
            i += size
        return out
    groups: list[list] = []
    pool = list(legs)
    while pool:
        g: list = []
        for leg in list(pool):
            if _acca_odds(g) >= TABLE3_ODDS_MIN or len(g) >= TABLE3_MAX_LEGS:
                break
            if _acca_odds(g + [leg]) <= TABLE3_ODDS_MAX:
                g.append(leg)
                pool.remove(leg)
        if not g:
            break
        if _acca_odds(g) >= TABLE3_ODDS_MIN and len(g) >= 2:
            groups.append(g)
            continue
        # too few legs left for a 2.00 acca: top up the last accas, else singles
        for leg in g:
            for last in reversed(groups):
                if len(last) < TABLE3_MAX_LEGS and _acca_odds(last + [leg]) <= TABLE3_ODDS_MAX:
                    last.append(leg)
                    break
        break
    return groups


def _build_megas(shortlist: list[BoardFixture]) -> list[tuple]:
    """All deploy picks split into as few near-equal slips as SportyBet allows
    (<= MEGA_MAX_LEGS each), strongest first. [(name, legs, combo), ...]."""
    legs = _ranked_legs(shortlist)
    if len(legs) < 2:
        return []
    k = -(-len(legs) // MEGA_MAX_LEGS)
    out, i = [], 0
    for n, size in enumerate(_split_sizes(len(legs), 2, -(-len(legs) // k))):
        g = legs[i:i + size]
        i += size
        combo = 1.0
        for _, _, prob in g:
            combo *= prob
        out.append((f"Mega {n + 1}", g, combo))
    return out


# ALTERNATIVE-MARKET ACCAS (Architect 2026-10-04, standing order 31): the same
# deploy fixtures, each with its likeliest winnable outcome from a DIFFERENT
# market family than its main pick (goals, handicaps, team goals ...), in
# accas of up to 3 legs (order 40: only matches no 50+ or main acca holds,
# 75%+ legs). The main slips all stand or fall on the same outcomes;
# these spread the risk over different outcomes of the same matches. Each alt
# leg is a little less likely than the main pick — this spreads risk, it does
# not raise the hit rate.
def alt_leg(bf: "BoardFixture") -> Optional[tuple]:
    """(key, chance, price) of the fixture's alternative-market leg, or None.

    From the run's pool of winnable in-band outcomes (>= 50%, price
    1.20-2.00): a different market family from the main pick, never one the
    team news flags, strongest chance first, then value."""
    if bf.probs is None or not bf.best_market_key:
        return None
    from engine.learning import family
    main = family(bf.best_market_key)
    from engine.half import is_first_half
    # first-half legs move with the full-time pick (a half-time "X or level"
    # beside a full-time "X or draw"), so they never spread the risk here
    pool = [c for c in (getattr(bf, "cand_pool", None) or [])
            if not is_first_half(c[2])
            and family(c[2]) != main and c[0] >= DEPLOY_MIN_MODEL_PROB]
    news = getattr(bf, "team_news", None)
    if news and pool:
        from engine import team_news as tn
        pool = [c for c in pool if tn.assess(c[2], news)["level"] not in ("CAUTION", "RISK")]
    if not pool:
        return None
    c = max(pool, key=lambda c: (c[0], c[1]))
    return c[2], c[0], c[5].price


SWITCH_WITHIN_PP = 0.05   # order 32: the steadier pick may be at most 5 pts less likely


def steadier_pick(bf: "BoardFixture", no_side: bool = False) -> Optional[tuple]:
    """The candidate a SHAKY pick switches to (standing order 32), or None.

    From the run's winnable in-band pool: a different market family from the
    pick, model and SportyBet agreeing (HIGH or MEDIUM certainty: within
    AGREE_PP), not touched by the team news, at most SWITCH_WITHIN_PP less
    likely than the pick. `no_side` keeps only outcomes that don't depend on
    which team wins (used when the two prediction models disagree on the
    result). The strongest such candidate, then the best value."""
    if bf.probs is None or not bf.best_market_key or bf.prob_source == "market":
        return None
    from engine.learning import family
    from engine import team_news as tn
    from engine.slate import AGREE_PP
    main = family(bf.best_market_key)
    floor = max(DEPLOY_MIN_MODEL_PROB, (bf.best_model_prob or 0.0) - SWITCH_WITHIN_PP)
    news = getattr(bf, "team_news", None)
    pool = []
    from engine.half import is_first_half
    for c in getattr(bf, "cand_pool", None) or []:
        win, _ev, key, model_p, market_p, _q = c
        if family(key) == main or win < floor or market_p is None or model_p is None:
            continue
        if is_first_half(key):
            continue     # first-half markets never become the main pick
        if abs(model_p - market_p) > AGREE_PP:
            continue
        if news and tn.assess(key, news)["level"] in ("CAUTION", "RISK"):
            continue
        if no_side and tn.pick_side(key):
            continue
        pool.append(c)
    return max(pool, key=lambda c: (c[0], c[1])) if pool else None


def _build_alt_accas(shortlist: list[BoardFixture]) -> list[tuple]:
    """[(name, [(bf, pick, prob, key, price)], combo)] — deploy fixtures whose
    alternative leg is 75%+ and that no 50+ or main acca already holds
    (order 40), strongest first, in accas of up to 3 legs."""
    taken = _used(_build_safe3(shortlist)) | _used(_build_accas(shortlist))
    legs = []
    for bf in shortlist:
        if bf.probs is None or _canon_short(bf.fixture) in taken:
            continue
        a = alt_leg(bf)
        if a and a[1] >= ACCA_LEG_MIN:
            key, prob, price = a
            legs.append((bf, mkt.display(key, bf.probs.home_team, bf.probs.away_team),
                         prob, key, price))
    legs.sort(key=lambda t: -t[2])
    if len(legs) < 2:
        return []
    out, i = [], 0
    for n, size in enumerate(_split_sizes(len(legs), ACCA_MIN, ACCA_MAX)):
        g = legs[i:i + size]
        i += size
        combo = 1.0
        for leg in g:
            combo *= leg[2]
        out.append((_acca_name(n).replace("Acca", "Alt"), g, combo))
    return out


VALUE_BET_MIN_EV = 0.02   # positive-value table (order 37): EV >= +2% on our chance


def value_leg(bf: BoardFixture) -> Optional[tuple[str, float, float, float, float, float]]:
    """POSITIVE-VALUE BET (order 37, Architect 2026-10-05): the outcome of this
    fixture whose price is furthest above our fair odds — EV >= +2% on our
    chance, still >= 50% and inside 1.20–2.00 (cand_pool holds only those) —
    when it is not already the main pick. None for a market-implied fixture
    (its numbers are the bookmaker's, so no outcome can beat them) or when the
    team news flags the outcome. Returns (key, chance, price, ev, model, market)."""
    if bf.probs is None or getattr(bf, "prob_source", "model") == "market":
        return None
    from engine import team_news as tn
    news = getattr(bf, "team_news", None)
    best = None
    for c in getattr(bf, "cand_pool", None) or []:
        chance, ev, key, model_p, market_p, quote = c
        if (key == bf.best_market_key or ev is None or ev < VALUE_BET_MIN_EV
                or market_p is None or not quote or not quote.price):
            continue
        if news and tn.assess(key, news)["level"] != "OK":
            continue
        if best is None or (ev, chance) > (best[3], best[1]):
            best = (key, chance, quote.price, ev, model_p, market_p)
    return best


def _build_value(shortlist: list[BoardFixture]) -> list[tuple]:
    """[(name, [(bf, pick, prob, key, price)], combo)] — each positive-value
    bet as its own single ("Value 1", …), best value first, then one
    "Value acca" when 2+ of them are 75%+ on matches no other acca holds
    (order 37; order 40: up to 3 legs, best value first)."""
    legs = []
    for bf in shortlist:
        v = value_leg(bf)
        if v:
            key, prob, price, ev, _m, _k = v
            legs.append((bf, mkt.display(key, bf.probs.home_team, bf.probs.away_team),
                         prob, key, price, ev))
    legs.sort(key=lambda t: -t[5])
    out = [(f"Value {i}", [leg[:5]], leg[2]) for i, leg in enumerate(legs, 1)]
    acca = [leg for leg in legs if leg[2] >= ACCA_LEG_MIN]
    if len(acca) > 1:
        taken = (_used(_build_safe3(shortlist)) | _used(_build_accas(shortlist))
                 | _used(_build_alt_accas(shortlist)))
        acca = [leg for leg in acca if _canon_short(leg[0].fixture) not in taken][:ACCA_MAX]
    if len(acca) > 1:
        combo = 1.0
        for leg in acca:
            combo *= leg[2]
        out.append(("Value acca", [leg[:5] for leg in acca], combo))
    return out


def _alt_odds(legs) -> float:
    odds = 1.0
    for leg in legs:
        odds *= leg[4] or 1.0
    return odds


SAFE3_LEGS = 3            # Architect 2026-10-02: 3-leg accas at 50%+
SAFE3_MIN_CHANCE = 0.50
_CERT_ORDER = {"HIGH": 0, "MEDIUM": 1}


def _build_safe3(shortlist: list[BoardFixture]) -> list[tuple]:
    """3-leg accas with a combined chance of 50%+, built ONLY from
    high-certainty legs (HIGH first, then MEDIUM — never LOW: a leg whose %
    we can't trust can't carry a 50%+ promise). Strongest legs first; stops
    at the first trio below 50%. A fixture appears in at most one."""
    legs = [l for l in _acca_legs(shortlist)
            if l[0].certainty in _CERT_ORDER]
    legs.sort(key=lambda t: (_CERT_ORDER[t[0].certainty], -t[2]))
    out = []
    for i in range(0, len(legs) - SAFE3_LEGS + 1, SAFE3_LEGS):
        g = sorted(legs[i:i + SAFE3_LEGS], key=lambda t: -t[2])
        combo = 1.0
        for _, _, prob in g:
            combo *= prob
        if combo < SAFE3_MIN_CHANCE:
            break
        out.append((f"50+ #{len(out) + 1}", g, combo))
    return out


LAGOS = timezone(timedelta(hours=1))      # WAT — Nigeria has no daylight saving


def kickoff(bf) -> str:
    """Kickoff in Lagos time, HH:MM (order 28), from the kickoff the run
    fetched (SportyBet's event start, or FotMob's for deploy picks). PENDING
    when no source gave a time — never a guessed one (HR35)."""
    ko = getattr(bf, "kickoff_utc", None) or ""
    if "T" not in ko:
        return "PENDING"
    try:
        when = datetime.fromisoformat(ko.replace("Z", "+00:00").replace(".000", ""))
    except ValueError:
        return "PENDING"
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(LAGOS).strftime("%H:%M")


def render_canonical_board(mode: str, phase: str, leagues_scanned: list[str],
                            calibration_count: int, mean_clv: Optional[float],
                            data_flags: list[str], board: list[BoardFixture],
                            acca_code: Optional[str] = None,
                            board_code: Optional[str] = None,
                            acca_codes: Optional[dict] = None,
                            mega_codes: Optional[dict] = None,
                            board_date: Optional[str] = None,
                            safe3_codes: Optional[dict] = None,
                            extra_codes: Optional[dict] = None,
                            run_id: Optional[str] = None,
                            alt_codes: Optional[dict] = None,
                            value_codes: Optional[dict] = None) -> str:
    """The ##########OLP XDV######### board the Architect reads on Telegram.

    Booking codes (real SportyBet share codes) are attached upstream by run_daily:
    per-fixture on BoardFixture.booking_code, plus the whole-board `board_code`
    and the Acca A `acca_code`. Anything unresolved renders PENDING (HR35).
    `board_date` (YYYY-MM-DD) is the day the board is FOR — the evening run passes
    tomorrow; defaults to today. `run_id` traces the board to the run that built
    it (HR59); a board without one renders "Run ID: PENDING" and the send gate
    (output.notify.board_gate) keeps it off Telegram."""
    day = (date.fromisoformat(board_date) if board_date
           else date.today()).strftime("%a %d %b %Y")
    verified = sum(1 for bf in board if bf.verification.tier == Tier.VERIFIED)
    out = [_CANON_HEAD, _CANON_BAR, "",
           f"\U0001F4C5  {day}   (PICK · win %  ·  alt markets)",
           f"Run ID: {run_id or 'PENDING'} | {phase}",
           f"Fixtures scanned: {len(board)} · Verified: {verified}",
           "KO = kickoff, Lagos time (WAT)", ""]

    if data_flags:
        out.append(f"⚠ {len(data_flags)} data flag(s) — full detail in the "
                   f"saved board / VERIFY RESULTS")
        out.append("")

    # --- TABLE 1 · full market grid + AI pick ---
    out += [_CANON_RULE, "TABLE 1 · LAYER 2 — FULL MARKET GRID + AI PICK",
            _CANON_RULE, ""]
    # Grouped by competition (blank line between, for the phone and so long
    # boards split on competition boundaries), strongest pick first within each.
    # NO-DATA fixtures leave the table for one collapsed line below it
    # (Telegram Output Spec §3, standing order 30) — listed, never dropped.
    rated = [bf for bf in board if bf.probs is not None]
    no_data = [bf for bf in board if bf.probs is None]
    if not board:
        out.append("No fixtures scanned today.")
    elif not rated:
        out.append("No fixture could be rated today.")
    else:
        order: dict[str, int] = {}
        for bf in rated:
            order.setdefault(comp.label(comp.league_of(bf.fixture)), len(order))
        rated.sort(key=lambda bf: (order[comp.label(comp.league_of(bf.fixture))],
                                   -(_deploy_pick(bf)[1] or 0.0)))
        rows, groups = [], []
        for bf in rated:
            where = comp.label(comp.league_of(bf.fixture))
            groups.append(where)
            p = bf.probs
            pick, prob = _deploy_pick(bf)
            pick_cell = (f"{'⇄' if bf.switched_from else ''}{_TIER_MARK.get(bf.tier, '')}"
                         f"{pick} · {round(prob*100)}%"
                         if prob else pick)
            odds = f"@{bf.best_price:.2f}" if bf.best_market_key and bf.best_price else "—"
            altm = (f"{bf.alt_market} @{bf.alt_price:.2f}" if bf.alt_market
                    else "—")
            alt = f"{_lean(p.p_over_15,'1.5')}/{_lean(p.p_over_25,'2.5')}"
            src = stamp(bf.verification) + ("ᴹ" if bf.prob_source == "market" else "")
            rows.append([kickoff(bf), _canon_short(bf.fixture), where, pick_cell, odds, altm,
                         alt, _dc_cell(p), src])
        table = _col(rows, ["KO", "Fixture", "Country · League", "AI PICK · win%", "Odds",
                            "Alt market", "O1.5/O2.5", "DC/BTTS", "Src"]).split("\n")
        lines = table[:1]
        for i, row in enumerate(table[1:]):
            if i and groups[i] != groups[i - 1]:
                lines.append("")
            lines.append(row)
        out.append(FENCE)
        out += lines
        out.append(FENCE)
        out.append("★ BANKER = straight win, model + market agree ≥70% "
                   "(backtest: 82% won, +4%) · ✓ SAFE = model + market agree · "
                   "ᴮ BOOK = model and SportyBet disagree, so the bookmaker's pick is "
                   "followed · $ VALUE = both teams to score / over goals priced above "
                   "its fair odds (order 36) · ⚠ SPLIT = no in-band outcome either side backs")
        if any(bf.prob_source == "market" for bf in board):
            out.append("ᴹ = MARKET-IMPLIED: no model history for this fixture — "
                       "priced from SportyBet with the margin removed; no edge claimed.")
        out.append("Src: ✓ = fixture confirmed by two independent sources (TheSportsDB · "
                   "ESPN · football-data · FotMob · Flashscore) · ○ = one source only · ⚠ = sources disagree "
                   "(e.g. postponed) — not deployed")
    if no_data:
        out += ["", f"⚠ {len(no_data)} fixture(s) unresolved — NO DATA — PENDING (no "
                    f"market data): " + " · ".join(comp.where(bf.fixture) for bf in no_data)
                + (f"   (full detail: run log {run_id})" if run_id else "")]
    acca_codes = dict(acca_codes or {})
    if acca_code and "Acca A" not in acca_codes:
        acca_codes["Acca A"] = acca_code
    shortlist = [bf for bf in board if bf.on_deploy_shortlist]
    extra_codes = extra_codes or {}

    # MEGA CODES (Architect 2026-10-03): every table carries a mega booking
    # code for all of its picks — one slip, or several of <= MEGA_MAX_LEGS
    # legs when SportyBet can't take them all at once.
    def _mega_lines(label: str) -> list[str]:
        if mega_codes is not None:
            lines = []
            for name, legs, combo in _build_megas(shortlist):
                code = mega_codes.get(name) or "PENDING"
                lines.append(f"{label} {name} ({len(legs)} legs · odds {_acca_odds(legs):,.0f} · "
                             f"chance 1 in {1 / combo:,.0f}): {code}"
                             + (f"   load ↦ www.sportybet.com/ng/?shareCode={code}"
                                if code != "PENDING" else ""))
            return lines
        if board_code:
            return [f"{label} mega code (all {len(shortlist)} deploy singles): {board_code}   "
                    f"load ↦ www.sportybet.com/ng/?shareCode={board_code}"]
        return [f"{label} mega code: PENDING (no deploy-eligible single resolved on "
                "SportyBet today)"]

    out += [""] + _mega_lines("TABLE 1") + [""]

    # --- TABLE 2 · deploy-eligible singles ---
    out += [_CANON_RULE, "TABLE 2 · LAYER 1 — DEPLOY-ELIGIBLE SINGLES",
            "(fixtures that clear the deploy threshold, one row each, own code)",
            _CANON_RULE, ""]
    if not shortlist:
        out.append("No deploy-eligible fixtures kicking off today.")
    else:
        rows = []
        for bf in shortlist:
            where = comp.label(comp.league_of(bf.fixture))
            if bf.probs is None:
                rows.append([kickoff(bf), _canon_short(bf.fixture), where, "NO DATA — PENDING", "—",
                             "—", "—", "—", "PENDING"])
                continue
            pick, prob = _deploy_pick(bf)
            trig = f"{bf.mes_trigger_price:.2f}+" if bf.mes_trigger_price else "NO DATA"
            price = f"@{bf.best_price:.2f}" if bf.best_price else "—"
            rows.append([kickoff(bf), _canon_short(bf.fixture), where,
                         ("⇄" if bf.switched_from else "") + _TIER_MARK.get(bf.tier, "") + pick,
                         f"{round(prob*100)}%" if prob else "—", price,
                         bf.certainty or "—",
                         (f"{bf.stake_pct:g}%" if bf.stake_pct else
                          ("PAUSED" if bf.stake_pct == 0 else "—")),
                         bf.booking_code or "PENDING"])
        out.append(FENCE)
        out.append(_col(rows, ["KO", "Fixture", "Country · League", "Pick", "Chance", "Odds",
                               "Certainty", "Stake", "Code"]))
        out.append(FENCE)
        out.append("Certainty = how sure we are the chance % is right: HIGH = model and "
                   "SportyBet within 3 pts · MEDIUM = within 7 · LOW = they disagree "
                   "or only one source.")
        out.append("Stake = suggested % of your bankroll per single (bigger only where an "
                   "edge is proven; PAUSED = stop-loss). Accas 0.25%, 50%+ accas 0.5%, "
                   "megas 0.1%.")
        out += _price_check_lines(shortlist)
        out += _sharp_lines(shortlist)
        sw = [bf for bf in shortlist if bf.switched_from and bf.probs is not None]
        if sw:
            out += ["", f"⇄ SWITCHED — {len(sw)} shaky pick(s) moved to a steadier market "
                        f"(model and SportyBet agree, at most 5 pts less likely):"]
            for bf in sw:
                out.append(f"   • {comp.where(bf.fixture)} — was {bf.switched_from} → now "
                           f"{_deploy_pick(bf)[0]} ({round((bf.best_model_prob or 0) * 100)}%, "
                           f"{bf.certainty})")
        news = [bf for bf in shortlist if bf.news_level in ("CAUTION", "RISK")]
        if news:
            out += ["", f"⚠ TEAM NEWS — {len(news)} pick(s) hit by injuries/suspensions "
                        f"(certainty lowered; re-checked when lineups are confirmed):"]
            for bf in news:
                out.append(f"   • {bf.news_level}: {comp.where(bf.fixture)} — {bf.news_note}")
        prof_rows = [bf for bf in shortlist if getattr(bf, "profile_line", None)]
        if prof_rows:
            out += ["", "TEAM PROFILES (last 20 games each side — context, not a price):"]
            for bf in prof_rows:
                out.append(f"   • {_canon_short(bf.fixture)}: {bf.profile_line}")
        out += [""] + _mega_lines("TABLE 2")
    out.append("")

    # --- TABLE 3A · 50%+ accas (3 legs, high certainty) ---
    safe3 = _build_safe3(shortlist)
    safe3_codes = safe3_codes or {}
    out += [_CANON_RULE, "TABLE 3A · 50%+ ACCAS",
            "(3 legs each, high-certainty 75%+ legs only, combined chance 50% or more)",
            _CANON_RULE, ""]
    if not safe3:
        out.append("No 3-leg acca reaches 50% from high-certainty legs today.")
    else:
        for name, legs, combo in safe3:
            out.append(f"{name} · code {safe3_codes.get(name) or 'PENDING'} · odds "
                       f"{_acca_odds(legs):.2f} · chance {round(combo*100)}%")
            for bf, pick, prob in legs:
                price = f" @{bf.best_price:.2f}" if bf.best_price else ""
                out.append(f"   • {kickoff(bf)} {comp.where(bf.fixture)} — {pick}{price} "
                           f"({round(prob*100)}%, {bf.certainty})")
        if len(safe3) > 1:
            n = sum(len(l) for _, l, _ in safe3)
            code = extra_codes.get("safe3_mega") or "PENDING"
            out += ["", f"TABLE 3A mega code (all {len(safe3)} accas, {n} legs): {code}"
                    + (f"   load ↦ www.sportybet.com/ng/?shareCode={code}" if code != "PENDING" else "")]
    out.append("")

    # --- TABLE 3 · ACCA route ---
    out += [_CANON_RULE, "TABLE 3 · ACCA ROUTE",
            "(75%+ picks only, each acca 2.00–3.00 odds, a match in one acca at most — order 40)",
            _CANON_RULE, ""]
    accas = _build_accas(shortlist)
    if not accas:
        out.append("No capital-eligible accas generated.")
    else:
        out.append(f"{len(accas)} accas · {sum(len(l) for _, l, _ in accas)} picks of 75%+ "
                   f"not already in a 50+ acca — every code is also in ALL CODES at the end.")
        _low = sum(1 for _l in _ranked_legs(shortlist) if _l[2] < ACCA_LEG_MIN)
        if _low:
            out.append(f"{_low} pick(s) under 75% stay singles only (Table 2).")
        out.append("")
        for name, legs, combo in accas:
            code = acca_codes.get(name) or "PENDING"
            out.append(f"{name} · code {code} · {len(legs)} legs · odds "
                       f"{_acca_odds(legs):.2f} · chance {round(combo*100)}%")
            for bf, pick, prob in legs:
                price = f" @{bf.best_price:.2f}" if bf.best_price else ""
                out.append(f"   • {kickoff(bf)} {comp.where(bf.fixture)} — {pick}{price} "
                           f"({round(prob*100)}%)")
        out += ["", "Every deploy pick on one slip (the same slip as Table 2's mega):"] \
            + _mega_lines("TABLE 3")
    out.append("")

    # --- TABLE 3B · alternative-market accas (order 31) ---
    alts = _build_alt_accas(shortlist)
    alt_codes = alt_codes or {}
    out += [_CANON_RULE, "TABLE 3B · ALT-MARKET ACCAS",
            "(matches no other acca holds, each on a DIFFERENT market from its main",
            " pick — goals, handicaps, team goals — 75%+ legs, 3 per acca)",
            _CANON_RULE, ""]
    if not alts:
        out.append("No alternative leg of 75%+ on a match no other acca holds today.")
    else:
        for name, legs, combo in alts:
            out.append(f"{name} · code {alt_codes.get(name) or 'PENDING'} · {len(legs)} legs · "
                       f"odds {_alt_odds(legs):.2f} · chance {round(combo*100)}%")
            for bf, pick, prob, _key, price in legs:
                px = f" @{price:.2f}" if price else ""
                out.append(f"   • {kickoff(bf)} {comp.where(bf.fixture)} — {pick}{px} "
                           f"({round(prob*100)}%)")
        out += ["", "Each alt leg is a little less likely than the main pick: this spreads "
                    "the risk, it does not raise the hit rate. Not part of the £1 live "
                    "test (order 26) unless the Architect says so."]
    out.append("")

    # --- TABLE 3C · positive-value bets (order 37) ---
    values = _build_value(shortlist)
    value_codes = value_codes or {}
    out += [_CANON_RULE, "TABLE 3C · POSITIVE-VALUE BETS",
            "(priced ABOVE our fair odds — the bets with value in them, even where",
            " they are not the likeliest outcome)", _CANON_RULE, ""]
    if not values:
        out.append("No outcome priced above our fair odds today (EV +2% or more, 50%+, "
                   "1.20–2.00).")
    else:
        for name, legs, combo in values:
            if name == "Value acca":
                out.append(f"{name} · code {value_codes.get(name) or 'PENDING'} · "
                           f"{len(legs)} legs · odds {_alt_odds(legs):.2f} · "
                           f"chance {round(combo*100)}%")
                continue
            bf, pick, prob, _key, price = legs[0]
            v = value_leg(bf)
            gap = f" · model {v[4]:.0%} vs SportyBet {v[5]:.0%}" if v else ""
            out.append(f"{name} · code {value_codes.get(name) or 'PENDING'} · "
                       f"{kickoff(bf)} {comp.where(bf.fixture)} — {pick} @{price:.2f} "
                       f"({round(prob*100)}%, value {v[3]*100:+.1f}%{gap})" if v else
                       f"{name} · {comp.where(bf.fixture)} — {pick} @{price:.2f}")
        out += ["", "Value means our chance × price is above 1. It comes from the model "
                    "disagreeing with SportyBet, which is unproven: graded as its own "
                    "line, minimal stake (0.25%) until results prove it."]
    out.append("")

    # --- TABLE 4 · the pick ---
    out += [_CANON_RULE, "TABLE 4 · THE PICK",
            "(primary single + Acca A recommendation)", _CANON_RULE, ""]
    ranked = [bf for bf in shortlist if bf.probs is not None]
    if not ranked:
        out.append("No pick today — nothing cleared the deploy threshold.")
    else:
        top = max(ranked, key=lambda b: _deploy_pick(b)[1] or 0.0)
        pick, prob = _deploy_pick(top)
        price = f" @{top.best_price:.2f}" if top.best_price else ""
        out.append(f"Primary single: {comp.where(top.fixture)} — {pick} "
                   f"({round((prob or 0)*100)}%){price} · code "
                   f"{top.booking_code or 'PENDING'}")
        if accas:
            out.append(f"Acca A: {len(accas[0][1])} legs, model "
                       f"{round(accas[0][2]*100)}% · code {acca_codes.get('Acca A') or 'PENDING'}")
    out.append("")

    # --- footer ---
    clv = f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None else "CLV logged: ZERO"
    any_code = bool(board_code or acca_codes or mega_codes
                    or any(bf.booking_code for bf in shortlist))
    if any_code:
        code_line = ("Booking codes: live SportyBet share codes — load a code on "
                     "SportyBet to see the slip. Nothing is placed; the Architect "
                     "deploys.")
    else:
        code_line = ("Booking codes: PENDING — no deploy-eligible pick resolved on "
                     "SportyBet today (HR35: shown, never fabricated).")
    out += [_CANON_BAR,
            "Honest edge: not a demonstrated edge · Capital: Architect only.",
            f"Deploy odds band: {DEPLOY_ODDS_MIN:.2f}–{DEPLOY_ODDS_MAX:.2f} "
            f"(safest ~{DEPLOY_ODDS_SAFE:.2f}); picks above 2.00 are never deployed.",
            f"Calibration: {calibration_count} legs logged, {clv}.",
            code_line,
            _CANON_BAR]

    # --- ALL CODES: every acca + mega code in one short block, LAST, so it
    # lands in its own final Telegram message and can't be missed in a long
    # board (2026-10-02: accas G-O sat in a later message and were missed).
    if accas or mega_codes or safe3 or board_code or alts or values:
        out += ["", "ALL CODES"]
        for name, legs, combo in safe3:
            out.append(f"{name}: {safe3_codes.get(name) or 'PENDING'} "
                       f"(3 legs · odds {_acca_odds(legs):.2f} · {round(combo*100)}% · "
                       f"stake 0.5%)")
        if len(safe3) > 1:
            out.append(f"50+ MEGA: {extra_codes.get('safe3_mega') or 'PENDING'} "
                       f"({sum(len(l) for _, l, _ in safe3)} legs · all 50%+ accas · stake 0.1%)")
        if mega_codes is None and board_code:
            out.append(f"Board MEGA: {board_code} ({len(shortlist)} legs · every single · "
                       f"stake 0.1%)")
        if extra_codes.get("accas_mega"):
            out.append(f"ACCAS MEGA: {extra_codes['accas_mega']} "
                       f"({sum(len(l) for _, l, _ in accas)} legs · every Table 3 acca on one slip · "
                       f"odds {_acca_odds([x for _, l, _ in accas for x in l]):,.2f} · stake 0.1%)")
        if extra_codes.get("alts_mega"):
            out.append(f"ALT MEGA: {extra_codes['alts_mega']} "
                       f"({extra_codes.get('alts_mega_legs', '?')} legs · every alt acca on one slip · stake 0.1%)")
        if extra_codes.get("value_mega"):
            out.append(f"VALUE MEGA: {extra_codes['value_mega']} "
                       f"({extra_codes.get('value_mega_legs', '?')} legs · every value bet on one slip · stake 0.1%)")
        megas = _build_megas(shortlist) if mega_codes is not None else []
        for name, legs, combo in megas:
            out.append(f"{name}: {(mega_codes or {}).get(name) or 'PENDING'} "
                       f"({len(legs)} legs · odds {_acca_odds(legs):,.0f} · stake 0.1%)")
        for name, legs, combo in accas:
            out.append(f"{name}: {acca_codes.get(name) or 'PENDING'} "
                       f"({len(legs)} legs · odds {_acca_odds(legs):.2f} · "
                       f"{round(combo*100)}% · stake 0.25%)")
        for name, legs, combo in alts:
            out.append(f"{name}: {alt_codes.get(name) or 'PENDING'} "
                       f"({len(legs)} legs · alt markets · odds {_alt_odds(legs):.2f} · "
                       f"{round(combo*100)}% · stake 0.25%)")
        for name, legs, combo in values:
            out.append(f"{name}: {value_codes.get(name) or 'PENDING'} "
                       f"({len(legs)} leg{'s' if len(legs) > 1 else ''} · positive value · "
                       f"odds {_alt_odds(legs):.2f} · {round(combo*100)}% · "
                       f"stake {'0.1' if len(legs) > 1 else '0.25'}%)")
    return "\n".join(out)


def render_subscriber_codes(board_text: str, board: list, board_date: str) -> str:
    """What a subscriber gets (order 33, Architect 2026-10-09: "just send them
    the codes, the booking codes ... they just only need the code"): each
    deploy single's code, then every acca / mega / alt / value code from the
    board's ALL CODES block — no tables, chances, stakes or analysis."""
    try:
        from datetime import date as _d
        day = _d.fromisoformat(board_date).strftime("%a %d %b")
    except (TypeError, ValueError):
        day = board_date or ""
    out = [f"OLP XDV · {day} · booking codes",
           "Load a code on SportyBet: Betslip → Load code (or sportybet.com/ng/?shareCode=CODE)"]
    singles = sorted((bf for bf in board
                      if getattr(bf, "on_deploy_shortlist", False) and getattr(bf, "booking_code", None)),
                     key=lambda bf: kickoff(bf))
    if singles:
        out += ["", "SINGLES"]
        for bf in singles:
            pick, _p = _deploy_pick(bf)
            price = f" @{bf.best_price:.2f}" if bf.best_price else ""
            out.append(f"{kickoff(bf)} {_canon_short(bf.fixture)} — {pick}{price}: {bf.booking_code}")
    parts = (board_text or "").split("\nALL CODES\n", 1)
    if len(parts) == 2:
        rows = []
        for line in parts[1].splitlines():
            if line.startswith("===="):
                break
            if line.strip():
                rows.append(re.sub(r" · stake [0-9.]+%", "", line))
        if rows:
            out += ["", "ACCAS · MEGAS · VALUE"] + rows
    if len(out) == 2:
        out += ["", "No booking codes today."]
    return "\n".join(out)


def _acca_odds(legs) -> float:
    odds = 1.0
    for bf, _pick, _prob in legs:
        odds *= getattr(bf, "best_price", None) or 1.0
    return odds


def render_telegram_board(mode: str, phase: str, leagues_scanned: list[str],
                           calibration_count: int, mean_clv: Optional[float],
                           data_flags: list[str], board: list[BoardFixture]) -> str:
    """The 07:00 message: flags in plain text, then the two tables."""
    shortlist = [bf for bf in board if bf.on_deploy_shortlist]
    clv = f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None else "CLV logged: ZERO"

    parts = [
        f"OLP XDV — DAILY BOARD\n{date.today().isoformat()}  |  {phase}\n"
        f"Leagues: {', '.join(leagues_scanned)}\n"
        f"Calibration: {calibration_count} legs logged, {clv}",
    ]
    if data_flags:
        parts.append("DATA FLAGS (surfaced first, per HR53/ID403)\n"
                     + "\n".join(f"⚠ {f}" for f in data_flags))
    parts.append(render_recommended_table(shortlist))
    detail = render_pick_detail(shortlist)
    if detail:
        parts.append(detail)
    parts.append(render_scan_tables(board))
    parts.append("HONEST EDGE LINE: an excellent informed process but NOT a "
                 "demonstrated profitable edge.\nCapital authority: THE "
                 "ARCHITECT. Nothing here is live until you deploy it.")
    return "\n\n".join(parts)
