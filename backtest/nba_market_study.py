"""
NBA MARKET STUDY — every SportyBet NBA market against the results
(Architect 2026-10-13, "do both (a) and (b)"; engine/nba_markets.py).

Each game's LAST look before tip-off — from the every-market record
(output/nba_markets/) and, for the games before it existed, the ladder
snapshots (output/nba_ladders/: full-game total, team points, handicap) —
settled from ESPN's final and quarter scores. Per market:
  landed   how often the outcome won
  fair     SportyBet's own chance: its prices with the margin removed
  return   £1 flat on every outcome at SportyBet's price
and the same split by the short side (price under 2.00) and the long side,
where a bookmaker's favourite-longshot lean shows. Preseason and regular
season apart (preseason rests starters). A market seen whose settlement rule
isn't confirmed is listed as seen and PENDING. A study, not a selector.

    python backtest/nba_market_study.py   → backtest/NBA_MARKET_STUDY.md
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_source as ns  # noqa: E402
from engine import nba_ladder as nl  # noqa: E402
from engine import nba_markets as nm  # noqa: E402

OUT = ROOT / "backtest" / "NBA_MARKET_STUDY.md"
NAMES = {"219": "Winner (incl. OT)", "1": "1X2 (regulation)", "225": "Total points (incl. OT)",
         "227": "Home team points (incl. OT)", "228": "Away team points (incl. OT)",
         "223": "Handicap (incl. OT)", "47": "Half time / full time", "18": "Total points (regulation)",
         "68": "1st half total", "236": "Quarter total", "66": "1st half handicap",
         "303": "Quarter handicap",
         # added 2026-11-05: every market with a settlement rule
         "90": "2nd half total (reg.)", "88": "2nd half handicap (reg.)", "69": "Home team 1st half points",
         "70": "Away team 1st half points", "756": "Home team quarter points", "757": "Away team quarter points",
         "60": "1st half 1X2", "64": "1st half draw no bet", "83": "2nd half 1X2 (reg.)",
         "86": "2nd half draw no bet (reg.)", "235": "Quarter 1X2", "302": "Quarter draw no bet",
         "11": "Draw no bet (regulation)", "229": "Odd/even (incl. OT)", "74": "1st half odd/even",
         "94": "2nd half odd/even (reg.)", "304": "Quarter odd/even", "220": "Overtime yes/no",
         "921": "Player points O/U", "922": "Player assists O/U", "923": "Player rebounds O/U",
         "924": "Player 3-pointers O/U", "768": "Player points N+", "770": "Player assists N+",
         "772": "Player rebounds N+", "774": "Player 3-pointers N+",
         "900967": "Team 3-pointers made total", "900968": "Home 3-pointers made", "900969": "Away 3-pointers made",
         "900975": "Team 2-pointers made total", "900976": "Home 2-pointers made", "900977": "Away 2-pointers made",
         "900961": "Total assists", "900962": "Total rebounds", "900876": "3-pointers made 1X2",
         "900874": "Assists 1X2", "900877": "Rebounds 1X2"}
QUARTERED = ("236", "303", "756", "757", "235", "302", "304")
LADDERS = ("768", "770", "772", "774")


def from_ladder(row: dict) -> dict:
    """A ladder snapshot in the every-market shape (its four full-game markets)."""
    mk = []
    for key, lines in (row.get("ladders") or {}).items():
        mid = key.split("/")[0]
        for line, a, b in lines:
            if mid in nl.TOTAL_MARKETS:
                mk.append({"id": mid, "name": NAMES.get(mid, mid), "spec": f"total={line:g}", "open": True,
                           "outcomes": [[f"Over {line:g}", a], [f"Under {line:g}", b]]})
            else:
                q = f"|quarternr={key.split('/q')[1]}" if "/q" in key else ""
                mk.append({"id": mid, "name": NAMES.get(mid, mid), "spec": f"hcp={line:g}{q}", "open": True,
                           "outcomes": [[f"Home ({line:+g})", a], [f"Away ({-line:+g})", b]]})
    return {**row, "markets": mk}


def looks() -> list[dict]:
    """Every game's last look before tip-off: the every-market record where it
    has the game, else the ladder snapshot."""
    full = {r["event_id"]: r for r in nm.last_looks(nm.load())}
    lad = [from_ladder(r) for r in nl.load() if nl.is_clean(r)]
    for r in nm.last_looks(lad):
        full.setdefault(r["event_id"], r)
    return list(full.values())


def espn_game(row: dict):
    tip = datetime.fromisoformat(row["tip"].replace("Z", "+00:00"))
    for d in (tip.date() - timedelta(days=1), tip.date()):
        for g in ns.scoreboard(d):
            if g.id == row.get("espn_id") and g.completed:
                return g
    return None


def family(m: dict) -> str:
    if m["id"] in NAMES:
        q = re.search(r"quarternr=(\d)", m.get("spec") or "")
        return f"{NAMES[m['id']]} Q{q.group(1)}" if m["id"] in QUARTERED and q else NAMES[m["id"]]
    name = re.sub(r"[-+]?\d+(\.\d+)?", "", m.get("name") or "").strip()
    return f"{name} [{m['id']}]"


def _sharp(r: dict):
    from types import SimpleNamespace
    sh = r.get("sharp") or {}
    return SimpleNamespace(ml_home=sh.get("ml_home"), ml_away=sh.get("ml_away"),
                           spread=sh.get("spread"), total=sh.get("total"))


def settle_rows(rows: list[dict], games: dict, boxes: dict | None = None) -> tuple[list[dict], dict]:
    """[{stage, family, mid, side, price, fair, model, won}] for every settled outcome, and the
    markets seen that couldn't be settled ({family: outcomes}). `model` is the board's fair
    chance from the sharp line (board and SHADOW markets), None where nothing prices it."""
    from engine import nba_value as nv
    boxes = boxes or {}
    out, unsettled = [], defaultdict(int)
    for r in rows:
        g = games.get(r["event_id"])
        if g is None:
            continue
        sharp = _sharp(r)
        for m in r["markets"]:
            if not m.get("open", True):
                continue
            prices = [p for _d, p in m["outcomes"]]
            if any(p <= 1 for p in prices):
                continue
            inv = sum(1 / p for p in prices)
            for desc, p in m["outcomes"]:
                spec = m.get("spec") or ""
                w = nm.settle_any(m["id"], spec, desc, g.hs, g.as_, g.q_home, g.q_away,
                                  name=m.get("name") or "", box=boxes.get(r["event_id"]))
                if w is None:
                    unsettled[family(m)] += 1
                    continue
                model = nv.fair_chance(m["id"], spec, desc, sharp, shadow=True) if sharp.total else None
                board = model is not None and nv.fair_chance(m["id"], spec, desc, sharp) is not None
                # an "N+" player ladder's outcomes overlap (28+ includes 29+): no margin to remove,
                # so its fair chance is the raw 1 / price (margin left in)
                fair = 1 / p if m["id"] in LADDERS else (1 / p) / inv
                out.append({"stage": r.get("stage"), "family": family(m), "mid": m["id"],
                            "side": desc.split()[0].lower() if desc else "", "price": p,
                            "fair": fair, "model": model, "board": board, "won": w,
                            "tip": r.get("tip"), "event_id": r["event_id"], "spec": spec})
    return out, dict(unsettled)


def _line(rows: list[dict]) -> str:
    n = len(rows)
    land = sum(r["won"] for r in rows) / n
    fair = sum(r["fair"] for r in rows) / n
    ret = sum(r["price"] * r["won"] - 1 for r in rows) / n
    return f"{n} | {land:.1%} | {fair:.1%} | {ret:+.1%}"


def would_be_picks(settled: list[dict]) -> list[str]:
    """The board's bars (engine/nba_value: price 1.20-2.00, chance >= 50%, value +3% winner /
    +5% line, at most +25%) on EVERY priced market at SportyBet's recorded last price, graded."""
    from engine import nba_value as nv
    fams: dict[str, list[dict]] = defaultdict(list)
    for r in settled:
        p = r["model"]
        if p is None or r["stage"] != "regular":
            continue
        ev = p * r["price"] - 1
        need = nv.MIN_EV_WINNER if r["mid"] == "219" else nv.MIN_EV_LINE
        if nv.BAND[0] <= r["price"] <= nv.BAND[1] and p >= nv.MIN_CHANCE and need <= ev <= nv.MAX_EV:
            fams[r["family"]].append({**r, "ev": ev})
    out = ["## Would-be picks — the board's bars on every priced market (regular season)", "",
           "Every outcome the sharp line prices (board markets and the SHADOW ones in "
           "engine/nba_value.SHADOW_MARKETS) that clears the board's bars at SportyBet's last recorded "
           "price before tip-off, graded. Several lines per game count (the board takes one); a backtest "
           "of the market, not of the board. SHADOW = priced and recorded only.", "",
           "| Market | board / shadow | picks | won | stated chance | return ± se |", "|---|---|---:|---:|---:|---|"]
    if not fams:
        return out + ["", "NO DATA — PENDING", ""]
    for fam, rs in sorted(fams.items(), key=lambda kv: -len(kv[1])):
        n = len(rs)
        rets = [r["price"] * r["won"] - 1 for r in rs]
        mean = sum(rets) / n
        se = (sum((x - mean) ** 2 for x in rets) / (n - 1) / n) ** 0.5 if n > 1 else None
        kind = "board" if rs[0]["board"] else "shadow"
        out.append(f"| {fam} | {kind} | {n} | {sum(r['won'] for r in rs) / n:.0%} | "
                   f"{sum(r['model'] for r in rs) / n:.0%} | {mean:+.1%}" + (f" ± {se:.1%}" if se else "") + " |")
    return out + [""]


