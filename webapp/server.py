"""Local dashboard server for the OLP XDV board — stdlib-only (no pip).

Serves today's board, history, gate stats and a JSON API, all READ-ONLY over
the saved board JSONs + the brain. It never writes to the repo and never
fabricates: a missing date is an honest 404 (NO DATA — PENDING), never a guess
(HR35).

Usage:
    python webapp/server.py                     # localhost only
    python webapp/server.py --host 0.0.0.0      # reachable from a phone on the LAN
    python webapp/server.py --port 8088

Start it once (or via start_server.bat) and open http://<host>:<port>.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

BOARD_DIR = ROOT / "output" / "boards"
_DT = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _render(self, html: str):
        self._send(200, html.encode("utf-8"))

    def _redirect(self, to: str):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _not_found(self):
        self._send(404, b"NO DATA \xe2\x80\x94 PENDING: nothing here.", "text/plain; charset=utf-8")

    def _not_found_html(self, html: str):
        # A missing board is an honest 404 (HR35) — the page explains, but the
        # status says "not there", so a client/fetcher can tell it apart from a
        # real board.
        self._send(404, html.encode("utf-8"))

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        today = date.today().isoformat()

        try:
            from webapp import render as R
            from webapp import schema as S

            if path in ("/", "/board"):
                self._redirect(f"/board/{today}")

            elif path == "/history":
                self._render(R.render_history_html(_board_dates(), today))

            elif path == "/stats":
                with _brain() as b:
                    from brain.report import render_stats
                    self._render(R.render_stats_html(render_stats(b), today))

            elif path.startswith("/board/"):
                d = path[len("/board/"):]
                if not _DT.match(d):
                    return self._not_found()
                try:
                    payload = S.read_payload(_payload_path(d))
                except (FileNotFoundError, ValueError):
                    return self._not_found_html(R.render_404_html(d, today))
                self._render(R.render_dashboard(payload))

            elif path == "/why":
                fixture = (qs.get("fixture") or [""])[0]
                d = (qs.get("date") or [today])[0]
                if not fixture:
                    return self._redirect(f"/board/{today}")
                try:
                    payload = S.read_payload(_payload_path(d))
                except (FileNotFoundError, ValueError):
                    return self._not_found_html(R.render_404_html(d, today))
                self._render(R.render_why_html(payload, fixture))

            elif path == "/api/board.json":
                payload = S.read_payload(_payload_path(today))
                self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")

            elif path.startswith("/api/board/"):
                d = path[len("/api/board/"):].removesuffix(".json")
                if not _DT.match(d):
                    return self._not_found()
                payload = S.read_payload(_payload_path(d))
                self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")

            elif path == "/api/stats.json":
                with _brain() as b:
                    from brain.report import render_stats
                    body = json.dumps({"text": render_stats(b)},
                                      ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")

            else:
                self._not_found()

        except FileNotFoundError:
            self._not_found()
        except Exception as e:  # server must never crash the thread
            try:
                self._send(500, (f"server error: {e}").encode("utf-8"), "text/plain; charset=utf-8")
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description="OLP XDV dashboard (read-only)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 makes it reachable from a phone on the LAN")
    ap.add_argument("--port", type=int, default=8088)
    a = ap.parse_args()
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"OLP XDV dashboard on http://{a.host}:{a.port}")
    print(f"  today:  http://localhost:{a.port}/board/{date.today().isoformat()}")
    print("  Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
