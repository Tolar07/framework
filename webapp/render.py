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
from datetime import date as _date, datetime, timedelta as _timedelta
from engine import markets as mkt
from engine.leagues import WHITELISTED_LEAGUES

# ─────────────────────────────────────────────────────────────────────────────
# CSS — the ratified design tokens + components (admin superset; the client
# view simply never uses the admin-only classes)
#
# Sprint 4: the FULL stylesheet lives in static/css/app.css (loaded by
# assets.js — see html_shell). Only the above-the-fold critical subset is
# inlined here so the page paints instantly and never flashes unstyled.
# Fonts are self-hosted in static/fonts/ (@font-face in app.css) — the Google
# CDN dependency is gone.
# ─────────────────────────────────────────────────────────────────────────────
_CRITICAL_CSS = """:root{
  --bg:#0B0E13;--surface:#131822;--surface-2:#1A2130;--line:#232B3B;
  --ink:#E7EAF0;--ink-dim:#8B93A6;--ink-faint:#7A8498; /* WCAG AA 4.6:1 on --bg */
  --amber:#D8A659;--amber-dim:#8C744A;--teal:#4FB894;--coral:#E2634F;--violet:#9089D6;
  --radius:10px;
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{
  margin:0;background:radial-gradient(circle at 15% 0%,#161d2b 0%,transparent 45%),var(--bg);
  color:var(--ink);font-family:'Inter',sans-serif;-webkit-font-smoothing:antialiased;
  padding:0 0 88px 0; /* room for the fixed bottom tab bar */
}
.mono{font-family:'IBM Plex Mono',monospace;}
.display{font-family:'Barlow Condensed',sans-serif;text-transform:uppercase;letter-spacing:0.02em;}
header.top{max-width:1180px;margin:0 auto;padding:28px 20px 18px 20px;border-bottom:1px solid var(--line);}
.brand{display:flex;align-items:baseline;gap:10px;}
.brand .mark{width:8px;height:8px;background:var(--amber);border-radius:1px;transform:rotate(45deg);flex:none;}
.brand h1{font-size:22px;font-weight:700;margin:0;letter-spacing:0.04em;}
.brand-link{display:flex;align-items:baseline;gap:10px;color:inherit;text-decoration:none;}
.brand-link:hover h1{opacity:.85;transition:opacity .15s;}
.brand .phase{font-size:11px;color:var(--amber);border:1px solid var(--amber-dim);padding:2px 8px;border-radius:20px;margin-left:auto;font-family:'IBM Plex Mono',monospace;}
.brand .phase.client{font-size:9.5px;color:var(--ink-dim);border-color:var(--line);letter-spacing:0.08em;}
.crumbs{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:11.5px;color:var(--ink-faint);}
.crumb-link a{color:var(--amber);text-decoration:none;}
.crumb-sep{color:var(--ink-faint);opacity:.5;}
.crumb-current{color:var(--ink);font-weight:500;}
.meta-row{display:flex;gap:18px;margin-top:12px;font-size:12.5px;color:var(--ink-dim);flex-wrap:wrap;}
.meta-row b{color:var(--ink);font-weight:600;}
.date-nav{display:flex;align-items:center;gap:8px;margin-top:14px;flex-wrap:wrap;font-size:12px;color:var(--ink-dim);}
.date-nav-btn{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);text-decoration:none;position:relative;}
.date-nav-btn::after{content:"";position:absolute;top:50%;left:50%;width:44px;height:44px;transform:translate(-50%,-50%);}
.date-nav-today{padding:5px 10px;border:1px solid var(--amber-dim);border-radius:8px;color:var(--amber);text-decoration:none;font-size:11.5px;}
.date-nav-label{font-size:11.5px;color:var(--ink-faint);font-family:'IBM Plex Mono',monospace;}
.paper-strip{max-width:1180px;margin:0 auto;padding:9px 20px;background:#1E1710;border-bottom:1px solid #3A2E18;color:#D8A659;font-size:12px;text-align:center;letter-spacing:0.03em;}
main{max-width:1180px;margin:0 auto;padding:0 20px;}
section{margin-top:34px;}
.sec-head{display:flex;align-items:baseline;gap:10px;margin-bottom:4px;}
.sec-head h2{font-size:20px;margin:0;font-weight:700;letter-spacing:0.01em;}
.sec-sub{font-size:12.5px;color:var(--ink-faint);margin:0 0 14px 0;}
.cap-pill{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--ink-dim);border:1px solid var(--line);padding:2px 7px;border-radius:20px;}
.hero-date{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;}
.hero-title{font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:0.04em;margin:0 0 12px 0;}
.hero-match{margin-bottom:14px;}
.hero-teams{font-size:18px;font-weight:600;color:var(--ink);}
.hero-league{display:block;font-size:11px;color:var(--ink-faint);margin-top:4px;}
.hero{border-bottom:1px solid var(--line);padding-bottom:26px;margin-bottom:6px;}
#call-section,#produced-section,#acca-section,#scan-section,#search-section,#flags-section,#verified-section,#phase3-gate-section{scroll-margin-top:16px;}
.hero-pick{display:inline-flex;align-items:center;gap:10px;padding:10px 18px;background:rgba(79,184,148,0.1);border:1px solid var(--teal);border-radius:999px;margin-bottom:16px;}
.hero-team{font-size:16px;font-weight:600;color:var(--teal);}
.hero-confidence{font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--ink);}
.hero-cta{display:inline-block;padding:10px 22px;background:var(--amber);color:var(--bg);font-weight:600;border-radius:8px;text-decoration:none;}
.tab-bar{position:fixed;bottom:0;left:0;right:0;z-index:100;display:flex;background:var(--surface);border-top:1px solid var(--line);padding:8px env(safe-area-inset-bottom) 8px env(safe-area-inset-left);gap:6px;}
.tab-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;min-height:44px;padding:10px 12px;border:none;background:transparent;color:var(--ink-dim);font-family:'Inter',sans-serif;font-size:12px;font-weight:500;border-radius:var(--radius);cursor:pointer;}
.tab-btn.active{background:rgba(216,166,89,0.1);border:1px solid var(--amber-dim);color:var(--amber);font-weight:600;}
.tab-btn:focus-visible{outline:2px solid var(--amber);outline-offset:2px;}
.chat-fab{position:fixed;right:20px;bottom:86px;z-index:101;display:inline-flex;align-items:center;gap:8px;padding:0 16px;min-height:44px;border:1px solid var(--amber-dim);border-radius:999px;background:var(--surface);color:var(--amber);font-size:12px;font-weight:600;cursor:pointer;}
.chat-fab:focus-visible{outline:2px solid var(--amber);outline-offset:2px;}
.chat-fab .fab-ico{font-size:15px;line-height:1;}
.chat-tab.hidden{display:none;}
@media (max-width:480px){.tab-btn{min-height:44px;padding:10px 8px;font-size:11px;}}"""


def _js_refs(base: str, *names: str) -> str:
    """External <script> tags for static/js/<name>.js, `defer` so they never
    block the critical first paint. Files only define functions + attach
    DOMContentLoaded hooks, so load order between them does not matter."""
    return "".join(f'<script src="{base}/js/{nm}.js" defer></script>'
                   for nm in names)


