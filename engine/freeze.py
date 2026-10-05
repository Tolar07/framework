"""
CODES FROZEN AT 10PM (Architect 2026-10-04).

The first board DELIVERED for a day — normally the ~10pm evening board — is
frozen: its booking codes are the day's codes. Every later run for that day
(the 7am refresh, a manual resend, the watchdog) keeps them and does NOT send
a new board with new codes. It sends a short check instead:

  * no change         -> "use last night's codes"
  * a leg has drifted out 5%+ on SportyBet, been hit by team news, or left
    the board          -> ONLY the slips carrying that leg get a new code,
                          marked "REPLACED — use NEW instead of OLD"; the
                          broken leg is swapped for the board's current pick
                          for that fixture, or dropped when there is none.

A leg whose match has started is never touched. The frozen board text is kept,
so a manual resend (e.g. to a new subscriber) sends the same board again.

Files: output/boards/frozen_<date>.json (codes, legs, the frozen ledger) and
output/boards/frozen_board_<date>.txt (the exact text that was sent).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BOARD_DIR = Path(__file__).parent.parent / "output" / "boards"
DRIFT = 0.05


def paths(target: str, board_dir: Optional[Path] = None) -> tuple[Path, Path]:
    # BOARD_DIR is read at call time, so a dry run (run_daily --no-send) can
    # point it at a scratch copy and never touch the real frozen files.
    d = board_dir or BOARD_DIR
    return d / f"frozen_{target}.json", d / f"frozen_board_{target}.txt"


def load(target: str, board_dir: Optional[Path] = None) -> Optional[dict]:
    p, _ = paths(target, board_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def board_text(target: str, board_dir: Optional[Path] = None) -> Optional[str]:
    _, t = paths(target, board_dir)
    return t.read_text(encoding="utf-8") if t.exists() else None


def save(target: str, ledger_doc: dict, text: str, run_id: Optional[str],
         board_code: Optional[str] = None, board_dir: Optional[Path] = None) -> Path:
    p, t = paths(target, board_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"date": target, "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "run_id": run_id, "board_code": board_code, "ledger": ledger_doc, "replacements": []}
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    t.write_text(text, encoding="utf-8")
    return p


def _lagos(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{(dt.hour + 1) % 24:02d}:{dt.minute:02d}"
    except (ValueError, AttributeError):
        return "?"


def slips(frozen: dict) -> list[dict]:
    """Every frozen slip as {kind, name, code, legs:[leg dict]} (board mega included)."""
    led = frozen["ledger"]
    singles = {s["fixture"]: s for s in led.get("singles", [])}

    def leg(s):
        return {"fixture": s["fixture"], "league": s.get("league"), "home": s["home"],
                "away": s["away"], "market": s["market"], "pick": s.get("pick"),
                "price": s.get("price"), "kickoff": s.get("kickoff"),
                "kickoff_utc": s.get("kickoff_utc")}
    out = []
    for s in led.get("singles", []):
        if s.get("code"):
            out.append({"kind": "single", "name": s["fixture"], "code": s["code"], "legs": [leg(s)]})
    for kind in ("safe3", "accas", "megas"):
        for x in led.get(kind, []):
            legs = [leg(singles[f]) for f in x["legs"] if f in singles]
            if x.get("code") and legs:
                out.append({"kind": kind, "name": x["name"], "code": x["code"], "legs": legs})
    for x in led.get("alts", []):
        legs = [{**l, "league": l.get("league"), "kickoff_utc": singles.get(l["fixture"], {}).get("kickoff_utc")}
                for l in x.get("alt_legs", [])]
        if x.get("code") and legs:
            out.append({"kind": "alts", "name": x["name"], "code": x["code"], "legs": legs})
    if frozen.get("board_code") and led.get("singles"):
        out.append({"kind": "board", "name": "Board MEGA", "code": frozen["board_code"],
                    "legs": [leg(s) for s in led["singles"]]})
    return out


def started(leg: dict, now: datetime) -> bool:
    ko = leg.get("kickoff_utc")
    try:
        return bool(ko) and datetime.fromisoformat(str(ko).replace("Z", "+00:00")) <= now
    except ValueError:
        return False


def league_of(fixture: str) -> str:
    return fixture.rsplit("(", 1)[-1].rstrip(")").strip() if "(" in fixture else ""


def forbidden(market: Optional[str], league: str) -> Optional[str]:
    """Why a standing order forbids this pick now, or None."""
    from engine import full_markets as fm
    if league in fm.NO_DOG_HANDICAP_LEAGUES and fm.is_underdog_handicap(market or ""):
        return f"underdog handicap in the {league} (order 38)"
    try:
        from engine import loss_watch
        if loss_watch.blocked(market, league, loss_watch.blocks()):
            return f"{loss_watch.segment(market)} in {league} blocked by the Architect (order 39)"
    except Exception:  # noqa: BLE001 — a missing proposals file blocks nothing
        pass
    return None


def leg_issue(leg: dict, board_by_fx: dict, price_now) -> Optional[str]:
    """Why a frozen leg must change, or None. `price_now(leg)` -> current
    SportyBet price of the leg's own market, or None."""
    b = board_by_fx.get(leg["fixture"])
    if b is None or getattr(b, "probs", None) is None:
        return "no longer on the board"
    # A pick a standing order now forbids (order 38 FA Cup underdog handicaps,
    # order 39 approved blocks) is replaced even on a frozen slip (Architect
    # 2026-10-05: "you stop picking it if it's recommended").
    why = forbidden(leg["market"], leg.get("league") or league_of(getattr(b, "fixture", "")))
    if why:
        return why
    p = price_now(leg)
    if p and leg.get("price") and p / leg["price"] - 1 >= DRIFT:
        return f"price drifted {leg['price']:.2f} → {p:.2f}"
    # Team news judged on the FROZEN pick itself (the board may have moved
    # its own pick for this fixture for news that doesn't touch ours).
    news = getattr(b, "team_news", None)
    if news:
        from engine import team_news as tn
        res = tn.assess(leg["market"], news)
        if res["level"] in ("CAUTION", "RISK"):
            return f"team news: {res['note']}"
    return None


