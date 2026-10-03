"""Static export of the FEED dashboard — the "open it anywhere" half.

Writes a self-contained folder (webapp/site/) that any static host can serve:
GitHub Pages, Netlify, Cloudflare Pages, or just a double-clicked index.html.
Sprint 4: the exported page now references external assets (css/js/fonts), so
the static tree (webapp/static → site/static) is copied alongside index.html;
the page uses asset_base="./static" so the relative links resolve from file://.

SECURITY (Architect 2026-08-12): the export is public — a static host cannot
authenticate — so it is built from schema.read_feed() (raw board → the same
feed payload the served page renders). The feed IS the Telegram board's lean
content: no Elo/xG second opinions, no engine divergence, no consensus votes,
no verification, no EV verdicts. stats.json is deliberately NOT exported — it
was the admin diagnostic layer. Auto-feed = auto-publish: there is no Approve
gate; the daily board_<date>.json is the single source of truth.

    python webapp/export.py                 # today
    python webapp/export.py --date 2026-08-05
    python webapp/export.py --out site

Re-run after each daily board to refresh the hosted copy (the daily run writes
board_<date>.json; this turns that into the hostable site).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = Path(__file__).parent / "site"
STATIC_SRC = Path(__file__).parent / "static"


def export(date_str: str, out: Path) -> list[Path]:
    from webapp import render_v2 as R
    from webapp import schema as S

    # The export is the PUBLIC face — it reads the day's raw board through the
    # feed builder (the same content the served page shows; one render, two
    # outlets). A missing board fails honestly (no site).
    try:
        client_payload = S.read_feed(date_str)
    except FileNotFoundError:
        raise FileNotFoundError(f"No board for {date_str}. Run the daily production "
                                f"first — it writes output/boards/board_<date>.json.")

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Sprint 4: copy the static tree (css/js/fonts) so the page's external
    # asset references (./static/...) resolve. Underscore-prefixed entries are
    # build tooling (_fetch_fonts.py, css/_fontface.css), not served runtime
    # assets — skip them.
    (out / "static").mkdir(parents=True, exist_ok=True)
    for child in STATIC_SRC.iterdir():
        if child.name.startswith("_"):
            continue
        dst = out / "static" / child.name
        if child.is_dir():
            shutil.copytree(child, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(child, dst)
    written.append(out / "static")

    # A STANDALONE multi-date site: the root page links its Scan date pills to a
    # per-date page for every published board (relative ./<iso>/index.html, so
    # file:// and every static host resolve them — no dead /dashboard/... links
    # and no trailing-slash that only a host's directory index would answer).
    # Booking codes render like the served client (codes are client-safe betslip
    # recalls; a missing codes file renders the honest NO DATA — PENDING).
    (out / "index.html").write_text(
        R.render_dashboard(client_payload, asset_base="./static",
                           booking_codes=S.read_booking_codes(date_str),
                           pill_base="."),
        encoding="utf-8")
    written.append(out / "index.html")

    for iso in S.list_board_dates():
        try:
            sub_payload = S.read_feed(iso)
        except FileNotFoundError:
            continue  # the board list is authoritative; skip a race if any
        sub = out / iso
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "index.html").write_text(
            R.render_dashboard(sub_payload, asset_base="../static",
                               booking_codes=S.read_booking_codes(iso),
                               pill_base=".."),
            encoding="utf-8")
        written.append(sub / "index.html")

    (out / "board.json").write_text(
        json.dumps(client_payload, indent=1, ensure_ascii=False), encoding="utf-8")
    written.append(out / "board.json")

    (out / "README.md").write_text(
        "# OLP XDV hosted board\n\n"
        f"Feed boards — {date_str} and every other board date — the Telegram board, on the web.\n\n"
        "This export IS the daily Telegram board (one render, two outlets): it is built from "
        "the raw board_<date>.json via schema.build_feed_payload, so the web can never drift "
        "from Telegram. `index.html` is the board for the exported date; the Scan date pills "
        "link to a per-date page under `<date>/index.html` for each board day, so the folder "
        "is a fully independent site (plain static host or straight from file://). Model "
        "internals (Elo second opinion, engine divergence, consensus votes, verification, EV "
        "verdicts) never leave the server.\n\n"
        "Data is in `board.json` (same payload the root page renders).\n",
        encoding="utf-8")
    written.append(out / "README.md")

    return written


def main():
    ap = argparse.ArgumentParser(description="Export the public OLP XDV dashboard")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-prefetch-crests", action="store_true",
                    help="skip the club-badge prefetch (the exported board.json "
                         "already determines the crests)")
    a = ap.parse_args()
    written = export(a.date, a.out)
    for w in written:
        print(f"wrote {w}")
    # Pre-warm club badges for the exported board so the hosted site carries
    # real crests. Best-effort (never raises); `export()` stays offline-pure so
    # the test suites don't hit the network.
    if not a.no_prefetch_crests:
        try:
            from webapp import crests as _crests
            teams = _crests.teams_from_board(a.out / "board.json")
            got = _crests.prefetch(teams)
            still = _crests.missing(teams)
            print(f"crest prefetch: {len(got)} added, "
                  f"{len(still)} team(s) still on initials: "
                  + (", ".join(still) if still else "none"))
        except Exception as e:
            print(f"crest prefetch skipped ({e})")


if __name__ == "__main__":
    main()
