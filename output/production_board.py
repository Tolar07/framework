"""
PRODUCTION BOARD — the single Telegram render path.

Implements the Architect's FINAL TELEGRAM OUTPUT SPEC (RATIFIED 2026-09-17),
stored canonically at docs/obsidian-vault/Telegram Output Spec.md.

  §1 header (run_id mandatory)   §2 stacked per-fixture block, grouped by
  competition                    §3 NO-DATA collapsed footer
  §4 acca route                  §5 competition-boundary chunking
  §7 honest-edge footer

Replaces the four-table blend (render_layer2_full_grid / render_layer1_compact /
render_the_pick), which the spec suspends in §0: it renders clumsily at phone
width. The stacked block reads without horizontal scroll and satisfies HR53
(full club names, markets named in words).

A NOTE ON "EV" — deliberate, not an oversight.
Spec §2 labels the per-pick number "EV" and then defines it as
`(model_prob − market_implied_prob) × 100`. That formula is this framework's
canonical EDGE, not EV (`model_prob × price − 1`). The spec's FORMULA is
authoritative here, so the number rendered is the edge; the spec's LABEL is
kept so the board matches the ratified document the Architect signed off.
Both inputs are printed beside it, as §2 requires, so the figure is auditable
either way and cannot be silently misread.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# Telegram hard-limits a message to 4096 characters. Chunking targets this and
# never splits a fixture block (spec §5).
TELEGRAM_MAX = 3900

# Spec §4.1(2) / §2 sub-threshold rule.
EV_THRESHOLD = 0.02

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Country -> flag. Covers every country in config/leagues.json (57 as of
# 2026-09-17). "Europe"/"World" are competition scopes, not nations, and get a
# trophy rather than a wrong flag.
_FLAGS = {
    "Albania": "🇦🇱", "Andorra": "🇦🇩", "Armenia": "🇦🇲", "Austria": "🇦🇹",
    "Azerbaijan": "🇦🇿", "Belarus": "🇧🇾", "Belgium": "🇧🇪",
    "Bosnia and Herzegovina": "🇧🇦", "Bulgaria": "🇧🇬", "Croatia": "🇭🇷",
    "Cyprus": "🇨🇾", "Czech Republic": "🇨🇿", "Denmark": "🇩🇰",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Estonia": "🇪🇪", "Faroe Islands": "🇫🇴",
    "Finland": "🇫🇮", "France": "🇫🇷", "Georgia": "🇬🇪", "Germany": "🇩🇪",
    "Gibraltar": "🇬🇮", "Greece": "🇬🇷", "Hungary": "🇭🇺", "Iceland": "🇮🇸",
    "Israel": "🇮🇱", "Italy": "🇮🇹", "Kazakhstan": "🇰🇿", "Kosovo": "🇽🇰",
    "Latvia": "🇱🇻", "Liechtenstein": "🇱🇮", "Lithuania": "🇱🇹",
    "Luxembourg": "🇱🇺", "Malta": "🇲🇹", "Moldova": "🇲🇩",
    "Montenegro": "🇲🇪", "Netherlands": "🇳🇱", "North Macedonia": "🇲🇰",
    "Northern Ireland": "🏴", "Norway": "🇳🇴", "Poland": "🇵🇱",
    "Portugal": "🇵🇹", "Republic of Ireland": "🇮🇪", "Romania": "🇷🇴",
    "Russia": "🇷🇺", "San Marino": "🇸🇲", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Serbia": "🇷🇸", "Slovakia": "🇸🇰", "Slovenia": "🇸🇮", "Spain": "🇪🇸",
    "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Turkey": "🇹🇷", "Ukraine": "🇺🇦",
    "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Europe": "🏆", "World": "🏆",
}

_RULE = "─" * 34


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _country_of(league: str) -> Optional[str]:
    # engine.leagues exposes league_registry(), not load_registry — the wrong
    # name meant this branch always raised ImportError and silently fell through
    # to the JSON read below. Harmless (flags still resolved) but it made the
    # fast path dead code.
    try:
        from engine.leagues import league_registry
        for entry in league_registry():
            if getattr(entry, "name", None) == league:
                return getattr(entry, "country", None)
    except Exception:
        pass
    try:
        import json
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "config" / "leagues.json"
        for e in json.loads(p.read_text(encoding="utf-8")).get("leagues", []):
            if e.get("name") == league:
                return e.get("country")
    except Exception:
        pass
    return None


def _flag(league: str) -> str:
    return _FLAGS.get(_country_of(league) or "", "🏆")


def _pct(p: Optional[float]) -> str:
    """Percent, or the honest gap. Never a zero standing in for missing."""
    return "PENDING" if p is None else f"{round(p * 100)}%"


def _league_of(fixture: str) -> str:
    if fixture.endswith(")") and " (" in fixture:
        return fixture.rsplit(" (", 1)[1][:-1]
    return "Unknown"


def _teams(bf) -> tuple[str, str]:
    """Full club names (HR53). Prefers explicit fields over splitting a string."""
    home = getattr(bf, "home_team", None)
    away = getattr(bf, "away_team", None)
    if home and away:
        return home, away
    core = getattr(bf, "fixture", "") or ""
    if core.endswith(")") and " (" in core:
        core = core.rsplit(" (", 1)[0]
    if " v " in core:
        h, a = core.split(" v ", 1)
        return h.strip(), a.strip()
    return core.strip() or "Home", "Away"


def _kickoff(bf) -> Optional[str]:
    """HH:MM, or None.

    Spec §2: "Real confirmed time only. Never ??:?? — a fixture without a
    second-source confirmed kickoff is held off the board." Returning None is
    what enforces that; the caller drops the fixture rather than printing a
    placeholder.
    """
    import re
    for attr in ("kickoff_utc", "kickoff_time"):
        v = getattr(bf, attr, None)
        if not v:
            continue
        m = re.search(r"(?:T|^)(\d{2}:\d{2})", str(v))
        if not m:
            continue
        hhmm = m.group(1)
        # "00:00" is the pipeline's DATE-ONLY PLACEHOLDER, not a real kickoff.
        # Stage A writes T00:00:00 for every fixture whose source gave a date
        # but no time (23 of 23 on 2026-09-17). Rendering that as a kickoff
        # would be worse than the ??:?? the spec bans, because midnight looks
        # like a real time and nothing downstream could tell it was invented.
        # Treated as absent, so the fixture is held off the board (spec §2).
        if hhmm == "00:00":
            continue
        return hhmm
    return None


def _src_stamp(bf) -> str:
    """ID403/ID404 stamp (spec §2)."""
    v = getattr(bf, "verification", None)
    raw = getattr(v, "tier", None)
    # tier is a Tier ENUM. str(Tier.VERIFIED) is "Tier.VERIFIED", NOT "VERIFIED",
    # so comparing str(tier) against "VERIFIED" never matched and every fixture
    # — including all 23 Stage A had verified — stamped ○ SINGLE-SOURCE with a
    # "Verified: 0" header. Read .value, and only fall back to str() for a
    # plain-string tier.
    tier = str(getattr(raw, "value", raw) or "").upper()
    if "CONFLICT" in tier:
        return "⚠ CONFLICT"
    if tier in ("TIER_A", "TIER_B", "VERIFIED"):
        return "✓ VERIFIED"
    if getattr(bf, "verified", None) is True:
        return "✓ VERIFIED"
    return "○ SINGLE-SOURCE"


# ---------------------------------------------------------------------------
# §2 per-fixture block
# ---------------------------------------------------------------------------
def _market_lines(bf) -> list[str]:
    """1X2 / DC / O-U / BTTS — every side printed, always (spec §2)."""
    p = getattr(bf, "probs", None)
    home, away = _teams(bf)
    if p is None:
        return []

    ph, pd, pa = (getattr(p, "p_home", None), getattr(p, "p_draw", None),
                  getattr(p, "p_away", None))

    lines = [f"1X2   {home} {_pct(ph)} · Draw {_pct(pd)} · {away} {_pct(pa)}"]

    # Double chance — all three combinations. Spec §2: "Never only the
    # favourite's DC — that hides the away-side option."
    if None not in (ph, pd, pa):
        lines.append(
            f"DC    {home} or Draw {_pct(ph + pd)} · "
            f"{home} or {away} {_pct(ph + pa)} · "
            f"Draw or {away} {_pct(pd + pa)}"
        )

    # Over/Under — BOTH SIDES ON SEPARATE LINES. Spec §2 calls this out as the
    # permanent fix for BUG5: a 46% Over must never render as "O46" when the
    # honest label is "U54". Under is derived as 1 - Over, never re-modelled.
    o15, o25, o35 = (getattr(p, "p_over_15", None), getattr(p, "p_over_25", None),
                     getattr(p, "p_over_35", None))
    if any(x is not None for x in (o15, o25, o35)):
        lines.append(f"O/U   O1.5 {_pct(o15)} · O2.5 {_pct(o25)} · O3.5 {_pct(o35)}")
        lines.append(
            "      "
            f"U1.5 {_pct(None if o15 is None else 1 - o15)} · "
            f"U2.5 {_pct(None if o25 is None else 1 - o25)} · "
            f"U3.5 {_pct(None if o35 is None else 1 - o35)}"
        )

    byes = getattr(p, "p_btts_yes", None)
    if byes is not None:
        lines.append(f"BTTS  Yes {_pct(byes)} · No {_pct(1 - byes)}")

    return lines


def _ai_pick_lines(bf, odds_index=None) -> list[str]:
    """🤖 AI PICK block (spec §2), including the sub-threshold variant."""
    market = getattr(bf, "best_market", None)
    prob = getattr(bf, "best_model_prob", None)
    price = getattr(bf, "best_price", None)
    edge = getattr(bf, "best_edge", None)

    # best_market is set from the acca builder's CAPITAL leg, which applies a
    # positive-edge gate -- so on a day where every priced market is negative
    # edge it is None for every fixture and the board showed "NO QUALIFYING
    # MARKET" 23 times. That is not what spec §2 asks for: the AI PICK is "the
    # single strongest market by EV for that fixture", and §2's sub-threshold
    # rule explicitly keeps a below-threshold pick ON the board, tagged
    # "SCAN ONLY, not deploy-eligible". Deploy-eligibility is a LABEL here, not
    # a filter. So fall back to the edge-ranked scan across all markets.
    if not market or prob is None:
        try:
            from output.produce_bet import _get_fixture_best_market
            m, p_, px, _bk = _get_fixture_best_market(bf, odds_index)
            if m and m != "NO DATA" and p_ is not None:
                market, prob, price = m, p_, px
                edge = (p_ - (1.0 / px)) if px else None
        except Exception:
            pass

    if not market or prob is None:
        # HR35: no pick is a real answer. It is stated, never filled.
        return ["🤖 AI PICK: NO QUALIFYING MARKET — PENDING",
                f"      Src {_src_stamp(bf)} · Booking code: PENDING"]

    if edge is None and price:
        edge = prob - (1.0 / price)

    out = [f"🤖 AI PICK: {market} — {_pct(prob)}"]

    if edge is None or not price:
        out.append("      EV PENDING — no confirmed price")
    else:
        implied = 1.0 / price
        trigger = 1.0 / prob if prob else None
        detail = (f"      EV {edge * 100:+.1f}% (model {_pct(prob)} vs "
                  f"market {_pct(implied)})")
        if trigger:
            detail += f" · Deploy at {trigger:.2f}+"
        if edge < EV_THRESHOLD:
            detail += f" · below +{EV_THRESHOLD * 100:.1f}% threshold"
        out.append(detail)
        if edge < EV_THRESHOLD:
            out.append("      → SCAN ONLY, not deploy-eligible")

    out.append(f"      Src {_src_stamp(bf)} · Booking code: PENDING")
    return out


def _fixture_block(bf, strict_kickoff: bool = True, odds_index=None) -> Optional[str]:
    """One stacked fixture block, or None if it must be held off the board.

    strict_kickoff=True is the spec (§2): no confirmed time -> held off the
    board entirely. False is a REVIEW-ONLY mode that renders the block with an
    explicit "KICKOFF PENDING" marker so the Architect can see the format while
    the upstream time-fetch gap is still open. It never invents a time, so it
    stays HR35-clean — but it does not satisfy §2 and must not be broadcast.
    """
    ko = _kickoff(bf)
    if ko is None and strict_kickoff:
        return None  # spec §2: never ??:??
    markets = _market_lines(bf)
    if not markets:
        return None  # no model output -> belongs in the NO-DATA footer
    home, away = _teams(bf)
    head = f"{ko}  {home} v {away}" if ko else f"KICKOFF PENDING  {home} v {away}"
    return "\n".join([head, *markets, *_ai_pick_lines(bf, odds_index)])


# ---------------------------------------------------------------------------
# §1 header / §3 no-data / §7 footer
# ---------------------------------------------------------------------------
def _header(board_date: str, run_id: str, n_scanned: int, n_verified: int) -> str:
    try:
        d = datetime.strptime(board_date, "%Y-%m-%d").date()
        date_txt = f"{_WEEKDAYS[d.weekday()]} {d.day:02d} {_MONTHS[d.month - 1]} {d.year}"
    except Exception:
        date_txt = board_date

    try:
        import config
        phase = f"Phase {config.PHASE} — {'LIVE' if config.PHASE >= 3 else 'PAPER'}"
    except Exception:
        phase = "Phase PENDING"

    return "\n".join([
        "##########OLP XDV#########",
        "=" * 34,
        "FULL PIPELINE BOARD — PRODUCTION",
        f"{date_txt} · all markets · AI pick",
        f"Run ID: {run_id} | {phase}",
        f"Fixtures scanned: {n_scanned} · Verified: {n_verified}",
    ])


def _no_data_footer(unresolved: list[str], run_id: str) -> str:
    """Spec §3 — one collapsed line, never per-fixture blocks.

    "If this line is ever renders empty, print nothing." A fixture the pipeline
    failed to fetch is not a fixture that doesn't exist (HR58 zero-silent-drops,
    HR35). Deleting the line would not create data, it would hide that data is
    missing — the condition behind the 3 Sep fabrication incidents.
    """
    if not unresolved:
        return ""
    short = " · ".join(unresolved)
    n = len(unresolved)
    return "\n".join([
        _RULE,
        f"{n} fixture{'s' if n != 1 else ''} unresolved — no market data after 2 retries:",
        f"{short}    (full detail: run log {run_id})",
    ])


# ---------------------------------------------------------------------------
# §4 ACCA ROUTE
# ---------------------------------------------------------------------------
# §4.2 formation constants. The Architect specified 5 legs per acca.
LEGS_PER_ACCA = 5
# §4.3 CONFLICT RESOLVED — Architect ruling 2026-09-17: FOUR accas.
#
# The spec recorded a genuine clash: the Architect's 17 Sep description (16
# picks -> accas of 5 legs; 20+ picks -> more) implied 3-4, while the standing
# rule reaffirmed 14-15 Aug was 2 accas + 1 SLV. HR56 makes both binding until a
# LATER explicit directive resolves them; that directive is the 2026-09-17
# ruling and this is it. Left at 2 until then, and the board printed that it was
# capped, rather than either number being assumed.
#
# Must stay equal to pipeline.production_stage_b.VEHICLE_ACCA_MAX — that is
# where the route is actually truncated. This constant only labels the board.
MAX_ACCAS = 4
MIN_SHORT_ACCA = 3          # §4.2 remainder threshold
ACCA_ODDS_CEILING = 1.50    # §4.1(3) ID420 per-leg ceiling


def _leg_line(i: int, leg) -> str:
    """'1. Lyon v Fenerbahçe — Over 1.5 goals .......... 81% @ 1.24'."""
    fixture = getattr(leg, "fixture", "?")
    if fixture.endswith(")") and " (" in fixture:
        fixture = fixture.rsplit(" (", 1)[0]
    name = getattr(leg, "market_name", "?")
    head = f"{i}. {fixture} — {name} "
    tail = f" {_pct(getattr(leg, 'prob', None))} @ {getattr(leg, 'price', 0.0):.2f}"
    dots = max(1, 52 - len(head) - len(tail))
    return f"{head}{'.' * dots}{tail}"


def _acca_block(acca, rank_from: int, rank_to: int) -> list[str]:
    """One acca with its MANDATORY disclosures (§4.5)."""
    legs = list(getattr(acca, "legs", None) or [])
    lines = [f"▸ {getattr(acca, 'label', 'ACCA')} — {len(legs)} legs · "
             f"EV rank {rank_from}–{rank_to}"]
    lines += [_leg_line(i, lg) for i, lg in enumerate(legs, 1)]

    combined_odds = getattr(acca, "combined_odds", None)
    if combined_odds is None:
        combined_odds = 1.0
        for lg in legs:
            combined_odds *= (getattr(lg, "price", None) or 1.0)

    combined_prob = getattr(acca, "combined_prob", None)
    if combined_prob is None:
        combined_prob = 1.0
        for lg in legs:
            combined_prob *= (getattr(lg, "prob", None) or 0.0)

    # §4.5: combined probability and break-even ALWAYS side by side. A five-leg
    # acca of strong-looking legs reads as high confidence and is not —
    # combined probability is the PRODUCT of the legs, not an average.
    break_even = (1.0 / combined_odds) if combined_odds else None
    # One decimal, matching the spec's own example (25.9% vs 24.9%). Whole
    # percents round these two onto each other — 26% vs 27% cannot show a
    # -1.4pp edge — and this pair exists precisely so the reader can compare
    # them (§4.5).
    _p1 = lambda x: "PENDING" if x is None else f"{x * 100:.1f}%"
    lines.append("   " + _RULE)
    lines.append(f"   Combined odds ............... {combined_odds:.2f}")
    lines.append(f"   Combined model probability ... {_p1(combined_prob)}")
    lines.append(f"   Break-even probability ....... {_p1(break_even)}")
    if break_even is not None:
        edge_pp = (combined_prob - break_even) * 100
        flag = "  ⚠ NEGATIVE" if edge_pp < 0 else ""
        lines.append(f"   Model edge ................... {edge_pp:+.1f}pp{flag}")
    lines.append("   Booking code: PENDING")
    return lines


def render_acca_route(route, n_scanned: int) -> str:
    """§4 ACCA ROUTE. Returns "" when the pool supports no acca at all.

    Rendered from the acca route Stage B already built, so the board and the
    acca cannot disagree about which legs qualified — §6 requires one shared
    board_data with no surface recalculating.
    """
    if route is None:
        return ""

    # Prefer the full list. Reading acca_a/acca_b only would silently cap the
    # BOARD at two however many the route actually carries — the same
    # shape-enforced limit that used to live in _build_acca_route.
    accas = [a for a in (getattr(route, "accas", None) or [])
             if a is not None and (getattr(a, "legs", None) or [])]
    if not accas:
        accas = [a for a in (getattr(route, "acca_a", None), getattr(route, "acca_b", None))
                 if a is not None and (getattr(a, "legs", None) or [])]
    slv = getattr(route, "slv", None)
    watchlist = list(getattr(route, "watchlist", None) or [])

    if not accas and slv is None and not watchlist:
        return ""

    # §4.1(3): a pick enters the ACCA POOL only if its price is at or under the
    # ID420 ceiling. Legs above it are NOT eligible, so they must not be counted
    # in the pool or filed under SURPLUS — surplus means "eligible but beyond
    # MAX_ACCAS", which is a different thing entirely. Today every qualifying
    # pick priced 1.78-7.81, so calling them "4 eligible" would have claimed an
    # acca pool that does not exist.
    def _over_ceiling(lg) -> bool:
        px = getattr(lg, "price", None)
        return px is not None and px > ACCA_ODDS_CEILING

    # A leg already inside a formed acca must not reappear as a single.
    #
    # ProductionAccaRoute.slv is "the single best standalone leg" and is chosen
    # independently of the accas, so it can BE one of their legs. On 2026-09-17
    # it was Acca B's first leg, and the board listed "Real Sociedad v AFC
    # Bournemouth — Under 3.5 goals" twice: once in the acca and again under
    # SURPLUS, reading as two separate bets on one fixture+market. That also
    # contradicts §4.1(5), one leg per fixture.
    in_accas = {(getattr(lg, "fixture", ""), getattr(lg, "market_key", ""))
                for a in accas for lg in (getattr(a, "legs", None) or [])}

    def _already_in_acca(lg) -> bool:
        return (getattr(lg, "fixture", ""), getattr(lg, "market_key", "")) in in_accas

    spare = [lg for lg in (([slv] if slv else []) + watchlist)
             if not _already_in_acca(lg)]
    surplus = [lg for lg in spare if not _over_ceiling(lg)]
    over_ceiling = [lg for lg in spare if _over_ceiling(lg)]

    pool = sum(len(a.legs) for a in accas) + len(surplus)
    formed = " · ".join(
        f"{len(a.legs)} legs" for a in accas) if accas else "none"

    lines = [_RULE, "🎟️ ACCA ROUTE", _RULE,
             f"Eligible pool: {pool} of {n_scanned} scanned"]

    lines.append(
        f"Formed: {len(accas)} acca(s) ({formed})"
        + (f" · Surplus: {len(surplus)} pick(s) → singles" if surplus else "")
    )
    lines.append(f"(MAX_ACCAS = {MAX_ACCAS} — Architect ruling 2026-09-17, spec §4.3 resolved)")
    lines.append("")

    rank = 1
    for acca in accas:
        n = len(acca.legs)
        lines += _acca_block(acca, rank, rank + n - 1)
        lines.append("")
        rank += n

    if surplus:
        lines.append(f"▸ SURPLUS — {len(surplus)} eligible pick(s), "
                     f"beyond acca cap, as singles")
        for lg in surplus:
            lines.append("   " + _leg_line(0, lg)[3:])
        lines.append("   Booking codes: PENDING")
        lines.append("")

    if over_ceiling:
        # ID420 watchlist. Shown, never silently dropped (§4.2 "visible, never
        # discarded"), but kept OUT of the eligible pool and clearly marked
        # not-deployable so it cannot read as a recommendation.
        lines.append(f"▸ ID420 WATCHLIST — {len(over_ceiling)} pick(s) above the "
                     f"{ACCA_ODDS_CEILING:.2f} per-leg ceiling")
        lines.append("   Not acca-eligible and not deployable — shown for review only.")
        for lg in over_ceiling:
            px = getattr(lg, "price", None)
            lines.append("   " + _leg_line(0, lg)[3:]
                         + (f"  ⚠ {px:.2f} > {ACCA_ODDS_CEILING:.2f}" if px else ""))
        lines.append("")

    # §4.5 — the accumulator honesty statement, non-optional.
    lines.append("HONEST EDGE: combined probability is the product of legs, not an")
    lines.append("average. Five legs at ~75% each land 23.7% of the time. Accumulator")
    lines.append("returns are not edge evidence — per the Accumulator Honesty Rule,")
    lines.append("acca outcomes remain quarantined from the calibration log.")
    return "\n".join(lines)


HONEST_EDGE_FOOTER = "\n".join([
    "=" * 34,
    "HONEST EDGE: an excellent informed process, NOT a demonstrated",
    "profitable edge. Capital authority: THE ARCHITECT.",
])


# ---------------------------------------------------------------------------
# §5 chunking
# ---------------------------------------------------------------------------
def _chunk(sections: list[str], limit: int = TELEGRAM_MAX) -> list[str]:
    """Pack whole sections into messages, never splitting one.

    Spec §5: chunk on competition boundaries, never mid-fixture. A section here
    is already a whole competition (or the header/footer), so packing sections
    intact is what enforces that. A single section larger than the limit is
    emitted alone rather than cut — an over-long message is visible and
    recoverable; a fixture sliced in half is neither.
    """
    out: list[str] = []
    cur = ""
    for s in sections:
        if not s:
            continue
        if not cur:
            cur = s
        elif len(cur) + 2 + len(s) <= limit:
            cur = f"{cur}\n\n{s}"
        else:
            out.append(cur)
            cur = s
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def render_production_board(
    board: list,
    board_date: str,
    run_id: str,
    acca_text: str = "",
    strict_kickoff: bool = True,
    odds_index=None,
    acca_route=None,
) -> list[str]:
    """Render the day's board as competition-chunked Telegram messages.

    Returns a LIST of message strings (spec §6), not one blob. An empty list
    means there was nothing publishable — the caller must not invent a board.

    run_id is mandatory (spec §1/HR59); a falsy run_id raises rather than
    rendering an untraceable board.
    """
    if not run_id:
        raise ValueError(
            "run_id is mandatory (spec §1, HR59) — a board without a run_id "
            "cannot be traced to a fetch and must not be rendered"
        )

    today = [bf for bf in board
             if getattr(bf, "kickoff_date", None) in (None, board_date)]

    # Group by competition, preserving registry-free ordering by name.
    groups: dict[str, list] = {}
    unresolved: list[str] = []
    n_verified = 0

    for bf in today:
        block = _fixture_block(bf, strict_kickoff=strict_kickoff, odds_index=odds_index)
        if block is None:
            home, away = _teams(bf)
            unresolved.append(f"{home} v {away}")
            continue
        if _src_stamp(bf) == "✓ VERIFIED":
            n_verified += 1
        groups.setdefault(_league_of(getattr(bf, "fixture", "")), []).append((bf, block))

    if not groups:
        return []

    sections = [_header(board_date, run_id, len(today), n_verified)]

    for league in sorted(groups):
        entries = groups[league]
        # Spec §2: within a competition, sort by AI pick confidence, highest
        # first. None sorts last rather than raising.
        entries.sort(key=lambda e: getattr(e[0], "best_model_prob", None) or -1.0,
                     reverse=True)
        body = "\n\n".join(block for _, block in entries)
        sections.append("\n".join([
            _RULE, f"{_flag(league)} {league.upper()}", _RULE, "", body,
        ]))

    # §4 — rendered from Stage B's own acca route so the board and the acca
    # cannot disagree about which legs qualified (§6: one shared board_data,
    # no surface recalculates). An explicit acca_text still wins if given.
    if not acca_text and acca_route is not None:
        acca_text = render_acca_route(acca_route, len(today))
    if acca_text:
        sections.append(acca_text)

    nd = _no_data_footer(unresolved, run_id)
    if nd:
        sections.append(nd)

    sections.append(HONEST_EDGE_FOOTER)
    return _chunk(sections)
