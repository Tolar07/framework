"""Server route tests for the two-tier dashboard — read-only, honest 404s,
Basic auth on /admin, never writes to the repo.

This test had a structural bug (the whole body was accidentally indented inside
`def _auth`, so zero assertions ran) — fixed 2026-08-10, and the markers were
updated for the NEW prototype design (render_v2): the client is the mobile
Call/Scan/Analyst view (no chat on client), the admin is the light dense table
with trigger/approve/chat.

A real ThreadingHTTPServer on an ephemeral port, with BOARD_DIR redirected to
a temp folder so the test can't touch the real boards. Auth env vars are set
on os.environ for the process during the test (the server reads them per
request)."""
import base64
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

# Auth under test — the server reads these from os.environ per request.
# Pin the auth toggle ON: importing server runs config.load_dotenv(), which
# would pull OLP_REQUIRE_ADMIN_AUTH=0 from the real .env and break the 401s.
os.environ["ADMIN_USER"] = "test"
os.environ["ADMIN_PASS"] = "testpass"
os.environ["OLP_REQUIRE_ADMIN_AUTH"] = "1"
# Publish gate sign-off so the fixture board passes the gate (gate logic has
# its own dedicated tests in webapp_schema_test.py).
os.environ["ARCHITECT_SIGNOFF"] = "1"


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
        softness_tier="D", on_deploy_shortlist=True,
        best_market="Fenerbahce to win", best_price=1.91,
        best_bookmaker="bet365", best_n_books=3, best_mes_ev=0.0696,
        best_model_prob=0.56, mes_trigger_price=1.52,
        kickoff_date="2026-08-11",
        elo_probs=(0.52, 0.27, 0.21),
        engine_divergence="4pp on home — within tolerance",
        rejection_reason=None)


def _unrated_bf() -> BoardFixture:
    return BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        softness_tier="D",
        rejection_reason="NO DATA — PENDING: no fitted history")


def _rated_bf_payload() -> dict:
    """A full raw board payload holding just the rated fixture (for board-edit)."""
    return schema.build_payload(
        date=date.today().isoformat(), phase="PHASE 2 — PAPER",
        leagues_scanned=["Champions League"], board=[_rated_bf()],
        data_flags=[], gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.2},
        telemetry={}, calibration_count=0, mean_clv=1.2)


# PUBLISHED_DIR must stay redirected for the WHOLE test — the server reads
# schema.PUBLISHED_DIR per request, and every GET below hits that store. A
# `with patch.object` block would revert the moment the board write finished,
# so redirect by assignment and restore after shutdown instead.
_real_published_dir = schema.PUBLISHED_DIR
_real_audit_log = schema.AUDIT_LOG
schema.PUBLISHED_DIR = boards
schema.AUDIT_LOG = boards / "publish_audit.jsonl"
httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
port = httpd.server_address[1]
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()
BASE = f"http://127.0.0.1:{port}"


def _write_board(date_str: str):
    payload = schema.build_payload(
        date=date_str, phase="PHASE 2 — PAPER", leagues_scanned=["EFL Cup", "Champions League"],
        board=[_rated_bf(), _unrated_bf()], data_flags=["⚠ test flag"],
        # A gate-PASSING fixture so the server-route tests exercise routing,
        # not the publish gate (the gate has its own dedicated tests).
        gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.2},
        telemetry={}, calibration_count=0, mean_clv=1.2)
    # The public dashboard reads from PUBLISHED_DIR, not BOARD_DIR.
    # Write as "published" (trimmed) so the client view works.
    schema.write_published(payload, approved_by="test")


_write_board(today)


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


def _auth(user="test", pw="testpass"):
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


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

# --- 2. /dashboard (public, no auth) renders the NEW client view ----------
# Call/Scan/Analyst tabs; the published board has no accas payload, so the
# client shows the honest NO DATA — PENDING single-card grid (the production
# panel stays admin-only). Date pills + search + collapsible league groups;
# Analyst is READ-ONLY (no chat anywhere on the client — admin-only).
code, body = _get(f"/dashboard/{today}")
assert code == 200
assert 'data-panel="call"' in body and 'data-panel="scan"' in body and 'data-panel="analyst"' in body
# The published board has no 'accas', so the Call holds the single-fiixture
# grid (honest NO DATA — PENDING for the unrated) and the scan list, not the
# OLD "Accumulator" / "Booking code" wording (replaced by the production block).
assert "NO DATA" in body and "Singles" in body
assert 'id="scan-search"' in body and 'class="c-datepills"' in body
assert 'class="c-league-head"' in body
# The client view must NOT carry model internals — not even in the HTML.
for needle in ("elo_probs", "engine_divergence", "verification",
               "best_mes_ev", "Model Internals", "Honest edge", "zero capital",
               "chat-fab", "admin-chatlog", "trigger-btn"):
    assert needle not in body, f"/dashboard leaks {needle!r}"
# The client uses the NEW stylesheet, not the old app.css bundle.
assert "proto.css" in body and "proto.js" in body
print("2. /dashboard is the new Call/Scan/Analyst client view: OK")

