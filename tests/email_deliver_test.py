"""Email delivery tests — mocked SMTP, no real network, no real credentials.

Mirrors notify.py / whatsapp_deliver.py discipline: never raises, returns
(ok, notes), retries 3x, and refuses to send when credentials are missing.
Email is the zero-approval copy channel: same stamped text as Telegram."""
import os
import smtplib as _smtplib  # real module, for genuine exception classes
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import email_deliver as ed


class FakeSMTP:
    """Context-manager stand-in for smtplib.SMTP that records its calls."""
    instances = []

    def __init__(self, host, port, timeout=30):
        self.host, self.port, self.timeout = host, port, timeout
        self.started_tls = False
        self.login_args = None
        self.sent = []
        self.exc = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, pw):
        self.login_args = (user, pw)

    def send_message(self, msg):
        if self.exc:
            raise self.exc
        self.sent.append(msg)


def _env(**kw):
    base = {k: "" for k in ("EMAIL_USER", "EMAIL_APP_PASSWORD", "EMAIL_TO")}
    base.update(kw)
    return patch.dict(os.environ, base)


# --- 1. successful send: SMTP connect/tls/login/send --------------------------
FakeSMTP.instances = []
with _env(EMAIL_USER="me@gmail.com", EMAIL_APP_PASSWORD="abcd1234abcd1234",
          EMAIL_TO="you@gmail.com"):
    with patch.object(ed, "smtplib") as msmtp:
        msmtp.SMTP.side_effect = FakeSMTP
        with patch.object(ed.time, "sleep"):
            ok, notes = ed.deliver("Fenerbahçe v Sturm Graz — Under 2.5 67%")
assert ok is True and any("delivered 1 part(s) to email" in n for n in notes)
srv = FakeSMTP.instances[0]
assert (srv.host, srv.port) == ("smtp.gmail.com", 587), "defaults to Gmail"
assert srv.started_tls, "must STARTTLS"
assert srv.login_args == ("me@gmail.com", "abcd1234abcd1234")
msg = srv.sent[0]
assert msg["To"] == "you@gmail.com" and msg["From"] == "me@gmail.com"
assert "Fenerbahçe v Sturm Graz — Under 2.5 67%" in msg.get_content()
assert "OLP XDV" in msg["Subject"]
print("1. successful send (tls/login/send): OK")

# --- 2. retry: two failures then success --------------------------------------
FakeSMTP.instances = []
with _env(EMAIL_USER="u@x.com", EMAIL_APP_PASSWORD="p" * 16, EMAIL_TO="t@x.com"):
    with patch.object(ed, "smtplib") as msmtp, \
            patch.object(ed.time, "sleep"):
        calls = {"n": 0}
        def flaky(host, port, timeout=30):
            calls["n"] += 1
            f = FakeSMTP(host, port, timeout)
            if calls["n"] < 3:
                f.exc = ConnectionError("reset")
            return f
        msmtp.SMTP.side_effect = flaky
        ok, _ = ed.deliver("retry me")
assert ok is True and calls["n"] == 3, f"must retry twice then succeed ({calls['n']})"
assert FakeSMTP.instances[2].sent, "3rd attempt must deliver"
print("2. retry on transient failure (3 attempts, succeeds): OK")

# --- 3. persistent failure returns (False, notes), never raises ---------------
FakeSMTP.instances = []
with _env(EMAIL_USER="u@x.com", EMAIL_APP_PASSWORD="p" * 16, EMAIL_TO="t@x.com"):
    with patch.object(ed, "smtplib") as msmtp, \
            patch.object(ed.time, "sleep"):
        calls = {"n": 0}
        def always_fail(host, port, timeout=30):
            calls["n"] += 1
            f = FakeSMTP(host, port, timeout)
            f.exc = _smtplib.SMTPAuthenticationError(535, b"auth failed")
            return f
        msmtp.SMTP.side_effect = always_fail
        ok, notes = ed.deliver("always fails")
assert ok is False and calls["n"] == 3
assert any("FAILED after 3 attempts" in n for n in notes), notes
print("3. persistent failure (returns False, no raise): OK")

# --- 4. env-missing guard: no credentials -> skip, zero SMTP ------------------
FakeSMTP.instances = []
with _env():
    with patch.object(ed, "smtplib") as msmtp, \
            patch.object(ed.time, "sleep"):
        ok, notes = ed.deliver("no creds")
assert ok is False and msmtp.SMTP.call_count == 0, "must not touch SMTP"
assert any("not set — email delivery skipped" in n for n in notes), notes
print("4. env-missing guard (no SMTP): OK")

# --- 5. explicit params override env ------------------------------------------
FakeSMTP.instances = []
with _env(EMAIL_USER="env@x.com", EMAIL_APP_PASSWORD="e" * 16, EMAIL_TO="+1"):
    with patch.object(ed, "smtplib") as msmtp, \
            patch.object(ed.time, "sleep"):
        msmtp.SMTP.side_effect = FakeSMTP
        ok, _ = ed.send_email("explicit", user="explicit@x.com",
                              app_password="x" * 16, to="z@x.com")
assert ok is True
srv = FakeSMTP.instances[0]
assert srv.login_args == ("explicit@x.com", "x" * 16)
assert srv.sent[0]["To"] == "z@x.com"
print("5. explicit params override env: OK")

print("\n✅ ALL EMAIL DELIVERY TESTS PASSED")
