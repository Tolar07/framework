"""HTML rendering for the web dashboard — plain-language, phone-first,
dark card design.

Design language: a dark AI-prediction app (card per match: league badge,
teams with the predicted score between them, a win-probability bar, "AI pick:
X — N of M models agree", per-model chips for our three competing engines —
Dixon-Coles, Elo, xG). This is OUR implementation of a generic design pattern
with OUR data and OUR wording; nothing is copied from any external product.

The voice stays the same as the board/Telegram (the Architect is
non-technical): predictions in words, NO DATA — PENDING for anything missing
(HR35 — never a guess), and the honest-edge statement + capital authority are
always present.

Colours follow the dataviz method: the accent highlights the leading side
(the pick); the other win-bar segments are neutral. Status colours
(good / warning / serious) are the validated dark steps and always ship with
an icon AND a label, never colour alone. League identity is carried by a
monogram badge + name (text), never by colour.
"""
from __future__ import annotations

import html
from datetime import date as _date

from config import PHASE_LABEL

# ---------------------------------------------------------------------------
# Dark theme — app chrome + validated status roles (light mode removed: this
# is deliberately a dark app). Status colours below are the dataviz-validated
# dark steps; each is used with an icon+label.
# ---------------------------------------------------------------------------
_CSS = """
:root { color-scheme: dark;
  --bg:        #0d1017;
  --surface:   #151a24;
  --surface-2: #1c2331;
  --border:    rgba(255,255,255,0.09);
  --ink:       #f2f4f8;
  --ink-2:     #97a1b3;
  --accent:    #7c5cff;
  --accent-2:  #3b82f6;
  --grad:      linear-gradient(135deg, #7c5cff 0%, #3b82f6 100%);
  --pick:      #c4b5fd;
  --good:      #6fd26f;   --good-bg:    #17301c;
  --warning:   #f3bf3f;   --warning-bg: #2b2414;
  --serious:   #f09672;   --serious-bg: #2c1f19;
  --mono:      ui-monospace, SFMono-Regular, Consolas, monospace;
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin:0; background:var(--bg); color:var(--ink);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased; }
.wrap { max-width: 52rem; margin: 0 auto; padding: 0 1rem 3rem; }
h1 { font-size: 1.3rem; margin: .2rem 0 .1rem; }
h2 { font-size: 1.05rem; margin: 1.6rem 0 .5rem; }
.muted { color: var(--ink-2); }
a { color: var(--accent-2); }
small { color: var(--ink-2); }

/* --- top nav --- */
nav { display:flex; align-items:center; gap:.9rem; padding:.7rem 0;
  border-bottom:1px solid var(--border); margin-bottom:1.1rem; }
.brand { font-weight:800; letter-spacing:.06em; color:var(--ink);
  text-decoration:none; font-size:.95rem; }
.brand b { background:var(--grad); -webkit-background-clip:text;
  background-clip:text; color:transparent; }
nav .spacer { flex:1; }
nav a.link, nav span.muted { font-size:.9rem; text-decoration:none; }
nav a.link { color: var(--ink-2); }
nav a.link:hover { color: var(--ink); }

/* --- hero --- */
.hero { background:var(--surface); border:1px solid var(--border);
  border-radius:1rem; padding:1.1rem 1.2rem; margin-bottom:1.1rem; }
.hero .stamp { font-size:.8rem; color:var(--ink-2); margin-bottom:.35rem; }
.hero h1 { margin:.1rem 0 .35rem; }
.hero p { margin:.25rem 0 0; color:var(--ink-2); font-size:.95rem; }
.hero .pills { display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.7rem; }
.pill { display:inline-flex; align-items:center; gap:.3rem; font-size:.78rem;
  padding:.18rem .55rem; border-radius:999px; border:1px solid var(--border);
  color:var(--ink-2); }
.pill.good { color:var(--good); background:var(--good-bg); border-color:transparent; }
.pill.warn { color:var(--warning); background:var(--warning-bg); border-color:transparent; }
.pill.grad { border-color:transparent; color:#fff;
  background:linear-gradient(135deg,#7c5cff,#3b82f6); }

/* --- stat tiles --- */
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(8rem,1fr));
  gap:.6rem; margin:.9rem 0 1.2rem; }
.tile { background:var(--surface); border:1px solid var(--border);
  border-radius:.8rem; padding:.6rem .8rem; }
.tile .n { font-size:1.35rem; font-weight:700; }
.tile .l { font-size:.75rem; color:var(--ink-2); }
.tile.good .n { color:var(--good); }

/* --- cards --- */
.card { background:var(--surface); border:1px solid var(--border);
  border-radius:1rem; padding:.9rem 1rem; margin:.7rem 0; }
.card p { margin:.35rem 0; }
.card pre { white-space:pre-wrap; margin:.3rem 0 0; font: inherit; }

/* --- TODAY'S PICKS parlay --- */
.picks { border:1px solid transparent; background:
  linear-gradient(var(--surface),var(--surface)) padding-box,
  var(--grad) border-box; border-radius:1rem; padding:1rem 1.1rem; margin:.7rem 0 1.2rem; }
.picks h2 { margin:0 0 .4rem; }
.picks h2 .dot { display:inline-block; width:.55rem; height:.55rem; border-radius:50%;
  background:var(--grad); margin-right:.4rem; vertical-align:1px; }
.picks pre { white-space:pre-wrap; margin:0; font-size:.98rem; color:var(--ink); }

/* --- league section --- */
.league-head { display:flex; align-items:center; gap:.6rem; margin:1.5rem 0 .6rem; }
.badge { width:2rem; height:2rem; border-radius:50%; display:flex; align-items:center;
  justify-content:center; font-size:.72rem; font-weight:700; color:var(--ink-2);
  background:var(--surface-2); border:1px solid var(--border); flex:none; }
.league-head h2 { margin:0; font-size:1.02rem; }
.league-head .count { font-size:.78rem; color:var(--ink-2); }

/* --- match card --- */
.match { background:var(--surface); border:1px solid var(--border);
  border-radius:1rem; padding:.8rem .95rem; margin:.55rem 0; }
.match .top { display:flex; align-items:center; gap:.5rem; font-size:.75rem;
  color:var(--ink-2); margin-bottom:.5rem; }
.match .top .badge { width:1.3rem; height:1.3rem; font-size:.55rem; }
.match .top .tier { margin-left:auto; }
.match .teams { display:grid; grid-template-columns:1fr auto 1fr; align-items:center;
  gap:.6rem; }
.match .side { min-width:0; }
.match .side.right { text-align:right; }
.match .side .name { font-weight:700; font-size:.98rem; line-height:1.25; }
.match .side .sub { font-size:.72rem; color:var(--ink-2); }
.match .score { font-family:var(--mono); font-size:1.25rem; font-weight:700;
  color:var(--ink); background:var(--surface-2); border:1px solid var(--border);
  border-radius:.6rem; padding:.15rem .55rem; text-align:center; }
/* win-probability bar — the leading side carries the accent, the rest neutral */
.winbar { display:flex; height:.5rem; border-radius:999px; overflow:hidden;
  background:var(--surface-2); margin:.65rem 0 .4rem; }
.winbar i { display:block; height:100%; }
.winbar i.lead { background:var(--grad); }
.winbar i.mid  { background:rgba(255,255,255,0.16); }
.pick-line { font-size:.92rem; margin:.2rem 0; }
.pick-line .team { color:var(--pick); font-weight:700; }
.models { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.55rem; }
.chip { font-size:.72rem; padding:.12rem .5rem; border-radius:999px;
  border:1px solid var(--border); color:var(--ink-2); background:var(--surface-2); }
.chip.ok { color:var(--good); border-color:transparent; background:var(--good-bg); }
.chip.miss { color:var(--serious); border-color:transparent; background:var(--serious-bg); }
.chip.na { opacity:.6; }
.market-line { margin-top:.55rem; font-size:.85rem; color:var(--ink-2);
  border-top:1px solid var(--border); padding-top:.5rem; }
.market-line b { color:var(--pick); }
.market-line .ev { color:var(--good); font-weight:700; }
/* NO DATA card — shown, not dropped (HR35) */
.match.na { opacity:.75; }
.match.na .why { font-size:.8rem; color:var(--serious); }

/* --- flags --- */
details { font-size:.85rem; }
summary { cursor:pointer; color:var(--ink-2); }
li { margin:.2rem 0; }

/* --- gate bar --- */
.gatebar { height:.55rem; background:var(--surface-2); border-radius:999px;
  overflow:hidden; margin:.35rem 0 .15rem; }
.gatebar > i { display:block; height:100%; background:var(--grad); border-radius:999px; }

/* --- footer --- */
.foot { margin-top:2.2rem; padding-top:.7rem; border-top:1px solid var(--border);
  font-size:.85rem; color:var(--ink-2); }
"""


