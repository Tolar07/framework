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
# AC stage codes: 10 = after extra time, 11 = after penalties; 4 = postponed,
# 5 = cancelled (both with no score). Read from the feed 1-8 Nov 2026.
EXTRA_TIME = ("10", "11")
POSTPONED = ("4", "5")


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


def parse_feed(text: str, sport: int = 1) -> list[dict]:
    """Every event in a Flashscore day feed:
    {league, home, away, fthg, ftag, finished_regular, stage, kickoff_utc}; basketball
    (sport 3) also h1_home / h1_away, the 1st-half points."""
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
        stage = kv.get("AC")
        h90, a90 = _ninety(stage, hg, ag, kv.get("AT"), kv.get("AU"))
        ev = {
            "league": league or "",
            "home": kv.get("AE", ""), "away": kv.get("AF", ""),
            "fthg": hg, "ftag": ag,
            "finished_regular": finished and stage == FINISHED_REGULAR and hg is not None,
            # first half = 90-minute score - second half (BC/BD are the SECOND-half
            # goals; checked on 37 of 37 matches against football-data's
            # half-time scores, 2026-10-05). None when the feed omits them. After
            # extra time it is taken from the 90-minute score, not the final one
            # (8 Nov 2026: Hornchurch v Blackpool read HT 1-1 from the 1-2 aet
            # final; it was 1-0, BBC).
            "fh_home": _first_half(h90 if stage in EXTRA_TIME else hg, kv.get("BC")),
            "fh_away": _first_half(a90 if stage in EXTRA_TIME else ag, kv.get("BD")),
            # Decided after 90 minutes (extra time, penalties, awarded). A
            # postponed / cancelled game (stage 4 / 5) carries no score and is
            # neither: it stays pending until it is played, never "no 90-min result".
            "finished_other": finished and stage != FINISHED_REGULAR and hg is not None,
            # The 90-minute score: AT/AU (regular time). After extra time it is
            # what bets settle on; None when the feed gives none.
            "ft90_home": h90, "ft90_away": a90,
            "stage": stage,
            "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if sport == 3:
            ev["h1_home"] = _basketball_half(kv.get("BA"), kv.get("BC"))
            ev["h1_away"] = _basketball_half(kv.get("BB"), kv.get("BD"))
        out.append(ev)
    return out


def _ninety(stage: str | None, hg: int | None, ag: int | None,
            at: str | None, au: str | None) -> tuple[int | None, int | None]:
    """The 90-minute score. Finished in 90 minutes: the final score. After extra
    time or penalties: AT/AU, the feed's regular-time score. Checked 2026-11-08 on
    every finished game of 1-7 Nov: AT/AU equals the final on all 4,339 games
    decided in 90 minutes, and on the 36 that went further it is never above the
    final (Hornchurch v Blackpool: AT/AU 1-1, final 1-2 aet = BBC "1-1 at the end
    of 90 minutes"). None when the feed gives no AT/AU or it fails that check."""
    if hg is None or ag is None:
        return None, None
    if stage == FINISHED_REGULAR:
        return hg, ag
    if stage not in EXTRA_TIME:
        return None, None
    try:
        h, a = int(at), int(au)        # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, None
    if not (0 <= h <= hg and 0 <= a <= ag):
        return None, None
    return h, a


def _basketball_half(p1: Optional[str], p2: Optional[str]) -> Optional[int]:
    """1st-half points = period 1 + period 2. Quarter leagues fill BA/BB (Q1) and BC/BD (Q2);
    men's NCAA plays halves and sends BA/BB = 0 with the 1st half in BC/BD, so the same sum holds
    (checked 2026-11-05 on NBA, EuroLeague, LNB, LNBP and NCAA finals: periods add up to the
    final). None when either period is missing."""
    try:
        return int(p1) + int(p2) if p1 is not None and p2 is not None else None
    except ValueError:
        return None


def _first_half(ft: Optional[int], second: Optional[str]) -> Optional[int]:
    try:
        s = int(second) if second is not None else None
    except ValueError:
        return None
    if ft is None or s is None or s > ft or s < 0:
        return None
    return ft - s


def results_for_offset(offset: int, sign: Optional[str] = None, sport: int = 1) -> list[dict]:
    """Events for a day relative to today (0 = today, -1 = yesterday, ...).
    Past days are cached once fully settled. sport 1 = football (the default,
    the grading source), 3 = basketball (engine/universe.py, 2026-10-07)."""
    day = date.fromordinal(date.today().toordinal() + offset).isoformat()
    cache = _CACHE / (f"{day}.json" if sport == 1 else f"s{sport}_{day}.json")
    if offset < -1 and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    text = _get(_FEED.replace("f_1_", f"f_{sport}_").format(offset=offset),
                {"x-fsign": sign or feed_sign(), "Referer": "https://www.flashscore.co.uk/"})
    events = parse_feed(text, sport)
    if offset < 0:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(events), encoding="utf-8")
    return events


