"""HTML rendering for the OLP XDV web dashboard — the Architect's two-tier
design (reference: webapp/design_reference/*.html, ratified 2026-08-07).

Two views share one visual language:

  render_dashboard(payload)       — the PUBLIC /dashboard (client view)
  render_admin_dashboard(payload) — the authed /admin (client + internals)

DATA-LEAK BOUNDARY: the client view is fed by schema.trim_payload(), so it
never contains a model internal by construction (Architect order 2026-08-07):
no Elo/xG second opinions, no engine divergence, no consensus votes, no
verification, no EV verdicts, no gate/calibration/flags. The admin view renders
the full payload. The client's full-analysis market grid is derived from the
market probabilities alone, so the grid needs nothing the client is denied.

HR35 is kept throughout — missing data reads NO DATA — PENDING, never a guess.
The honest-edge statement and capital authority live on /admin only (the
Architect's explicit choice: the public client view matches the approved HTML
exactly and omits them).

Fonts: Barlow Condensed (display), Inter (body), IBM Plex Mono (numbers) via
Google Fonts with system fallbacks (Architect approved the CDN).
"""
from __future__ import annotations

import html
from datetime import date as _date, datetime

# Google Fonts (Architect-approved): degrade gracefully to the system stacks
# below when offline.
_FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">"""

