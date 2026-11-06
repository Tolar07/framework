"""
NBA TEAM NEWS PER PICK — twin of engine/team_news.py (framework #329; config/sport_parity.json).

Football's engine/team_news.py says whether a team's news hurts THIS pick. This does it for the NBA from
the ESPN injury report (data/nba_players.py): for each board / watch pick it works out which side the pick
leans on and says HURT, HELPED or NEUTRAL.

  * a team's LOST SHARE = recent minutes of its Out players (plus Doubtful / Questionable / Day-To-Day
    weighted by the chance they sit) divided by the minutes of everyone on its sheet;
  * winner / handicap (219, 223, 88): depends on one side; hurt when that side loses >= CAUTION and the
    other loses clearly less, helped when the other side is the one short;
  * team total (227/228, 69/70, 756/757): the team's own loss; Over is hurt, Under is helped;
  * game / half / quarter total (225, 68, 236, 90, 18): minutes lost on EITHER side; Over is hurt, Under helped
    (fewer good players = fewer points: a lean, not proof);
  * any other market: NOT JUDGED. Missing report / box scores: PENDING (HR35), never guessed.

Levels follow football: CAUTION at 12% of minutes lost, RISK at 25% (a starter is about 13%).
RECORDED ONLY: nothing here drops, restakes or re-prices a pick. It writes output/nba_team_news/<date>.jsonl so
the verdicts can be graded against results before they are ever allowed to matter.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from data import nba_players as npl

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "nba_team_news"
CAUTION_SHARE, RISK_SHARE = 0.12, 0.25
GAP = 0.08                       # the other side must be this much less hit for "hurt" / "helped" to stand

WINNER_MARKETS = {"219", "223", "88"}
TEAM_TOTAL = {"227": "home", "69": "home", "756": "home", "228": "away", "70": "away", "757": "away"}
GAME_TOTAL = {"225", "68", "236", "90", "18"}


def pick_side(market_id: str, outcome: str) -> Optional[str]:
    """'home' / 'away' for a pick that leans on one team, else None."""
    o = (outcome or "").lower()
    if market_id in WINNER_MARKETS:
        return "home" if o.startswith("home") else "away" if o.startswith("away") else None
    return TEAM_TOTAL.get(market_id)


def sits_chance(status: str) -> float:
    """Chance a listed player does not play (Out 1, Doubtful .75, Questionable .5, Day-To-Day .4)."""
    if status in npl.OUT:
        return 1.0
    p_play = npl.DOUBT.get(status)
    return 0.0 if p_play is None else round(1 - p_play, 2)


def team_loss(rows: list[dict], team: str, injured: Optional[list[dict]]) -> dict:
    """{team, lost_share, missing:[{name,status,min}], pending}: how much of the team's minutes sit out."""
    if injured is None:
        return {"team": team, "lost_share": None, "missing": [], "pending": "injury report unreadable"}
    players, n_games, _ = npl.player_lines(rows, team)
    if n_games < npl.MIN_GAMES:
        return {"team": team, "lost_share": None, "missing": [], "pending": f"{n_games} games logged"}
    mins = {p["id"]: (p["min10"] if p["min10"] is not None else p["min"]) or 0.0 for p in players}
    total = sum(mins.values())
    if total <= 0:
        return {"team": team, "lost_share": None, "missing": [], "pending": "no minutes logged"}
    lost, missing = 0.0, []
    for i in injured:
        w = sits_chance(i.get("status", ""))
        m = mins.get(i.get("id"), 0.0)
        if w > 0 and m > 0:
            lost += w * m
            missing.append({"name": i.get("name", ""), "status": i["status"], "min": round(m, 1)})
    missing.sort(key=lambda x: -x["min"])
    return {"team": team, "lost_share": round(lost / total, 3), "missing": missing, "pending": None}


def level(share: Optional[float]) -> str:
    if share is None:
        return "PENDING"
    return "RISK" if share >= RISK_SHARE else "CAUTION" if share >= CAUTION_SHARE else "OK"


