"""render_v2.py — the web page IS the Telegram board (Architect 2026-08-11;
Verge "Match Intelligence" skin, ratified 2026-08-12).

One render, two outlets: the daily run's production builds the Telegram
message, and THAT same output (telegram_<date>.txt + the raw board JSON) feeds
this page. The page is the Telegram board — same PRODUCTION BETS block (Acca A
headline, split accas, singles, each with its SportyBet booking code), same
lean scan, yesterday-graded, 7-day rolling, and the honest-edge line. An
honest NO DATA — PENDING renders wherever a pick or code is genuinely missing
(HR35) — nothing is fabricated.

Page structure (the "Match Intelligence" editorial board):
  masthead (wordmark / centerline / dateline) → sticky tab nav
    (CALL / SCAN / SINGLES) → hero (honest-edge kicker + CTAs + chips + flags
    + gate) → Part 1 THE CALL (Lean / Trimmed / Full densities) → Part 2 THE
    SCAN (date pills + table) → Part 3 SINGLES (three densities) →
    YESTERDAY — GRADED → 7-DAY ROLLING → footer (honest edge / capital).

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
"""
from __future__ import annotations

import html
import math
from datetime import date as _date, datetime, timedelta as _timedelta

from webapp.render import (
    _league_of,
    _pick,
    _short_fixture,
    _teams,
)


