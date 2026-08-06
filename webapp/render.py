"""HTML rendering for the web dashboard — plain language, phone-first.

Reads the board JSON written by run_daily (webapp/schema) and renders it as
HTML. The voice is the same as the board/Telegram (the Architect is
non-technical): predictions in words, NO DATA — PENDING for anything missing
(HR35 — never a guess), the honest-edge statement and capital authority always
present.

Colours follow the dataviz method: this is a stat-tile + table layout, so it
uses only status colours (good / warning / serious) — every one shipped with an
icon AND a label, never colour alone — plus neutral ink. No categorical series,
so no categorical palette is needed.
"""
from __future__ import annotations

import html
from datetime import date as _date

from config import PHASE_LABEL

# ---------------------------------------------------------------------------
# Palette — validated status + neutral roles (dataviz method, light + dark).
# ---------------------------------------------------------------------------
_CSS = """
:root { color-scheme: light;
  --surface:      #fcfcfb;
  --surface-2:    #f2f1ee;
  --ink:          #0b0b0b;
  --ink-2:        #52514e;
  --border:       rgba(11,11,11,0.10);
  --good:         #006300;   /* good text on light surface */
  --good-bg:      #e7f5e7;
  --warning:      #fab219;   /* sub-3:1 by design — icon+label required */
  --warning-bg:   #fdf3d7;
  --serious:      #ec835a;
  --serious-bg:   #fbe9e1;
  --star:         #b26a00;   /* the ⭐ picks accent (not a series colour) */
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { color-scheme: dark;
  --surface:    #1a1a19;
  --surface-2:  #232322;
  --ink:        #ffffff;
  --ink-2:      #c3c2b7;
  --border:     rgba(255,255,255,0.10);
  --good:       #6fd26f;
  --good-bg:    #1c2b1c;
  --warning:    #f3bf3f;
  --warning-bg: #2b2414;
  --serious:    #f09672;
  --serious-bg: #2c1f19;
  --star:       #f0a93a;
  }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width: 46rem; margin: 0 auto; padding: 1rem 1rem 3rem; }
h1 { font-size: 1.25rem; margin: .2rem 0 .1rem; }
h2 { font-size: 1.05rem; margin: 1.6rem 0 .5rem; }
.muted { color: var(--ink-2); }
a { color: var(--star); }
nav { font-size: .9rem; padding:.35rem 0 .6rem; border-bottom:1px solid var(--border); margin-bottom:.4rem; }
nav a { margin-right: .9rem; text-decoration:none; }
.card { background:var(--surface-2); border:1px solid var(--border);
  border-radius:.6rem; padding:.8rem .9rem; margin:.7rem 0; }
.card p { margin:.35rem 0; }
.card pre { white-space:pre-wrap; margin:.3rem 0 0; font: inherit; }
table { width:100%; border-collapse:collapse; margin:.4rem 0 .9rem; }
th, td { text-align:left; padding:.45rem .3rem; border-bottom:1px solid var(--border);
  vertical-align:top; }
th { font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-2); }
.pick { color: var(--star); font-weight:600; }
.flag-warn { color: var(--warning); font-weight:600; }
.flag-good { color: var(--good); }
.badge { display:inline-block; font-size:.78rem; padding:.1rem .45rem;
  border-radius:999px; border:1px solid var(--border); }
.badge.good { color:var(--good); background:var(--good-bg); border-color:transparent; }
.badge.warn { color:var(--warning); background:var(--warning-bg); border-color:transparent; }
.badge.serious { color:var(--serious); background:var(--serious-bg); border-color:transparent; }
/* Gate strip — status colour ALWAYS carries a label + number, never alone. */
.gatebar { height:.55rem; background:var(--border); border-radius:999px; overflow:hidden; margin:.35rem 0 .15rem; }
.gatebar > i { display:block; height:100%; background:var(--good); border-radius:999px; }
.foot { margin-top:2.2rem; padding-top:.7rem; border-top:1px solid var(--border);
  font-size:.85rem; color:var(--ink-2); }
details { font-size:.85rem; }
summary { cursor:pointer; color:var(--ink-2); }
li { margin:.2rem 0; }
"""


