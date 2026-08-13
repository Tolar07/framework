"""render_v2.py — the web page IS the Telegram board (Architect 2026-08-11;
pitch-night editorial skin, ratified 2026-08-12 — supersedes the Verge pass).

One render, two outlets: the daily run's production builds the Telegram
message, and THAT same output (telegram_<date>.txt + the raw board JSON) feeds
this page. The page is the Telegram board — same PRODUCTION BETS block (Acca A
headline, split accas, singles, each with its SportyBet booking code), same
lean scan, yesterday-graded, 7-day rolling, and the honest-edge line. An
honest NO DATA — PENDING renders wherever a pick or code is genuinely missing
(HR35) — nothing is fabricated.

Page structure (the "pitch-night editorial" board — mockup grammar at
docs/design-reference/pitch_night_mockup.html):
  masthead (wordmark / dateline pill / centerline) → sticky tab nav
    (CALL / SCAN / SINGLES) → hero (honest-edge kicker + CTAs + chips + flags
    + gate callout) → Part 1 THE CALL (Lean tickets / Trimmed + Full call
    cards at three densities) → Part 2 THE SCAN (date pills + league-grouped
    table) → Part 3 SINGLES (three densities) → YESTERDAY — GRADED →
    7-DAY ROLLING → footer (honest edge / capital).

  render_dashboard(payload, booking_codes=None, scores=None, pill_base=...)
      — the single-scroll feed page. Fed by schema.build_feed_payload (a widened
        trim: elo/xg/consensus/EV/verification never leave the server). The
        gate_state callout (PASS / OVERRIDE / NOT MET) is always visible and an
        ARCHITECT_SIGNOFF override is stated plainly, never silent.

Interaction is CSP-clean: NO inline handlers anywhere. Every copyable booking
code carries a data-* hook and static/js/proto.js binds them via
addEventListener (script-src 'self'). Codes are read server-side from the
day's acca_<date>_codes.json (schema.read_booking_codes) — they recall a
betslip in SportyBet; they are never a stake (Phase-2 bright line).

Feed-boundary rules (hard): never emit best_price / best_mes_ev / verification
/ elo / xg / consensus vectors / engine-names-as-data / EV / source-tier to
the page — only the public fields schema.build_feed_payload hands us. No
Google Fonts <link> (self-hosted woff2 under /static/fonts). No inline
<script> or onclick= anywhere.
"""
from __future__ import annotations

import html
import math
from datetime import date as _date, datetime, timedelta as _timedelta

from webapp.render import (
    _league_of,
    _short_fixture,
    _teams,
)


def _prov_tag(bf: dict | None) -> str:
    """Provenance tag for a NON-fitted rating (bookable, labeled per Architect
    2026-08-12): a ClubElo stretch or carry-over rating is real, but it must
    never be mistaken for a primary-window fitted one. Empty for a fitted
    fixture — only ratings that need labeling carry the tag. (`rating_source`
    is stripped by the feed trim today, so this renders empty until the trim
    carries it — the label pattern stays ready, never fabricated.)"""
    rs = (bf or {}).get("rating_source")
    if rs == "clubelo":
        return ('<span class="call-prov" title="Rated on the keyless ClubElo '
                'current-season snapshot — not a fitted model">ClubElo</span>')
    if rs == "carry":
        return ('<span class="call-prov" title="Rated on the previous-season '
                'carry-over fit (promoted club) — not a primary fit">Carry</span>')
    return ""


def _asset_version() -> str:
    """Cache-buster for the three proto assets (proto.css, motion.js, proto.js).
    A version query on the <link> and <script> tags means a browser can NEVER
    serve a stale asset from its cache. Any edit to any asset bumps the mtime
    and therefore the query, so a normal refresh re-fetches. Falls back to '1'
    if the assets can't be stat'd."""
    from pathlib import Path as _P
    mtimes = []
    for f in (_P(__file__).parent / "static" / "css" / "proto.css",
              _P(__file__).parent / "static" / "js" / "motion.js",
              _P(__file__).parent / "static" / "js" / "proto.js"):
        try:
            if f.exists():
                mtimes.append(int(f.stat().st_mtime))
        except OSError:
            continue
    return str(max(mtimes)) if mtimes else "1"


def _shell(title: str, body: str, asset_base: str = "/static") -> str:
    base = html.escape(asset_base, quote=True)
    v = _asset_version()
    return f"""<!doctype html>
<html lang="en" data-asset-base="{base}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#0e1a16" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F5F6F8" media="(prefers-color-scheme: light)">
<link rel="manifest" href="{base}/manifest.json">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{base}/css/proto.css?v={v}">
</head><body>
{body}
<div class="toast" id="toast"></div>
<script src="{base}/js/motion.js?v={v}"></script>
<script src="{base}/js/proto.js?v={v}" defer></script>
</body></html>"""


def _friendly_date(d: str) -> str:
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(d)
    day = dt.strftime("%d").lstrip("0") or "0"
    return f"{dt.strftime('%a')}, {day} {dt.strftime('%b %Y')}"


