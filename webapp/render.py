"""HTML rendering for the OLP XDV web dashboard — ScoreGPT visual language.

Design: dark AI-prediction app modeled on scoregpt.app/ai-football-predictions.
Every league has a header row; each match is a 3-rail card with team rows,
predicted score, AI pick line, model agreement, expandable model picks, win bar,
and market/EV line. NO DATA — PENDING is always shown, never guessed (HR35).
The honest-edge statement and capital authority are never removed.

Fonts: Fraunces (serif display), Inter (body), JetBrains Mono (mono labels).
Self-contained — no external URLs, no CDN (the export test asserts it).
"""
from __future__ import annotations

import html
from datetime import date as _date, datetime

from config import PHASE_LABEL

# ─────────────────────────────────────────────────────────────────────────────
# CSS — ScoreGPT design tokens + component styles (inline, self-contained)
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """
:root{color-scheme:dark;
  --bg:#080b11;--surface:#0e1520;--card:#10161d;
  --border:#141c26;--border-light:rgba(255,255,255,.06);
  --ink:#f2f6ff;--ink-2:#9fb2c3;--ink-3:#808d9b;
  --accent:#00d4aa;--accent-2:#3b82f6;--accent-light:#5cead0;
  --accent-muted:rgba(0,212,170,.10);--accent-soft:rgba(0,212,170,.15);
  --grad:linear-gradient(135deg,#00d4aa 0%,#3b82f6 100%);
  --pick:#5cead0;
  --good:#00c758;--good-bg:#0d2a1a;
  --warning:#f59e0b;--warning-bg:#2b2414;
  --serious:#ff6568;--serious-bg:rgba(255,101,104,.12);
  --sans:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --display:Fraunces,Georgia,"Times New Roman",serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Consolas,monospace;
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:54rem;margin:0 auto;padding:1.4rem 1rem 3rem}
a{color:var(--accent-2)}
h1{font:700 1.2rem var(--display);margin:.2rem 0 .1rem}
h2{font:700 1.05rem var(--display);margin:1.6rem 0 .5rem}
.muted{color:var(--ink-2)}

/* ─── nav ─── */
nav{position:sticky;top:.75rem;z-index:10;display:flex;align-items:center;gap:.9rem;padding:.55rem .9rem;
  background:rgba(14,21,32,.7);backdrop-filter:blur(12px);border:1px solid var(--border-light);
  border-radius:999px;margin-bottom:1.4rem;pointer-events:auto}
.brand{font:700 .95rem/1 var(--display);font-style:italic;text-transform:uppercase;letter-spacing:.06em;
  color:var(--ink);text-decoration:none;white-space:nowrap}
.brand b{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
nav .spacer{flex:1}
nav a.link{font-size:.9rem;color:var(--ink-2);text-decoration:none}
nav a.link:hover{color:var(--ink)}
.nav-cta{background:var(--grad);color:#fff!important;padding:.3rem .85rem;border-radius:999px;
  font-size:.85rem;font-weight:700;text-decoration:none;white-space:nowrap}

/* ─── hero ─── */
.hero{padding:0 0 .8rem;margin-bottom:.6rem}
.hero .stamp{font:.68rem/1 var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--accent);margin-bottom:.5rem}
.hero h1{font:700 1.85rem/1.15 var(--display);margin-bottom:.5rem}
.hero p{color:var(--ink-2);font-size:.95rem;margin:.3rem 0}
.hero .pills{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.8rem}
.pill{display:inline-flex;align-items:center;gap:.3rem;font-size:.78rem;padding:.18rem .55rem;
  border-radius:999px;border:1px solid var(--border);color:var(--ink-2)}
.pill.good{color:var(--good);background:var(--good-bg);border-color:transparent}
.pill.warn{color:var(--warning);background:var(--warning-bg);border-color:transparent}
.pill.grad{border-color:transparent;color:#fff;background:var(--grad)}

/* ─── buttons ─── */
.btn{display:inline-flex;align-items:center;gap:.5rem;background:var(--grad);color:#fff;
  font:700 .9rem/1 var(--sans);padding:.55rem 1.1rem;border-radius:999px;text-decoration:none;margin-top:1rem}
.btn-sub{font-size:.8rem;color:var(--ink-3);margin-top:.35rem}

/* ─── picks card ─── */
.picks{border:1px solid transparent;border-radius:1rem;padding:1rem 1.1rem;margin:.7rem 0 1.2rem;
  background:linear-gradient(var(--card),var(--card)) padding-box,var(--grad) border-box}
.picks h2{margin:0 0 .4rem;font:700 1.05rem var(--display)}
.picks h2 .dot{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;
  background:var(--grad);margin-right:.4rem;vertical-align:1px}
.picks pre{white-space:pre-wrap;margin:0;font:inherit}

/* ─── section / tiles / card ─── */
.section{margin-top:.3rem}
.section-head{display:flex;align-items:baseline;gap:.75rem;margin:1.6rem 0 .8rem}
.section-head h2{margin:0;font:700 1.25rem var(--display)}
.rule{flex:1;height:1px;background:var(--border)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(7.5rem,1fr));gap:.55rem;margin:.9rem 0 1.1rem}
.tile{background:var(--card);border:1px solid var(--border);border-radius:.8rem;padding:.6rem .8rem}
.tile .n{font:700 1.25rem var(--mono)}
.tile .l{font-size:.75rem;color:var(--ink-3)}
.card{background:var(--card);border:1px solid var(--border);border-radius:.9rem;padding:.8rem .9rem;margin:.55rem 0}
.card p{margin:.35rem 0}
.card pre{white-space:pre-wrap;margin:.3rem 0 0;font:inherit}

/* ─── gate bar ─── */
.gatebar{height:.5rem;border-radius:999px;background:var(--surface);overflow:hidden;margin:.35rem 0 .15rem}
.gatebar>i{display:block;height:100%;background:var(--grad);border-radius:999px}

/* ─── league header row ─── */
.league-head{display:flex;align-items:center;gap:.6rem;margin:1.6rem 0 .7rem}
.badge{width:2rem;height:2rem;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font:700 .72rem var(--mono);color:var(--ink-3);background:var(--surface);border:1px solid var(--border);flex:none}
.league-name{font:700 .85rem var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3);margin:0}
.league-count{font:700 .75rem var(--mono);color:var(--ink-3)}

/* ─── match card (3-rail) ─── */
.match{display:flex;background:var(--card);border:1px solid var(--border);border-radius:.9rem;
  overflow:hidden;margin:.55rem 0;transition:border-color .2s}
.match:hover{border-color:var(--accent-muted)}
.match.na{opacity:.72}
.rail-l{width:4.2rem;border-right:1px solid var(--border);padding:.65rem .55rem;text-align:center;flex:none;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.3rem}
.rail-m{flex:1;min-width:0;padding:.65rem .75rem}
.rail-r{width:9rem;border-left:1px solid var(--border);padding:.65rem .65rem;flex:none;
  display:flex;flex-direction:column;gap:.35rem;justify-content:center}
.tag{font:600 .65rem var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.date{font:700 .7rem var(--mono);color:var(--ink-3)}
.tier{font:700 .6rem var(--mono);padding:.1rem .35rem;border-radius:999px;color:var(--accent);
  border:1px solid var(--accent-muted)}
.mrow{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.15rem 0}
.tname{font:600 .92rem/1.2 var(--sans);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.tname.win{color:var(--ink)}
.tname.lose{color:var(--ink-3)}
.score{font:700 .95rem var(--mono);padding:.1rem .35rem;border-radius:.35rem;
  background:var(--surface);min-width:1.6rem;text-align:center}
.score.win{color:var(--ink);background:var(--accent-muted)}
.pick-line{font-size:.82rem;line-height:1.3}
.pick-line .team{color:var(--pick);font-weight:700}
.models{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.3rem}
.chip{font:500 .68rem var(--mono);padding:.12rem .45rem;border-radius:999px;border:1px solid var(--border);
  color:var(--ink-3);background:var(--surface)}
.chip.ok{color:var(--accent);border-color:transparent;background:var(--accent-muted)}
.chip.miss{color:var(--serious);border-color:transparent;background:var(--serious-bg)}
.chip.na{opacity:.55}
.market-line{font-size:.8rem;color:var(--ink-3);margin-top:.35rem;border-top:1px solid var(--border);
  padding-top:.4rem}
.market-line b{color:var(--pick)}
.market-line .ev{color:var(--good);font-weight:700}

/* ─── win bar ─── */
.winbar{display:flex;height:.4rem;border-radius:999px;overflow:hidden;background:var(--surface);margin:.45rem 0 .25rem}
.winbar>i{display:block;height:100%}
.winbar>i.lead{background:var(--grad)}
.winbar>i.mid{background:rgba(255,255,255,.16)}
.winbar-labels{display:flex;justify-content:space-between;font-size:.72rem;color:var(--ink-3);margin-bottom:.15rem}

/* ─── model picks expander ─── */
details.mpicks>summary{font:600 .8rem var(--sans);color:var(--ink-3);cursor:pointer;list-style:none;padding:.2rem 0}
details.mpicks>summary::before{content:"▾ ";color:var(--accent)}
details.mpicks[open]>summary::before{content:"▴ "}
.mpicks-list{list-style:none;margin:0;padding:0}
.mpicks-list li{display:flex;justify-content:space-between;align-items:baseline;font-size:.78rem;padding:.18rem 0;color:var(--ink-2)}
.mpicks-list li span{color:var(--ink-3);font:500 .72rem var(--mono)}
.mpicks-list li b{font:600 .78rem var(--mono);color:var(--ink)}

/* ─── yesterday graded ─── */
.graded .verdict{display:inline-flex;align-items:center;gap:.25rem;padding:.2rem .55rem;
  border-radius:999px;font:700 .7rem var(--sans)}
.verdict.hit{background:var(--accent-muted);color:var(--accent)}
.verdict.miss{background:var(--serious-bg);color:var(--serious)}

/* ─── rolling band ─── */
.rolling{background:var(--card);border:1px solid var(--border);border-radius:.9rem;padding:.8rem .9rem;margin:.6rem 0}
.rolling h3{margin:0 0 .3rem;font:700 .9rem var(--display)}
.rolling p{color:var(--ink-2);font-size:.88rem;margin:.25rem 0}

/* ─── league hubs ─── */
.hubs{display:flex;flex-wrap:wrap;gap:.5rem;margin:.4rem 0 .8rem}
.hub{padding:.4rem .8rem;border-radius:.6rem;border:1px solid var(--border);background:var(--card);
  color:var(--ink-2);font-size:.85rem;text-decoration:none;transition:border-color .2s}
.hub:hover{border-color:var(--accent-muted);color:var(--ink)}

/* ─── methodology steps ─── */
.steps{list-style:none;counter-reset:step;margin:.4rem 0 0;padding:0}
.steps li{counter-increment:step;padding:.55rem 0 .55rem 2.6rem;position:relative;
  font-size:.92rem;color:var(--ink-2);border-bottom:1px solid var(--border)}
.steps li:last-child{border-bottom:none}
.steps li::before{content:counter(step);position:absolute;left:0;top:.55rem;width:1.7rem;height:1.7rem;
  display:flex;align-items:center;justify-content:center;border-radius:999px;
  border:1px solid var(--accent-muted);color:var(--accent);font:700 .78rem var(--mono)}
.steps li strong{color:var(--ink);font-weight:600}
.steps li::after{content:"";position:absolute;left:2.55rem;bottom:-1px;width:0;height:1px;background:var(--border)}
.steps li:last-child::after{display:none}

/* ─── FAQ accordion ─── */
details.faq{border:1px solid var(--border);border-radius:.8rem;background:var(--card);margin:.45rem 0}
details.faq>summary{padding:.65rem .85rem;font:600 .88rem var(--sans);color:var(--ink);cursor:pointer;
  list-style:none;display:flex;align-items:center;gap:.5rem}
details.faq>summary::before{content:"▸";color:var(--accent);font-size:.8rem;flex:none;transition:transform .15s}
details.faq[open]>summary::before{transform:rotate(90deg)}
details.faq p{padding:0 .85rem .7rem;color:var(--ink-2);font-size:.88rem;line-height:1.5}

/* ─── footer ─── */
.foot{margin-top:2.4rem;padding-top:1rem;border-top:1px solid var(--border);
  display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:1rem}
.foot p{margin:.2rem 0;font-size:.85rem;color:var(--ink-3)}
.foot p strong{color:var(--ink-2);font-weight:600}

/* ─── why / stats pages ─── */
h1.serif{font:700 1.5rem var(--display);margin-bottom:.8rem}
.pick{color:var(--accent-light);font-weight:700}

/* ─── NO-DATA card ─── */
.match.na .why{font-size:.8rem;color:var(--serious);margin-top:.2rem}
.match.na .score{color:var(--ink-3);background:var(--surface);opacity:.7}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Page shell
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers (unchanged logic — these carry the test needles)
# ─────────────────────────────────────────────────────────────────────────────

def _pct(x) -> str:
    return "NO DATA — PENDING" if x is None else f"{round(x * 100)}%"


def _short_fixture(fixture: str) -> str:
    return fixture.split(" (")[0]


def _league_of(fixture: str) -> str:
    return fixture.split(" (")[-1].rstrip(")") if " (" in fixture else "—"


def _teams(bf: dict) -> tuple[str, str, str]:
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
    if probs is None:
        return None
    if isinstance(probs, dict):
        ph, pd, pa = probs.get("p_home"), probs.get("p_draw"), probs.get("p_away")
    else:
        # elo_probs / xg_probs arrive as LISTS from the JSON schema (tuples
        # became lists on serialization), so normalise before padding.
        seq = tuple(probs) if isinstance(probs, (tuple, list)) else ()
        ph, pd, pa = (seq + (None, None, None))[:3]
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
    return f"{round(lh)}–{round(la)}"  # en-dash


def _models_agree(bf: dict) -> tuple[int, int, dict]:
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
    labels = (f'<div class="winbar-labels">'
              f'<span>{html.escape(p.get("home_team", ""))} {_pct(ph)}</span>'
              f'<span>Draw {_pct(pd)}</span>'
              f'<span>{_pct(pa)} {html.escape(p.get("away_team", ""))}</span></div>')
    return labels + "".join(out)


def _fmt_ev(ev) -> str:
    return "NO DATA — PENDING" if ev is None else f"{ev:+.0%}"


def _engine_display(key: str) -> str:
    return {"dc": "Dixon-Coles", "cross": "Dixon-Coles (pooled)",
            "elo": "Elo", "xg": "xG", "bookmaker": "Bookmaker",
            "consensus": "Consensus"}.get(key, key)


# ─────────────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────────────

def _nav(active: str, today: str) -> str:
    links = [("today", f"/board/{today}", "Today", False),
             ("history", "/history", "History", False),
             ("stats", "/stats", "Gate", True)]
    parts: list[str] = []
    for key, url, name, is_cta in links:
        if key == active:
            if is_cta:
                parts.append(f'<a class="nav-cta" href="{url}">{name}</a>')
            else:
                parts.append(f'<span class="muted">{name}</span>')
        else:
            if is_cta:
                parts.append(f'<a class="nav-cta" href="{url}">{name}</a>')
            else:
                parts.append(f'<a class="link" href="{url}">{name}</a>')
    return (f'<nav><a class="brand" href="/board/{today}">OLP&nbsp;<b>XDV</b></a>'
            f'<span class="spacer"></span>{" ".join(parts)}</nav>')


def _hero(payload: dict) -> str:
    gate = payload.get("gate", {})
    n = gate.get("legs_with_clv", 0)
    req = gate.get("gate_requirement", 30)
    phase = payload.get("phase") or PHASE_LABEL
    gate_pill = (f'<span class="pill good">✓ gate reached</span>'
                 if gate.get("gate_met_pending_architect_signoff")
                 else f'<span class="pill warn">⏳ {n}/{req} CLV legs</span>')
    pills = (f'<span class="pill">{html.escape(payload.get("date", "?"))}</span>'
             f'<span class="pill">{html.escape(phase)}</span>'
             f'<span class="pill grad">🎯 4 engines · graded in public</span>'
             f'{gate_pill}')
    return f"""<div class="hero">
  <div class="stamp">Updated {html.escape(payload.get("date","?"))} · 07:00 run</div>
  <h1>AI football predictions from 4 competing engines — graded in public</h1>
  <p>Dixon-Coles + Elo + xG + the market's devigged odds, paper-only, logged
     closing-line value toward the Phase 3 capital gate. Honest edge:
     excellent process, NOT a demonstrated profitable edge.</p>
  <div class="pills">{pills}</div>