# ─────────────────────────────────────────────────────────────────────────────
# CSS — the ratified design tokens + components (admin superset; the client
# view simply never uses the admin-only classes)
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """
:root{
  --bg:#0B0E13;
  --surface:#131822;
  --surface-2:#1A2130;
  --line:#232B3B;
  --ink:#E7EAF0;
  --ink-dim:#8B93A6;
  --ink-faint:#565F72;
  --amber:#D8A659;
  --amber-dim:#8C744A;
  --teal:#4FB894;
  --coral:#E2634F;
  --violet:#9089D6;
  --radius:10px;
}
*{box-sizing:border-box;}
body{
  margin:0;
  background:
    radial-gradient(circle at 15% 0%, #161d2b 0%, transparent 45%),
    var(--bg);
  color:var(--ink);
  font-family:'Inter',sans-serif;
  -webkit-font-smoothing:antialiased;
  padding:0 0 80px 0;
}
.mono{font-family:'IBM Plex Mono',monospace;}
.display{font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; letter-spacing:0.02em;}

header.top{
  max-width:720px;margin:0 auto;padding:28px 20px 18px 20px;
  border-bottom:1px solid var(--line);
}
.brand{display:flex;align-items:baseline;gap:10px;}
.brand .mark{
  width:8px;height:8px;background:var(--amber);border-radius:1px;
  transform:rotate(45deg);flex:none;
}
.brand h1{font-size:22px;font-weight:700;margin:0;letter-spacing:0.04em;}
.brand .phase{
  font-size:11px;color:var(--amber);border:1px solid var(--amber-dim);
  padding:2px 8px;border-radius:20px;margin-left:auto;font-family:'IBM Plex Mono',monospace;
}
.meta-row{display:flex;gap:18px;margin-top:12px;font-size:12.5px;color:var(--ink-dim);flex-wrap:wrap;}
.meta-row b{color:var(--ink);font-weight:600;}
.paper-strip{
  max-width:720px;margin:0 auto;padding:9px 20px;background:#1E1710;
  border-bottom:1px solid #3A2E18;color:#D8A659;font-size:12px;text-align:center;
  letter-spacing:0.03em;
}

main{max-width:720px;margin:0 auto;padding:0 20px;}
section{margin-top:34px;}
.sec-head{display:flex;align-items:baseline;gap:10px;margin-bottom:4px;}
.sec-head h2{font-size:20px;margin:0;font-weight:700;letter-spacing:0.01em;}
.sec-sub{font-size:12.5px;color:var(--ink-faint);margin:0 0 14px 0;}
.cap-pill{
  font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--ink-dim);
  border:1px solid var(--line);padding:2px 7px;border-radius:20px;
}

/* THE CALL — deploy shortlist cards */
.call-card{
  background:linear-gradient(180deg,#161C29,var(--surface));
  border:1px solid var(--line);border-left:3px solid var(--amber);
  border-radius:var(--radius);padding:16px 16px 14px 16px;margin-bottom:12px;
  cursor:pointer;transition:border-color 0.15s;
}
.call-card:hover{border-color:var(--amber-dim);}
.call-card .expand-hint{
  font-size:10.5px;color:var(--ink-faint);margin-top:10px;
  display:flex;align-items:center;gap:5px;
}
.call-card .expand-hint .chevron{transition:transform 0.2s;}
.call-card.open .expand-hint .chevron{transform:rotate(90deg);}
.full-analysis{
  display:none;margin-top:14px;padding-top:14px;border-top:1px solid var(--line);
}
.call-card.open .full-analysis{display:block;}
.market-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;}
.market-row{
  display:flex;justify-content:space-between;font-size:12.5px;
  padding:6px 0;border-bottom:1px solid var(--line);
}
.market-row .m-name{color:var(--ink-dim);}
.market-row .m-val{font-family:'IBM Plex Mono',monospace;color:var(--ink);font-weight:600;}
.internals{
  margin-top:14px;padding:12px;background:#0E1219;border:1px dashed var(--line);
  border-radius:8px;
}
.internals .int-head{
  font-size:10px;color:var(--violet);text-transform:uppercase;letter-spacing:0.06em;
  margin-bottom:8px;font-family:'IBM Plex Mono',monospace;
}
.internals .int-row{font-size:12px;color:var(--ink-dim);padding:4px 0;line-height:1.5;}
.internals .int-row b{color:var(--ink);}
.divergence-warn{color:#E2634F;}
@media (max-width:480px){.market-grid{grid-template-columns:1fr;}}

.call-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;}
.fixture-name{font-size:16px;font-weight:600;}
.league-tag{font-size:11px;color:var(--ink-faint);margin-top:2px;}
.tier-badge{
  font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--bg);
  background:var(--amber);padding:3px 8px;border-radius:4px;font-weight:600;flex:none;
}
.pick-line{
  margin-top:12px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
}
.pick-label{font-size:14px;color:var(--ink);}
.pick-prob{font-family:'IBM Plex Mono',monospace;color:var(--teal);font-size:14px;font-weight:600;}
.trigger{
  margin-left:auto;text-align:right;font-family:'IBM Plex Mono',monospace;
}
.trigger .num{color:var(--amber);font-size:15px;font-weight:600;}
.trigger .lbl{font-size:9.5px;color:var(--ink-faint);letter-spacing:0.06em;text-transform:uppercase;}
.stamp-row{margin-top:10px;display:flex;gap:8px;align-items:center;}
.stamp{
  width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;flex:none;
}
.stamp.verified{background:rgba(79,184,148,0.15);color:var(--teal);border:1px solid var(--teal);}
.stamp.single{background:rgba(216,166,89,0.12);color:var(--amber);border:1px solid var(--amber-dim);}
.stamp.warn{background:rgba(226,99,79,0.15);color:var(--coral);border:1px solid var(--coral);}
.stamp.na{background:rgba(86,95,114,0.15);color:var(--ink-faint);border:1px solid var(--line);}
.stamp-note{font-size:11px;color:var(--ink-faint);}

/* THE SCAN — wide table */
.scan-table{width:100%;border-collapse:collapse;font-size:12.5px;}
.scan-table th{
  text-align:left;font-family:'IBM Plex Mono',monospace;font-size:10px;
  color:var(--ink-faint);text-transform:uppercase;letter-spacing:0.05em;
  padding:0 8px 8px 8px;font-weight:500;border-bottom:1px solid var(--line);
}
.scan-table td{padding:11px 8px;border-bottom:1px solid var(--line);vertical-align:middle;}
.scan-table tr:last-child td{border-bottom:none;}
.scan-fixture{font-weight:500;color:var(--ink);}
.scan-league{display:block;font-size:10px;color:var(--ink-faint);margin-top:1px;}
.scan-num{font-family:'IBM Plex Mono',monospace;color:var(--ink-dim);white-space:nowrap;}
.scan-num .fav{color:var(--ink);}
.nodata{color:var(--ink-faint);font-style:italic;font-size:11.5px;}
.src-dot{
  width:16px;height:16px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
  font-size:9.5px;font-weight:700;
}
.src-dot.v{background:rgba(79,184,148,0.15);color:var(--teal);}
.src-dot.s{background:rgba(216,166,89,0.12);color:var(--amber);}
.src-dot.n{background:rgba(86,95,114,0.15);color:var(--ink-faint);}
.scan-table tr.clickable{cursor:pointer;transition:background 0.12s;}
.scan-table tr.clickable:hover{background:rgba(216,166,89,0.04);}
.scan-table .chevron{color:var(--ink-faint);font-size:11px;transition:transform 0.2s;display:inline-block;margin-right:6px;}
.scan-table tr.open .chevron{transform:rotate(90deg);}
.detail-row td{padding:0;border-bottom:1px solid var(--line);}
.detail-row .full-analysis{display:none;padding:14px 8px 16px 8px;}
.detail-row.open .full-analysis{display:block;}

/* graded / verify results */
.graded-row{
  display:flex;align-items:center;gap:12px;padding:10px 0;
  border-bottom:1px solid var(--line);font-size:13px;
}
.graded-row:last-child{border-bottom:none;}
.hit-tag,.miss-tag,.pend-tag{
  font-family:'IBM Plex Mono',monospace;font-size:10.5px;font-weight:600;
  padding:2px 7px;border-radius:4px;flex:none;
}
.hit-tag{background:rgba(79,184,148,0.15);color:var(--teal);}
.miss-tag{background:rgba(226,99,79,0.15);color:var(--coral);}
.pend-tag{background:rgba(86,95,114,0.15);color:var(--ink-faint);}
.graded-ft{font-family:'IBM Plex Mono',monospace;color:var(--ink-dim);font-size:12px;margin-left:auto;}

/* data flags */
.flags{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 16px;
}
.flag-line{font-size:12px;color:var(--ink-dim);padding:5px 0;display:flex;gap:8px;}
.flag-line .mk{color:var(--amber);flex:none;}

/* footer honest line */
footer{
  max-width:720px;margin:40px auto 0 auto;padding:18px 20px 0 20px;
  border-top:1px solid var(--line);
}
.honest{
  font-size:12.5px;color:var(--ink-dim);line-height:1.6;text-align:center;
  padding:14px 10px 4px 10px;
}
.honest b{color:var(--ink);}
.gate{
  display:flex;justify-content:center;gap:6px;align-items:center;
  font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--ink-faint);margin-top:10px;
}
.gate .bar{width:90px;height:4px;background:var(--line);border-radius:2px;overflow:hidden;}
.gate .fill{height:100%;background:var(--amber-dim);width:0%;}

@media (max-width:480px){
  .scan-table{font-size:11.5px;}
  .scan-table th:nth-child(4), .scan-table td:nth-child(4){display:none;}
}
"""

