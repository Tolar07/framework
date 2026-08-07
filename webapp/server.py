"""Local dashboard server for the OLP XDV board — stdlib-only (no pip).

Two-tier design (Architect order 2026-08-07, reference webapp/design_reference/):

  /dashboard            — the PUBLIC client view: predictions only. Served from
                          schema.trim_payload(), so a model internal can NEVER
                          reach this route or the public JSON API.
  /admin                — the authed view: everything + model internals,
                          verification, cap, data flags, yesterday-graded.
                          Protected by HTTP Basic auth (ADMIN_USER / ADMIN_PASS
                          from .env). Without ADMIN_PASS configured it returns a
                          503 "set ADMIN_PASS" — never a default password.

/stats, /why and /api/stats.json are admin-only too (they render internals).
Everything is READ-ONLY over the saved board JSONs + the brain; a missing date
is an honest 404 (HR35), never a guess.

Usage:
    python webapp/server.py                     # localhost only
    python webapp/server.py --host 0.0.0.0      # reachable from a phone on the LAN
    python webapp/server.py --port 8088
"""
from __future__ import annotations

import argparse
import base64
import hmac
import json
import os
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402 — imports and runs load_dotenv() so .env reaches os.environ

BOARD_DIR = ROOT / "output" / "boards"
_DT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NO_DATA = b"NO DATA \xe2\x80\x94 PENDING: nothing here."


def _brain():
    from brain.store import Brain
    return Brain(ROOT / "brain" / "olp.db", read_only=True)


def _payload_path(date_str: str) -> Path:
    return BOARD_DIR / f"board_{date_str}.json"


