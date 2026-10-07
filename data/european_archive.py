"""
EUROPEAN RESULTS ARCHIVE (2026-10-05).

The European club competitions are priced market-implied because the engine
has no current-season results for them: the cross-league model's history
source (API-Football, free plan) can't see this season, and Flashscore's feed
keeps only 7 days. Every daily run therefore archives the men's Champions
League, Europa League and Conference League results Flashscore shows into
data/european/results.json (committed by daily.yml), so this season's results
accumulate for a current-season European model. Nothing reads it for picks
yet; it is the history that model needs.

DOMESTIC CUPS (2026-10-07, Architect: "study each of the fixtures, study the
outcome and use it for training the model"): the same feed's Turkish Cup
results — every round, qualification included — go to data/cups/results.json
with each club's division as this week's league results show it (None when the
club is in no Turkish league table that week: usually an amateur side).
SportyBet does not offer most early rounds, and nothing prices the cup yet;
backtest/cup_study.py turns the archive into backtest/TURKISH_CUP_STUDY.md.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PATH = Path(__file__).parent / "european" / "results.json"
COMPETITIONS = ("EUROPE: UEFA Champions League", "EUROPE: UEFA Europa League",
                "EUROPE: UEFA Conference League")
_EXCLUDE = ("Women", "Youth", "U19", "Qualification")


def is_european_club(league: str) -> bool:
    return (league.startswith(COMPETITIONS)
            and not any(x in league for x in _EXCLUDE))


CUP_PATH = Path(__file__).parent / "cups" / "results.json"
CUPS = ("TURKEY: Turkish Cup",)
_TIERS = (("TURKEY: Super Lig", 1), ("TURKEY: 1. Lig", 2), ("TURKEY: 2. Lig", 3), ("TURKEY: 3. Lig", 4))


def is_domestic_cup(league: str) -> bool:
    return league.startswith(CUPS) and not any(x in league for x in ("Women", "Youth", "U19"))


def tiers(events: list[dict]) -> dict[str, int]:
    """{club: division} from the league results in the same feed (1 = Super Lig)."""
    out: dict[str, int] = {}
    for e in events:
        for tag, t in _TIERS:
            if (e.get("league") or "").startswith(tag):
                out[e.get("home", "")] = out[e.get("away", "")] = t
    return out


def archive_cups(events: list[dict], path: Path | None = None) -> int:
    """Add finished domestic-cup results (with both clubs' divisions) to the cup
    archive. A tie level after 90 minutes is kept with went_to_et = True: its
    score includes extra time, so it is never read as a 90-minute score."""
    path = path or CUP_PATH
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    seen = {(r["date"], r["home"], r["away"]) for r in old}
    div = tiers(events)
    new = []
    for e in events:
        if not is_domestic_cup(e.get("league", "")):
            continue
        if not (e.get("finished_regular") or e.get("finished_other")):
            continue
        if e.get("fthg") is None or e.get("ftag") is None:
            continue
        key = ((e.get("kickoff_utc") or "")[:10], e.get("home", ""), e.get("away", ""))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        new.append({"date": key[0], "competition": e["league"], "home": key[1], "away": key[2],
                    "home_tier": div.get(key[1]), "away_tier": div.get(key[2]),
                    "fthg": e["fthg"], "ftag": e["ftag"],
                    "fh_home": e.get("fh_home"), "fh_away": e.get("fh_away"),
                    "went_to_et": bool(e.get("finished_other"))})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(old + new, key=lambda r: (r["date"], r["home"]))
        path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return len(new)


def archive(events: list[dict], path: Optional[Path] = None) -> int:
    """Add finished European club results to the archive. Returns how many
    were new. Only finished matches with a full-time score are kept."""
    path = path or PATH      # read at call time: a dry run points PATH at a scratch copy
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    seen = {(r["date"], r["home"], r["away"]) for r in old}
    new = []
    for e in events:
        if not is_european_club(e.get("league", "")):
            continue
        if not (e.get("finished_regular") or e.get("finished_other")):
            continue
        if e.get("fthg") is None or e.get("ftag") is None:
            continue
        key = ((e.get("kickoff_utc") or "")[:10], e.get("home", ""), e.get("away", ""))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        new.append({"date": key[0], "competition": e["league"], "home": key[1],
                    "away": key[2], "fthg": e["fthg"], "ftag": e["ftag"],
                    "fh_home": e.get("fh_home"), "fh_away": e.get("fh_away"),
                    "after_90": bool(e.get("finished_other"))})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(old + new, key=lambda r: (r["date"], r["home"]))
        path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return len(new)
