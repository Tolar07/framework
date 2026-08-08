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
  padding:0 0 88px 0; /* space for bottom tab bar */
}
.mono{font-family:'IBM Plex Mono',monospace;}
.display{font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; letter-spacing:0.02em;}

header.top{
  max-width:1180px;margin:0 auto;padding:28px 20px 18px 20px;
  border-bottom:1px solid var(--line);
}
.brand{display:flex;align-items:baseline;gap:10px;}
.brand .mark{
  width:8px;height:8px;background:var(--amber);border-radius:1px;
  transform:rotate(45deg);flex:none;
}
.brand h1{font-size:22px;font-weight:700;margin:0;letter-spacing:0.04em;}
.brand-link{display:flex;align-items:baseline;gap:10px;color:inherit;text-decoration:none;}
.brand-link:hover h1{opacity:.85;transition:opacity .15s;}
.brand-link .mark{transition:transform .15s;}
.brand-link:hover .mark{transform:rotate(90deg);}
.crumbs{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:11.5px;color:var(--ink-faint);}
.crumb-link a{color:var(--amber);text-decoration:none;}
.crumb-link a:hover{text-decoration:underline;}
.crumb-sep{color:var(--ink-faint);opacity:.5;}
.crumb-current{color:var(--ink);font-weight:500;}
.brand .phase{
  font-size:11px;color:var(--amber);border:1px solid var(--amber-dim);
  padding:2px 8px;border-radius:20px;margin-left:auto;font-family:'IBM Plex Mono',monospace;
}
.meta-row{display:flex;gap:18px;margin-top:12px;font-size:12.5px;color:var(--ink-dim);flex-wrap:wrap;}
.meta-row b{color:var(--ink);font-weight:600;}
.date-nav{
  display:flex;align-items:center;gap:8px;margin-top:14px;flex-wrap:wrap;
  font-size:12px;color:var(--ink-dim);
}
.date-nav-btn{
  display:inline-flex;align-items:center;justify-content:center;
  width:28px;height:28px;border:1px solid var(--line);border-radius:8px;
  background:var(--surface);color:var(--ink);text-decoration:none;
  transition:border-color 0.15s,background 0.15s;
}
.date-nav-btn:hover{border-color:var(--amber-dim);background:var(--surface-2);}
.date-nav-input{
  padding:5px 8px;background:var(--surface-2);border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font-family:'IBM Plex Mono',monospace;font-size:12px;
}
.date-nav-input::-webkit-calendar-picker-indicator{filter:invert(0.7);cursor:pointer;}
.date-nav-today{
  padding:5px 10px;border:1px solid var(--amber-dim);border-radius:8px;
  color:var(--amber);text-decoration:none;font-size:11.5px;transition:opacity 0.15s;
}
.date-nav-today:hover{opacity:0.85;}
.date-nav-label{font-size:11.5px;color:var(--ink-faint);font-family:'IBM Plex Mono',monospace;}
.paper-strip{
  max-width:1180px;margin:0 auto;padding:9px 20px;background:#1E1710;
  border-bottom:1px solid #3A2E18;color:#D8A659;font-size:12px;text-align:center;
  letter-spacing:0.03em;
}

main{max-width:1180px;margin:0 auto;padding:0 20px;}
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
/* THE CALL on a wide desktop is a responsive card grid; it collapses to one
   column on a phone (minmax floor) and reflows to 2-3 columns as the window
   widens. Applied to BOTH dashboards via _the_call. */
.call-grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:14px;align-items:stretch;
}
.call-grid .call-card{margin-bottom:0;display:flex;flex-direction:column;}
.call-grid .call-card .full-analysis{margin-top:auto;padding-top:14px;}
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

/* THE CALL tier-grouped sections (admin "show all the tiers") */
.tier-section{margin-bottom:24px;}
.tier-head{
  display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:14px;
}
.tier-name{
  font-family:'Barlow Condensed',sans-serif;text-transform:uppercase;
  letter-spacing:0.02em;color:var(--amber);font-weight:700;font-size:15px;
}
.tier-count{
  font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--ink-faint);
  white-space:nowrap;
}
.tier-badge.deploy{
  background:var(--teal);margin-left:6px;
}
.produce-summary{
  margin-top:16px;padding:16px;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius);
  font-size:12.5px;color:var(--ink-dim);line-height:1.7;
}
.produce-summary h3{margin:0 0 10px 0;font-size:14px;color:var(--ink);}
.produce-summary ul{margin:0;padding-left:16px;}
.produce-summary li{margin-bottom:6px;}
.produce-summary b{color:var(--ink);}
.produce-summary .honest-line{
  margin-top:12px;padding-top:10px;border-top:1px dashed var(--line);
  color:var(--amber);font-size:12px;
}

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
  max-width:1180px;margin:40px auto 0 auto;padding:18px 20px 0 20px;
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

/* Bottom tab bar — ScoreAI-style with pill active state */
.tab-bar{
  position:fixed;bottom:0;left:0;right:0;z-index:100;
  display:flex;background:var(--surface);
  border-top:1px solid var(--line);
  padding:8px env(safe-area-inset-bottom) 8px env(safe-area-inset-left);
  gap:6px;
}
.tab-btn{
  flex:1;display:flex;align-items:center;justify-content:center;gap:6px;
  padding:10px 12px;border:none;background:transparent;color:var(--ink-dim);
  font-family:'Inter',sans-serif;font-size:12px;font-weight:500;
  border-radius:var(--radius);cursor:pointer;
  transition:color 0.15s,background 0.15s,border-color 0.15s;
}
.tab-btn svg{width:18px;height:18px;stroke:currentColor;stroke-width:2;fill:none;flex:none;}
.tab-btn.active{
  background:rgba(216,166,89,0.1);border:1px solid var(--amber-dim);
  color:var(--amber);font-weight:600;
}
.tab-btn:not(.active):hover{color:var(--ink);background:rgba(255,255,255,0.03);}
.tab-btn:focus-visible{outline:none;}
@media (max-width:480px){
  .tab-btn{padding:10px 8px;font-size:11px;}
}

/* Date scroller pills */
.date-pills{
  display:flex;gap:6px;padding:10px 20px;overflow-x:auto;
  -webkit-overflow-scrolling:touch;scroll-snap-type:x mandatory;
  scrollbar-width:thin;scrollbar-color:var(--line) transparent;
}
.date-pill{
  flex:none;padding:6px 12px;border:1px solid var(--line);border-radius:999px;
  background:var(--surface);color:var(--ink);font-size:11.5px;
  font-family:'IBM Plex Mono',monospace;white-space:nowrap;
  text-decoration:none;scroll-snap-align:start;
  transition:border-color 0.15s,background 0.15s,color 0.15s;
}
.date-pill:hover{border-color:var(--amber-dim);background:var(--surface-2);}
.date-pill.today{
  border-color:var(--amber);color:var(--amber);background:rgba(216,166,89,0.1);
  font-weight:600;
}