def html_shell(title: str, body: str, script: str = "", asset_base: str = "/static") -> str:
    """Full HTML document.

    `asset_base` is the URL prefix for the external css/js/fonts tree:
    '/static' on the local server, './static' for the static export (relative,
    so any host path works). The critical CSS is inlined (fast first paint);
    assets.js then injects app.css + font preloads off `data-asset-base`, which
    keeps the page CSP-clean (script-src 'self', no inline handlers)."""
    # PWA manifest + theme-color for install prompt + dark-mode initial state
    # Service worker registration is inline (tiny) and CSP-safe because it's a
    # single 'self' script-src — no inline event handlers used.
    return f"""<!doctype html>
<html lang="en" data-asset-base="{html.escape(asset_base, quote=True)}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#0B0E13" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F5F6F8" media="(prefers-color-scheme: light)">
<link rel="manifest" href="{html.escape(asset_base, quote=True)}/manifest.json">
<title>{html.escape(title)}</title>
<style>{_CRITICAL_CSS}</style>
</head><body>
{body}
<script src=\"{asset_base}/js/assets.js\" defer></script>
<script src=\"{asset_base}/js/date_nav.js\" defer></script>
{script}
<script>
  // Service Worker registration (cache-first static, network-first HTML/API)
  if ('serviceWorker' in navigator) {{
    navigator.serviceWorker.register('{html.escape(asset_base, quote=True)}/sw.js', {{scope: '{html.escape(asset_base, quote=True)}/'}})
      .catch(() => {{ /* SW optional — ignore if unsupported */ }});
  }}
  // Dark-mode initial sync: respect localStorage, then prefers-color-scheme
  (function() {{
    var saved = localStorage.getItem('olp-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var dark = saved ? saved === 'dark' : prefersDark;
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  }})();
</script>
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


# ─────────────────────────────────────────────────────────────────────────────
# League flags + club crests (local cache, initials fallback)
# ─────────────────────────────────────────────────────────────────────────────

# Country code for each league (ISO alpha-2) — used for flag emoji/img
_LEAGUE_COUNTRY = {
    "Premier League": "GB",
    "Championship": "GB",
    "Bundesliga": "DE",
    "Serie A": "IT",
    "Ligue 1": "FR",
    "La Liga": "ES",
    "Eredivisie": "NL",
    "Primeira Liga": "PT",
    "Scottish Premiership": "GB",
    "Danish Superliga": "DK",
    "Belgian Pro League": "BE",
    "Austrian Bundesliga": "AT",
    "Champions League": "EU",
    "Europa League": "EU",
    "EFL Cup": "GB",
    "Ekstraklasa": "PL",
    "HNL": "HR",
}

# Club crest mapping: league -> {team_name: crest_url_or_data_uri}
# Populated lazily; on miss, initials fallback is used.
_CLUB_CRESTS: dict[str, dict[str, str]] = {}


_CLUB_PREFIXES = ("fc", "ac", "cf", "sc", "rc", "afc", "as", "cd", "ud", "sv")


def _initials(name: str) -> str:
    """Badge initials for a club.

    Multi-word clubs get the initials of their first two significant words
    (Manchester United -> MU). A single significant word gets its first 3
    letters (Ajax -> AJA) — but when a club prefix like FC/AC/AS was stripped,
    the bare word is the club's common name, so a single letter reads best on
    a badge (FC Barcelona -> B, AC Milan -> M, AS Roma -> R)."""
    tokens = [t for t in name.split()]
    words = [t for t in tokens if t.lower() not in _CLUB_PREFIXES]
    if not words:
        return name[:2].upper()
    if len(words) == 1:
        if len(words) < len(tokens):
            return words[0][0].upper()
        return words[0][:3].upper()
    return "".join(w[0].upper() for w in words[:2])


def _flag_html(league: str) -> str:
    """Return <img class='flag' ...> for the league's country, or placeholder."""
    code = _LEAGUE_COUNTRY.get(league)
    if not code:
        return '<span class="flag placeholder">?</span>'
    if code == "EU":
        return '<span class="flag placeholder" title="European competition">EU</span>'
    # Use flagcdn.com (free, no key, SVG flags) - with onerror fallback
    url = f"https://flagcdn.com/24x16/{code.lower()}.svg"
    return f'<img class="flag" src="{url}" alt="{code}" title="{league}" onerror="this.onerror=null; this.outerHTML=\'<span class=\\\"flag placeholder\\\" title=\\\"{html.escape(league)}\\\">?</span>\'">'


def _crest_html(team: str, league: str) -> str:
    """Return <img class='crest' ...> for the club, or initials placeholder.

    The crest cache (webapp.crests.badge_url) is the hotlinked TheSportsDB
    source (Architect-approved); _CLUB_CRESTS stays as a legacy in-memory
    override for tests. A club TheSportsDB can't match keeps the labelled
    initials placeholder — never a fake crest (HR35)."""
    try:
        from webapp import crests as _crests
        url = _crests.badge_url(team)
    except Exception:
        url = None
    if not url:
        url = _CLUB_CRESTS.get(league, {}).get(team)
    if url:
        # onerror: swap to initials placeholder if the hotlinked image fails
        escaped_initials = html.escape(_initials(team))
        escaped_title = html.escape(team)
        h = hash(team) % 360
        color = f"hsl({h}, 55%, 45%)"
        return (f'<img class="crest" src="{url}" alt="{escaped_title}" title="{escaped_title}" '
                f'loading="lazy" onerror="this.onerror=null; this.outerHTML='
                f'\'<span class=\\\"crest placeholder\\\" style=\\\"background:{color}\\\" '
                f'title=\\\"{escaped_title}\\\">{escaped_initials}</span>\'">')
    # Fallback: initials in a coloured circle
    initials = _initials(team)
    # Deterministic colour from team name
    h = hash(team) % 360
    color = f"hsl({h}, 55%, 45%)"
    return (f'<span class="crest placeholder" style="background:{color}" '
            f'title="{team}">{initials}</span>')


def _fixture_teams_with_badges(bf: dict) -> tuple[str, str, str]:
    """Return (home_badged, away_badged, league) for fixture rendering.

    Each badged team is crest + name (the scan table renders "crest Name v
    crest Name"). The fixture CARD (THE CALL) builds its badge/name separately
    via _crest_html + _teams so the name isn't duplicated."""
    home, away, league = _teams(bf)
    home_badged = _crest_html(home, league) + html.escape(home)
    away_badged = _crest_html(away, league) + html.escape(away)
    return home_badged, away_badged, league


def _fixture_teams_with_badges_admin(bf: dict) -> tuple[str, str, str]:
    """Admin version includes flag on league name."""
    home, away, league = _teams(bf)
    flag = _flag_html(league)
    home_badged = _crest_html(home, league) + html.escape(home)
    away_badged = _crest_html(away, league) + html.escape(away)
    league_badged = flag + " " + html.escape(league)
    return home_badged, away_badged, league_badged


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
    """THE CALL fixture card — badge | home — vs — away | badge, plus kickoff,
    league, star toggle, pick line and (admin) tier + internals."""
    home, away, league = _teams(bf)
    home_crest = _crest_html(home, league)
    away_crest = _crest_html(away, league)
    if admin:
        league_badged = _flag_html(league) + " " + html.escape(league)
    else:
        league_badged = html.escape(league)
    p = bf.get("probs")
    pick_label, pick_prob = _pick(bf)
    trigger = _fmt_price(bf.get("mes_trigger_price"))
    kickoff = bf.get("kickoff_date", "")
    kickoff_display = ""
    if kickoff:
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(kickoff.replace("Z", "+00:00"))
            kickoff_display = dt.strftime("%H:%M")
        except Exception:
            kickoff_display = kickoff[:5] if len(kickoff) >= 5 else kickoff

    # Star/favorite toggle — check if fixture is favorited
    fixture_key = bf.get("fixture", "")
    is_fav = bf.get("favorited", False)

    # Fixture card header (shared by client + admin)
    card_head = f"""<div class="fixture-card">
  {home_crest}
  <div class="teams">
    <div class="team"><span class="team-name">{html.escape(home)}</span></div>
    <span class="vs">vs</span>
    <div class="team"><span class="team-name">{html.escape(away)}</span></div>
  </div>
  {away_crest}
  <div class="meta">
    <span class="kickoff">{kickoff_display}</span>
    <span class="league-tag">{league_badged}</span>
    <span class="star{' active' if is_fav else ''}" data-fav="{html.escape(fixture_key)}"
      role="button" tabindex="0" aria-label="Toggle favorite"
      aria-pressed="{'true' if is_fav else 'false'}">★</span>
  </div>
</div>
<div class="pick-line">
  <span class="pick-label">{html.escape(pick_label)}</span>
  <span class="pick-prob">{pick_prob}</span>
  <div class="trigger">
    <div class="num">{trigger}</div>
    <div class="lbl">Deploy At</div>
  </div>
</div>"""

    if admin:
        deploy = ('<span class="tier-badge deploy">DEPLOY</span>'
                  if bf.get("on_deploy_shortlist") else "")
        head = card_head + deploy
        stamp = _stamp_row(bf)
        hint = "Full analysis + model internals"
        extras = _internals(bf) if p is not None else ""
    else:
        head = card_head
        stamp = ""
        hint = "Full analysis — all markets"
        extras = ""

    grid = _market_grid(p) if p is not None else ""
    if p is None and not admin:
        # An unrated call row stays honest: shown, never guessed (HR35).
        reason = bf.get("rejection_reason") or "NO DATA — PENDING"
        grid = f'<div class="flag-line"><span class="mk">⚠</span> {html.escape(reason)}</div>'

    return f"""<div class="call-card"
    role="button" tabindex="0" aria-expanded="false">
  {head}
  {stamp}
  <div class="expand-hint"><span class="chevron">▸</span> {hint}</div>
  <div class="full-analysis" aria-hidden="true">
    {grid}
    {extras}
  </div>
</div>"""


