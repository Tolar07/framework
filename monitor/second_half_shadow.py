"""
SECOND-HALF STAKES SHADOW (framework #494; Architect 2026-11-09 plan, step 3).

The one lead of backtest/second_half_study.py (#493): late in the season (both
sides past LATE of their games), a home side still within reach of a title /
Europe / relegation line playing an away side with nothing left won more often
than the opening price said (372 bets, ROI +17.8% ± 8.4%, CLV +1.1%) — but
without a probability gain, so it is not promoted. This records it live:

1. EVERY league match of this season (football-data, the study's leagues):
   once both sides are past LATE, a match where exactly one side is live is
   TAGGED "home stakes" or "away stakes"; its opening / closing price for that
   side and the result are kept. ROI at the opening price and CLV build up.
2. TODAY'S BOARD: the rated fixtures (output/picks) with the same tag from
   the table before the day, so the Architect can see them in the 23:02 report.

RECORD-ONLY. Nothing selects, stakes or changes a pick. Missing data reads
PENDING (HR35). Written to data/bots/second_half_shadow.json by the nightly
bot-grader run; one block in the 23:02 report.

    python monitor/second_half_shadow.py            print the block (no file written)
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import inputs as ip  # noqa: E402

PICKS_DIR = ROOT / "output" / "picks"
OUT = ROOT / "data" / "bots" / "second_half_shadow.json"
LATE = 0.75
LEAGUES = ("Premier League", "Championship", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Eredivisie",
           "Primeira Liga", "Scottish Premiership", "Belgian Pro League", "2. Bundesliga", "La Liga 2",
           "Serie B", "Ligue 2", "League One", "League Two", "National League", "Turkish Super Lig",
           "Greek Super League")


def season_code(day: str) -> str:
    y = int(ip.season_start(day)[:4])
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def tag(H: ip.History, home: str, away: str, day: str) -> str | None:
    """'home' / 'away' = only that side is live, late in the season; else None."""
    t = ip.table_asof(H, day)
    h, a = t.get(home), t.get(away)
    if not h or not a:
        return None
    n = h["size"]
    if min(h["played"], a["played"]) < LATE * 2 * (n - 1):
        return None
    sh, sa = ip.stakes(t, home), ip.stakes(t, away)
    if not sh or not sa or sh["live"] == sa["live"]:
        return None
    return "home" if sh["live"] else "away"


def league_rows(lg: str, results: list) -> list[dict]:
    H = ip.History(ip.from_results(results))
    out = []
    for m in sorted(results, key=lambda r: r.date):
        side = tag(H, m.home_team, m.away_team, m.date)
        if not side:
            continue
        od = m.odds
        mp = (od.home if side == "home" else od.away) if od else None
        won = (m.fthg > m.ftag) if side == "home" else (m.ftag > m.fthg)
        out.append({"date": m.date, "league": lg, "fixture": f"{m.home_team} v {m.away_team}", "side": side,
                    "open": getattr(mp, "open", None), "close": getattr(mp, "close", None),
                    "ft": f"{m.fthg}-{m.ftag}", "won": bool(won)})
    return out


def summary(rows: list[dict]) -> dict[str, Any]:
    priced = [r for r in rows if isinstance(r.get("open"), (int, float)) and r["open"] > 1]
    roi = [r["open"] * r["won"] - 1 for r in priced]
    clv = [r["open"] / r["close"] - 1 for r in priced if isinstance(r.get("close"), (int, float)) and r["close"] > 1]
    return {"tagged": len(rows), "priced": len(priced), "won": sum(r["won"] for r in rows),
            "roi": round(100 * sum(roi) / len(roi), 2) if roi else None,
            "clv": round(100 * sum(clv) / len(clv), 2) if clv else None}


def board_tags(today: str, tables: dict[str, ip.History], picks_dir: Path = PICKS_DIR) -> list[dict]:
    p = picks_dir / f"picks_{today}.json"
    if not p.exists():
        return []
    out = []
    for r in json.loads(p.read_text(encoding="utf-8")).get("rated", []):
        H = tables.get(r.get("league") or "")
        if H is None or not r.get("home") or not r.get("away"):
            continue
        side = tag(H, r["home"], r["away"], today)
        if side:
            out.append({"fixture": r.get("fixture") or f"{r['home']} v {r['away']}", "league": r["league"],
                        "side": side})
    return out


def build(today: str, load: Callable | None = None, picks_dir: Path = PICKS_DIR) -> dict[str, Any]:
    if load is None:
        from data.football_data_source import load_league
        load = load_league
    s = season_code(today)
    rows: list[dict] = []
    tables: dict[str, ip.History] = {}
    skipped = []
    for lg in LEAGUES:
        try:
            res, _ = load(lg, s)
        except Exception as e:  # noqa: BLE001 — one league down never blocks the rest
            skipped.append(f"{lg}: {type(e).__name__}")
            continue
        res = [m for m in res if m.date < today]
        tables[lg] = ip.History(ip.from_results(res))
        rows += league_rows(lg, res)
    sm = summary(rows)
    today_tags = board_tags(today, tables, picks_dir)
    if sm["tagged"]:
        line = (f"SECOND-HALF STAKES SHADOW (record-only, #494): {sm['tagged']} tagged games this season, "
                f"won {sm['won']}; ROI at opening {sm['roi'] if sm['roi'] is not None else 'PENDING'}%, "
                f"CLV {sm['clv'] if sm['clv'] is not None else 'PENDING'}%.")
    else:
        line = ("SECOND-HALF STAKES SHADOW (record-only, #494): no tagged games yet. Tags start once both sides "
                f"are {int(LATE * 100)}% through their season (about March).")
    if today_tags:
        line += " Today: " + "; ".join(f"{t['fixture']} ({t['side']} side has stakes)" for t in today_tags[:8])
    return {"date": today, "season": s, "summary": sm, "today": today_tags, "rows": rows,
            "skipped": skipped, "report_line": line}


def save(card: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(card, indent=1, sort_keys=True), encoding="utf-8")


def run(today: str, write: bool = True, **kw) -> dict:
    card = build(today, **kw)
    if write:
        save(card)
    return card


if __name__ == "__main__":
    print(run(date.today().isoformat(), write=False)["report_line"])