def html_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_CSS}</style>
</head><body><div class="wrap">
{body}
</div></body></html>"""


def _nav(active: str, today: str) -> str:
    links = [("today", f"/board/{today}", "Today"),
             ("history", "/history", "History"),
             ("stats", "/stats", "Gate")]
    parts: list[str] = []
    for key, url, name in links:
        if key == active:
            parts.append(f'<span class="muted">{name}</span>')
        else:
            parts.append(f'<a href="{url}">{name}</a>')
    return "<nav>" + " ".join(parts) + "</nav>"


def _pct(x: float | None) -> str:
    return "NO DATA — PENDING" if x is None else f"{round(x * 100)}%"


def _league_of(fixture: str) -> str:
    if " (" in fixture:
        return fixture.split(" (")[-1].rstrip(")")
    return "—"


def _short_fixture(fixture: str) -> str:
    return fixture.split(" (")[0]


def _gate_strip(gate: dict, telemetry: dict) -> str:
    n = gate.get("legs_with_clv", 0)
    req = gate.get("gate_requirement", 30)
    pct = min(1.0, n / req) if req else 0.0
    capture = telemetry.get("clv_capture_rate")
    cap_txt = ("NO DATA — PENDING" if capture is None
               else f"{round(capture * 100)}% of settled legs")
    days = telemetry.get("days_to_gate")
    days_txt = ("NO DATA — PENDING" if days is None
                else f"~{days} days at today's rate")
    met = gate.get("gate_met_pending_architect_signoff")
    badge = ("<span class='badge good'>✓ gate reached — ARCHITECT sign-off pending</span>"
             if met else "<span class='badge warn'>⏳ paper calibration in progress</span>")
    return f"""<div class="card">
  <strong>Road to the Phase&nbsp;3 gate</strong> {badge}
  <p class="muted">Closed-line value (CLV) legs — the only legs that count toward capital.</p>
  <p>{n} of {req} legs with a logged closing line</p>
  <div class="gatebar" aria-label="{n} of {req}"><i style="width:{round(pct*100)}%"></i></div>
  <p class="muted">Capture rate: {cap_txt} · CLV legs/day: {telemetry.get('clv_legs_per_day') or 'NO DATA — PENDING'} · projected gate: {days_txt}</p>
