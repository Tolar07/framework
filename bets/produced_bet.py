"""PRODUCED-BET RECORD — the day's produced bet, saved and verified next day.

WHY THIS EXISTS
  A real £1 eight-fold accumulator was placed from a board, and when we went
  looking for "the produced bet" the framework had no record of it. The board
  .txt/.json carry the predictions, but nothing is designated as *the bet
  produced today*, and — the real gap — the daily run never settled its own
  league predictions (only the continental monitor called record_outcomes). So
  a produced bet was invisible the day it was made and unverified the day after.

  This module closes both gaps:
    - record_produced_bet() writes output/boards/produced_<date>.json each run:
      every RATED fixture whose kickoff is TODAY as one leg (pick + model prob
      + best price/EV when present). No fixtures today -> an honest empty
      record ("no bet produced"), still written and findable.
    - verify_produced_bet() runs the NEXT day: settles each pending leg against
      the real result (football-data, same keying + refusal rules as
      grade_open_legs), writes ft_result/hit/settled back to the JSON, and calls
      brain.record_outcomes so graded_yesterday / rolling_7d / /stats populate.

  The JSON is canonical; the brain `produced_bets` table is a queryable mirror
  (synced by brain.sync_produced_bets). This is paper-level — config still
  asserts Phase 2, zero capital; a produced-bet record never carries a stake.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from brain.store import Brain
from data.football_data_source import load_league
from engine import markets as mkt


def _next_season_code(season: str) -> str:
    """'2526' -> '2627'. Same rule as orchestrator.next_season_code, defined
    locally so this module never pulls orchestrator (which imports produce_bet
    -> circular). A result reaches the board only from the season now being
    played, not the completed one the model was fit on."""
    if len(season) != 4 or not season.isdigit():
        raise ValueError(f"Season code must be 4 digits like '2526', got {season!r}")
    return f"{int(season[:2]) + 1:02d}{int(season[2:]) + 1:02d}"

BOARD_DIR = Path(__file__).parent.parent / "output" / "boards"


# --------------------------------------------------------------------------
# record — save today's produced bet
# --------------------------------------------------------------------------

def _league_of(fixture: str) -> str:
    """'Home v Away (League)' -> 'League'. Mirrors the board's league tag."""
    return fixture.split(" (")[-1].rstrip(")") if " (" in fixture else "—"


def _result_pick(probs) -> tuple[str, str, float]:
    """The model's predicted RESULT for a rated fixture as a canonical market
    key + display side + probability. One produced-bet leg per rated fixture,
    pick = the 1X2 argmax (the board's 'AI pick' per match)."""
    side = max((probs.p_home, "1X2_HOME"), (probs.p_draw, "1X2_DRAW"),
               (probs.p_away, "1X2_AWAY"), key=lambda t: t[0])[1]
    prob = {"1X2_HOME": probs.p_home, "1X2_DRAW": probs.p_draw,
            "1X2_AWAY": probs.p_away}[side]
    return side, mkt.display(side, probs.home_team, probs.away_team), prob


def _leg_from_board(bf, run_date: str) -> Optional[dict]:
    """Serialize one rated board fixture into a produced-bet leg. Returns None
    for an unrated fixture (probs is None) — nothing was bet on it (HR35), so
    it is not a leg."""
    if bf.probs is None:
        return None
    pick, pick_name, prob = _result_pick(bf.probs)
    return {
        "date": run_date,
        "leg_id": f"{bf.fixture.split(' (')[0]}_{pick}",
        "fixture": bf.fixture.split(" (")[0],
        "league": _league_of(bf.fixture),
        "pick": pick,            # canonical market key, e.g. "1X2_HOME"
        "pick_name": pick_name,  # words, e.g. "Dundee to win"
        "model_prob": prob,
        "on_deploy_shortlist": bool(bf.on_deploy_shortlist),
        "best_market": bf.best_market,
        "best_price": bf.best_price,
        "best_mes_ev": bf.best_mes_ev,
        "kickoff_date": bf.kickoff_date,
        "ft_result": None,
        "hit": None,
        "settled": False,
    }


def load_produced_bet(run_date: str) -> Optional[dict]:
    """Read back a day's produced-bet record (canonical JSON). None when the
    day has no record — the caller renders the honest empty block."""
    path = BOARD_DIR / f"produced_{run_date}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def record_produced_bet(board, run_date: str, brain: Brain) -> dict:
    """Write the produced-bet record for `run_date` (today): one leg per RATED
    fixture whose kickoff is that date. No fixtures today -> an honest empty
    record, still written. Mirrors legs into the brain. Returns the record."""
    legs = []
    for bf in board:
        if bf.kickoff_date != run_date:
            continue  # today's bet is today's fixtures alone (ID415)
        leg = _leg_from_board(bf, run_date)
        if leg is not None:
            legs.append(leg)

    record = {
        "date": run_date,
        "produced": bool(legs),
        "n_legs": len(legs),
        "note": ("" if legs
                 else "no fixtures today — no bet produced"),
        "legs": legs,
    }
    path = BOARD_DIR / f"produced_{run_date}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    brain.sync_produced_bets(legs)
    return record


# --------------------------------------------------------------------------
# verify — settle yesterday's produced bet, show the result today
# --------------------------------------------------------------------------