# --- 3. missing date is an honest 404 --------------------------------------
code, body = _get("/dashboard/1999-01-01")
assert code == 404 and "No board for that date" in body
print("3. missing date -> 404 (not a guess): OK")

# --- 4. traversal/bad paths blocked -----------------------------------------
assert _get("/dashboard/not-a-date")[0] == 404
assert _get("/dashboard/..%2F..%2Fetc")[0] == 404
print("4. malformed paths blocked: OK")

# --- 4b. /static serves the NEW assets; traversal refused -------------------
code, body, hdrs = _req("/static/css/proto.css")
assert code == 200 and ".c-tab" in body and "font-family" in body
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

# --- 5. /admin requires Basic auth (guard restored 2026-08-10) --------------
code, body, hdrs = _req("/admin")
assert code == 401, f"/admin unauthed should 401, got {code}"
assert "WWW-Authenticate" in hdrs and "Basic" in hdrs["WWW-Authenticate"]
code, body = _get("/admin/1999-01-01")  # auth is checked BEFORE the 404
assert code == 401
code, body = _get("/admin", _auth())
assert code == 200 and 'id="trigger-btn"' in body and "Model Internals" in body
# New admin surface: search bar, trigger + date, stat pills, filter chips,
# dense table, Approve->Publish, and the AI Analyst FULL chat.
assert 'id="admin-search"' in body and 'id="trigger-date"' in body
assert 'class="a-stat"' in body and 'class="a-chip"' in body
assert 'data-chip="eligible"' in body and 'data-gate' in body and 'id="gate-detail"' in body
assert 'class="a-table"' in body and 'id="approve-btn"' in body
assert 'id="admin-chatlog"' in body and 'id="admin-chat-send"' in body
code, body = _get("/admin", _auth(pw="wrong"))
assert code == 401
print("5. /admin: 401 without creds, 200 with, 401 wrong password: OK")
print("5b. admin has trigger/date/stats/chips/table/approve/chat: OK")

# --- 5c. OLP_REQUIRE_ADMIN_AUTH=0 lifts the wall (dev escape hatch) ----------
# Default is ON (sections 5/7/8c assert the 401s); setting the flag to 0 makes
# /admin and the mutating trigger route reachable without credentials.
with patch.dict(os.environ, {"OLP_REQUIRE_ADMIN_AUTH": "0"}, clear=False):
    assert _get("/admin/2026-08-10")[0] == 200
    assert _get("/stats")[0] == 200
    assert _get("/api/admin/board.json")[0] == 200
    code, body, _ = _post("/api/trigger-board?date=bad-date")
    assert code == 200 and json.loads(body).get("ok") is False, \
        "bad-date guard must still reject even with auth off"
print("5c. OLP_REQUIRE_ADMIN_AUTH=0 lifts auth; guards still hold: OK")

# --- 6. /admin renders the FULL payload (internals present) -----------------
code, body = _get(f"/admin/{today}", _auth())
assert code == 200
for needle in ("Model Internals", "HR30 MES", "NO DATA", "Rejection",
               "Error / Rejection Log"):
    assert needle in body, f"/admin missing {needle!r}"
print("6. /admin is the full internal view: OK")

# --- 7. internals pages are admin-only --------------------------------------
assert _get("/stats")[0] == 401
assert _get("/why?fixture=Fenerbahce")[0] == 401
assert _get("/api/stats.json")[0] == 401
assert _get("/stats", _auth())[0] == 200
assert _get("/why?fixture=Fenerbahce", _auth())[0] == 200
assert _get("/why?fixture=NoTeam", _auth())[0] == 200  # honest 'no such fixture'
print("7. /stats, /why, /api/stats.json are admin-only: OK")

# --- 8. public JSON API is TRIMMED; admin API is full -----------------------
code, body = _get("/api/board.json")
d = json.loads(body)
assert code == 200 and d["date"] == today
b0 = d["board"][0]
assert b0["fixture"].startswith("Fenerbahce")
for k in ("elo_probs", "engine_divergence", "verification", "best_mes_ev",
          "softness_tier", "consensus"):
    assert k not in b0, f"public api leaks {k}"
assert _get("/api/board/1999-01-01.json")[0] == 404

# --- 8b. the public JSON never serves an UNPUBLISHED board -------------
# A raw board that exists in BOARD_DIR but was never approved/published
# must 404 on the public JSON routes — the approve gate is the only path
# to the client. (Regression guard: both /api/board routes previously read
# the raw board dir, bypassing the gate.)
# The raw board lives in server.BOARD_DIR (the run store), NOT the published
# store, and uses a date with no published counterpart.
raw_dir = tmp / "boards_raw"
raw_dir.mkdir()
_real_board_dir = server.BOARD_DIR
server.BOARD_DIR = raw_dir
raw_only = schema.build_payload(
    date="2026-08-09", phase="PHASE 2 — PAPER",
    leagues_scanned=["Champions League"], board=[_rated_bf()],
    data_flags=[], gate={"legs_with_clv": 0, "gate_requirement": 30},
    telemetry={}, calibration_count=0, mean_clv=None)