</div>"""


def _picks_card(recommendation: str) -> str:
    if not recommendation:
        recommendation = "⭐ TODAY'S PICKS\nNO DATA — no eligible pick today."
    lines = [html.escape(l) for l in recommendation.splitlines()]
    return (f'<div class="card"><h2 style="margin-top:0">⭐ TODAY\'S PICKS</h2>'
            f'<pre>{chr(10).join(lines)}</pre></div>')


def _the_call_rows(board: list[dict]) -> str:
    rows = [bf for bf in board if bf.get("on_deploy_shortlist")]
    if not rows:
        return '<p class="muted">No deploy-eligible call today (softness A/B only).</p>'
    out = ["<table><thead><tr><th>Fixture</th><th>Pick</th><th>Price</th><th>EV</th></tr></thead><tbody>"]
    for bf in rows:
        pick = f"{html.escape(bf.get('best_market') or '')}"
        if bf.get("best_model_prob") is not None:
            pick += f" ({round(bf['best_model_prob']*100)}%)"
        ev = bf.get("best_mes_ev")
        ev_txt = "NO DATA — PENDING" if ev is None else f"{ev:+.0%}"
        out.append(
            f"<tr><td><a href='/why?fixture={html.escape(bf['fixture'])}'>{html.escape(_short_fixture(bf['fixture']))}</a>"
            f"<div class='muted'>{html.escape(_league_of(bf['fixture']))} · tier {bf.get('softness_tier','?')}</div></td>"
            f"<td class='pick'>{html.escape(pick)}</td>"
            f"<td>{bf.get('best_price') or 'NO DATA — PENDING'}</td>"
            f"<td class='pick'>{ev_txt}</td></tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _league_tables(board: list[dict]) -> str:
    leagues: dict[str, list[dict]] = {}
    for bf in board:
        leagues.setdefault(_league_of(bf["fixture"]), []).append(bf)
    if not leagues:
        return '<p class="muted">No fixtures in the window today. On a quiet day the board is honestly near-empty.</p>'
    out: list[str] = []
    for league in sorted(leagues):
        out.append(f"<h2>{html.escape(league)}</h2>")
        out.append("<table><thead><tr><th>Fixture</th><th>Prediction</th></tr></thead><tbody>")
        for bf in leagues[league]:
            p = bf.get("probs")
            if p is None:
                reason = bf.get("rejection_reason") or "NO DATA — PENDING"
                out.append(
                    f"<tr><td>{html.escape(_short_fixture(bf['fixture']))}"
                    f"<div class='muted'>{html.escape(reason)}</div></td>"
                    f"<td class='muted'>NO DATA — PENDING</td></tr>")
                continue
            home = p.get("p_home"); draw = p.get("p_draw"); away = p.get("p_away")
            winner = (p.get("home_team") if max(home or 0, draw or 0, away or 0) == home
                      else ("Draw" if (draw or 0) >= (away or 0) else p.get("away_team")))
            wp = max(home or 0, draw or 0, away or 0)
            pick = bf.get("best_market")
            extra = f"<div class='pick'>{html.escape(pick)}</div>" if pick else ""
            out.append(
                f"<tr><td>{html.escape(_short_fixture(bf['fixture']))}</td>"
                f"<td>{html.escape(winner)} {_pct(wp)}"
                f"<div class='muted'>Draw {_pct(draw)} · Away {_pct(away)}</div>{extra}</td></tr>")
        out.append("</tbody></table>")
    return "".join(out)


def _flags_block(data_flags: list[str]) -> str:
    if not data_flags:
        return ""
    lis = "".join(f"<li>{html.escape(f)}</li>" for f in data_flags)
    return (f'<h2>⚠ {len(data_flags)} data flag(s)</h2>'
            f'<details><summary>What the framework could not source — shown, never guessed</summary>'
            f'<ul>{lis}</ul></details>')


def _footer(payload: dict) -> str:
    phase = payload.get("phase") or PHASE_LABEL
    return (f'<div class="foot">'
            f'<p><strong>Honest edge statement:</strong> this is an excellent informed process, but it is NOT a '
            f'demonstrated profitable edge. The forward paper ledger settles that — nothing here is staked.</p>'
            f'<p><strong>Capital authority:</strong> {html.escape(phase)} — paper only, zero capital. '
            f'Staking is hard-blocked below Phase&nbsp;3.</p>'
            f'<p class="muted">Board for {html.escape(payload.get("date","?"))} · '
            f'{payload.get("n_leagues","?")} leagues scanned · schema v{payload.get("schema_version","?")}.</p>'
            f'</div>')


def render_dashboard(payload: dict) -> str:
    today = payload.get("date", _date.today().isoformat())
    title = f"OLP XDV — {today}"
    body = (
        _nav("today", today)
        + f"<h1>OLP XDV — daily board</h1><div class='muted'>{today}</div>"
        + _picks_card(payload.get("recommendation", ""))
        + _gate_strip(payload.get("gate", {}), payload.get("telemetry", {}))
        + "<h2>THE CALL</h2>" + _the_call_rows(payload.get("board", []))
        + "<h2>Today's fixtures</h2>" + _league_tables(payload.get("board", []))
        + _flags_block(payload.get("data_flags", []))
        + _footer(payload))
    return html_shell(title, body)


def render_stats_html(stats_text: str, today: str) -> str:
    body = (_nav("stats", today)
            + "<h1>Gate &amp; calibration</h1>"
            + "<div class='card'><pre>" + html.escape(stats_text) + "</pre></div>"
            + "<p class='muted'>CLV figures are read from clv/clv_log.json via the brain.</p>")
    return html_shell("OLP XDV — Gate & calibration", body)


def render_why_html(payload: dict, fixture: str) -> str:
    today = payload.get("date", _date.today().isoformat())
    match = next((bf for bf in payload.get("board", [])
                  if fixture in bf.get("fixture", "")), None)
    if match is None:
        body = (_nav("today", today)
                + "<h1>No such fixture</h1>"
                + "<p class='muted'>NO DATA — PENDING: no board row matches that fixture.</p>")
        return html_shell("OLP XDV — not found", body)
    p = match.get("probs")
    lines = [f"<h1>{html.escape(_short_fixture(match['fixture']))}</h1>",
             f"<div class='muted'>{html.escape(_league_of(match['fixture']))} · tier {match.get('softness_tier','?')} · "
             f"{match.get('model_engine','dc')} engine · kickoff {match.get('kickoff_date') or 'NO DATA — PENDING'}</div>"]
    if p is not None:
        lines.append("<div class='card'>"
                     f"<p><strong>Win chance:</strong> {html.escape(p['home_team'])} {_pct(p['p_home'])} · "
                     f"Draw {_pct(p['p_draw'])} · {html.escape(p['away_team'])} {_pct(p['p_away'])}</p>"
                     f"<p class='muted'>Over 1.5 {_pct(p['p_over_15'])} · Over 2.5 {_pct(p['p_over_25'])} · "
                     f"Over 3.5 {_pct(p['p_over_35'])} · BTTS {_pct(p['p_btts_yes'])}</p></div>")
    else:
        lines.append(f"<div class='card'><p class='flag-warn'>NO DATA — PENDING</p>"
                     f"<p>{html.escape(match.get('rejection_reason') or 'no fitted history')}</p></div>")
    if match.get("best_market"):
        lines.append("<div class='card'><p><strong>Best available market:</strong> "
                     f"{html.escape(match['best_market'])} @ {match['best_price']} "
                     f"(model {_pct(match['best_model_prob'])}, EV "
                     f"<span class='pick'>{_fmt_ev(match['best_mes_ev'])}</span>).</p>"
                     f"<p class='muted'>Bookmaker: {html.escape(match['best_bookmaker'] or '—')} · "
                     f"{match['best_n_books']} book(s) quoted.</p></div>")
    if match.get("engine_divergence"):
        lines.append(f"<div class='card'><p class='flag-warn'>⚠ {html.escape(match['engine_divergence'])}</p></div>")
    if match.get("elo_probs"):
        e = match["elo_probs"]
        lines.append(f"<div class='card'><p class='muted'>Elo second opinion: "
                     f"{_pct(e[0] if len(e)>0 else None)} / {_pct(e[1] if len(e)>1 else None)} / "
                     f"{_pct(e[2] if len(e)>2 else None)}</p></div>")
    lines.append(f"<div class='foot'><p class='muted'>Prediction persisted to the brain. "
                 f"Model probability shown is the RAW model_prob — recalibration deltas "
                 f"(cal_adjustment {match.get('cal_adjustment')}) apply only to THE CALL's EV, "
                 f"never the ledger.</p></div>")
    return html_shell("OLP XDV — fixture", _nav("today", today) + "".join(lines))


def _fmt_ev(ev: float | None) -> str:
    return "NO DATA — PENDING" if ev is None else f"{ev:+.0%}"


def render_history_html(dates: list[str], today: str) -> str:
    rows = "".join(
        f"<li><a href='/board/{d}'>{d}</a></li>" for d in dates)
    body = (_nav("history", today) + "<h1>Board history</h1>"
            + ("<ul>" + rows + "</ul>" if rows else "<p class='muted'>No boards saved yet.</p>"))
    return html_shell("OLP XDV — history", body)


def render_404_html(date_str: str, today: str) -> str:
    body = (_nav("today", today)
            + "<h1>No board for that date</h1>"
            + "<p class='muted'>NO DATA — PENDING: no board exists for "
            + html.escape(date_str) + " — the run either didn't happen or produced no fixtures.</p>")
    return html_shell("OLP XDV — not found", body)
