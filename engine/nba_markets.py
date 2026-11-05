"""
NBA EVERY-MARKET RECORD — every market SportyBet lists on an NBA game, at
every look, graded against the result (Architect 2026-10-13: "what are you
doing in terms of studying it and understanding each of the NBA betting
markets ... the under and over for first half, second half ... the point";
"do both (a) and (b)").

The board (run_nba.py) and the line watch (monitor/nba_watch.py) read
SportyBet's NBA list, which carries only the markets they ask for. Here each
game's full market page is read and kept whole — winner, 1X2, totals, team
points, handicaps, half time / full time, and every half / quarter market
SportyBet adds closer to tip-off — so nothing it offers goes unmeasured:

  output/nba_markets/<UTC date>.jsonl   one line per game per look

backtest/nba_market_study.py takes each game's last look before tip-off,
settles every outcome from ESPN's final and quarter scores (settle_any) and
compares how often each market landed with SportyBet's own chance (its
prices, margin removed). A market whose settlement rule isn't confirmed
(the 2nd half / 4th quarter: overtime in or out?) is kept and counted but
never settled — PENDING, not a guess.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output" / "nba_markets"
_EVENT = "https://www.sportybet.com/api/ng/factsCenter/event?eventId={eid}&productId=3"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def full_event(event_id: str) -> dict:
    """SportyBet's whole market page for one game."""
    req = urllib.request.Request(_EVENT.format(eid=urllib.parse.quote(event_id)),  # noqa: S310
                                 headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        return (json.loads(r.read()).get("data") or {})


def compact_markets(event: dict) -> list[dict]:
    """[{id, name, spec, open, outcomes: [[desc, price], ...]}] — every market."""
    out = []
    for m in event.get("markets") or []:
        outs = []
        for o in m.get("outcomes") or []:
            try:
                outs.append([o.get("desc", ""), float(o.get("odds"))])
            except (TypeError, ValueError):
                continue
        if outs:
            out.append({"id": str(m.get("id")), "name": m.get("desc") or m.get("name") or "",
                        "spec": m.get("specifier") or "", "open": m.get("status") in (None, 0, "0"),
                        "outcomes": outs})
    return out


def snapshot(now: datetime, stage: str, event_id: str, home: str, away: str, g) -> dict | None:
    """One look at one game: every market, with the ESPN game it settles on.
    None when SportyBet's page can't be read (the look is skipped, not faked)."""
    try:
        markets = compact_markets(full_event(event_id))
    except Exception:  # noqa: BLE001 — a page that won't load is a missing look
        return None
    if not markets:
        return None
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "stage": stage, "event_id": event_id,
            "espn_id": g.id, "espn_date": (g.tip or g.date)[:10], "tip": g.tip, "home": home, "away": away,
            "sharp": {"ml_home": g.ml_home, "ml_away": g.ml_away, "spread": g.spread, "total": g.total},
            "markets": markets}


