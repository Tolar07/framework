"""
EXCHANGE PRICES — the sharp reference for every pick and every SportyBet side (Architect
2026-11-04: "how can the training turn to an edge? ... do 1 to 7").

Why: SportyBet's own prices already know what our model knows (backtest/BOTH_SIDES_STUDY.md:
8,953 games, learning moved the Brier score 0.18320 -> 0.18314, likeliest-outcome picking
-4.3% ± 0.6%). An edge exists only where the price we TAKE beats the true chance. The best
free estimate of the true chance is an exchange price with no bookmaker margin in it.
football-data's Betfair columns (pipeline/sharp.py) cover 1X2 and O/U 2.5 in 19 leagues
only: 69 of 345 singles over 25 Oct - 3 Nov had a sharp price.

Matchbook's REST API reads events, markets and prices WITHOUT logging in (fetched by
data/matchbook_prices.py, which already puts Matchbook's best BACK beside SportyBet's main
markets for backtest/MATCHBOOK_PRICE_STUDY.md). This module turns every runner of every market
into a FAIR chance (no margin) and maps every SportyBet side key onto it.

Fair chance of a runner:
  * best back and best lay both quoted, spread <= MAX_SPREAD (in chance points): the midpoint
    of the two implied chances — no margin in it;
  * otherwise, in a 2-3 way market whose runners partition the result (1X2, totals,
    handicap pairs, yes/no ...), every side backed with £5+, the best backs with their
    over-round (at most 8%) removed;
  * otherwise None (HR35: a thin or one-sided book gives no number).

Keys. Football SportyBet sides keep the ladder's key ("SB:16|hcp=1.5|Home (+1.5)",
engine/universe.py). Basketball sides read straight from SportyBet's feed are keyed
"B:<market id>|<specifier>|<outcome>" (219 winner, 223 handicap, 225 total, 68 1st-half total),
the same fields the NBA board's picks carry. RECORDED ONLY: nothing here picks or stakes.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import datetime, timedelta
from difflib import SequenceMatcher

MAX_SPREAD = 0.04            # back/lay spread, chance points, for a midpoint fair chance
MAX_OVERROUND = 1.08         # back-only fallback: the book's over-round at most this
MIN_LIQ = 5.0                # back-only fallback: £ at every side's best back
KICKOFF_TOLERANCE = timedelta(minutes=20)

_NOISE = {"fc", "cf", "sc", "ac", "afc", "fk", "sk", "if", "bk", "cd", "ud", "sd", "rc", "sv", "vfb",
          "vfl", "tsg", "us", "as", "ss", "club", "de", "the", "calcio", "1907", "1909", "1913"}
_ALIASES = {"man": "manchester", "utd": "united", "psg": "paris saint germain", "spurs": "tottenham",
            "wolves": "wolverhampton", "nottm": "nottingham", "sheff": "sheffield", "bodoe": "bodo"}


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _dt(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


# ---------------------------------------------------------------- fetching
def fetch_events(get: Callable[[str], dict] | None = None) -> list[dict]:
    """Every open Matchbook football + basketball event with best prices (no login), each
    tagged e["_sport"]. The fetch is data/matchbook_prices.py's (the universe sweep's)."""
    from data import matchbook_prices as mbp
    events = mbp.fetch(get) if get else mbp.fetch()
    for e in events:
        e["_sport"] = mbp._sport_of(e)
    return [e for e in events if e["_sport"]]


# ---------------------------------------------------------------- one event's fair chances
def book(runner: dict) -> dict:
    backs = [(_f(p.get("odds")), _f(p.get("available-amount")) or 0.0)
             for p in runner.get("prices") or [] if p.get("side") == "back"]
    lays = [_f(p.get("odds")) for p in runner.get("prices") or [] if p.get("side") == "lay"]
    backs = sorted((b for b in backs if b[0] and b[0] > 1.0), reverse=True)
    lays = sorted(x for x in lays if x and x > 1.0)
    return {"back": backs[0][0] if backs else None, "lay": lays[0] if lays else None,
            "liq": round(backs[0][1], 2) if backs else 0.0}


def split_event(name: str) -> tuple[str, str]:
    if " at " in name and " vs " not in name and " v " not in name:   # US sports: "Away at Home"
        a, h = name.split(" at ", 1)
        return h.strip(), a.strip()
    for sep in (" vs ", " v "):
        if sep in name:
            h, a = name.split(sep, 1)
            return h.strip(), a.strip()
    return name, ""


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [_ALIASES.get(w, w) for w in s.split()]
    return " ".join(w for w in " ".join(words).split() if w not in _NOISE)


def alike(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    contain = len(ta & tb) / min(len(ta), len(tb))
    return max(SequenceMatcher(None, a, b).ratio(), 0.9 * contain)


def _g(x: float | None) -> str:
    return "" if x is None else f"{x:g}"


def _runner_keys(e: dict, m: dict) -> list[tuple[str, dict, bool]]:
    """[(canonical key, runner, market partitions the result)] for one Matchbook market."""
    eh, ea = split_event(e.get("name") or "")
    name, mtype = (m.get("name") or "").strip().lower(), m.get("market-type")
    hc = _f(m.get("handicap"))
    out: list[tuple[str, dict, bool]] = []
    for r in m.get("runners") or []:
        if r.get("status") != "open":
            continue
        rn = (r.get("name") or "").strip()
        rl = rn.lower()
        side = "home" if rl == eh.lower() else "away" if rl == ea.lower() else "draw" if rl == "draw" else None
        ou = "over" if rl.startswith("over") else "under" if rl.startswith("under") else None
        k = None
        part = True
        if mtype == "one_x_two" and side:
            k = f"1x2|{side}"
        elif mtype == "money_line" and side in ("home", "away"):
            k = f"ml|{side}"
        elif mtype == "total" and name == "total" and ou and hc is not None:
            k = f"total|{_g(hc)}|{ou}"
        elif mtype == "total" and name == "1st half total" and ou and hc is not None:
            k = f"fh|{_g(hc)}|{ou}"
        elif mtype == "total" and name in ("home team total goals", "away team total goals") and ou and hc is not None:
            k = f"tt|{name.split()[0]}|{_g(hc)}|{ou}"
        elif mtype == "handicap" and name == "handicap":
            team = rn.rsplit(" ", 1)[0]
            line = _f(r.get("handicap"))
            s = "home" if alike(team, eh) >= 0.8 else "away" if alike(team, ea) >= 0.8 else None
            if s and line is not None:
                k = f"hcp|{_g(line)}|{s}"
        elif name == "double chance":
            role = {f"{eh} or draw".lower(): "home_or_draw", f"{eh} or {ea}".lower(): "home_or_away",
                    f"draw or {ea}".lower(): "draw_or_away"}.get(rl)
            k, part = (f"dc|{role}" if role else None), False
        elif mtype == "both_to_score" and rl in ("yes", "no"):
            k = f"btts|{rl}"
        elif name in ("home team to win to nil", "away team to win to nil") and rl in ("yes", "no"):
            k = f"wtn|{name.split()[0]}|{rl}"
        elif name == "odd or even total" and rl in ("odd", "even"):
            k = f"oe|{rl}"
        elif name == "half-time result" and side:
            k = f"ht|{side}"
        elif name == "draw no bet" and side in ("home", "away"):
            k = f"dnb|{side}"
        elif name == "match result and total goals" and hc is not None:
            mm = re.fullmatch(r"(.+) and (over|under) [\d.]+", rl)
            if mm:
                t = mm.group(1)
                s = "home" if t == eh.lower() else "away" if t == ea.lower() else "draw" if t == "draw" else None
                k = f"rt|{s}|{mm.group(2)}|{_g(hc)}" if s else None
        elif name == "match result and both teams to score":
            mm = re.fullmatch(r"(.+) and (yes|no)", rl)
            if mm:
                t = mm.group(1)
                s = "home" if t == eh.lower() else "away" if t == ea.lower() else "draw" if t == "draw" else None
                k = f"rb|{s}|{mm.group(2)}" if s else None
        if k:
            out.append((k, r, part))
    return out


def index_event(e: dict) -> dict[str, dict]:
    """{canonical key: {"p", "back", "lay", "liq"}} for one Matchbook event."""
    idx: dict[str, dict] = {}
    for m in e.get("markets") or []:
        if m.get("status") != "open":
            continue
        rows = [(k, book(r), part) for k, r, part in _runner_keys(e, m)]
        # handicap runners of one market are paired by line, so de-vig pairs, not the market
        groups: dict[str, list[tuple[str, dict, bool]]] = {}
        for k, b, part in rows:
            g = f"hcp|{abs(_f(k.split('|')[1]) or 0):g}" if k.startswith("hcp|") else "all"
            groups.setdefault(g, []).append((k, b, part))
        for grp in groups.values():
            backs = [b["back"] for _k, b, _p in grp]
            # back-only fallback: a 2-3 way book, every side backed with real money behind it
            # (thin 6-way combo books carry placeholder backs at 9.0 / 22.0 that de-vig to junk)
            solid = len(grp) in (2, 3) and all(backs) and all(b["liq"] >= MIN_LIQ for _k, b, _p in grp)
            over = sum(1 / x for x in backs) if solid else None
            for k, b, part in grp:
                p = None
                if b["back"] and b["lay"] and 1 / b["back"] - 1 / b["lay"] <= MAX_SPREAD:
                    p = (1 / b["back"] + 1 / b["lay"]) / 2
                elif part and over and b["back"] and 1.0 <= over <= MAX_OVERROUND:
                    p = (1 / b["back"]) / over
                idx[k] = {"p": round(p, 4) if p is not None else None, **b}
    return idx


# ---------------------------------------------------------------- SportyBet key -> exchange key
def canonical(key: str) -> str | None:
    """A SportyBet side ("SB:..." football ladder key or "B:..." basketball key) -> the
    exchange's canonical key, or None when the exchange has no bet that pays the same on
    every score. Whole and quarter lines are left out (push rules could differ)."""
    parts = key.split("|")
    if key == "OVER_2_5":
        return "total|2.5|over"
    if key == "BTTS_YES":
        return "btts|yes"
    if len(parts) != 3:
        return None
    sb, spec, outcome = parts
    out = outcome.strip().lower()

    def half(rx: str) -> float | None:
        mm = re.fullmatch(rx, spec)
        v = float(mm.group(1)) if mm else None
        return v if v is not None and abs(v) % 1 == 0.5 else None

    if sb in ("SB:18", "B:225", "B:68"):
        line = half(r"total=(\d+(?:\.\d+)?)")
        if line is None or not out.startswith(("over", "under")):
            return None
        return f"{'fh' if sb == 'B:68' else 'total'}|{line:g}|{out.split()[0]}"
    if sb == "SB:10":
        role = {"home or draw": "home_or_draw", "home or away": "home_or_away",
                "draw or away": "draw_or_away", "1x": "home_or_draw", "12": "home_or_away",
                "x2": "draw_or_away"}.get(out)
        return f"dc|{role}" if role else None
    if sb in ("SB:16", "B:223"):
        mm = re.fullmatch(r"(home|away) \(([+-]?\d+(?:\.\d+)?)\)", out)
        if not mm or abs(float(mm.group(2))) % 1 != 0.5:
            return None
        return f"hcp|{float(mm.group(2)):g}|{mm.group(1)}"
    if sb == "SB:1" and out in ("home", "draw", "away"):
        return f"1x2|{out}"
    if sb == "B:219" and out in ("home", "away"):
        return f"ml|{out}"
    if sb == "SB:29" and out in ("yes", "no"):
        return f"btts|{out}"
    if sb == "SB:30" and out == "both teams":
        return "btts|yes"
    if sb == "SB:11" and out in ("home", "away"):
        return f"dnb|{out}"
    if sb in ("SB:19", "SB:20"):
        line = half(r"total=(\d+(?:\.\d+)?)")
        if line is None or not out.startswith(("over", "under")):
            return None
        return f"tt|{'home' if sb == 'SB:19' else 'away'}|{line:g}|{out.split()[0]}"
    if sb in ("SB:31", "SB:32") and out in ("yes", "no"):     # clean sheet = the other side's goals u0.5
        return f"tt|{'away' if sb == 'SB:31' else 'home'}|0.5|{'under' if out == 'yes' else 'over'}"
    if sb in ("SB:33", "SB:34") and out in ("yes", "no"):
        return f"wtn|{'home' if sb == 'SB:33' else 'away'}|{out}"
    if sb == "SB:14":                                         # 3-way handicap a:b == Asian half line
        mm = re.fullmatch(r"hcp=(\d+):(\d+)", spec)
        o = re.fullmatch(r"(home|away) \((\d+):(\d+)\)", out)
        if not mm or not o:
            return None
        h = int(mm.group(1)) - int(mm.group(2))
        return f"hcp|{(h - 0.5) if o.group(1) == 'home' else (-h - 0.5):g}|{o.group(1)}"
    if sb == "SB:26" and out in ("odd", "even"):
        return f"oe|{out}"
    if sb == "SB:37":
        line = half(r"total=(\d+(?:\.\d+)?)")
        o = re.fullmatch(r"(home|draw|away) & (over|under) (\d+(?:\.\d+)?)", out)
        return f"rt|{o.group(1)}|{o.group(2)}|{line:g}" if o and line is not None else None
    if sb == "SB:35":
        o = re.fullmatch(r"(home|draw|away) & (yes|no)", out)
        return f"rb|{o.group(1)}|{o.group(2)}" if o else None
    if sb == "SB:60" and out in ("home", "draw", "away"):
        return f"ht|{out}"
    return None


def nba_key(p: dict) -> str:
    """An NBA board pick's side key, in the "B:" form."""
    return f"B:{p.get('market_id')}|{p.get('specifier') or ''}|{p.get('outcome') or ''}"


def match_event(home: str, away: str, ko: datetime | None, events: list[dict]) -> dict | None:
    """The Matchbook event of one fixture: kick-off within ±20 min and both names close."""
    best, best_score = None, 0.0
    for e in events:
        start = _dt(e.get("start"))
        if start is None or ko is None or abs(start - ko) > KICKOFF_TOLERANCE:
            continue
        eh, ea = split_event(e.get("name") or "")
        sh, sa = alike(home, eh), alike(away, ea)
        if min(sh, sa) < 0.5 or sh + sa < 1.3:
            continue
        if sh + sa > best_score:
            best, best_score = e, sh + sa
    return best


def quote(key: str, idx: dict[str, dict]) -> dict | None:
    """The exchange's book for one SportyBet side, or None."""
    c = canonical(key)
    return idx.get(c) if c else None
