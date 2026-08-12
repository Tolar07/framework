"""Server route tests for the single-tier feed dashboard (Architect 2026-08-12).

The web page IS the Telegram board: /dashboard/<date> is served straight from
the raw board_<date>.json via schema.build_feed_payload() — no publish step, no
admin tier. Auto-feed = auto-publish. Removed admin routes (/admin*, /stats,
/why, /api/admin/*, /api/trigger-board) are GONE and 404 (not 401/503). The
public JSON is the feed payload (lean + honest gate numbers, no model
internals). /history, /api/live-scores, /api/analyst, /health, /metrics stay.

A real ThreadingHTTPServer on an ephemeral port, with BOARD_DIR redirected to a
temp folder so the test can't touch the real boards or codes files."""
import json
import os
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen, Request
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp import schema, server
from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_server_"))
boards = tmp / "boards"
boards.mkdir()
today = date.today().isoformat()

# Deterministic gate state: pin the Architect sign-off OFF so the feed renders
# the honest "NOT MET" callout (the OVERRIDE path has its own render test).
os.environ["ARCHITECT_SIGNOFF"] = "0"


def _rated_bf() -> BoardFixture:
    return BoardFixture(
        fixture="Fenerbahce v Sturm Graz (Champions League)",
        probs=FixtureProbabilities("Fenerbahce", "Sturm Graz",
                                   lambda_home=1.8, lambda_away=0.9,
                                   p_home=0.56, p_draw=0.24, p_away=0.20,
                                   p_over_15=0.71, p_over_25=0.45,
                                   p_over_35=0.22, p_btts_yes=0.55,
                                   modal_scoreline=(1, 0)),
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        on_deploy_shortlist=True,
        best_market="Fenerbahce to win", best_price=1.91,
        best_bookmaker="bet365", best_n_books=3, best_mes_ev=0.0696,
        best_model_prob=0.56, mes_trigger_price=1.52,
        kickoff_date=today,
        elo_probs=(0.52, 0.27, 0.21),
        engine_divergence="4pp on home — within tolerance",
        rejection_reason=None)


def _unrated_bf() -> BoardFixture:
    return BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        on_deploy_shortlist=True,
        rejection_reason="NO DATA — PENDING: no fitted history")


def _leg(fixture, league, market_name, price, prob):
    return {"fixture": fixture, "league": league, "market_name": market_name,
            "price": price, "prob": prob}


def _acca(label, legs, odds, prob):
    return {"label": label, "legs": legs, "combined_odds": odds,
            "combined_prob": prob, "n_legs": len(legs)}


def _board_payload(d: str) -> dict:
    """A raw run_daily board: rated + unrated fixtures, accas (the production
    block source), honest gate numbers, yesterday/rolling. This is exactly what
    run_daily writes — the server trims it, never a publish step."""
    accas = [
        _acca("Acca A",
              [_leg("Fenerbahce v Sturm Graz (Champions League)",
                    "Champions League", "Fenerbahce to win", 1.91, 0.56)],
              1.91, 0.56),
        _acca("SINGLE — Bristol City v Walsall (EFL Cup)",
              [_leg("Bristol City v Walsall (EFL Cup)", "EFL Cup",
                    "Bristol City to win", 1.80, 0.55)],
              1.80, 0.55),
    ]
    return schema.build_payload(
        date=d, phase="Phase 2 — paper calibration, zero capital",
        leagues_scanned=["Champions League", "EFL Cup"],
        board=[_rated_bf(), _unrated_bf()],
        data_flags=["⚠ EFL Cup: no history"],
        gate={"legs_with_clv": 3, "gate_requirement": 30, "mean_clv_pct": -1.2},
        telemetry={}, calibration_count=3, mean_clv=-1.2,
        yesterday_graded=[{
            "fixture": "Fenerbahce v Sturm Graz",
            "league": "Champions League",
            "outcome": "HOME",
            "engines": {"dc": {"1X2_HOME": {"prob": 0.56, "hit": True}},
                        "elo": {"1X2_HOME": {"prob": 0.52, "hit": False}}},
        }],
        rolling_7d={
            "engines": {"dc": {"predictions": 20, "settled": 10,
                               "hit_rate": 0.5}},
            "legs_logged": 40, "legs_with_clv": 3, "avg_clv_pct": -1.2,
            "gate": {"legs_with_clv": 3, "gate_requirement": 30,
                     "gate_met": False},
        },
        accas=accas)


