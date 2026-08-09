"""
Telegram webhook mode tests (Phase 5.4).

Registration, the HTTP receiver, and the routing hand-off — NOTHING here runs
the pipeline. A webhook is only reachable via a public HTTPS URL (none exists
on a dev box), so the module is built and tested here but the long-polling
daemon stays the delivery path until the Architect points it at a reachable
URL.

The receiver hands every update to telegram_commands.handle_update — the SAME
function the poller uses — so the safety properties (chat whitelist,
bright-line refusal, lazy pipeline import) are inherited, not re-tested.
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import output.telegram_commands as tc
from output import telegram_webhook as wh
from output.telegram_webhook import WEBHOOK_PATH, WebhookReceiver, info, register

# Point the command layer's state files at a throwaway dir so no real ledger
# state (corrections.csv / offset) is mutated by this suite.
_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_webhook_test_"))
tc.STATE_DIR = _tmp
tc.OFFSET_FILE = _tmp / "telegram_offset.json"
tc.CORRECTIONS_FILE = _tmp / "corrections.csv"

_old_cid = os.environ.get("TELEGRAM_CHAT_ID")
os.environ["TELEGRAM_CHAT_ID"] = "888"  # whitelist the test chat like the real one


# --- registration -----------------------------------------------------------
def _faked_requests():
    fake = mock.MagicMock()
    fake.post.return_value.json.return_value = {"ok": True, "description": "ok"}
    fake.get.return_value.json.return_value = {
        "ok": True, "url": "https://example.com/webhook"}
    return fake


try:
    fake = _faked_requests()
    with mock.patch.object(wh, "requests", fake):
        ok, notes = register(token="t", url="https://example.com/webhook",
                             secret_token="s3cret")
    assert ok, f"register must succeed, got: {notes}"
    args, kwargs = fake.post.call_args
    assert args[0].endswith("/setWebhook"), f"must call setWebhook, got {args[0]}"
    payload = kwargs["json"]
    assert payload["url"] == "https://example.com/webhook"
    assert payload["secret_token"] == "s3cret"
    assert payload["allowed_updates"] == ["message", "callback_query"]
    print("register posts setWebhook with url + secret + allowed_updates: OK")

    fake = _faked_requests()
    with mock.patch.object(wh, "requests", fake):
        ok, notes = register(token="t", url="")
    assert ok, f"removal must succeed, got: {notes}"
    assert fake.post.call_args[0][0].endswith("/deleteWebhook"), \
        "an empty url must remove the webhook"
    print("register(url='') removes the webhook: OK")

    fake = _faked_requests()
    with mock.patch.object(wh, "requests", fake):
        res = info(token="t")
    assert fake.get.call_args[0][0].endswith("/getWebhookInfo"), \
        "info must call getWebhookInfo"
    assert res.get("ok") is True and res.get("url"), "info must surface the URL"
    print("info reads getWebhookInfo: OK")

    # A missing token must refuse, not attempt the call.
    with mock.patch.object(wh, "requests", mock.MagicMock()) as f2, \
         mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        ok, notes = register(url="https://example.com/webhook")
    assert not ok and "TELEGRAM_BOT_TOKEN not set" in notes[0]
    f2.post.assert_not_called()
    print("register without a token refuses and calls nothing: OK")

    # --- routing hand-off: the receiver uses the poller's exact path ---------
    with mock.patch.object(tc, "send_telegram",
                           return_value=(True, ["delivered 1 part(s) to Telegram"])) as _sent:
        ok, notes = wh.handle_update(
            {"update_id": 9,
             "message": {"message_id": 2,
                         "chat": {"id": 888, "type": "private"},
                         "text": "/status"}},
            token="t")
    assert ok and _sent.call_count == 1, "a webhook message must produce one reply"
    assert "PHASE 3 GATE" in _sent.call_args[0][0], \
        "the webhook reply must be the same command reply the poller sends"
    print("webhook routes /status through handle_update -> same reply as poller: OK")

    # --- the stdlib receiver: fast 200, secret verified, update handed off ----
    _received: list = []

    def _capture(update, token=None):
        _received.append((update, token))
        return True, ["handled in test"]

    _receiver = WebhookReceiver(("127.0.0.1", 0), bot_token="t", secret_token="s3cret")
    threading.Thread(target=_receiver.serve_forever, daemon=True).start()
    _port = _receiver.server_address[1]
    _body = json.dumps({"update_id": 1,
                        "message": {"message_id": 1,
                                    "chat": {"id": 888, "type": "private"},
                                    "text": "/status"}}).encode("utf-8")

    def _post(path, secret=None):
        conn = http.client.HTTPConnection("127.0.0.1", _port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if secret is not None:
            headers["X-Telegram-Bot-Api-Secret-Token"] = secret
        conn.request("POST", path, body=_body, headers=headers)
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp.status

    try:
        with mock.patch.object(wh, "handle_update", side_effect=_capture):
            status = _post(WEBHOOK_PATH, secret="s3cret")
        assert status == 200, f"valid secret must 200, got {status}"
        for _ in range(100):  # the handler handles in a daemon thread
            if _received:
                break
            time.sleep(0.05)
        assert _received and _received[0][0].get("update_id") == 1, \
            "the POSTed update must reach handle_update"
        assert _received[0][1] == "t", "the bot token must be passed through"
        assert _post(WEBHOOK_PATH, secret="wrong") == 403, \
            "a spoofed POST without the secret must be refused 403"
        assert _post("/other", secret="s3cret") == 404, \
            "a wrong path must 404"
    finally:
        _receiver.shutdown()
        _receiver.server_close()
    print("receiver: fast 200 + secret verified + update handed to handle_update: OK")
finally:
    if _old_cid is None:
        os.environ.pop("TELEGRAM_CHAT_ID", None)
    else:
        os.environ["TELEGRAM_CHAT_ID"] = _old_cid

print("\n[OK] ALL TELEGRAM WEBHOOK TESTS PASSED")
