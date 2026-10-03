"""Resolve a fixtures-feed team name to the fitted model's name for that club.

TheSportsDB (fixtures) and football-data.co.uk (the model's history) spell
clubs differently: "Blackpool FC" vs "Blackpool", "Hellas Verona" vs
"Verona", "Peterborough United" vs "Peterboro". Without a match the model
cannot rate the fixture, so it falls back to market-implied odds. On
2026-10-03 that hit ~25 fixtures in 7 leagues.

The rules are deliberately narrow, because a wrong match would put one
club's rating on another (HR59 forbids a guessed value). A feed name
resolves to a model name only when:

  * after folding accents/punctuation and dropping club-noise tokens (FC,
    SC, Calcio, years, ...) the two names have the same core tokens, or the
    feed name only adds generic suffixes (United, City, Rovers, ...), or the
    model name abbreviates feed tokens by prefix ("Peterboro"); and
  * exactly ONE model team matches; and
  * no other feed name in the same league resolves to that model team.

Anything else stays unmapped (market-implied, flagged as today). Every
automatic match is surfaced as a board flag so it can be checked, and a
wrong one is fixed by an explicit TEAM_ALIASES entry, which wins.
"""
from __future__ import annotations

import re
import unicodedata

# Tokens that never distinguish one club from another.
NOISE = frozenset({
    "fc", "afc", "cf", "sc", "ss", "ssc", "as", "ac", "us", "sv", "vfl", "vfb",
    "tsv", "fk", "sk", "nk", "calcio", "lr", "energie", "hellas",
})
# Generic suffixes a feed name may ADD to the model's shorter name.
SUFFIXES = frozenset({
    "united", "city", "rovers", "wanderers", "county", "town", "athletic",
})
MIN_PREFIX = 4
# Same club, spelling the general rules deliberately won't guess. Checked
# against both sources' team lists on 2026-10-03.
EXPLICIT = {
    "Sheffield Wednesday": "Sheffield Weds",
    "Sochaux-Montbeliard": "Sochaux",
}


def tokens(name: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    raw = re.split(r"[^a-z0-9]+", folded.lower())
    return [t for t in raw if len(t) > 1 and not t.isdigit() and t not in NOISE]


def _tok_match(model_tok: str, feed_tok: str) -> bool:
    return model_tok == feed_tok or (
        len(model_tok) >= MIN_PREFIX and feed_tok.startswith(model_tok))


def _starts_with(model_toks: list[str], stem: list[str]) -> bool:
    """Model name begins with the club stem (the feed name minus suffixes)."""
    return bool(stem) and len(model_toks) >= len(stem) and all(
        _tok_match(m, s) or _tok_match(s, m) for m, s in zip(model_toks, stem, strict=False))


def same_club(feed: str, model: str) -> bool:
    """True when `model` is a plausible spelling of `feed` under the rules."""
    f, m = tokens(feed), tokens(model)
    if not f or not m or len(m) > len(f):
        return False
    # Model tokens must match the feed's tokens in order, by equality or
    # prefix; any feed tokens left over must be generic suffixes.
    i = 0
    for ft in f:
        if i < len(m) and _tok_match(m[i], ft):
            i += 1
        elif ft not in SUFFIXES:
            return False
    return i == len(m)


def resolve(feed_names: list[str], model_names: list[str]) -> dict[str, str]:
    """{feed name: model name} for feed names absent from the model that
    resolve to exactly one model team, with no two feed names sharing it."""
    known = set(model_names)
    out: dict[str, str] = {}
    for name in feed_names:
        if name in known:
            continue
        if EXPLICIT.get(name) in known:
            out[name] = EXPLICIT[name]
            continue
        cands = [m for m in model_names if same_club(name, m)]
        if len(cands) != 1:
            continue
        # A second model team sharing the club stem ("Cambridge" and
        # "Cambridge City" for feed "Cambridge United") makes it a guess.
        stem = [t for t in tokens(name) if t not in SUFFIXES]
        rivals = [m for m in model_names if m != cands[0] and _starts_with(tokens(m), stem)]
        if not rivals:
            out[name] = cands[0]
    taken: dict[str, int] = {}
    for target in out.values():
        taken[target] = taken.get(target, 0) + 1
    exact_feed = set(feed_names) & known
    return {k: v for k, v in out.items()
            if taken[v] == 1 and v not in exact_feed}