def _friendly_day(d: str, today: str) -> str:
    """Pill label: Today / Tomorrow / weekday — for the scan date pills."""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        t = _date.fromisoformat(today)
    except (TypeError, ValueError):
        return d[5:]
    if dt == t:
        return "Today"
    if dt == t + _timedelta(days=1):
        return "Tomorrow"
    return dt.strftime("%a")


def _pill_href(pill_base: str, iso: str) -> str:
    """Date-pill href. A route base ('/dashboard') links to the served route;
    a relative base ('.' at the site root, '..' on a per-date page) links to a
    per-date page of the static export — explicit index.html so file:// and
    every static host resolve it."""
    if pill_base.startswith("/"):
        return f"{pill_base}/{iso}"
    return f"{pill_base}/{iso}/index.html"


# ─────────────────────────────────────────────────────────────────────────────
# Booking codes (from schema.read_booking_codes) — label → code
# ─────────────────────────────────────────────────────────────────────────────
def _codes_by_label(codes) -> dict:
    out = {}
    for r in (codes or {}).get("results") or []:
        if r.get("label") and r.get("code"):
            out[r["label"]] = r["code"]
    return out


def _price2(x) -> str:
    """Price as the Telegram board writes it — '1.91', never a fabricated
    quote (HR35: None renders NO DATA — PENDING)."""
    return "—" if x is None else f"{x:.2f}"


def _pct_of(x) -> str:
    return "—" if x is None else f"{round(x * 100)}%"


def _override_extra(gs: dict) -> str:
    """The honest override sentence — stated plainly, never silent."""
    return (" Architect sign-off is active — publishing live side-by-side "
            "with paper until mean CLV turns positive (override never silent)."
            if gs.get("override", False) else "")


# ─────────────────────────────────────────────────────────────────────────────
# Masthead / tabnav / hero / gate
# ─────────────────────────────────────────────────────────────────────────────
def _masthead(payload: dict) -> str:
    d = payload.get("date", _date.today().isoformat())
    return (f'<header class="masthead"><div class="wrap">'
            f'<div class="masthead-row">'
            f'<div class="intro" style="animation-delay:0s">'
            f'<div class="wordmark">OLP<span>·</span>XDV</div></div>'
            f'</div>'
            f'<div class="centerline"></div></div></header>')


def _tabnav() -> str:
    return ('<nav class="tabnav"><div class="wrap"><div class="tabnav-row">'
            '<button type="button" class="pill on" data-scroll-target="the-call">Call</button>'
            '<button type="button" class="pill" data-scroll-target="the-scan">Scan</button>'
            '<button type="button" class="pill" data-scroll-target="the-singles">Singles</button>'
            '</div></div></nav>')


def _hero(payload: dict) -> str:
    """Hero — honest-edge kicker + the two CTAs (mockup layout: no chips, no
    data flags, no gate callout in the hero — the gate rides as a strip at the
    top of THE CALL section so it stays always visible without breaking the
    mockup's hero grammar)."""
    sub = ("An excellent informed process. Not, on its own, a demonstrated "
           "profitable edge — the board says so before it says anything else. "
           "Every number here is auditable Dixon-Coles, not a black box, and "
           "every source is graded before it's trusted.")
    return (f'<section class="hero" id="top">'
            f'<div class="sweep" aria-hidden="true"></div>'
            f'<div class="wrap">'
            f'<p class="hero-sub intro" style="animation-delay:.08s">{html.escape(sub)}</p>'
            f'<div class="hero-cta intro" style="animation-delay:.16s">'
            f'<button type="button" class="btn btn-primary" data-scroll-target="the-call">View the Call</button>'
            f'<button type="button" class="btn btn-ghost" data-scroll-target="the-scan">View the full Scan</button>'
            f'</div>'
            f'</div></section>')


def _feed_flags(payload: dict) -> str:
    """Data flags — the honest ⚠ line, absent when clean."""
    flags = payload.get("data_flags") or []
    if not flags:
        return ""
    chips = "".join(f'<span class="flag">{html.escape(f)}</span>' for f in flags)
    return f'<div class="data-flags"><span class="flag-head">⚠ {len(flags)} data flag(s)</span>{chips}</div>'


def _feed_gate_callout(payload: dict) -> str:
    """The publish-gate callout — PASS / OVERRIDE / NOT MET, always visible.
    An Architect override is stated plainly, never silent."""
    gs = payload.get("gate_state") or {}
    legs = gs.get("legs_with_clv", 0)
    req = gs.get("gate_requirement", 30)
    mean = gs.get("mean_clv_pct")
    gate_met = gs.get("gate_met", False)
    override = gs.get("override", False)
    if gate_met:
        status, cls = "PASS", "pass"
    elif override:
        status, cls = "OVERRIDE", "override"
    else:
        status, cls = "NOT MET", "notmet"
    detail = (f"{legs}/{req} legs with CLV · mean CLV {mean:+.2f}%"
              if mean is not None else f"{legs}/{req} legs with CLV · mean CLV ZERO")
    if override:
        detail += " · Architect sign-off active — live side-by-side with paper until mean CLV turns positive"
    return (f'<div class="gate-callout {cls}"><span class="gate-status">{status}</span>'
            f'<span class="gate-detail">{html.escape(detail)}</span></div>')