def _board_dates() -> list[str]:
    return sorted((p.name[len("board_"):-len(".json")] for p in
                   BOARD_DIR.glob("board_*.json")), reverse=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "OLPXDV/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter than the default stderr spam
        sys.stderr.write("[web] %s %s\n" % (self.address_string(), fmt % args))

    # -- helpers ----------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8",
              extra_headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _render(self, html: str):
        self._send(200, html.encode("utf-8"))

    def _json(self, obj):
        self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _redirect(self, to: str):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _not_found(self):
        self._send(404, _NO_DATA, "text/plain; charset=utf-8")

    def _not_found_html(self, html: str):
        # A missing board is an honest 404 (HR35) — the page explains, but the
        # status says "not there", so a client/fetcher can tell it apart from a
        # real board.
        self._send(404, html.encode("utf-8"))

    # -- admin auth ---------------------------------------------------------
    def _admin_ok(self) -> bool:
        """True when the request carries valid ADMIN_USER/ADMIN_PASS (Basic).
        A missing ADMIN_PASS env var is treated as NOT ok — the caller returns
        a 503 "set ADMIN_PASS" rather than ever accepting a default."""
        pw = os.environ.get("ADMIN_PASS")
        user = os.environ.get("ADMIN_USER", "admin")
        if not pw:
            return False
        hdr = self.headers.get("Authorization", "")
        if not hdr.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(hdr[len("Basic "):]).decode("utf-8")
            u, _, p = raw.partition(":")
        except Exception:
            return False
        return hmac.compare_digest(u, user) and hmac.compare_digest(p, pw)

    def _require_admin(self) -> bool:
        """401 (+WWW-Authenticate so the browser prompts) when not authed;
        503 when auth is unconfigured. Returns True only when the request is
        allowed through."""
        if self._admin_ok():
            return True
        if not os.environ.get("ADMIN_PASS"):
            self._send(503, (b"NO DATA \xe2\x80\x94 PENDING: ADMIN_PASS is not "
                             b"set in .env, so /admin is locked."),
                       "text/plain; charset=utf-8")
            return False
        body = (b"NO DATA \xe2\x80\x94 PENDING: admin authentication required.")
        self._send(401, body,
                   "text/plain; charset=utf-8",
                   extra_headers={"WWW-Authenticate": 'Basic realm="OLP XDV Admin"'})
        return False

    def _load_payload(self, d: str):
        """Full board payload, or None when missing/refused (honest 404)."""
        try:
            from webapp import schema as S
            return S.read_payload(_payload_path(d))
        except (FileNotFoundError, ValueError):
            return None

    def _load_published(self, d: str):
        """Published (trimmed) board payload, or None."""
        try:
            from webapp import schema as S
            return S.read_published(d)
        except (FileNotFoundError, ValueError):
            return None

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        today = date.today().isoformat()

        try:
            from webapp import render as R
            from webapp import schema as S

            # --- public dashboard ----------------------------------------
            if path in ("/", "/board"):
                self._redirect(f"/dashboard/{today}")

            elif path in ("/dashboard", "/dashboard/") :
                self._redirect(f"/dashboard/{today}")

            elif path.startswith("/dashboard/"):
                d = path[len("/dashboard/"):]
                if not _DT.match(d):
                    return self._not_found()
                payload = self._load_published(d)
                if payload is None:
                    return self._not_found_html(R.render_404_html(d, today))
                self._render(R.render_dashboard(payload))

            # --- authed admin view ----------------------------------------
            elif path in ("/admin", "/admin/"):
                self._redirect(f"/admin/{today}")

            elif path.startswith("/admin/"):
                if not self._require_admin():
                    return
                d = path[len("/admin/"):]
                if not _DT.match(d):
                    return self._not_found()
                payload = self._load_payload(d)
                if payload is None:
                    return self._not_found_html(R.render_404_html(d, today))
                self._render(R.render_admin_dashboard(payload))

            # --- history (a date list, no internals — stays public) ------
            elif path == "/history":
                self._render(R.render_history_html(_board_dates(), today))

            # --- internals pages: admin-only ------------------------------
            elif path == "/stats":
                if not self._require_admin():
                    return
                with _brain() as b:
                    from brain.report import render_stats
                    self._render(R.render_stats_html(render_stats(b), today))

            elif path == "/why":
                if not self._require_admin():
                    return
                fixture = (qs.get("fixture") or [""])[0]
                d = (qs.get("date") or [today])[0]
                if not fixture:
                    return self._redirect(f"/admin/{today}")
                payload = self._load_payload(d)
                if payload is None:
                    return self._not_found_html(R.render_404_html(d, today))
                self._render(R.render_why_html(payload, fixture))

            # --- JSON API -------------------------------------------------
            # Public board JSON is served from the PUBLISHED store only —
            # same approve-gate as the HTML /dashboard route. An unapproved
            # board is never exposed via JSON (previously both these routes
            # read the raw board dir, bypassing the gate).
            elif path == "/api/board.json":
                payload = self._load_published(today)
                if payload is None:
                    return self._not_found()
                self._json(payload)

            elif path.startswith("/api/board/"):
                d = path[len("/api/board/"):].removesuffix(".json")
                if not _DT.match(d):
                    return self._not_found()
                payload = self._load_published(d)
                if payload is None:
                    return self._not_found()
                self._json(payload)

            elif path == "/api/admin/board.json":
                if not self._require_admin():
                    return
                payload = self._load_payload(today)
                if payload is None:
                    return self._not_found()
                self._json(payload)

            elif path == "/api/stats.json":
                if not self._require_admin():
                    return
                with _brain() as b:
                    from brain.report import render_stats
                    self._json({"text": render_stats(b)})

            else:
                self._not_found()

        except FileNotFoundError:
            self._not_found()
        except Exception as e:  # server must never crash the thread
            try:
                self._send(500, (f"server error: {e}").encode("utf-8"), "text/plain; charset=utf-8")
            except Exception:
                pass

    def do_POST(self):
        """Publish action — admin only. Accepts JSON {date, approved_by?}."""
        parsed = urlparse(self.path)
        path = parsed.path
        if path != "/api/admin/publish":
            self._not_found()
            return
        if not self._require_admin():
            return
        try:
            import json
            from webapp import schema as S
            content_len = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
            data = json.loads(body) if body else {}
            d = data.get("date", "")
            approved_by = data.get("approved_by", "admin")
            if not d:
                self._json({"ok": False, "error": "date required"})
                return
            payload = self._load_payload(d)
            if payload is None:
                self._json({"ok": False, "error": f"no board for {d}"})
                return
            S.write_published(payload, approved_by=approved_by)
            self._json({"ok": True, "date": d, "published": True})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})


def main():
    ap = argparse.ArgumentParser(description="OLP XDV dashboard (read-only)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 makes it reachable from a phone on the LAN")
    ap.add_argument("--port", type=int, default=8088)
    a = ap.parse_args()
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"OLP XDV dashboard on http://{a.host}:{a.port}")
    print(f"  today:  http://localhost:{a.port}/dashboard/{date.today().isoformat()}")
    print(f"  admin:  http://localhost:{a.port}/admin (Basic auth — ADMIN_USER/ADMIN_PASS)")
    print("  Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