def html_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
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
            parts.append(f'<a class="link" href="{url}">{name}</a>')
    return (f'<nav><a class="brand" href="/board/{today}">OLP&nbsp;<b>XDV</b></a>'
            f'<span class="spacer"></span>{" ".join(parts)}</nav>')


def _pct(x) -> str:
    return "NO DATA — PENDING" if x is None else f"{round(x * 100)}%"


def _short_fixture(fixture: str) -> str:
    return fixture.split(" (")[0]


def _league_of(fixture: str) -> str:
    return fixture.split(" (")[-1].rstrip(")") if " (" in fixture else "—"


def _teams(bf: dict) -> tuple[str, str, str]:
    """(home, away, league) — probs carry the real names (aliases resolved)."""
    league = _league_of(bf.get("fixture", ""))
    p = bf.get("probs")
    if p and p.get("home_team") and p.get("away_team"):
        return p["home_team"], p["away_team"], league
    short = _short_fixture(bf.get("fixture", "? v ?"))
    if " v " in short:
        h, a = [s.strip() for s in short.split(" v ", 1)]
        return h, a, league
    return short, "—", league


def _monogram(league: str) -> str:
    words = [w for w in league.replace("-", " ").split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def _result_side(probs) -> str | None:
    """'home' | 'draw' | 'away' for a probs dict or (h,d,a) tuple, else None."""
    if probs is None:
        return None
    if isinstance(probs, dict):
        ph, pd, pa = probs.get("p_home"), probs.get("p_draw"), probs.get("p_away")
    else:
        # the schema serializes elo/xg tuples as LISTS in the JSON
        seq = probs if isinstance(probs, (tuple, list)) else ()
        ph = seq[0] if len(seq) > 0 else None
        pd = seq[1] if len(seq) > 1 else None
        pa = seq[2] if len(seq) > 2 else None
    if ph is None or pd is None or pa is None:
        return None
    m = max(ph, pd, pa)
    return "home" if m == ph else ("draw" if m == pd else "away")


def _side_name(bf: dict, side: str) -> str:
    home, away, _ = _teams(bf)
    return {"home": home, "away": away, "draw": "Draw"}.get(side, "—")


def _predicted_score(p: dict) -> str:
    lh, la = p.get("lambda_home"), p.get("lambda_away")
    if lh is None or la is None:
        return "—"
    return f"{round(lh)}–{round(la)}"


def _models_agree(bf: dict) -> tuple[int, int, dict]:
    """(agree, total, per-engine) — how many of the up-to-4 voters pick the
    same result as the DC lead. Voters: Dixon-Coles, Elo, xG, and the
    bookmaker's devigged implied 1X2 (market_probs, ID413). `total` counts
    voters with an opinion (DC always)."""
    dc = _result_side(bf.get("probs"))
    elo = _result_side(bf.get("elo_probs"))
    xg = _result_side(bf.get("xg_probs"))
    mkt = _result_side(bf.get("market_probs"))
    engines = {"Dixon-Coles": dc, "Elo": elo, "xG": xg, "Bookmaker": mkt}
    agree = sum(1 for s in engines.values() if s is not None and s == dc)
    total = sum(1 for s in engines.values() if s is not None)
    return agree, total, engines


def _win_bar(p: dict) -> str:
    ph, pd, pa = p.get("p_home"), p.get("p_draw"), p.get("p_away")
    if ph is None or pd is None or pa is None:
        return '<div class="winbar"><i class="mid" style="width:100%"></i></div>'
    lead = max(ph, pd, pa)
    lead_i = ph if lead == ph else (1 if lead == pd else 2)
    segs = [ph, pd, pa]
    out = ['<div class="winbar">']
    for i, s in enumerate(segs):
        w = max(2.0, s * 100)
        cls = "lead" if i == lead_i else "mid"
        out.append(f'<i class="{cls}" style="width:{w:.1f}%"></i>')
    out.append("</div>")
    # the three odds, leading one labelled with its side
    labels = f"""<div class="muted" style="font-size:.78rem;display:flex;justify-content:space-between;margin-bottom:.3rem">
<span>{html.escape(p.get('home_team','Home'))} {_pct(ph)}</span>
<span>Draw {_pct(pd)}</span>
<span>{_pct(pa)} {html.escape(p.get('away_team','Away'))}</span></div>"""
    return labels + "".join(out)


def _match_card(bf: dict) -> str:
    league = _league_of(bf.get("fixture", ""))
    home, away, _ = _teams(bf)
    p = bf.get("probs")
    tier = bf.get("softness_tier", "?")
    date_txt = bf.get("kickoff_date") or "—"
    badge = f'<span class="badge">{html.escape(_monogram(league))}</span>'

    if p is None:
        reason = bf.get("rejection_reason") or "NO DATA — PENDING"
        return f"""<div class="match na">
  <div class="top">{badge}<span>{html.escape(league)}</span>
    <span class="tier">tier {html.escape(tier)} · {html.escape(date_txt)}</span></div>
  <div class="teams">
    <div class="side"><div class="name">{html.escape(home)}</div></div>
    <div class="score">NO&nbsp;DATA</div>
    <div class="side right"><div class="name">{html.escape(away)}</div></div>
  </div>
  <div class="why">⚠ {html.escape(reason)}</div>
</div>"""

    agree, total, engines = _models_agree(bf)
    winner = _side_name(bf, _result_side(p))
    agree_txt = (f"{agree} of {total} models agree" if agree == total
                 else f"{agree} of {total} models agree")
    chips = []
    for name, side in engines.items():
        if side is None:
            chips.append(f'<span class="chip na">{html.escape(name)} —</span>')
        elif side == _result_side(p):
            chips.append(f'<span class="chip ok">✓ {html.escape(name)}</span>')
        else:
            chips.append(f'<span class="chip miss">✗ {html.escape(name)}</span>')
    market = ""
    if bf.get("best_market"):
        ev = bf.get("best_mes_ev")
        ev_txt = "NO DATA — PENDING" if ev is None else f"{ev:+.0%} EV"
        market = (f'<div class="market-line">Pick: <b>{html.escape(bf["best_market"])}</b>'
                  f' @ {bf["best_price"]} · <span class="ev">{ev_txt}</span>'
                  f' <span class="muted">· {bf["best_n_books"]} book(s)</span></div>')
    link = f'/why?fixture={html.escape(bf["fixture"])}'
    return f"""<div class="match">
  <div class="top">{badge}<span>{html.escape(league)}</span>
    <span class="tier">tier {html.escape(tier)} · {html.escape(date_txt)}</span></div>
  <div class="teams">
    <div class="side"><div class="name">{html.escape(home)}</div>
      <div class="sub">home</div></div>
    <div class="score">{_predicted_score(p)}</div>
    <div class="side right"><div class="name">{html.escape(away)}</div>
      <div class="sub">away</div></div>
  </div>
  {_win_bar(p)}
  <div class="pick-line">AI pick: <span class="team">{html.escape(winner)}</span>
    <span class="muted">· {agree_txt}</span></div>
  <div class="models">{''.join(chips)}</div>
  {market}
  <div class="top" style="margin-top:.5rem;margin-bottom:0">
    <a href="{link}">Full analysis →</a></div>
</div>"""


def _league_sections(board: list[dict]) -> str:
    leagues: dict[str, list[dict]] = {}
    for bf in board:
        leagues.setdefault(_league_of(bf["fixture"]), []).append(bf)
    if not leagues:
        return '<div class="card"><p class="muted">No fixtures in the window today. ' \
               'On a quiet day the board is honestly near-empty.</p></div>'
    out: list[str] = []
    for league in sorted(leagues, key=lambda L: -len(leagues[L])):
        n = len(leagues[league])
        out.append(f'<div class="league-head"><span class="badge">'
                   f'{html.escape(_monogram(league))}</span>'
                   f'<h2>{html.escape(league)}</h2>'
                   f'<span class="count">{n} fixture{"s" if n != 1 else ""}</span></div>')
        for bf in leagues[league]:
            out.append(_match_card(bf))
    return "".join(out)


def _the_call(board: list[dict]) -> str:
    rows = [bf for bf in board if bf.get("on_deploy_shortlist")]
    if not rows:
        return '<div class="card"><p class="muted">No deploy-eligible call today ' \
               '(softness A/B only).</p></div>'
    cards = "".join(_match_card(bf) for bf in rows)
    return cards


def _gate_strip(gate: dict, telemetry: dict) -> str:
    n = gate.get("legs_with_clv", 0)
    req = gate.get("gate_requirement", 30)
    pct = min(1.0, n / req) if req else 0.0
    capture = telemetry.get("clv_capture_rate")
    cap_txt = ("NO DATA — PENDING" if capture is None
               else f"{round(capture * 100)}%")
    days = telemetry.get("days_to_gate")
    days_txt = "NO DATA — PENDING" if days is None else f"~{days} days"
    met = gate.get("gate_met_pending_architect_signoff")
    pill = ('<span class="pill good">✓ gate reached — ARCHITECT sign-off pending</span>'
            if met else '<span class="pill warn">⏳ paper calibration</span>')
    return f"""<div class="tiles">
  <div class="tile"><div class="n">{n}<small> / {req}</small></div>
    <div class="l">legs with CLV</div></div>
  <div class="tile"><div class="n">{cap_txt}</div>
    <div class="l">closing-line capture</div></div>
  <div class="tile"><div class="n">{days_txt}</div>
    <div class="l">projected to gate</div></div>
  <div class="tile"><div class="n">{telemetry.get('legs_per_day', '—') or '—'}</div>
    <div class="l">legs per day</div></div>
</div>
<div class="card">
  <p><strong>Road to the Phase 3 gate</strong> {pill}</p>
  <div class="gatebar" aria-label="{n} of {req}" style="margin-top:.5rem">
    <i style="width:{round(pct*100)}%"></i></div>
  <p class="muted">CLV legs are the only legs that count toward capital —
    capture is {cap_txt} of settled legs.</p>
</div>"""


def _picks_card(recommendation: str) -> str:
    if not recommendation:
        recommendation = "⭐ TODAY'S PICKS\nNO DATA — no eligible pick today."
    lines = [l for l in recommendation.splitlines()
             if not l.startswith("⭐ TODAY'S PICKS")]  # title lives in the header
    if not lines:
        lines = ["NO DATA — no eligible pick today."]
    lines = [html.escape(l) for l in lines]
    return (f'<div class="picks"><h2><span class="dot"></span>TODAY\'S PICKS</h2>'
            f'<pre>{chr(10).join(lines)}</pre></div>')


def _hero(payload: dict) -> str:
    gate = payload.get("gate", {})
    n, req = gate.get("legs_with_clv", 0), gate.get("gate_requirement", 30)
    phase = payload.get("phase") or PHASE_LABEL
    pills = [f'<span class="pill">📅 {html.escape(payload.get("date","?"))}</span>',
             f'<span class="pill">🔒 {html.escape(phase)}</span>',
             f'<span class="pill grad">🎯 4 engines · graded in public</span>',
             (f'<span class="pill good">✓ gate {n}/{req} legs</span>'
              if n >= req else f'<span class="pill warn">⏳ {n}/{req} CLV legs</span>')]
    return f"""<div class="hero">
  <div class="stamp">Updated {html.escape(payload.get('date','?'))} · daily 07:00 run</div>
  <h1>AI football predictions from 4 competing engines — graded in public</h1>
  <p>Dixon-Coles + Elo + xG + the market's devigged odds, paper-only, logged
     closing-line value toward the Phase 3 capital gate. Honest edge:
     excellent process, NOT a demonstrated profitable edge.</p>
  <div class="pills">{''.join(pills)}</div>
</div>"""


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
        + _hero(payload)
        + _picks_card(payload.get("recommendation", ""))
        + _gate_strip(payload.get("gate", {}), payload.get("telemetry", {}))
        + "<h2>THE CALL</h2>" + _the_call(payload.get("board", []))
        + "<h2>Today's fixtures</h2>" + _league_sections(payload.get("board", []))
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
    home, away, league = _teams(match)
    lines = [f"<h1>{html.escape(home)} v {html.escape(away)}</h1>",
             f"<div class='muted'>{html.escape(league)} · tier {match.get('softness_tier','?')} · "
             f"{match.get('model_engine','dc')} engine · kickoff {match.get('kickoff_date') or 'NO DATA — PENDING'}</div>"]
    if p is not None:
        agree, total, engines = _models_agree(match)
        lines.append("<div class='card'>"
                     f"<p><strong>Win chance:</strong> {html.escape(home)} {_pct(p['p_home'])} · "
                     f"Draw {_pct(p['p_draw'])} · {html.escape(away)} {_pct(p['p_away'])}</p>"
                     f"<p class='muted'>Predicted score ≈ {_predicted_score(p)} · Over 1.5 {_pct(p['p_over_15'])} · "
                     f"Over 2.5 {_pct(p['p_over_25'])} · BTTS {_pct(p['p_btts_yes'])}</p>"
                     f"<p class='pick-line'>AI pick: {html.escape(_side_name(match, _result_side(p)))} "
                     f"<span class='muted'>· {agree} of {total} models agree</span></p>"
                     f"<div class='models'>" + "".join(
                         f'<span class="chip {"ok" if s == _result_side(p) else ("na" if s is None else "miss")}">'
                         f'{"✓" if s == _result_side(p) else ("—" if s is None else "✗")} '
                         f'{html.escape(name)}</span>' for name, s in engines.items()) + "</div>"
                     "</div>")
    else:
        lines.append(f"<div class='card'><p class='muted'><strong>NO DATA — PENDING</strong></p>"
                     f"<p>{html.escape(match.get('rejection_reason') or 'no fitted history')}</p></div>")
    if match.get("best_market"):
        lines.append("<div class='card'><p><strong>Best available market:</strong> "
                     f"{html.escape(match['best_market'])} @ {match['best_price']} "
                     f"(model {_pct(match['best_model_prob'])}, EV "
                     f"<span class='pick'>{_fmt_ev(match['best_mes_ev'])}</span>).</p>"
                     f"<p class='muted'>Bookmaker: {html.escape(match['best_bookmaker'] or '—')} · "
                     f"{match['best_n_books']} book(s) quoted.</p></div>")
    if match.get("engine_divergence"):
        lines.append(f"<div class='card'><p class='muted'>⚠ {html.escape(match['engine_divergence'])}</p></div>")
    lines.append(f"<div class='foot'><p class='muted'>Prediction persisted to the brain. "
                 f"Model probability shown is the RAW model_prob — recalibration deltas "
                 f"(cal_adjustment {match.get('cal_adjustment')}) apply only to THE CALL's EV, "
                 f"never the ledger.</p></div>")
    return html_shell("OLP XDV — fixture", _nav("today", today) + "".join(lines))


def _fmt_ev(ev) -> str:
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
