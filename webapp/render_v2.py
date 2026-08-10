"""render_v2.py — the NEW OLP XDV design, implementing the ratified prototype.

Reference: webapp/design_reference/OLP_XDV_PROTOTYPE.html + FUNCTION_MAP.md
(full-replacement rebuild of /dashboard and /admin).

  render_dashboard(payload, booking_codes=None, scores=None)
      — the PUBLIC /dashboard: a mobile-first (~420px) client with bottom
        tabs CALL / SCAN / ANALYST. No model internals (fed by
        schema.trim_payload() via the published store). No chat — the client
        Analyst tab is READ-ONLY (full chat lives in admin only).
  render_admin_dashboard(payload, booking_codes=None)
      — the authed /admin: light theme, top search, Trigger Production + date
        selector, clickable stat pills, league filter chips, a dense
        Fixture|1|X|2|O1.5|Elo|MES|Tier|Src table with expandable internals,
        Approve→Publish (hard-gated), the error/rejection log, and the AI
        Analyst full chat (real /api/analyst backend, same as the Telegram bot).

Interaction is CSP-clean: NO inline handlers anywhere. Every control carries a
data-* hook and static/js/proto.js binds them via addEventListener
(script-src 'self'). Booking codes are read server-side from the day's
acca_<date>_codes.json (schema.read_booking_codes) and rendered as text — they
recall a betslip in SportyBet; they are never a stake (Phase-2 bright line).

HR35 is kept: a fixture with no rating renders NO DATA — PENDING, a day with no
captured booking codes renders NO DATA — PENDING, never a fabricated code.
"""
from __future__ import annotations

import html
import re
from datetime import date as _date, datetime, timedelta as _timedelta

from webapp.render import (
    _fmt_price,
    _internals,
    _league_of,
    _pct,
    _pick,
    _short_fixture,
    _src_dot,
    _teams,
    _verification_tier,
)

# ─────────────────────────────────────────────────────────────────────────────
# Document shell (PWA metas preserved from html_shell; stylesheet is proto.css,
# interaction is proto.js — the old app.css/assets.js are NOT loaded here)
# ─────────────────────────────────────────────────────────────────────────────
def _shell(title: str, body: str, asset_base: str = "/static") -> str:
    base = html.escape(asset_base, quote=True)
    return f"""<!doctype html>
<html lang="en" data-asset-base="{base}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#0B0E13" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F5F6F8" media="(prefers-color-scheme: light)">
<link rel="manifest" href="{base}/manifest.json">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{base}/css/proto.css">
</head><body>
{body}
<div class="toast" id="toast"></div>
<script src="{base}/js/proto.js" defer></script>
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


def _norm(name: str) -> str:
    """Lowercase + strip punctuation, for booking-code fixture matching."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Booking codes (from schema.read_booking_codes) — label → code, plus a
# per-single lookup across every booked acca's legs.
# ─────────────────────────────────────────────────────────────────────────────
def _codes_by_label(codes) -> dict:
    out = {}
    for r in (codes or {}).get("results") or []:
        if r.get("label") and r.get("code"):
            out[r["label"]] = r["code"]
    return out


def _single_code(codes, fixture: str) -> str | None:
    """The acca booking code a single fixture was booked inside, if any."""
    short = _norm(_short_fixture(fixture))
    for r in (codes or {}).get("results") or []:
        for leg in r.get("per_leg") or []:
            if _norm(leg.get("fixture", "")) == short:
                return r.get("code")
    return None


def _pct_of(x) -> str:
    return "—" if x is None else f"{round(x * 100)}%"


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT — the mobile-first Call / Scan / Analyst view
# ─────────────────────────────────────────────────────────────────────────────
def _client_market_rows(bf: dict) -> str:
    """The expandable market detail for a client card (derived ONLY from the
    client-safe `probs` — no model internals reach this markup)."""
    p = bf.get("probs") or {}
    pick_label, pick_prob = _pick(bf)
    rows = [
        f'<div class="c-mkt-row"><span>{html.escape(pick_label)}</span>'
        f"<b>{html.escape(pick_prob)}</b></div>",
        f'<div class="c-mkt-row"><span>Draw</span><b>{_pct_of(p.get("p_draw"))}</b></div>',
        f'<div class="c-mkt-row"><span>Over 1.5 goals</span><b>{_pct_of(p.get("p_over_15"))}</b></div>',
        f'<div class="c-mkt-row"><span>BTTS Yes</span><b>{_pct_of(p.get("p_btts_yes"))}</b></div>',
        f'<div class="c-mkt-row"><span>Deploy at</span>'
        f"<b>{html.escape(_fmt_price(bf.get('mes_trigger_price')))}</b></div>",
    ]
    return "".join(rows)


