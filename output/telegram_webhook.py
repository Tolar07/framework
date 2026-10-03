"""Telegram webhook mode — instant replies without a resident poller.

Long-polling (telegram_commands --loop) is a daemon that calls getUpdates; it
answers within the poll window but needs a process always running and reachable.
Webhook mode inverts this: the bot registers an HTTPS URL with Telegram
(setWebhook), and Telegram POSTs each update there the instant it arrives — no
poller process, near-instant replies.

Cost: Telegram requires a public HTTPS endpoint (a valid certificate, or a
self-signed one supplied at registration). There is no such endpoint on a dev
box, so this module is built and TESTED but only activated when the Architect
points it at a reachable URL (e.g. a Cloudflare tunnel or a small VPS). Until
then the long-polling daemon stays the delivery path.

Both transports run the EXACT same per-update handling —
telegram_commands.handle_update — so a webhook reply is a poller reply: same
commands, same whitelist, same bright-line refusals.

Standalone use (source-run, like every other module here):
  python output/telegram_webhook.py --register https://your.host/webhook --secret <s>
  python output/telegram_webhook.py --info
  python output/telegram_webhook.py --serve --port 8443 --secret <s>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from output.telegram_commands import handle_update

TELEGRAM_API = "https://api.telegram.org/bot{token}"
WEBHOOK_PATH = "/webhook"

# The only update kinds we understand. Everything else (chat_member, edited
# message, ...) is answered and ignored — never routed, never executed.
ALLOWED_UPDATES = ["message", "callback_query"]


def _token(token: str | None) -> str:
    return token or os.environ.get("TELEGRAM_BOT_TOKEN", "")


def register(token: str | None = None, url: str = "",
             secret_token: str = "", max_connections: int = 40,
             drop_pending: bool = False) -> tuple[bool, list[str]]:
    """Set (url given) or clear (url empty) the bot's webhook.

    `secret_token` becomes the value of the X-Telegram-Bot-Api-Secret-Token
    header Telegram sends on every update; the receiver rejects any POST that
    lacks it, which is the only real authentication a public endpoint has.
    Returns (ok, notes)."""
    token = _token(token)
    if requests is None:
        return False, ["requests not installed — cannot set a webhook"]
    if not token:
        return False, ["TELEGRAM_BOT_TOKEN not set — cannot set a webhook"]
    try:
        if not url:
            payload = {"drop_pending_updates": bool(drop_pending)}
            endpoint = "deleteWebhook"
        else:
            payload = {"url": url, "allowed_updates": ALLOWED_UPDATES,
                       "max_connections": max_connections}
            if secret_token:
                payload["secret_token"] = secret_token
            endpoint = "setWebhook"
        r = requests.post(f"{TELEGRAM_API.format(token=token)}/{endpoint}",
                          json=payload, timeout=20)
        data = r.json()
        if data.get("ok"):
            verb = "registered" if url else "removed"
            return True, [f"webhook {verb} ({endpoint}): {data.get('description', 'ok')}"]
        return False, [f"webhook API error: {data.get('description', 'unknown')}"]
    except Exception as e:
        return False, [f"webhook API call failed: {str(e)[:120]}"]


def info(token: str | None = None) -> dict:
    """getWebhookInfo — what Telegram thinks the webhook state is."""
    token = _token(token)
    if requests is None or not token:
        return {"ok": False, "error": "requests not installed / token not set"}
    try:
        r = requests.get(f"{TELEGRAM_API.format(token=token)}/getWebhookInfo",
                         timeout=20)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


class _WebhookHandler(BaseHTTPRequestHandler):
    """Serves POST /webhook. Acks 200 FAST, then handles the update in a
    daemon thread so Telegram never sees a slow reply and retries us.

    A /send takes ~30s; if the handler blocked until it finished, Telegram
    would time out and re-post the same update, double-answering the command.
    A fast 200 marks delivery done; the thread finishes on its own."""

    server_version = "OLPXDV/1.0"

    def do_POST(self) -> None:
        if urlparse(self.path).path != WEBHOOK_PATH:
            self.send_error(404)
            return
        server = self.server
        secret = getattr(server, "secret_token", "")
        if secret and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
            self.send_error(403)  # spoofed POST to a public URL — refuse it
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            update = json.loads(body.decode("utf-8"))
            if not isinstance(update, dict):
                raise ValueError("update must be an object")
        except Exception:
            self.send_error(400)
            return
        # 200 NOW — before the command runs. Telegram counts delivery done.
        self.send_response(200)
        self.end_headers()
        token = getattr(server, "bot_token", "")
        threading.Thread(target=handle_update, args=(update, token),
                         daemon=True).start()

    def log_message(self, fmt: str, *args) -> None:  # keep the socket quiet
        pass


class WebhookReceiver(ThreadingHTTPServer):
    """A stdlib HTTPS server that hands POST /webhook updates to handle_update.

    Plain HTTP by default (dev/testing); run it behind a TLS terminator in
    production, or subclass with ssl and a certificate. `bot_token` and
    `secret_token` are read by the handler off this instance."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, bot_token: str = "", secret_token: str = "") -> None:
        super().__init__(addr, _WebhookHandler)
        self.bot_token = bot_token
        self.secret_token = secret_token


def serve(port: int, bot_token: str = "", secret_token: str = "",
          host: str = "127.0.0.1") -> None:
    """Run the receiver until interrupted. The quiet path — the poller-style
    log lines carry the detail, so the daemon logs to stdout like the poller."""
    receiver = WebhookReceiver((host, port), bot_token=bot_token,
                               secret_token=secret_token)
    print(f"OLP XDV webhook receiver on {host}:{port}{WEBHOOK_PATH} — Ctrl-C to stop")
    try:
        receiver.serve_forever()
    except KeyboardInterrupt:
        print("webhook receiver stopped")
        receiver.server_close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="OLP XDV Telegram webhook mode — register, inspect or serve.")
    ap.add_argument("--register", nargs="?", const="", default=None, metavar="URL",
                    help="register this HTTPS webhook URL (no value = remove)")
    ap.add_argument("--secret", default="",
                    help="secret token Telegram must send on each update")
    ap.add_argument("--info", action="store_true", help="show getWebhookInfo")
    ap.add_argument("--serve", action="store_true", help="run the receiver")
    ap.add_argument("--port", type=int, default=8443, help="receiver port (default 8443)")
    args = ap.parse_args()

    if args.register is not None:
        ok, notes = register(url=args.register, secret_token=args.secret)
        for n in notes:
            print(("OK: " if ok else "FAILED: ") + n)
        if not ok:
            sys.exit(1)
    if args.info:
        print(json.dumps(info(), indent=2))
    if args.serve:
        serve(port=args.port, secret_token=args.secret)


if __name__ == "__main__":
    main()
