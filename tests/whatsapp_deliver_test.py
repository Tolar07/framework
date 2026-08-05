"""WhatsApp delivery tests — mocked network, no real keys, no real requests.

The sender mirrors notify.py's discipline: never raises, returns (ok, notes),
retries transient faults 3x, and refuses to send when credentials are missing.
The 7am push is business-initiated, so it must go out as a TEMPLATE message
(Meta Cloud API rule) — the template body is a single {{1}} parameter."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import whatsapp_deliver as wd

OK_PAYLOAD = {"messages": [{"id": "wamid.test"}]}
ERR_PAYLOAD = {"error": {"message": "boom", "code": 131026}}


def _env(clear=True, **kw):
    """Env vars for a configured send; clear removes any pre-set WHATSAPP_*."""
    base = {k: "" for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
                            "WHATSAPP_TO")} if clear else {}
    base.update(kw)
    return patch.dict(os.environ, base)


def _fake_post(status=200, payload=None, n=None):
    """A requests.post stand-in. `n` counts calls. Returns the callable."""
    state = {"n": 0}

    class R:
        def __init__(self):
            self.status_code = status

        def json(self):
            return payload if payload is not None else OK_PAYLOAD

    def fake_post(*a, **k):
        state["n"] += 1
        return R()

    return fake_post, state


# --- 1. successful template send: URL, auth, template structure --------------
called = {}
with _env(WHATSAPP_TOKEN="tok", WHATSAPP_PHONE_NUMBER_ID="pid",
          WHATSAPP_TO="+15550000000"):
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        fake, _ = _fake_post()
        mreq.post.side_effect = fake
        ok, notes = wd.send_whatsapp("Fenerbahçe v Sturm Graz — Under 2.5 67%")
assert ok is True
assert any("delivered 1 part(s) to WhatsApp" in n for n in notes), notes
assert mreq.post.call_count == 1, "one part must be one POST"
args = mreq.post.call_args
url = args.args[0] if args.args else args.kwargs["url"]
assert url == "https://graph.facebook.com/v23.0/pid/messages", url
assert args.kwargs["headers"]["Authorization"] == "Bearer tok"
body = args.kwargs["json"]
assert body["type"] == "template"
assert body["to"] == "+15550000000"
assert body["template"]["name"] == "olp_daily_pick"  # env/default name
assert body["template"]["language"]["code"] == "en"
txt = body["template"]["components"][0]["parameters"][0]["text"]
assert "Fenerbahçe v Sturm Graz — Under 2.5 67%" in txt, "stamped body carries the picks"
print("1. template send (URL/auth/payload): OK")

# --- 2. retry: two failures then success --------------------------------------
with _env(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="p", WHATSAPP_TO="+1"):
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        fail = _fake_post(status=500, payload=ERR_PAYLOAD)[0]
        ok_post = _fake_post(status=200)[0]
        calls = {"n": 0}
        def flaky(*a, **k):  # fail, fail, ok
            calls["n"] += 1
            return fail(*a, **k) if calls["n"] < 3 else ok_post(*a, **k)
        mreq.post.side_effect = flaky
        ok, notes = wd.send_whatsapp("retry me")
assert ok is True and calls["n"] == 3, f"must retry twice then succeed ({calls['n']})"
print("2. retry on transient failure (3 attempts, succeeds): OK")

# --- 3. persistent failure returns (False, notes), never raises ---------------
with _env(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="p", WHATSAPP_TO="+1"):
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        fake, state = _fake_post(status=500, payload=ERR_PAYLOAD)
        mreq.post.side_effect = fake
        ok, notes = wd.send_whatsapp("always fails")
assert ok is False and state["n"] == 3, "3 attempts on persistent failure"
assert any("FAILED after 3 attempts" in n for n in notes), notes
print("3. persistent failure (returns False, no raise): OK")

# --- 4. env-missing guard: no credentials -> skip, zero network ---------------
with _env():  # WHATSAPP_* all empty
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        ok, notes = wd.send_whatsapp("no creds")
assert ok is False and mreq.post.call_count == 0, "must not hit the network"
assert any("not set — WhatsApp delivery skipped" in n for n in notes), notes
print("4. env-missing guard (no network): OK")

# --- 5. requests not installed -> graceful False ------------------------------
with _env(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="p", WHATSAPP_TO="+1"):
    with patch.object(wd, "requests", None):
        ok, notes = wd.send_whatsapp("no requests lib")
assert ok is False and any("requests not installed" in n for n in notes), notes
print("5. requests missing (graceful False): OK")

# --- 6. long body is chunked under the template param cap ----------------------
with _env(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="p", WHATSAPP_TO="+1"):
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        fake, state = _fake_post()
        mreq.post.side_effect = fake
        # many short rows, like a real board — total stamped length > cap.
        big = "\n".join(f"row {i} " + "x" * 50 for i in range(30))
        ok, notes = wd.send_whatsapp(big)
assert ok is True and state["n"] >= 2, f"long body must split ({state['n']} posts)"
for c in mreq.post.call_args_list:
    part = c.kwargs["json"]["template"]["components"][0]["parameters"][0]["text"]
    assert len(part) <= wd.WHATSAPP_PARAM_MAX, "each part must respect the cap"
# a single row longer than the cap is never truncated mid-row (notify discipline)
with _env(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="p", WHATSAPP_TO="+1"):
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        fake, state = _fake_post()
        mreq.post.side_effect = fake
        wd.send_whatsapp("x" * 1400)  # one oversized line
posted = [c.kwargs["json"]["template"]["components"][0]["parameters"][0]["text"]
          for c in mreq.post.call_args_list]
assert any("x" * 1400 in p for p in posted), "the oversized row must survive whole"
print("6. long body chunked under the parameter cap: OK")

# --- 7. explicit params win over env ------------------------------------------
with _env(WHATSAPP_TOKEN="envtok", WHATSAPP_PHONE_NUMBER_ID="envpid",
          WHATSAPP_TO="+1"):
    with patch.object(wd, "requests") as mreq, \
            patch.object(wd.time, "sleep"):
        fake, _ = _fake_post()
        mreq.post.side_effect = fake
        ok, _ = wd.send_whatsapp("explicit", token="explicit",
                                 phone_number_id="explicit",
                                 to="+2348012345678",
                                 template_name="alt", language="en_GB")
assert ok is True
j = mreq.post.call_args.kwargs["json"]
assert j["to"] == "+2348012345678"
assert j["template"]["name"] == "alt"
assert j["template"]["language"]["code"] == "en_GB"
print("7. explicit params override env: OK")

print("\n✅ ALL WHATSAPP DELIVERY TESTS PASSED")