def _bookcode_block(code: str | None, extra_cls: str = "") -> str:
    """Booking-code line: the real SportyBet code + Copy, or an honest
    NO DATA — PENDING (HR35: never fabricate a code)."""
    if code:
        return (f'<div class="c-bookcode {extra_cls}">Booking code: <b>{html.escape(code)}</b> '
                f'<button type="button" data-code="{html.escape(code)}">Copy</button></div>')
    return ('<div class="c-bookcode ' + extra_cls + '">Booking code: '
            '<span class="pnd">NO DATA — PENDING</span></div>')


def _client_call(board: list, accas: list, codes) -> str:
    singles = [bf for bf in board if bf.get("probs") and bf.get("on_deploy_shortlist")]
    parts = ['<div class="c-panel-head">Singles — recommended individually</div>']
    if not singles:
        parts.append('<div class="c-empty">NO DATA — PENDING: no deploy-shortlist '
                     'fixtures rated on this board yet.</div>')
    for i, bf in enumerate(singles):
        home, away, league = _teams(bf)
        p = bf.get("probs") or {}
        pct = _pct_of(bf.get("best_model_prob"))
        fixture_txt = f"{home} v {away}" if home and away and away != "—" \
            else _short_fixture(bf.get("fixture", ""))
        code = _single_code(codes, bf.get("fixture", ""))
        parts.append(
            f'<div class="c-card">'
            f'<button type="button" class="c-card-top" data-detail="call-{i}" aria-expanded="false">'
            f'<span><span class="c-fixture">{html.escape(fixture_txt)}</span>'
            f'<span class="c-league-sub">{html.escape(league)}</span></span>'
            f'<span class="c-pct">{pct}</span></button>'
            f'<div class="c-detail" id="call-{i}">{_client_market_rows(bf)}</div>'
            f"{_bookcode_block(code)}</div>"
        )
    parts.append('<div class="c-panel-head" style="margin-top:18px;">'
                 'The Accumulator — all singles combined, one bet</div>')
    if accas:
        acca = accas[0]
        legs = acca.get("legs") or []
        codes_by_label = _codes_by_label(codes)
        code = codes_by_label.get(acca.get("label"))
        leg_rows = "".join(
            f'<div class="c-mkt-row"><span>{html.escape(l.get("fixture", ""))} — '
            f'{html.escape(l.get("market_name", ""))}</span>'
            f"<b>{_pct_of(l.get('prob'))}</b></div>"
            for l in legs
        )
        combined = _pct_of(acca.get("combined_prob"))
        parts.append(
            f'<div class="c-card acca">'
            f'<div style="font-size:12px;font-weight:700;margin-bottom:6px;">'
            f'{len(legs)}-leg ACCA</div>'
            f'{leg_rows}'
            f'<div class="c-mkt-row total"><span>Combined probability</span>'
            f"<b>{combined}</b></div>"
            f"{_bookcode_block(code, 'acca')}</div>"
        )
    else:
        parts.append('<div class="c-empty">NO DATA — PENDING: no accumulator '
                     'produced for this board.</div>')
    return "".join(parts)