</div>"""


def _picks_card(recommendation: str) -> str:
    if not recommendation:
        recommendation = "⭐ TODAY'S PICKS\nNO DATA — no eligible pick today."
    lines = [l for l in recommendation.splitlines()
             if not l.startswith("⭐ TODAY'S PICKS")]
    if not lines:
        lines = ["NO DATA — no eligible pick today."]
    lines = [html.escape(l) for l in lines]
    return (f'<div class="picks" id="picks"><h2><span class="dot"></span>TODAY\'S PICKS</h2>'
            f'<pre>{chr(10).join(lines)}</pre></div>')


def _gate_strip(gate: dict, telemetry: dict) -> str:
    n = gate.get("legs_with_clv", 0)
    req = gate.get("gate_requirement", 30)
    pct = min(1.0, n / req) if req else 0.0
    capture = telemetry.get("clv_capture_rate")
    cap_txt = "NO DATA — PENDING" if capture is None else f"{round(capture * 100)}%"
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
  <div class="tile"><div class="n">{telemetry.get("legs_per_day","—") or "—"}</div>
    <div class="l">legs per day</div></div>
</div>
<div class="card">
  <p><strong>Road to the Phase 3 gate</strong> {pill}</p>
  <div class="gatebar" aria-label="{n} of {req}" style="margin-top:.5rem">
    <i style="width:{round(pct*100)}%"></i></div>
  <p class="muted">CLV legs are the only legs that count toward capital —
    capture is {cap_txt} of settled legs.</p>
</div>"""


