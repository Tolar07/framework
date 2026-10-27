"""
NBA EVERY-MARKET RECORD — every market SportyBet lists on an NBA game, at
every look, graded against the result (Architect 2026-10-13: "what are you
doing in terms of studying it and understanding each of the NBA betting
markets ... the under and over for first half, second half ... the point";
"do both (a) and (b)").

The board (run_nba.py) and the line watch (monitor/nba_watch.py) read
SportyBet's NBA list, which carries only the markets they ask for. Here each
game's full market page is read and kept whole — winner, 1X2, totals, team
points, handicaps, half time / full time, and every half / quarter market
SportyBet adds closer to tip-off — so nothing it offers goes unmeasured:

  output/nba_markets/<UTC date>.jsonl   one line per game per look

backtest/nba_market_study.py takes each game's last look before tip-off,
settles every outcome from ESPN's final and quarter scores (settle_any) and
compares how often each market landed with SportyBet's own chance (its
prices, margin removed). A market whose settlement rule isn't confirmed
(the 2nd half / 4th quarter: overtime in or out?) is kept and counted but
never settled — PENDING, not a guess.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output" / "nba_markets"
_EVENT = "https://www.sportybet.com/api/ng/factsCenter/event?eventId={eid}&productId=3"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def full_event(event_id: str) -> dict:
    """SportyBet's whole market page for one game."""
    req = urllib.request.Request(_EVENT.format(eid=urllib.parse.quote(event_id)),  # noqa: S310
                                 headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        return (json.loads(r.read()).get("data") or {})


def compact_markets(event: dict) -> list[dict]:
    """[{id, name, spec, open, outcomes: [[desc, price], ...]}] — every market."""
    out = []
    for m in event.get("markets") or []:
        outs = []
        for o in m.get("outcomes") or []:
            try:
                outs.append([o.get("desc", ""), float(o.get("odds"))])
            except (TypeError, ValueError):
                continue
        if outs:
            out.append({"id": str(m.get("id")), "name": m.get("desc") or m.get("name") or "",
                        "spec": m.get("specifier") or "", "open": m.get("status") in (None, 0, "0"),
                        "outcomes": outs})
    return out


def snapshot(now: datetime, stage: str, event_id: str, home: str, away: str, g) -> dict | None:
    """One look at one game: every market, with the ESPN game it settles on.
    None when SportyBet's page can't be read (the look is skipped, not faked)."""
    try:
        markets = compact_markets(full_event(event_id))
    except Exception:  # noqa: BLE001 — a page that won't load is a missing look
        return None
    if not markets:
        return None
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "stage": stage, "event_id": event_id,
            "espn_id": g.id, "espn_date": (g.tip or g.date)[:10], "tip": g.tip, "home": home, "away": away,
            "sharp": {"ml_home": g.ml_home, "ml_away": g.ml_away, "spread": g.spread, "total": g.total},
            "markets": markets}


def save(rows: list[dict | None], now: datetime, folder: Path = OUT_DIR) -> None:
    kept = [r for r in rows if r]
    if not kept:
        return
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def load(folder: Path = OUT_DIR) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*.jsonl")):
        rows += [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows


def _t(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def last_looks(rows: list[dict]) -> list[dict]:
    """Each game's last look taken before its tip-off."""
    best: dict[str, dict] = {}
    for r in rows:
        if not r.get("tip") or _t(r["at"]) >= _t(r["tip"]):
            continue
        if r["event_id"] not in best or _t(r["at"]) > _t(best[r["event_id"]]["at"]):
            best[r["event_id"]] = r
    return list(best.values())


def _result(home: int, away: int) -> str:
    return "Home" if home > away else "Away" if away > home else "Draw"


def settle_any(mid: str, spec: str, outcome: str, hs: int, as_: int,
               qh: list | None, qa: list | None) -> int | None:
    """1 won / 0 lost for any outcome whose rule is known; None otherwise.
    The board's own rules (engine/nba_value.settle) for its markets; here also
    1X2 (regulation time: four quarters) and half time / full time (the full
    time part is regulation too when a draw is one of its outcomes)."""
    from engine import nba_value as nv
    if mid in nv.MARKETS:
        r = nv.settle({"market_id": mid, "specifier": spec, "outcome": outcome}, hs, as_, qh, qa)
        return None if r is None else int(r == "won")
    if not qh or not qa or len(qh) < 4 or len(qa) < 4:
        return None
    reg = _result(sum(qh[:4]), sum(qa[:4]))
    if mid == "1":
        return int(outcome.strip().lower() == {"Home": "home", "Away": "away", "Draw": "draw"}[reg])
    if mid == "47":
        parts = [p.strip().lower() for p in re.split(r"[/-]", outcome)]
        if len(parts) != 2:
            return None
        half = _result(sum(qh[:2]), sum(qa[:2])).lower()
        return int(parts == [half, reg.lower()])
    return None