def save(rows: list[dict | None], now: datetime, folder: Path = OUT_DIR) -> None:
    kept = [r for r in rows if r]
    if not kept:
        return
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def load(folder: Path = OUT_DIR) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*.jsonl")):
        rows += [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows


def _t(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def last_looks(rows: list[dict]) -> list[dict]:
    """Each game's last look taken before its tip-off."""
    best: dict[str, dict] = {}
    for r in rows:
        if not r.get("tip") or _t(r["at"]) >= _t(r["tip"]):
            continue
        if r["event_id"] not in best or _t(r["at"]) > _t(best[r["event_id"]]["at"]):
            best[r["event_id"]] = r
    return list(best.values())


def _result(home: int, away: int) -> str:
    return "Home" if home > away else "Away" if away > home else "Draw"


# ── box scores: player props and team stat totals (2026-11-05) ─────────────────────────
# SportyBet's player and team-stat markets all say "(incl. overtime)": settled from ESPN's
# finished box score. A player who did not play (or isn't on the box score) voids: None.
PROP_STAT = {"921": "pts", "922": "ast", "923": "reb", "924": "3pm",
             "768": "pts", "770": "ast", "772": "reb", "774": "3pm"}
TEAM_STAT = {"900967": ("3pm", None), "900968": ("3pm", "home"), "900969": ("3pm", "away"),
             "900975": ("2pm", None), "900976": ("2pm", "home"), "900977": ("2pm", "away"),
             "900961": ("ast", None), "900962": ("reb", None)}
TEAM_STAT_1X2 = {"900876": "3pm", "900874": "ast", "900877": "reb"}


def norm_name(name: str) -> str:
    """'Antetokounmpo, Giannis' and 'Giannis Antetokounmpo' -> 'giannis antetokounmpo'."""
    import unicodedata
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    if "," in n:
        last, first = n.split(",", 1)
        n = f"{first} {last}"
    n = re.sub(r"[^a-z ]", " ", n)
    return " ".join(w for w in n.split() if w not in ("jr", "sr", "ii", "iii", "iv"))


def box_stats(blob: dict | None, home_abbr: str, away_abbr: str) -> dict | None:
    """{'players': {norm name: {pts, reb, ast, 3pm, played}}, 'home': {...team sums}, 'away': ...}
    from an ESPN summary, or None when it has no box score."""
    sides = ((blob or {}).get("boxscore") or {}).get("players") or []
    if not sides:
        return None
    out: dict = {"players": {}, "home": {}, "away": {}}
    for side in sides:
        abbr = (side.get("team") or {}).get("abbreviation")
        team = "home" if abbr == home_abbr else "away" if abbr == away_abbr else None
        if team is None:
            continue
        tot = {"pts": 0, "reb": 0, "ast": 0, "3pm": 0, "2pm": 0}
        for st in side.get("statistics") or []:
            keys = st.get("keys") or []
            need = ("points", "rebounds", "assists", "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
                    "fieldGoalsMade-fieldGoalsAttempted")
            if not all(k in keys for k in need):
                continue
            ix = {k: keys.index(k) for k in need}
            for a in st.get("athletes") or []:
                stats = a.get("stats") or []
                name = norm_name((a.get("athlete") or {}).get("displayName", ""))
                if a.get("didNotPlay") or not stats:
                    out["players"][name] = {"played": False}
                    continue
                try:
                    row = {"pts": int(stats[ix["points"]]), "reb": int(stats[ix["rebounds"]]),
                           "ast": int(stats[ix["assists"]]),
                           "3pm": int(str(stats[ix[need[3]]]).split("-")[0]),
                           "fgm": int(str(stats[ix[need[4]]]).split("-")[0])}
                except (ValueError, IndexError):
                    continue
                row["2pm"] = row["fgm"] - row["3pm"]
                row["played"] = True
                out["players"][name] = row
                for k in tot:
                    tot[k] += row[k]
        out[team] = tot
    return out if out["home"] and out["away"] else None


def _over_under(outcome: str, value: float, line: float | None) -> int | None:
    o = outcome.strip().lower()
    if line is None or value == line or not o.startswith(("over", "under")):
        return None
    return int((value > line) == o.startswith("over"))


def settle_box(mid: str, spec: str, outcome: str, name: str, box: dict | None) -> int | None:
    """Player props (921-924 over/under, 768-774 'N+' ladders) and team stat totals."""
    if not box:
        return None
    line = None
    m = re.search(r"total=(-?\d+(?:\.\d+)?)", spec or "")
    if m:
        line = float(m.group(1))
    if mid in ("921", "922", "923", "924"):
        player = norm_name(re.split(r" total ", name or "", maxsplit=1)[0])
        st = box["players"].get(player)
        if not st or not st.get("played"):
            return None
        return _over_under(outcome, st[PROP_STAT[mid]], line)
    if mid in ("768", "770", "772", "774"):
        mm = re.fullmatch(r"(.+?) (\d+)\+", outcome.strip())
        if not mm:
            return None
        st = box["players"].get(norm_name(mm.group(1)))
        if not st or not st.get("played"):
            return None
        return int(st[PROP_STAT[mid]] >= int(mm.group(2)))
    if mid in TEAM_STAT:
        stat, side = TEAM_STAT[mid]
        v = box[side][stat] if side else box["home"][stat] + box["away"][stat]
        return _over_under(outcome, v, line)
    if mid in TEAM_STAT_1X2:
        stat = TEAM_STAT_1X2[mid]
        h, a = box["home"][stat], box["away"][stat]
        res = "home" if h > a else "away" if a > h else "draw"
        return int(outcome.strip().lower() == res)
    return None


def _period(qh: list, qa: list, which: str) -> tuple[int, int] | None:
    """Home / away points in a regulation period: h1, h2 (Q3+Q4) or q1-q4."""
    if len(qh) < 4 or len(qa) < 4:
        return None
    sl = {"h1": slice(0, 2), "h2": slice(2, 4), "q1": slice(0, 1), "q2": slice(1, 2),
          "q3": slice(2, 3), "q4": slice(3, 4), "reg": slice(0, 4)}[which]
    return sum(qh[sl]), sum(qa[sl])


def _side_result(outcome: str, h: int, a: int, dnb: bool) -> int | None:
    o = outcome.strip().lower()
    res = "home" if h > a else "away" if a > h else "draw"
    if dnb and res == "draw":
        return None                                  # draw no bet: stake back
    return int(o == res)


def settle_any(mid: str, spec: str, outcome: str, hs: int, as_: int,
               qh: list | None, qa: list | None, name: str = "", box: dict | None = None) -> int | None:
    """1 won / 0 lost for any outcome whose rule is known; None otherwise.
    The board's own rules (engine/nba_value.settle) for its markets; here also
    1X2 (regulation time: four quarters) and half time / full time (the full
    time part is regulation too when a draw is one of its outcomes). Added
    2026-11-05: the SHADOW period markets (nba_value.SHADOW_MARKETS), period 1X2 /
    draw no bet / odd-even, overtime yes/no, player props and team stat totals (`box`,
    from box_stats). A 2nd-half market is graded only in a game without overtime."""
    from engine import nba_value as nv
    if mid in nv.MARKETS or mid in nv.SHADOW_MARKETS:
        r = nv.settle({"market_id": mid, "specifier": spec, "outcome": outcome}, hs, as_, qh, qa)
        return None if r is None else int(r == "won")
    if mid in PROP_STAT or mid in TEAM_STAT or mid in TEAM_STAT_1X2:
        return settle_box(mid, spec, outcome, name, box)
    if mid == "229":                                 # odd / even incl. overtime
        return int(outcome.strip().lower() == ("odd" if (hs + as_) % 2 else "even"))
    if not qh or not qa or len(qh) < 4 or len(qa) < 4:
        return None
    ot = len(qh) > 4 or len(qa) > 4
    if mid == "220":                                 # will there be overtime
        return int(outcome.strip().lower() == ("yes" if ot else "no"))
    period = {"60": "h1", "64": "h1", "74": "h1", "83": "h2", "86": "h2", "94": "h2",
              "11": "reg"}.get(mid)
    if mid in ("235", "302", "304"):
        q = re.search(r"quarternr=(\d)", spec or "")
        period = f"q{q.group(1)}" if q and q.group(1) in "1234" else None
    if period:
        if period == "h2" and ot:
            return None                              # 2nd half: graded only without overtime
        hp = _period(qh, qa, period)
        if hp is None:
            return None
        if mid in ("74", "94", "304"):
            return int(outcome.strip().lower() == ("odd" if sum(hp) % 2 else "even"))
        return _side_result(outcome, hp[0], hp[1], dnb=mid in ("64", "86", "302", "11"))
    reg = _result(sum(qh[:4]), sum(qa[:4]))
    if mid == "1":
        return int(outcome.strip().lower() == {"Home": "home", "Away": "away", "Draw": "draw"}[reg])
    if mid == "47":
        parts = [p.strip().lower() for p in re.split(r"[/-]", outcome)]
        if len(parts) != 2:
            return None
        half = _result(sum(qh[:2]), sum(qa[:2])).lower()
        return int(parts == [half, reg.lower()])
    return None
