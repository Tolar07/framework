"""
NBA SHADOW BOARD — every NBA market played side by side with the live NBA board
(Architect 2026-11-05: "It needs small graded game first. Do it side by side. You learn by
doing it side by side. Still go with NBA for tonight").

The live board (run_nba.py, monitor/nba_watch.py) is unchanged and keeps its markets. Next to
it, on every line-watch look (monitor/nba_watch.py, every 15 min before tip-off), each game's
SportyBet market page is priced for the SHADOW markets (engine/nba_value.SHADOW_MARKETS:
2nd-4th quarter totals, 2nd-half total and handicap, 4th-quarter handicap, each team's 1st-half
and quarter points) with the board's own bars (price 1.20-2.00, chance >= 50%, value >= +5%,
at most +25%). The first line that clears them is FROZEN per game and market, at that look's
price: an entry taken before tip-off, never chosen after the result.

  output/nba_shadow/shadow_<night>.json   the frozen picks, graded after the night
  backtest/NBA_SHADOW.md                  per market: graded, won, return ± se, and whether it
                                          has earned a place on the board

Graded from ESPN's quarter scores (engine/nba_markets.settle_any; a 2nd-half line only in a
game without overtime). PAPER: nothing is booked, staked or sent. A market reaches READY when
it has PROMOTE_N graded picks and its return is above zero by more than PROMOTE_SE standard
errors; moving it onto the board is then a separate change.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output" / "nba_shadow"
REPORT = ROOT / "backtest" / "NBA_SHADOW.md"
PROMOTE_N = 100
PROMOTE_SE = 2.0          # nine markets tested at once: 1 se would pass one by luck about half the time
NAMES = {"219": "Winner (incl. OT)", "223": "Handicap (incl. OT)", "225": "Total (incl. OT)",
         "68": "1st half total", "66": "1st half handicap", "227": "Home team points (incl. OT)",
         "228": "Away team points (incl. OT)", "18": "Total (regulation)", "236": "Quarter total", "90": "2nd half total (reg.)", "88": "2nd half handicap (reg.)",
         "69": "Home team 1st half points", "70": "Away team 1st half points",
         "756": "Home team quarter points", "757": "Away team quarter points", "303": "Quarter handicap"}


def family(mid: str, spec: str) -> str:
    q = re.search(r"quarternr=(\d)", spec or "")
    return f"{NAMES.get(mid, mid)} Q{q.group(1)}" if q else NAMES.get(mid, mid)


def _t(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def candidates(look: dict) -> list[dict]:
    """Lines in one look that clear the board's bars with the board's (blended) chance, best per
    market family. Since 2026-11-05 evening every market is live, so this records every family,
    not only the former SHADOW ones: the board takes one pick per game, this grades them all."""
    from engine import nba_value as nv
    sh = look.get("sharp") or {}
    sharp = SimpleNamespace(ml_home=sh.get("ml_home"), ml_away=sh.get("ml_away"),
                            spread=sh.get("spread"), total=sh.get("total"))
    if sharp.total is None:
        return []
    best: dict[str, dict] = {}
    for m in look.get("markets") or []:
        mid, spec = str(m.get("id")), m.get("spec") or ""
        if mid not in nv.MARKETS or not m.get("open", True):
            continue
        twin = [(d, x) for d, x in m.get("outcomes") or []]
        for desc, price in m.get("outcomes") or []:
            p = nv.blended(nv.fair_chance(mid, spec, desc, sharp), mid, spec, nv.sb_fair(twin, desc))
            if p is None or not (nv.BAND[0] <= price <= nv.BAND[1]) or p < nv.MIN_CHANCE:
                continue
            ev = p * price - 1
            need = nv.MIN_EV_WINNER if mid == "219" else nv.MIN_EV_LINE
            if not need <= ev <= nv.MAX_EV:
                continue
            fam = family(mid, spec)
            if fam not in best or ev > best[fam]["ev"]:
                best[fam] = {"family": fam, "market_id": mid, "specifier": spec, "outcome": desc,
                             "price": price, "chance": round(p, 4), "ev": round(ev, 4)}
    return list(best.values())


def update(looks: Sequence[dict | None], night: str, folder: Path = OUT_DIR) -> int:
    """Freeze every new (game, market family) shadow pick from this round's looks. Returns how
    many were added. A look at or after tip-off is ignored."""
    path = folder / f"shadow_{night}.json"
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"date": night, "picks": []}
    have = {(p["event_id"], p["family"]) for p in doc["picks"]}
    added = 0
    for lk in looks:
        if not lk or not lk.get("tip") or _t(lk["at"]) >= _t(lk["tip"]):
            continue
        for c in candidates(lk):
            if (lk["event_id"], c["family"]) in have:
                continue                                   # frozen at its first entry
            doc["picks"].append({"event_id": lk["event_id"], "espn_id": lk.get("espn_id"),
                                 "espn_date": lk.get("espn_date"), "tip": lk["tip"], "home": lk.get("home"),
                                 "away": lk.get("away"), "stage": lk.get("stage"), "at": lk["at"], **c,
                                 "result": None})
            have.add((lk["event_id"], c["family"]))
            added += 1
    if added:
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return added


def load_all(folder: Path = OUT_DIR) -> list[tuple[Path, dict]]:
    out = []
    for f in sorted(folder.glob("shadow_*.json")) if folder.exists() else []:
        try:
            out.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def grade(now: datetime, folder: Path = OUT_DIR, scoreboard=None) -> int:
    """Grade every finished pick from ESPN's quarter scores: won / lost / void. Returns how many."""
    from data import nba_source as ns
    from engine import nba_markets as nm
    scoreboard = scoreboard or ns.scoreboard
    cache: dict[str, dict] = {}
    n = 0
    for path, doc in load_all(folder):
        changed = False
        for p in doc["picks"]:
            if p.get("result") or _t(p["tip"]) > now - timedelta(hours=4):
                continue
            tip_day = date.fromisoformat(p["tip"][:10])
            g = None
            for day in (tip_day - timedelta(days=1), tip_day):     # ESPN lists games by US date
                d = day.isoformat()
                if d not in cache:
                    try:
                        cache[d] = {x.id: x for x in scoreboard(day)}
                    except Exception:  # noqa: BLE001 — ESPN down: graded on a later run
                        cache[d] = {}
                g = g or cache[d].get(p.get("espn_id"))
            if g is None or not g.completed:
                continue
            w = nm.settle_any(p["market_id"], p["specifier"], p["outcome"], g.hs, g.as_, g.q_home, g.q_away)
            p["result"] = "void" if w is None else ("won" if w else "lost")
            p["score"] = f"{g.hs}-{g.as_}"
            changed = True
            n += 1
        if changed:
            path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return n