def assess(market_id: str, outcome: str, home: dict, away: dict) -> dict:
    """{verdict: HURT|HELPED|NEUTRAL|NOT JUDGED|PENDING, level, side, note} for one pick."""
    side = pick_side(market_id, outcome)
    over = (outcome or "").lower().startswith("over")
    under = (outcome or "").lower().startswith("under")
    if side is None and market_id not in GAME_TOTAL:
        return {"verdict": "NOT JUDGED", "level": None, "side": None, "note": f"market {market_id} is not judged"}
    sides = [side] if side else ["home", "away"]
    teams = {"home": home, "away": away}
    shares = [teams[s]["lost_share"] for s in sides]
    if any(s is None for s in shares):
        why = "; ".join(f"{teams[s]['team']}: {teams[s]['pending']}" for s in sides if teams[s]["lost_share"] is None)
        return {"verdict": "PENDING", "level": "PENDING", "side": side, "note": why}

    def names(t: dict) -> str:
        return ", ".join(f"{m['name']} ({m['status']})" for m in t["missing"][:3]) or "none"

    if market_id in WINNER_MARKETS:
        mine, theirs = teams[side], teams["away" if side == "home" else "home"]
        gap = mine["lost_share"] - theirs["lost_share"]
        if mine["lost_share"] >= CAUTION_SHARE and gap >= GAP:
            v, note = "HURT", f"{mine['team']} short {mine['lost_share']:.0%} of minutes: {names(mine)}"
        elif theirs["lost_share"] >= CAUTION_SHARE and -gap >= GAP:
            v, note = "HELPED", f"{theirs['team']} short {theirs['lost_share']:.0%} of minutes: {names(theirs)}"
        else:
            v, note = "NEUTRAL", f"{mine['team']} {mine['lost_share']:.0%} v {theirs['team']} {theirs['lost_share']:.0%} of minutes lost"
        return {"verdict": v, "level": level(mine["lost_share"]), "side": side, "note": note}
    lost = shares[0] if side else round(sum(shares), 3)
    if lost >= CAUTION_SHARE and (over or under):
        who = ", ".join(t["team"] for t in (teams[s] for s in sides) if t["missing"])
        v = "HURT" if over else "HELPED"
        note = f"{who} short {lost:.0%} of minutes (fewer scorers): " + "; ".join(names(teams[s]) for s in sides)
    else:
        v, note = "NEUTRAL", f"{lost:.0%} of minutes lost" + (" (both teams)" if not side else "")
    return {"verdict": v, "level": level(lost), "side": side, "note": note}


def assess_game(rows: list[dict], home_abbr: str, away_abbr: str, inj: Optional[dict],
                picks: list[dict]) -> list[dict]:
    """One verdict per pick of one game. `inj` = data.nba_players.injuries(summary), None when unreadable."""
    h = team_loss(rows, home_abbr, None if inj is None else inj.get(home_abbr, []))
    a = team_loss(rows, away_abbr, None if inj is None else inj.get(away_abbr, []))
    return [{"event_id": p.get("event_id"), "pick": p.get("pick"), "market_id": p.get("market_id"),
             **assess(str(p.get("market_id")), p.get("outcome", ""), h, a)} for p in picks]


def record(day: str, now_iso: str, game: str, verdicts: list[dict], out_dir: Path = OUT_DIR) -> None:
    """Append the verdicts (record only) so they can be graded against results later."""
    if not verdicts:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{day}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        for v in verdicts:
            f.write(json.dumps({"at": now_iso, "game": game, **v}) + "\n")


def changes(verdicts: list[dict], seen: dict) -> list[str]:
    """Alert lines for picks whose HURT / HELPED verdict is new or changed since last round (state `seen`)."""
    out = []
    for v in verdicts:
        key = f"{v['event_id']}|{v['market_id']}|{v['pick']}"
        now = v["verdict"] if v["verdict"] in ("HURT", "HELPED") else "NEUTRAL"
        if seen.get(key, "NEUTRAL") != now:
            out.append(f"{v['pick']} - NEWS {now}: {v['note']} (recorded only, no stake change)")
        seen[key] = now
    return out