/* Select Markets panel (admin) — ScoreAI collapsible style */
.market-select-panel{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  margin-bottom:16px;overflow:hidden;
}
.market-select-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 16px;cursor:pointer;
  transition:background 0.15s;
}
.market-select-header:hover{background:rgba(255,255,255,0.02);}
.market-select-title{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--ink);}
.market-select-title svg{width:18px;height:18px;color:var(--amber);flex:none;}
.market-select-chevron{color:var(--ink-faint);font-size:12px;transition:transform 0.2s;flex:none;}
.market-select-panel.collapsed .market-select-chevron{transform:rotate(-90deg);}
.market-select-body{padding:0 16px 14px 16px;display:block;}
.market-select-panel.collapsed .market-select-body{display:none;}
.market-select-actions{display:flex;gap:10px;margin-bottom:10px;}
.market-select-action{
  font-size:12px;padding:0;border:none;background:transparent;
  color:var(--amber);cursor:pointer;font-weight:500;
}
.market-select-action:hover{text-decoration:underline;}
.market-checkboxes{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px;}
.market-checkbox{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink);}
.market-checkbox input{width:16px;height:16px;accent-color:var(--amber);flex:none;}

/* AI Analyst chat tab */
.chat-tab{
  position:fixed;bottom:0;left:0;right:0;z-index:200;max-width:1180px;
  margin:0 auto;padding:0 20px 88px 20px;
}
.chat-tab.hidden{display:none;}
/* Floating opener for the AI Analyst — the only path into the chat panel */
.chat-fab{
  position:fixed;right:20px;bottom:100px;z-index:190;
  display:inline-flex;align-items:center;gap:8px;
  padding:11px 16px;border-radius:999px;border:1px solid var(--amber-dim);
  background:var(--surface);color:var(--ink);font-size:13px;font-weight:600;
  cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,0.35);
  transition:border-color 0.15s,color 0.15s,transform 0.05s;
}
.chat-fab:hover{border-color:var(--amber);color:var(--amber);}
.chat-fab:active{transform:scale(0.98);}
.chat-fab .fab-ico{font-size:15px;line-height:1;}
.chat-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius) var(--radius) 0 0;
}
.chat-title{font-size:14px;font-weight:600;color:var(--ink);}
.chat-close{background:none;border:none;color:var(--ink-dim);font-size:20px;cursor:pointer;}
.chat-messages{
  flex:1;overflow-y:auto;padding:16px;background:var(--bg);
  border:1px solid var(--line);border-top:none;border-radius:0 0 var(--radius) var(--radius);
  max-height:300px;display:flex;flex-direction:column;gap:12px;
}
.chat-message{display:flex;gap:8px;max-width:85%;}
.chat-message.user{align-self:flex-end;flex-direction:row-reverse;}
.chat-message .bubble{
  padding:10px 14px;border-radius:16px;font-size:13px;line-height:1.5;
}
.chat-message.assistant .bubble{background:var(--surface);border:1px solid var(--line);color:var(--ink);border-bottom-left-radius:4px;}
.chat-message.user .bubble{background:var(--amber);color:var(--bg);border-bottom-right-radius:4px;}
.chat-input-area{display:flex;gap:8px;padding:12px;background:var(--surface);border:1px solid var(--line);border-top:none;border-radius:0 0 var(--radius) var(--radius);}
.chat-input{flex:1;padding:10px 14px;background:var(--bg);border:1px solid var(--line);border-radius:999px;color:var(--ink);font-family:'Inter',sans-serif;font-size:13px;}
.chat-input:focus{outline:none;border-color:var(--amber);}
.chat-send{padding:10px 18px;background:var(--amber);color:var(--bg);border:none;border-radius:999px;font-weight:600;cursor:pointer;}
.chat-send:disabled{opacity:0.5;cursor:not-allowed;}
.chat-quick{display:flex;gap:6px;flex-wrap:wrap;padding:0 12px 12px 12px;}
.chat-quick-btn{font-size:11px;padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:var(--surface-2);color:var(--ink);cursor:pointer;}
.chat-quick-btn:hover{border-color:var(--amber);}

/* Fixture card — ScoreAI schedule layout (badge — team — vs — team — badge) */
.fixture-card{
  display:flex;align-items:center;gap:12px;padding:14px 16px;
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  margin-bottom:8px;transition:border-color 0.15s;
}
.fixture-card:hover{border-color:var(--amber-dim);}
.fixture-card .crest{width:32px;height:32px;}
.fixture-card .teams{
  flex:1;display:flex;align-items:center;justify-content:center;gap:14px;
}
.fixture-card .team{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:80px;}
.fixture-card .team-name{font-weight:600;font-size:13px;color:var(--ink);text-align:center;}
.fixture-card .vs{color:var(--ink-faint);font-size:11px;font-weight:700;letter-spacing:0.05em;}
.fixture-card .meta{
  display:flex;flex-direction:column;align-items:flex-end;gap:4px;
  font-size:11px;color:var(--ink-dim);min-width:50px;
}
.fixture-card .kickoff{font-family:'IBM Plex Mono',monospace;font-weight:500;}
.fixture-card .star{
  color:var(--ink-faint);cursor:pointer;font-size:16px;
  transition:color 0.15s,transform 0.15s;
}
.fixture-card .star.active{color:var(--amber);transform:scale(1.15);}
.fixture-card .star:hover{color:var(--amber);}

