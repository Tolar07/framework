"""
Cricket first innings by over block from Cricsheet ball-by-ball (cricsheet.org, free open data), framework #589.
RECORD ONLY: feeds engine/cricket_events.py and backtest/cricket_events_study.py; nothing here picks or stakes.
Licence: Cricsheet data is CC BY 4.0 (credit Cricsheet); nothing from it is stored in this repo, it is read on the fly.

One row per men's international match whose FIRST innings ran its course (all out, or every over bowled):
  {"id","date","fmt","venue","bat","bowl","blocks":[runs x 3],"wk"}
T20 blocks = overs 1-6 (powerplay), 7-15, 16-20; ODI blocks = overs 1-10, 11-40, 41-50. wk = wickets lost.
Only the first innings is used: a chase stops when the target is reached, so its totals are not a free sample.
A shortened, abandoned or malformed innings is skipped, PENDING - never a guessed zero (HR35).
"""
from __future__ import annotations

import json
import zipfile
from io import BytesIO

FORMATS = {"t20s_male": ("T20", 20, (6, 15)), "odis_male": ("ODI", 50, (10, 40))}   # key -> (name, overs, block ends)


def parse_match(d: dict, fmt: str, overs: int, cuts: tuple[int, int], mid: str = "") -> dict | None:
    """First-innings runs by over block. None (PENDING) unless the first innings ran its course."""
    try:
        info = d["info"]
        venue, teams = info.get("venue"), info["teams"]
        inn = d["innings"][0]
        bat = inn["team"]
        if not venue or len(teams) != 2 or bat not in teams or int(info.get("overs", overs)) != overs:
            return None
        bowl = teams[1] if teams[0] == bat else teams[0]
        blocks = [0, 0, 0]
        wk = balls = 0
        for ov in inn["overs"]:
            n = int(ov["over"])
            b = 0 if n < cuts[0] else 1 if n < cuts[1] else 2
            for dl in ov["deliveries"]:
                blocks[b] += int(dl["runs"]["total"])
                ex = dl.get("extras") or {}
                if "wides" not in ex and "noballs" not in ex:
                    balls += 1
                wk += len(dl.get("wickets") or [])
        if wk < 10 and balls < overs * 6:
            return None                          # shortened / abandoned: skipped, not guessed
        return {"id": mid, "date": info["dates"][0], "fmt": fmt, "venue": venue, "bat": bat, "bowl": bowl,
                "blocks": blocks, "wk": wk}
    except (KeyError, TypeError, IndexError, ValueError):
        return None


def rows_from_zip(raw: bytes, fmt: str, overs: int, cuts: tuple[int, int]) -> list[dict]:
    z = zipfile.ZipFile(BytesIO(raw))
    out = []
    for name in z.namelist():
        if name.endswith(".json"):
            try:
                r = parse_match(json.loads(z.read(name)), fmt, overs, cuts, name)
            except ValueError:
                continue
            if r:
                out.append(r)
    return out


def load(fetch=None) -> list[dict]:
    """All rows, both formats, date order. A format that will not load is PENDING (printed), never invented."""
    if fetch is None:
        from backtest.cricket_backtest import fetch_zip as fetch
    rows: list[dict] = []
    for key, (fmt, overs, cuts) in FORMATS.items():
        try:
            rows += rows_from_zip(fetch(key), fmt, overs, cuts)
        except Exception as ex:  # noqa: BLE001
            print(f"{fmt}: not loaded ({type(ex).__name__})")
    rows.sort(key=lambda r: (r["date"], r["id"]))
    return rows
