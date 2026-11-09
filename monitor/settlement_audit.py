"""
SETTLEMENT AUDIT — record-only (framework#378, from the R&D bot's "grader with universe settlement").

monitor/bot_grader.py already grades every bot leg by game + market + side and writes one sidecar per bot
per day (ledger/.../graded/<day>.json) beside each bot's ledger: leg result 'won' / 'lost' / 'void' / None
(pending), plus its source. This reads those sidecars and records, per bot, how many legs are SETTLED vs
PENDING, which source settled them, and how often the framework's own settlement (universe / sport board)
was OVERRULED by the bookmaker's settlement ("sportybet (universe said ...)") - the grader's mislabel
rate. The issue's reject line is 5%: above it the audit says so.

It never edits a bot ledger, stake, limit, the CLV gate or any pick rule. `settled_legs()` is the helper a
CLV reader can use to take only settled legs; nothing calls it in a live decision yet (promotion gate).
Basketball (NBA, world, NCAA) legs are graded by the same grader, so they are audited here too.
Missing sidecars read PENDING (HR35), never a guessed figure.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bots" / "settlement_audit.json"
REJECT_RATE = 0.05
SETTLED = ("won", "lost", "void")


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def settled_legs(bet: dict) -> list[dict]:
    """The legs of a graded bet the grader has settled (won / lost / void); pending legs are left out."""
    return [x for x in bet.get("legs") or [] if x.get("result") in SETTLED]


def audit_bot(folder: Path) -> dict:
    """One bot's graded folder -> counts. Paper files (paper_<day>.json) are counted apart."""
    c: Counter = Counter()
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not files:
        return {"status": "PENDING", "why": "no graded sidecars"}
    for f in files:
        paper = f.name.startswith("paper_")
        data = _read(f) or {}
        for bet in (data.get("bets") or {}).values():
            c["paper_bets" if paper else "bets"] += 1
            for leg in bet.get("legs") or []:
                if paper:
                    continue
                res = leg.get("result")
                c["legs"] += 1
                if res in SETTLED:
                    c["settled"] += 1
                    c[res] += 1
                    src = str(leg.get("source") or "")
                    if "universe said" in src or "board said" in src:
                        c["overruled"] += 1
                    elif src.startswith("sportybet"):
                        c["by_bookmaker"] += 1
                    elif src.startswith("exchange"):
                        c["by_exchange"] += 1
                    else:
                        c["by_framework"] += 1
                else:
                    c["pending"] += 1
    settled = c["settled"]
    # overruled legs are the only ones where the framework's grade and the bookmaker's can be seen to differ
    checked = c["overruled"] + c["by_framework"]
    rate = round(c["overruled"] / checked, 4) if checked else None
    return {"status": "OK" if settled else "PENDING", "bets": c["bets"], "paper_bets": c["paper_bets"],
            "legs": c["legs"], "settled": settled, "pending": c["pending"], "won": c["won"],
            "lost": c["lost"], "void": c["void"], "by_framework": c["by_framework"],
            "by_bookmaker": c["by_bookmaker"], "by_exchange": c["by_exchange"],
            "overruled_by_bookmaker": c["overruled"], "mislabel_rate": rate,
            "rejects_grader": bool(rate is not None and rate > REJECT_RATE)}


def audit(root: Path, sidecar: dict) -> dict:
    """sidecar = bot_grader.SIDECAR ({bot: (repo, subfolder)})."""
    return {bot: audit_bot(root / repo / sub) for bot, (repo, sub) in sidecar.items()}


def save(rows: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                "reject_rate": REJECT_RATE, "bots": rows}, indent=1) + "\n", encoding="utf-8")


def lines(rows: dict) -> list[str]:
    out = []
    for bot, r in rows.items():
        if r.get("status") != "OK":
            out.append(f"{bot}: PENDING ({r.get('why', 'nothing settled yet')})")
        else:
            m = "n/a" if r["mislabel_rate"] is None else f"{r['mislabel_rate']:.1%}"
            out.append(f"{bot}: {r['settled']} legs settled, {r['pending']} pending, bookmaker overruled the framework on {m}")
    return out


if __name__ == "__main__":
    from monitor import bot_grader as bg
    res = audit(bg.BOTS, bg.SIDECAR)
    save(res)
    print("\n".join(lines(res)))