schema.write_payload(raw_only, raw_dir / "board_2026-08-09.json")
assert _get("/api/board/2026-08-09.json")[0] == 404, \
    "unpublished raw board leaked via public JSON"
assert _get("/api/board.json")[0] != 500  # today still served
# admin API still sees it (internal view, auth'd)
code, body = _get("/api/admin/board/2026-08-09.json", _auth())
assert code == 200 and body
server.BOARD_DIR = _real_board_dir
print("8b. unpublished board NOT served publicly; admin-only: OK")

code, body = _get("/api/admin/board.json", _auth())
assert code == 200 and "elo_probs" in json.loads(body)["board"][0]
assert _get("/api/admin/board.json")[0] == 401
print("8. /api/board.json trimmed; /api/admin/board.json full behind auth: OK")

# --- 8c. mutating POST endpoints require admin auth -------------------------
code, _, _ = _post("/api/trigger-board?date=bad-date")
assert code == 401, f"unauth trigger-board should 401, got {code}"
code, body, _ = _post("/api/trigger-board?date=bad-date", _auth())
assert code == 200
d = json.loads(body)
assert d.get("ok") is False and "date" in d.get("error", ""), \
    f"trigger guard should reject a bad date: {body[:100]}"
code, _, _ = _post("/api/admin/publish", data={"date": today})
assert code == 401, "unauth publish should 401"
print("8c. trigger-board + publish require admin; guard rejects bad date: OK")

# --- 8d. edit-before-publish: POST /api/admin/board-edit patches the RAW board
# Redirect BOARD_DIR to a temp dir so the edit writes there, never the repo.
edit_dir = tmp / "boards_edit"
edit_dir.mkdir()
_real_board_dir_edit = server.BOARD_DIR
server.BOARD_DIR = edit_dir
schema.write_payload(_rated_bf_payload(), edit_dir / f"board_{today}.json")
code, _, _ = _post("/api/admin/board-edit",
                   data={"date": today, "fixture": "Fenerbahce v Sturm Graz", "edits": {"best_price": "2.05"}})
assert code == 401, "board-edit must require admin"
code, body, _ = _post("/api/admin/board-edit", _auth(),
                      data={"date": today, "fixture": "Fenerbahce v Sturm Graz",
                            "edits": {"best_market": "Fenerbahce -1", "best_price": "2.05",
                                      "on_deploy_shortlist": False}})
assert code == 200
d = json.loads(body)
assert d.get("ok") is True and "best_price" in d.get("applied", []), body[:200]
edited = schema.read_payload(edit_dir / f"board_{today}.json")
b0 = edited["board"][0]
assert b0["best_price"] == 2.05 and b0["best_market"] == "Fenerbahce -1"
# No softness-tier edit exists any more (ID402 tiers removed 2026-08-10) — the
# deploy-shortlist toggle is the only gating control the edit can change.
assert b0["on_deploy_shortlist"] is False
# bad fixture / bad price are honest errors, never a crash
code, body, _ = _post("/api/admin/board-edit", _auth(),
                      data={"date": today, "fixture": "NoSuchTeam", "edits": {"best_market": "x"}})
assert code == 200 and json.loads(body).get("ok") is False, "unknown fixture should error"
code, body, _ = _post("/api/admin/board-edit", _auth(),
                      data={"date": today, "fixture": "Fenerbahce v Sturm Graz", "edits": {"best_price": "abc"}})
assert code == 200 and json.loads(body).get("ok") is False, "non-numeric price should error"
server.BOARD_DIR = _real_board_dir_edit
print("8d. board-edit patches the raw board (auth'd), honest errors otherwise: OK")

# --- 9. when ADMIN_PASS is unset, /admin is locked (503, no default) --------
with patch.dict(os.environ, {}, clear=True):
    # re-set just the un-auth'd vars the server needs for this request
    os.environ.pop("ADMIN_PASS", None)
    code, body, _ = _req("/admin")
assert code == 503 and "ADMIN_PASS" in body
os.environ["ADMIN_USER"] = "test"
os.environ["ADMIN_PASS"] = "testpass"
os.environ["ARCHITECT_SIGNOFF"] = "1"
os.environ["OLP_REQUIRE_ADMIN_AUTH"] = "1"
print("9. no ADMIN_PASS -> /admin 503 'set ADMIN_PASS': OK")

# --- 10. history stays public ------------------------------------------------
code, body = _get("/history")
assert code == 200 and "Board history" in body
print("10. /history public: OK")

# --- 11. the server never WRITES to its board dir ----------------------------
after = sorted(p.name for p in boards.iterdir())
expected = [f"board_{today}.json", "publish_audit.jsonl"]
assert after == expected, f"server wrote to disk: {after}"
assert sorted(p.name for p in raw_dir.iterdir()) == ["board_2026-08-09.json"]
print("11. server is read-only (board dir unchanged): OK")

httpd.shutdown()
schema.PUBLISHED_DIR = _real_published_dir
schema.AUDIT_LOG = _real_audit_log
print("\n[OK] ALL WEBAPP SERVER TESTS PASSED")