def _asset_version() -> str:
    """Cache-buster for the two proto assets. A version query on the <link> and
    <script> tags means a browser can NEVER serve a stale proto.js/proto.css
    from its cache. Any edit to either asset bumps the mtime and therefore the
    query, so a normal refresh re-fetches. Falls back to '1' if the assets
    can't be stat'd."""
    from pathlib import Path as _P
    mtimes = []
    for f in (_P(__file__).parent / "static" / "css" / "proto.css",
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
<meta name="theme-color" content="#131313" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F5F6F8" media="(prefers-color-scheme: light)">
<link rel="manifest" href="{base}/manifest.json">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{base}/css/proto.css?v={v}">
</head><body>
{body}
<div class="toast" id="toast"></div>
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


def _feed_code_line(code: str | None) -> str:
    """Booking-code line: the real SportyBet code + a copy button, or an honest
    NO DATA — PENDING (HR35: never fabricate a code). Copy binds via proto.js."""
    if code:
        return (f'<div class="f-code"><span>Booking code:</span>'
                f'<button type="button" class="f-code-pill" '
                f'data-code="{html.escape(code)}"><b>{html.escape(code)}</b> '
                f'Copy</button></div>')
    return ('<div class="f-code"><span>Booking code:</span>'
            '<span class="pnd">NO DATA — PENDING</span></div>')


# ─────────────────────────────────────────────────────────────────────────────
# FEED — the single scrolling Telegram-board page (Verge skin)
# ─────────────────────────────────────────────────────────────────────────────
def _override_extra(gs: dict) -> str:
    """The honest override sentence — stated plainly, never silent."""
    return (" Architect sign-off is active — publishing live side-by-side "
            "with paper until mean CLV turns positive (override never silent)."
            if gs.get("override", False) else "")


def _masthead(payload: dict) -> str:
    d = payload.get("date", _date.today().isoformat())
    return (f'<header class="f-masthead">'
            f'<div class="f-wordmark"><span class="f-mark" aria-hidden="true"></span>'
            f'<span class="f-name">OLP XDV</span></div>'
            f'<span class="f-centerline">Match Intelligence</span>'
            f'<span class="f-dateline">{html.escape(_friendly_date(d))}</span>'
            f'</header>')


def _tabnav() -> str:
    return ('<nav class="f-tabnav" aria-label="Sections">'
            '<a class="f-tabpill active" href="#call" data-spy="call">CALL</a>'
            '<a class="f-tabpill" href="#scan" data-spy="scan">SCAN</a>'
            '<a class="f-tabpill" href="#singles" data-spy="singles">SINGLES</a>'
            '</nav>')


def _hero(payload: dict) -> str:
    """Hero — honest-edge kicker, the two CTAs, phase/league/calibration chips,
    data flags, and the always-visible gate callout."""
    phase = payload.get("phase", "")
    leagues = payload.get("leagues_scanned") or []
    cal = payload.get("calibration_count", 0)
    leagues_txt = f"{len(leagues)} leagues" if leagues else "no leagues"
    chips = "".join(
        f'<span class="f-chip">{html.escape(t)}</span>'
        for t in (phase, leagues_txt, f"{cal} legs logged") if t)
    gs = payload.get("gate_state") or {}
    sub = ("An excellent informed process but NOT a demonstrated profitable "
           "edge." + _override_extra(gs))
    return (f'<header class="f-hero">'
            f'<p class="f-hero-sub">{html.escape(sub)}</p>'
            f'<div class="f-hero-cta">'
            f'<a class="f-btn f-btn-primary" href="#call">View today\'s call</a>'
            f'<a class="f-btn f-btn-ghost" href="#singles">Standalone singles</a>'
            f'</div>'
            f'<div class="f-chips">{chips}</div>'
            f'{_feed_flags(payload)}'
            f'{_feed_gate_callout(payload)}'
            f'</header>')


def _feed_flags(payload: dict) -> str:
    """Data flags — the honest ⚠ line, absent when clean."""
    flags = payload.get("data_flags") or []
    if not flags:
        return ""
    chips = "".join(f'<span class="f-flag">{html.escape(f)}</span>' for f in flags)
    return f'<div class="f-flags"><span class="f-flag-head">⚠ {len(flags)} data flag(s)</span>{chips}</div>'


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
    return (f'<div class="f-gate {cls}"><span class="f-gate-status">{status}</span>'
            f'<span class="f-gate-detail">{html.escape(detail)}</span></div>')


def _density_bar(group: str) -> str:
    """The Lean / Trimmed / Full switcher. CSP-clean buttons (data-* hooks;
    proto.js binds the click). Trimmed is the default active density."""
    return (f'<div class="f-densitybar" data-group="{html.escape(group)}" '
            f'role="tablist" aria-label="Density views">'
            f'<button type="button" class="f-density-pill" data-for="lean">Lean</button>'
            f'<button type="button" class="f-density-pill active" data-for="trimmed">Trimmed</button>'
            f'<button type="button" class="f-density-pill" data-for="full">Full</button>'
            f'</div>')


def _feed_leg_rows(legs: list) -> str:
    """Leg row — byte-faithful to the Telegram production block:
    `fixture (league) — market @ price` (the — is part of the parity anchor)."""
    return "".join(
        f'<div class="f-leg"><span class="f-leg-name">{html.escape(l.get("fixture", ""))} '
        f'({html.escape(l.get("league", ""))}) —</span>'
        f'<span class="f-leg-mkt">{html.escape(l.get("market_name", ""))} @ '
        f'{_price2(l.get("price"))}</span></div>'
        for l in legs)


def _feed_acca_ticket(acca: dict, code: str | None, hero: bool = False) -> str:
    """A Telegram-faithful ticket. Acca A is the amber hero band (★ Acca A —
    HEADLINE, N legs); splits keep the ★ label  N legs form. Both carry the
    byte-faithful leg rows + `Combined X.XX` + booking code (HR35 honest
    NO DATA — PENDING when a code is missing)."""
    legs = acca.get("legs") or []
    n_legs = acca.get("n_legs", len(legs))
    combined = acca.get("combined_odds")
    comb = f"Combined {combined:.2f}" if combined is not None else "Combined —"
    cls = "f-ticket f-ticket-hero" if hero else "f-ticket"
    label = acca.get("label", "Acca A")
    head = (f"★ {html.escape(label)} — HEADLINE, {n_legs} legs"
            if hero else f"★ {html.escape(label)}  {n_legs} legs")
    return (f'<div class="{cls}">'
            f'<div class="f-ticket-head">{head}</div>'
            f'{_feed_leg_rows(legs)}'
            f'<div class="f-ticket-foot"><span class="f-combined">{comb}</span>'
            f'{_feed_code_line(code)}</div>'
            f'</div>')


# ─────────────────────────────────────────────────────────────────────────────
# Call cards (Trimmed / Full) — MODEL % dial, market bars, breakeven strip
# ─────────────────────────────────────────────────────────────────────────────
_DIAL_R = 18
_DIAL_C = round(2 * math.pi * _DIAL_R, 1)


def _dial(prob) -> str:
    """SVG probability dial. The fill's final offset is inline (no-JS shows the
    filled dial); proto.js re-animates from empty on view activation."""
    if prob is None:
        return (f'<div class="f-dial" data-prob="0">'
                f'<svg viewBox="0 0 44 44" aria-hidden="true">'
                f'<circle class="f-dial-track" cx="22" cy="22" r="{_DIAL_R}"></circle>'
                f'<circle class="f-dial-fill" cx="22" cy="22" r="{_DIAL_R}" '
                f'stroke-dasharray="{_DIAL_C}" stroke-dashoffset="{_DIAL_C}"></circle></svg>'
                f'<span class="f-dial-txt">—</span></div>')
    p = max(0.0, min(1.0, prob))
    off = round(_DIAL_C * (1 - p), 1)
    return (f'<div class="f-dial" data-prob="{p:.2f}">'
            f'<svg viewBox="0 0 44 44" aria-hidden="true">'
            f'<circle class="f-dial-track" cx="22" cy="22" r="{_DIAL_R}"></circle>'
            f'<circle class="f-dial-fill" cx="22" cy="22" r="{_DIAL_R}" '
            f'stroke-dasharray="{_DIAL_C}" stroke-dashoffset="{off}"></circle></svg>'
            f'<span class="f-dial-txt">{round(p * 100)}%</span></div>')


def _mkt_line(fam: str, p, hl: bool = False) -> str:
    pct = round(p * 100)
    cls = " f-mkt-line strong" if hl else ""
    return (f'<div class="f-mkt-line{cls}"><span class="f-mkt-fam">{fam}</span>'
            f'<span class="f-mkt-track"><span class="f-mkt-fill" '
            f'style="width:{pct}%" data-value="{pct}"></span></span>'
            f'<span class="f-mkt-pct">{pct}%</span></div>')


def _market_bars(probs: dict) -> str:
    """All-market bars from the feed-safe probs (1X2 lean highlighted)."""
    if not probs:
        return ""
    lines = []
    ph, pd, pa = probs.get("p_home"), probs.get("p_draw"), probs.get("p_away")
    if None not in (ph, pd, pa):
        mx = max(ph, pd, pa)
        lines.append(_mkt_line("HOME", ph, hl=(ph == mx)))
        lines.append(_mkt_line("DRAW", pd, hl=(pd == mx)))
        lines.append(_mkt_line("AWAY", pa, hl=(pa == mx)))
    if probs.get("p_over_25") is not None:
        lines.append(_mkt_line("O2.5", probs["p_over_25"]))
    if probs.get("p_btts_yes") is not None:
        lines.append(_mkt_line("BTTS YES", probs["p_btts_yes"]))
    return f'<div class="f-mkt-block">{"".join(lines)}</div>' if lines else ""


def _edge_strip(prob, price) -> str:
    """Breakeven strip — MODEL % against 1/price. Honest: this is the model's
    read vs the price-implied line (1/price), NOT EV and NOT a live quote."""
    if prob is None or price is None or price <= 0:
        return ""
    p = max(0.0, min(1.0, prob))
    break_pct = round(100 / price, 1)
    model_pct = round(p * 100)
    fill_w = max(0, min(100, model_pct))
    marker_l = max(0.0, min(100.0, break_pct))
    above = " above" if p > 1 / price else ""
    return (f'<div class="f-edge-block">'
            f'<span class="f-edge-cap">MODEL vs BREAKEVEN · 1/{_price2(price)}</span>'
            f'<div class="f-edge-track">'
            f'<span class="f-edge-fill{above}" style="width:{fill_w}%" '
            f'data-value="{fill_w}"></span>'
            f'<span class="f-edge-marker" style="left:{marker_l}%"></span></div>'
            f'<div class="f-edge-line"><span class="f-edge-note">model {model_pct}%</span>'
            f'<span class="f-edge-note">breakeven {break_pct}%</span></div></div>')


def _call_card(leg: dict, code: str | None, bf: dict | None) -> str:
    """A call card (Trimmed density). Fields: league kicker, Anton fixture,
    market @ price (mono), the MODEL % dial + DEPLOY breakeven hint, all-market
    bars, the breakeven strip, and the acca's booking code. `bf` is the matching
    feed-safe board fixture (best_model_prob / mes_trigger_price / probs) when
    the fixture was rated — missing fields render honest —, never fabricated."""
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
    deploy_hint = (f'<span class="f-call-hint">DEPLOY @ {deploy:.2f} — model '
                   f'breakeven, not a live quote</span>' if deploy is not None else "")
    return (f'<div class="f-call-card">'
            f'<span class="f-call-league">{html.escape(league_label)}</span>'
            f'<span class="f-call-fixture">{html.escape(_short_fixture(fix))}</span>'
            f'<span class="f-call-market">{html.escape(market)} @ {_price2(price)}</span>'
            f'<div class="f-call-dial-row">{_dial(prob)}'
            f'<div class="f-call-data"><span class="f-call-model">MODEL {_pct_of(prob)}</span>'
            f'{deploy_hint}</div></div>'
            f'{_market_bars(probs)}'
            f'{_edge_strip(prob, price)}'
            f'{_feed_code_line(code)}'
            f'</div>')


def _call_cards(payload: dict, accas_real: list, codes_by_label: dict,
                dense: bool = False) -> str:
    """Call cards for the production accas — one per leg (Trimmed), or the same
    fields in a denser grid (Full = a denser grid of the SAME fields)."""
    board_by_fixture = {bf.get("fixture"): bf for bf in payload.get("board", [])}
    cards = []
    for acca in accas_real:
        code = codes_by_label.get(acca.get("label"))
        for leg in acca.get("legs") or []:
            cards.append(_call_card(leg, code, board_by_fixture.get(leg.get("fixture"))))
    grid = "f-call-grid dense" if dense else "f-call-grid"
    return f'<div class="{grid}">{"".join(cards)}</div>' if cards \
        else '<div class="f-dim">No call cards today.</div>'


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
    acca_a = next((a for a in accas_real if a.get("label") == "Acca A"), None)
    splits = [a for a in accas_real if a is not acca_a]

    head = ('<div class="f-sec-head"><span class="f-eyebrow">Part 1</span>'
            '<h2 class="f-title">The Call</h2>'
            '<p class="f-desc">Production accas — the same board Telegram reads, '
            'three densities.</p></div>')
    prod_head = (f'<div class="f-prod-head">PRODUCTION BETS — {html.escape(d)}'
                 f'<span class="f-prod-sub">today\'s fixtures only</span></div>')

    if not accas_real and not singles:
        return (f'<section class="f-section" id="call">{head}{prod_head}'
                '<div class="f-card f-prod-empty">NO production pick today — no '
                'deploy-eligible fixture with a live price kicks off today. A '
                'valid, honest result (HR35).</div></section>')
    lean = prod_head + "".join(
        [(_feed_acca_ticket(acca_a, codes_by_label.get(acca_a.get("label")), hero=True)
          if acca_a else "")]
        + [_feed_acca_ticket(a, codes_by_label.get(a.get("label")))
           for a in splits])
    if not lean.strip():
        lean = '<div class="f-dim">No call accas today.</div>'
    trimmed = _call_cards(payload, accas_real, codes_by_label, dense=False)
    full = _call_cards(payload, accas_real, codes_by_label, dense=True)

    return (f'<section class="f-section" id="call">{head}'
            f'{_density_bar("call")}'
            f'<div class="f-density-view" data-view="lean">{lean}</div>'
            f'<div class="f-density-view active" data-view="trimmed">{trimmed}</div>'
            f'<div class="f-density-view" data-view="full">{full}</div>'
            f'</section>')


def _one_two_cell(ph, pd, pa) -> str:
    if None in (ph, pd, pa):
        return '<span class="pnd">—</span>'
    mx = max(ph, pd, pa)
    parts = []
    for name, v in (("H", ph), ("D", pd), ("A", pa)):
        t = f"{round(v * 100)}"
        parts.append(f"{name} <b>{t}</b>" if v == mx else f"{name} {t}")
    return " · ".join(parts)


def _pct_cell(v) -> str:
    return "—" if v is None else f"{round(v * 100)}%"


def _scan_row(bf: dict, scores: dict) -> str:
    """A scan table row — fixture + league + live badge, the 1X2/totals/BTTS
    cells, and the honest pick cell. data-fixture is the live-score hook."""
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
            if score else '<span class="f-live"></span>')
    probs = bf.get("probs") or {}
    ph, pd, pa = probs.get("p_home"), probs.get("p_draw"), probs.get("p_away")
    pick_label, pick_prob = _pick(bf)
    return (f'<tr class="f-scan-row" data-fixture="{html.escape(key)}">'
            f'<td class="f-fx"><span class="f-fx-name">{html.escape(fixture_txt)}</span>'
            f'<span class="f-fx-league">{html.escape(lg)}</span>{live}</td>'
            f'<td class="f-cell">{_one_two_cell(ph, pd, pa)}</td>'
            f'<td class="f-cell">{_pct_cell(probs.get("p_over_15"))}</td>'
            f'<td class="f-cell">{_pct_cell(probs.get("p_over_25"))}</td>'
            f'<td class="f-cell">{_pct_cell(probs.get("p_over_35"))}</td>'
            f'<td class="f-cell">{_pct_cell(probs.get("p_btts_yes"))}</td>'
            f'<td class="f-cell pick"><span class="f-pick-lbl">{html.escape(pick_label)}</span> '
            f'<b>{html.escape(pick_prob)}</b></td></tr>')


