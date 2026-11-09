"""
VALUE LINE (Architect 2026-11-09 plan, step 6: judge the framework by price, not hit rate).

A board of short favourites can win 80% of the time and still lose money. This puts one
block in the 23:02 report: the board's football singles of the last DAYS days, overall and by
market family —
    bets / won      graded singles and how many won (hit rate shown, but not the score)
    ROI             £1 flat at the price taken
    CLV             price x the exchange's closing fair chance - 1 (engine/edge_book), and the
                    share of singles that beat the close
RECORD-ONLY: it reads the picks ledger and the edge book, changes nothing. A single with no
exchange close counts in ROI but not in CLV; nothing is filled in (HR35).

    python monitor/value_line.py            print the block
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import edge_book as eb  # noqa: E402
from engine import exchange as ex  # noqa: E402
from engine import learning  # noqa: E402
from monitor.edge_scoreboard import _ALIAS, PICKS_DIR, _picks, summarize  # noqa: E402

DAYS = 30
TOP_FAMILIES = 6


def rows(today: str, picks_dir: Path = PICKS_DIR, obs: dict | None = None) -> dict[str, list[dict]]:
    since = (date.fromisoformat(today) - timedelta(days=DAYS)).isoformat()
    obs = eb.load_all() if obs is None else obs
    out: dict[str, list[dict]] = {}
    for day, doc in _picks("picks", picks_dir):
        if not (since <= day <= today):
            continue
        for s in doc.get("singles") or []:
            price = ex._f(s.get("price"))
            if not price:
                continue
            key = _ALIAS.get(s.get("market") or "", s.get("market") or "")
            ev = eb.find(obs, s.get("sb_event_id"), s.get("home") or "", s.get("away") or "", day)
            rec = (ev or {}).get("k", {}).get(key) or {}
            row = {"price": price, "won": {"won": 1, "lost": 0}.get(s.get("result")), "p_close": rec.get("p1")}
            fam = (s.get("drift") or {}).get("family") or learning.family(s.get("market") or key)
            out.setdefault("all", []).append(row)
            out.setdefault(fam, []).append(row)
    return out


def _pct(x: float | None) -> str:
    return "PENDING" if x is None else f"{x:+.1%}"


def build(today: str, picks_dir: Path = PICKS_DIR, obs: dict | None = None) -> dict:
    groups = {k: summarize(k, v) for k, v in rows(today, picks_dir, obs).items()}
    a = groups.get("all")
    if not a or not a["n"]:
        return {"groups": groups, "report_line": f"VALUE LINE (last {DAYS} days, board singles): no graded singles "
                                                  "yet — PENDING."}
    head = (f"VALUE LINE (last {DAYS} days, board singles; judged by price, not hit rate): {a['n']} graded, "
            f"won {a['hit']:.0%}; ROI {_pct(a['roi'])}; CLV {_pct(a['clv'])} on {a['n_clv']} with an exchange close"
            + (f", {a['beat']:.0%} beat the close" if a.get("beat") is not None else "") + ".")
    fams = sorted((g for k, g in groups.items() if k != "all" and g["n"]), key=lambda g: -g["n"])[:TOP_FAMILIES]
    lines = [head] + [f"- {g['name']}: {g['n']} bets, won {g['hit']:.0%}, ROI {_pct(g['roi'])}, CLV {_pct(g['clv'])}"
                      for g in fams]
    return {"groups": groups, "report_line": "\n".join(lines)}


def run(today: str, **kw) -> dict:
    return build(today, **kw)


if __name__ == "__main__":
    print(run(date.today().isoformat())["report_line"])