def _density_bar() -> str:
    """The Lean / Trimmed / Full switcher. CSP-clean buttons (data-* hooks;
    proto.js binds the click). Trimmed is the default active density."""
    return (f'<div class="densitybar">'
            f'<span class="densitybar-label">Board density</span>'
            f'<div class="density-pills">'
            f'<button type="button" class="density-pill" data-density="lean">Lean</button>'
            f'<button type="button" class="density-pill on" data-density="trimmed">Trimmed</button>'
            f'<button type="button" class="density-pill" data-density="full">Full</button>'
            f'</div></div>')


# ─────────────────────────────────────────────────────────────────────────────
# THE CALL — byte-faithful Lean tickets, then Trimmed/Full call cards
# ─────────────────────────────────────────────────────────────────────────────
def _ticket_leg(l: dict) -> str:
    """Leg row — byte-faithful to the Telegram production block:
    `fixture (league) — market @ price` (the — is part of the parity anchor).
    Layout matches the mockup: leg-fixture (with inline .leg-league span) +
    .leg-market + .leg-price as three flex children."""
    fix = l.get("fixture", "")
    lg = l.get("league", "")
    if lg and not fix.endswith(f" ({lg})"):
        fixture_html = (f"{html.escape(fix)} "
                        f'<span class="leg-league">({html.escape(lg)})</span> —')
    else:
        fixture_html = f"{html.escape(fix)} —"
    return (f'<div class="ticket-leg">'
            f'<span class="leg-fixture">{fixture_html}</span>'
            f'<span class="leg-market">{html.escape(l.get("market_name", ""))} @</span>'
            f'<span class="leg-price">{_price2(l.get("price"))}</span></div>')


def _ticket_foot(combined, code: str | None) -> str:
    """`Combined X.XX` + `Booking code: <code>` — the parity foot. A missing
    code is an honest NO DATA — PENDING (HR35), never a fabricated one."""
    comb = f"Combined {combined:.2f}" if combined is not None else "Combined —"
    if code:
        code_html = (f'<button type="button" class="code-value-t copy-pill" '
                     f'data-code="{html.escape(code)}">{html.escape(code)} Copy</button>')
    else:
        code_html = '<span class="code-value-t pending">NO DATA — PENDING</span>'
    return (f'<div class="ticket-foot">'
            f'<div><span class="combined-price">{comb}</span></div>'
            f'<div><span class="code-label-t">Booking code:</span>{code_html}</div>'
            f'</div>')


def _acca_ticket(acca: dict, code: str | None, hero: bool = False) -> str:
    """A Telegram-faithful ticket. Acca A is the amber hero band (★ Acca A —
    HEADLINE, N legs); splits keep the ★ label  N legs form. Both carry the
    byte-faithful leg rows + `Combined X.XX` + booking code."""
    legs = acca.get("legs") or []
    n_legs = acca.get("n_legs", len(legs))
    combined = acca.get("combined_odds")
    cls = "ticket ticket-hero" if hero else "ticket"
    label = acca.get("label", "Acca A")
    title = (f"★ {html.escape(label)} — HEADLINE, {n_legs} legs"
             if hero else f"★ {html.escape(label)}  {n_legs} legs")
    return (f'<div class="{cls}">'
            f'<div class="ticket-head">'
            f'<span class="ticket-title">{title}</span>'
            f'<span class="ticket-legs-count">{n_legs} legs</span></div>'
            f'<div class="ticket-legs">{"".join(_ticket_leg(l) for l in legs)}</div>'
            f'{_ticket_foot(combined, code)}'
            f'</div>')


def _single_line(s: dict, codes_by_label: dict) -> str:
    """A lean single line — parity anchor:
    `fixture (league) — market @ price Booking code: <code>`. Mockup grammar:
    .sl-fixture + .sl-market + .sl-price + .sl-code (the fixed test asserts the
    combined `fixture (league) — market @ price` substring, so the — and @ are
    kept as separators between the three spans)."""
    label = (s.get("label") or "").replace("SINGLE — ", "")
    leg0 = (s.get("legs") or [{}])[0]
    lg = leg0.get("league", "")
    fix = leg0.get("fixture") or label
    if lg and not fix.endswith(f" ({lg})"):
        fix_txt = (f"{html.escape(fix)} "
                   f'<span class="leg-league">({html.escape(lg)})</span> —')
    else:
        fix_txt = f"{html.escape(fix)} —"
    code = codes_by_label.get(s.get("label"))
    if code:
        code_html = (f'<span class="sl-code">'
                     f'<span class="code-label-t">Booking code:</span>'
                     f'<button type="button" class="copy-pill" data-code="{html.escape(code)}">'
                     f'{html.escape(code)} Copy</button></span>')
    else:
        code_html = '<span class="sl-code pending">NO DATA — PENDING</span>'
    return (f'<div class="single-line">'
            f'<span class="sl-fixture">{fix_txt}</span>'
            f'<span class="sl-market">{html.escape(leg0.get("market_name", ""))} @</span>'
            f'<span class="sl-price">{_price2(leg0.get("price"))}</span>'
            f'{code_html}</div>')