def _client_scan(board: list, d: str, today: str, scores: dict) -> str:
    # Date pills: yesterday / today / +1 / +2 (links — honest 404 on missing days)
    pills = []
    for off in (-1, 0, 1, 2):
        dt = _date.fromisoformat(d) + _timedelta(days=off)
        iso = dt.isoformat()
        cls = ["c-pill"]
        if iso == d:
            cls.append("selected")
        if off == 0:
            cls.append("today")
        sub = iso[5:]
        label = _friendly_day(iso, today)
        pills.append(f'<a class="{" ".join(cls)}" href="/dashboard/{iso}">'
                     f"{label}<span class='sub'>{sub}</span></a>")
    datepills = f'<div class="c-datepills">{"".join(pills)}</div>'

    search = ('<input class="c-search" id="scan-search" type="search" '
              'placeholder="Filter by team or league...">')

    rated = [bf for bf in board if bf.get("probs")]
    unrated = [bf for bf in board if not bf.get("probs")]
    groups: dict[str, list] = {}
    for bf in rated:
        groups.setdefault(_league_of(bf.get("fixture", "")), []).append(bf)

    group_html = []
    card_i = 0
    for gi, (league, bfs) in enumerate(sorted(groups.items())):
        open_cls = " open" if gi == 0 else ""
        cards = []
        for bf in bfs:
            home, away, _ = _teams(bf)
            pick_label, pick_prob = _pick(bf)
            p = bf.get("probs") or {}
            fixture_txt = f"{home} v {away}" if home and away and away != "—" \
                else _short_fixture(bf.get("fixture", ""))
            search_hay = f"{fixture_txt} {league}".lower()
            live = ""
            key = f"{home}|{away}" if home and away and away != "—" else _short_fixture(bf.get("fixture", ""))
            score = None
            for k, v in (scores or {}).items():
                if k.startswith(key + "|") or k.startswith(f"{key}|"):
                    score = v
                    break
            # Live badge is a data-live-score placeholder: server can pre-fill it,
            # and proto.js polls /api/live-scores to update it in place. Empty is
            # hidden by CSS (.c-live:empty{display:none}).
            live = (f'<span class="c-live" data-live-score>{html.escape(score)}</span>'
                    if score else '<span class="c-live" data-live-score></span>')
            sub_line = f'{html.escape(pick_label)}{live}'
            cards.append(
                f'<div class="c-card scan-row" data-fixture="{html.escape(key)}" '
                f'data-search="{html.escape(search_hay)}">'
                f'<button type="button" class="c-card-top" data-detail="scan-{card_i}" aria-expanded="false">'
                f'<span class="c-fixture">{html.escape(fixture_txt)}<br>'
                f'<span style="font-size:10px;color:var(--ink-faint);font-weight:400;">{sub_line}</span></span>'
                f'<span class="c-pct">{html.escape(pick_prob)}</span></button>'
                f'<div class="c-detail" id="scan-{card_i}">{_client_market_rows(bf)}</div>'
                f"</div>"
            )
            card_i += 1
        group_html.append(
            f'<div class="c-league-group">'
            f'<button type="button" class="c-league-head{open_cls}" aria-expanded="{"true" if open_cls else "false"}">'
            f'<span>{html.escape(league)} ({len(bfs)})</span><span class="chev">▸</span></button>'
            f'<div class="c-league-body{open_cls}">{"".join(cards)}</div></div>'
        )

    if unrated:
        unrated_cards = "".join(
            f'<div class="c-card scan-row" data-search="{html.escape(_short_fixture(bf.get("fixture","")) + " " + _league_of(bf.get("fixture",""))).lower()}">'
            f'<div class="c-card-top"><span><span class="c-fixture">'
            f'{html.escape(_short_fixture(bf.get("fixture", "")))}</span>'
            f'<span class="c-league-sub">{html.escape(_league_of(bf.get("fixture", "")))}</span></span>'
            f'<span class="c-pct" style="color:var(--ink-faint);">PENDING</span></div>'
            f'<div class="c-bookcode"><span class="pnd">NO DATA — PENDING</span></div></div>'
            for bf in unrated
        )
        group_html.append(
            f'<div class="c-league-group">'
            f'<button type="button" class="c-league-head" aria-expanded="false">'
            f'<span>NO DATA — PENDING ({len(unrated)})</span><span class="chev">▸</span></button>'
            f'<div class="c-league-body">{unrated_cards}</div></div>'
        )

    empty = ('<div id="scan-empty" style="display:none;text-align:center;'
             'color:var(--ink-faint);font-size:12px;padding:20px;">No fixtures match '
             '"<span id="scan-empty-term"></span>"</div>')
    return datepills + search + "".join(group_html) + empty


