"""
WORLD FACTS - every finished football match Flashscore lists, kept so the framework has its own statistics.

The Architect, 2026-11-12, on five stats videos (league both-teams-to-score rankings, first-half goals, corner
consistency, a first-half goal filter, lower-league value): "Stats are key. Statistics are very, very important ...
look for where you can get all the statistics ... these are part of the things I want the framework to
autonomously do." The source check of that day (docs/obsidian-vault/Stats-Sources.md, config/stat_sources.json)
found that the day feed the framework already reads for grading carries the half-time score of nearly every
match in the world (1,361 of 1,396 matches in 387 competitions on one Sunday), and that a match's own feeds
give about 40 team stats for the match and each half (corners, shots, expected goals, cards) and the minute of
every goal for roughly half of them (top flights and most second tiers).

Two archives, appended once per match, never rewritten:
  data/world_facts/<month>.jsonl         one line per match finished in regular time:
      {"id", "ko", "league", "home", "away", "ft": [h, a], "ht": [h, a] | null}
  data/world_facts_detail/<month>.jsonl  one line per match whose detail feeds were read:
      {"id", "ko", "league", "home", "away", "ft", "goals": [[minute, added, side], ...] | null,
       "stats": {"match": {stat: [home, away]}, "h1": {...}, "h2": {...}} | null}
      goals is null unless the goal minutes add up to the full-time score (HR35: never a part list);
      stats is null when Flashscore lists none for the match.

RECORD ONLY. Nothing here picks, stakes, prices or blocks anything. League profiles, first-half models and corner
tables are built FROM these files by their own modules, each proved by walk-forward before anything uses it.
A run is one polite pass (DETAIL_PER_RUN matches), not a crawl: a day's matches are finished over several runs.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "world_facts"
DETAIL_DIR = ROOT / "data" / "world_facts_detail"
OUT = ROOT / "output" / "world_facts" / "latest.json"
UTC = timezone.utc
DAYS_BACK = (-1, -2, -3)        # the day feeds read each run (today's games are not all finished)
DETAIL_PER_RUN = 150            # matches whose two detail feeds are read in one run
PAUSE = 0.2
_FEED = "https://local-global.flashscore.ninja/2/x/feed/"
# the team stats kept from the STATS tab (Flashscore's own names, lower case) -> short key
KEEP = {"expected goals (xg)": "xg", "ball possession": "poss", "total shots": "shots", "shots on target": "sot",
        "big chances": "big", "corner kicks": "corners", "yellow cards": "yellow", "red cards": "red",
        "fouls": "fouls", "offsides": "offsides", "shots inside the box": "box_shots",
        "touches in opposition box": "box_touches", "goalkeeper saves": "saves", "free kicks": "free_kicks",
        "throw ins": "throws"}
PERIOD = {"match": "match", "1st half": "h1", "2nd half": "h2"}


# ---------------------------------------------------------------- parsing (pure)

def _blocks(text: str):
    for block in text.split("~"):
        kv = {}
        for f in block.split("¬"):
            if "÷" in f:
                k, v = f.split("÷", 1)
                kv.setdefault(k, v)
        if kv:
            yield kv


def parse_day(text: str) -> list[dict]:
    """Every football match of a day feed that finished in regular time, with its half-time score where the
    feed has one. Uses the grading source's own rules (data/flashscore_results.py) for the 90-minute and
    first-half scores, so this archive and the grades agree."""
    from data import flashscore_results as fr
    out, league = [], ""
    for kv in _blocks(text):
        if "ZA" in kv:
            league = kv["ZA"]
            continue
        if "AA" not in kv or kv.get("AB") != "3" or kv.get("AC") != fr.FINISHED_REGULAR:
            continue
        try:
            hg, ag = int(kv["AG"]), int(kv["AH"])
            ko = datetime.fromtimestamp(int(kv.get("AD", "0")), tz=UTC)
        except (KeyError, ValueError, OverflowError):
            continue
        fh, fa = fr._first_half(hg, kv.get("BC")), fr._first_half(ag, kv.get("BD"))
        out.append({"id": kv["AA"], "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "league": league,
                    "home": kv.get("AE", ""), "away": kv.get("AF", ""), "ft": [hg, ag],
                    "ht": [fh, fa] if fh is not None and fa is not None else None})
    return out


def _minute(raw: str) -> tuple[int, int] | None:
    m = re.match(r"\s*(\d+)(?:\+(\d+))?", raw or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def parse_goals(text: str, ft: list[int]) -> list[list] | None:
    """[[minute, added time, 'h' | 'a'], ...] from the incidents feed, in order. A goal is a change in the
    running score the feed prints on scoring incidents (INX-IOX), so own goals and penalties need no special
    case. None unless the goals found add up to the full-time score."""
    goals, score = [], [0, 0]
    for block in text.split("~"):
        fields = [f.split("÷", 1) for f in block.split("¬") if "÷" in f]
        keys = dict((k, v) for k, v in fields)
        if "INX" not in keys or "IOX" not in keys or "IB" not in keys:
            continue
        try:
            now = [int(keys["INX"]), int(keys["IOX"])]
        except ValueError:
            continue
        when = _minute(keys["IB"])
        if when is None:
            continue
        for side, idx in (("h", 0), ("a", 1)):
            for _ in range(max(0, now[idx] - score[idx])):
                goals.append([when[0], when[1], side])
        score = [max(score[0], now[0]), max(score[1], now[1])]
    if [sum(1 for g in goals if g[2] == "h"), sum(1 for g in goals if g[2] == "a")] != list(ft):
        return None
    return goals


def _num(value: str) -> float | None:
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value or ""))
    return float(m.group(1)) if m else None


def parse_stats(text: str) -> dict | None:
    """{"match": {key: [home, away]}, "h1": {...}, "h2": {...}} for the stats in KEEP; None when the tab is empty.
    A stat listed twice in a period (the Top stats group repeats some) is taken once."""
    out: dict[str, dict] = {}
    period = None
    for kv in _blocks(text):
        if "SE" in kv:
            period = PERIOD.get(kv["SE"].strip().lower())
        name = (kv.get("SG") or "").strip().lower()
        if period is None or name not in KEEP:
            continue
        h, a = _num(kv.get("SH")), _num(kv.get("SI"))
        if h is None or a is None:
            continue
        out.setdefault(period, {}).setdefault(KEEP[name], [h, a])
    return out or None


# ---------------------------------------------------------------- the archive

def _month_file(folder: Path, ko: str) -> Path:
    return folder / f"{ko[:7]}.jsonl"


def known_ids(folder: Path, months: set[str]) -> set[str]:
    seen = set()
    for m in months:
        p = folder / f"{m}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    return seen


def append(folder: Path, rows: list[dict]) -> int:
    for r in rows:
        p = _month_file(folder, r["ko"])
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(rows)


def detail_row(match: dict, stats_text: str, incidents_text: str) -> dict:
    return {**{k: match[k] for k in ("id", "ko", "league", "home", "away", "ft")},
            "goals": parse_goals(incidents_text, match["ft"]), "stats": parse_stats(stats_text)}


def summary(base: list[dict], detail: list[dict], now: datetime) -> dict:
    """What the archive holds, for the Control Room and the stats desk (counts only: not a league table yet)."""
    leagues = {r["league"] for r in base}
    return {"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "matches": len(base),
            "with_half_time": sum(1 for r in base if r.get("ht")), "competitions": len(leagues),
            "detail_read": len(detail), "with_stats": sum(1 for r in detail if r.get("stats")),
            "with_corners": sum(1 for r in detail if "corners" in ((r.get("stats") or {}).get("match") or {})),
            "with_goal_minutes": sum(1 for r in detail if r.get("goals") is not None),
            "note": "Football world facts, record only. Counts for the months touched by this run."}


def run(now: datetime | None = None, root: Path = ROOT, get=None, days=DAYS_BACK, detail_per_run: int = DETAIL_PER_RUN) -> str:
    """Read the last days' feeds, archive every new finished match, then the detail feeds of up to
    `detail_per_run` matches not read yet (newest day first). One line saying what was done."""
    from data import flashscore_results as fr
    now = now or datetime.now(UTC)
    sign = None

    def _get(path: str) -> str:
        nonlocal sign
        if get is not None:
            return get(path)
        sign = sign or fr.feed_sign()
        time.sleep(PAUSE)
        return fr._get(_FEED + path, {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})

    base_dir, detail_dir = root / "data" / "world_facts", root / "data" / "world_facts_detail"
    matches, unread_days = [], 0
    for off in days:
        try:
            matches += parse_day(_get(f"f_1_{off}_1_en-uk_1"))
        except Exception:  # noqa: BLE001 - a silent day feed: its matches are read on a later run
            unread_days += 1
    matches = list({m["id"]: m for m in matches}.values())
    months = {m["ko"][:7] for m in matches}
    have = known_ids(base_dir, months)
    new = [m for m in matches if m["id"] not in have]
    append(base_dir, new)
    read = known_ids(detail_dir, months)
    todo = sorted((m for m in matches if m["id"] not in read), key=lambda m: m["ko"], reverse=True)[:detail_per_run]
    rows, failed = [], 0
    for m in todo:
        try:
            rows.append(detail_row(m, _get("df_st_1_" + m["id"]), _get("df_sui_1_" + m["id"])))
        except Exception:  # noqa: BLE001 - not marked as read: tried again next run
            failed += 1
    append(detail_dir, rows)
    all_base = [json.loads(x) for mth in months for x in ((base_dir / f"{mth}.jsonl").read_text(encoding="utf-8").splitlines()
                                                        if (base_dir / f"{mth}.jsonl").exists() else [])]
    all_detail = [json.loads(x) for mth in months for x in ((detail_dir / f"{mth}.jsonl").read_text(encoding="utf-8").splitlines()
                                                          if (detail_dir / f"{mth}.jsonl").exists() else [])]
    out = root / "output" / "world_facts" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = summary(all_base, all_detail, now)
    out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    left = sum(1 for m in matches if m["id"] not in read) - len(rows)
    return (f"world facts: {len(matches)} finished matches in the feeds, {len(new)} new archived "
            f"({sum(1 for m in new if m['ht'])} with half-time); detail read for {len(rows)} "
            f"({sum(1 for r in rows if r['stats'])} with stats, {sum(1 for r in rows if r['goals'] is not None)} "
            f"with goal minutes), {left} still to read"
            + (f", {failed} failed" if failed else "") + (f", {unread_days} day feed(s) unread" if unread_days else ""))