def _call_lean(accas_real: list, singles: list, codes_by_label: dict) -> str:
    """Lean density: the acca tickets (Acca A hero band first) + the singles
    block — the byte-faithful Telegram production block."""
    parts = []
    for a in accas_real:
        is_hero = a.get("label") == "Acca A"
        parts.append(_acca_ticket(a, codes_by_label.get(a.get("label")), hero=is_hero))
    if singles:
        sl = "".join(_single_line(s, codes_by_label) for s in singles)
        parts.append(
            f'<div class="ticket-singles">'
            f'<div class="ticket-singles-label">SINGLES — one standalone slip each, own booking code</div>'
            f'{sl}</div>')
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Call cards (Trimmed / Full) — MODEL % dial, market bars, breakeven strip
# ─────────────────────────────────────────────────────────────────────────────
def _dial(prob, size: int = 72, r: int = 30, txt_y: int = 33,
          stroke: int = 5, cls: str = "dial") -> str:
    """SVG probability dial. The fill's final offset is inline (no-JS shows the
    filled dial); proto.js setupDials/fillDials re-animates from empty on view
    activation. data-value/data-radius are the JS hooks."""
    cx = size / 2
    c = round(2 * math.pi * r, 3)
    if prob is None:
        off, txt, val = c, "—", 0
    else:
        p = max(0.0, min(1.0, prob))
        off = round(c * (1 - p), 3)
        txt = f"{round(p * 100)}%"
        val = round(p * 100)
    return (f'<svg class="{cls}" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" data-value="{val}" data-radius="{r}">'
            f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="#26392f" '
            f'stroke-width="{stroke}"></circle>'
            f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="#e8a33d" '
            f'stroke-width="{stroke}" stroke-linecap="round" class="dial-fill" '
            f'transform="rotate(-90 {cx} {cx})" '
            f'style="stroke-dasharray:{c};stroke-dashoffset:{off}"></circle>'
            f'<text x="{cx}" y="{txt_y}" text-anchor="middle">{txt}</text></svg>')


def _mkt_bar(name: str, p: float, fav: bool = False) -> str:
    pct = max(0, min(100, round(p * 100)))
    cls = " fav" if fav else ""
    return (f'<div class="mkt-bar{cls}"><span class="mkt-bar-name">{html.escape(name)}</span>'
            f'<div class="mkt-bar-track"><div class="mkt-bar-fill" data-value="{pct}"></div></div>'
            f'<span class="mkt-bar-pct">{pct}%</span></div>')


def _market_bars(probs: dict) -> str:
    """All-market bars from the feed-safe probs: 1X2, O/U 1.5, O/U 2.5, BTTS,
    and the derived Double-chance — the family the mockup calls "All markets"."""
    if not probs:
        return ""
    out = []
    ph, pd, pa = probs.get("p_home"), probs.get("p_draw"), probs.get("p_away")
    if None not in (ph, pd, pa):
        mx = max(ph, pd, pa)
        out.append(
            f'<div class="mkt-fam"><div class="mkt-fam-label">1X2</div>'
            f'{_mkt_bar("Home", ph, ph == mx)}{_mkt_bar("Draw", pd, pd == mx)}'
            f'{_mkt_bar("Away", pa, pa == mx)}</div>')
    o15 = probs.get("p_over_15")
    if o15 is not None:
        over, under = o15, 1 - o15
        out.append(
            f'<div class="mkt-fam"><div class="mkt-fam-label">O/U 1.5</div>'
            f'{_mkt_bar("Over", over, over >= under)}{_mkt_bar("Under", under, under > over)}</div>')
    o25 = probs.get("p_over_25")
    if o25 is not None:
        over, under = o25, 1 - o25
        out.append(
            f'<div class="mkt-fam"><div class="mkt-fam-label">O/U 2.5</div>'
            f'{_mkt_bar("Over", over, over >= under)}{_mkt_bar("Under", under, under > over)}</div>')
    btts = probs.get("p_btts_yes")
    if btts is not None:
        yes, no = btts, 1 - btts
        out.append(
            f'<div class="mkt-fam"><div class="mkt-fam-label">BTTS</div>'
            f'{_mkt_bar("Yes", yes, yes >= no)}{_mkt_bar("No", no, no > yes)}</div>')
    if None not in (ph, pd, pa):
        vals = ((ph + pd, "1X"), (ph + pa, "12"), (pd + pa, "X2"))
        mxv = max(v for v, _ in vals)
        out.append(
            f'<div class="mkt-fam"><div class="mkt-fam-label">Double chance</div>'
            + "".join(f'{_mkt_bar(name, v, v == mxv)}' for v, name in vals)
            + '</div>')
    return f'<div class="mkt-block"><div class="mkt-block-label">All markets</div>{"".join(out)}</div>'


def _edge_strip(prob, deploy) -> str:
    """Breakeven strip — MODEL % against 100/deploy (the price-implied
    breakeven, the same basis as the DEPLOY hint). Honest: this is the model's
    read vs the breakeven, NOT EV and NOT a live quote."""
    if prob is None or deploy is None or deploy <= 0:
        return ""
    p = max(0.0, min(1.0, prob))
    break_pct = round(100 / deploy, 1)
    model_pct = round(p * 100)
    marker_l = max(0.0, min(100.0, break_pct))
    model_l = max(0.0, min(100.0, model_pct))
    return (f'<div class="edge-block">'
            f'<div class="edge-caption"><span class="model">Model {model_pct}%</span>'
            f'<span class="break">Breakeven {break_pct}%</span></div>'
            f'<div class="edge-track">'
            f'<div class="edge-fill" data-value="{model_pct}"></div>'
            f'<div class="edge-break" style="left:{break_pct}%"></div>'
            f'<div class="edge-marker" style="left:{model_l}%"></div></div>'
            f'<div class="edge-note">Deploy at {deploy:.2f}+ — breakeven, not a live '
            f'quote. Deploy at this price or better.</div></div>')