def _match_card(bf: dict) -> str:
    home, away, league = _teams(bf)
    p = bf.get("probs")
    tier = bf.get("softness_tier", "?")
    kd = bf.get("kickoff_date") or ""
    # Format date for the left rail
    try:
        dt = datetime.strptime(kd, "%Y-%m-%d")
        date_txt = dt.strftime("%a %-d").upper()  # "THU 6"
    except (ValueError, TypeError):
        date_txt = "—"
    # Determine match status tag (UP / LIVE / FT)
    tag = "UP"

    if p is None:
        reason = bf.get("rejection_reason") or "NO DATA — PENDING"
        return f"""<div class="match na">
  <div class="rail-l"><div class="tag">{tag}</div>
    <div class="date">{date_txt}</div>
    <div class="tier">{html.escape(tier)}</div></div>
  <div class="rail-m">
    <div class="mrow"><span class="tname">{html.escape(home)}</span>
      <span class="score">—</span></div>
    <div class="mrow"><span class="tname">{html.escape(away)}</span>
      <span class="score">—</span></div>
  </div>
  <div class="rail-r">
    <div class="pick-line" style="color:var(--ink-3)">NO DATA — PENDING</div>
    <div class="why">⚠ {html.escape(reason)}</div>
  </div>
</div>"""

    agree, total, engines = _models_agree(bf)
    winner = _side_name(bf, _result_side(p))
    # Per-engine chips (TEST NEEDLE: "✓ Dixon-Coles", "✓ Elo", "✓ Bookmaker", "xG —")
    chips = []
    for name, side in engines.items():
        if side is None:
            chips.append(f'<span class="chip na">{html.escape(name)} —</span>')
        elif side == _result_side(p):
            chips.append(f'<span class="chip ok">✓ {html.escape(name)}</span>')
        else:
            chips.append(f'<span class="chip miss">✗ {html.escape(name)}</span>')
    # Market line
    market = ""
    if bf.get("best_market"):
        ev = bf.get("best_mes_ev")
        ev_txt = "NO DATA — PENDING" if ev is None else f"{ev:+.0%} EV"
        market = (f'<div class="market-line">Pick: <b>{html.escape(bf["best_market"])}</b>'
                  f' @ {bf.get("best_price","")} · <span class="ev">{ev_txt}</span>'
                  f' <span class="muted">· {bf.get("best_n_books",0)} book(s)</span></div>')
    # Model picks expander (engine_picks from schema)
    ep = bf.get("engine_picks") or {}
    mp_rows = []
    for ek in ("Dixon-Coles", "Elo", "xG", "Bookmaker"):
        ev_data = ep.get(ek)
        name = html.escape(ek)
        if ev_data is None:
            mp_rows.append(f'<li><span>{name}</span><b class="muted">—</b></li>')
        else:
            result = ev_data.get("result", "?")
            sl = ev_data.get("scala scoreline")
            score_str = f" · {sl[0]}–{sl[1]}" if sl else ""
            mp_rows.append(f'<li><span>{name}</span><b>{html.escape(result)}{score_str}</b></li>')
    model_picks = (f'<details class="mpicks"><summary>Model picks ▾</summary>'
                   f'<ul class="mpicks-list">{"".join(mp_rows)}</ul></details>')
    # Home/away team scores for the middle rail
    lam_h = p.get("lambda_home")
    lam_a = p.get("lambda_away")
    score_h = str(round(lam_h)) if lam_h is not None else "—"
    score_a = str(round(lam_a)) if lam_a is not None else "—"
    return f"""<div class="match">
  <div class="rail-l"><div class="tag">{tag}</div>
    <div class="date">{date_txt}</div>
    <div class="tier">{html.escape(tier)}</div></div>
  <div class="rail-m">
    <div class="mrow"><span class="tname win">{html.escape(home)}</span>
      <span class="score win">{score_h}</span></div>
    <div class="mrow"><span class="tname lose">{html.escape(away)}</span>
      <span class="score lose">{score_a}</span></div>
    {_win_bar(p)}
    <div class="models">{''.join(chips)}</div>
    {market}
  </div>
  <div class="rail-r">
    <div class="pick-line">AI pick: <span class="team">{html.escape(winner)}</span>
      — predicted {_predicted_score(p)}
      <span class="muted">· {agree} of {total} models agree</span></div>
    {model_picks}
    <a href="/why?fixture={html.escape(bf['fixture'])}" style="font-size:.75rem;color:var(--ink-3)">Full analysis →</a>
  </div>
</div>"""