_SCAN_JS = """<script>
  function toggleScanRow(id){
    document.getElementById(id).classList.toggle('open');
    event.currentTarget.classList.toggle('open');
  }
</script>"""


def html_shell(title: str, body: str, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{html.escape(title)}</title>
{_FONTS}
<style>{_CSS}</style>
</head><body>
{body}
{script}
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
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


def _friendly_date(d) -> str:
    """ISO date -> 'Thu, 6 Aug 2026' (no platform-specific %-d)."""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(d)
    day = dt.strftime("%d").lstrip("0") or "0"
    return f"{dt.strftime('%a')}, {day} {dt.strftime('%b %Y')}"


def _fmt_price(x) -> str:
    return "—" if x is None else f"{x:g}+"


# ─────────────────────────────────────────────────────────────────────────────
# The full-market grid (derived from market probabilities alone — this is what
# makes the client grid possible without leaking model internals)
# ─────────────────────────────────────────────────────────────────────────────

def _market_rows(p: dict) -> list[tuple[str, str]]:
    """The 10-row full market breakdown: 1X2, goals lines, BTTS, double chance."""
    home = p.get("home_team", "Home")
    away = p.get("away_team", "Away")
    ph, pd, pa = p.get("p_home"), p.get("p_draw"), p.get("p_away")
    o15 = p.get("p_over_15")
    o25 = p.get("p_over_25")
    o35 = p.get("p_over_35")
    btts = p.get("p_btts_yes")

    def P(x) -> str:
        return "—" if x is None else f"{round(x * 100)}%"

    dc1x = None if (ph is None or pd is None) else ph + pd
    dc12 = None if (ph is None or pa is None) else ph + pa
    return [
        (f"{home} to win", P(ph)),
        ("Draw", P(pd)),
        (f"{away} to win", P(pa)),
        ("Over 1.5 goals", P(o15)),
        ("Over 2.5 goals", P(o25)),
        ("Over 3.5 goals", P(o35)),
        ("BTTS Yes", P(btts)),
        ("BTTS No", P(None if btts is None else 1 - btts)),
        ("Double Chance 1X", P(dc1x)),
        ("Double Chance 12", P(dc12)),
    ]


def _market_grid(p: dict) -> str:
    cells = "\n".join(
        f'<div class="market-row"><span class="m-name">{html.escape(name)}</span>'
        f'<span class="m-val">{val}</span></div>'
        for name, val in _market_rows(p))
    return f'<div class="market-grid">\n{cells}\n</div>'


# ─────────────────────────────────────────────────────────────────────────────
# THE SCAN column codes (1X2 / goals / double-chance+BTTS)
# ─────────────────────────────────────────────────────────────────────────────

def _scan_1x2(p: dict) -> str:
    ph, pd, pa = p.get("p_home"), p.get("p_draw"), p.get("p_away")
    if ph is None:
        return "—"
    side, pct = max((("home", ph), ("draw", pd), ("away", pa)), key=lambda t: t[1])
    home = p.get("home_team", "Home")
    away = p.get("away_team", "Away")
    name = {"home": home, "draw": "Draw", "away": away}[side]
    return f'<span class="fav">{html.escape(name)}</span>&nbsp;{round(pct * 100)}%'


def _scan_goals(p: dict) -> str:
    def code(x) -> str:
        if x is None:
            return "—"
        return f"O{round(x * 100)}" if x >= 0.5 else f"U{round((1 - x) * 100)}"

    o15, o25 = p.get("p_over_15"), p.get("p_over_25")
    if o15 is None and o25 is None:
        return "—"
    return f"{code(o15)} / {code(o25)}"


def _scan_dc_btts(p: dict) -> str:
    def dc(x) -> str:
        if x is None:
            return "—"
        return f"1X{round(x * 100)}" if x >= 0.5 else f"X2{round((1 - x) * 100)}"

    def bt(x) -> str:
        if x is None:
            return "—"
        return f"Y{round(x * 100)}" if x >= 0.5 else f"N{round((1 - x) * 100)}"

    ph, pd, pa = p.get("p_home"), p.get("p_draw"), p.get("p_away")
    dc1x = None if (ph is None or pd is None) else ph + pd
    return f"{dc(dc1x)} / {bt(p.get('p_btts_yes'))}"


# ─────────────────────────────────────────────────────────────────────────────
# Pick line + trigger + stamps (admin extras)
# ─────────────────────────────────────────────────────────────────────────────

def _pick(bf: dict) -> tuple[str, str]:
    """(pick label, pick prob) — the market when priced, else the model argmax."""
    label = bf.get("best_market")
    prob = bf.get("best_model_prob")
    if label and prob is not None:
        return label, f"{round(prob * 100)}%"
    p = bf.get("probs")
    if p:
        ph, pd, pa = p.get("p_home"), p.get("p_draw"), p.get("p_away")
        if None not in (ph, pd, pa):
            side, pct = max((("home", ph), ("draw", pd), ("away", pa)), key=lambda t: t[1])
            home, away, _ = _teams(bf)
            name = {"home": home, "draw": "Draw", "away": away}[side]
            return f"{name} to win", f"{round(pct * 100)}%"
    return "NO DATA — PENDING", "—"


def _verification_tier(bf: dict) -> str:
    v = bf.get("verification") or {}
    return (v.get("tier") or "NO_DATA").upper()


def _stamp_row(bf: dict) -> str:
    tier = _verification_tier(bf)
    note = (bf.get("verification") or {}).get("note")
    if tier == "VERIFIED":
        glyph, cls, label = "✓", "verified", "VERIFIED"
    elif tier == "SINGLE_SOURCE":
        glyph, cls, label = "○", "single", "SINGLE-SOURCE"
    elif tier == "CONFLICT":
        glyph, cls, label = "✗", "warn", "CONFLICT"
    else:
        glyph, cls, label = "—", "na", "NO-DATA"
    src = f" — {note}" if note else ""
    return (f'<div class="stamp-row"><span class="stamp {cls}">{glyph}</span>'
            f'<span class="stamp-note">{label}{html.escape(src)}</span></div>')


def _src_dot(bf: dict) -> str:
    tier = _verification_tier(bf)
    if tier == "VERIFIED":
        return '<span class="src-dot v">✓</span>'
    if tier == "SINGLE_SOURCE":
        return '<span class="src-dot s">○</span>'
    return '<span class="src-dot n">—</span>'


def _internals(bf: dict) -> str:
    """Model Internals — ADMIN ONLY. Never rendered by the client view."""
    home, away, _ = _teams(bf)
    p = bf.get("probs")

    def pct(x) -> str:
        return "—" if x is None else f"{round(x * 100)}%"

    lines: list[str] = []
    if p is not None:
        lines.append(
            f'<div class="int-row"><b>Dixon-Coles engine:</b> {html.escape(home)} '
            f'{pct(p.get("p_home"))} / Draw {pct(p.get("p_draw"))} / '
            f'{html.escape(away)} {pct(p.get("p_away"))}</div>')
    elo = bf.get("elo_probs")
    if elo:
        lines.append(
            f'<div class="int-row"><b>Elo second opinion:</b> {html.escape(home)} '
            f'{pct(elo[0])} / Draw {pct(elo[1])} / {html.escape(away)} {pct(elo[2])}</div>')
    div = bf.get("engine_divergence")
    if div:
        warn = ("divergence-warn" if ("⚠" in div or "approaching" in div.lower()
                                      or "V5" in div) else "")
        lines.append(f'<div class="int-row {warn}"><b>Engine divergence:</b> '
                     f'{html.escape(div)}</div>')
    if bf.get("best_market") and bf.get("best_price") is not None:
        ev = bf.get("best_mes_ev")
        ev_txt = ("NO DATA — PENDING" if ev is None
                  else f"EV {ev:+.1%} ({'POSITIVE' if ev >= 0 else 'NEGATIVE'})")
        book = f" ({bf['best_bookmaker']})" if bf.get("best_bookmaker") else ""
        lines.append(f'<div class="int-row"><b>HR30 MES:</b> '
                     f'{html.escape(bf["best_market"])} @ {bf["best_price"]}{book} — {ev_txt}</div>')
    else:
        lines.append('<div class="int-row"><b>HR30 MES:</b> '
                     'NO DATA — PENDING (no live price captured this run)</div>')
    tier = _verification_tier(bf)
    note = (bf.get("verification") or {}).get("note")
    vline = tier.replace("_", " ") + (f" ({note})" if note else "")
    lines.append(f'<div class="int-row"><b>Verification:</b> {html.escape(vline)} '
                 f'— no capital on this alone</div>')
    return ('<div class="internals"><div class="int-head">Model Internals — '
            'admin only</div>' + "".join(lines) + "</div>")


# ─────────────────────────────────────────────────────────────────────────────
# THE CALL cards
# ─────────────────────────────────────────────────────────────────────────────

def _call_card(bf: dict, admin: bool = False) -> str:
    home, away, league = _teams(bf)
    p = bf.get("probs")
    pick_label, pick_prob = _pick(bf)
    trigger = _fmt_price(bf.get("mes_trigger_price"))

    if admin:
        tier = html.escape(str(bf.get("softness_tier", "?")))
        head = (f'<div class="call-top">'
                f'<div><div class="fixture-name">{html.escape(f"{home} v {away}")}</div>'
                f'<div class="league-tag">{html.escape(league)}</div></div>'
                f'<div class="tier-badge">TIER {tier}</div></div>')
        stamp = _stamp_row(bf)
        hint = "Full analysis + model internals"
        extras = _internals(bf) if p is not None else ""
    else:
        head = (f'<div class="fixture-name">{html.escape(f"{home} v {away}")}</div>'
                f'<div class="league-tag">{html.escape(league)}</div>')
        stamp = ""
        hint = "Full analysis — all markets"
        extras = ""

    grid = _market_grid(p) if p is not None else ""
    if p is None and not admin:
        # An unrated call row stays honest: shown, never guessed (HR35).
        reason = bf.get("rejection_reason") or "NO DATA — PENDING"
        grid = f'<div class="flag-line"><span class="mk">⚠</span> {html.escape(reason)}</div>'

    return f"""<div class="call-card" onclick="this.classList.toggle('open')">
  {head}
  <div class="pick-line">
    <span class="pick-label">{html.escape(pick_label)}</span>
    <span class="pick-prob">{pick_prob}</span>
    <div class="trigger">
      <div class="num">{trigger}</div>
      <div class="lbl">Deploy At</div>
    </div>
  </div>
  {stamp}
  <div class="expand-hint"><span class="chevron">▸</span> {hint}</div>
  <div class="full-analysis">
    {grid}
    {extras}
  </div>
</div>"""


def _the_call(board: list[dict], admin: bool = False) -> str:
    rows = [bf for bf in board if bf.get("on_deploy_shortlist")]
    if not rows:
        return ('<div class="flags"><div class="flag-line"><span class="mk">—</span> '
                'No deploy-eligible call today (softness A/B only).</div></div>')
    return "".join(_call_card(bf, admin=admin) for bf in rows)


# ─────────────────────────────────────────────────────────────────────────────
# THE SCAN table (click-to-expand rows)
# ─────────────────────────────────────────────────────────────────────────────

def _scan_table(board: list[dict], admin: bool = False) -> str:
    headers = ["Fixture", "1X2", "O1.5/O2.5", "DC/BTTS"] + (["Src"] if admin else [])
    n_cols = len(headers)
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    body: list[str] = []
    idx = 0
    for bf in board:
        idx += 1
        home, away, league = _teams(bf)
        fixture_td = (f'<td><span class="scan-fixture">{html.escape(f"{home} v {away}")}</span>'
                      f'<span class="scan-league">{html.escape(league)}</span></td>')
        src_td = f'<td>{_src_dot(bf)}</td>' if admin else ""
        p = bf.get("probs")
        if p is None:
            reason = bf.get("rejection_reason") or "NO DATA — PENDING"
            body.append(f"""<tr>
  {fixture_td}
  <td class="nodata" colspan="3">NO DATA — PENDING · {html.escape(reason)}</td>
  {src_td}
</tr>""")
            continue
        row_id = ("a-" if admin else "") + f"scan-{idx}"
        c2 = _scan_1x2(p)
        c3 = _scan_goals(p)
        c4 = _scan_dc_btts(p)
        body.append(f"""<tr class="clickable" onclick="toggleScanRow('{row_id}')">
  <td><span class="chevron">▸</span>{fixture_td}</td>
  <td class="scan-num">{c2}</td>
  <td class="scan-num">{c3}</td>
  <td class="scan-num">{c4}</td>
  {src_td}
</tr>
<tr class="detail-row" id="{row_id}">
  <td colspan="{n_cols}">
    <div class="full-analysis">
      {_market_grid(p)}
      {_internals(bf) if admin else ""}
    </div>
  </td>
</tr>""")
    return f"""<table class="scan-table">
  <thead>
  {thead}
  </thead>
  <tbody>
  {''.join(body)}
  </tbody>
</table>"""


# ─────────────────────────────────────────────────────────────────────────────
# Headers + admin-only sections
# ─────────────────────────────────────────────────────────────────────────────

def _board_header(payload: dict, admin: bool = False) -> str:
    date_txt = _friendly_date(payload.get("date") or _date.today().isoformat())
    if admin:
        n_leagues = payload.get("n_leagues") or len(payload.get("leagues_scanned", []))
        gate = payload.get("gate") or {}
        n = gate.get("legs_with_clv")
        req = gate.get("gate_requirement")
        calib = f"{n}/{req}" if (n is not None and req) else "—"
        brand_right = ('<div style="margin-left:auto;display:flex;gap:6px;">'
                       '<span class="phase mono">ADMIN</span>'
                       '<span class="phase mono">PHASE 2 · PAPER</span></div>')
        meta = (f'<span>{date_txt} · <b>07:00</b></span>'
                f'<span>{n_leagues} leagues scanned</span>'
                f'<span>Calibration: <b>{calib}</b> legs</span>')
    else:
        brand_right = ""
        meta = f'<span>{date_txt}</span><span><b>07:00</b></span>'
    return f"""<header class="top">
  <div class="brand">
    <span class="mark"></span>
    <h1>OLP&nbsp;XDV</h1>
    {brand_right}
  </div>
  <div class="meta-row">
    {meta}
  </div>
</header>"""


def _flags_block(data_flags: list[str]) -> str:
    if not data_flags:
        rows = '<div class="flag-line"><span class="mk">✓</span> No data flags this run.</div>'
    else:
        rows = "".join(
            f'<div class="flag-line"><span class="mk">⚠</span> {html.escape(f)}</div>'
            for f in data_flags)
    return (f'<section><div class="sec-head"><h2 class="display">Data Flags</h2></div>'
            f'<div class="flags">{rows}</div></section>')


def _market_label(mk: str, fixture: str) -> str:
    if mk == "1X2_HOME":
        return f"{_short_fixture(fixture).split(' v ')[0]} to win"
    if mk == "1X2_AWAY":
        parts = _short_fixture(fixture).split(" v ")
        return f"{parts[-1]} to win" if len(parts) > 1 else mk
    if mk == "1X2_DRAW":
        return "Draw"
    return {
        "OVER_1_5": "Over 1.5 goals", "OVER_2_5": "Over 2.5 goals",
        "OVER_3_5": "Over 3.5 goals", "UNDER_1_5": "Under 1.5 goals",
        "UNDER_2_5": "Under 2.5 goals", "UNDER_3_5": "Under 3.5 goals",
        "BTTS_YES": "BTTS Yes", "BTTS_NO": "BTTS No",
    }.get(mk, mk)


def _yesterday_graded(rows: list[dict]) -> str:
    """Verified — Yesterday: one row per (fixture, market), graded HIT/MISS/
    PENDING against the 90-minute full-time result (HR15)."""
    if not rows:
        return ('<div class="flags"><div class="flag-line">NO DATA — PENDING — '
                'no settled predictions from yesterday yet.</div></div>')
    out: list[str] = []
    for g in rows:
        fixture = g.get("fixture", "?")
        league = g.get("league")
        label = fixture + (f" ({league})" if league else "")
        ft_raw = g.get("outcome")
        ft = ("FT " + ft_raw.replace("-", "–")) if ft_raw else "FT —"
        engines = g.get("engines", {})
        markets: dict[str, list] = {}
        for eng, mdict in engines.items():
            for mk, v in mdict.items():
                markets.setdefault(mk, []).append(v.get("hit"))
        if not markets:
            out.append(
                f'<div class="graded-row"><span class="pend-tag mono">— PENDING</span>'
                f'<span>{html.escape(label)}</span><span class="graded-ft">{ft}</span></div>')
            continue
        for mk, hits in markets.items():
            if any(h is None for h in hits):
                tag = '<span class="pend-tag mono">— PENDING</span>'
            elif all(hits):
                tag = '<span class="hit-tag mono">✓ HIT</span>'
            elif not any(hits):
                tag = '<span class="miss-tag mono">✗ MISS</span>'
            else:
                tag = '<span class="pend-tag mono">— MIXED</span>'
            mlabel = _market_label(mk, fixture)
            out.append(
                f'<div class="graded-row">{tag}'
                f'<span>{html.escape(label)} — {html.escape(mlabel)}</span>'
                f'<span class="graded-ft">{ft}</span></div>')
    return '<div class="flags" style="padding:6px 16px;">' + "".join(out) + "</div>"


def _admin_footer(payload: dict) -> str:
    gate = payload.get("gate") or {}
    n = gate.get("legs_with_clv")
    req = gate.get("gate_requirement")
    fill_w = 0
    if n is not None and req:
        fill_w = round(max(0.0, min(1.0, n / req)) * 100)
    n_txt = f"{n} / {req} legs" if (n is not None and req) else "— / — legs"
    return f"""<footer>
  <div class="honest">
    <b>Honest edge line:</b> an excellent informed process, <b>not</b> a demonstrated profitable edge.<br>
    Capital authority: <b>THE ARCHITECT</b> — paper only, zero capital; nothing here is live until you deploy it.
  </div>
  <div class="gate">
    <span>PHASE 3 GATE</span>
    <div class="bar"><div class="fill" style="width:{fill_w}%"></div></div>
    <span>{n_txt}</span>
  </div>
</footer>"""


# ─────────────────────────────────────────────────────────────────────────────
# The two dashboards
# ─────────────────────────────────────────────────────────────────────────────

def render_dashboard(payload: dict) -> str:
    """The PUBLIC client view — predictions only (the caller is expected to have
    passed schema.trim_payload(payload); the renderer reads no internals)."""
    body = (
        _board_header(payload, admin=False)
        + "<main>"
        + '<section><div class="sec-head"><h2 class="display">The Call</h2></div>'
        + _the_call(payload.get("board", []), admin=False)
        + "</section>"
        + '<section><div class="sec-head"><h2 class="display">The Scan</h2></div>'
        + _scan_table(payload.get("board", []), admin=False)
        + "</section>"
        + "</main>"
    )
    return html_shell("OLP XDV — Today's Board", body, script=_SCAN_JS)


def render_admin_dashboard(payload: dict) -> str:
    """The authed /admin view — the full payload including model internals,
    verification, cap, data flags, yesterday-graded and the honest footer."""
    n_leagues = payload.get("n_leagues") or len(payload.get("leagues_scanned", []))
    n_call = sum(1 for bf in payload.get("board", []) if bf.get("on_deploy_shortlist"))
    body = (
        _board_header(payload, admin=True)
        + '<div class="paper-strip mono">PAPER ONLY — no stake is placed by this system</div>'
        + "<main>"
        + '<section><div class="sec-head"><h2 class="display">The Call</h2>'
        + f'<span class="cap-pill">{n_call} / 6 CAP</span></div>'
        + '<p class="sec-sub">Deploy-eligible only — softness A/B, ID402 pool cap</p>'
        + _the_call(payload.get("board", []), admin=True)
        + "</section>"
        + '<section><div class="sec-head"><h2 class="display">The Scan</h2></div>'
        + f'<p class="sec-sub">Every fixture across all {n_leagues} scanned leagues</p>'
        + _scan_table(payload.get("board", []), admin=True)
        + "</section>"
        + _flags_block(payload.get("data_flags", []))
        + '<section><div class="sec-head"><h2 class="display">Verified — Yesterday</h2></div>'
        + '<p class="sec-sub">Graded against full-time result, 90-min basis (HR15)</p>'
        + _yesterday_graded(payload.get("yesterday_graded", []))
        + "</section>"
        + "</main>"
        + _admin_footer(payload)
    )
    return html_shell("OLP XDV — Admin Dashboard", body, script=_SCAN_JS)


# ─────────────────────────────────────────────────────────────────────────────
# Admin pages (stats / why / history / 404)
# ─────────────────────────────────────────────────────────────────────────────

def _min_header(today: str) -> str:
    return (f'<header class="top"><div class="brand"><span class="mark"></span>'
            f'<h1>OLP&nbsp;XDV</h1></div>'
            f'<div class="meta-row"><span>{_friendly_date(today)} · <b>07:00</b></span></div></header>')


def render_stats_html(stats_text: str, today: str) -> str:
    body = (_min_header(today) + "<main>" + '<section><div class="sec-head">'
            '<h2 class="display">Gate &amp; calibration</h2></div>'
            f'<div class="flags"><div class="flag-line" style="white-space:pre-wrap;'
            f'display:block;line-height:1.6;">{html.escape(stats_text)}</div></div>'
            "</section></main>")
    return html_shell("OLP XDV — Gate & calibration", body)


def render_why_html(payload: dict, fixture: str) -> str:
    """Full analysis for one fixture (admin page)."""
    board = payload.get("board", [])
    q = fixture.strip().lower()
    bf = next((b for b in board if q in _short_fixture(b.get("fixture", "")).lower()),
              None)
    if bf is None:
        body = (_min_header(payload.get("date") or _date.today().isoformat())
                + "<main>" + '<section><div class="flags"><div class="flag-line">'
                + 'NO DATA — PENDING: no such fixture on this board.</div></div></section>'
                + "</main>")
        return html_shell("OLP XDV — No such fixture", body)
    home, away, league = _teams(bf)
    p = bf.get("probs")
    pick_label, pick_prob = _pick(bf)
    grid = _market_grid(p) if p is not None else ""
    if p is None:
        reason = bf.get("rejection_reason") or "NO DATA — PENDING"
        grid = f'<div class="flag-line"><span class="mk">⚠</span> {html.escape(reason)}</div>'
    tier = html.escape(str(bf.get("softness_tier", "?")))
    kd = bf.get("kickoff_date") or "—"
    body = (
        _min_header(payload.get("date") or _date.today().isoformat())
        + "<main>"
        + '<section><div class="sec-head"><h2 class="display">Full analysis</h2></div>'
        + f'<div class="call-card" style="cursor:default;">'
        + f'<div class="call-top"><div>'
        + f'<div class="fixture-name">{html.escape(f"{home} v {away}")}</div>'
        + f'<div class="league-tag">{html.escape(league)} · tier {tier} · kickoff {html.escape(kd)}</div>'
        + "</div></div>"
        + f'<div class="pick-line"><span class="pick-label">{html.escape(pick_label)}</span>'
        + f'<span class="pick-prob">{pick_prob}</span></div>'
        + "</div>"
        + f'<div class="flags" style="margin-top:14px;"><div class="flag-line" style="display:block;">'
        + f'<span class="mk">Pick</span> {html.escape(pick_label)} — {pick_prob}. '
        + f'Every market the model rates:</div></div>'
        + f'<div style="margin-top:12px;">{grid}</div>'
        + (_internals(bf) if p is not None else "")
        + "</section></main>"
    )
    return html_shell("OLP XDV — Full analysis", body)


def render_history_html(dates: list[str], today: str) -> str:
    if dates:
        rows = "".join(
            f'<div class="graded-row"><a class="scan-fixture" '
            f'href="/dashboard/{html.escape(d)}">{html.escape(_friendly_date(d))}</a>'
            f'<span class="graded-ft mono">{html.escape(d)}</span></div>'
            for d in dates)
    else:
        rows = '<div class="flag-line">NO DATA — PENDING: no boards have been saved yet.</div>'
    body = (_min_header(today) + "<main>" + '<section><div class="sec-head">'
            '<h2 class="display">Board history</h2></div>'
            f'<div class="flags" style="padding:6px 16px;">{rows}</div></section>'
            "</main>")
    return html_shell("OLP XDV — Board history", body)


def render_404_html(date_str: str, today: str) -> str:
    body = (_min_header(today) + "<main>" + '<section><div class="flags">'
            f'<div class="flag-line"><span class="mk">—</span> No board for that date '
            f'({html.escape(date_str)}) — the run either didn\'t happen or produced '
            'no fixtures. NO DATA — PENDING.</div></div></section></main>')
    return html_shell("OLP XDV — Not found", body)
