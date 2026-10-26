"""
KICKOFF COHORTS (Architect 2026-10-26 18:20-18:30 UK: "time-bucketed accas").

An acca is built only from fixtures kicking off inside the same 30-minute window
(a "cohort"): a 14:45 leg never shares a slip with a 20:00 leg. Why: an early
loss kills the late legs before they start, and cash-out needs every leg live at
the same time.

  - Legs are sorted by kickoff_utc; a cohort runs from its first kickoff to at
    most MAX_BUCKET_SPREAD_MINUTES later (earliest to latest leg).
  - A SPARSE cohort (too few legs for the acca kind) may merge with the
    immediately next cohort only, and only when that one starts at most
    MAX_FALLBACK_GAP_MINUTES after it. Otherwise its games stay singles; they
    are never pushed into a later acca.
  - A leg with no fetched kickoff can't be placed in a cohort, so it stays a
    single (HR35: no guessed time).

This changes only which legs share a slip. Every existing rule (value first,
75%+ legs, max legs, the acca mix, a match in one acca at most) runs inside each
cohort unchanged. Each slip in picks_<date>.json carries the cohort fields
(slip_fields) so the live ticket monitor can watch an acca as one unit and
rebook its unstarted legs. FIELD NAMES ARE STABLE — another session reads them:
cohort_id, cohort_merged, earliest_kickoff_utc, latest_kickoff_utc,
spread_minutes, leg_detail[{fixture, home, away, kickoff_utc, sb_event_id,
sb_tid, market, sb_market, pick, price, chance}].
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

MAX_BUCKET_SPREAD_MINUTES = 30
MAX_FALLBACK_GAP_MINUTES = 60

# fixtures of a built slip -> (cohort id, merged?), filled in by the builders
_REGISTRY: dict[frozenset, tuple[str, bool]] = {}


def kickoff_dt(bf) -> Optional[datetime]:
    """The fixture's fetched kickoff as an aware UTC datetime, else None."""
    ko = getattr(bf, "kickoff_utc", None) or ""
    if "T" not in ko:
        return None
    try:
        when = datetime.fromisoformat(ko.replace("Z", "+00:00").replace(".000", ""))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def cohort_id(start: datetime) -> str:
    """COHORT_<yyyymmdd>_<hhmm> of the cohort's first kickoff, UK time."""
    from engine.uktime import UK
    return start.astimezone(UK).strftime("COHORT_%Y%m%d_%H%M")


def _leg_ko(leg) -> Optional[datetime]:
    return kickoff_dt(leg[0])


def buckets(legs: list, enough: Callable[[list], bool],
            ko: Callable = _leg_ko) -> list[tuple[str, bool, list]]:
    """Ranked legs -> [(cohort_id, merged, legs)] in kickoff order. Each
    cohort's legs keep the order they came in (the caller's ranking).
    `enough(legs)` says whether a cohort has what its acca kind needs; one that
    doesn't may take in the next cohort (MAX_FALLBACK_GAP_MINUTES), once."""
    rank = {id(leg): i for i, leg in enumerate(legs)}
    timed = sorted((leg for leg in legs if ko(leg) is not None), key=lambda l: (ko(l), rank[id(l)]))
    raw: list[list] = []
    spread = timedelta(minutes=MAX_BUCKET_SPREAD_MINUTES)
    for leg in timed:
        if raw and ko(leg) - ko(raw[-1][0]) <= spread:
            raw[-1].append(leg)
        else:
            raw.append([leg])
    out, i = [], 0
    gap = timedelta(minutes=MAX_FALLBACK_GAP_MINUTES)
    while i < len(raw):
        b, merged = raw[i], False
        if not enough(b) and i + 1 < len(raw) and ko(raw[i + 1][0]) - ko(b[0]) <= gap:
            b, merged = b + raw[i + 1], True
            i += 1
        i += 1
        out.append((cohort_id(ko(b[0])), merged, sorted(b, key=lambda l: rank[id(l)])))
    return out


def _fixture(bf) -> str:
    return bf.fixture.split(" (")[0]


def remember(legs: list, cid: str, merged: bool) -> None:
    _REGISTRY[frozenset(_fixture(leg[0]) for leg in legs)] = (cid, merged)


def same_cohort(slips: list) -> bool:
    """True when every slip [(name, legs, combo)] sits in one cohort — the only
    case where a combined code (ACCAS / ALT / VALUE / 50+ MEGA) keeps the rule."""
    ids = {slip_fields(legs)["cohort_id"] for _n, legs, _c in slips}
    return len(ids) == 1 and None not in ids


def _leg_detail(leg) -> dict:
    bf = leg[0]
    key = leg[3] if len(leg) > 3 and isinstance(leg[3], str) else getattr(bf, "best_market_key", None)
    price = leg[4] if len(leg) > 4 else getattr(bf, "best_price", None)
    from engine.picks_ledger import _sb_market
    p = getattr(bf, "probs", None)
    return {"fixture": _fixture(bf),
            "home": getattr(p, "home_team", None), "away": getattr(p, "away_team", None),
            "kickoff_utc": getattr(bf, "kickoff_utc", None),
            "sb_event_id": getattr(bf, "sb_event_id", None), "sb_tid": getattr(bf, "sb_tid", None),
            "market": key, "sb_market": _sb_market(key) if key else None,
            "pick": leg[1], "price": price, "chance": leg[2]}


def slip_fields(legs: list) -> dict:
    """The cohort fields stored with a slip in picks_<date>.json."""
    kos = [k for k in (kickoff_dt(leg[0]) for leg in legs) if k is not None]
    reg = _REGISTRY.get(frozenset(_fixture(leg[0]) for leg in legs))
    cid, merged = reg if reg else ((cohort_id(min(kos)), False) if kos else (None, False))
    iso = (lambda d: d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return {"cohort_id": cid, "cohort_merged": merged,
            "earliest_kickoff_utc": iso(min(kos)) if kos else None,
            "latest_kickoff_utc": iso(max(kos)) if kos else None,
            "spread_minutes": int((max(kos) - min(kos)).total_seconds() // 60) if kos else None,
            "leg_detail": [_leg_detail(leg) for leg in legs]}