def side_split(settled: list[dict]) -> list[str]:
    """Over vs Under for the player-prop and team-stat totals: a book that leans one way shows here."""
    fams: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in settled:
        if r["stage"] == "regular" and r["mid"] in nm.PROP_STAT | nm.TEAM_STAT.keys() and r["side"] in ("over", "under"):
            fams[(r["family"], r["side"])].append(r)
    if not fams:
        return []
    out = ["## Player props and team stat totals — Over vs Under (regular season)", "",
           "| Market | side | outcomes | landed | fair | return |", "|---|---|---:|---:|---:|---:|"]
    for (fam, side), rs in sorted(fams.items()):
        n = len(rs)
        out.append(f"| {fam} | {side} | {n} | {sum(r['won'] for r in rs) / n:.1%} | "
                   f"{sum(r['fair'] for r in rs) / n:.1%} | {sum(r['price'] * r['won'] - 1 for r in rs) / n:+.1%} |")
    return out + [""]


def build(rows: list[dict], games: dict, boxes: dict | None = None) -> str:
    settled, unsettled = settle_rows(rows, games, boxes)
    out = ["# NBA MARKET STUDY — every SportyBet NBA market against the results", "",
           "Each game's last look before tip-off, every outcome settled from ESPN's final and quarter "
           "scores. *Landed* = how often it won; *fair* = SportyBet's own chance (its prices, margin "
           "removed); *return* = £1 flat on every outcome at SportyBet's price. Landed above fair on a "
           "side = SportyBet under-prices it. Written by `backtest/nba_market_study.py`. A study, not a selector.", "",
           f"Games with a look: {len(rows)} · graded (ESPN final): {sum(r['event_id'] in games for r in rows)}", ""]
    if not settled:
        return "\n".join(out + ["NO DATA — PENDING (no graded game yet)"]) + "\n"
    for stage in ("regular", "preseason"):
        part = [r for r in settled if r["stage"] == stage]
        out += [f"## {stage.capitalize()}" + (" (starters rested — a weak test)" if stage == "preseason" else ""), ""]
        if not part:
            out += ["NO DATA — PENDING", ""]
            continue
        out += ["| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return "
                "| long side (≥2.00): n · landed · fair · return |", "|---|---:|---:|---:|---:|---|---|"]
        fams: dict[str, list[dict]] = defaultdict(list)
        for r in part:
            fams[r["family"]].append(r)
        for fam, rs in sorted(fams.items(), key=lambda kv: -len(kv[1])):
            short = [r for r in rs if r["price"] < 2]
            long_ = [r for r in rs if r["price"] >= 2]
            out.append(f"| {fam} | {_line(rs)} | {_line(short).replace(' | ', ' · ') if short else '—'} | "
                       f"{_line(long_).replace(' | ', ' · ') if long_ else '—'} |")
        out.append("")
    out += would_be_picks(settled)
    out += side_split(settled)
    if unsettled:
        out += ["## Seen, not settled (rule not confirmed — PENDING)", ""]
        out += [f"- {fam}: {n} outcomes" for fam, n in sorted(unsettled.items())]
    return "\n".join(out) + "\n"


def main() -> int:
    rows = looks()
    games = {}
    for r in rows:
        if datetime.fromisoformat(r["tip"].replace("Z", "+00:00")) < datetime.now().astimezone() - timedelta(hours=3):
            g = espn_game(r)
            if g is not None:
                games[r["event_id"]] = g
    from data import nba_players as npl
    boxes = {}
    for eid, g in games.items():                 # box scores for player props / team stat totals
        try:
            boxes[eid] = nm.box_stats(npl.summary(g.id, True), g.home, g.away)
        except Exception:  # noqa: BLE001 — a missing box score leaves those markets unsettled
            continue
    text = build(rows, games, boxes)
    OUT.write_text(text, encoding="utf-8")
    print(f"NBA market study: {len(rows)} games, {len(games)} graded → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