def _feed_scan(payload: dict, scores: dict, pill_base: str) -> str:
    """Part 2 — THE SCAN: date pills + the league-grouped table with live-score
    badges and honest NO DATA — PENDING rows (the other session's lean board
    commit carried the same simplification: AI-pick cards, no internals)."""
    board = payload.get("board", [])
    d = payload.get("date", _date.today().isoformat())
    today = _date.today().isoformat()

    pills = []
    for off in (-1, 0, 1, 2):
        dt = _date.fromisoformat(d) + _timedelta(days=off)
        iso = dt.isoformat()
        cls = ["f-pill"]
        if iso == d:
            cls.append("selected")
        if off == 0:
            cls.append("today")
        sub = iso[5:]
        label = _friendly_day(iso, today)
        pills.append(f'<a class="{" ".join(cls)}" href="{_pill_href(pill_base, iso)}">'
                     f"{label}<span class='f-pill-sub'>{sub}</span></a>")
    datepills = f'<div class="f-datepills">{"".join(pills)}</div>'

    rated = [bf for bf in board if bf.get("probs")]
    unrated = [bf for bf in board if not bf.get("probs")]
    groups: dict[str, list] = {}
    for bf in rated:
        groups.setdefault(_league_of(bf.get("fixture", "")), []).append(bf)

    rows = []
    for league, bfs in sorted(groups.items()):
        rows.append(f'<tr class="f-league-sep"><td colspan="7">'
                    f'<span>{html.escape(league)} ({len(bfs)})</span></td></tr>')
        for bf in bfs:
            rows.append(_scan_row(bf, scores))
    if unrated:
        rows.append(f'<tr class="f-league-sep"><td colspan="7"><span>'
                    f'NO DATA — PENDING ({len(unrated)})</span></td></tr>')
        for bf in unrated:
            fix = _short_fixture(bf.get("fixture", ""))
            lg = _league_of(bf.get("fixture", ""))
            rows.append(
                f'<tr class="f-scan-row pending"><td class="f-fx">'
                f'<span class="f-fx-name">{html.escape(fix)}</span>'
                f'<span class="f-fx-league">{html.escape(lg)}</span></td>'
                f'<td class="f-cell pick" colspan="6">'
                f'<span class="pnd">NO DATA — PENDING</span></td></tr>')

    if not rows:
        return datepills + ('<div class="f-card"><div class="f-sec-title">THE SCAN</div>'
                            '<div class="f-dim">No fixtures on this board.</div></div>')

    table = (f'<div class="f-scan-wrap"><table class="f-scan">'
             f'<thead><tr><th>Fixture</th><th>1X2</th><th>O1.5</th>'
             f'<th>O2.5</th><th>O3.5</th><th>BTTS</th><th>Pick</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    return datepills + table


def _scan_section(payload: dict, scores: dict, pill_base: str) -> str:
    return (f'<section class="f-section" id="scan">'
            f'<div class="f-sec-head"><span class="f-eyebrow">Part 2</span>'
            f'<h2 class="f-title">The Scan</h2>'
            f'<p class="f-desc">Every fixture scanned — 1X2, totals, BTTS, and '
            f'the honest pick.</p></div>'
            f'{_feed_scan(payload, scores, pill_base)}</section>')


def _singles_lean(singles: list, codes_by_label: dict) -> str:
    """The byte-faithful singles list (parity anchor: fixture (league) — market
    @ price  Booking code)."""
    rows = []
    for s in singles:
        label = (s.get("label") or "").replace("SINGLE — ", "")
        leg0 = (s.get("legs") or [{}])[0]
        lg = leg0.get("league", "")
        fix = leg0.get("fixture") or label
        fix_txt = fix if (not lg or fix.endswith(f" ({lg})")) else f"{fix} ({lg})"
        rows.append(
            f'<div class="f-single">'
            f'<div class="f-leg"><span class="f-leg-name">{html.escape(fix_txt)} —</span>'
            f'<span class="f-leg-mkt">{html.escape(leg0.get("market_name", ""))} @ '
            f'{_price2(leg0.get("price"))}</span></div>'
            f'{_feed_code_line(codes_by_label.get(s.get("label")))}'
            f'</div>')
    return ('<div class="f-card"><div class="f-singles-title">'
            'SINGLES — one standalone slip each, own booking code</div>'
            + "".join(rows) + '</div>')


def _single_cards(payload: dict, singles: list, codes_by_label: dict,
                  dense: bool = False) -> str:
    """Singles as cards (Trimmed / Full) — same card grammar as the call cards,
    one standalone slip each, own booking code."""
    board_by_fixture = {bf.get("fixture"): bf for bf in payload.get("board", [])}
    cards = []
    for s in singles:
        label = (s.get("label") or "").replace("SINGLE — ", "")
        leg0 = (s.get("legs") or [{}])[0]
        bf = board_by_fixture.get(leg0.get("fixture")) \
            or board_by_fixture.get(label)
        cards.append(_call_card(leg0, codes_by_label.get(s.get("label")), bf))
    grid = "f-singles-grid dense" if dense else "f-singles-grid"
    return f'<div class="{grid}">{"".join(cards)}</div>' if cards \
        else '<div class="f-dim">No standalone singles today.</div>'


def _singles_section(payload: dict, codes_by_label: dict) -> str:
    """Part 3 — SINGLES: standalone slips, one booking code each, at three
    densities. Honest empty state when there are none today."""
    accas = payload.get("accas") or []
    singles = [a for a in accas if (a.get("label") or "").startswith("SINGLE — ")]
    head = ('<div class="f-sec-head"><span class="f-eyebrow">Part 3</span>'
            '<h2 class="f-title">Singles</h2>'
            '<p class="f-desc">Standalone slips — one booking code each.</p></div>')
    if not singles:
        return (f'<section class="f-section" id="singles">{head}'
                '<div class="f-card"><div class="f-sec-title">SINGLES</div>'
                '<div class="f-dim">No standalone singles today.</div></div></section>')
    lean = _singles_lean(singles, codes_by_label)
    trimmed = _single_cards(payload, singles, codes_by_label, dense=False)
    full = _single_cards(payload, singles, codes_by_label, dense=True)
    return (f'<section class="f-section" id="singles">{head}'
            f'{_density_bar("singles")}'
            f'<div class="f-density-view" data-view="lean">{lean}</div>'
            f'<div class="f-density-view active" data-view="trimmed">{trimmed}</div>'
            f'<div class="f-density-view" data-view="full">{full}</div>'
            f'</section>')


def _feed_yesterday(payload: dict) -> str:
    """Yesterday — graded: fixture, outcome and per-engine ✓/✗ (the Telegram
    block, carried through the feed-safe yesterday_graded)."""
    yg = payload.get("yesterday_graded")
    if not yg:
        return ('<div class="f-card"><div class="f-sec-title">YESTERDAY — GRADED</div>'
                '<div class="f-dim">No settled predictions to grade yet.</div></div>')
    rows = []
    for g in yg:
        marks = []
        for eng, hit in (g.get("engines_hit") or {}).items():
            marks.append(f'<span class="f-mark {"hit" if hit else "miss"}">'
                         f'{html.escape(eng)} {"✓" if hit else "✗"}</span>')
        marks_txt = "".join(marks) if marks \
            else '<span class="f-dim">no engine pick recorded</span>'
        rows.append(
            f'<div class="f-yday-row"><span class="f-yday-fix">'
            f'{html.escape(g.get("fixture", ""))} — '
            f'{html.escape(g.get("outcome", "?"))}</span>'
            f'<span class="f-yday-marks">{marks_txt}</span></div>')
    return ('<div class="f-card"><div class="f-sec-title">YESTERDAY — GRADED</div>'
            + "".join(rows) + '</div>')


def _feed_rolling(payload: dict) -> str:
    """7-day rolling — per-engine hit rates plus the honest legs/CLV/gate line
    (the Telegram bar, through the feed-safe rolling_7d)."""
    r7 = payload.get("rolling_7d")
    if not r7:
        return ('<div class="f-card"><div class="f-sec-title">7-DAY ROLLING</div>'
                '<div class="f-dim">No run history yet.</div></div>')
    engines = r7.get("engines") or {}
    rates = []
    for eng in ("dc", "cross", "elo", "xg", "bookmaker"):
        st = engines.get(eng)
        if st and st.get("hit_rate") is not None:
            rates.append(f'<span class="f-rate"><b>{html.escape(eng)}</b> '
                         f'{round(st["hit_rate"] * 100)}%</span>')
    rates_txt = "".join(rates) if rates \
        else '<span class="f-dim">no settled predictions in 7d</span>'
    legs = r7.get("legs_logged", 0)
    with_clv = r7.get("legs_with_clv", 0)
    avg = r7.get("avg_clv_pct")
    clv_txt = f'avg CLV {avg:+.2f}%' if avg is not None else "CLV: ZERO"
    gate = r7.get("gate") or {}
    gate_txt = (f' · gate {gate.get("legs_with_clv", 0)}/'
                f'{gate.get("gate_requirement", 30)} legs') if gate else ""
    return (f'<div class="f-card"><div class="f-sec-title">7-DAY ROLLING</div>'
            f'<div class="f-rates">{rates_txt}</div>'
            f'<div class="f-roll-line">{legs} legs logged · {with_clv} with CLV '
            f'({html.escape(clv_txt)}){html.escape(gate_txt)}</div></div>')


def _feed_honest_edge(payload: dict) -> str:
    """The honest-edge/capital line — carried from the Telegram envelope.
    An active override is stated plainly (never silent)."""
    gs = payload.get("gate_state") or {}
    extra = _override_extra(gs)
    return (
        f'<div class="f-honest">'
        f'<span class="f-honest-title">HONEST EDGE LINE</span>'
        f'<span class="f-honest-body">An excellent informed process but NOT a '
        f'demonstrated profitable edge.{html.escape(extra)}</span>'
        f'<span class="f-honest-cap">Capital authority: THE ARCHITECT. '
        f'Nothing here is live until you deploy it.</span></div>')


def _footer(payload: dict) -> str:
    return (f'<footer class="f-footer">'
            f'{_feed_honest_edge(payload)}'
            f'<div class="f-foot-bottom">'
            f'<span>OLP XDV — Match Intelligence</span>'
            f'<span>One render, two outlets</span>'
            f'</div></footer>')


def render_dashboard(payload: dict, asset_base: str = "/static",
                     booking_codes=None, scores=None,
                     pill_base: str = "/dashboard") -> str:
    """The single-scroll feed page — structurally the Telegram board."""
    codes_by_label = _codes_by_label(booking_codes)
    body = f"""<div class="f-page">
  {_masthead(payload)}
  {_tabnav()}
  {_hero(payload)}
  <main class="f-main">
    {_call_section(payload, codes_by_label)}
    {_scan_section(payload, scores or {}, pill_base)}
    {_singles_section(payload, codes_by_label)}
    <section class="f-section" id="yesterday">{_feed_yesterday(payload)}</section>
    <section class="f-section" id="rolling">{_feed_rolling(payload)}</section>
  </main>
  {_footer(payload)}
</div>"""
    return _shell("OLP XDV — Today's Board", body, asset_base)
