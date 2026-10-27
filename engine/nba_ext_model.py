"""
NBA EXTERNAL MODEL — SHADOW ONLY (sketch; not an Architect order yet).

Reads the cover predictions of the external NBA_Betting project
(external/nba-patterns/NBA_Betting: AutoGluon, ~761 team-stat features,
"does the home team cover the OPENING spread?") and writes them NEXT TO the
order-41 paper picks, so the graded record can later answer one question:
when that model agreed with a price-edge pick, did the pick do better?

It never chooses, drops or reorders a pick. backtest/NBA_STUDY.md found the
closing line sharper than any rating model (best model weight 0), so a model
may only become a filter once the graded regular-season record shows it adds
something — and that is the Architect's call, not this file's.

Source: NBA_Betting's SQLite (`predictions` ⨝ `games`), opened READ-ONLY.
  games.open_line    the home handicap of the opening line (home covers when
                     home_score + open_line > away_score — the same rule as
                     nba_value.settle for market 223)
  home_cover_prob    the model's chance the home side covers open_line
  model_variant      "standard" (no line as a feature) / "vegas" (with it)
  game_id            "YYYYMMDD0HOM" — the US game date + home abbreviation

The model only speaks to the OPENING spread. Its view is marked `applies`
only for a handicap pick (223) whose SportyBet line is within LINE_TOL points
of that opening line; anything else is recorded for context, never compared.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

LINE_TOL = 1.0

_QUERY = """
    SELECT p.game_id, p.model_variant, p.predicted_at, p.home_cover_prob,
           p.predicted_margin, g.home_team, g.away_team, g.open_line
    FROM predictions AS p
    JOIN games AS g ON g.game_id = p.game_id
    WHERE substr(p.game_id, 1, 8) BETWEEN :lo AND :hi
"""


def load(db_path: str | Path, days: list[date]) -> list[dict]:
    """Every external prediction for games on `days` (±1 day for US vs UTC dates).
    A missing or unreadable database gives [] — the board never depends on it."""
    path = Path(db_path)
    if not days or not path.exists():
        return []
    lo = (min(days) - timedelta(days=1)).strftime("%Y%m%d")
    hi = (max(days) + timedelta(days=1)).strftime("%Y%m%d")
    try:
        con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute(_QUERY, {"lo": lo, "hi": hi})]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def match(rows: list[dict], home_key: str, away_key: str, tip_date: date) -> dict[str, dict]:
    """{variant: row} for one game by NBA team code (engine/nba_teams key — the
    same codes NBA_Betting stores), its US date within a day of tip."""
    out: dict[str, dict] = {}
    for r in rows:
        if r.get("home_team") != home_key or r.get("away_team") != away_key:
            continue
        try:
            d = date(int(r["game_id"][:4]), int(r["game_id"][4:6]), int(r["game_id"][6:8]))
        except (TypeError, ValueError):
            continue
        if abs((d - tip_date).days) <= 1:
            out[r["model_variant"]] = r
    return out


def view(pick: dict, by_variant: dict[str, dict]) -> dict | None:
    """The shadow record stored on a paper pick, or None when no prediction matched."""
    if not by_variant:
        return None
    side = (pick.get("outcome") or "").split(" ")[0]          # "Home" / "Away" / "Over" ...
    hcp = None
    if pick.get("market_id") == "223":
        spec = pick.get("specifier") or ""
        try:
            hcp = float(spec.split("hcp=")[1].split("&")[0]) if "hcp=" in spec else None
        except ValueError:
            hcp = None
    out = {}
    for variant, r in sorted(by_variant.items()):
        p_home, line = r.get("home_cover_prob"), r.get("open_line")
        applies = (hcp is not None and line is not None and p_home is not None
                   and side in ("Home", "Away") and abs(hcp - line) <= LINE_TOL)
        rec = {"home_cover_prob": p_home, "open_line": line,
               "predicted_margin": r.get("predicted_margin"),
               "predicted_at": r.get("predicted_at"), "applies": applies}
        if applies and p_home is not None:
            p_side = float(p_home) if side == "Home" else 1 - float(p_home)
            rec["side_prob"] = round(p_side, 4)
            rec["agrees"] = p_side > 0.5
        out[variant] = rec
    return out


def shadow_record(picks: list[dict]) -> str:
    """Graded regular-season handicap picks, split by whether the external model agreed."""
    buckets: dict[str, list[dict]] = {"agreed": [], "disagreed": []}
    for p in picks:
        ext = (p.get("ext_model") or {}).get("vegas") or (p.get("ext_model") or {}).get("standard")
        if (p.get("stage") != "regular" or p.get("result") not in ("won", "lost")
                or not ext or not ext.get("applies")):
            continue
        buckets["agreed" if ext["agrees"] else "disagreed"].append(p)
    parts = []
    for k, rows in buckets.items():
        if not rows:
            parts.append(f"{k}: none")
            continue
        w = sum(p["result"] == "won" for p in rows)
        ret = sum(p["price"] for p in rows if p["result"] == "won") - len(rows)
        parts.append(f"{k}: {len(rows)} · won {w} · £1 each {ret:+.2f}")
    return "External model (shadow) on handicap picks — " + " | ".join(parts)