def _the_call(board: list[dict]) -> str:
    rows = [bf for bf in board if bf.get("on_deploy_shortlist")]
    if not rows:
        return ("<div class='card'><p class='muted'>No deploy-eligible call today "
                "(softness A/B only).</p></div>")
    return "".join(_match_card(bf) for bf in rows)


def _league_sections(board: list[dict]) -> str:
    leagues: dict[str, list[dict]] = {}
    for bf in board:
        leagues.setdefault(_league_of(bf["fixture"]), []).append(bf)
    if not leagues:
        return ('<div class="card"><p class="muted">No fixtures in the window '
                'today. On a quiet day the board is honestly near-empty.</p></div>')
    out: list[str] = []
    for league in sorted(leagues, key=lambda L: -len(leagues[L])):
        n = len(leagues[league])
        slug = league.lower().replace(" ", "-")
        out.append(f'<div class="league-head" id="league-{slug}">'
                   f'<span class="badge">{html.escape(_monogram(league))}</span>'
                   f'<span class="league-name">{html.escape(league)}</span>'
                   f'<span class="league-count">({n})</span>'
                   f'<span class="rule"></span></div>')
        for bf in leagues[league]:
            out.append(_match_card(bf))
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# New ScoreGPT sections
# ─────────────────────────────────────────────────────────────────────────────