def _client_analyst(payload: dict, n_singles: int, n_accas: int) -> str:
    n_leagues = payload.get("n_leagues", payload.get("leagues_scanned") and len(payload.get("leagues_scanned")) or 0)
    phase = payload.get("phase", "")
    cal = payload.get("calibration_count")
    cards = [
        ("Today's board",
         f"{n_singles} singles, {n_accas} accumulator, {n_leagues} leagues scanned. Full detail above."),
        ("Track record",
         f"Phase 2 — paper calibration, {cal or 0}/30 legs logged. Not yet a demonstrated edge."),
        ("Explain a pick",
         "Tap any fixture in Call or Scan to see the full market breakdown behind it."),
    ]
    html_cards = "".join(
        f'<div class="c-card"><div style="font-size:12px;font-weight:700;'
        f'margin-bottom:6px;">{t}</div><div style="font-size:11px;color:var(--ink-dim);">'
        f"{html.escape(desc)}</div></div>"
        for t, desc in cards
    )
    return ('<div class="c-panel-head">READ-ONLY — full chat lives in admin only</div>'
            + html_cards)


def render_dashboard(payload: dict, asset_base: str = "/static",
                     booking_codes=None, scores=None) -> str:
    d = payload.get("date", _date.today().isoformat())
    today = _date.today().isoformat()
    board = payload.get("board", [])
    accas = payload.get("accas") or []

    singles = sum(1 for bf in board if bf.get("probs") and bf.get("on_deploy_shortlist"))

    call = _client_call(board, accas, booking_codes)
    scan = _client_scan(board, d, today, scores or {})
    analyst = _client_analyst(payload, singles, len(accas))

    body = f"""<div class="app-frame"><div id="client-app">
  <header class="c-header">
    <div class="c-brand"><span class="mark"></span><h1>OLP XDV</h1></div>
    <div class="c-date">{_friendly_date(d)}</div>
  </header>
  <nav class="c-tabs">
    <button type="button" class="c-tab active" data-panel="call">Call</button>
    <button type="button" class="c-tab" data-panel="scan">Scan</button>
    <button type="button" class="c-tab" data-panel="analyst">Analyst</button>
  </nav>
  <section id="panel-call" class="c-panel active">{call}</section>
  <section id="panel-scan" class="c-panel">{scan}</section>
  <section id="panel-analyst" class="c-panel">{analyst}</section>
</div></div>"""
    return _shell("OLP XDV — Today's Board", body, asset_base)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — light, dense production control + internals + AI chat
# ─────────────────────────────────────────────────────────────────────────────
def _a_pct(bf: dict, key: str) -> str:
    p = bf.get("probs")
    return _pct_of(p.get(key)) if p else "NO DATA"


def _a_elo(bf: dict) -> str:
    elo = bf.get("elo_probs")
    if not elo or len(elo) < 3:
        return "—"
    best = max(elo)
    return _pct_of(best)


def _a_mes(bf: dict) -> str:
    ev = bf.get("best_mes_ev")
    return "—" if ev is None else f"{ev:+.0%}"


def _a_tier(bf: dict) -> str:
    t = bf.get("softness_tier")
    if not t:
        return '<span class="a-tag">—</span>'
    return f'<span class="a-tag T{t}">{html.escape(str(t))}</span>'


def _a_edit_form(bf: dict, row_i: int) -> str:
    """Inline edit-before-publish: adjusts the publishable (client-visible)
    fields on the RAW board; Approve→Publish then ships the edited trim."""
    f = html.escape(bf.get("fixture", ""), quote=True)
    market = html.escape(bf.get("best_market") or "", quote=True)
    price = "" if bf.get("best_price") is None else html.escape(str(bf["best_price"]))
    tier = bf.get("softness_tier") or ""
    short = ' checked' if bf.get("on_deploy_shortlist") else ""
    opts = "".join(
        f'<option value="{t}"{" selected" if t == tier else ""}>'
        f'{"Tier " + t if t else "Tier —"}</option>'
        for t in ("", "A", "B", "C", "D"))
    return (
        f'<div class="a-edit">'
        f'<div class="a-edit-title">Edit before publish — <span class="dim">client-visible fields</span></div>'
        f'<div class="a-edit-grid">'
        f'<label>Fixture <input class="a-edit-in" id="edit-fixture-{row_i}" value="{f}"></label>'
        f'<label>Best market <input class="a-edit-in" id="edit-market-{row_i}" value="{market}"></label>'
        f'<label>Best price <input class="a-edit-in" id="edit-price-{row_i}" value="{price}" inputmode="decimal"></label>'
        f'<label>Softness tier <select class="a-edit-in" id="edit-tier-{row_i}">{opts}</select></label>'
        f'<label class="check"><input type="checkbox" id="edit-short-{row_i}"{short}> Deploy shortlist</label>'
        f'</div>'
        f'<button type="button" class="a-edit-save" data-row="{row_i}" data-fixture="{f}">Save edits</button>'
        f'<span class="a-edit-status" id="edit-status-{row_i}"></span>'
        f'</div>'
    )