def _tier_grouped_call(board: list[dict]) -> str:
    """THE CALL — the FULL production as ONE unified pool (Architect 2026-08-10:
    ID402 softness tiers removed). Every fixture stays visible, ranked within the
    single pool by deploy-shortlist first then model confidence. The DEPLOY pill
    (on the card) marks the actual shortlist; there is no tier grouping and no
    cap. The public client view does NOT use this (it renders the deploy
    shortlist only, per the data-leak boundary)."""
    grp = sorted(board, key=lambda b: (not b.get("on_deploy_shortlist"),
                                       -_pick_confidence(b)))
    n_deploy = sum(1 for b in grp if b.get("on_deploy_shortlist"))
    count = f"{len(grp)} fixture{'s' if len(grp) != 1 else ''}"
    if n_deploy:
        count += f" · {n_deploy} in deploy pool"
    cards = "".join(_call_card(b, admin=True) for b in grp)
    return ('<div class="tier-section">'
            '<div class="tier-head"><span class="tier-name">'
            'All Leagues — one unified pool (all whitelisted deploy-eligible)</span>'
            f'<span class="tier-count">{count}</span></div>'
            f'<div class="call-grid">{cards}</div>'
            '</div>')


def _the_call(board: list[dict], admin: bool = False) -> str:
    if not board:
        return ('<div class="flags"><div class="flag-line"><span class="mk">—</span> '
                'No fixtures on this board today — NO DATA — PENDING. '
                'The daily pipeline runs at 07:00; check back then.</div></div>')
    if admin:
        # The full production as one unified pool — nothing produced is hidden,
        # ranked by deploy-shortlist first then model confidence.
        return _tier_grouped_call(board)
    # Standing rule 2026-08-09: the call is TODAY's fixtures and nothing else.
    # A fixture with no kickoff date is never assumed to be today (HR35).
    today = _date.today().isoformat()
    rows = [bf for bf in board
            if bf.get("on_deploy_shortlist") and bf.get("kickoff_date") == today]
    if not rows:
        return ('<div class="flags"><div class="flag-line"><span class="mk">—</span> '
                'No deploy-eligible call today — the call is strictly fixtures '
                'kicking off today (same-day rule). Check the Scan tab for the '
                'wider window.</div></div>')
    # Responsive card grid — 2-3 columns on desktop, 1 column on mobile.
    return ('<div class="call-grid">'
            + "".join(_call_card(bf, admin=False) for bf in rows)
            + "</div>")


# ─────────────────────────────────────────────────────────────────────────────
# THE SCAN — grouped by league, sorted by pick confidence (both views)
# ─────────────────────────────────────────────────────────────────────────────

def _pick_confidence(bf: dict) -> float:
    """Extract the highest model probability for sorting."""
    p = bf.get("probs")
    if not p:
        return 0.0
    # Get max of home/draw/away probabilities
    probs = [p.get("p_home"), p.get("p_draw"), p.get("p_away")]
    return max([pr for pr in probs if pr is not None] or [0.0])


def _scan_table(board: list[dict], admin: bool = False, payload_date: str = "") -> str:
    # Group by league
    from collections import defaultdict
    by_league = defaultdict(list)
    for bf in board:
        league = _league_of(bf.get("fixture", ""))
        by_league[league].append(bf)

    # Sort leagues by name for consistency
    sorted_leagues = sorted(by_league.keys())

    # Determine which leagues have live/upcoming fixtures (default expanded)
    # A league is "live/upcoming" if any fixture has a kickoff today or tomorrow
    from datetime import date as _date_cls, timedelta as _td
    today = _date_cls.today()
    tomorrow = today + _td(days=1)
    live_leagues = set()
    for league, fixtures in by_league.items():
        for bf in fixtures:
            kickoff_str = bf.get("kickoff_utc") or bf.get("date")
            if kickoff_str:
                try:
                    kickoff_date = _date_cls.fromisoformat(kickoff_str[:10])
                    if kickoff_date <= tomorrow:
                        live_leagues.add(league)
                        break
                except (ValueError, TypeError):
                    pass

    # Build the grouped table — one tbody per league so collapse is a valid
    # per-group class toggle (CSS hides .league-row/.detail-row under
    # tbody.collapsed, keeping the header visible as the toggle).
    headers = ["Fixture", "1X2", "O1.5/O2.5", "DC/BTTS"] + (["Src"] if admin else [])
    n_cols = len(headers)
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"

    body_parts: list[str] = []

    for league in sorted_leagues:
        fixtures = by_league[league]
        # Separate accumulator candidates (on the deploy shortlist) from others.
        # Every whitelisted league is one unified pool (Architect 2026-08-10) —
        # the shortlist itself is the only discriminator.
        acc_candidates = [bf for bf in fixtures if bf.get("on_deploy_shortlist")]
        other_fixtures = [bf for bf in fixtures if not bf.get("on_deploy_shortlist")]
        # Accumulator candidates first, then others — both sorted by confidence
        acc_candidates.sort(key=_pick_confidence, reverse=True)
        other_fixtures.sort(key=_pick_confidence, reverse=True)
        fixtures_sorted = acc_candidates + other_fixtures

        # Default expanded for live/upcoming leagues, collapsed otherwise
        is_live = league in live_leagues
        collapsed_class = "" if is_live else " collapsed"

        # League card header — ScoreAI layout: badge + name + season + meta + chevron
        flag = _flag_html(league)
        country_code = _LEAGUE_COUNTRY.get(league, "")
        country_name = {"GB": "England", "DE": "Germany", "IT": "Italy", "FR": "France",
                        "ES": "Spain", "NL": "Netherlands", "PT": "Portugal", "DK": "Denmark",
                        "BE": "Belgium", "AT": "Austria", "EU": "Europe", "PL": "Poland",
                        "HR": "Croatia"}.get(country_code, "")
        # Derive matchday from the number of fixtures (approximate)
        matchday = f"Matchday {len(fixtures_sorted)}" if fixtures_sorted else ""
        season = "2026/27"
        # Count accumulator candidates for the league badge
        n_acc = len(acc_candidates)
        acc_badge = (f' · <span class="acc-pill league-count">⭐ {n_acc} acc candidate{"s" if n_acc != 1 else ""}</span>'
                     if n_acc else "")
        _expanded_attr = "false" if collapsed_class else "true"
        body_parts.append(f"""<tbody class="league-group{collapsed_class}" data-league="{html.escape(league)}">
<tr class="league-group-header"
    role="button" tabindex="0" aria-expanded="{_expanded_attr}"
    aria-controls="league-{html.escape(league).replace(' ', '-')}-rows">
  <td colspan="{n_cols}" id="league-{html.escape(league).replace(' ', '-')}-rows">
    <div class="league-card">
      <div class="league-badge">{flag}</div>
      <div class="league-name">{html.escape(league)}</div>
      <div class="league-meta">
        <span><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>{html.escape(matchday)}</span>
        <span><svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>{html.escape(country_name)}</span>
      </div>
      <span class="league-chevron">▾</span>
      <div class="league-season">{html.escape(season)} · {len(fixtures_sorted)} fixture{'s' if len(fixtures_sorted) != 1 else ''}{acc_badge}</div>
    </div>
  </td>
</tr>""")

        idx = 0
        for bf in fixtures_sorted:
            idx += 1
            if admin:
                home_badged, away_badged, league_badged = _fixture_teams_with_badges_admin(bf)
            else:
                home_badged, away_badged, league_badged = _fixture_teams_with_badges(bf)
            p = bf.get("probs")
            is_acc = bf.get("on_deploy_shortlist")
            acc_pill = ('<span class="acc-pill"><svg viewBox="0 0 24 24"><path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.4l6.1-.9z"/></svg>Acca</span>'
                        if is_acc else "")
            fixture_td = (f'<span class="scan-fixture">{home_badged} v {away_badged}{acc_pill}</span>'
                          f'<span class="scan-league">{league_badged}</span>')
            src_td = f'<td>{_src_dot(bf)}</td>' if admin else ""
            status = "deploy" if is_acc else ("no-data" if p is None else "scan-only")
            best_market = bf.get("best_market_key") or ""
            date_str = payload_date if admin else ""
            acc_marker = '<span class="acc-star">⭐</span> ' if is_acc else ""
            acc_row_class = " acc-row" if is_acc else ""

            if p is None:
                reason = bf.get("rejection_reason") or "NO DATA — PENDING"
                body_parts.append(f"""<tr class="league-row{acc_row_class}" data-fixture="{html.escape(bf.get("fixture", ""))}" data-league="{html.escape(_league_of(bf.get("fixture", "")))}" data-market="{html.escape(best_market)}" data-status="{html.escape(status)}" data-date="{html.escape(date_str)}">
  <td>{acc_marker}{fixture_td}</td>
  <td class="nodata" colspan="3">NO DATA — PENDING · {html.escape(reason)}</td>
  {src_td}
</tr>""")
                continue
            row_id = ("a-" if admin else "") + f"scan-{idx}-{html.escape(league).replace(' ', '-')}"
            c2 = _scan_1x2(p)
            c3 = _scan_goals(p)
            c4 = _scan_dc_btts(p)
            body_parts.append(f"""<tr class="clickable league-row{acc_row_class}" data-target="{row_id}" data-fixture="{html.escape(bf.get("fixture", ""))}" data-league="{html.escape(_league_of(bf.get("fixture", "")))}" data-market="{html.escape(best_market)}" data-status="{html.escape(status)}" data-date="{html.escape(date_str)}"
    role="button" tabindex="0" aria-expanded="false" aria-controls="{row_id}">
  <td><span class="chevron">▸</span>{acc_marker}{fixture_td}</td>
  <td class="scan-num">{c2}</td>
  <td class="scan-num">{c3}</td>
  <td class="scan-num">{c4}</td>
  {src_td}
</tr>
<tr class="detail-row" id="{row_id}" role="region" aria-labelledby="{row_id}" aria-hidden="true">
  <td colspan="{n_cols}">
    <div class="full-analysis">
      {_market_grid(p)}
      {_internals(bf) if admin else ""}
    </div>
  </td>
</tr>""")

        body_parts.append("</tbody>")

    return f"""<table class="scan-table">
  <thead>
  {thead}
  </thead>
  {''.join(body_parts)}
</table>"""