def _yesterday_graded(rows: list[dict]) -> str:
    if not rows:
        return ('<div class="section"><div class="section-head"><h2>Yesterday — graded</h2>'
                '<span class="rule"></span></div>'
                '<div class="card"><p class="muted">No settled predictions to grade yet.</p></div></div>')
    cards = []
    for g in rows:
        fix = g.get("fixture") or "?"
        outcome = g.get("outcome") or "?"
        home, away = "—", "—"
        if " v " in fix:
            home, away = [s.strip() for s in fix.split(" v ", 1)]
        # Parse FT score
        ht, at = "—", "—"
        if "-" in outcome:
            parts = outcome.split("-")
            ht, at = parts[0].strip(), parts[1].strip() if len(parts) > 1 else "?"
        # Per-engine hits
        engines = g.get("engines") or {}
        engine_items = []
        for ek, markets in engines.items():
            for mk in ("1X2_HOME", "1X2_DRAW", "1X2_AWAY"):
                row = markets.get(mk)
                if row and row.get("hit") is not None:
                    label = _engine_display(ek)
                    icon = "✓" if row["hit"] else "✗"
                    cls = "hit" if row["hit"] else "miss"
                    engine_items.append(
                        f'<div class="graded"><span class="verdict {cls}">{icon} {html.escape(label)}</span></div>')
                    break
        # Determine overall verdict (majority)
        hits = sum(1 for _, markets in engines.items()
                   for mk in ("1X2_HOME", "1X2_DRAW", "1X2_AWAY")
                   if (markets.get(mk) or {}).get("hit"))
        total_e = sum(1 for _, markets in engines.items()
                      for mk in ("1X2_HOME", "1X2_DRAW", "1X2_AWAY")
                      if (markets.get(mk) or {}).get("hit") is not None)
        overall_cls = "hit" if hits > total_e / 2 else "miss" if total_e > 0 else "miss"
        overall_icon = "✓" if overall_cls == "hit" else "✗"
        try:
            dt = datetime.strptime(g.get("match_date", ""), "%Y-%m-%d")
            date_txt = dt.strftime("%a %-d").upper()
        except (ValueError, TypeError):
            date_txt = "—"
        cards.append(f"""<div class="match">
  <div class="rail-l"><div class="tag">FT</div><div class="date">{date_txt}</div></div>
  <div class="rail-m">
    <div class="mrow"><span class="tname win">{html.escape(home)}</span>
      <span class="score win">{html.escape(ht)}</span></div>
    <div class="mrow"><span class="tname lose">{html.escape(away)}</span>
      <span class="score lose">{html.escape(at)}</span></div>
  </div>
  <div class="rail-r">
    <div class="graded"><span class="verdict {overall_cls}">{overall_icon} Hit</span></div>
    {''.join(engine_items)}
  </div>
</div>""")
    return (f'<div class="section"><div class="section-head"><h2>Yesterday — graded</h2>'
            f'<span class="rule"></span></div>{"".join(cards)}</div>')


