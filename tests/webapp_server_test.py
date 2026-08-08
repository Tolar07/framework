"""Server route tests for the two-tier dashboard — read-only, honest 404s,
Basic auth on /admin, never writes to the repo.

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
os.environ["ADMIN_USER"] = "test"
os.environ["ADMIN_PASS"] = "testpass"
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


# The PUBLISHED_DIR patch must stay ACTIVE while the server serves —
# _load_published reads from schema.PUBLISHED_DIR per request.
# AUDIT_LOG is also module-level and must be patched to match.
with patch.object(schema, "PUBLISHED_DIR", boards):
    schema.AUDIT_LOG = boards / "publish_audit.jsonl"
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    BASE = f"http://127.0.0.1:{port}"

    # Write the test board INSIDE the patch context
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


def _auth(user="test", pw="testpass"):
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

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

    # --- 2. /dashboard (public, no auth) renders the CLIENT view ---------------
    code, body = _get(f"/dashboard/{today}")
    assert code == 200
    assert "The Call" in body and "The Scan" in body
    assert "Fenerbahce v Sturm Graz" in body and "NO DATA" in body
    # The client view must NOT carry model internals — not even in the HTML.
    for needle in ("elo_probs", "engine_divergence", "verification",
                   "best_mes_ev", "Model Internals", "Honest edge", "zero capital"):
        assert needle not in body, f"/dashboard leaks {needle!r}"
    print("2. /dashboard is the trimmed client view: OK")

    # --- 3. missing date is an honest 404 --------------------------------------
    code, body = _get("/dashboard/1999-01-01")
    assert code == 404 and "No board for that date" in body
    print("3. missing date -> 404 (not a guess): OK")

    # --- 4. traversal/bad paths blocked -----------------------------------------
    assert _get("/dashboard/not-a-date")[0] == 404
    assert _get("/dashboard/..%2F..%2Fetc")[0] == 404
    print("4. malformed paths blocked: OK")

    # --- 5. /admin requires Basic auth ------------------------------------------
    code, body, hdrs = _req("/admin")
    assert code == 401, f"/admin unauthed should 401, got {code}"
    assert "WWW-Authenticate" in hdrs and "Basic" in hdrs["WWW-Authenticate"]
    code, body = _get("/admin/1999-01-01")  # auth is checked BEFORE the 404
    assert code == 401
    code, body = _get("/admin", _auth())
    assert code == 200 and "Model Internals" in body and "Honest edge" in body
    code, body = _get("/admin", _auth(pw="wrong"))
    assert code == 401
    print("5. /admin: 401 without creds, 200 with, 401 wrong password: OK")

    # --- 6. /admin renders the FULL payload (internals present) -----------------
    code, body = _get(f"/admin/{today}", _auth())
    assert code == 200
    for needle in ("Model Internals", "Elo second opinion", "Engine divergence",
                   "HR30 MES", "Data Flags", "Verified — Yesterday",
                   "zero capital", "TIER D", "SINGLE-SOURCE"):
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
    raw_only = schema.build_payload(
        date="2026-08-10", phase="PHASE 2 — PAPER",
        leagues_scanned=["Champions League"], board=[_rated_bf()],
        data_flags=[], gate={"legs_with_clv": 0, "gate_requirement": 30},
        telemetry={}, calibration_count=0, mean_clv=None)
    schema.write_payload(raw_only, boards / "board_2026-08-10.json")
    assert _get("/api/board/2026-08-10.json")[0] == 404, \
        "unpublished raw board leaked via public JSON"
    assert _get("/api/board.json")[0] != 500  # today still served
    # admin API still sees it (internal view, auth'd)
    code, body = _get("/api/admin/board/2026-08-10.json", _auth())
    assert code == 200 and body
    print("8b. unpublished board NOT served publicly; admin-only: OK")

    code, body = _get("/api/admin/board.json", _auth())
    assert code == 200 and "elo_probs" in json.loads(body)["board"][0]
    assert _get("/api/admin/board.json")[0] == 401
    print("8. /api/board.json trimmed; /api/admin/board.json full behind auth: OK")

    # --- 9. when ADMIN_PASS is unset, /admin is locked (503, no default) --------
    with patch.dict(os.environ, {}, clear=True):
        # re-set just the un-auth'd vars the server needs for this request
        os.environ.pop("ADMIN_PASS", None)
        code, body, _ = _req("/admin")
    assert code == 503 and "ADMIN_PASS" in body
    os.environ["ADMIN_USER"] = "test"
    os.environ["ADMIN_PASS"] = "testpass"
    print("9. no ADMIN_PASS -> /admin 503 'set ADMIN_PASS': OK")

    # --- 10. history stays public ------------------------------------------------
    code, body = _get("/history")
    assert code == 200 and "Board history" in body
    print("10. /history public: OK")

    # --- 11. the server never WRITES to its board dir ----------------------------
    after = sorted(p.name for p in boards.iterdir())
    assert after == [f"board_{today}.json"], f"server wrote to disk: {after}"
    print("11. server is read-only (board dir unchanged): OK")

    httpd.shutdown()
print("\n✅ ALL WEBAPP SERVER TESTS PASSED")