def _code_row(code: str | None) -> str:
    """Booking-code line on a call card: the real SportyBet code, or an honest
    No data — pending (HR35). Structure matches pitch-night mockup grammar."""
    if code:
        return (f'<div class="code-row">'
                f'<span class="code-label">Booking code</span>'
                f'<span class="code-value">{html.escape(code)}</span></div>')
    return ('<div class="code-row pending">'
            '<span class="code-label">Booking code</span>'
            '<span class="code-value">No data — pending</span></div>')


def _call_card(leg: dict, code: str | None, bf: dict | None, dense: bool = False) -> str:
    """A call card (Trimmed density). Fields: league kicker, Fraunces fixture,
    market @ price, the MODEL % dial + DEPLOY breakeven hint, all-market bars,
    the breakeven strip, and the acca's booking code. `bf` is the matching
    feed-safe board fixture (best_model_prob / mes_trigger_price / probs) when
    the fixture was rated — missing fields render honest, never fabricated."""
    fixture = leg.get("fixture", "")
    lg = leg.get("league", "")
    fix = fixture if (not lg or fixture.endswith(f" ({lg})")) else f"{fixture} ({lg})"
    market = leg.get("market_name", "")
    price = leg.get("price")
    prob = leg.get("prob")
    if prob is None and bf is not None:
        prob = bf.get("best_model_prob")
    deploy = (bf or {}).get("mes_trigger_price")
    probs = (bf or {}).get("probs") or {}
    league_label = lg or _league_of(fixture)
    prov = _prov_tag(bf)
    reveal = "" if dense else " reveal"
    deploy_html = (f'<br>DEPLOY <b>@{deploy:.2f}+</b>'
                   if deploy is not None else "")
    note = ""
    if deploy is not None:
        note = (f'<p class="call-note">Deploy at {deploy:.2f}+ — breakeven, not a '
                f'live quote. Deploy at this price or better.</p>')
    model_pct = _pct_of(prob)
    return (f'<article class="call-card{reveal}">'
            f'<div class="call-league">{html.escape(league_label)}</div>{prov}'
            f'<h3 class="call-fixture">{html.escape(_short_fixture(fix))}</h3>'
            f'<div class="call-market">{html.escape(market)} @ {_price2(price)}</div>'
            f'<div class="call-dial-row">{_dial(prob)}'
            f'<div class="call-data">MODEL <b>{model_pct}</b>{deploy_html}</div></div>'
            f'{note}'
            f'{_market_bars(probs)}'
            f'{_edge_strip(prob, deploy)}'
            f'{_code_row(code)}'
            f'</article>')


def _call_cards(payload: dict, accas_real: list, codes_by_label: dict,
                dense: bool = False) -> str:
    """Call cards for the production accas — one per leg (Trimmed), or the same
    fields in a denser grid (Full = a denser grid of the SAME fields)."""
    board_by_fixture = {bf.get("fixture"): bf for bf in payload.get("board", [])}
    cards = []
    for acca in accas_real:
        code = codes_by_label.get(acca.get("label"))
        for leg in acca.get("legs") or []:
            fix = leg.get("fixture")
            lg = leg.get("league")
            # Board keys include league suffix; acca legs may omit it — reconstruct
            board_fix = f"{fix} ({lg})" if lg and f"{fix} ({lg})" in board_by_fixture else fix
            cards.append(_call_card(leg, code, board_by_fixture.get(board_fix),
                                    dense=dense))
    grid = "call-grid dense" if dense else "call-grid"
    return f'<div class="{grid}">{"".join(cards)}</div>' if cards \
        else '<div class="density-note">No call cards today.</div>'