def _rolling_band(r: dict | None) -> str:
    if not r or not r.get("engines"):
        return (f'<div class="section"><div class="section-head"><h2>Rolling 7 days</h2>'
                f'<span class="rule"></span></div>'
                f'<div class="card"><p class="muted">No run history yet.</p></div></div>')
    engines = r.get("engines", {})
    total_preds = 0
    total_hits = 0
    for ek, st in engines.items():
        s = st.get("settled", 0)
        hr = st.get("hit_rate", 0) or 0
        total_preds += s
        total_hits += round(hr * s)
    if total_preds == 0:
        acc_txt = "NO DATA — PENDING"
    else:
        acc_txt = f"{total_hits} of {total_preds} ({total_hits / total_preds * 100:.1f}%)"
    legs = r.get("legs_logged", 0)
    with_clv = r.get("legs_with_clv", 0)
    gate_req = (r.get("gate") or {}).get("gate_requirement", 30)
    cap = r.get("avg_clv_pct")
    cap_txt = "NO DATA — PENDING" if cap is None else f"{cap:+.2f}%"
    gate_pct = min(1.0, with_clv / gate_req) if gate_req else 0.0
    return f"""<div class="rolling section">
  <h3>Rolling 7 days</h3>
  <p>Rolling 7 days: the board called <strong>{acc_txt}</strong> settled
     predictions correctly. This is the whole public record, not a highlight reel.</p>
  <div class="tiles" style="margin-top:.5rem">
    <div class="tile"><div class="n">{legs}</div><div class="l">legs logged</div></div>
    <div class="tile"><div class="n">{with_clv}</div><div class="l">with CLV</div></div>
    <div class="tile"><div class="n">{cap_txt}</div><div class="l">mean CLV</div></div>
  </div>
  <div class="gatebar" aria-label="{with_clv} of {gate_req}"><i style="width:{round(gate_pct*100)}%"></i></div>
</div>"""


