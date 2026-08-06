"""Static export of the dashboard — the "open it anywhere" half.

Writes a self-contained folder (webapp/site/) that any static host can serve:
GitHub Pages, Netlify, Cloudflare Pages, or just a double-clicked index.html.
The board + stats JSON are exported alongside so a client or future app can
read the data without a server.

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

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    (out / "index.html").write_text(
        R.render_dashboard(payload), encoding="utf-8")
    written.append(out / "index.html")

    (out / "board.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    written.append(out / "board.json")

    from brain.store import Brain
    from brain.report import render_stats
    with Brain(ROOT / "brain" / "olp.db", read_only=True) as b:
        stats_txt = render_stats(b)
    (out / "stats.json").write_text(
        json.dumps({"text": stats_txt}, ensure_ascii=False), encoding="utf-8")
    written.append(out / "stats.json")

    (out / "README.md").write_text(
        "# OLP XDV hosted board\n\n"
        f"Exported {date_str}. Upload this folder to any static host and open "
        "index.html. Re-run `python webapp/export.py` after each daily board.\n",
        encoding="utf-8")
    written.append(out / "README.md")
    return written


def main():
    ap = argparse.ArgumentParser(description="Export the dashboard as static files")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    for w in export(a.date, a.out):
        print(f"  wrote {w}")
    print(f"site ready at {a.out} — upload index.html + board.json + stats.json "
          "to any static host.")


if __name__ == "__main__":
    main()
