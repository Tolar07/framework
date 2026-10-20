"""
FIXTURE FEATURES (autonomy plan item 5, 2026-10-20) — what the model and the
shadow strategies can read about a fixture beyond its own goals model:

  xg      each team's recent FotMob xG for / against (data/match_stats/),
          only matches played BEFORE the fixture's date (no look-ahead)
  news    injuries and the lineup (predicted or confirmed) from FotMob,
          captured before kick-off (data/fixture_features.capture_news)
  close   the last price before kick-off, margin removed: Matchbook (sharp)
          and SportyBet (the book the board bets), from data/universe/, and
          the Betfair Exchange close (football-data.co.uk, main leagues)

Pure functions over saved records — no fetch here. Anything without data reads
PENDING (HR35), never 0 and never a guess. Features are studied
(backtest/FEATURES_STUDY.md) and read by shadow strategies; nothing here
selects, stakes or changes a board pick.
"""
from __future__ import annotations

from typing import Any

PENDING = "PENDING"
XG_WINDOW = 5          # last N matches per team
XG_MIN = 2             # fewer prior matches than this -> PENDING


def _avg(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def team_xg(team: str, before: str, rows: list[dict], window: int = XG_WINDOW) -> list[tuple[str, float, float]]:
    """[(date, xg_for, xg_against)] of the team's last `window` matches with
    xG strictly before `before` (YYYY-MM-DD), oldest first. Team names are the
    rated ledger's own spelling, which data/match_stats copies, so equality is
    exact — no fuzzy matching that could put one club's xG on another."""
    out = []
    for r in rows:
        xg = (r.get("stats") or {}).get("xg")
        if not (isinstance(xg, list) and len(xg) == 2) or None in xg or not r.get("date"):
            continue
        if r["date"] >= before:
            continue
        if r.get("home") == team:
            out.append((r["date"], float(xg[0]), float(xg[1])))
        elif r.get("away") == team:
            out.append((r["date"], float(xg[1]), float(xg[0])))
    out.sort()
    return out[-window:]


def xg_form(team: str, before: str, rows: list[dict]) -> dict[str, Any]:
    """{n, xgf, xga, trend}: averages of the last matches; trend is the latest
    two matches' xG difference minus the earlier ones' (needs 4)."""
    m = team_xg(team, before, rows)
    if len(m) < XG_MIN:
        return {"n": len(m), "xgf": PENDING, "xga": PENDING, "trend": PENDING}
    diffs = [f - a for _, f, a in m]
    trend: Any = PENDING
    if len(m) >= 4:
        trend = round(_avg(diffs[-2:]) - _avg(diffs[:-2]), 3)
    return {"n": len(m), "xgf": round(_avg([f for _, f, _ in m]), 3),
            "xga": round(_avg([a for _, _, a in m]), 3), "trend": trend}


def xg_features(home: str, away: str, day: str, rows: list[dict]) -> dict[str, Any]:
    h, a = xg_form(home, day, rows), xg_form(away, day, rows)
    known = PENDING not in (h["xgf"], a["xgf"])
    return {"home": h, "away": a,
            # home's net xG minus away's: positive favours the home side
            "edge": round((h["xgf"] - h["xga"]) - (a["xgf"] - a["xga"]), 3) if known else PENDING,
            # expected goals in this match from both sides' recent attack + defence
            "total": round((h["xgf"] + a["xga"] + a["xgf"] + h["xga"]) / 2, 3) if known else PENDING}


def news_features(snap: dict | None) -> dict[str, Any]:
    """From a capture_news snapshot: lineup type, each side's share of its
    best XI's market value that is unavailable, the top absentees."""
    if not snap:
        return {"lineup": PENDING, "home_missing": PENDING, "away_missing": PENDING,
                "edge": PENDING, "absent": PENDING, "at": PENDING}
    hm, am = snap.get("home_missing_share"), snap.get("away_missing_share")
    return {"lineup": snap.get("lineup_type") or PENDING,
            "home_missing": PENDING if hm is None else hm, "away_missing": PENDING if am is None else am,
            # away weakened minus home weakened: positive favours the home side
            "edge": round(am - hm, 4) if isinstance(hm, (int, float)) and isinstance(am, (int, float))
            else PENDING,
            "absent": snap.get("absent") or PENDING, "at": snap.get("at") or PENDING}


def fair(prices: list | None) -> list[float] | None:
    """Margin removed proportionally; None when any price is missing."""
    if not prices or any(not isinstance(x, (int, float)) or x <= 1 for x in prices):
        return None
    inv = [1 / x for x in prices]
    s = sum(inv)
    return [round(x / s, 4) for x in inv]


def close_features(urow: dict | None, bf_row: dict | None = None) -> dict[str, Any]:
    """Fair chances at the last look before kick-off: sharp (Matchbook) and
    soft (SportyBet) for home/draw/away, over 2.5 and BTTS yes."""
    out: dict[str, Any] = {}
    for name, key in (("sharp", "mb_last"), ("soft", "last")):
        block = (urow or {}).get(key) or {}
        p = block.get("p") or {}
        f12, fou, fbt = fair(p.get("1x2")), fair(p.get("ou2.5")), fair(p.get("btts"))
        out[name] = {"home": f12[0] if f12 else PENDING, "draw": f12[1] if f12 else PENDING,
                     "away": f12[2] if f12 else PENDING,
                     "over25": fou[0] if fou else PENDING, "btts": fbt[0] if fbt else PENDING,
                     "at": block.get("at") or PENDING}
    # Betfair Exchange closing odds (football-data.co.uk BFEC*, main leagues only,
    # published with the results a few days after the match)
    b = bf_row or {}
    f12 = fair([_px(b.get(k)) for k in ("BFECH", "BFECD", "BFECA")]) if b else None
    fou = fair([_px(b.get(k)) for k in ("BFEC>2.5", "BFEC<2.5")]) if b else None
    out["betfair"] = {"home": f12[0] if f12 else PENDING, "draw": f12[1] if f12 else PENDING,
                      "away": f12[2] if f12 else PENDING, "over25": fou[0] if fou else PENDING,
                      "btts": PENDING, "at": "close" if (f12 or fou) else PENDING}
    return out


def _px(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build(fx: dict, day: str, stats_rows: list[dict], news_snap: dict | None,
          urow: dict | None, bf_row: dict | None = None) -> dict[str, Any]:
    """Every feature of one rated fixture (fx: a `rated` row of the ledger)."""
    return {"fixture": f"{fx['home']} v {fx['away']}", "league": fx.get("league") or PENDING,
            "home": fx["home"], "away": fx["away"], "date": day,
            "model_p": fx.get("p") if fx.get("src") == "model" else PENDING,
            "xg": xg_features(fx["home"], fx["away"], day, stats_rows),
            "news": news_features(news_snap),
            "close": close_features(urow, bf_row),
            "ft": fx.get("ft") or PENDING}
