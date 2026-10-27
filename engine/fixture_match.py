"""
Find the same MATCH in two feeds that spell clubs differently.

Used only to corroborate a fixture or a price (verification/fixture_check.py,
pipeline/odds_verify.py) — never to put one club's rating on another; that is
engine/name_match.py's job and stays strict.

Matching is per league and per day, on BOTH teams, and must be unique: a
league plays each club once a day, so a candidate set of ~10 events leaves no
room for a wrong pairing once both names agree. Two strengths:

  STRONG (both names equal after normalising, or one a subset of the other)
         — enough to report a CONFLICT (e.g. the other feed says postponed).
  WEAK   (a name matched only by prefix/suffix, e.g. "Karlsruhe"/"Karlsruher")
         — may corroborate, never conflict.

Anything less is no match: a spelling we can't pair is not evidence about
the fixture either way. Two clubs of one city ("Dundee", "Dundee United")
can't be confused because both teams of the pair must match and the match
must be unique among that league's games that day.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Optional, TypeVar

from engine.name_match import NOISE

STRONG = 0.9
WEAK = 0.75

# Words that carry no identity across feeds: legal forms, articles, reserve
# markers (a club's B/II side never shares a division with its first team).
_DROP = NOISE | {
    "and", "the", "de", "of", "club", "cd", "ud", "sd", "rc", "rcd", "ca", "cp",
    "if", "bk", "ff", "kv", "krc", "sk", "fk", "ii", "reserves", "u21", "u23",
}

# Short forms (football-data / the model's keys) -> the long form other feeds
# print. Keys and values are in normalised form (see _norm).
ALIASES = {
    "man united": "manchester united", "man utd": "manchester united",
    "man city": "manchester city", "wolves": "wolverhampton wanderers",
    "nottm forest": "nottingham forest", "sheffield weds": "sheffield wednesday",
    "qpr": "queens park rangers", "west brom": "west bromwich albion",
    "spurs": "tottenham hotspur", "ath madrid": "atletico madrid",
    "ath bilbao": "athletic club", "sp gijon": "sporting gijon",
    "espanol": "espanyol", "ein frankfurt": "eintracht frankfurt",
    "mgladbach": "monchengladbach", "paris sg": "paris saint germain",
    "psg": "paris saint germain", "inter": "internazionale",
    "for sittard": "fortuna sittard", "st truiden": "sint truiden",
    "hearts": "heart of midlothian", "la coruna": "deportivo la coruna",
    "sp lisbon": "sporting", "sporting lisbon": "sporting",
    "brighton": "brighton and hove albion",
    "turkiye": "turkey", "czechia": "czech republic",
    "cote divoire": "ivory coast", "usa": "united states",
}


# Letters NFKD can't fold to ASCII; dropping them split one club into two names
# (Nordsjælland / Nordsjaelland, Kasımpaşa / Kasimpasa, Płock / Plock).
_TRANSLIT = str.maketrans({"æ": "ae", "Æ": "Ae", "ø": "o", "Ø": "O", "ı": "i", "ł": "l",
                           "Ł": "L", "đ": "d", "Đ": "D", "ß": "ss", "þ": "th", "ð": "d"})


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.translate(_TRANSLIT)).encode("ascii", "ignore").decode().lower()
    # Scandinavian "aa" is the feeds' spelling of "å" (Vasteraas / Västerås).
    s = s.replace("aa", "a")
    s = s.replace("&", " and ").replace("'", "").replace(".", " ")
    s = " ".join(re.split(r"[^a-z0-9]+", s)).strip()
    return ALIASES.get(s, s)


def tokens(name: str) -> list[str]:
    return [t for t in _norm(name).split()
            if t and t not in _DROP and not t.isdigit() and len(t) > 1]


def _tok_match(x: str, y: str) -> int:
    """2 exact, 1 prefix/suffix (≥4/≥5 letters), 0 none."""
    if x == y:
        return 2
    if (len(x) >= 4 and y.startswith(x)) or (len(y) >= 4 and x.startswith(y)):
        return 1
    if (len(x) >= 5 and y.endswith(x)) or (len(y) >= 5 and x.endswith(y)):
        return 1
    return 0


def team_score(a: str, b: str) -> float:
    """1.0 same name, STRONG subset, WEAK prefix/suffix, 0.0 no match."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    if ta == tb:
        return 1.0
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    used: set[int] = set()
    exact = True
    for x in short:
        best, best_i = 0, -1
        for i, y in enumerate(long_):
            if i in used:
                continue
            m = _tok_match(x, y)
            if m > best:
                best, best_i = m, i
        if best == 0:
            return 0.0
        used.add(best_i)
        exact = exact and best == 2
    return STRONG if exact else WEAK


T = TypeVar("T")


@dataclass
class Match(Generic[T]):
    item: T
    strength: float

    @property
    def strong(self) -> bool:
        return self.strength >= STRONG


def find_match(home: str, away: str, candidates: Iterable[T],
               names: Callable[[T], tuple[str, str]]) -> Optional[Match[T]]:
    """The one candidate whose home AND away both match, or None when none
    does or more than one could (ambiguous is treated as no match).

    A candidate that matches at least as well the other way round (a derby:
    "Dundee v Dundee United" against "Dundee United v Dundee") is not a match —
    the feeds disagree on which side is at home, so neither corroborates."""
    scored = []
    for c in candidates:
        h, a = names(c)
        s = min(team_score(home, h), team_score(away, a))
        if s >= WEAK and s > min(team_score(home, a), team_score(away, h)):
            scored.append((s, c))
    if len(scored) != 1:
        return None
    return Match(item=scored[0][1], strength=scored[0][0])