/* Produce panel — Search → Select → Produce (admin Search tab) */
.produce-panel{margin-top:12px;}
.produce-toolbar{display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap;}
.produce-toolbar select,.produce-toolbar input{
  padding:8px 12px;background:var(--surface-2);border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font-family:'Inter',sans-serif;font-size:12px;
}
.produce-toolbar input{flex:1;min-width:180px;}
.produce-toolbar select:focus,.produce-toolbar input:focus{outline:none;border-color:var(--amber);}
.produce-results{max-height:400px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--bg);}
.produce-league-group{padding:8px 12px;}
.produce-league-name{font-size:12px;font-weight:600;color:var(--amber);margin-bottom:6px;padding:4px 0;border-bottom:1px solid var(--line);}
.produce-item{display:flex;align-items:center;gap:10px;padding:8px 12px;cursor:pointer;transition:background 0.12s;}
.produce-item:hover{background:rgba(216,166,89,0.04);}
.produce-item input{width:16px;height:16px;accent-color:var(--amber);flex:none;}
.produce-item-text{font-size:12.5px;color:var(--ink);flex:1;}
.produce-item-meta{font-size:11px;color:var(--ink-faint);font-family:'IBM Plex Mono',monospace;}
.produce-tray{
  display:flex;align-items:center;gap:12px;padding:12px 16px;
  background:var(--surface);border:1px solid var(--amber-dim);border-radius:var(--radius);
  margin-top:12px;
}
.produce-tray .btn-primary{flex:none;}
.produce-result{
  margin-top:16px;border:1px solid var(--line);border-radius:var(--radius);
  background:var(--bg);overflow:hidden;
}
.produce-result-header{
  display:flex;align-items:center;gap:12px;padding:12px 16px;
  background:var(--surface);border-bottom:1px solid var(--line);
  font-size:12px;color:var(--ink-dim);
}
.produce-flags{padding:8px 16px;}
.produce-cards{padding:12px 16px;}

/* Produce day picker — "produce the bet for that day" chips + date input */
.produce-day-chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;}
.produce-day-chip{
  font-size:11.5px;padding:6px 12px;border:1px solid var(--line);
  border-radius:999px;background:var(--surface-2);color:var(--ink-dim);
  cursor:pointer;transition:border-color 0.15s,color 0.15s;
}
.produce-day-chip:hover{border-color:var(--amber-dim);color:var(--amber);}
.produce-day-chip.active{border-color:var(--amber);color:var(--amber);background:rgba(216,166,89,0.1);}

/* League card — ScoreAI card layout (badge + name + season + matchday + country) */
tbody.league-group{width:100%;}
.league-group-header{cursor:pointer;}
.league-group-header .league-card{
  display:grid;grid-template-columns:auto auto 1fr auto;grid-template-rows:auto auto;
  align-items:center;gap:6px 14px;
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px;margin:6px 0;transition:border-color 0.15s;
}
.league-group-header:hover .league-card{border-color:var(--amber-dim);}
.league-card .league-badge{grid-row:1/3;width:44px;height:44px;border-radius:10px;}
.league-card .league-name{font-size:16px;font-weight:700;color:var(--ink);line-height:1.1;}
.league-card .league-season{font-size:12px;color:var(--ink-dim);}
.league-card .league-meta{
  display:flex;align-items:center;gap:12px;font-size:11px;color:var(--ink-faint);
  grid-column:3/4;
}
.league-card .league-meta span{display:flex;align-items:center;gap:4px;}
.league-card .league-meta svg{width:14px;height:14px;stroke:currentColor;stroke-width:2;fill:none;}
.league-card .league-chevron{
  grid-row:1/3;grid-column:4;justify-self:end;
  color:var(--amber);font-size:14px;transition:transform 0.2s;flex:none;
}
tbody.collapsed .league-chevron{transform:rotate(-90deg);}
.league-group-header:hover .league-group{background:rgba(216,166,89,0.12);}
.league-group-toggle{color:var(--amber);font-size:14px;transition:transform 0.2s;flex:none;}
tbody.collapsed .league-group-toggle{transform:rotate(-90deg);}
.league-group-badge{display:inline-flex;align-items:center;flex:none;}
.league-group-badge .flag{margin-right:0;}
.league-group-name{font-weight:600;color:var(--ink);text-transform:uppercase;font-family:'Barlow Condensed',sans-serif;letter-spacing:0.02em;flex:1;}
.league-group-count{color:var(--ink-faint);font-size:11px;font-family:'IBM Plex Mono',monospace;}

/* Hero section (client view) */
.hero-date{
  font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--ink-faint);
  text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;
}
.hero-title{
  font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;
  color:var(--amber);text-transform:uppercase;letter-spacing:0.04em;margin:0 0 12px 0;
}
.hero-match{
  margin-bottom:14px;
}
.hero-teams{
  font-size:18px;font-weight:600;color:var(--ink);
}
.hero-league{
  display:block;font-size:11px;color:var(--ink-faint);margin-top:4px;
}
.hero-pick{
  display:inline-flex;align-items:center;gap:10px;padding:10px 18px;
  background:rgba(79,184,148,0.1);border:1px solid var(--teal);
  border-radius:999px;margin-bottom:16px;
}
.hero-team{font-size:16px;font-weight:600;color:var(--teal);}
.hero-confidence{
  font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--ink);
}
.hero-cta{
  display:inline-block;padding:10px 22px;background:var(--amber);color:var(--bg);
  font-weight:600;border-radius:8px;text-decoration:none;transition:opacity 0.15s;
}
.hero-cta:hover{opacity:0.9;}

/* Admin actions + search bar */
.admin-actions{
  max-width:1180px;margin:10px auto 0 auto;padding:0 20px;
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
}
.btn-primary{
  background:var(--amber);color:var(--bg);font-weight:600;
  padding:9px 18px;border-radius:8px;border:none;cursor:pointer;
  transition:opacity 0.15s,transform 0.05s;
}
.btn-primary:hover{opacity:0.9;}
.btn-primary:active{transform:scale(0.98);}
.btn-primary:disabled{opacity:0.5;cursor:not-allowed;}
.published-stamp{
  display:none;font-size:12px;color:var(--teal);
  font-family:'IBM Plex Mono',monospace;
}
.admin-search-bar{
  max-width:1180px;margin:14px auto 0 auto;padding:0 20px;
  display:flex;gap:10px;flex-wrap:wrap;align-items:center;
  font-size:12px;
}
.admin-search-bar input[type="search"]{
  flex:1;min-width:180px;padding:8px 12px;
  background:var(--surface-2);border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font-family:'Inter',sans-serif;
}
.admin-search-bar input[type="search"]::placeholder{color:var(--ink-faint);}
.admin-search-bar select{
  padding:8px 12px;background:var(--surface-2);border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font-family:'Inter',sans-serif;
  min-width:120px;
}
.admin-search-bar select:focus,
.admin-search-bar input:focus{outline:none;border-color:var(--amber);}

/* League group collapse — hiding the fixture rows under a collapsed group */
tbody.collapsed .league-row,
tbody.collapsed .detail-row{
  display:none;
}