# ─────────────────────────────────────────────────────────────────────────────
# THE CALL / THE SCAN / SINGLES sections
# ─────────────────────────────────────────────────────────────────────────────
def _call_section(payload: dict, codes_by_label: dict) -> str:
    """Part 1 — THE CALL. Lean = the byte-faithful production tickets; Trimmed
    and Full = call cards at two densities. Honest empty state when the day has
    no deploy-eligible pick (HR35)."""
    d = payload.get("date", _date.today().isoformat())
    accas = payload.get("accas") or []
    accas_real = [a for a in accas
                  if not (a.get("label") or "").startswith("SINGLE — ")]
    singles = [a for a in accas if (a.get("label") or "").startswith("SINGLE — ")]

    head = ('<div class="section-eyebrow">Part 1</div>'
            '<h2 class="section-title">The Call</h2>'
            '<p class="section-desc">The deploy shortlist. Every market is shown, '
            'not just the pick — nothing here needs a click to reveal.</p>')
    prod_head = (f'<div class="prod-head">PRODUCTION BETS — {html.escape(d)}'
                 f'<span class="prod-sub">today\'s fixtures only</span></div>')

    if not accas_real and not singles:
        return (f'<section class="section" id="the-call"><div class="wrap">{head}'
                f'{prod_head}'
                f'{_feed_gate_callout(payload)}'
                '<div class="density-note">NO production pick today — no '
                'deploy-eligible fixture with a live price kicks off today. A '
                'valid, honest result (HR35).</div></div></section>')

    lean = _call_lean(accas_real, singles, codes_by_label)
    trimmed = _call_cards(payload, accas_real, codes_by_label, dense=False)
    full = _call_cards(payload, accas_real, codes_by_label, dense=True)

    return (f'<section class="section" id="the-call"><div class="wrap">{head}'
            f'{prod_head}'
            f'{_feed_gate_callout(payload)}'
            f'{_density_bar()}'
            f'<div class="density-note">Lean mirrors the Telegram production '
            f'ticket. Trimmed and Full show the same public fields — the full '
            f'market family, the model\'s breakeven, and the booking code. No '
            f'EV, no source tier on the public board.</div>'
            f'<div class="density-view" data-group="call" data-for="lean">{lean}</div>'
            f'<div class="density-view active" data-group="call" data-for="trimmed">{trimmed}</div>'
            f'<div class="density-view" data-group="call" data-for="full">{full}</div>'
            f'</div></section>')


def _one_two_cell(ph, pd, pa) -> str:
    if None in (ph, pd, pa):
        return '<span class="pending">—</span>'
    mx = max(ph, pd, pa)
    side = "1" if mx == ph else ("X" if mx == pd else "2")
    return f"{side} · {round(mx * 100)}%"


def _totals_cell(o15, o25) -> str:
    if o15 is None and o25 is None:
        return '<span class="pending">—</span>'
    a = f"O{round(o15 * 100)}" if o15 is not None else "—"
    b = f"O{round(o25 * 100)}" if o25 is not None else "—"
    return f"{a} / {b}"


def _btts_cell(p) -> str:
    if p is None:
        return '<span class="pending">—</span>'
    pct = round(p * 100)
    if pct >= 50:
        return f'Y {pct}%'
    return f'N {100 - pct}%'


def _btts_cls(p) -> str:
    if p is None:
        return ""
    return "yes" if p >= 0.5 else "no"


def _scan_row(bf: dict, scores: dict) -> str:
    """A scan table row — fixture + league (+ provenance tag), the 1X2/totals/
    BTTS cells and the live-score badge. data-fixture is the live-score hook."""
    home, away, lg = _teams(bf)
    fixture_txt = f"{home} v {away}" if home and away and away != "—" \
        else _short_fixture(bf.get("fixture", ""))
    key = f"{home}|{away}" if home and away and away != "—" \
        else _short_fixture(bf.get("fixture", ""))
    score = ""
    for k, v in (scores or {}).items():
        if k.startswith(key + "|"):
            score = v
            break
    live = (f'<span class="f-live">{html.escape(score)}</span>'
            if score else '<span class="f-live">—</span>')
    probs = bf.get("probs") or {}
    ph, pd, pa = probs.get("p_home"), probs.get("p_draw"), probs.get("p_away")
    prov = _prov_tag(bf)
    return (f'<tr class="f-scan-row" data-fixture="{html.escape(key)}">'
            f'<td><span class="fx-name">{html.escape(fixture_txt)}</span>'
            f'{prov}<span class="fx-league">{html.escape(lg)}</span></td>'
            f'<td>{_one_two_cell(ph, pd, pa)}</td>'
            f'<td>{_totals_cell(probs.get("p_over_15"), probs.get("p_over_25"))}</td>'
            f'<td class="{_btts_cls(probs.get("p_btts_yes"))}">{_btts_cell(probs.get("p_btts_yes"))}</td>'
            f'<td>{live}</td></tr>')