def _league_hubs(payload: dict) -> str:
    leagues = payload.get("leagues_scanned", [])
    if not leagues:
        return ""
    chips = "".join(
        f'<a class="hub" href="#league-{html.escape(league.lower().replace(" ","-"))}">'
        f'AI {html.escape(league)} predictions</a>'
        for league in leagues)
    return (f'<div class="section"><div class="section-head"><h2>League hubs</h2>'
            f'<span class="rule"></span></div>'
            f'<div class="hubs">{chips}</div></div>')


def _methodology() -> str:
    steps = [
        ("Verified data in", "Data ingestion — every league in the whitelist is pulled from verified sources (football-data.co.uk, TheSportsDB, odds feed), with live entry prices attached."),
        ("Independent engines", "Each of the four engines — Dixon-Coles, Elo, xG, and the market's devigged odds — analyses the match independently."),
        ("Consensus vote", "A majority-vote consensus determines the AI pick; each card shows how many engines agree."),
        ("Public grading", "After full-time, every prediction is graded against the real result and recorded in the brain — wins and losses alike."),
    ]
    items = "".join(f'<li><strong>{html.escape(t)}</strong> — {html.escape(d)}</li>' for t, d in steps)
    return (f'<div class="section"><div class="section-head"><h2>How the predictions are made</h2>'
            f'<span class="rule"></span></div>'
            f'<ol class="steps">{items}</ol></div>')


def _faq() -> str:
    qs = [
        ("What is OLP XDV?", "OLP XDV is a Phase 2 football-betting calibration framework. It runs Dixon-Coles, Elo, xG, and devigged bookmaker odds over every fixture across 16 leagues, and logs paper legs with closing-line value toward a 30-leg Phase 3 capital gate."),
        ("Is any money staked?", "No. This is paper-only, zero capital. Capital is hard-blocked below Phase 3. The honest-edge statement at the bottom of every page is the truth, not marketing."),
        ("What is the Phase 3 gate?", "A paper leg only counts toward the capital gate when it has a logged closing line (CLV). The gate requires 30 such legs before staking is considered — and even then, the Architect must explicitly approve."),
        ("What does NO DATA — PENDING mean?", "The framework refused to fabricate a prediction. A team name isn't in the fitted data, a league has no history, or a fixture has no price — the gap is shown, never hidden."),
        ("How is 'graded in public' honest?", "Every settled prediction — wins and losses — is recorded in the brain's predictions table and served on the dashboard. Nothing is deleted, filtered, or reworded after the fact."),
    ]
    items = "".join(
        f'<details class="faq"><summary>{html.escape(q)}</summary>'
        f'<p>{html.escape(a)}</p></details>'
        for q, a in qs)
    return (f'<div class="section"><div class="section-head"><h2>FAQ</h2>'
            f'<span class="rule"></span></div><div style="margin-top:.4rem">{items}</div></div>')


# ─────────────────────────────────────────────────────────────────────────────
# Secondary pages
# ─────────────────────────────────────────────────────────────────────────────

def _flags_block(data_flags: list[str]) -> str:
    if not data_flags:
        return ""
    lis = "".join(f"<li>{html.escape(f)}</li>" for f in data_flags)
    return (f'<div class="section"><div class="section-head"><h2>⚠ {len(data_flags)} data flag(s)</h2>'
            f'<span class="rule"></span></div>'
            f'<details class="faq"><summary>What the framework could not source — shown, never guessed</summary>'
            f'<ul style="padding-left:.9rem;margin:0">{lis}</ul></details></div>')


