"""Server route tests — read-only, honest 404s, never writes to the repo.

A real ThreadingHTTPServer on an ephemeral port, with BOARD_DIR redirected to
a temp folder so the test can't touch the real boards."""
import json
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from http.client import HTTPConnection

sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp import schema, server
from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_server_"))
boards = tmp / "boards"
boards.mkdir()
today = date.today().isoformat()


def _write_board(date_str: str):
    bf = BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        softness_tier="D",
        rejection_reason="NO DATA — PENDING: no fitted history")
    payload = schema.build_payload(
        date=date_str, phase="PHASE 2 — PAPER", leagues_scanned=["EFL Cup"],
        board=[bf], data_flags=["⚠ test flag"], gate={"legs_with_clv": 0},
        telemetry={}, calibration_count=0, mean_clv=None)
    schema.write_payload(payload, boards / f"board_{date_str}.json")


_write_board(today)


def _get(path: str):
    try:
        with urlopen(BASE + path, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8")


# The patch must stay ACTIVE while the server serves — the handler resolves
# server.BOARD_DIR per request, so if the patch ends the server reads the real
# boards dir.
with patch.object(server, "BOARD_DIR", boards):
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    BASE = f"http://127.0.0.1:{port}"

    # --- 1. / redirects to today ---------------------------------------------
    import urllib.request
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    op = urllib.request.build_opener(NoRedirect)
    try:
        op.open(BASE + "/", timeout=5)
        raise SystemExit("/ must redirect")
    except urllib.error.HTTPError as e:
        assert e.code == 302 and e.headers.get("Location") == f"/board/{today}"
    print("1. / -> 302 to today: OK")

    # --- 2. today's board renders 200 ----------------------------------------
    code, body = _get(f"/board/{today}")
    assert code == 200 and "TODAY'S PICKS" in body and "Bristol City v Walsall" in body
    print("2. /board/<today> 200 with the board: OK")

    # --- 3. missing date is an honest 404 -------------------------------------
    code, body = _get("/board/1999-01-01")
    assert code == 404 and "No board for that date" in body
    print("3. missing date -> 404 (not a guess): OK")

    # --- 4. traversal/bad paths blocked ---------------------------------------
    assert _get("/board/not-a-date")[0] == 404
    assert _get("/board/..%2F..%2Fetc")[0] == 404
    print("4. malformed paths blocked: OK")

    # --- 5. history, stats, why ------------------------------------------------
    code, body = _get("/history")
    assert code == 200 and "Board history" in body
    assert _get("/stats")[0] == 200
    code, body = _get("/why?fixture=Walsall")
    assert code == 200 and "Bristol City v Walsall" in body
    assert _get("/why?fixture=NoTeam")[0] == 200  # honest 'no such fixture'
    print("5. history/stats/why respond: OK")

    # --- 6. JSON API is valid + the right day ----------------------------------
    code, body = _get("/api/board.json")
    d = json.loads(body)
    assert code == 200 and d["date"] == today and d["board"][0]["fixture"] == "Bristol City v Walsall (EFL Cup)"
    assert _get("/api/board/1999-01-01.json")[0] == 404
    print("6. /api/board.json valid; missing api date 404: OK")

    # --- 7. the server never WRITES to its board dir ---------------------------
    after = sorted(p.name for p in boards.iterdir())
    assert after == [f"board_{today}.json"], f"server wrote to disk: {after}"
    print("7. server is read-only (board dir unchanged): OK")

    httpd.shutdown()
print("\n✅ ALL WEBAPP SERVER TESTS PASSED")