/* Crests and flags */
.crest{
  width:18px;height:18px;border-radius:50%;object-fit:cover;
  background:var(--surface-2);vertical-align:middle;margin-right:6px;
  border:1px solid var(--line);flex:none;
}
.crest.placeholder{
  border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
  font-size:9px;font-weight:700;color:var(--ink-faint);background:var(--surface-2);
}
.flag{
  width:22px;height:16px;border-radius:2px;object-fit:cover;
  vertical-align:middle;margin-right:6px;flex:none;
  border:1px solid var(--line);
}
.flag.placeholder{
  display:inline-flex;align-items:center;justify-content:center;
  font-size:9px;font-weight:600;color:var(--ink-faint);background:var(--surface-2);
}

"""

_SCAN_JS = """<script>
  // Row expand/collapse for the full-analysis detail row.
  function toggleScanRow(id){
    document.getElementById(id).classList.toggle('open');
    event.currentTarget.classList.toggle('open');
  }
  // League group collapse is wired inline on each header row
  // (onclick toggles 'collapsed' on the parent tbody).
</script>"""

_PUBLISH_JS = """<script>
  document.addEventListener('DOMContentLoaded', function() {
    var btn = document.querySelector('.publish-btn');
    var stamp = document.querySelector('.published-stamp');
    if (btn) {
      btn.addEventListener('click', function() {
        var d = btn.getAttribute('data-date');
        if (!d) return;
        btn.disabled = true;
        btn.textContent = 'Publishing…';
        fetch('/api/admin/publish', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({date: d})
        }).then(function(r){ return r.json(); })
          .then(function(data) {
            if (data.ok) {
              btn.style.display = 'none';
              if (stamp) stamp.style.display = 'block';
            } else {
              btn.disabled = false;
              btn.textContent = 'Approve → Publish to Client';
              alert('Publish failed: ' + (data.error || 'unknown'));
            }
          }).catch(function(e) {
            btn.disabled = false;
            btn.textContent = 'Approve → Publish to Client';
            alert('Network error: ' + e);
          });
      });
    }
  });
</script>"""

_ADMIN_SEARCH_JS = """<script>
  document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('admin-search');
    var leagueSel = document.getElementById('admin-filter-league');
    var tierSel = document.getElementById('admin-filter-tier');
    var marketSel = document.getElementById('admin-filter-market');
    var statusSel = document.getElementById('admin-filter-status');
    var allRows = document.querySelectorAll('table.scan-table tbody tr.clickable');
    var allDetail = document.querySelectorAll('table.scan-table tbody tr.detail-row');
    function filter() {
      var q = (input?.value || '').toLowerCase();
      var league = leagueSel?.value || '';
      var tier = tierSel?.value || '';
      var market = marketSel?.value || '';
      var status = statusSel?.value || '';
      allRows.forEach(function(tr, i) {
        var txt = tr.textContent.toLowerCase();
        var bf = tr.dataset;
        var ok = true;
        if (q && !txt.includes(q)) ok = false;
        if (league && bf.league !== league) ok = false;
        if (tier && bf.tier !== tier) ok = false;
        if (market && bf.market !== market) ok = false;
        if (status && bf.status !== status) ok = false;
        tr.style.display = ok ? '' : 'none';
        if (allDetail[i]) allDetail[i].style.display = ok ? '' : 'none';
      });
    }
    [input, leagueSel, tierSel, marketSel, statusSel].forEach(function(el) {
      if (el) el.addEventListener('input', filter);
    });
  });
</script>"""

_CLIENT_SEARCH_JS = """<script>
  // Client Search tab — live filter over the scan table in #search-section.
  // Works on the trimmed payload only (team/league text already on the page),
  // so the data-leak boundary (no model internals) is untouched.
  document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('client-search');
    if (!input) return;
    var leagueSel = document.getElementById('client-filter-league');
    var groups = document.querySelectorAll('#search-section table.scan-table tbody.league-group');
    var summary = document.getElementById('client-search-summary');
    function filter() {
      var q = (input.value || '').toLowerCase();
      var league = leagueSel.value || '';
      var shown = 0;
      groups.forEach(function(tb) {
        var any = false;
        var lastOk = true;
        tb.querySelectorAll('tr').forEach(function(tr) {
          if (tr.classList.contains('league-row')) {
            var txt = tr.textContent.toLowerCase();
            var ok = true;
            if (q && !txt.includes(q)) ok = false;
            if (league && tr.dataset.league !== league) ok = false;
            tr.style.display = ok ? '' : 'none';
            if (ok) any = true;
            lastOk = ok;
          } else if (tr.classList.contains('detail-row')) {
            // A detail row always immediately follows its fixture row
            tr.style.display = lastOk ? '' : 'none';
          }
        });
        tb.style.display = any ? '' : 'none';
        if (any) shown++;
      });
      if (summary) {
        summary.innerHTML = shown
          ? '<div class="flag-line">' + shown + ' league' + (shown === 1 ? '' : 's') + ' match your search.</div>'
          : '<div class="flag-line">No fixtures match — try another team or league.</div>';
      }
    }
    input.addEventListener('input', filter);
    if (leagueSel) leagueSel.addEventListener('change', filter);
  });
</script>"""

_TAB_JS = """<script>
  function switchTab(tabId) {
    // Only toggle Call/Scan/Search — flags + verified stay visible always
    var tabSections = ['call-section', 'scan-section', 'search-section'];
    tabSections.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.style.display = (id === tabId + '-section') ? 'block' : 'none';
    });
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    window.scrollTo(0, 0);
  }
  function navTab(tabId, e) {
    if (e) e.preventDefault();
    switchTab(tabId);
    return false;
  }
  document.addEventListener('DOMContentLoaded', function() {
    var hash = window.location.hash.slice(1);
    if (hash && ['call', 'scan', 'search'].includes(hash)) {
      switchTab(hash);
    }
  });
  window.addEventListener('hashchange', function() {
    var h = location.hash.slice(1);
    if (['call','scan','search'].includes(h)) switchTab(h);
  });
</script>"""

_CHAT_JS = """<script>
  function openChatTab() {
    document.getElementById('chat-tab').classList.remove('hidden');
    var fab = document.getElementById('chat-fab');
    if (fab) fab.style.display = 'none';
    document.getElementById('chat-input').focus();
  }
  function closeChatTab() {
    document.getElementById('chat-tab').classList.add('hidden');
    var fab = document.getElementById('chat-fab');
    if (fab) fab.style.display = '';
  }
  function getBoardDate() {
    var tab = document.getElementById('chat-tab');
    return tab ? (tab.getAttribute('data-date') || '') : '';
  }
  function sendChatMessage() {
    var input = document.getElementById('chat-input');
    var msg = input.value.trim();
    if (!msg) return;
    appendMessage('user', msg);
    input.value = '';
    document.getElementById('chat-send').disabled = true;
    // Call the AI Analyst API
    fetch('/api/analyst', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg, date: getBoardDate()})
    }).then(function(r) { return r.json(); })
      .then(function(data) {
        appendMessage('assistant', data.reply || 'Error: no reply');
      }).catch(function(e) {
        appendMessage('assistant', 'Network error: ' + e);
      });
  }
  function sendQuickPrompt(prompt) {
    var input = document.getElementById('chat-input');
    input.value = prompt;
    sendChatMessage();
  }
  function appendMessage(role, text) {
    var container = document.getElementById('chat-messages');
    var div = document.createElement('div');
    div.className = 'chat-message ' + role;
    div.innerHTML = '<div class="bubble">' + escapeHtml(text) + '</div>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }
  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('chat-input');
    var sendBtn = document.getElementById('chat-send');
    if (!input) return;
    input.addEventListener('input', function() {
      sendBtn.disabled = !input.value.trim();
    });
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (input.value.trim()) sendChatMessage();
      }
    });
  });
