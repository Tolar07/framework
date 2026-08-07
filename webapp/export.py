"""Static export of the CLIENT dashboard — the "open it anywhere" half.

Writes a self-contained folder (webapp/site/) that any static host can serve:
GitHub Pages, Netlify, Cloudflare Pages, or just a double-clicked index.html.

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
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = Path(__file__).parent / "site"


def export(date_str: str, out: Path) -> list[Path]:
    from webapp import render as R
    from webapp import schema as S

    payload = S.read_payload(ROOT / "output" / "boards" / f"board_{date_str}.json")
    # The public surface is the TRIMMED payload — internals never reach the
    # hosted copy, by construction.
    client_payload = S.trim_payload(payload)

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    (out / "index.html").write_text(
        R.render_dashboard(client_payload), encoding="utf-8")
    written.append(out / "index.html")

    (out / "board.json").write_text(
        json.dumps(client_payload, indent=1, ensure_ascii=False), encoding="utf-8")
    written.append(out / "board.json")

    (out / "README.md").write_text(
        "# OLP XDV hosted board\n\n"
        f"Client board for **{date_str}** — predictions only.\n\n"
        "This export is the PUBLIC dashboard: it is trimmed server-side to the "
        "market predictions (the model's 1X2 / goals / BTTS / double-chance "
        "probabilities). Model internals (Elo second opinion, engine "
        "divergence, consensus votes, verification, EV verdicts, the gate, "
        "calibration) are admin-only and are not exported here.\n\n"
        "Data is in `board.json` (same payload the page renders). The full "
        "admin view is served by the local server at `/admin`.\n",
        encoding="utf-8")
    written.append(out / "README.md")

    return written


def main():
    ap = argparse.ArgumentParser(description="Export the public OLP XDV dashboard")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    written = export(a.date, a.out)
    for w in written:
        print(f"wrote {w}")


if __name__ == "__main__":
    main()