def _feed_scan(payload: dict, scores: dict, pill_base: str) -> str:
    """Part 2 — THE SCAN: date pills + the league-grouped table with live-score
    badges and honest NO DATA — PENDING rows (HR35)."""
    board = payload.get("board", [])
    d = payload.get("date", _date.today().isoformat())
    today = _date.today().isoformat()

    pills = []
    for off in (-1, 0, 1, 2):
        dt = _date.fromisoformat(d) + _timedelta(days=off)
        iso = dt.isoformat()
        cls = ["date-pill"]
        if iso == d:
            cls.append("selected")
        if off == 0:
            cls.append("today")
        sub = iso[5:]
        label = _friendly_day(iso, today)
        pills.append(f'<a class="{" ".join(cls)}" href="{_pill_href(pill_base, iso)}">'
                     f"{label}<span class='date-pill-sub'>{sub}</span></a>")
    datepills = f'<div class="datepills">{"".join(pills)}</div>'

    rated = [bf for bf in board if bf.get("probs")]
    unrated = [bf for bf in board if not bf.get("probs")]
    groups: dict[str, list] = {}
    for bf in rated:
        groups.setdefault(_league_of(bf.get("fixture", "")), []).append(bf)

    rows = []
    for league, bfs in sorted(groups.items()):
        rows.append(f'<tr class="scan-league"><td colspan="5">'
                    f'<span>{html.escape(league)} ({len(bfs)})</span></td></tr>')
        for bf in bfs:
            rows.append(_scan_row(bf, scores))
    if unrated:
        rows.append(f'<tr class="scan-league"><td colspan="5"><span>'
                    f'NO DATA — PENDING ({len(unrated)})</span></td></tr>')
        for bf in unrated:
            fix = _short_fixture(bf.get("fixture", ""))
            lg = _league_of(bf.get("fixture", ""))
            rows.append(
                f'<tr class="f-scan-row pending"><td>'
                f'<span class="fx-name">{html.escape(fix)}</span>'
                f'<span class="fx-league">{html.escape(lg)}</span></td>'
                f'<td class="pending" colspan="4">NO DATA — PENDING</td></tr>')

    if not rows:
        return datepills + '<div class="density-note">No fixtures on this board.</div>'

    table = (f'<div class="scan-table-wrap"><table class="scan">'
             f'<thead><tr><th>Fixture</th><th>1X2</th><th>O1.5 / O2.5</th>'
             f'<th>BTTS</th><th>Live</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    return datepills + table


def _scan_section(payload: dict, scores: dict, pill_base: str) -> str:
    return (f'<section class="section" id="the-scan">'
            f'<div class="wrap">'
            f'<div class="section-eyebrow">Part 2</div>'
            f'<h2 class="section-title">The Scan</h2>'
            f'<p class="section-desc">Every fixture, every approved league, '
            f'every market — scored whether or not it deploys.</p>'
            f'{_feed_scan(payload, scores, pill_base)}</div></section>')


def _single_card(leg0: dict, code: str | None, bf: dict | None,
                 dense: bool = False) -> str:
    """A singles card (Trimmed/Full) — the mockup grammar: league kicker,
    fixture, the small MODEL dial, market @ price and the DEPLOY breakeven."""
    lg = leg0.get("league", "")
    fix = leg0.get("fixture", "")
    market = leg0.get("market_name", "")
    price = leg0.get("price")
    prob = leg0.get("prob")
    if prob is None and bf is not None:
        prob = bf.get("best_model_prob")
    deploy = (bf or {}).get("mes_trigger_price")
    league_label = lg or _league_of(fix)
    reveal = "" if dense else " reveal"
    deploy_html = (f'<br>DEPLOY <b>@{deploy:.2f}+</b>' if deploy is not None else "")
    return (f'<div class="single-card{reveal}">'
            f'<div class="single-league">{html.escape(league_label)}</div>'
            f'<div class="single-fixture">{html.escape(_short_fixture(fix))}</div>'
            f'<div class="single-dial-row">{_dial(prob, size=48, r=19, txt_y=28, stroke=4, cls="single-dial")}'
            f'<div class="single-data"><span class="mkt">{html.escape(market)} @ '
            f'{_price2(price)}</span>{deploy_html}</div></div>'
            f'</div>')


def _single_cards(payload: dict, singles: list, codes_by_label: dict,
                  dense: bool = False) -> str:
    """Singles as cards (Trimmed / Full) — same card grammar as the call cards,
    one standalone slip each."""
    board_by_fixture = {bf.get("fixture"): bf for bf in payload.get("board", [])}
    cards = []
    for s in singles:
        label = (s.get("label") or "").replace("SINGLE — ", "")
        leg0 = (s.get("legs") or [{}])[0]
        bf = board_by_fixture.get(leg0.get("fixture")) \
            or board_by_fixture.get(label)
        cards.append(_single_card(leg0, codes_by_label.get(s.get("label")), bf,
                                  dense=dense))
    grid = "singles-grid dense" if dense else "singles-grid"
    return f'<div class="{grid}">{"".join(cards)}</div>' if cards \
        else '<div class="density-note">No standalone singles today.</div>'


def _singles_section(payload: dict, codes_by_label: dict) -> str:
    """Part 3 — SINGLES: standalone slips at three densities. Honest empty
    state when there are none today."""
    accas = payload.get("accas") or []
    singles = [a for a in accas if (a.get("label") or "").startswith("SINGLE — ")]
    head = ('<div class="section-eyebrow">Part 3</div>'
            '<h2 class="section-title">Singles</h2>'
            '<p class="section-desc">One market, one line, no accumulator risk '
            '— for legs the board rates highly enough to stand alone.</p>')
    if not singles:
        return (f'<section class="section" id="the-singles">{head}'
                '<div class="wrap"><div class="density-note">No standalone '
                'singles today.</div></div></section>')
    lean = "".join(_single_line(s, codes_by_label) for s in singles)
    trimmed = _single_cards(payload, singles, codes_by_label, dense=False)
    full = _single_cards(payload, singles, codes_by_label, dense=True)
    return (f'<section class="section" id="the-singles"><div class="wrap">{head}'
            f'{_density_bar()}'
            f'<div class="density-view" data-group="singles" data-for="lean">{lean}</div>'
            f'<div class="density-view active" data-group="singles" data-for="trimmed">{trimmed}</div>'
            f'<div class="density-view" data-group="singles" data-for="full">{full}</div>'
            f'</div></section>')


# ─────────────────────────────────────────────────────────────────────────────
# Yesterday / rolling / footer
# ─────────────────────────────────────────────────────────────────────────────
def _feed_yesterday(payload: dict) -> str:
    """Yesterday — graded: fixture, outcome and per-engine ✓/✗ (the Telegram
    block, carried through the feed-safe yesterday_graded)."""
    yg = payload.get("yesterday_graded")
    if not yg:
        return ('<div class="grade-card"><div class="grade-title">YESTERDAY — GRADED</div>'
                '<div class="grade-note">No settled predictions to grade yet.</div></div>')
    rows = []
    for g in yg:
        marks = []
        for eng, hit in (g.get("engines_hit") or {}).items():
            marks.append(f'<span class="mark {"hit" if hit else "miss"}">'
                         f'{html.escape(eng)} {"✓" if hit else "✗"}</span>')
        marks_txt = "".join(marks) if marks \
            else '<span class="grade-note">no engine pick recorded</span>'
        rows.append(
            f'<div class="yday-row"><span class="yday-fix">'
            f'{html.escape(g.get("fixture", ""))} — '
            f'{html.escape(g.get("outcome", "?"))}</span>'
            f'<span class="yday-marks">{marks_txt}</span></div>')
    return ('<div class="grade-card"><div class="grade-title">YESTERDAY — GRADED</div>'
            + "".join(rows) + '</div>')


def _feed_rolling(payload: dict) -> str:
    """7-day rolling — per-engine hit rates plus the honest legs/CLV/gate line
    (the Telegram bar, through the feed-safe rolling_7d)."""
    r7 = payload.get("rolling_7d")
    if not r7:
        return ('<div class="roll-card"><div class="roll-title">7-DAY ROLLING</div>'
                '<div class="grade-note">No run history yet.</div></div>')
    engines = r7.get("engines") or {}
    rates = []
    for eng in ("dc", "cross", "elo", "xg", "bookmaker"):
        st = engines.get(eng)
        if st and st.get("hit_rate") is not None:
            rates.append(f'<span class="rate"><b>{html.escape(eng)}</b> '
                         f'{round(st["hit_rate"] * 100)}%</span>')
    rates_txt = "".join(rates) if rates \
        else '<span class="grade-note">no settled predictions in 7d</span>'
    legs = r7.get("legs_logged", 0)
    with_clv = r7.get("legs_with_clv", 0)
    avg = r7.get("avg_clv_pct")
    clv_txt = f'avg CLV {avg:+.2f}%' if avg is not None else "CLV: ZERO"
    gate = r7.get("gate") or {}
    gate_txt = (f' · gate {gate.get("legs_with_clv", 0)}/'
                f'{gate.get("gate_requirement", 30)} legs') if gate else ""
    return (f'<div class="roll-card"><div class="roll-title">7-DAY ROLLING</div>'
            f'<div class="rates">{rates_txt}</div>'
            f'<div class="roll-line">{legs} legs logged · {with_clv} with CLV '
            f'({html.escape(clv_txt)}){html.escape(gate_txt)}</div></div>')


def _feed_honest_edge(payload: dict) -> str:
    """The honest-edge/capital line — carried from the Telegram envelope.
    An active override is stated plainly (never silent)."""
    gs = payload.get("gate_state") or {}
    extra = _override_extra(gs)
    return (
        f'<div class="honest-edge">'
        f'<span class="honest-title">HONEST EDGE LINE</span>'
        f'<span class="honest-body">An excellent informed process but NOT a '
        f'demonstrated profitable edge.{html.escape(extra)}</span>'
        f'<span class="honest-cap">Capital authority: THE ARCHITECT. '
        f'Nothing here is live until you deploy it.</span></div>')


def _footer(payload: dict) -> str:
    return (f'<footer><div class="wrap">'
            f'{_feed_honest_edge(payload)}'
            f'<p class="foot-note">All capital deployment decisions rest solely '
            f'with the Architect. This board is read-only intelligence — never '
            f'a place to place a bet from. The honest edge stands: the framework '
            f'never fabricates a pick, a price, or a closing line, and every '
            f'missing number reads NO DATA — PENDING until it is real.</p>'
            f'<div class="foot-bottom">'
            f'<span>OLP·XDV — Match Intelligence</span>'
            f'<span>One render, two outlets</span>'
            f'</div></div></footer>')


def render_dashboard(payload: dict, asset_base: str = "/static",
                     booking_codes=None, scores=None,
                     pill_base: str = "/dashboard") -> str:
    """The single-scroll feed page — structurally the Telegram board."""
    codes_by_label = _codes_by_label(booking_codes)
    body = f"""{_masthead(payload)}
{_tabnav()}
{_hero(payload)}
<main>
  {_call_section(payload, codes_by_label)}
  {_scan_section(payload, scores or {}, pill_base)}
  {_singles_section(payload, codes_by_label)}
  <section class="section" id="yesterday"><div class="wrap">{_feed_yesterday(payload)}</div></section>
  <section class="section" id="rolling"><div class="wrap">{_feed_rolling(payload)}</div></section>
</main>
{_footer(payload)}"""
    return _shell("OLP XDV — Today's Board", body, asset_base)
