"""Booking Tracker — wire PRODUCE BET → tracker.place and VERIFY RESULTS → tracker.settle.

THREE integration points for the bridge
  1. place(accas)       – called by run_daily after production: the board's acca
                          set is written to output/boards/produced_<date>.json.
                          Returns {"placed": N, "skipped": M, "errors": [...]}.
  2. settle(date)       – called by run_daily the next day: each leg in produced
                          <date>.json is graded against football-data result.
                          Returns {"settled": N, "pending": M, "wins": W}.
  3. status(date?)      – returns current state of produced-<date>.json: counts
                          by final status + per-leg detail.

CALL SEQUENCE (run_daily produces a bet)
  07:00 run:
    olp_xdv_pipeline.run_pipeline() -> board (list of acca dicts, each with "legs")
    booking_tracker.place(board["accas"]) -> writes produced_<date>.json
    status = booking_tracker.status(today) -> summary for Telegram/dashboard

  N+1 run:
    settlement = booking_tracker.settle(today - 1) -> grades yesterday's legs
    produced_bet.verify_produced_bet() also runs (existing path) and updates the
    brain. Both paths write the same produced_<date>.json — tracker.settle is the
    simpler thin wrapper; verify_produced_bet covers brain sync + stats.

HR35: NO fabrication. If a result is missing from football-data + ESPN, the
leg stays PENDING — never guessed, never silently degraded to LOSS.

This module is importable by:
  • Python run_daily.py               (tracker.place / tracker.settle)
  • TypeScript bridge.ts  (spawn "py -m bets.booking_tracker <subcommand>")
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Re-use the existing produced_bet + markets + brain machinery
import bets.produced_bet as produced_bet
from engine import markets as mkt
from brain.store import Brain

sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "boards"


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------

def _produced_path(target_date: str | date | None = None) -> Path:
    """Path to the produced_<date>.json for the given date."""
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()
    return OUTPUT_DIR / f"produced_{target_date}.json"


def _load_produced(target_date: str | date | None = None) -> dict:
    """Load produced_<date>.json. Returns empty template if missing."""
    p = _produced_path(target_date)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": str(target_date or date.today()), "accas": [], "settled": False}


def _save_produced(data: dict) -> None:
    """Atomically replace produced_<date>.json."""
    p = _produced_path(data["date"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _leg_key(leg: dict) -> str:
    """Stable identity key for a single leg (fixture + market + pick)."""
    return "|".join([
        leg.get("fixture", leg.get("label", "")).strip(),
        leg.get("market_key", "").strip(),
        leg.get("pick", "").strip(),
    ])


# ---------------------------------------------------------------------------
# PLACE — write produced_<date>.json from the day's board accas
# ---------------------------------------------------------------------------

def place(
    accas: list[dict],
    target_date: str | date | None = None,
) -> dict[str, Any]:
    """BOOK the produced bet: write produced_<date>.json from board accas.

    Each element of `accas` must be a dict with:
      - label  (str, e.g. "Acca 1")
      - legs   (list of leg dicts; each leg has fixture/league/market_key/pick/
               price/prob/ev/edge/verification_stamp — same shape as produced_bet)

    Returns:
      {
        "date": "<iso>",
        "placed": <int>,       # accas written
        "skipped": <int>,      # accas with no legs
        "accas": <list>,       # full acca list with per-leg status
        "errors": [<str>],
      }
    """
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    placed: list[dict] = []
    skipped = 0
    errors: list[str] = []

    for acca in accas:
        legs = acca.get("legs") or []
        if not legs:
            skipped += 1
            errors.append(f"{acca.get('label', '?')}: empty legs — skipped")
            continue

        legs_out: list[dict] = []
        for leg in legs:
            _pick = (
                leg.get("pick")
                or leg.get("market_name", "")
            ).strip()
            legs_out.append({
                "fixture": leg.get("fixture", leg.get("label", "")).strip(),
                "league": leg.get("league", "").strip(),
                "market_key": leg.get("market_key", "").strip(),
                "market_name": leg.get("market_name", "").strip(),
                "pick": _pick,
                "price": leg.get("price"),
                "prob": leg.get("prob"),
                "ev": leg.get("ev"),
                "edge": leg.get("edge"),
                "verification_stamp": leg.get("verification_stamp", ""),
                # field consumed by produced_bet.verify_produced_bet next day
                "status": "PENDING",
            })
        placed.append({
            "label": acca.get("label", f"Acca {len(placed)+1}"),
            "combined_odds": acca.get("combined_odds"),
            "combined_prob": acca.get("combined_prob"),
            "n_legs": len(legs_out),
            "legs": legs_out,
        })

    record = {
        "date": target_date,
        "settled": False,
        "accas": placed,
    }
    _save_produced(record)
    return {
        "date": target_date,
        "placed": len(placed),
        "skipped": skipped,
        "accas": placed,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# SETTLE — grade legs in produced_<date>.json against actual results
# ---------------------------------------------------------------------------

def settle(target_date: str | date | None = None) -> dict[str, Any]:
    """SETTLE one day's produced bet: grade each leg via football-data + ESPN.

    Reads produced_<date>.json, for each PENDING leg:
      1. Look up the result via data.football_data_source + fallback ESPN.
      2. Settle with engine.markets.settle(pick, fthg, ftag).
      3. Mark leg.status = WIN / LOSS / PENDING and write ft_result + hit.

    Calls brain.record_outcomes so graded_yesterday / rolling_7d / stats populate
    (mirrors what produced_bet.verify_produced_bet does).

    Returns:
      {
        "date": "<iso>",
        "settled": <int>,     # legs finalised (WIN or LOSS)
        "pending": <int>,     # legs still missing results
        "wins": <int>,        # wins out of settled
        "losses": <int>,      # losses out of settled
        "legs": [<per-leg>],  # each with status, hit, ft_result or "PENDING"
        "errors": [<str>],
      }
    """
    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    record = _load_produced(target_date)
    if not record.get("accas"):
        return {"date": target_date, "settled": 0, "pending": 0,
                "wins": 0, "losses": 0, "legs": [], "errors": ["no produced bet"]}

    try:
        from data.football_data_source import load_league, MatchResult
        _fd = True
    except ImportError:
        _fd = False

    try:
        from data.espn_results import fetch_results_for_date
        _espn = True
    except ImportError:
        _espn = False

    # Build result lookup by (league, home, away)
    # Derive season from the record date or fall back to the live season
    _record_date = record.get("date", target_date)
    _year = _record_date[:4] if isinstance(_record_date, str) else ""
    derived_season = f"{int(_year)-1}{_year[2:]}" if len(_year) == 4 else "2526"
    results_map: dict[tuple[str, str, str], dict] = {}
    if _fd:
        seen_leagues: set[str] = set()
        for acca in record.get("accas", []):
            for leg in acca.get("legs", []):
                lg = leg.get("league", "")
                if lg and lg not in seen_leagues:
                    seen_leagues.add(lg)
                    try:
                        rrows, _ = load_league(lg, derived_season)
                        for r in rrows:
                            key = (r.league, r.home_team, r.away_team)
                            results_map[key] = {
                                "fthg": r.fthg,
                                "ftag": r.ftag,
                                "date": r.date,
                            }
                    except (ValueError, OSError):
                        pass
    if _espn:
        try:
            for r in (fetch_results_for_date(target_date) or []):
                results_map[(r.league, r.home_team, r.away_team)] = {
                    "fthg": r.fthg,
                    "ftag": r.ftag,
                    "date": getattr(r, "date", target_date),
                }
        except (OSError, TypeError):
            pass

    settled = 0
    pending = 0
    wins = 0
    losses = 0
    legs_out: list[dict] = []
    errors: list[str] = []

    for acca in record.get("accas", []):
        for leg in acca.get("legs", []):
            out: dict[str, Any] = dict(leg)
            pick = (leg.get("pick") or "").strip()
            mkt_key = (leg.get("market_key") or "").strip()
            fixture_raw = leg.get("fixture", "")
            league = leg.get("league", "")

            # Pick the h/a side from the fixture string: "Home v Away"
            # or "Home vs Away"
            parts = fixture_raw.replace(" vs ", " v ").split(" v ", 1)
            home = parts[0].strip() if parts else ""
            away = parts[1].strip() if len(parts) > 1 else ""

            res = results_map.get((league, home, away))
            if not res and home and away:
                # strip common FC / suffixes to widen match
                for k, v in results_map.items():
                    if len(k) == 3:
                        lg_k, h_k, a_k = k
                        # normalise trailing FC / FC / CF / Town
                        def _norm(s: str) -> str:
                            for suf in (" FC", " CF", " Town", " United"):
                                if s.endswith(suf):
                                    return s[: -len(suf)].strip()
                            return s.strip()
                        if (lg_k == league
                                and _norm(h_k) == _norm(home)
                                and _norm(a_k) == _norm(away)):
                            res = v
                            break

            if not res or res.get("fthg") is None or res.get("ftag") is None:
                out["status"] = "PENDING"
                out["ft_result"] = "NO DATA — PENDING"
                out["hit"] = None
                pending += 1
                legs_out.append(out)
                continue

            fthg = int(res["fthg"])
            ftag = int(res["ftag"])
            try:
                hit: bool | None = mkt.settle(mkt_key, fthg, ftag)
            except Exception as exc:
                out["status"] = "PENDING"
                out["ft_result"] = f"{fthg}-{ftag} (settle error: {exc})"
                out["hit"] = None
                pending += 1
                errors.append(f"{fixture_raw}: {exc}")
                legs_out.append(out)
                continue

            out["fthg"] = fthg
            out["ftag"] = ftag
            out["ft_result"] = f"{fthg}-{ftag}"
            if hit:
                out["status"] = "WIN"
                wins += 1
            else:
                out["status"] = "LOSS"
                losses += 1
            out["hit"] = hit
            settled += 1
            legs_out.append(out)

    # Update the legs in the record, preserving the acca structure
    acca_iter = iter(legs_out)
    new_accas: list[dict] = []
    for acca in record.get("accas", []):
        updated_legs = [next(acca_iter) for _ in acca.get("legs", [])]
        new_accas.append({**acca, "legs": updated_legs})
    record["accas"] = new_accas
    record["settled"] = True
    _save_produced(record)

    # Mirror the outcomes into the brain so graded_yesterday / rolling_7d / stats
    # populate, exactly like produced_bet.verify_produced_bet does.
    try:
        _sync_brain(target_date, record)
    except (OSError, Exception):
        errors.append("brain sync failed")

    return {
        "date": target_date,
        "settled": settled,
        "pending": pending,
        "wins": wins,
        "losses": losses,
        "legs": legs_out,
        "errors": errors,
    }


def _sync_brain(target_date: str | date, record: dict) -> None:
    """Mirror produced-bet outcomes into brain.record_outcomes (best-effort)."""
    try:
        brain = Brain()
    except (OSError, Exception):
        return
    season = produced_bet._current_season()
    try:
        brain.record_outcomes(
            season=season,
            date_str=str(target_date),
            legs=[leg for acca in record.get("accas", [])
                  for leg in acca.get("legs", [])],
        )
        brain.sync_produced_bets(season)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# STATUS — inspect produced_<date>.json
# ---------------------------------------------------------------------------

def status(
    target_date: str | date | None = None,
) -> dict[str, Any]:
    """Return a summary of the produced bet for the given date.

    If no date is provided, today is used.
    """
    record = _load_produced(target_date)

    total_legs = 0
    statuses: dict[str, int] = {}
    legs: list[dict] = []

    for acca in record.get("accas", []):
        for leg in acca.get("legs", []):
            statuses[leg.get("status", "UNKNOWN")] = statuses.get(leg.get("status", "UNKNOWN"), 0) + 1
            legs.append({
                "acca": acca.get("label", "?"),
                "fixture": leg.get("fixture", ""),
                "pick": leg.get("pick", ""),
                "price": leg.get("price"),
                "status": leg.get("status", "UNKNOWN"),
                "ft_result": leg.get("ft_result"),
                "hit": leg.get("hit"),
            })
            total_legs += 1

    return {
        "date": record.get("date", str(date.today())),
        "n_accas": len(record.get("accas", [])),
        "n_legs": total_legs,
        "statuses": statuses,
        "legs": legs,
        "settled": record.get("settled", False),
    }


# ---------------------------------------------------------------------------
# CLI entry point — used by bridge.ts spawn and for ad-hoc runs
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="booking_tracker CLI")
    sub = p.add_subparsers(dest="cmd")

    # place
    sp_place = sub.add_parser("place")
    sp_place.add_argument("--date")
    sp_place.add_argument("accas_json", nargs="?", default="-")

    # settle
    sp_settle = sub.add_parser("settle")
    sp_settle.add_argument("--date")

    # status
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--date")

    args = p.parse_args()
    if args.cmd == "place":
        if args.accas_json == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.accas_json).read_text(encoding="utf-8")
        accas = json.loads(raw)
        result = place(accas, target_date=args.date)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif args.cmd == "settle":
        result = settle(target_date=args.date)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif args.cmd == "status":
        result = status(target_date=args.date)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _main()