# BOARD_DIR must stay redirected for the WHOLE test — the server reads
# server.BOARD_DIR (raw board) and schema.BOARD_DIR (booking codes) per
# request. Redirect by assignment and restore after shutdown instead.
_real_schema_board_dir = schema.BOARD_DIR
_real_server_board_dir = server.BOARD_DIR
schema.BOARD_DIR = boards
server.BOARD_DIR = boards

schema.write_payload(_board_payload(today), boards / f"board_{today}.json")
# The day's SportyBet booking codes (schema.read_booking_codes reads them from
# schema.BOARD_DIR — same temp dir, so the production block renders real codes).
(boards / f"acca_{today}_codes.json").write_text(json.dumps({
    "results": [
        {"label": "Acca A", "code": "AA111",
         "per_leg": [{"fixture": "Fenerbahce v Sturm Graz (Champions League)"}]},
        {"label": "SINGLE — Bristol City v Walsall (EFL Cup)", "code": "SB_BRST",
         "per_leg": [{"fixture": "Bristol City v Walsall (EFL Cup)"}]},
    ],
}), encoding="utf-8")

httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
port = httpd.server_address[1]
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()
BASE = f"http://127.0.0.1:{port}"


def _req(path: str, headers: dict | None = None):
    req = Request(BASE + path, headers=headers or {})
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


def _get(path: str, headers: dict | None = None):
    return _req(path, headers)[:2]


def _status(path: str, headers: dict | None = None) -> int:
    """Status code only — for binary assets (_req would choke decoding them)."""
    req = Request(BASE + path, headers=headers or {})
    try:
        with urlopen(req, timeout=5) as r:
            return r.status
    except HTTPError as e:
        return e.code


