"""
SHARP PRICE CHECK (Architect 2026-10-05) — is our price better than the sharpest
book's fair odds?

The Betfair Exchange is where sharp money trades: its prices, with the tiny margin
removed, are the best free estimate of a match's true chances. football-data's free
fixtures.csv carries the exchange's 1X2 (BFEH, BFED, BFEA) and Over/Under 2.5
(BFE>2.5, BFE<2.5) for the coming week's main-league matches; it no longer
carries Pinnacle's (checked 2026-10-05). For every pick in a
market those prices define — home / draw / away, double chance, Over/Under 2.5,
whether a basic key or SportyBet's ladder key — this records:

  sharp_p   the exchange's chance for the pick, margin removed (proportional de-vig)
  sharp_ev  sharp_p x our SportyBet price - 1: positive means the price we take
            is better than the sharp market's fair odds — the edge that matters

A LABEL ONLY, like the price check (order 27): nothing selects, stakes or blocks
on it. It makes the edge measurable at the moment the pick is made, instead of
only at the close. A pick in another market, a league fixtures.csv does not
carry, or a fixture without exchange prices gets no number (HR35: no figure is
invented).
"""
from __future__ import annotations

from typing import Optional

from pipeline.odds_footballdata import _load_fixtures_rows, _to_float
from data.football_data_source import LEAGUE_CODES

_SHARP_1X2 = ("BFEH", "BFED", "BFEA")    # Betfair Exchange
_SHARP_OU = ("BFE>2.5", "BFE<2.5")


def _devig(prices: list[float]) -> list[float]:
    inv = [1 / p for p in prices]
    s = sum(inv)
    return [i / s for i in inv]


def fair_book(rows: Optional[list[dict]] = None) -> tuple[dict, list[str]]:
    """{(div, home, away): {"h","d","a","o25","u25"}} — the exchange's margin-free
    chances from fixtures.csv. Rows lacking a full 1X2 or O/U pair skip that part."""
    flags: list[str] = []
    if rows is None:
        rows, flags = _load_fixtures_rows()
    out: dict = {}
    for r in rows:
        key = (r.get("Div"), (r.get("HomeTeam") or "").strip(), (r.get("AwayTeam") or "").strip())
        if not all(key):
            continue
        fair: dict = {}
        x = [_to_float(r.get(c)) for c in _SHARP_1X2]
        if all(v and v > 1 for v in x):
            fair["h"], fair["d"], fair["a"] = _devig(x)
        ou = [_to_float(r.get(c)) for c in _SHARP_OU]
        if all(v and v > 1 for v in ou):
            fair["o25"], fair["u25"] = _devig(ou)
        if fair:
            out[key] = fair
    return out, flags


def market_prob(key: Optional[str], fair: dict) -> Optional[float]:
    """The exchange's fair chance for one pick key, or None if the key is not a
    1X2 / double-chance / Over-Under-2.5 outcome or the price is missing."""
    if not key:
        return None
    h, d, a = fair.get("h"), fair.get("d"), fair.get("a")
    o, u = fair.get("o25"), fair.get("u25")

    def add(*xs):
        return None if any(v is None for v in xs) else sum(xs)

    basic = {"1X2_HOME": (h,), "1X2_DRAW": (d,), "1X2_AWAY": (a,),
             "DC_1X": (h, d), "DC_X2": (d, a), "DC_12": (h, a),
             "OVER_2_5": (o,), "UNDER_2_5": (u,)}
    if key in basic:
        return add(*basic[key])
    if not key.startswith("SB:"):
        return None
    head, outcome = key[3:].rsplit("|", 1)
    mid, spec = head.split("|", 1) if "|" in head else (head, "")
    out = outcome.strip().lower()
    if mid == "1":
        return {"home": h, "draw": d, "away": a}.get(out)
    if mid == "10":
        parts = {"home or draw": (h, d), "draw or away": (d, a), "home or away": (h, a)}
        return add(*parts[out]) if out in parts else None
    if mid == "18" and spec == "total=2.5":
        return o if out.startswith("over") else u if out.startswith("under") else None
    return None


def check(board: list, rows: Optional[list[dict]] = None) -> tuple[int, int, list[str]]:
    """Set `sharp_p` / `sharp_ev` on each deploy pick the sharp book prices.
    Returns (n_checked, n_above_fair, flags)."""
    fair, flags = fair_book(rows)
    n = above = 0
    for b in board:
        b.sharp_p = b.sharp_ev = None
        if not (getattr(b, "on_deploy_shortlist", False) and b.probs is not None
                and getattr(b, "best_market_key", None) and getattr(b, "best_price", None)):
            continue
        if getattr(b, "prob_source", "model") == "market":
            continue          # SportyBet's spellings, not football-data's
        lg = b.fixture.rsplit("(", 1)[-1].rstrip(")").strip()
        f = fair.get((LEAGUE_CODES.get(lg), b.probs.home_team, b.probs.away_team))
        p = market_prob(b.best_market_key, f) if f else None
        if p is None:
            continue
        b.sharp_p = round(p, 4)
        b.sharp_ev = round(p * b.best_price - 1, 4)
        n += 1
        above += b.sharp_ev > 0
    return n, above, flags