def report(folder: Path = OUT_DIR) -> str:
    rows: dict[str, list[dict]] = {}
    pending = 0
    for _path, doc in load_all(folder):
        for p in doc["picks"]:
            if p.get("stage") == "preseason":
                continue
            if p.get("result") in ("won", "lost"):
                rows.setdefault(p["family"], []).append(p)
            elif not p.get("result"):
                pending += 1
    L = ["# NBA SIDE-BY-SIDE RECORD — every NBA market, next to the live board", "",
         "Written by `engine/nba_shadow.py`. Every market is live on the board since 2026-11-05, which "
         "takes ONE pick per game; this grades each game's first SportyBet line that clears the board's "
         "bars (with the board's blended chance, backtest/NBA_BLEND_STUDY.md) in EVERY market family, "
         "frozen before tip-off at that price, graded from ESPN. Recorded only: nothing booked from it.", "",
         f"PROVEN = {PROMOTE_N}+ graded and return more than {PROMOTE_SE:g} se above zero. A family "
         f"that stays negative is the first to look at. Still to grade: {pending}.", "",
         "| Market | graded | won | stated chance | return ± se | status |", "|---|---:|---:|---:|---|---|"]
    if not rows:
        return "\n".join(L + ["", "NO DATA — PENDING (no graded shadow pick yet)"]) + "\n"
    for fam, rs in sorted(rows.items(), key=lambda kv: -len(kv[1])):
        n = len(rs)
        rets = [p["price"] - 1 if p["result"] == "won" else -1.0 for p in rs]
        mean = sum(rets) / n
        se = math.sqrt(sum((x - mean) ** 2 for x in rets) / (n - 1) / n) if n > 1 else None
        ready = n >= PROMOTE_N and se is not None and mean > PROMOTE_SE * se
        status = "**PROVEN**" if ready else f"COLLECTING ({n} of {PROMOTE_N})" if n < PROMOTE_N else "not yet"
        L.append(f"| {fam} | {n} | {sum(p['result'] == 'won' for p in rs) / n:.0%} | "
                 f"{sum(p['chance'] for p in rs) / n:.0%} | {mean:+.1%}" + (f" ± {se:.1%}" if se else "")
                 + f" | {status} |")
    return "\n".join(L) + "\n"


def by_night(looks: Sequence[dict | None], night_key) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for lk in looks:
        if lk and lk.get("tip"):
            out.setdefault(night_key(_t(lk["tip"])), []).append(lk)
    return out


def backfill(folder: Path = OUT_DIR) -> int:
    """Replay every look already recorded live (output/nba_markets/, oldest first) through the
    same first-entry rule: the prices were taken before tip-off when they were recorded."""
    import run_nba
    from engine import nba_markets as nm
    looks = sorted(nm.load(), key=lambda r: r["at"])
    return sum(update(v, k, folder) for k, v in by_night(looks, run_nba.night_key).items())


def main() -> int:
    import sys
    from datetime import UTC
    if "--backfill" in sys.argv:
        print(f"NBA shadow board: {backfill()} picks replayed from recorded looks")
    n = grade(datetime.now(UTC))
    REPORT.write_text(report(), encoding="utf-8")
    print(f"NBA shadow board: {n} newly graded -> {REPORT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