# ─────────────────────────────────────────────────────────────────────────────
# Headers + admin-only sections
# ─────────────────────────────────────────────────────────────────────────────

def _date_nav(d: str, base: str) -> str:
    """Prev / native date-picker / next / Today navigation between board dates.

    `base` is the route prefix ("/admin" or "/dashboard") — a picked or stepped
    date loads that board; a date with no board hits the existing honest 404
    (HR35: NO DATA — PENDING, never a guess). The date is navigation, not a
    filter, which is why it lives here rather than in the search bar."""
    d = d or _date.today().isoformat()
    today = _date.today().isoformat()
    prev = (_date.fromisoformat(d) - _timedelta(days=1)).isoformat()
    nxt = (_date.fromisoformat(d) + _timedelta(days=1)).isoformat()
    today_link = f'<a class="date-nav-today" href="{base}/{today}">Today</a>' if d != today else ""
    return (f'<div class="date-nav">'
            f'<a class="date-nav-btn" href="{base}/{prev}" aria-label="Previous day">◀</a>'
            f'<div class="date-picker">'
            f'<svg class="date-picker-ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            f'<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="16" y1="3" x2="16" y2="7"/>'
            f'<line x1="8" y1="3" x2="8" y2="7"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'
            f'<input type="date" class="date-nav-input" value="{d}" data-base="{base}" '
            f'aria-label="Jump to a board date">'
            f'</div>'
            f'<a class="date-nav-btn" href="{base}/{nxt}" aria-label="Next day">▶</a>'
            f'{today_link}'
            f'<span class="date-nav-label">{_friendly_date(d)}</span>'
            f'</div>'
            f'<!-- picker jump wired in static/js/date_nav.js (loaded by html_shell) -->')


def _board_header(payload: dict, admin: bool = False) -> str:
    date_txt = _friendly_date(payload.get("date") or _date.today().isoformat())
    d = payload.get("date") or _date.today().isoformat()
    date_nav = _date_nav(d, "/admin" if admin else "/dashboard")
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
        # Client brand keeps a quiet phase note — the honest-edge statement and
        # full capital authority stay on /admin (Architect's explicit choice),
        # but the public view is never presented as a live product.
        brand_right = '<span class="phase client">PAPER · PHASE 2</span>'
        meta = f'<span>{date_txt}</span><span><b>07:00</b></span>'
    base = "/admin" if admin else "/dashboard"
    crumbs = _crumbs(base, d, admin)
    # Theme toggle button (top-right in header, next to phase badge)
    theme_toggle = ('<button class="theme-toggle" id="theme-toggle" '
                    'aria-label="Toggle dark/light mode" '
                    'aria-pressed="true" title="Toggle theme">'
                    '<svg class="theme-icon theme-sun" viewBox="0 0 24 24" '
                    'fill="none" stroke="currentColor" stroke-width="2" '
                    'aria-hidden="true"><circle cx="12" cy="12" r="5"/><path '
                    'd="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 '
                    '1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
                    '<svg class="theme-icon theme-moon" viewBox="0 0 24 24" '
                    'fill="none" stroke="currentColor" stroke-width="2" '
                    'aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 '
                    '7 7 0 0 0 21 12.79z"/></svg></button>')
    return f"""<header class="top">
  <div class="brand">
    <a class="brand-link" href="{base}/{d}">
      <span class="mark"></span>
      <h1>OLP&nbsp;XDV</h1>
    </a>
    {brand_right}
    {theme_toggle}
  </div>
  {crumbs}
  <div class="meta-row">
    {meta}
  </div>
  {date_nav}
</header>"""


