"""
NBA MARKET STUDY — every SportyBet NBA market against the results
(Architect 2026-10-13, "do both (a) and (b)"; engine/nba_markets.py).

Each game's LAST look before tip-off — from the every-market record
(output/nba_markets/) and, for the games before it existed, the ladder
snapshots (output/nba_ladders/: full-game total, team points, handicap) —
settled from ESPN's final and quarter scores. Per market:
  landed   how often the outcome won
  fair     SportyBet's own chance: its prices with the margin removed
  return   £1 flat on every outcome at SportyBet's price
and the same split by the short side (price under 2.00) and the long side,
where a bookmaker's favourite-longshot lean shows. Preseason and regular
season apart (preseason rests starters). A market seen whose settlement rule
isn't confirmed is listed as seen and PENDING. A study, not a selector.

    python backtest/nba_market_study.py   → backtest/NBA_MARKET_STUDY.md
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_source as ns  # noqa: E402
from engine import nba_ladder as nl  # noqa: E402
from engine import nba_markets as nm  # noqa: E402

OUT = ROOT / "backtest" / "NBA_MARKET_STUDY.md"
NAMES = {"219": "Winner (incl. OT)", "1": "1X2 (regulation)", "225": "Total points (incl. OT)",
         "227": "Home team points (incl. OT)", "228": "Away team points (incl. OT)",
         "223": "Handicap (incl. OT)", "47": "Half time / full time", "18": "Total points (regulation)",
         "68": "1st half total", "236": "1st quarter total", "66": "1st half handicap",
         "303": "Quarter handicap (Q1-Q3)"}


def from_ladder(row: dict) -> dict:
    """A ladder snapshot in the every-market shape (its four full-game markets)."""
    mk = []
    for key, lines in (row.get("ladders") or {}).items():
        mid = key.split("/")[0]
        for line, a, b in lines:
            if mid in nl.TOTAL_MARKETS:
                mk.append({"id": mid, "name": NAMES.get(mid, mid), "spec": f"total={line:g}", "open": True,
                           "outcomes": [[f"Over {line:g}", a], [f"Under {line:g}", b]]})
            else:
                q = f"|quarternr={key.split('/q')[1]}" if "/q" in key else ""
                mk.append({"id": mid, "name": NAMES.get(mid, mid), "spec": f"hcp={line:g}{q}", "open": True,
                           "outcomes": [[f"Home ({line:+g})", a], [f"Away ({-line:+g})", b]]})
    return {**row, "markets": mk}


def looks() -> list[dict]:
    """Every game's last look before tip-off: the every-market record where it
    has the game, else the ladder snapshot."""
    full = {r["event_id"]: r for r in nm.last_looks(nm.load())}
    lad = [from_ladder(r) for r in nl.load() if nl.is_clean(r)]
    for r in nm.last_looks(lad):
        full.setdefault(r["event_id"], r)
    return list(full.values())


def espn_game(row: dict):
    tip = datetime.fromisoformat(row["tip"].replace("Z", "+00:00"))
    for d in (tip.date() - timedelta(days=1), tip.date()):
        for g in ns.scoreboard(d):
            if g.id == row.get("espn_id") and g.completed:
                return g
    return None


def family(m: dict) -> str:
    if m["id"] in NAMES:
        return NAMES[m["id"]]
    name = re.sub(r"[-+]?\d+(\.\d+)?", "", m.get("name") or "").strip()
    return f"{name} [{m['id']}]"


def settle_rows(rows: list[dict], games: dict) -> tuple[list[dict], dict]:
    """[{stage, family, price, fair, won}] for every settled outcome, and the
    markets seen that couldn't be settled ({family: outcomes})."""
    out, unsettled = [], defaultdict(int)
    for r in rows:
        g = games.get(r["event_id"])
        if g is None:
            continue
        for m in r["markets"]:
            if not m.get("open", True):
                continue
            prices = [p for _d, p in m["outcomes"]]
            if any(p <= 1 for p in prices):
                continue
            inv = sum(1 / p for p in prices)
            for desc, p in m["outcomes"]:
                w = nm.settle_any(m["id"], m.get("spec") or "", desc, g.hs, g.as_, g.q_home, g.q_away)
                if w is None:
                    unsettled[family(m)] += 1
                    continue
                out.append({"stage": r.get("stage"), "family": family(m), "price": p,
                            "fair": (1 / p) / inv, "won": w})
    return out, dict(unsettled)


def _line(rows: list[dict]) -> str:
    n = len(rows)
    land = sum(r["won"] for r in rows) / n
    fair = sum(r["fair"] for r in rows) / n
    ret = sum(r["price"] * r["won"] - 1 for r in rows) / n
    return f"{n} | {land:.1%} | {fair:.1%} | {ret:+.1%}"


def build(rows: list[dict], games: dict) -> str:
    settled, unsettled = settle_rows(rows, games)
    out = ["# NBA MARKET STUDY — every SportyBet NBA market against the results", "",
           "Each game's last look before tip-off, every outcome settled from ESPN's final and quarter "
           "scores. *Landed* = how often it won; *fair* = SportyBet's own chance (its prices, margin "
           "removed); *return* = £1 flat on every outcome at SportyBet's price. Landed above fair on a "
           "side = SportyBet under-prices it. Written by `backtest/nba_market_study.py`. A study, not a selector.", "",
           f"Games with a look: {len(rows)} · graded (ESPN final): {sum(r['event_id'] in games for r in rows)}", ""]
    if not settled:
        return "\n".join(out + ["NO DATA — PENDING (no graded game yet)"]) + "\n"
    for stage in ("regular", "preseason"):
        part = [r for r in settled if r["stage"] == stage]
        out += [f"## {stage.capitalize()}" + (" (starters rested — a weak test)" if stage == "preseason" else ""), ""]
        if not part:
            out += ["NO DATA — PENDING", ""]
            continue
        out += ["| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return "
                "| long side (≥2.00): n · landed · fair · return |", "|---|---:|---:|---:|---:|---|---|"]
        fams: dict[str, list[dict]] = defaultdict(list)
        for r in part:
            fams[r["family"]].append(r)
        for fam, rs in sorted(fams.items(), key=lambda kv: -len(kv[1])):
            short = [r for r in rs if r["price"] < 2]
            long_ = [r for r in rs if r["price"] >= 2]
            out.append(f"| {fam} | {_line(rs)} | {_line(short).replace(' | ', ' · ') if short else '—'} | "
                       f"{_line(long_).replace(' | ', ' · ') if long_ else '—'} |")
        out.append("")
    if unsettled:
        out += ["## Seen, not settled (rule not confirmed — PENDING)", ""]
        out += [f"- {fam}: {n} outcomes" for fam, n in sorted(unsettled.items())]
    return "\n".join(out) + "\n"


def main() -> int:
    rows = looks()
    games = {}
    for r in rows:
        if datetime.fromisoformat(r["tip"].replace("Z", "+00:00")) < datetime.now().astimezone() - timedelta(hours=3):
            g = espn_game(r)
            if g is not None:
                games[r["event_id"]] = g
    text = build(rows, games)
    OUT.write_text(text, encoding="utf-8")
    print(f"NBA market study: {len(rows)} games, {len(games)} graded → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