</script>"""

_MARKET_SELECT_JS = """<script>
  function toggleAllMarkets(select) {
    document.querySelectorAll('.market-checkbox input[name="market-col"]').forEach(function(cb) {
      cb.checked = select;
      toggleMarketColumn(cb.value, select);
    });
  }
  function toggleMarketColumn(key, show) {
    var isAdmin = document.querySelector('.phase.mono')?.textContent?.includes('ADMIN') || false;
    var thIndex = -1;
    var headers = document.querySelectorAll('.scan-table th');
    headers.forEach(function(th, i) {
      if (th.textContent.includes(key.replace('/', '')) || th.textContent === key) {
        thIndex = i;
      }
    });
    if (thIndex === -1) return;
    var selector = 'th:nth-child(' + (thIndex + 1) + '), td:nth-child(' + (thIndex + 1) + ')';
    document.querySelectorAll(selector).forEach(function(cell) {
      cell.style.display = show ? '' : 'none';
    });
  }
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.market-checkbox input').forEach(function(cb) {
      cb.addEventListener('change', function() {
        toggleMarketColumn(cb.value, cb.checked);
      });
    });
  });
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
    # Use flagcdn.com (free, no key, SVG flags)
    url = f"https://flagcdn.com/24x16/{code.lower()}.svg"
    return f'<img class="flag" src="{url}" alt="{code}" title="{league}">'


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
        return f'<img class="crest" src="{url}" alt="{team}" title="{team}" loading="lazy">'
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
    <span class="star{' active' if is_fav else ''}" onclick="event.stopPropagation(); toggleFavorite('{html.escape(fixture_key)}')">★</span>
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
        tier = html.escape(str(bf.get("softness_tier", "?")))
        deploy = ('<span class="tier-badge deploy">DEPLOY</span>'
                  if bf.get("on_deploy_shortlist") else "")
        head = card_head + f'<div class="tier-badge">TIER {tier}</div>' + deploy
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

    return f"""<div class="call-card" onclick="this.classList.toggle('open')">
  {head}
  {stamp}
  <div class="expand-hint"><span class="chevron">▸</span> {hint}</div>
  <div class="full-analysis">
    {grid}
    {extras}
  </div>
</div>"""


def _tier_grouped_call(board: list[dict]) -> str:
    """THE CALL grouped by softness tier — the FULL production, sorted into its
    trust tiers (Architect order 2026-08-08). Every fixture stays visible: A/B
    deploy-eligible first, C/D scan-only after, ranked within each tier by the
    deploy pool first then model confidence. The DEPLOY pill (on the card)
    marks the actual cap-6 pool — the tier grouping is display, the deploy cap
    + market gate are unchanged rules. The public client view does NOT use this
    (it renders the deploy shortlist only, per the data-leak boundary)."""
    order = ["A", "B", "C", "D", "?"]
    labels = {
        "A": "Tier A — deploy-eligible",
        "B": "Tier B — deploy-eligible",
        "C": "Tier C — scan-only, never a capital pick",
        "D": "Tier D — scan-only, never a capital pick",
        "?": "Unrated league",
    }
    groups: dict[str, list[dict]] = {}
    for bf in board:
        groups.setdefault(str(bf.get("softness_tier", "?")), []).append(bf)
    out: list[str] = []
    for tier in order:
        grp = groups.get(tier)
        if not grp:
            continue
        # Deploy-pool picks first, then strongest model confidence.
        grp.sort(key=lambda b: (not b.get("on_deploy_shortlist"),
                                -_pick_confidence(b)))
        n_deploy = sum(1 for b in grp if b.get("on_deploy_shortlist"))
        count = f"{len(grp)} fixture{'s' if len(grp) != 1 else ''}"
        if n_deploy:
            count += f" · {n_deploy} in deploy pool"
        cards = "".join(_call_card(b, admin=True) for b in grp)
        out.append('<div class="tier-section">'
                   f'<div class="tier-head"><span class="tier-name">'
                   f'{html.escape(labels.get(tier, labels["?"]))}</span>'
                   f'<span class="tier-count">{count}</span></div>'
                   f'<div class="call-grid">{cards}</div>'
                   '</div>')
    return "".join(out)