def _a_detail(bf: dict, row_i: int) -> str:
    """Expanded internals under a dense row — admin only."""
    inner = [_internals(bf)]
    p = bf.get("probs")
    if p:
        pick_label, pick_prob = _pick(bf)
        price = bf.get("best_price")
        inner.append(f'<div class="int-row"><b>Pick:</b> {html.escape(pick_label)} '
                     f"({html.escape(pick_prob)}{f' @ {price}' if price is not None else ''})</div>")
    reason = bf.get("rejection_reason")
    if reason:
        inner.append(f'<div class="int-row"><b>Rejection:</b> {html.escape(reason)}</div>')
    return f'<div class="a-detail-inner">{"".join(inner)}</div>' + _a_edit_form(bf, row_i)


def _admin_table(board: list) -> str:
    sep_i = 0
    rows = []
    by_league: dict[str, list] = {}
    for bf in board:
        by_league.setdefault(_league_of(bf.get("fixture", "")), []).append(bf)
    row_i = 0
    for league, bfs in sorted(by_league.items()):
        rows.append(f'<tr class="a-league-sep" data-league="L{sep_i}">'
                    f'<td colspan="9">{html.escape(league.upper())}'
                    f'<span class="cnt">({len(bfs)})</span></td></tr>')
        for bf in bfs:
            home, away, lg = _teams(bf)
            fixture_txt = f"{home} v {away}" if home and away and away != "—" \
                else _short_fixture(bf.get("fixture", ""))
            hay = f"{fixture_txt} {lg}".lower()
            has_probs = bf.get("probs") is not None
            cells = [
                f'<td>{html.escape(fixture_txt)}</td>',
                f'<td>{_a_pct(bf, "p_home") if has_probs else "—"}</td>',
                f'<td>{_a_pct(bf, "p_draw") if has_probs else "—"}</td>',
                f'<td>{_a_pct(bf, "p_away") if has_probs else "—"}</td>',
                f'<td>{_a_pct(bf, "p_over_15") if has_probs else "—"}</td>',
                f"<td>{_a_elo(bf)}</td>",
                f"<td>{_a_mes(bf)}</td>",
                f"<td>{_a_tier(bf)}</td>",
                f"<td>{_src_dot(bf)}</td>",
            ]
            rows.append(
                f'<tr class="clickable" data-target="adm-{row_i}" data-league="L{sep_i}" '
                f'data-fixture="{html.escape(bf.get("fixture", ""), quote=True)}" '
                f'data-search="{html.escape(hay)}" aria-expanded="false" tabindex="0">'
                f'{"".join(cells)}</tr>'
                f'<tr class="a-detail-row hidden" id="adm-{row_i}" data-league="L{sep_i}">'
                f'<td colspan="9">{_a_detail(bf, row_i)}</td></tr>'
            )
            row_i += 1
        sep_i += 1
    thead = ("<tr><th>Fixture</th><th>1</th><th>X</th><th>2</th><th>O1.5</th>"
             "<th>Elo</th><th>MES</th><th>Tier</th><th>Src</th></tr>")
    return (f'<div class="a-tablewrap"><table class="a-table" id="admin-table">'
            f"<thead>{thead}</thead><tbody id=\"admin-tbody\">"
            f'{"".join(rows)}</tbody></table></div>')


def _admin_chips(board: list) -> str:
    leagues = sorted({_league_of(bf.get("fixture", "")) for bf in board})
    chips = ['<div class="a-chip active" data-league="all" tabindex="0">All leagues</div>']
    for i, lg in enumerate(leagues):
        if lg in ("—", ""):
            continue
        chips.append(f'<div class="a-chip" data-league="L{i}" tabindex="0">'
                     f"{html.escape(lg)}</div>")
    return f'<div class="a-filterbar">{"".join(chips)}</div>'


