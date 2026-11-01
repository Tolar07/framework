"""
BOT LEARNING — the bots' paper challengers brought into the framework (Architect 2026-11-01: "make
sure everything is connected"). Bot-training plan step 5 gave each live bot a paper challenger (the
live rule with one setting changed, graded beside it). This reads each bot's own challenger ledger
from the checkouts the bot grader already has (.bots/, universe.yml) with the bot's OWN code
(<pkg>/challenger.py summary()), and:

  * report_block()  — the challenger lines for the ONE daily bot report (monitor/bot_grader.py), so
                      the Architect sees "challenger beats live" without opening four repos;
  * save()          — data/bots/learning.json: per bot and variant the verdict, graded counts, win
                      rate, CLV and level-stake ROI (ratios only: this repo is public, no stake or
                      money figure is written or printed);
  * scripts/self_improve.py reads that file: a challenger that beats live becomes a weekly
    "Promotion ready" proposal. Nothing here changes a bot.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bots" / "learning.json"

# (label, repo folder, package, ledger reader)
BOTS = (
    ("Matchbook", "matchbook-agent", "matchbook_live", "state:ledger"),
    ("SportyBet 1", "sportybet-agent", "sportybet", "file:ledger/sportybet/rules/challenger.json"),
    ("SportyBet 2", "sportybet-agent", "sportybet", "file:ledger/sportybet2/rules/challenger.json"),
    ("Betfair", "betfair-agent", "betfair", "file:ledger/challenger.json"),
)


def _module(root: Path, pkg: str):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return importlib.import_module(f"{pkg}.challenger")


def _records(mod, root: Path, reader: str) -> list[dict]:
    kind, rel = reader.split(":", 1)
    if kind == "state":
        recs, _ = mod._load(root / rel)
        return list(recs)
    p = root / rel
    return list((mod.load(p).get("bets") or [])) if p.exists() else []


def _baseline(mod, variant: str) -> str | None:
    base = getattr(mod, "BASELINE", None)
    if isinstance(base, dict):                       # SportyBet: one baseline per rule
        rule, ov = mod.VARIANTS[variant]
        return base[rule] if ov else None
    return None if variant == base else base


def collect(bots_dir: Path) -> list[dict]:
    """One row per bot: label, lines (the bot's own report lines), variants [{...}], or error."""
    out = []
    for label, repo, pkg, reader in BOTS:
        root = bots_dir / repo
        if not (root / pkg / "challenger.py").exists():
            continue
        try:
            mod = _module(root, pkg)
            recs = _records(mod, root, reader)
            s = mod.summary(recs)
            rows = []
            for v in mod.VARIANTS:
                b = _baseline(mod, v)
                if not b:
                    continue
                ch, lv = s[v], s[b]
                rows.append({"variant": v, "baseline": b, "verdict": mod.verdict(ch, lv),
                             "graded": ch["graded"], "baseline_graded": lv["graded"],
                             "win_rate": ch["win_rate"], "baseline_win_rate": lv["win_rate"],
                             "clv": ch["clv"], "baseline_clv": lv["clv"],
                             "roi": ch["roi"], "baseline_roi": lv["roi"]})
            out.append({"bot": label, "lines": mod.report(recs, s), "variants": rows})
        except Exception as e:  # noqa: BLE001 — one bot's ledger never stops the others or the report
            out.append({"bot": label, "error": f"{type(e).__name__}: {str(e)[:120]}", "variants": []})
    return out


def beats(row: dict) -> bool:
    return "beats" in str(row.get("verdict") or "").lower() and "not" not in str(row.get("verdict")).lower()


def report_block(rows: list[dict]) -> str:
    if not rows:
        return ""
    lines = ["Paper challengers (live rule with one setting changed, level stakes):"]
    for r in rows:
        if r.get("error"):
            lines.append(f"{r['bot']}: challenger ledger unreadable ({r['error']})")
            continue
        lines.append(f"{r['bot']}:")
        lines += r.get("lines") or ["  no challenger bets yet"]
    return "\n".join(lines)


def save(rows: list[dict], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = [{"bot": r["bot"], "error": r.get("error"), "variants": r.get("variants") or []} for r in rows]
    path.write_text(json.dumps({"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "bots": safe},
                               indent=1), encoding="utf-8")


def load(path: Path = OUT) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