def _the_call(board: list[dict], admin: bool = False) -> str:
    if not board:
        return ('<div class="flags"><div class="flag-line"><span class="mk">—</span> '
                'No fixtures on this board today — NO DATA — PENDING.</div></div>')
    if admin:
        # The full production sorted into its softness tiers — nothing produced
        # is hidden, ranked by the trust level assigned to each league.
        return _tier_grouped_call(board)
    rows = [bf for bf in board if bf.get("on_deploy_shortlist")]
    if not rows:
        return ('<div class="flags"><div class="flag-line"><span class="mk">—</span> '
                'No deploy-eligible call today (softness A/B only).</div></div>')
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
        # Sort fixtures by pick confidence (highest first)
        fixtures_sorted = sorted(fixtures, key=_pick_confidence, reverse=True)

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
        body_parts.append(f"""<tbody class="league-group{collapsed_class}" data-league="{html.escape(league)}">
<tr class="league-group-header" onclick="this.parentElement.classList.toggle('collapsed')">
  <td colspan="{n_cols}">
    <div class="league-card">
      <div class="league-badge">{flag}</div>
      <div class="league-name">{html.escape(league)}</div>
      <div class="league-meta">
        <span><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>{html.escape(matchday)}</span>
        <span><svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>{html.escape(country_name)}</span>
      </div>
      <span class="league-chevron">▾</span>
      <div class="league-season">{html.escape(season)} · {len(fixtures_sorted)} fixture{'s' if len(fixtures_sorted) != 1 else ''}</div>
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
            fixture_td = (f'<span class="scan-fixture">{home_badged} v {away_badged}</span>'
                          f'<span class="scan-league">{league_badged}</span>')
            src_td = f'<td>{_src_dot(bf)}</td>' if admin else ""
            p = bf.get("probs")
            tier = bf.get("softness_tier", "?")
            status = "deploy" if bf.get("on_deploy_shortlist") else ("no-data" if p is None else "scan-only")
            best_market = bf.get("best_market_key") or ""
            date_str = payload_date if admin else ""

            if p is None:
                reason = bf.get("rejection_reason") or "NO DATA — PENDING"
                body_parts.append(f"""<tr class="league-row" data-fixture="{html.escape(bf.get("fixture", ""))}" data-league="{html.escape(_league_of(bf.get("fixture", "")))}" data-tier="{html.escape(tier)}" data-market="{html.escape(best_market)}" data-status="{html.escape(status)}" data-date="{html.escape(date_str)}">
  <td>{fixture_td}</td>
  <td class="nodata" colspan="3">NO DATA — PENDING · {html.escape(reason)}</td>
  {src_td}
</tr>""")
                continue
            row_id = ("a-" if admin else "") + f"scan-{idx}-{html.escape(league).replace(' ', '-')}"
            c2 = _scan_1x2(p)
            c3 = _scan_goals(p)
            c4 = _scan_dc_btts(p)
            body_parts.append(f"""<tr class="clickable league-row" onclick="toggleScanRow('{row_id}')" data-fixture="{html.escape(bf.get("fixture", ""))}" data-league="{html.escape(_league_of(bf.get("fixture", "")))}" data-tier="{html.escape(tier)}" data-market="{html.escape(best_market)}" data-status="{html.escape(status)}" data-date="{html.escape(date_str)}">
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
            f'<input type="date" class="date-nav-input" value="{d}" data-base="{base}" '
            f'aria-label="Jump to a board date">'
            f'<a class="date-nav-btn" href="{base}/{nxt}" aria-label="Next day">▶</a>'
            f'{today_link}'
            f'<span class="date-nav-label">{_friendly_date(d)}</span>'
            f'</div>'
            f'<script>'
            f"document.addEventListener('DOMContentLoaded',function(){{"
            f"var i=document.querySelector('.date-nav-input');"
            f"if(i)i.addEventListener('change',function(){{"
            f"if(i.value)window.location.href=i.getAttribute('data-base')+'/'+i.value;}});}});"
            f'</script>')


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
        brand_right = ""
        meta = f'<span>{date_txt}</span><span><b>07:00</b></span>'
    base = "/admin" if admin else "/dashboard"
    crumbs = _crumbs(base, d, admin)
    return f"""<header class="top">
  <div class="brand">
    <a class="brand-link" href="{base}/{d}">
      <span class="mark"></span>
      <h1>OLP&nbsp;XDV</h1>
    </a>
    {brand_right}
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
    next day. `admin=True` renders model prob / softness tier / EV; the client
    receives only fixture + pick + price + outcome (see schema.trim_payload)."""
    if not record:
        return ('<div class="flags"><div class="flag-line">NO DATA — PENDING — '
                'no produced-bet record for this date.</div></div>')
    if not record.get("produced"):
        return ('<div class="flags"><div class="flag-line">No fixtures today — '
                'no bet produced. A valid, honest result (ID415).</div></div>')
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
            verdict = '<span class="pend-tag mono">— PENDING</span>'
        rows.append(
            f'<div class="graded-row">{verdict}'
            f'<span>{html.escape(label)} — {html.escape(detail)}</span></div>')
    head = (f'TODAY\'S PRODUCED BET — {date}'
            if date else 'TODAY\'S PRODUCED BET')
    tail = ('MARKED PAPER — Phase 2, zero capital.' if admin
            else 'Predictions only — verified WON/LOST next day.')
    return ('<div class="flags" style="padding:6px 16px;">'
            f'<div class="flag-line">{head} — {record.get("n_legs", 0)} leg(s). '
            f'{tail}</div>'
            + "".join(rows) + "</div>")


def _admin_search_bar(payload: dict) -> str:
    """Search/filter controls for the admin scan table.

    The league dropdown is the FULL ID401 whitelist (engine.softness.SOFTNESS_TIER)
    plus any league actually on the board — an approved league with no fixtures
    today is still searchable, because "I need all the leagues" is an audit
    requirement, not a today-requirement. Date is NOT a filter here: it is a
    navigation control in the header (see _date_nav), so the operator can move
    between board dates instead of filtering one board."""
    board_leagues = {_league_of(bf.get("fixture", "")) for bf in payload.get("board", [])}
    try:
        from engine.softness import SOFTNESS_TIER
        whitelist = set(SOFTNESS_TIER.keys())
    except Exception:
        whitelist = set()
    leagues = sorted(whitelist | board_leagues)
    tiers = ["A", "B", "C", "D"]
    markets = ["1X2_HOME", "1X2_DRAW", "1X2_AWAY", "OVER_1_5", "OVER_2_5", "BTTS_YES"]
    statuses = ["deploy", "scan-only", "no-data"]

    league_opts = "".join(f'<option value="{html.escape(lg)}">{html.escape(lg)}</option>' for lg in leagues)
    tier_opts = "".join(f'<option value="{t}">{t}</option>' for t in tiers)
    market_opts = "".join(f'<option value="{m}">{m}</option>' for m in markets)
    status_opts = "".join(f'<option value="{s}">{s}</option>' for s in statuses)

    return f"""<div class="admin-search-bar">
  <input type="search" id="admin-search" placeholder="Search team, league, fixture…" aria-label="Search fixtures">
  <select id="admin-filter-league" aria-label="Filter by league">
    <option value="">All leagues</option>{league_opts}
  </select>
  <select id="admin-filter-tier" aria-label="Filter by softness tier">
    <option value="">All tiers</option>{tier_opts}
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
    # We'll use onclick navigation instead of href for SPA-like behavior
    tab_html = ""
    for tab_id, label, icon, _ in tabs:
        active_class = " active" if tab_id == active else ""
        tab_html += f'<button class="tab-btn{active_class}" data-tab="{tab_id}" onclick="switchTab(\'{tab_id}\')"><svg viewBox="0 0 24 24">{_tab_icon(icon)}</svg><span>{label}</span></button>'
    return f'<nav class="tab-bar" role="tablist" aria-label="Main navigation">{tab_html}</nav>'

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
  <div class="market-select-header" onclick="document.getElementById('market-select-panel').classList.toggle('collapsed')">
    <span class="market-select-title">{gear_svg} Select Markets to Display</span>
    <span class="market-select-chevron">▾</span>
  </div>
  <div class="market-select-body">
    <div class="market-select-actions">
      <button class="market-select-action" onclick="toggleAllMarkets(true)">Select All</button>
      <button class="market-select-action" onclick="toggleAllMarkets(false)">Clear All</button>
    </div>
    <div class="market-checkboxes">{checkboxes}</div>
  </div>
</div>"""