def results_since(days_back: int = 7, sport: int = 1) -> list[dict]:
    """Every event from `days_back` days ago up to today (Flashscore keeps 7)."""
    sign = feed_sign()
    out = []
    for off in range(-min(days_back, 7), 1):
        try:
            out += results_for_offset(off, sign, sport)
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
        (r"^spurs$", "tottenham"),
        # Turkish clubs Flashscore lists under their current names (8 Oct 2026:
        # the Turkish Cup tie stayed ungraded on the name mismatch).
        (r"^denizli iy gureller$", "denizli idman yurdu"),
        (r"^serik spor$", "serik belediyespor"),
        (r"^sabah masazir$", "sabah baku"),          # Flashscore: 'Sabah Baku'
        # 22 Oct 2026: two AI Survivor picks of 18 Oct stayed ungraded on these
        # ('Go Ahead Eagles' v Flashscore's 'G.A. Eagles'; 'Istanbul BB' is
        # Basaksehir's old name, 'Istanbul Buyuksehir Belediyespor').
        (r"^g a eagles$", "go ahead eagles"),
        (r"^istanbul bb$", "basaksehir"), (r"^istanbul basaksehir$", "basaksehir"),
        # 26 Oct 2026: two 25 Oct singles stayed PENDING on these ('VfL 1899
        # Osnabruck' v 'VfL Osnabruck'; SportyBet's 'Sp Lisbon' v 'Sporting CP').
        (r"^vfl 1899 osnabruck$", "vfl osnabruck"), (r"^sporting lisbon$", "sporting cp"),
        # 8 Nov 2026: board picks of 24 Oct - 7 Nov stayed ungraded on these
        # (football-data / SportyBet spelling v Flashscore and FotMob). Each one
        # checked against both sources' names on the day.
        (r"^ein frankfurt$", "eintracht frankfurt"),                      # FS + FM 'Eintracht Frankfurt'
        (r"^(paris sg|psg|paris saint germain)$", "paris saint germain"),  # FS 'PSG', FM 'Paris Saint-Germain'
        (r"^(m gladbach|b monchengladbach|borussia monchengladbach)$", "monchengladbach"),
        (r"^(kuopion palloseura|kups)$", "kups"),                         # FS + FM 'KuPS'
        # Turkish Cup 28 Oct 2026 (TFF fixture list): the Eskisehir club is
        # FotMob's 'Anadolu Universitesi'; Halide Edip Adivarspor was renamed
        # Beyoglu Yeni Carsi in 2021.
        (r"^arnavutkoy belediyesi genclik ve spor$", "arnavutkoy belediyespor"),
        (r"^eskisehir anadolu spor faaliyetleri as$", "anadolu universitesi"),
        (r"^(halide edip adivarspor|beyoglu yeni carsi( futbol kulubu| spor faaliyetleri as)?)$",
         "beyoglu yeni carsi")]


def norm(name: str) -> str:
    # Strip accents first ('Cádiz' -> 'cadiz', 'Leganés' -> 'leganes'). Turkish
    # dotless 'ı' has no accent to strip and was dropped ('Çarşı' -> 'cars').
    n = (name or "").replace("ı", "i")
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
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

# Youth / women's sides. On a Champions League day the UEFA Youth League plays
# the same clubs ('Inter U19' v 'Club Brugge U19'); a senior pick must never
# weigh them, or two candidates tie and the result is never graded (13 Oct
# 2026: Inter v Club Brugge, Lens v Sporting, Sabah v Slavia stayed ungraded).
_SECOND_XI = re.compile(r"\b(u1[5-9]|u2[0-3]|women|w|youth)\b", re.I)


def _name_sim(ours: str, theirs: str) -> float:
    """_sim, also trying the board's own alias for `ours` (engine/name_match.py
    EXPLICIT, the table that rates feed spellings), counted only when the
    alias is exactly Flashscore's name. Never lower than _sim alone.
    12 Oct 2026: 'Vaalerenga IF' v Flashscore's 'Valerenga' scored 0.82 and
    the won pick stayed ungraded; its alias 'Valerenga' matches."""
    from engine.name_match import EXPLICIT
    alias = EXPLICIT.get(ours)
    if alias and norm(alias) == norm(theirs):
        return 1.0      # exact alias only: 'AEK' must not reach 'AEK Larnaca' by containment
    return _sim(ours, theirs)


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
        if ev.get("stage") in POSTPONED and ev.get("fthg") is None:
            continue                     # postponed / cancelled: the replayed game is the one
        if (_SECOND_XI.search(f'{ev["home"]} {ev["away"]}')
                and not _SECOND_XI.search(f"{home} {away}")):
            continue                     # a youth / women's game, not ours
        s = min(_name_sim(home, ev["home"]), _name_sim(away, ev["away"]))
        if s >= MATCH_MIN:
            scored.append((s, ev))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    if len(scored) > 1 and scored[1][0] >= scored[0][0] - 0.02:
        return None                      # ambiguous — never guess
    return scored[0][1]