def _post(path: str, headers: dict | None = None, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(BASE + path, headers=headers or {}, data=body, method="POST")
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


# --- 1. / redirects to /dashboard/<today> ---------------------------------
import urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
op = urllib.request.build_opener(NoRedirect)
try:
    op.open(BASE + "/", timeout=5)
    raise SystemExit("/ must redirect")
except urllib.error.HTTPError as e:
    assert e.code == 302 and e.headers.get("Location") == f"/dashboard/{today}"
print("1. / -> 302 to /dashboard/<today>: OK")

# --- 2. /dashboard (no publish step) renders the FEED page -----------------
# Auto-feed = auto-publish: the raw board renders directly, no Approve gate.
# The page IS the Telegram board — hero, gate callout, PRODUCTION BETS with
# the booking codes, lean scan — and carries NO model internals in the HTML.
code, body = _get(f"/dashboard/{today}")
assert code == 200, f"dashboard should 200, got {code}"
assert 'class="hero"' in body and "OLP XDV" in body
assert 'class="gate-callout notmet"' in body and "NOT MET" in body
assert "PRODUCTION BETS" in body
assert "★ Acca A — HEADLINE, 1 legs" in body
assert "Fenerbahce to win @ 1.91" in body
assert "AA111" in body and "SB_BRST" in body  # booking codes render + copyable
assert 'class="f-scan-row"' in body
assert "proto.css" in body and "proto.js" in body
# The data-leak boundary: no internals anywhere in the HTML.
for needle in ("elo_probs", "engine_divergence", "verification",
               "best_mes_ev", "consensus", "lambda_home", "model_engine",
               "best_price", "best_bookmaker"):
    assert needle not in body, f"/dashboard leaks {needle!r}"
print("2. /dashboard is the feed page, straight from the raw board: OK")

# --- 3. missing date is an honest 404 --------------------------------------
code, body = _get("/dashboard/1999-01-01")
assert code == 404 and "No board for that date" in body
print("3. missing date -> 404 (not a guess): OK")

# --- 4. traversal/bad paths blocked -----------------------------------------
assert _get("/dashboard/not-a-date")[0] == 404
assert _get("/dashboard/..%2F..%2Fetc")[0] == 404
print("4. malformed paths blocked: OK")

# --- 4b. /static serves the feed assets; traversal refused -------------------
code, body, hdrs = _req("/static/css/proto.css")
assert code == 200 and ".hero" in body and "font-family" in body
assert next((v for k, v in hdrs.items() if k.lower() == "content-type"),
            "").startswith("text/css")
assert _get("/static/js/proto.js")[0] == 200
assert _status("/static/fonts/Inter-normal-400.woff2") == 200
# Directory + traversal attempts are honest 404s, never a file read.
assert _get("/static/")[0] == 404
assert _get("/static/..%2F..%2Fconfig.py")[0] == 404
assert _get("/static/../config.py")[0] == 404
print("4b. /static serves proto.css/js/fonts; traversal -> 404: OK")

# --- 4c. strict CSP header on every response --------------------------------
code, body, hdrs = _req(f"/dashboard/{today}")
csp = next((v for k, v in hdrs.items() if k.lower() == "content-security-policy"), "")
assert "script-src 'self'" in csp, f"CSP missing script-src 'self': {csp!r}"
assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
code, body, hdrs = _req("/static/css/proto.css")
csp = next((v for k, v in hdrs.items() if k.lower() == "content-security-policy"), "")
assert "script-src 'self'" in csp, "static assets should carry CSP too"
print("4c. strict CSP header present on HTML and static responses: OK")

# --- 5. the paused admin tier is GONE: every route 404s --------------------
# Removed routes -> 404, NOT 401/503 — the tier is hard-paused, not gated.
for p in ("/admin", f"/admin/{today}", "/stats",
          "/why?fixture=Fenerbahce", "/api/stats.json",
          "/api/admin/board.json", "/api/admin/board/2026-08-09.json",
          "/api/admin/fixtures"):
    assert _get(p)[0] == 404, f"GET {p} should 404"
for p in ("/api/admin/publish", "/api/admin/board-edit",
          "/api/admin/produce", "/api/admin/signoff",
          "/api/trigger-board"):
    assert _post(p, data={})[0] == 404, f"POST {p} should 404"
print("5. /admin, /stats, /why, /api/admin/*, /api/trigger-board all -> 404: OK")

# --- 6. /api/board.json is the FEED payload: lean + honest gate numbers ------
code, body = _get("/api/board.json")
d = json.loads(body)
assert code == 200 and d["date"] == today
# The honest gate/edge numbers the Telegram board carries ARE present...
assert d["gate_state"]["legs_with_clv"] == 3
assert d["gate_state"]["gate_met"] is False
assert d["data_flags"] == ["⚠ EFL Cup: no history"]
# ...and the model internals are not.
b0 = d["board"][0]
assert b0["fixture"].startswith("Fenerbahce")
assert b0["best_market"] == "Fenerbahce to win"
assert b0["probs"]["p_home"] == 0.56
for k in ("elo_probs", "engine_divergence", "verification", "best_mes_ev",
          "consensus", "lambda_home", "modal_scoreline", "engine_picks",
          "best_price", "best_bookmaker"):
    assert k not in b0, f"api board leaks {k!r}"
assert _get("/api/board/1999-01-01.json")[0] == 404
print("6. /api/board.json is the feed payload (lean + gate numbers): OK")

# --- 6b. /api/board/<date>.json pinned to a date ----------------------------
code, body = _get(f"/api/board/{today}.json")
assert code == 200 and json.loads(body)["date"] == today
assert _get("/api/board/not-a-date.json")[0] == 404
print("6b. /api/board/<date>.json serves a pinned feed: OK")

# --- 7. /history stays public ------------------------------------------------
code, body = _get("/history")
assert code == 200 and "Board history" in body
print("7. /history public: OK")

# --- 8. /api/live-scores still reachable (fetch stubbed) ---------------------
with patch.object(server, "_fetch_live_scores", lambda leagues: {"a|b|2026-08-12": "2-1"}):
    code, body, _ = _post("/api/live-scores", data={"leagues": ["Champions League"]})
assert code == 200
d = json.loads(body)
assert d["ok"] is True and d["scores"]["a|b|2026-08-12"] == "2-1"
print("8. /api/live-scores reachable: OK")

# --- 9. /api/analyst reachable, honest when the key is absent -----------------
# With ANTHROPIC_API_KEY unset the analyst says so plainly (never a network
# call, no fabrication). Context is scoped to the feed payload — internals
# never reach the browser-facing model.
with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
    code, body, _ = _post("/api/analyst", data={"message": "hi"})
assert code == 200
d = json.loads(body)
assert d["ok"] is True and "unavailable" in d["reply"].lower()
print("9. /api/analyst reachable; honest no-key reply: OK")

# --- 10. the server never WRITES to its board dir ----------------------------
after = sorted(p.name for p in boards.iterdir())
expected = sorted([f"board_{today}.json", f"acca_{today}_codes.json"])
assert after == expected, f"server wrote to disk: {after}"
print("10. server is read-only (board dir unchanged): OK")

# --- 11. global /api/* rate limiting (60 req/min) ------------------------------
# Hit /api/board.json 61 times rapidly — the 61st should 429. The test uses
# the same in-memory store so the counter carries across requests.
# Note: the test client (localhost) is the single "IP" here; production behind
# Caddy would see real client IPs via X-Forwarded-For.
for i in range(61):
    code, _, _ = _req("/api/board.json")
    if i == 60:
        assert code == 429, f"request 61 should 429, got {code}"
        assert b"rate limited" in _req("/api/board.json")[1].encode() or b"rate limited" in _req("/api/board.json")[1]
print("11. global /api/* rate limit (60/min) -> 429 on 61st: OK")

# --- 11b. /api/analyst sub-limit still applies (10 req/min) --------------------
# The analyst endpoint has a stricter 10/min sub-limit ON TOP OF the global 60.
# We've already made 61 requests above (all to /api/board.json), so the global
# limit for this IP is exhausted. But let's test the sub-limit independently
# by clearing the global store and hitting /api/analyst 11 times.
# (In practice, both limits track the same IP; this verifies the sub-limit code
# path is reachable and the stricter bound is enforced.)
server._API_LIMIT.clear()
server._ANALYST_LIMIT.clear()
with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
    for i in range(11):
        code, body, _ = _post("/api/analyst", data={"message": "hi"})
        if i == 10:
            assert code == 429, f"analyst request 11 should 429, got {code}"
print("11b. /api/analyst sub-limit (10/min) -> 429 on 11th: OK")

# --- 12. hardening headers present on every response ---------------------------
code, body, hdrs = _req(f"/dashboard/{today}")
for hdr, expected in [
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "strict-origin-when-cross-origin"),
    ("strict-transport-security", "max-age=31536000; includesubdomains"),
]:
    val = next((v for k, v in hdrs.items() if k.lower() == hdr), "")
    assert expected.lower() in val.lower(), f"missing {hdr}={expected!r} (got {val!r})"
# Also check static assets get the headers
code, body, hdrs = _req("/static/css/proto.css")
val = next((v for k, v in hdrs.items() if k.lower() == "x-content-type-options"), "")
assert val.lower() == "nosniff", f"static missing nosniff: {val!r}"
print("12. hardening headers (nosniff, DENY, referrer, HSTS) on all responses: OK")

httpd.shutdown()
schema.BOARD_DIR = _real_schema_board_dir
server.BOARD_DIR = _real_server_board_dir
print("\n[OK] ALL WEBAPP SERVER TESTS PASSED")