def _chat_fab() -> str:
    """Floating 'AI Analyst' opener — the only path into the chat panel
    (openChatTab() is defined in _CHAT_JS; without this button the panel is
    unreachable)."""
    return ('<button class="chat-fab" id="chat-fab" onclick="openChatTab()" '
            'aria-label="Open AI Analyst chat"><span class="fab-ico">✦</span> '
            'AI Analyst</button>')


def _chat_tab(payload_date: str = "") -> str:
    """AI Analyst chat tab — reusable component."""
    return f"""<div class="chat-tab hidden" id="chat-tab" role="dialog" aria-label="AI Analyst" data-date="{html.escape(payload_date)}">
  <div class="chat-header">
    <span class="chat-title">AI Analyst</span>
    <button class="chat-close" onclick="closeChatTab()" aria-label="Close chat">&times;</button>
  </div>
  <div class="chat-messages" id="chat-messages" role="log" aria-live="polite"></div>
  <div class="chat-quick" role="group" aria-label="Quick actions">
    <button class="chat-quick-btn" onclick="sendQuickPrompt('Analyze today\'s board')">Analyze Board</button>
    <button class="chat-quick-btn" onclick="sendQuickPrompt('Explain the top pick')">Explain Top Pick</button>
    <button class="chat-quick-btn" onclick="sendQuickPrompt('Which fixtures have the highest confidence?')">High Confidence</button>
    <button class="chat-quick-btn" onclick="sendQuickPrompt('Show me value bets')">Value Bets</button>
  </div>
  <div class="chat-input-area">
    <input type="text" class="chat-input" id="chat-input" placeholder="Ask about today's board, a fixture, or the framework..." aria-label="Chat input">
    <button class="chat-send" id="chat-send" onclick="sendChatMessage()" disabled>Send</button>
  </div>
</div>"""

def _produce_panel() -> str:
    """Admin-only: BET Production panel — visible at the top of /admin.

    Pick a league + a day, search that day's fixtures across the approved
    leagues, select matches, and produce predictions in real time. Defaults
    to today (the board's rolling window is today..+3)."""
    from engine.softness import SOFTNESS_TIER
    league_opts = "".join(
        f'<option value="{html.escape(lg)}">{html.escape(lg)}</option>'
        for lg in sorted(SOFTNESS_TIER.keys()))
    today = _date.today()
    day_isos = [(today + _timedelta(days=i)).isoformat() for i in range(4)]
    day_labels = ["Today", "Tomorrow", "+2 days", "+3 days"]
    chips = "".join(
        f'<button type="button" class="produce-day-chip" data-date="{di}" '
        f'onclick="produceSetDay(\'{di}\')">{lb}</button>'
        for di, lb in zip(day_isos, day_labels))
    return f"""<div class="produce-panel" id="produce-panel">
  <div class="produce-toolbar">
    <select id="produce-league" aria-label="Select league">
      <option value="">All leagues</option>{league_opts}
    </select>
    <input type="search" id="produce-query" placeholder="Search team name…" aria-label="Search fixtures">
    <input type="date" id="produce-date" value="{today.isoformat()}" aria-label="Produce for day" title="Pick the day to produce">
    <button id="produce-search-btn" class="btn-primary" onclick="produceSearch()">Search fixtures</button>
  </div>
  <div class="produce-day-chips">{chips}</div>
  <div id="produce-results" class="produce-results"></div>
  <div class="produce-tray" id="produce-tray" style="display:none;">
    <span id="produce-count">0 selected</span>
    <button id="produce-go" class="btn-primary" onclick="produceGo()" disabled>⚡ Produce predictions</button>
    <button class="market-select-action" onclick="produceClear()">Clear</button>
  </div>
  <div id="produce-output"></div>
</div>"""


