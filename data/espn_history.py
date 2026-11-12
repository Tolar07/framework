"""
ESPN HISTORY - every football match ESPN lists, any competition in the world (leagues, cups, FIFA and continental
tournaments, women's football), kept with the facts a trend needs.

The Architect, 2026-11-12: "look for the trends for every market ... league by league, team by team, year by year
... cover the entire football ... FIFA events, any event. As long as it's football, cover it."

Source: ESPN's public all-competitions scoreboard, one date per request
(site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates=YYYYMMDD, about 200 matches on a Saturday).
Per match it gives the score, every goal and card with its minute, and each side's corners, fouls, shots and
shots on target. Flashscore keeps only 7 days, so this is the framework's worldwide history.

One line per finished match in data/espn_matches/<yyyy-mm>.jsonl:
  {"id", "date" (UTC kick-off), "lid" (ESPN league id: the key), "league" (its name, e.g. "MLS"),
   "phase" (ESPN season slug without the year), "season" (e.g. "2024-25"), "year", "hid", "aid" (ESPN team ids),
   "home", "away", "ft": [h, a],
   "goals": [[minute, side], ...] | null    (null unless the goal minutes add up to the score: HR35),
   "ht": [h, a] | null                       (from the goal minutes: minute <= 45 incl. first-half added time),
   "cards": [[minute, side, "Y"|"R"], ...] | null,
   "corners", "fouls", "shots", "sot": [home, away] | null}
Minutes: "45'+2'" -> 45 (first half), "90'+3'" -> 90; side 0 = home, 1 = away.

RECORD ONLY: nothing here picks, stakes or blocks. engine/trend_atlas.py reads it.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "espn_matches"
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates={d}&limit=1000"
UA = {"User-Agent": "Mozilla/5.0 (OLP XDV research)", "Accept": "application/json"}
STAT = {"wonCorners": "corners", "foulsCommitted": "fouls", "totalShots": "shots", "shotsOnTarget": "sot"}
_MIN = re.compile(r"(\d+)'(?:\+(\d+)')?")


def _minute(txt: str):
    m = _MIN.search(txt or "")
    if not m:
        return None
    return int(m.group(1))


def _league_season(slug: str):
    m = re.match(r"^(\d{4}(?:-\d{2})?)-(.+)$", slug or "")
    return (m.group(2), m.group(1)) if m else (slug or "unknown", "")


def parse_event(e: dict) -> dict | None:
    """One finished match, or None (not finished, missing a side)."""
    st = (e.get("status") or {}).get("type") or {}
    if not st.get("completed") or (st.get("name") or "") not in ("STATUS_FULL_TIME", "STATUS_FINAL"):
        return None   # extra time / penalties / abandoned are left out: every trend here is a 90-minute market
    c = (e.get("competitions") or [{}])[0]
    comp = c.get("competitors") or []
    try:
        h = next(t for t in comp if t.get("homeAway") == "home")
        a = next(t for t in comp if t.get("homeAway") == "away")
        ft = [int(h.get("score")), int(a.get("score"))]
    except (StopIteration, TypeError, ValueError):
        return None
    hid, aid = str((h.get("team") or {}).get("id")), str((a.get("team") or {}).get("id"))
    goals, cards = [], []
    for d in c.get("details") or []:
        mn = _minute((d.get("clock") or {}).get("displayValue", ""))
        tid = str((d.get("team") or {}).get("id"))
        side = 0 if tid == hid else 1 if tid == aid else None
        if mn is None or side is None:
            continue
        if d.get("scoringPlay"):
            goals.append([mn, side])
        elif d.get("redCard"):
            cards.append([mn, side, "R"])
        elif d.get("yellowCard"):
            cards.append([mn, side, "Y"])
    gl = goals if [sum(1 for g in goals if g[1] == 0), sum(1 for g in goals if g[1] == 1)] == ft else None
    ht = [sum(1 for g in gl if g[1] == s and g[0] <= 45) for s in (0, 1)] if gl is not None else None
    stats = {}
    for key in STAT.values():
        stats[key] = None
    for k, key in STAT.items():
        vals = []
        for t in (h, a):
            v = next((s.get("displayValue") for s in t.get("statistics") or [] if s.get("name") == k), None)
            try:
                vals.append(int(float(v)))
            except (TypeError, ValueError):
                vals.append(None)
        stats[key] = vals if None not in vals else None
    has_events = bool(c.get("details"))
    league, season = _league_season((e.get("season") or {}).get("slug", ""))
    m_lid = re.search(r"~l:(\d+)", e.get("uid") or "")
    lname = (c.get("altGameNote") or "").strip()
    if not lname or lname.lower() in ("regular season", "apertura", "clausura"):
        lname = league
    return {"id": e.get("id"), "date": (e.get("date") or "")[:16] + "Z" if e.get("date") else "",
            "lid": m_lid.group(1) if m_lid else None, "league": lname, "phase": league,
            "season": season, "year": (e.get("season") or {}).get("year"), "hid": hid, "aid": aid,
            "home": (h.get("team") or {}).get("displayName"),
            "away": (a.get("team") or {}).get("displayName"), "ft": ft, "goals": gl, "ht": ht,
            "cards": cards if has_events else None, **stats}


def _get(url: str) -> dict:
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)  # noqa: S310 (fixed https URL)
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 - retry, then report
            time.sleep(3 * (i + 1))
    raise RuntimeError("ESPN unavailable")


def day(d: date, get=None) -> list[dict]:
    blob = (get or _get)(URL.format(d=d.strftime("%Y%m%d")))
    return [m for m in (parse_event(e) for e in blob.get("events") or []) if m]


def _done_file(folder: Path) -> Path:
    return folder / "days_read.json"


def run(start: date, end: date, folder: Path = DIR, get=None, max_days: int | None = None, pause: float = 0.3) -> str:
    """Read every date from start to end not read before (days_read.json); a date within 2 days of today is
    read again next time (late results). Appends to the month files, one line per new match id."""
    folder.mkdir(parents=True, exist_ok=True)
    df = _done_file(folder)
    done = set(json.loads(df.read_text(encoding="utf-8"))) if df.exists() else set()
    today = datetime.now(UTC).date()
    seen: dict[str, set] = {}
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [d for d in days if d.isoformat() not in done][: max_days or None]
    n_new = n_days = failed = 0
    for d in todo:
        try:
            ms = day(d, get)
        except Exception:  # noqa: BLE001 - read next run
            failed += 1
            continue
        for m in ms:
            mk = (m["date"] or d.isoformat())[:7]
            p = folder / f"{mk}.jsonl"
            if mk not in seen:
                seen[mk] = {json.loads(x)["id"] for x in p.read_text(encoding="utf-8").splitlines()} if p.exists() else set()
            if m["id"] in seen[mk]:
                continue
            seen[mk].add(m["id"])
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(m, ensure_ascii=False, separators=(",", ":")) + "\n")
            n_new += 1
        n_days += 1
        if (today - d).days > 2:
            done.add(d.isoformat())
        if get is None:
            time.sleep(pause)
        if n_days % 25 == 0:
            df.write_text(json.dumps(sorted(done)), encoding="utf-8")
    df.write_text(json.dumps(sorted(done)), encoding="utf-8")
    left = sum(1 for d in days if d.isoformat() not in done)
    return f"espn history: {n_days} dates read, {n_new} new matches, {failed} failed, {left} dates still to read"


def load(folder: Path = DIR) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-07-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--dir", default=str(DIR))
    a = ap.parse_args()
    end = date.fromisoformat(a.end) if a.end else datetime.now(UTC).date()
    print(run(date.fromisoformat(a.start), end, Path(a.dir), max_days=a.max_days))
