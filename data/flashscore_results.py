"""
Flashscore.co.uk results — the grading source for EVERY league on the board.

football-data.co.uk (the model's history feed) has no FA Cup, no Nations
League and updates days late, so legs sat PENDING forever ("graded 0 of 24").
Flashscore (the Architect's chosen live source) publishes every finished
match the same day.

Only matches finished in REGULAR TIME (stage code 3) are graded: bets settle
on the 90-minute score, and a match decided after extra time or penalties
has no reliable 90-minute score in this feed, so it is flagged, never guessed
(HR35 / ID48).
"""
from __future__ import annotations

import difflib
import json
import re
import time
import unicodedata
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_PAGE = "https://www.flashscore.co.uk/football/europe/uefa-nations-league/"
_FEED = "https://local-global.flashscore.ninja/2/x/feed/f_1_{offset}_1_en-uk_1"
_CACHE = Path(__file__).parent / "cache" / "flashscore"
_FALLBACK_SIGN = "SW9D1eZo"
FINISHED_REGULAR = "3"          # AC stage code: finished in 90 minutes


def _get(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **headers})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def feed_sign() -> str:
    """The feed's access header, read from a Flashscore page (it can rotate)."""
    try:
        m = re.search(r'feed_sign":"([^"]+)', _get(_PAGE, {}))
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001 — fall back to the last known sign
        pass
    return _FALLBACK_SIGN


def parse_feed(text: str) -> list[dict]:
    """Every event in a Flashscore day feed:
    {league, home, away, fthg, ftag, finished_regular, stage, kickoff_utc}."""
    out, league = [], None
    for block in text.split("~"):
        kv = {}
        for f in block.split("¬"):
            if "÷" in f:
                k, v = f.split("÷", 1)
                kv.setdefault(k, v)
        if "ZA" in kv:
            league = kv["ZA"]
            continue
        if "AA" not in kv:
            continue
        try:
            ko = datetime.fromtimestamp(int(kv.get("AD", "0")), tz=timezone.utc)
        except (ValueError, OverflowError):
            continue
        finished = kv.get("AB") == "3"
        try:
            hg, ag = int(kv["AG"]), int(kv["AH"])
        except (KeyError, ValueError):
            hg = ag = None
        out.append({
            "league": league or "",
            "home": kv.get("AE", ""), "away": kv.get("AF", ""),
            "fthg": hg, "ftag": ag,
            "finished_regular": finished and kv.get("AC") == FINISHED_REGULAR and hg is not None,
            # first half = full time - second half (BC/BD are the SECOND-half
            # goals; checked on 37 of 37 matches against football-data's
            # half-time scores, 2026-10-05). None when the feed omits them.
            "fh_home": _first_half(hg, kv.get("BC")),
            "fh_away": _first_half(ag, kv.get("BD")),
            "finished_other": finished and kv.get("AC") != FINISHED_REGULAR,
            "stage": kv.get("AC"),
            "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return out


def _first_half(ft: Optional[int], second: Optional[str]) -> Optional[int]:
    try:
        s = int(second) if second is not None else None
    except ValueError:
        return None
    if ft is None or s is None or s > ft or s < 0:
        return None
    return ft - s


def results_for_offset(offset: int, sign: Optional[str] = None) -> list[dict]:
    """Events for a day relative to today (0 = today, -1 = yesterday, ...).
    Past days are cached once fully settled."""
    day = date.fromordinal(date.today().toordinal() + offset).isoformat()
    cache = _CACHE / f"{day}.json"
    if offset < -1 and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    text = _get(_FEED.format(offset=offset),
                {"x-fsign": sign or feed_sign(), "Referer": "https://www.flashscore.co.uk/"})
    events = parse_feed(text)
    if offset < 0:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(events), encoding="utf-8")
    return events


def results_since(days_back: int = 7) -> list[dict]:
    """Every event from `days_back` days ago up to today (Flashscore keeps 7)."""
    sign = feed_sign()
    out = []
    for off in range(-min(days_back, 7), 1):
        try:
            out += results_for_offset(off, sign)
        except Exception:  # noqa: BLE001 — a missing day stays ungraded
            continue
        time.sleep(0.3)
    return out


# --------------------------------------------------------------------------
# Matching our fixture names to Flashscore's
# --------------------------------------------------------------------------
_DROP = re.compile(r"\b(fc|afc|cf|sc|ac|cd|ud|rc|sd|fk|football club|town fc)\b")
# Abbreviations used by football-data / SportyBet, expanded to full words.
_SYN = [(r"\bczechia\b", "czech republic"), (r"\bturkiye\b", "turkey"),
        (r"\bman\b", "manchester"), (r"\bnott m\b", "nottingham"),
        (r"\bsp\b", "sporting"), (r"\bath\b", "atletico"), (r"\batl\b", "atletico"),
        (r"\bweds\b", "wednesday"), (r"\bwed\b", "wednesday"), (r"\brvs\b", "rovers"),
        (r"\bcelta b\b", "celta vigo b"), (r"\bpeterboro\b", "peterborough"),
        (r"\bpa\b", "park avenue"), (r"^wolves$", "wolverhampton wanderers"),
        (r"^spurs$", "tottenham")]


def norm(name: str) -> str:
    # Strip accents first ('Cádiz' -> 'cadiz', 'Leganés' -> 'leganes').
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    n = n.lower().replace("&", " and ").replace("utd", "united")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = _DROP.sub(" ", n)
    n = re.sub(r"\s+", " ", n).strip()
    for pat, rep in _SYN:
        n = re.sub(pat, rep, n)
    return n


def _sim(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # One name fully inside the other ("Wigan" / "Wigan Athletic").
    if a in b or b in a:
        return 0.92
    return difflib.SequenceMatcher(None, a, b).ratio()


MATCH_MIN = 0.85     # 'Man City' vs 'Manchester Utd' scores 0.81 — kept out


def find_result(events: list[dict], home: str, away: str,
                match_date: str) -> Optional[dict]:
    """The finished event for `home v away` kicking off on `match_date`
    (UTC date, +-1 day for timezone edges), or None. Both team names must
    match strongly and the best match must be unambiguous — a loose match
    would settle a bet on the wrong game (ID48)."""
    try:
        d0 = date.fromisoformat(match_date[:10])
    except ValueError:
        return None
    scored = []
    for ev in events:
        try:
            d = date.fromisoformat(ev["kickoff_utc"][:10])
        except ValueError:
            continue
        if abs((d - d0).days) > 1:
            continue
        s = min(_sim(home, ev["home"]), _sim(away, ev["away"]))
        if s >= MATCH_MIN:
            scored.append((s, ev))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    if len(scored) > 1 and scored[1][0] >= scored[0][0] - 0.02:
        return None                      # ambiguous — never guess
    return scored[0][1]