_PRODUCE_JS = """<script>
  var _produceSelected = new Set();

  function produceSetDay(date) {
    document.getElementById('produce-date').value = date;
    document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
      ch.classList.toggle('active', ch.getAttribute('data-date') === date);
    });
    produceSearch();
  }

  function produceSearch() {
    var league = document.getElementById('produce-league').value;
    var q = document.getElementById('produce-query').value;
    var date = document.getElementById('produce-date').value || '';
    var results = document.getElementById('produce-results');
    results.innerHTML = '<div style="padding:12px;color:var(--ink-faint);">Searching fixtures for ' + escapeHtml(date || 'window') + '…</div>';
    var params = 'days=4';
    if (date) params += '&date=' + encodeURIComponent(date);
    if (league) params += '&league=' + encodeURIComponent(league);
    if (q) params += '&q=' + encodeURIComponent(q);
    fetch('/api/admin/fixtures?' + params)
      .then(function(r) {
        if (r.status === 401) { window.location.href = '/admin'; return null; }
        return r.json();
      })
      .then(function(data) {
        if (!data || !data.ok) {
          results.innerHTML = '<div style="padding:12px;color:var(--coral);">Error: ' + (data ? data.error : 'failed') + '</div>';
          return;
        }
        var html = '';
        data.leagues.forEach(function(lg) {
          html += '<div class="produce-league-group">';
          html += '<div class="produce-league-name">' + escapeHtml(lg.name) + ' (' + lg.fixtures.length + ')</div>';
          lg.fixtures.forEach(function(f) {
            var key = lg.name + '|' + f.home + '|' + f.away + '|' + f.date;
            var checked = _produceSelected.has(key) ? ' checked' : '';
            html += '<label class="produce-item">';
            html += '<input type="checkbox" data-key="' + escapeHtml(key) + '" data-league="' + escapeHtml(lg.name) + '" data-home="' + escapeHtml(f.home) + '" data-away="' + escapeHtml(f.away) + '" data-date="' + escapeHtml(f.date) + '"' + checked + '>';
            html += '<span class="produce-item-text">' + escapeHtml(f.home) + ' vs ' + escapeHtml(f.away) + '</span>';
            html += '<span class="produce-item-meta">' + escapeHtml(f.date || '') + '</span>';
            html += '</label>';
          });
          html += '</div>';
        });
        if (!data.leagues.length) {
          html = '<div style="padding:12px;color:var(--ink-faint);">No fixtures found</div>';
        }
        results.innerHTML = html;
        results.querySelectorAll('input[type=checkbox]').forEach(function(cb) {
          cb.addEventListener('change', function() {
            if (cb.checked) _produceSelected.add(cb.dataset.key);
            else _produceSelected.delete(cb.dataset.key);
            updateProduceTray();
          });
          if (_produceSelected.has(cb.dataset.key)) cb.checked = true;
        });
        updateProduceTray();
      }).catch(function(e) {
        results.innerHTML = '<div style="padding:12px;color:var(--coral);">Network error: ' + e + '</div>';
      });
  }

  function updateProduceTray() {
    var tray = document.getElementById('produce-tray');
    var count = document.getElementById('produce-count');
    var go = document.getElementById('produce-go');
    if (!tray) return;
    tray.style.display = _produceSelected.size > 0 ? 'flex' : 'none';
    count.textContent = _produceSelected.size + ' selected';
    go.disabled = _produceSelected.size === 0;
  }

  function produceClear() {
    _produceSelected.clear();
    var results = document.getElementById('produce-results');
    if (results) results.querySelectorAll('input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
    updateProduceTray();
  }

  function produceGo() {
    if (_produceSelected.size === 0) return;
    var go = document.getElementById('produce-go');
    var output = document.getElementById('produce-output');
    go.disabled = true;
    go.textContent = 'Producing…';
    output.innerHTML = '<div style="padding:20px;text-align:center;color:var(--ink-faint);">Running engine… (~3s warm)</div>';
    var groups = {};
    _produceSelected.forEach(function(key) {
      var parts = key.split('|');
      var league = parts[0], home = parts[1], away = parts[2], date = parts[3];
      if (!groups[league]) groups[league] = [];
      groups[league].push({home: home, away: away, date: date});
    });
    var groupsArr = Object.keys(groups).map(function(lg) {
      return {league: lg, fixtures: groups[lg]};
    });
    fetch('/api/admin/produce', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({groups: groupsArr})
    }).then(function(r) {
      if (r.status === 401) { window.location.href = '/admin'; return null; }
      return r.json();
    }).then(function(data) {
      go.disabled = false;
      go.textContent = '\\u26a1 Produce predictions';
      if (!data || !data.ok) {
        output.innerHTML = '<div style="padding:16px;color:var(--coral);">Error: ' + (data ? data.error : 'failed') + '</div>';
        return;
      }
      var html = '<div class="produce-result">';
      html += '<div class="produce-result-header">';
      html += '<span>' + data.n_rated + ' rated \\u00b7 ' + data.n_deploy + ' deploy-eligible \\u00b7 ' + data.elapsed_s + 's</span>';
      html += '<span class="phase mono" style="margin-left:auto;">' + escapeHtml(data.phase || '') + '</span>';
      html += '</div>';
      if (data.flags && data.flags.length) {
        html += '<div class="produce-flags">';
        data.flags.forEach(function(f) { html += '<div class="flag-line"><span class="mk">\\u26a0</span> ' + escapeHtml(f) + '</div>'; });
        html += '</div>';
      }
      html += '<div class="produce-cards">' + data.cards_html + '</div>';
      if (data.summary_html) html += data.summary_html;
      html += '</div>';
      output.innerHTML = html;
      output.querySelectorAll('.call-card').forEach(function(card) {
        card.addEventListener('click', function() { card.classList.toggle('open'); });
      });
    }).catch(function(e) {
      go.disabled = false;
      go.textContent = '\\u26a1 Produce predictions';
      output.innerHTML = '<div style="padding:16px;color:var(--coral);">Network error: ' + e + '</div>';
    });
  }

  document.addEventListener('DOMContentLoaded', function() {
    var dateInput = document.getElementById('produce-date');
    if (!dateInput) return;
    // Mark the day chip that matches the default (today)
    document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
      ch.classList.toggle('active', ch.getAttribute('data-date') === dateInput.value);
    });
    // A manual date-picker change triggers the same search
    dateInput.addEventListener('change', function() {
      document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
        ch.classList.toggle('active', ch.getAttribute('data-date') === dateInput.value);
      });
      produceSearch();
    });
  });
</script>"""


def render_dashboard(payload: dict) -> str:
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
        + '<section id="produced-section"><div class="sec-head"><h2 class="display">Today\'s Produced Bet</h2></div>'
        + '<p class="sec-sub">What the framework bet today — one leg per rated fixture, '
        + 'verified WON/LOST next day (ID415)</p>'
        + _produced_bet_block(payload.get("produced_bet"), admin=False)
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
                      script=_SCAN_JS + _TAB_JS + _CHAT_JS + _CLIENT_SEARCH_JS)


def render_admin_dashboard(payload: dict) -> str:
    """The authed /admin view — the full payload including model internals,
    verification, cap, data flags, yesterday-graded and the honest footer."""
    n_leagues = payload.get("n_leagues") or len(payload.get("leagues_scanned", []))
    n_call = sum(1 for bf in payload.get("board", []) if bf.get("on_deploy_shortlist"))
    d = payload.get("date", "")
    published_stamp = ""
    if d:
        try:
            from webapp import schema as S
            pub = S.read_published(d)
            if pub:
                published_stamp = f'<div class="published-stamp">✅ Published to client — {d}</div>'
        except Exception:
            pass
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
        + f'<span class="cap-pill">{n_call} / 6 CAP</span></div>'
        + '<p class="sec-sub">All tiers grouped by trust — A/B deploy-eligible (DEPLOY = in today\'s cap-6 pool), C/D scan-only. Paper only, zero capital.</p>'
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
        + '<section id="produced-section"><div class="sec-head"><h2 class="display">Today\'s Produced Bet</h2></div>'
        + '<p class="sec-sub">The produced-bet record (ID415) — every rated fixture with a '
        + 'kickoff today is one leg; the verified outcome is written next day</p>'
        + _produced_bet_block(payload.get("produced_bet"), admin=True)
        + "</section>"
        + '<section id="verified-section"><div class="sec-head"><h2 class="display">Verified — Yesterday</h2></div>'
        + '<p class="sec-sub">Graded against full-time result, 90-min basis (HR15)</p>'
        + _yesterday_graded(payload.get("yesterday_graded", []))
        + "</section>"
        + "</main>"
        + _chat_tab()
        + _chat_fab()
        + _tab_bar("call", "/admin", d)
        + _admin_footer(payload)
    )
    return html_shell("OLP XDV — Admin Dashboard", body, script=_SCAN_JS + _PUBLISH_JS + _ADMIN_SEARCH_JS + _TAB_JS + _CHAT_JS + _MARKET_SELECT_JS + _PRODUCE_JS)


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