def check(frozen: dict, board: list, price_now, book, now: Optional[datetime] = None,
          display=None) -> tuple[list[str], list[dict]]:
    """(message lines, replacement records). `book(legs)` -> new code or None,
    legs as (league, home, away, market). `display(market, home, away)` names a pick."""
    now = now or datetime.now(timezone.utc)
    by_fx = {b.fixture.split(" (")[0]: b for b in board}
    lines, recs = [], []
    for s in slips(frozen):
        new_legs, notes = [], []
        for leg in s["legs"]:
            if started(leg, now):
                new_legs.append(leg)
                continue
            why = leg_issue(leg, by_fx, price_now)
            if not why:
                new_legs.append(leg)
                continue
            b = by_fx.get(leg["fixture"])
            if (b is not None and getattr(b, "on_deploy_shortlist", False)
                    and getattr(b, "best_market_key", None)
                    and b.best_market_key != leg["market"]):
                rep = {**leg, "market": b.best_market_key, "price": b.best_price,
                       "pick": display(b.best_market_key, b.probs.home_team, b.probs.away_team)
                       if display else b.best_market_key}
                new_legs.append(rep)
                notes.append(f"{leg['fixture']}: {leg.get('pick')} → {rep['pick']} ({why})")
            else:
                notes.append(f"{leg['fixture']}: {leg.get('pick')} dropped ({why})")
        if not notes:
            continue
        min_legs = 1 if s["kind"] == "single" else 2
        if len(new_legs) < min_legs:
            lines.append(f"✖ {s['name']} {s['code']} — WITHDRAWN, don't play it · " + "; ".join(notes))
            recs.append({"kind": s["kind"], "name": s["name"], "old_code": s["code"],
                         "new_code": None, "notes": notes, "alt_legs": []})
            continue
        code = book([(l.get("league"), l["home"], l["away"], l["market"]) for l in new_legs])
        odds = 1.0
        for l in new_legs:
            odds *= l.get("price") or 1.0
        lines.append(f"⇄ {s['name']} {s['code']} → REPLACED by {code or 'PENDING'} "
                     f"({len(new_legs)} legs · odds {odds:.2f}) · " + "; ".join(notes))
        recs.append({"kind": s["kind"], "name": s["name"], "old_code": s["code"], "new_code": code,
                     "notes": notes, "odds": round(odds, 3), "result": None,
                     "alt_legs": [{"fixture": l["fixture"], "home": l["home"], "away": l["away"],
                                   "kickoff": l.get("kickoff"), "market": l["market"],
                                   "pick": l.get("pick"), "price": l.get("price"),
                                   "result": None} for l in new_legs]})
    return lines, recs


def message(frozen: dict, lines: list[str], target: str, run_id: str) -> str:
    head = [f"🔒 OLP XDV — CODES FROZEN · {target}", f"Run ID: {run_id}",
            f"The codes from the board sent at {_lagos(frozen['frozen_at'])} (Lagos) "
            f"are the codes for {target}."]
    if not lines:
        return "\n".join(head + ["", "✅ No changes — every leg still stands. Use last night's codes."])
    return "\n".join(head + ["", f"⚠ {len(lines)} slip(s) changed — use the NEW code for these "
                                 f"only; every other code stays as it was:", ""] + lines)