def _admin_log(payload: dict, board: list) -> str:
    flags = payload.get("data_flags") or []
    rejected = [bf for bf in board if bf.get("rejection_reason")]
    rows = []
    for flag in flags:
        rows.append(f'<div class="log-row"><span class="tier flag">FLAG</span>'
                    f'<span class="why">{html.escape(flag)}</span></div>')
    for bf in rejected:
        t = bf.get("softness_tier") or "—"
        rows.append(f'<div class="log-row"><span class="tier">T{t}</span>'
                    f'<span class="why"><b>{html.escape(_short_fixture(bf.get("fixture", "")))}</b> — '
                    f"{html.escape(bf.get('rejection_reason', ''))}</span></div>")
    if not rows:
        rows.append('<div class="log-row"><span class="empty">No rejections or data flags '
                    'on this board.</span></div>')
    n = len(flags) + len(rejected)
    return (
        f'<div class="a-panel"><h3 id="log-toggle" role="button" tabindex="0" '
        f'aria-expanded="false" style="cursor:pointer;">Error / Rejection Log ({n}) ▸</h3>'
        f'<div id="log-body" class="a-log hidden">{"".join(rows)}</div></div>'
    )


def render_admin_dashboard(payload: dict, asset_base: str = "/static",
                           booking_codes=None) -> str:
    d = payload.get("date", _date.today().isoformat())
    board = payload.get("board", [])
    gate = payload.get("gate") or {}
    telemetry = payload.get("telemetry") or {}

    n_scanned = len(board)
    n_eligible = sum(1 for bf in board if bf.get("on_deploy_shortlist"))
    clv = gate.get("legs_with_clv", 0)
    req = gate.get("gate_requirement", 30)

    predicted_at = ""
    for k in ("predicted_at", "run_started", "produced_at"):
        if telemetry.get(k):
            predicted_at = telemetry[k]
            break
    if predicted_at:
        try:
            predicted_at = datetime.fromisoformat(str(predicted_at)).strftime("%H:%M")
        except (TypeError, ValueError):
            pass
    last_run = f"Last run: {predicted_at}" if predicted_at else "Last run: —"

    stat_scanned = f'<div class="a-stat" data-chip="all" title="All fixtures"><b>{n_scanned}</b>scanned</div>'
    stat_eligible = f'<div class="a-stat" title="Deploy-shortlist fixtures"><b>{n_eligible}</b>eligible</div>'
    stat_gate = f'<div class="a-stat" title="Phase 3 CLV gate - publish blocked until met"><b>{clv}/{req}</b>CLV gate</div>'

    body = f"""<div class="app-frame wide"><div id="admin-app">
  <header class="a-topbar">
    <div class="a-logo">OLP XDV — ADMIN</div>
    <input class="a-search" id="admin-search" type="search" placeholder="Search fixture, team, league...">
  </header>
  <div class="a-actionbar">
    <button id="trigger-btn" type="button"><span class="spinner"></span><span id="trigger-label">▶ Trigger Production</span></button>
    <input class="a-date" id="trigger-date" type="date" value="{d}" aria-label="Board date">
    {stat_scanned}{stat_eligible}{stat_gate}
    <span id="last-run">{html.escape(last_run)}</span>
  </div>
  {_admin_chips(board)}
  {_admin_table(board)}
  <div class="a-approve-row">
    <button id="approve-btn" type="button">Approve → Publish to Client</button>
    <div id="publish-status"></div>
  </div>
  <div class="a-panel">
    <h3>AI Analyst (admin — full chat)</h3>
    <div id="admin-chatlog"><div class="a">Ask about today's board, why a pick diverged, or the CLV backtest.</div></div>
    <div class="chat-row">
      <input id="admin-chat-input" type="text" placeholder="Ask a question..." aria-label="Ask the AI Analyst">
      <button id="admin-chat-send" type="button">Send</button>
    </div>
  </div>
  {_admin_log(payload, board)}
</div></div>"""
    return _shell("OLP XDV — Admin", body, asset_base)
