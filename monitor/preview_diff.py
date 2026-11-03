"""
PREVIEW CHANGES (Architect 2026-11-03): compare each day's two latest preview boards (output/preview/) and
append what moved to output/preview/changes_<date>.md: picks added or dropped, the pick switched, price moves
of 3%+, chance moves of 3+ pts, news / line-up flags. latest.json lists every previewed day. Read-only on the
real board: it never edits picks, codes or stakes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "output" / "preview"
PRICE_MOVE, CHANCE_MOVE = 0.03, 0.03


def _singles(doc: dict) -> dict:
    return {s["fixture"]: s for s in doc.get("singles") or []}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def changes(old: dict, new: dict) -> list[str]:
    a, b = _singles(old), _singles(new)
    out = [f"+ {fx}: {b[fx].get('pick')} @{b[fx].get('price')}" for fx in sorted(set(b) - set(a))]
    out += [f"- {fx}: dropped ({a[fx].get('pick')})" for fx in sorted(set(a) - set(b))]
    for fx in sorted(set(a) & set(b)):
        o, n = a[fx], b[fx]
        if o.get("market") != n.get("market"):
            out.append(f"~ {fx}: pick {o.get('pick')} -> {n.get('pick')}")
            continue
        po, pn = _f(o.get("price")), _f(n.get("price"))
        if po and pn and abs(pn / po - 1) >= PRICE_MOVE:
            out.append(f"~ {fx}: price {po:.2f} -> {pn:.2f}")
        co, cn = _f(o.get("chance")), _f(n.get("chance"))
        if co is not None and cn is not None and abs(cn - co) >= CHANCE_MOVE:
            out.append(f"~ {fx}: chance {co:.0%} -> {cn:.0%}")
        if (o.get("news_level") or "OK") != (n.get("news_level") or "OK"):
            out.append(f"! {fx}: news {o.get('news_level')} -> {n.get('news_level')} ({n.get('news_note') or ''})")
    for sec in ("accas", "safe3", "clv_accas"):
        if len(old.get(sec) or []) != len(new.get(sec) or []):
            out.append(f"~ {sec}: {len(old.get(sec) or [])} -> {len(new.get(sec) or [])}")
    return out


def main(d: Path = DIR) -> int:
    if not d.exists():
        return 0
    by_day: dict = {}
    for p in sorted(d.glob("preview_*_*.json")):
        m = re.match(r"preview_(\d{4}-\d{2}-\d{2})_(\d{4})\.json$", p.name)
        if m:
            by_day.setdefault(m.group(1), []).append(p)
    latest = {}
    for day, files in sorted(by_day.items()):
        new = json.loads(files[-1].read_text(encoding="utf-8"))
        latest[day] = {"file": files[-1].name, "singles": len(new.get("singles") or []),
                       "accas": len(new.get("accas") or []), "looks": len(files)}
        if len(files) < 2:
            continue
        old = json.loads(files[-2].read_text(encoding="utf-8"))
        lines = changes(old, new) or ["no change"]
        with (d / f"changes_{day}.md").open("a", encoding="utf-8") as f:
            f.write(f"\n## {files[-2].stem[-4:]} -> {files[-1].stem[-4:]} UTC\n" + "\n".join(lines) + "\n")
        print(f"{day}: {len(lines)} change line(s)")
    (d / "latest.json").write_text(json.dumps(latest, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