def _flags_block(data_flags: list[str]) -> str:
    if not data_flags:
        rows = '<div class="flag-line"><span class="mk">✓</span> No data flags this run.</div>'
    else:
        rows = "".join(
            f'<div class="flag-line"><span class="mk">⚠</span> {html.escape(f)}</div>'
            for f in data_flags)
    return (f'<section id="flags-section"><div class="sec-head"><h2 class="display">Data Flags</h2></div>'
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


# ─────────────────────────────────────────────────────────────────────────────
# Admin search/filter bar
# ─────────────────────────────────────────────────────────────────────────────

def _produced_bet_block(record: Optional[dict], admin: bool) -> str:
    """The produced-bet section (ID415): what the framework bet today (one leg
    per rated fixture, pick + price) and the verified WON/LOST outcome shown the
    next day. `admin=True` renders model prob / EV; the client
    receives only fixture + pick + price + outcome (see schema.trim_payload).
    Live scores are fetched client-side for pending legs."""
    if not record:
        return ('<div class="flags"><div class="flag-line">NO DATA — PENDING — '
                'no produced-bet record for this date. The daily pipeline writes '
                'it at 07:00; Admin can produce one on demand.</div></div>')
    if not record.get("produced"):
        return ('<div class="flags"><div class="flag-line">No fixtures today — '
                'no bet produced. A valid, honest result (ID415). '
                'Check back tomorrow when the board runs.</div></div>')
    date = record.get("date", "")
    rows: list[str] = []
    for leg in record.get("legs") or []:
        fixture = leg.get("fixture", "?")
        league = leg.get("league")
        label = fixture + (f" ({league})" if league else "")
        pick = leg.get("pick_name") or leg.get("pick") or "?"
        detail = pick
        if admin and leg.get("model_prob") is not None:
            detail += f" — {round((leg['model_prob'] or 0) * 100)}%"
        if leg.get("best_price") is not None:
            detail += f" @ {leg['best_price']:.2f}"
            if admin and leg.get("best_mes_ev") is not None:
                detail += f" (EV {leg['best_mes_ev']:+.2%})"
        if leg.get("settled"):
            mark = ('<span class="hit-tag mono">✓ WON</span>'
                    if leg.get("hit") else '<span class="miss-tag mono">✗ LOST</span>')
            ft = leg.get("ft_result") or "?"
            verdict = f"{mark} <span class='graded-ft'>{ft}</span>"
        else:
            # For pending legs, add a live score placeholder
            verdict = ('<span class="pend-tag mono">— PENDING</span> '
                       f'<span class="live-score" data-fixture="{html.escape(fixture)}" '
                       f'data-date="{html.escape(date)}">LIVE — loading…</span>')
        rows.append(
            f'<div class="graded-row">{verdict}'
            f'<span>{html.escape(label)} — {html.escape(detail)}</span></div>')
    head = (f'📋 SCAN RECORD — today\'s rated fixtures — {date} (paper, ID415)'
            if date else '📋 SCAN RECORD — today\'s rated fixtures (paper, ID415)')
    tail = ('This is the scan\'s paper record, NOT a recommendation — the '
            'production pick (if any) is in PRODUCTION BETS. MARKED PAPER — '
            'Phase 2, zero capital.' if admin
            else 'Predictions only — verified WON/LOST next day.')
    return ('<div class="flags" style="padding:6px 16px;">'
            f'<div class="flag-line">{head} — {record.get("n_legs", 0)} leg(s). '
            f'{tail}</div>'
            + "".join(rows) + "</div>")


def _acca_section(accas: Optional[list], admin: bool) -> str:
    """The day's 4-leg acca set (standing rule 2026-08-09) as HTML. `admin=True`
    shows each leg's EV and market key; the client gets fixture + market + price
    + probability only (see schema._client_safe_accas). No accas -> the honest
    'no eligible today' note, never a fabricated set."""
    if not accas:
        return ('<div class="flags"><div class="flag-line">NO ACCA today — no '
                'deploy-eligible fixture with a live price kicks off today. '
                'A valid, honest result — check the Scan tab for priced '
                'fixtures in the wider window.</div></div>')
    blocks: list[str] = []
    for acca in accas:
        rows = [f'<div class="acca-head mono">{html.escape(acca.get("label", "Acca"))} '
                f'— {acca.get("n_legs", 0)} legs'
                + (f' · combined {acca.get("combined_odds", 0):.2f}'
                   if acca.get("combined_odds") else "")
                + (f' (≈{round((acca.get("combined_prob") or 0) * 100)}% all win)'
                   if acca.get("combined_prob") is not None else "")
                + '</div>']
        for leg in acca.get("legs") or []:
            fixture = leg.get("fixture", "?")
            league = leg.get("league")
            label = fixture + (f" ({league})" if league else "")
            detail = f'{html.escape(leg.get("market_name") or leg.get("market_key") or "?")}'
            if leg.get("price") is not None:
                detail += f" @ {leg['price']:.2f}"
            if leg.get("prob") is not None:
                detail += f" ({round((leg['prob'] or 0) * 100)}%)"
            if admin and leg.get("ev") is not None:
                detail += f" · EV {leg['ev']:+.1%}"
            rows.append(f'<div class="acca-leg"><span>{html.escape(label)}</span> — '
                        f'{detail}</div>')
        blocks.append('<div class="acca-block">' + "".join(rows) + "</div>")
    note = ('Capital gate (ID405): every leg is Draw or Under 2.5 — the only '
            'markets cleared for capital. PAPER — Phase 2, zero capital.'
            if admin else
            'Today\'s fixtures only (standing rule 2026-08-09). Paper.')
    return ('<div class="acca-wrap">' + "".join(blocks)
            + f'<div class="acca-note">{note}</div></div>')


def _booking_codes_section(codes: Optional[dict], accas: Optional[list]) -> str:
    """Admin-only: the day's SportyBet booking codes, captured by
    booking/booking_codes.py. A code recalls the betslip — a pre-fill, never a
    stake (Phase-2 bright line: the Architect is the only one who can turn a
    code into money). Missing file → NO DATA — PENDING (HR35)."""
    if not codes or not codes.get("results"):
        return ('<div class="flags"><div class="flag-line">NO DATA — PENDING — '
                'no SportyBet booking codes captured for this board. Run '
                '`py -3.12 -m booking.booking_codes --date <day>` after the '
                'daily pipeline has priced the acca legs.</div></div>')
    blocks: list[str] = []
    for r in codes.get("results") or []:
        status = r.get("status", "MANUAL")
        code = r.get("code")
        status_cls = ("hit-tag mono" if status == "BOOKED" and code
                      else "pend-tag mono" if status == "SLIP READY"
                      else "miss-tag mono")
        head = (f'<div class="acca-head mono">{html.escape(r.get("label", "Acca"))}'
                f' — {r.get("n_legs", 0)} legs · '
                f'<span class="{status_cls}">{status}</span>')
        if code:
            head += (f' · <span class="booking-code" '
                     f'title="Paste into SportyBet to recall the slip">'
                     f'CODE {html.escape(code)}</span>')
        head += '</div>'
        legs = []
        for leg in r.get("per_leg") or []:
            booked = leg.get("status") == "BOOKED"
            mark = ('<span class="hit-tag mono">✓</span>' if booked
                    else '<span class="miss-tag mono">✗</span>')
            note = f' — {html.escape(leg.get("reason", ""))}' if leg.get("reason") else ""
            legs.append(f'<div class="acca-leg">{mark} '
                        f'{html.escape(leg.get("fixture", "?"))} — '
                        f'{html.escape(leg.get("market_name", "?"))}'
                        f'<span class="graded-ft">{note}</span></div>')
        blocks.append('<div class="acca-block">' + head + "".join(legs) + "</div>")
    n_codes = sum(1 for r in codes.get("results") or [] if r.get("code"))
    note = (f'{n_codes} code(s) captured. Codes pre-fill the slip when pasted '
            'into SportyBet — a MANUAL leg must be added by hand first. '
            'PAPER — Phase 2: this system never stakes. The Architect approves '
            'and stakes.')
    return ('<div class="acca-wrap">' + "".join(blocks)
            + f'<div class="acca-note">{note}</div></div>')


def _admin_search_bar(payload: dict) -> str:
    """Search/filter controls for the admin scan table.

    The league dropdown is the FULL ID401 whitelist (WHITELISTED_LEAGUES) plus any
    league actually on the board — an approved league with no fixtures today is
    still searchable, because "I need all the leagues" is an audit requirement,
    not a today-requirement. Date is NOT a filter here: it is a navigation
    control in the header (see _date_nav), so the operator can move between
    board dates instead of filtering one board."""
    board_leagues = {_league_of(bf.get("fixture", "")) for bf in payload.get("board", [])}
    leagues = sorted(set(WHITELISTED_LEAGUES) | board_leagues)
    markets = ["1X2_HOME", "1X2_DRAW", "1X2_AWAY", "OVER_1_5", "OVER_2_5", "BTTS_YES"]
    statuses = ["deploy", "scan-only", "no-data"]

    league_opts = "".join(f'<option value="{html.escape(lg)}">{html.escape(lg)}</option>' for lg in leagues)
    market_opts = "".join(f'<option value="{m}">{m}</option>' for m in markets)
    status_opts = "".join(f'<option value="{s}">{s}</option>' for s in statuses)

    return f"""<div class="admin-search-bar">
  <input type="search" id="admin-search" placeholder="Search team, league, fixture…" aria-label="Search fixtures">
  <select id="admin-filter-league" aria-label="Filter by league">
    <option value="">All leagues</option>{league_opts}
  </select>
  <select id="admin-filter-market" aria-label="Filter by market type">
    <option value="">All markets</option>{market_opts}
  </select>
  <select id="admin-filter-status" aria-label="Filter by deploy status">
    <option value="">All statuses</option>{status_opts}
  </select>
</div>"""


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


def _phase3_gate_section(gate: dict) -> str:
    """Phase 3 Gate dashboard section for the admin view.

    Shows: legs count, mean CLV, trend, sign-off status, and sign-off action.
    """
    n = gate.get("legs_with_clv", 0)
    req = gate.get("gate_requirement", 30)
    mean_clv = gate.get("mean_clv_pct")
    positive_mean = gate.get("positive_mean_clv", False)
    gate_met = gate.get("gate_met_pending_architect_signoff", False)
    signed = gate.get("architect_signed_off", False)
    signed_by = gate.get("signed_by", "")
    signed_at = gate.get("signed_at", "")

    # Progress bar fill
    fill_w = 0
    if req:
        fill_w = round(max(0.0, min(1.0, n / req)) * 100)

    # Mean CLV display
    mean_clv_str = f"{mean_clv:+.2f}%" if mean_clv is not None else "—"
    clv_class = "clv-positive" if (mean_clv or 0) > 0 else "clv-negative"

    # Gate status
    if signed:
        status_html = f'<span class="status-badge status-signed">✅ SIGNED OFF by {html.escape(signed_by)} at {html.escape(signed_at)}</span>'
    elif gate_met:
        status_html = f'<span class="status-badge status-pending">⏳ GATE MET — Awaiting Architect Sign-off</span>'
    elif n == 0:
        status_html = f'<span class="status-badge status-empty">📭 NO LEGS WITH CLV</span>'
    else:
        status_html = f'<span class="status-badge status-progress">🔄 IN PROGRESS</span>'

    # Trend: would need historical gate snapshots; for now show current state
    trend_html = ""
    if mean_clv is not None:
        trend_html = f'<div class="gate-row"><span class="gate-label">Mean CLV:</span><span class="gate-value {clv_class}">{mean_clv_str}</span></div>'

    # Sign-off form (only shown when gate is met and not yet signed)
    signoff_form = ""
    if gate_met and not signed:
        signoff_form = f'''
        <div id="phase3-signoff-form">
            <div class="signoff-row">
                <label for="architect_name">Architect (V7) Name:</label>
                <input type="text" id="architect_name" required placeholder="Your name/identifier">
            </div>
            <div class="signoff-row">
                <label><input type="checkbox" id="signoff-confirm" required> I confirm: ≥30 paper legs with logged CLV, positive mean CLV. Deploy is authorized.</label>
            </div>
            <button type="button" class="btn-primary signoff-btn" id="phase3-signoff-btn">✅ Sign Off & Open Capital Gate</button>
            <div id="phase3-signoff-msg" class="flags"></div>
        </div>
        <!-- sign-off handler lives in static/js/signoff.js (admin _js_refs) -->
        '''
    elif signed:
        signoff_form = f'''
        <div class="signoff-complete">
            <p>Capital gate is OPEN — Phase 3 → Phase 4 transition authorized.</p>
            <p class="signoff-detail">Signed by: {html.escape(signed_by)}<br>At: {html.escape(signed_at)}</p>
            <button type="button" class="btn-secondary" id="phase3-revoke-btn">🔓 Revoke Sign-off</button>
            <!-- revoke handler lives in static/js/signoff.js (admin _js_refs) -->
        </div>
        '''

    return f'''<section id="phase3-gate-section" class="cv-auto">
    <div class="sec-head"><h2 class="display">Phase 3 Gate — Capital Deployment Authority</h2></div>
    <p class="sec-sub">Phase 2 paper legs accumulate CLV evidence. ≥30 legs with logged CLV + positive mean CLV + Architect (V7) sign-off unlocks Phase 3 capital deployment.</p>
    <div class="gate-dashboard">
        <div class="gate-progress">
            <div class="gate-row"><span class="gate-label">Legs with CLV:</span><span class="gate-value">{n} / {req}</span></div>
            <div class="gate-row"><span class="gate-label">Progress:</span><div class="bar"><div class="fill" style="width:{fill_w}%"></div></div></div>
            {trend_html}
            <div class="gate-row"><span class="gate-label">Positive Mean CLV:</span><span class="gate-value {'yes' if positive_mean else 'no'}">{'✅ YES' if positive_mean else '❌ NO'}</span></div>
            <div class="gate-row"><span class="gate-label">Gate Status:</span><span class="gate-value">{status_html}</span></div>
        </div>
        <div class="gate-signoff">
            <h3>Architect Sign-off</h3>
            {signoff_form}
        </div>
    </div>
</section>'''


# ─────────────────────────────────────────────────────────────────────────────
# The two dashboards
# ─────────────────────────────────────────────────────────────────────────────

def _tab_bar(active: str, base: str, payload_date: str = "") -> str:
    """Bottom tab bar navigation — 3 tabs: Call, Scan, Search."""
    d = payload_date or _date.today().isoformat()
    tabs = [
        ("call", "Call", "📋", f"{base}/{d}#call"),
        ("scan", "Scan", "📊", f"{base}/{d}#scan"),
        ("search", "Search", "🔍", f"{base}/{d}#search"),
    ]
    # We'll use onclick navigation instead of href for SPA-like behavior.
    # Each tab is a real button with the WAI-ARIA tab pattern: roving tabindex
    # (active tab is 0, others -1), aria-selected, aria-controls pointing at the
    # matching <section>, and arrow-key navigation wired in static/js/tab.js.
    tab_html = ""
    for tab_id, label, icon, _ in tabs:
        active_class = " active" if tab_id == active else ""
        selected = "true" if tab_id == active else "false"
        tabindex = "0" if tab_id == active else "-1"
        tab_html += (f'<button class="tab-btn{active_class}" data-tab="{tab_id}" '
                     f'role="tab" aria-selected="{selected}" tabindex="{tabindex}" '
                     f'aria-controls="{tab_id}-section">'
                     f'<svg viewBox="0 0 24 24">{_tab_icon(icon)}</svg>'
                     f'<span>{label}</span></button>')
    return (f'<nav class="tab-bar" role="tablist" aria-label="Main navigation">'
            f'{tab_html}</nav>')

def _tab_icon(name: str) -> str:
    """Return SVG path for tab icons."""
    icons = {
        "📋": '<path d="M9 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm0 2v14h6V5H9z"/><path d="M9 9h6"/><path d="M9 13h6"/>',
        "📊": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/><path d="M6 15h12"/><path d="M6 9h8"/>',
        "🔍": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/>',
    }
    return icons.get(name, icons["🔍"])

def _date_pills(payload_date: str, base: str) -> str:
    """Horizontal scrollable date pills (yesterday, today, +3 days)."""
    from datetime import date as _date_cls, timedelta as _td
    today = _date_cls.today()
    d = payload_date or today.isoformat()
    try:
        current = _date_cls.fromisoformat(d)
    except ValueError:
        current = today

    pills = []
    for offset in range(-1, 4):  # yesterday to +3 days
        pill_date = today + _td(days=offset)
        pill_str = pill_date.isoformat()
        is_today = (pill_date == today)
        is_active = (pill_date == current)
        label = pill_date.strftime("%a %d %b")
        if is_today:
            label = "Today"
        elif offset == -1:
            label = "Yesterday"
        elif offset == 1:
            label = "Tomorrow"

        active_class = " today" if is_active else ""
        pills.append(f'<a class="date-pill{active_class}" href="{base}/{pill_str}" data-date="{pill_str}">{label}</a>')

    return f'<div class="date-pills" role="navigation" aria-label="Date filter">{"".join(pills)}</div>'

def _market_select_panel(payload: dict) -> str:
    """Admin-only: ScoreAI-style collapsible 'Select Markets to Display' panel.

    Matches ScoreAI's 'Select Stats to Display': gear icon + title +
    chevron toggle, 'Select All' / 'Clear All' text links, 2-column
    checkbox grid."""
    all_markets = [
        ("1X2", "1X2 (Home/Draw/Away)"),
        ("O1.5/O2.5", "Over 1.5 / Over 2.5 Goals"),
        ("DC/BTTS", "Double Chance / BTTS"),
    ]
    if payload.get("admin"):
        all_markets.append(("Src", "Source Verification"))

    checkboxes = ""
    for key, label in all_markets:
        checkboxes += f'<label class="market-checkbox"><input type="checkbox" name="market-col" value="{key}" checked> {html.escape(label)}</label>'

    # ScoreAI-style collapsible panel with gear icon
    gear_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>'
    return f"""<div class="market-select-panel" id="market-select-panel">
  <div class="market-select-header" role="button" tabindex="0" aria-expanded="true" aria-controls="market-select-body">
    <span class="market-select-title">{gear_svg} Select Markets to Display</span>
    <span class="market-select-chevron">▾</span>
  </div>
  <div class="market-select-body" id="market-select-body">
    <div class="market-select-actions">
      <button class="market-select-action" data-toggle="all">Select All</button>
      <button class="market-select-action" data-toggle="none">Clear All</button>
    </div>
    <div class="market-checkboxes">{checkboxes}</div>
  </div>
</div>"""

def _chat_fab() -> str:
    """Floating 'AI Analyst' opener — the only path into the chat panel
    (openChatTab() is defined in static/js/chat.js; without this button the panel is
    unreachable)."""
    return ('<button class="chat-fab" id="chat-fab" '
            'aria-label="Open AI Analyst chat"><span class="fab-ico">✦</span> '
            'AI Analyst</button>')


def _chat_tab(payload_date: str = "") -> str:
    """AI Analyst chat tab — reusable component."""
    return f"""<div class="chat-tab hidden" id="chat-tab" role="dialog" aria-label="AI Analyst" data-date="{html.escape(payload_date)}">
  <div class="chat-header">
    <span class="chat-title">AI Analyst</span>
    <button class="chat-close" aria-label="Close chat">&times;</button>
  </div>
  <div class="chat-messages" id="chat-messages" role="log" aria-live="polite"></div>
  <div class="chat-quick" role="group" aria-label="Quick actions">
    <button class="chat-quick-btn" data-prompt="Analyze today's board">Analyze Board</button>
    <button class="chat-quick-btn" data-prompt="Explain the top pick">Explain Top Pick</button>
    <button class="chat-quick-btn" data-prompt="Which fixtures have the highest confidence?">High Confidence</button>
    <button class="chat-quick-btn" data-prompt="Show me value bets">Value Bets</button>
  </div>
  <div class="chat-input-area">
    <input type="text" class="chat-input" id="chat-input" placeholder="Ask about today's board, a fixture, or the framework..." aria-label="Chat input">
    <button class="chat-send" id="chat-send" disabled>Send</button>
  </div>
</div>"""

def _produce_panel() -> str:
    """Admin-only: BET Production panel — visible at the top of /admin.

    Pick a day, see ALL fixtures across all approved leagues, select matches,
    and produce predictions in real time. Defaults to today."""
    today = _date.today()
    day_isos = [(today + _timedelta(days=i)).isoformat() for i in range(4)]
    day_labels = ["Today", "Tomorrow", "+2 days", "+3 days"]
    chips = "".join(
        f'<button type="button" class="produce-day-chip" data-date="{di}">{lb}</button>'
        for di, lb in zip(day_isos, day_labels))
    return f"""<div class="produce-panel" id="produce-panel">
  <div class="produce-toolbar">
    <input type="search" id="produce-query" placeholder="Search team name…" aria-label="Search fixtures">
    <input type="date" id="produce-date" value="{today.isoformat()}" aria-label="Produce for day" title="Pick the day to produce">
    <button id="produce-search-btn" class="btn-primary">Search fixtures</button>
  </div>
  <div class="produce-day-chips">{chips}</div>
  <div id="produce-results" class="produce-results"></div>
  <div class="produce-tray" id="produce-tray" style="display:none;">
    <span id="produce-count">0 selected</span>
    <button id="produce-go" class="btn-primary" disabled>⚡ Produce predictions</button>
    <button id="produce-clear" class="market-select-action">Clear</button>
  </div>
  <div id="produce-output"></div>
</div>"""



def render_dashboard(payload: dict, asset_base: str = "/static") -> str:
    """The PUBLIC client view — predictions only with tab navigation."""
    d = payload.get("date", "")
    today = _date.today().isoformat()
    board = payload.get("board", [])
    # League dropdown for the client Search tab — only leagues on this board
    # (client-safe: names alone, no model internals).
    _board_leagues = sorted({_league_of(bf.get("fixture", "")) for bf in board if bf.get("fixture")})
    league_opts = "".join(
        f'<option value="{html.escape(lg)}">{html.escape(lg)}</option>'
        for lg in _board_leagues)
    # Find the strongest pick for the hero
    hero_pick = None
    for bf in board:
        if bf.get("probs") and bf.get("on_deploy_shortlist"):
            hero_pick = bf
            break
    if not hero_pick:
        for bf in board:
            if bf.get("probs"):
                hero_pick = bf
                break

    hero_html = ""
    if hero_pick:
        p = hero_pick.get("probs", {})
        home, away, league = _teams(hero_pick)
        probs = {}
        if p:
            probs = {
                "home": p.get("p_home"),
                "draw": p.get("p_draw"),
                "away": p.get("p_away")
            }
        best = max(probs.items(), key=lambda x: x[1] or 0) if probs else ("home", 0)
        best_team = home if best[0] == "home" else (away if best[0] == "away" else "Draw")
        best_pct = round((best[1] or 0) * 100)
        hero_html = f"""<section class="hero" id="call">
  <div class="hero-date">Today — {_friendly_date(today)}</div>
  <h1 class="hero-title">Top Pick</h1>
  <div class="hero-match">
    <span class="hero-teams">{html.escape(f"{home} v {away}")}</span>
    <span class="hero-league">{html.escape(league)}</span>
  </div>
  <div class="hero-pick">
    <span class="hero-team">{html.escape(best_team)}</span>
    <span class="hero-confidence">{best_pct}%</span>
  </div>
  <a class="hero-cta" href="#scan">View Full Board</a>
</section>"""

    body = (
        _board_header(payload, admin=False)
        + hero_html
        + "<main>"
        + '<section id="call-section"><div class="sec-head"><h2 class="display">The Call</h2></div>'
        + _the_call(payload.get("board", []), admin=False)
        + "</section>"
        + '<section id="produced-section" class="cv-auto"><div class="sec-head"><h2 class="display">Today\'s Produced Bet</h2></div>'
        + '<p class="sec-sub">What the framework bet today — one leg per rated fixture, '
        + 'verified WON/LOST next day (ID415)</p>'
        + _produced_bet_block(payload.get("produced_bet"), admin=False)
        + "</section>"
        + '<section id="acca-section" class="cv-auto"><div class="sec-head"><h2 class="display">Today\'s 4-Leg Acca</h2></div>'
        + '<p class="sec-sub">Today\'s fixtures only (standing rule) — a set of '
        + '4-leg accas from the deploy call, named at the end of production</p>'
        + _acca_section(payload.get("accas"), admin=False)
        + "</section>"
        + '<section id="scan-section" style="display:none;"><div class="sec-head"><h2 class="display">The Scan</h2></div>'
        + _date_pills(d, "/dashboard")
        + _scan_table(payload.get("board", []), admin=False, payload_date=payload.get("date", ""))
        + "</section>"
        + '<section id="search-section" style="display:none;"><div class="sec-head"><h2 class="display">Search</h2></div>'
        + '<div class="admin-search-bar">'
        + '<input type="search" id="client-search" placeholder="Search team, league, fixture…" aria-label="Search fixtures">'
        + f'<select id="client-filter-league" aria-label="Filter by league"><option value="">All leagues</option>{league_opts}</select>'
        + "</div>"
        + '<div id="client-search-summary" class="flags"></div>'
        + _scan_table(board, admin=False, payload_date=payload.get("date", ""))
        + "</section>"
        + "</main>"
        + _chat_tab()
        + _chat_fab()
        + _tab_bar("call", "/dashboard")
    )
    return html_shell("OLP XDV — Today's Board", body,
                      script=_js_refs(asset_base, "scan", "tab", "chat",
                                      "client_search", "theme"),
                      asset_base=asset_base)


def render_admin_dashboard(payload: dict, asset_base: str = "/static") -> str:
    """The authed /admin view — the full payload including model internals,
    verification, cap, data flags, yesterday-graded and the honest footer."""
    n_leagues = payload.get("n_leagues") or len(payload.get("leagues_scanned", []))
    n_call = sum(1 for bf in payload.get("board", []) if bf.get("on_deploy_shortlist"))
    d = payload.get("date", "")
    published_stamp = ""
    booking_codes = None
    if d:
        from webapp import schema as S
        try:
            pub = S.read_published(d)
            if pub:
                published_stamp = f'<div class="published-stamp">✅ Published to client — {d}</div>'
        except Exception:
            pass  # not published yet — honest, not an error
        # Separate read: a missing published board must not hide the codes.
        booking_codes = S.read_booking_codes(d)
    body = (
        _board_header(payload, admin=True)
        + '<div class="paper-strip mono">PAPER ONLY — no stake is placed by this system</div>'
        + '<div class="admin-actions">'
        + f'<button class="btn-primary publish-btn" data-date="{html.escape(d)}">'
        + 'Approve → Publish to Client</button>'
        + f'{published_stamp}'
        + '</div>'
        + _produce_panel()
        + _admin_search_bar(payload)
        + _market_select_panel(payload)
        + "<main>"
        + '<section id="call-section"><div class="sec-head"><h2 class="display">The Call</h2>'
        + f'<span class="cap-pill">{n_call} deploy (no cap)</span></div>'
        + '<p class="sec-sub">All whitelisted leagues are one unified pool — every '
        + 'rated fixture is deploy-eligible, no cap, ranked by EV/conviction '
        + '(Architect 2026-08-10). The full 3-day production shown; the BET is '
        + 'today\'s fixtures only (see Produced Bet / Acca). Paper only, zero '
        + 'capital.</p>'
        + _the_call(payload.get("board", []), admin=True)
        + "</section>"
        + '<section id="scan-section" style="display:none;"><div class="sec-head"><h2 class="display">The Scan</h2></div>'
        + f'<p class="sec-sub">Every fixture across all {n_leagues} scanned leagues</p>'
        + _date_pills(d, "/admin")
        + _scan_table(payload.get("board", []), admin=True, payload_date=payload.get("date", ""))
        + "</section>"
        + '<section id="search-section" style="display:none;"><div class="sec-head"><h2 class="display">Board Search</h2></div>'
        + '<p class="sec-sub">Filter today\'s board by team, league, or market</p>'
        + _admin_search_bar(payload)
        + "</section>"
        + _flags_block(payload.get("data_flags", []))
        + '<section id="produced-section" class="cv-auto"><div class="sec-head"><h2 class="display">Today\'s Produced Bet</h2></div>'
        + '<p class="sec-sub">The produced-bet record (ID415) — every rated fixture with a '
        + 'kickoff today is one leg; the verified outcome is written next day</p>'
        + _produced_bet_block(payload.get("produced_bet"), admin=True)
        + "</section>"
        + '<section id="acca-section" class="cv-auto"><div class="sec-head"><h2 class="display">Today\'s 4-Leg Acca</h2></div>'
        + '<p class="sec-sub">Today\'s fixtures only (standing rule) — a set of 4-leg accas '
        + 'from the deploy call, each leg capital-cleared (ID405). EV is a model '
        + 'internal, admin-only.</p>'
        + _acca_section(payload.get("accas"), admin=True)
        + "</section>"
        + '<section id="booking-section" class="cv-auto"><div class="sec-head"><h2 class="display">SportyBet Booking Codes</h2></div>'
        + '<p class="sec-sub">Codes captured from the day\'s accas by '
        + 'booking/booking_codes.py — paste into SportyBet to recall the slip. '
        + 'A pre-fill, never a stake.</p>'
        + _booking_codes_section(booking_codes, payload.get("accas"))
        + "</section>"
        + '<section id="verified-section" class="cv-auto"><div class="sec-head"><h2 class="display">Verified — Yesterday</h2></div>'
        + '<p class="sec-sub">Graded against full-time result, 90-min basis (HR15)</p>'
        + _yesterday_graded(payload.get("yesterday_graded", []))
        + "</section>"
        + _phase3_gate_section(payload.get("gate", {}))
        + "</main>"
        + _chat_tab()
        + _chat_fab()
        + _tab_bar("call", "/admin", d)
        + _admin_footer(payload)
    )
    return html_shell("OLP XDV — Admin Dashboard", body,
                      script=_js_refs(asset_base, "scan", "publish",
                                      "admin_search", "tab", "chat",
                                      "market_select", "produce", "signoff", "theme"),
                      asset_base=asset_base)


# ─────────────────────────────────────────────────────────────────────────────
# Admin pages (stats / why / history / 404)
# ─────────────────────────────────────────────────────────────────────────────

def _crumbs(base: str, d: str, admin: bool, page: str = "") -> str:
    """Breadcrumb bar: OLP XDV > {view} > {date} [> {page}] + admin toggle.

    `base` is '/admin' or '/dashboard', `d` is the ISO date, `admin` is True
    when the request is for /admin, `page` is an optional sub-page label."""
    view_name = "Admin" if admin else "Client"
    other_base = "/dashboard" if admin else "/admin"
    other_name = "Client View" if admin else "Admin View"
    today = _date.today().isoformat()
    crumbs = (
        f'<div class="crumbs">'
        f'<span class="crumb-link"><a href="{other_base}/{d}">{other_name}</a></span>'
        f'<span class="crumb-sep">›</span>'
        f'<span class="crumb-current">{view_name}</span>'
        + (f'<span class="crumb-sep">›</span><span class="crumb-current">{html.escape(page)}</span>' if page else "")
        + '</div>')
    return crumbs


def _min_header(today: str, crumbs: str = "") -> str:
    return (f'<header class="top"><div class="brand">'
            f'<a class="brand-link" href="/dashboard/{today}">'
            f'<span class="mark"></span>'
            f'<h1>OLP&nbsp;XDV</h1></a></div>'
            f'{crumbs}'
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
    kd = bf.get("kickoff_date") or "—"
    body = (
        _min_header(payload.get("date") or _date.today().isoformat())
        + "<main>"
        + '<section><div class="sec-head"><h2 class="display">Full analysis</h2></div>'
        + f'<div class="call-card" style="cursor:default;">'
        + f'<div class="call-top"><div>'
        + f'<div class="fixture-name">{html.escape(f"{home} v {away}")}</div>'
        + f'<div class="league-tag">{html.escape(league)} · kickoff {html.escape(kd)}</div>'
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
