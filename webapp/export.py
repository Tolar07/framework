"""Static export of the CLIENT dashboard — the "open it anywhere" half.

Writes a self-contained folder (webapp/site/) that any static host can serve:
GitHub Pages, Netlify, Cloudflare Pages, or just a double-clicked index.html.
Sprint 4: the exported page now references external assets (css/js/fonts), so
the static tree (webapp/static → site/static) is copied alongside index.html;
the page uses asset_base="./static" so the relative links resolve from file://.

SECURITY (Architect order 2026-08-07): the export is public — a static host
cannot authenticate — so it is built from schema.trim_payload(). It contains
predictions only: no Elo/xG second opinions, no engine divergence, no consensus
votes, no verification, no EV verdicts, no gate/calibration/flags. stats.json
is deliberately NOT exported — it is the admin diagnostic layer.

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
    from webapp import render as R
    from webapp import schema as S

    # The export is the PUBLIC face — it reads ONLY from the published store.
    # If nothing is published for the date, the export fails honestly (no site).
    try:
        client_payload = S.read_published(date_str)
    except FileNotFoundError:
        raise FileNotFoundError(f"No published board for {date_str}. Run the server, "
                                f"open /admin/{date_str}, and click 'Approve → Publish to Client'.")

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

    (out / "index.html").write_text(
        R.render_dashboard(client_payload, asset_base="./static"), encoding="utf-8")
    written.append(out / "index.html")

    (out / "board.json").write_text(
        json.dumps(client_payload, indent=1, ensure_ascii=False), encoding="utf-8")
    written.append(out / "board.json")

    (out / "README.md").write_text(
        "# OLP XDV hosted board\n\n"
        f"Client board for **{date_str}** — predictions only.\n\n"
        "This export is the PUBLIC dashboard: it is built from the PUBLISHED store "
        "(written ONLY by the 'Approve → Publish to Client' action in /admin). "
        "Model internals (Elo second opinion, engine divergence, consensus votes, "
        "verification, EV verdicts, the gate, calibration) are admin-only and are "
        "not exported here.\n\n"
        "Data is in `board.json` (same payload the page renders). The full "
        "admin view is served by the local server at `/admin`.\n",
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