def _load_results(league: str, season: str) -> dict:
    """football-data results keyed (home, away, date) for a league across the
    current + next season. Same keying grade_open_legs uses — the date is part
    of the key so a leg can never settle against last season's same-pairing
    meeting."""
    table: dict = {}
    for s in {season, _next_season_code(season)}:
        try:
            res, _ = load_league(league, s)
            table.update({(r.home_team, r.away_team, r.date): r for r in res})
        except Exception:
            continue  # that season simply isn't published yet
    return table


def verify_produced_bet(season: str, brain: Brain,
                        record_date: Optional[str] = None) -> dict:
    """Settle the PREVIOUS day's produced-bet legs against real results and
    record outcomes in the brain so verification is visible next day. Returns a
    summary {date, n, won, lost, pending}.

    A leg with no recorded kickoff date is refused (HR48 — matching on the
    pairing alone fabricated results before); a leg whose match has no result
    yet stays PENDING (ID48 — never guessed)."""
    day = record_date or (date.today() - timedelta(days=1)).isoformat()
    path = BOARD_DIR / f"produced_{day}.json"
    if not path.exists():
        return {"date": day, "n": 0, "won": 0, "lost": 0, "pending": 0,
                "note": "no produced-bet record for this date"}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"date": day, "n": 0, "won": 0, "lost": 0, "pending": 0,
                "note": "produced-bet record unreadable — left untouched"}

    legs = record.get("legs") or []
    results_by_league: dict[str, dict] = {}
    settled = won = lost = 0
    for leg in legs:
        if leg.get("settled"):
            continue  # already verified — first result wins
        if not leg.get("kickoff_date"):
            continue  # cannot match without the date (HR48) — stays PENDING
        league = leg.get("league") or "—"
        if league not in results_by_league:
            results_by_league[league] = _load_results(league, season)
        home, away = [s.strip() for s in leg["fixture"].split(" v ", 1)]
        match = results_by_league[league].get((home, away, leg["kickoff_date"]))
        if match is None:
            continue  # not played/published yet — remains PENDING (ID48)
        hit = mkt.settle(leg["pick"], match.fthg, match.ftag)
        if hit is None:
            continue  # no settlement rule for this market — PENDING
        leg["ft_result"] = f"{match.fthg}-{match.ftag}"
        leg["hit"] = bool(hit)
        leg["settled"] = True
        settled += 1
        won += int(hit)
        lost += int(not hit)

        # Record outcomes for the whole fixture so graded_yesterday / rolling
        # stats / /stats populate — not just the produced pick. This is the
        # missing daily-run settlement the continental monitor used to be the
        # only caller of.
        hits = {}
        for market in mkt.ALL:
            h = mkt.settle(market, match.fthg, match.ftag)
            if h is not None:
                hits[market] = h
        if hits:
            brain.record_outcomes(leg["fixture"], leg["kickoff_date"],
                                  leg["ft_result"], hits)

    record["legs"] = legs
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    brain.sync_produced_bets(legs)
    return {"date": day, "n": len(legs), "won": won, "lost": lost,
            "pending": len(legs) - settled}


# --------------------------------------------------------------------------
# render — the board / Telegram block
# --------------------------------------------------------------------------

def render_produced_bet(record: Optional[dict]) -> str:
    """The day's SCAN RECORD block: one paper leg per RATED fixture kicking off
    today (pick + model prob + best price/EV when present). This is the ID415
    paper trail the next day's verification settles — it is NOT a production
    recommendation, and the header says so (HR53): the actual production pick,
    if any, lives in the separate PRODUCTION BETS block. Away picks appear here
    as the model's raw prediction only, never as a recommendation (ID405)."""
    if not record:
        return ("📋 SCAN RECORD — today's rated fixtures (paper, ID415)\n"
                "No produced-bet record yet.")
    if not record.get("produced"):
        return ("📋 SCAN RECORD — today's rated fixtures (paper, ID415)\n"
                "No rated fixtures today — no bet recorded. A valid, honest "
                "result (ID415).")
    lines = [f"📋 SCAN RECORD — today's rated fixtures — {record.get('date', '')} "
             "(paper, ID415)",
             f"{record.get('n_legs', 0)} rated fixture(s) today. This is the "
             "scan's paper record, NOT a recommendation — the production pick "
             "(if any) is in PRODUCTION BETS below. MARKED PAPER — the scan "
             "itself never carries a stake (capital is the Architect's).", ""]
    for i, leg in enumerate(record.get("legs") or [], 1):
        L = [f"{i}. {leg.get('fixture', '?')} ({leg.get('league', '?')})"]
        L.append(f"   Pick: {leg.get('pick_name', leg.get('pick', '?'))} "
                 f"({round((leg.get('model_prob') or 0) * 100)}%)")
        if leg.get("best_price") is not None:
            ev = leg.get("best_mes_ev")
            ev_txt = f"{ev:+.2%} EV" if ev is not None else "EV NO DATA"
            L.append(f"   Best market: {leg.get('best_market', '?')} at "
                     f"{leg['best_price']:.2f} — {ev_txt}")
        if leg.get("settled"):
            mark = "✓" if leg.get("hit") else "✗"
            L.append(f"   Verified: {mark} {leg.get('ft_result', '?')}")
        lines.append("\n".join(L))
    if any((leg.get("pick") or "").endswith("_AWAY")
           for leg in record.get("legs") or []):
        lines.append("Away picks are the model's prediction only — never "
                     "recommended (ID405).")
    return "\n".join(lines)
