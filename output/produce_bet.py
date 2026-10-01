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
from engine.slate import (DEPLOY_POOL_CAP, DEPLOY_ODDS_MIN, DEPLOY_ODDS_MAX,
                          DEPLOY_ODDS_SAFE)
from engine import markets as mkt
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
                      board_date: Optional[str] = None) -> str:
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
        f"Phase 3 gate: CLV ledger {calibration_count}/ legs with CLV, {clv}.\n"
        f"{tail}")


def _canon_short(fixture: str) -> str:
    """'Home v Away (League)' -> 'Home v Away' (league is a grouping detail)."""
    return fixture.split(" (")[0]


def _build_accas(shortlist: list[BoardFixture]) -> list[tuple]:
    """Group the deploy-eligible singles into one honest accumulator (Acca A) of
    the strongest legs. The combined model probability is the PRODUCT of the leg
    probabilities — an explicit independence assumption, stated on the board, not
    hidden. Returns [] when fewer than two legs qualify (no acca to route)."""
    legs = []
    for bf in shortlist:
        if bf.probs is None:
            continue
        pick, prob = _deploy_pick(bf)
        if prob:
            legs.append((bf, pick, prob))
    if len(legs) < 2:
        return []
    legs = sorted(legs, key=lambda t: t[2], reverse=True)[:4]  # cap Acca A at 4 legs
    combo = 1.0
    for _, _, prob in legs:
        combo *= prob
    return [("Acca A", legs, combo)]


def render_canonical_board(mode: str, phase: str, leagues_scanned: list[str],
                            calibration_count: int, mean_clv: Optional[float],
                            data_flags: list[str], board: list[BoardFixture],
                            acca_code: Optional[str] = None,
                            board_code: Optional[str] = None,
                            board_date: Optional[str] = None) -> str:
    """The ##########OLP XDV######### board the Architect reads on Telegram.

    Booking codes (real SportyBet share codes) are attached upstream by run_daily:
    per-fixture on BoardFixture.booking_code, plus the whole-board `board_code`
    and the Acca A `acca_code`. Anything unresolved renders PENDING (HR35).
    `board_date` (YYYY-MM-DD) is the day the board is FOR — the evening run passes
    tomorrow; defaults to today."""
    day = (date.fromisoformat(board_date) if board_date
           else date.today()).strftime("%a %d %b %Y")
    out = [_CANON_HEAD, _CANON_BAR, "",
           f"\U0001F4C5  {day}   (PICK · win %  ·  alt markets)", "", ""]

    if data_flags:
        out.append(f"⚠ {len(data_flags)} data flag(s) — full detail in the "
                   f"saved board / VERIFY RESULTS")
        out.append("")

    # --- TABLE 1 · full market grid + AI pick ---
    out += [_CANON_RULE, "TABLE 1 · LAYER 2 — FULL MARKET GRID + AI PICK",
            _CANON_RULE, ""]
    if not board:
        out.append("No fixtures scanned today.")
    else:
        rows = []
        for bf in board:
            if bf.probs is None:
                rows.append([_canon_short(bf.fixture), "NO DATA — PENDING", "—",
                             "—", stamp(bf.verification)])
                continue
            p = bf.probs
            pick, prob = _best_market_desc(p)
            pick_cell = f"{pick} · {round(prob*100)}%" if prob else pick
            alt = f"{_lean(p.p_over_15,'1.5')}/{_lean(p.p_over_25,'2.5')}"
            rows.append([_canon_short(bf.fixture), pick_cell, alt, _dc_cell(p),
                         stamp(bf.verification)])
        out.append(FENCE)
        out.append(_col(rows, ["Fixture", "AI PICK · win%", "O1.5/O2.5",
                               "DC/BTTS", "Src"]))
        out.append(FENCE)
    if board_code:
        out += ["", f"Board code (all deploy singles): {board_code}   "
                f"load ↦ www.sportybet.com/ng/?shareCode={board_code}", ""]
    else:
        out += ["", "Board code: PENDING (no deploy-eligible single resolved on "
                "SportyBet today)", ""]

    shortlist = [bf for bf in board if bf.on_deploy_shortlist]

    # --- TABLE 2 · deploy-eligible singles ---
    out += [_CANON_RULE, "TABLE 2 · LAYER 1 — DEPLOY-ELIGIBLE SINGLES",
            "(fixtures that clear the deploy threshold, one row each, own code)",
            _CANON_RULE, ""]
    if not shortlist:
        out.append("No deploy-eligible fixtures kicking off today.")
    else:
        rows = []
        for bf in shortlist:
            if bf.probs is None:
                rows.append([_canon_short(bf.fixture), "NO DATA — PENDING", "—",
                             "—", "PENDING"])
                continue
            pick, prob = _deploy_pick(bf)
            trig = f"{bf.mes_trigger_price:.2f}+" if bf.mes_trigger_price else "NO DATA"
            price = f"@{bf.best_price:.2f}" if bf.best_price else "—"
            rows.append([_canon_short(bf.fixture), pick,
                         f"{round(prob*100)}%" if prob else "—", price,
                         bf.booking_code or "PENDING"])
        out.append(FENCE)
        out.append(_col(rows, ["Fixture", "Pick", "Model%", "Odds", "Code"]))
        out.append(FENCE)
    out.append("")

    # --- TABLE 3 · ACCA route ---
    out += [_CANON_RULE, "TABLE 3 · ACCA ROUTE",
            "(capital-eligible grouped accumulators, own code per acca)",
            _CANON_RULE, ""]
    accas = _build_accas(shortlist)
    if not accas:
        out.append("No capital-eligible accas generated.")
    else:
        for name, legs, combo in accas:
            code = acca_code or "PENDING"
            out.append(f"{name}  ({len(legs)} legs · model {round(combo*100)}% "
                       f"· code {code})")
            for bf, pick, prob in legs:
                out.append(f"   • {_canon_short(bf.fixture)} — {pick} "
                           f"({round(prob*100)}%)")
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
        out.append(f"Primary single: {_canon_short(top.fixture)} — {pick} "
                   f"({round((prob or 0)*100)}%){price} · code "
                   f"{top.booking_code or 'PENDING'}")
        if accas:
            out.append(f"Acca A: {len(accas[0][1])} legs, model "
                       f"{round(accas[0][2]*100)}% · code {acca_code or 'PENDING'}")
    out.append("")

    # --- footer ---
    clv = f"mean CLV {mean_clv:+.2f}%" if mean_clv is not None else "CLV logged: ZERO"
    any_code = bool(board_code or acca_code
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
    return "\n".join(out)


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
