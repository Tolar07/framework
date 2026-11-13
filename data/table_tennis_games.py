"""
Table tennis points by game, from the SCORE Sports Data Repository's Setka Cup file (data.scorenetwork.org, free, no key),
framework #594. RECORD ONLY: feeds engine/table_tennis_events.py and backtest/table_tennis_events_study.py.

One row per finished best-of-5 match: {"day","home","away","hs","as","sets":[[h,a], ...]}; hs/as = games won,
sets = points in each game, in order (Player1 is "home"). A match with a missing (NA) game, a game count that differs
from hs + as, or game winners that disagree with hs / as is skipped, PENDING - never a guessed zero (HR35).
Setka Cup is a league the board leaves out for integrity (order 50): this is accuracy evidence only.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from datetime import datetime
from pathlib import Path

URL = "https://data.scorenetwork.org/data/table_tennis-sept2022.csv"
CACHE = Path(__file__).parent / "cache" / "table_tennis_games.csv"
_UA = {"User-Agent": "OLP-XDV-research/1.0 (record-only study; github.com/Tolar07/framework)"}


def parse_row(r: dict) -> dict | None:
    """One CSV row to a match, or None (PENDING) unless it is a consistent finished best-of-5."""
    try:
        day = datetime.strptime(r["Date"], "%m/%d/%Y").date().isoformat()
        hs, as_ = int(r["Sets_P1"]), int(r["Sets_P2"])
        n = hs + as_
        sets = [[int(r[f"P1_G{i}"]), int(r[f"P2_G{i}"])] for i in range(1, n + 1)]
    except (KeyError, ValueError, TypeError):
        return None                                   # NA or missing game points
    home, away = (r.get("Player1") or "").strip(), (r.get("Player2") or "").strip()
    if not home or not away or home == away or max(hs, as_) != 3 or min(hs, as_) > 2:
        return None
    if any(p == q for p, q in sets) or sum(p > q for p, q in sets) != hs:
        return None                                   # a drawn game, or winners that do not match the games won
    for i in range(n + 1, 6):                         # games after the end must be empty
        if (r.get(f"P1_G{i}") or "NA") != "NA":
            return None
    return {"day": day, "home": home, "away": away, "hs": hs, "as": as_, "sets": sets, "t": r.get("Time", ""), "x": r.get("X", "")}


def parse(text: str) -> list[dict]:
    rows = [m for m in (parse_row(r) for r in csv.DictReader(io.StringIO(text))) if m]
    rows.sort(key=lambda m: (m["day"], m["t"], int(m["x"]) if str(m["x"]).isdigit() else 0))
    return rows


def load(get=None) -> list[dict]:
    """Every parsed match. A failed fetch falls back to the cached file; no file either gives [] (PENDING)."""
    try:
        if get is None:
            req = urllib.request.Request(URL, headers=_UA)  # noqa: S310 - fixed https URL
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                text = resp.read().decode("utf-8", "replace")
        else:
            text = get()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(text, encoding="utf-8")
    except Exception as ex:  # noqa: BLE001
        print(f"table tennis games not fetched ({type(ex).__name__})")
        text = CACHE.read_text(encoding="utf-8") if CACHE.exists() else ""
    return parse(text)