def _footer(payload: dict) -> str:
    phase = payload.get("phase") or PHASE_LABEL
    return (f'<div class="foot">'
            f'<div><p><strong>Honest edge statement:</strong> this is an excellent informed process, '
            f'but it is NOT a demonstrated profitable edge. The forward paper ledger settles that '
            f'— nothing here is staked.</p></div>'
            f'<div><p><strong>Capital authority:</strong> {html.escape(phase)} — paper only, '
            f'zero capital. Staking is hard-blocked below Phase&nbsp;3.</p></div>'
            f'<div><p class="muted">Board for {html.escape(payload.get("date","?"))} · '
            f'{payload.get("n_leagues","?")} leagues scanned · schema v{payload.get("schema_version","?")}</p></div>'
            f'</div>')


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard composition
# ─────────────────────────────────────────────────────────────────────────────

def render_dashboard(payload: dict) -> str:
    today = payload.get("date", _date.today().isoformat())
    title = f"OLP XDV — {today}"
    board = payload.get("board", [])
    body = (
        _nav("today", today)
        + _hero(payload)
        + _picks_card(payload.get("recommendation", ""))
        + _gate_strip(payload.get("gate", {}), payload.get("telemetry", {}))
        + f'<div class="section"><div class="section-head"><h2>THE CALL</h2><span class="rule"></span></div>'
        + _the_call(board)
        + f'</div><div class="section"><div class="section-head"><h2>Today\'s fixtures</h2><span class="rule"></span></div>'
        + _league_sections(board)
        + f'</div>'
        + _yesterday_graded(payload.get("yesterday_graded", []))
        + _rolling_band(payload.get("rolling_7d"))
        + _league_hubs(payload)
        + _methodology()
        + _faq()
        + _flags_block(payload.get("data_flags", []))
        + _footer(payload))
    return html_shell(title, body)


def render_stats_html(stats_text: str, today: str) -> str:
    body = (_nav("stats", today)
            + '<h1 class="serif">Gate &amp; calibration</h1>'
            + '<div class="card"><pre>' + html.escape(stats_text) + "</pre></div>"
            + '<p class="muted">CLV figures are read from clv/clv_log.json via the brain.</p>')
    return html_shell("OLP XDV — Gate & calibration", body)


def render_why_html(payload: dict, fixture: str) -> str:
    today = payload.get("date", _date.today().isoformat())
    match = next((bf for bf in payload.get("board", [])
                  if fixture in bf.get("fixture", "")), None)
    if match is None:
        body = (_nav("today", today)
                + '<h1 class="serif">No such fixture</h1>'
                + "<p class='muted'>NO DATA — PENDING: no board row matches that fixture.</p>")
        return html_shell("OLP XDV — not found", body)
    p = match.get("probs")
    home, away, league = _teams(match)
    lines = [f'<h1 class="serif">{html.escape(home)} v {html.escape(away)}</h1>',
             f"<div class='muted'>{html.escape(league)} · tier {match.get('softness_tier','?')} · "
             f"{match.get('model_engine','dc')} engine · kickoff {match.get('kickoff_date') or 'NO DATA — PENDING'}</div>"]
    if p is not None:
        agree, total, engines = _models_agree(match)
        lines.append("<div class='card'>"
                     f"<p><strong>Win chance:</strong> {html.escape(p['home_team'])} {_pct(p['p_home'])} · "
                     f"Draw {_pct(p['p_draw'])} · {html.escape(p['away_team'])} {_pct(p['p_away'])}</p>"
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
                     f"{match.get('best_n_books',0)} book(s) quoted.</p></div>")
    if match.get("engine_divergence"):
        lines.append(f"<div class='card'><p class='muted'>⚠ {html.escape(match['engine_divergence'])}</p></div>")
    lines.append(f"<div class='foot'><p class='muted'>Prediction persisted to the brain. "
                 f"Model probability shown is the RAW model_prob — recalibration deltas "
                 f"(cal_adjustment {match.get('cal_adjustment')}) apply only to THE CALL's EV, "
                 f"never the ledger.</p></div>")
    return html_shell("OLP XDV — fixture", _nav("today", today) + "".join(lines))


def render_history_html(dates: list[str], today: str) -> str:
    rows = "".join(f"<li style='padding:.3rem 0'><a href='/board/{d}'>{d}</a></li>" for d in dates)
    body = (_nav("history", today)
            + '<h1 class="serif">Board history</h1>'
            + ("<ul style='list-style:none;padding:0;margin:0'>" + rows + "</ul>"
               if rows else "<p class='muted'>No boards saved yet.</p>"))
    return html_shell("OLP XDV — history", body)


def render_404_html(date_str: str, today: str) -> str:
    body = (_nav("today", today)
            + '<h1 class="serif">No board for that date</h1>'
            + '<p class="muted">NO DATA — PENDING: no board exists for '
            + html.escape(date_str) + " — the run either didn't happen or produced no fixtures.</p>")
    return html_shell("OLP XDV — not found", body)
