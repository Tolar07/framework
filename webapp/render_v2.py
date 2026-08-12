"""render_v2.py — the web page IS the Telegram board (Architect 2026-08-11).

One render, two outlets: the daily run's production builds the Telegram
message, and THAT same output (telegram_<date>.txt + the raw board JSON) feeds
this page. The page is the Telegram board — same lean PRODUCTION BETS block
(Acca A headline, split accas, singles, each with its SportyBet booking code),
same lean scan, yesterday-graded, 7-day rolling, and the honest-edge line. An
honest NO DATA — PENDING renders wherever a pick or code is genuinely missing
(HR35) — nothing is fabricated.

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
<meta name="theme-color" content="#0b0e11" media="(prefers-color-scheme: dark)">
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
# FEED — the single scrolling Telegram-board page
# ─────────────────────────────────────────────────────────────────────────────
def _feed_hero(payload: dict) -> str:
    """Date / phase / leagues / calibration stat header."""
    d = payload.get("date", _date.today().isoformat())
    phase = payload.get("phase", "")
    leagues = payload.get("leagues_scanned") or []
    cal = payload.get("calibration_count", 0)
    leagues_txt = f"{len(leagues)} leagues" if leagues else "no leagues"
    return (
        f'<header class="f-hero">'
        f'<div class="f-brand"><span class="mark"></span><h1>OLP XDV</h1></div>'
        f'<div class="f-date">{html.escape(_friendly_date(d))}</div>'
        f'<div class="f-chips">'
        f'<span class="f-chip">{html.escape(phase)}</span>'
        f'<span class="f-chip">{html.escape(leagues_txt)}</span>'
        f'<span class="f-chip">{cal} legs logged</span>'
        f'</div></header>')


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


def _feed_leg_rows(legs: list) -> str:
    """Leg row — byte-faithful to the Telegram production block:
    `fixture (league) — market @ price` (the — is part of the parity anchor)."""
    return "".join(
        f'<div class="f-leg"><span class="f-leg-name">{html.escape(l.get("fixture", ""))} '
        f'({html.escape(l.get("league", ""))}) —</span>'
        f'<span class="f-leg-mkt">{html.escape(l.get("market_name", ""))} @ '
        f'{_price2(l.get("price"))}</span></div>'
        for l in legs)


def _feed_acca_hero(acca: dict, code: str | None) -> str:
    """Acca A — the amber hero band (the Telegram headline, byte-faithful:
    ★ Acca A — HEADLINE, N legs; each leg fixture (league) — market @ price;
    Combined X.XX · Booking code: CODE)."""
    legs = acca.get("legs") or []
    n_legs = acca.get("n_legs", len(legs))
    combined = acca.get("combined_odds")
    comb = f"Combined {combined:.2f}" if combined is not None else "Combined —"
    return (
        f'<div class="f-card f-acca f-acca-hero">'
        f'<div class="f-acca-title">★ {html.escape(acca.get("label", "Acca A"))} '
        f'— HEADLINE, {n_legs} legs</div>'
        f'{_feed_leg_rows(legs)}'
        f'<div class="f-combined">{comb}{_feed_code_line(code)}</div>'
        f'</div>')


def _feed_acca_card(acca: dict, code: str | None) -> str:
    """A split acca (Acca B/C/D...) in the consistent list."""
    legs = acca.get("legs") or []
    n_legs = acca.get("n_legs", len(legs))
    combined = acca.get("combined_odds")
    comb = f"Combined {combined:.2f}" if combined is not None else "Combined —"
    label = acca.get("label", "")
    return (
        f'<div class="f-card f-acca">'
        f'<div class="f-acca-title">★ {html.escape(label)}  {n_legs} legs</div>'
        f'{_feed_leg_rows(legs)}'
        f'<div class="f-combined">{comb}{_feed_code_line(code)}</div>'
        f'</div>')


def _feed_singles(singles: list, codes_by_label: dict) -> str:
    """Singles — one standalone slip each, own booking code (production intent
    #6; the Telegram format: fixture (league) — market @ price  Booking code)."""
    rows = []
    for s in singles:
        label = (s.get("label") or "").replace("SINGLE — ", "")
        leg0 = (s.get("legs") or [{}])[0]
        rows.append(
            f'<div class="f-single">'
            f'<div class="f-leg"><span class="f-leg-name">{html.escape(label)} '
            f'({html.escape(leg0.get("league", ""))}) —</span>'
            f'<span class="f-leg-mkt">{html.escape(leg0.get("market_name", ""))} @ '
            f'{_price2(leg0.get("price"))}</span></div>'
            f'{_feed_code_line(codes_by_label.get(s.get("label")))}'
            f'</div>')
    return ('<div class="f-card"><div class="f-singles-title">'
            'SINGLES — one standalone slip each, own booking code</div>'
            + "".join(rows) + '</div>')


def _feed_production_block(payload: dict, booking_codes) -> str:
    """PRODUCTION BETS — the parity anchor. Acca A (headline) → split accas →
    singles, each with its own booking code; honest NO production pick today
    when nothing eligible (HR35)."""
    d = payload.get("date", _date.today().isoformat())
    accas = payload.get("accas") or []
    codes_by_label = _codes_by_label(booking_codes)
    accas_real = [a for a in accas
                  if not (a.get("label") or "").startswith("SINGLE — ")]
    singles = [a for a in accas if (a.get("label") or "").startswith("SINGLE — ")]
    acca_a = next((a for a in accas_real if a.get("label") == "Acca A"), None)
    splits = [a for a in accas_real if a is not acca_a]

    heading = (f'<div class="f-prod-head">PRODUCTION BETS — {html.escape(d)}'
               f'<span class="f-prod-sub">today\'s fixtures only</span></div>')

    if not accas_real and not singles:
        return (heading + '<div class="f-card f-prod-empty">'
                'NO production pick today — no deploy-eligible fixture with a '
                'live price kicks off today. A valid, honest result (HR35).</div>')

    parts = [heading]
    if acca_a:
        parts.append(_feed_acca_hero(acca_a, codes_by_label.get(acca_a.get("label"))))
    parts += [_feed_acca_card(a, codes_by_label.get(a.get("label")))
              for a in splits]
    if singles:
        parts.append(_feed_singles(singles, codes_by_label))
    return "".join(parts)


def _feed_scan(payload: dict, scores: dict, pill_base: str) -> str:
    """The lean scan — league-grouped cards, live-score badge, honest PENDING
    rows (the other session's lean board commit carried the same simplification:
    AI-pick cards, no internals)."""
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

    group_html = []
    for league, bfs in sorted(groups.items()):
        cards = []
        for bf in bfs:
            home, away, lg = _teams(bf)
            fixture_txt = f"{home} v {away}" if home and away and away != "—" \
                else _short_fixture(bf.get("fixture", ""))
            pick_label, pick_prob = _pick(bf)
            key = f"{home}|{away}" if home and away and away != "—" \
                else _short_fixture(bf.get("fixture", ""))
            score = ""
            for k, v in (scores or {}).items():
                if k.startswith(key + "|"):
                    score = v
                    break
            live = (f'<span class="f-live">{html.escape(score)}</span>'
                    if score else '<span class="f-live"></span>')
            cards.append(
                f'<div class="f-scan-card" data-fixture="{html.escape(key)}">'
                f'<div class="f-scan-name"><span class="f-fixture">'
                f'{html.escape(fixture_txt)}</span>'
                f'<span class="f-league">{html.escape(lg)}</span>{live}</div>'
                f'<div class="f-scan-pick"><span>{html.escape(pick_label)}</span>'
                f'<b>{html.escape(pick_prob)}</b></div>'
                f'</div>')
        group_html.append(
            f'<div class="f-league-group"><div class="f-league-head">'
            f'<span>{html.escape(league)} ({len(bfs)})</span></div>'
            f'<div class="f-league-body">{"".join(cards)}</div></div>')

    if unrated:
        uc = "".join(
            f'<div class="f-scan-card pending"><div class="f-scan-name">'
            f'<span class="f-fixture">{html.escape(_short_fixture(bf.get("fixture", "")))}</span>'
            f'<span class="f-league">{html.escape(_league_of(bf.get("fixture", "")))}</span></div>'
            f'<div class="f-scan-pick"><span class="pnd">NO DATA — PENDING</span></div></div>'
            for bf in unrated)
        group_html.append(
            f'<div class="f-league-group"><div class="f-league-head">'
            f'<span>NO DATA — PENDING ({len(unrated)})</span></div>'
            f'<div class="f-league-body">{uc}</div></div>')

    return datepills + "".join(group_html)


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
    extra = (" Architect sign-off is active — publishing live side-by-side "
             "with paper until mean CLV turns positive (override never silent)."
             if gs.get("override", False) else "")
    return (
        f'<div class="f-honest">'
        f'<span class="f-honest-title">HONEST EDGE LINE</span>'
        f'<span class="f-honest-body">An excellent informed process but NOT a '
        f'demonstrated profitable edge.{html.escape(extra)}</span>'
        f'<span class="f-honest-cap">Capital authority: THE ARCHITECT. '
        f'Nothing here is live until you deploy it.</span></div>')


def render_dashboard(payload: dict, asset_base: str = "/static",
                     booking_codes=None, scores=None,
                     pill_base: str = "/dashboard") -> str:
    """The single-scroll feed page — structurally the Telegram board."""
    body = f"""<div class="f-page">
  {_feed_hero(payload)}
  {_feed_flags(payload)}
  {_feed_gate_callout(payload)}
  <main class="f-main">
    <section class="f-section" id="production">{_feed_production_block(payload, booking_codes)}</section>
    <section class="f-section" id="scan">{_feed_scan(payload, scores or {}, pill_base)}</section>
    <section class="f-section" id="yesterday">{_feed_yesterday(payload)}</section>
    <section class="f-section" id="rolling">{_feed_rolling(payload)}</section>
  </main>
  {_feed_honest_edge(payload)}
</div>"""
    return _shell("OLP XDV — Today's Board", body, asset_base)
