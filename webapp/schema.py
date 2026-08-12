"""Board JSON schema — the contract the web dashboard (local server AND hosted
static export) reads.

run_daily writes `output/boards/board_<date>.json` next to the .txt each run.
The web layer is strictly read-only over that JSON + the brain — it never
re-runs the pipeline, never writes back, and never fabricates (HR35: a missing
field renders NO DATA — PENDING, never a guess).

Only JSON-safe primitives leave this module: dataclasses and tuples are
converted here, so a consumer never touches engine objects.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from output.produce_bet import BoardFixture
from engine.dixon_coles import FixtureProbabilities

SCHEMA_VERSION = 1


def _opt(x) -> Any:
    return None if x is None else x


def _consensus_to_dict(c) -> Any:
    """The cross-engine vote (ID412), JSON-safe, or None when absent."""
    if c is None:
        return None
    return {
        "result": _opt(c.result),
        "votes": dict(c.votes),
        "n_engines": c.n_engines,
        "agreeing": c.agreeing,
        "avg_home": _opt(c.avg_home),
        "avg_draw": _opt(c.avg_draw),
        "avg_away": _opt(c.avg_away),
        "split": c.split,
    }


def probs_to_dict(p: FixtureProbabilities) -> dict:
    return {
        "home_team": p.home_team,
        "away_team": p.away_team,
        "lambda_home": _opt(p.lambda_home),
        "lambda_away": _opt(p.lambda_away),
        "p_home": _opt(p.p_home),
        "p_draw": _opt(p.p_draw),
        "p_away": _opt(p.p_away),
        "p_over_15": _opt(p.p_over_15),
        "p_over_25": _opt(p.p_over_25),
        "p_over_35": _opt(p.p_over_35),
        "p_btts_yes": _opt(p.p_btts_yes),
        # ID414: the true modal scoreline from the Poisson matrix
        "modal_scoreline": list(p.modal_scoreline) if p.modal_scoreline else None,
    }


def fixture_to_dict(bf: BoardFixture) -> dict:
    """Every BoardFixture field, JSON-safe. Tuples (elo/xg) become lists."""
    # Build per-engine predicted result + modal scoreline for ScoreGPT's
    # "Model picks" expander (ID414).
    engine_picks = {}
    if bf.probs is not None:
        # DC pick
        dc_side = max(
            (("HOME", bf.probs.p_home), ("DRAW", bf.probs.p_draw), ("AWAY", bf.probs.p_away)),
            key=lambda t: t[1]
        )[0]
        engine_picks["Dixon-Coles"] = {
            "result": dc_side,
            "scala scoreline": list(bf.probs.modal_scoreline) if bf.probs.modal_scoreline else None
        }
        # Elo pick
        if bf.elo_probs:
            elo_side = max(
                (("HOME", bf.elo_probs[0]), ("DRAW", bf.elo_probs[1]), ("AWAY", bf.elo_probs[2])),
                key=lambda t: t[1]
            )[0]
            engine_picks["Elo"] = {"result": elo_side}
        # xG pick
        if bf.xg_probs:
            xg_side = max(
                (("HOME", bf.xg_probs[0]), ("DRAW", bf.xg_probs[1]), ("AWAY", bf.xg_probs[2])),
                key=lambda t: t[1]
            )[0]
            engine_picks["xG"] = {"result": xg_side}
        # Bookmaker pick
        if bf.market_probs:
            bm_side = max(
                (("HOME", bf.market_probs[0]), ("DRAW", bf.market_probs[1]), ("AWAY", bf.market_probs[2])),
                key=lambda t: t[1]
            )[0]
            engine_picks["Bookmaker"] = {"result": bm_side}
    # Consensus pick (majority result + averaged modal scoreline)
    consensus_pick = None
    if bf.consensus and bf.consensus.result:
        consensus_pick = {
            "result": bf.consensus.result,
            "agreeing": bf.consensus.agreeing,
            "n_engines": bf.consensus.n_engines,
            "avg_scoreline": [bf.consensus.avg_home, bf.consensus.avg_draw, bf.consensus.avg_away]
        }

    return {
        "fixture": bf.fixture,
        "probs": probs_to_dict(bf.probs) if bf.probs is not None else None,
        "on_deploy_shortlist": bf.on_deploy_shortlist,
        "mes_trigger_price": _opt(bf.mes_trigger_price),
        "rejection_reason": _opt(bf.rejection_reason),
        "best_market": _opt(bf.best_market),
        "best_market_key": _opt(bf.best_market_key),
        "best_price": _opt(bf.best_price),
        "best_bookmaker": _opt(bf.best_bookmaker),
        "best_n_books": bf.best_n_books,
        "best_mes_ev": _opt(bf.best_mes_ev),
        "best_model_prob": _opt(bf.best_model_prob),
        "cal_adjustment": _opt(bf.cal_adjustment),
        "kickoff_date": _opt(bf.kickoff_date),
        "elo_probs": list(bf.elo_probs) if bf.elo_probs else None,
        "engine_divergence": _opt(bf.engine_divergence),
        "xg_probs": list(bf.xg_probs) if bf.xg_probs else None,
        # Phase 3.4: xG's goals-market read (O1.5/O2.5/O3.5/BTTS) + the
        # DC-vs-xG goals divergence flag. Admin-only (trim_payload drops them).
        "xg_goals": list(bf.xg_goals) if bf.xg_goals else None,
        "goals_divergence": _opt(bf.goals_divergence),
        "market_probs": list(bf.market_probs) if bf.market_probs else None,
        "consensus": _consensus_to_dict(bf.consensus),
        "engine_picks": engine_picks,
        "consensus_pick": consensus_pick,
        "model_engine": bf.model_engine,
        "verification": {
            "tier": str(getattr(bf.verification.tier, "name", bf.verification.tier)),
            "note": _opt(bf.verification.note),
        },
    }


def board_to_dict(board: list[BoardFixture]) -> list[dict]:
    return [fixture_to_dict(bf) for bf in board]


def build_payload(*, date: str, phase: str, leagues_scanned: list[str],
                  board: list[BoardFixture], data_flags: list[str],
                  gate: dict, telemetry: dict,
                  calibration_count: int, mean_clv: Optional[float],
                  recommendation: str = "",
                  yesterday_graded: Optional[list] = None,
                  rolling_7d: Optional[dict] = None,
                  produced_bet: Optional[dict] = None,
                  accas: Optional[list] = None) -> dict:
    """The full board_<date>.json payload, ready to write to disk.

    `recommendation` is the already-rendered ⭐ TODAY'S PICKS parlay text
    (produce_bet.render_daily_recommendation) — computed from the REAL
    BoardFixture list at run time so the web never re-implements the pick
    rule and drifts from the phone board.

    `yesterday_graded` — list of graded fixtures for the ScoreGPT "Yesterday"
    section (ID414). Each has fixture, league, outcome, engines with per-market
    prob+hit.

    `rolling_7d` — rolling 7-day aggregates for the ScoreGPT stats bar (ID414).
    Contains engine hit rates, legs logged, CLV capture, gate progress.

    `produced_bet` — the day's produced-bet record (ID415): one leg per rated
    fixture with a kickoff today, plus the verified outcome (WON/LOST) once
    yesterday's record is settled next day. The FULL record (model prob,
    best EV) is admin-visible; trim_payload reduces it to a
    client-safe form (fixture + pick + price + outcome only).

    `accas` — the day's 4-leg acca set (standing rule 2026-08-09), as the
    acca_<date>.json payload. Admin keeps every leg field (incl. EV); the
    client-safe trim keeps fixture + market + price + probability only.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "date": date,
        "phase": phase,
        "leagues_scanned": sorted(leagues_scanned),
        "n_leagues": len(leagues_scanned),
        "data_flags": data_flags,
        "gate": gate,
        "telemetry": telemetry,
        "calibration_count": calibration_count,
        "mean_clv": mean_clv,
        "recommendation": recommendation,
        "board": board_to_dict(board),
    }
    if yesterday_graded is not None:
        payload["yesterday_graded"] = yesterday_graded
    if rolling_7d is not None:
        payload["rolling_7d"] = rolling_7d
    if produced_bet is not None:
        payload["produced_bet"] = produced_bet
    if accas is not None:
        payload["accas"] = accas
    return payload


def write_payload(payload: dict, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Client-safe trimming — the PUBLIC data-leak boundary
# ─────────────────────────────────────────────────────────────────────────────
# The /dashboard route, the public /api/board.json, and the static export are
# all served from `trim_payload`. It keeps exactly the fields the client
# dashboard renders (fixture, the market probabilities the full-analysis grid
# is derived from, the pick and its price) and strips the diagnostic layer —
# Elo/xG second opinions, engine divergence, consensus votes, verification,
# EV/CLV verdicts, calibration, the gate, data flags, yesterday-graded and
# rolling stats. The client browser therefore NEVER receives a model internal,
# by construction (Architect order, 2026-08-07).
CLIENT_PROBS_KEYS = frozenset({
    "home_team", "away_team",
    "p_home", "p_draw", "p_away",
    "p_over_15", "p_over_25", "p_over_35",
    "p_btts_yes",
})
CLIENT_FIXTURE_KEYS = frozenset({
    "fixture", "probs", "on_deploy_shortlist",
    "best_market", "best_market_key", "best_model_prob",
    "mes_trigger_price", "rejection_reason",
    "kickoff_date",  # factual datum (not a model internal); needed for the
                     # today-only call filter (standing rule 2026-08-09)
})
CLIENT_TOP_KEYS = frozenset({
    "schema_version", "date", "phase",
    "leagues_scanned", "n_leagues", "board",
})
# The produced-bet record is the ONE deliberate narrowing of the 2026-08-07
# data-leak boundary (ratified ID415): the client dashboard shows what the
# framework bet (fixture, pick, price) and the verified result (WON/LOST) —
# the point of the produced-bet feature. Model prob, deploy
# shortlist and EV/CLV verdicts stay admin-only.
CLIENT_PRODUCED_BET_KEYS = frozenset({
    "fixture", "league", "pick", "pick_name",
    "best_market", "best_price", "kickoff_date",
    "ft_result", "hit", "settled",
})
_CLIENT_PRODUCED_RECORD_KEYS = frozenset({
    "date", "produced", "n_legs", "note",
})


def _client_safe_produced(record: dict) -> dict:
    """The produced-bet record as the client may see it: fixture + pick +
    price + verified outcome, no model internals (ID415)."""
    out = {k: record[k] for k in _CLIENT_PRODUCED_RECORD_KEYS if k in record}
    legs = []
    for leg in record.get("legs") or []:
        lb = {k: leg[k] for k in CLIENT_PRODUCED_BET_KEYS if k in leg}
        legs.append(lb)
    out["legs"] = legs
    return out


_CLIENT_ACCA_KEYS = ("label", "combined_odds", "combined_prob", "n_legs")
_CLIENT_ACCA_LEG_KEYS = ("fixture", "league", "market_name", "price", "prob")


def _client_safe_accas(accas: list[dict]) -> list[dict]:
    """The acca set as the client may see it: fixture + market + price +
    probability + combined figures — no EV, no market keys (model internals).
    The full leg list (with EV) stays admin-only."""
    out = []
    for acca in accas:
        a = {k: acca[k] for k in _CLIENT_ACCA_KEYS if k in acca}
        a["legs"] = [{k: leg[k] for k in _CLIENT_ACCA_LEG_KEYS if k in leg}
                     for leg in acca.get("legs") or []]
        out.append(a)
    return out


def trim_payload(payload: dict) -> dict:
    """The public-facing payload — predictions only, no model internals.

    Never mutates the source payload; builds fresh dicts. A fixture's `probs`
    is reduced to the market-probability fields the grid needs (lambdas and the
    modal scoreline are Dixon-Coles internals and are dropped). The produced-bet
    record (ID415) passes through in a reduced client-safe form."""
    trimmed_board = []
    for bf in payload.get("board", []):
        tb = {k: bf[k] for k in CLIENT_FIXTURE_KEYS if k in bf}
        p = bf.get("probs")
        if p is not None:
            tb["probs"] = {k: p[k] for k in CLIENT_PROBS_KEYS if k in p}
        else:
            tb["probs"] = None
        trimmed_board.append(tb)
    out = {k: payload[k] for k in CLIENT_TOP_KEYS if k in payload}
    out["board"] = trimmed_board
    if payload.get("produced_bet") is not None:
        out["produced_bet"] = _client_safe_produced(payload["produced_bet"])
    if payload.get("accas") is not None:
        out["accas"] = _client_safe_accas(payload["accas"])
    return out


class ClientPublishGateError(RuntimeError):
    """Raised when attempting to publish to client before Phase 3 gate is met."""


def _gate_state(admin_payload: dict) -> dict:
    """Compute the publish-gate state: the statistical gate + Architect override.

    The statistical gate is `legs_with_clv >= gate_requirement` AND
    `mean_clv_pct is not None and > 0`. `ARCHITECT_SIGNOFF=1` is the Architect's
    explicit override of that statistical gate (Architect 2026-08-10): it does
    NOT pretend the gate is met — it records that the Architect chose to publish
    knowing the evidence, so `override` stays visible in the audit trail and the
    honest-edge statement is never removed from the client view."""
    gate = admin_payload.get("gate", {})
    legs_with_clv = gate.get("legs_with_clv", 0)
    mean_clv = gate.get("mean_clv_pct")
    gate_req = gate.get("gate_requirement", 30)
    gate_met = (legs_with_clv >= gate_req) and (mean_clv is not None and mean_clv > 0)
    signoff = os.environ.get("ARCHITECT_SIGNOFF", "0").strip().lower()
    signed_off = signoff in ("1", "true", "yes")
    return {
        "legs_with_clv": legs_with_clv,
        "gate_requirement": gate_req,
        "mean_clv_pct": mean_clv,
        "gate_met": gate_met,
        "architect_signed_off": signed_off,
        "override": (not gate_met) and signed_off,
    }


def check_client_publish_gate(admin_payload: dict, require_architect_signoff: bool = True) -> dict:
    """
    Hard gate: publishing to the client-facing dashboard is blocked until the
    Phase 3 CLV gate is met (≥30 legs with logged CLV + positive mean CLV +
    Architect sign-off), OR the Architect explicitly overrides it.

    Architect override (2026-08-10): `ARCHITECT_SIGNOFF=1` bypasses the
    statistical gate. The Architect is publish authority — the same authority
    they hold over capital (config.assert_paper_only()). The override is never
    silent: write_published stamps `_gate_state` (gate numbers + override) into
    the audit log, and the honest-edge statement stays in the client view.

    Args:
        admin_payload: The full board payload (must include 'gate' dict with
                       legs_with_clv, mean_clv_pct, gate_requirement)
        require_architect_signoff: If True, also requires ARCHITECT_SIGNOFF=1 in env

    Returns:
        The gate state dict (see _gate_state) — the caller stamps it into the
        audit log so an override is never silent.

    Raises:
        ClientPublishGateError: If the gate is unmet AND no override applies.
    """
    st = _gate_state(admin_payload)
    if st["gate_met"]:
        if require_architect_signoff and not st["architect_signed_off"]:
            raise ClientPublishGateError(
                "Client publish blocked: gate met but Architect sign-off "
                "required — set ARCHITECT_SIGNOFF=1 after reviewing the board."
            )
        return st

    if require_architect_signoff and st["architect_signed_off"]:
        # Architect override — the sign-off IS publish authority.
        return st

    parts = []
    if st["legs_with_clv"] < st["gate_requirement"]:
        parts.append(f"{st['legs_with_clv']}/{st['gate_requirement']} legs "
                     f"with CLV (need ≥{st['gate_requirement']})")
    if st["mean_clv_pct"] is None or st["mean_clv_pct"] <= 0:
        parts.append(f"mean CLV {st['mean_clv_pct']!r} (must be positive)")
    if require_architect_signoff and not st["architect_signed_off"]:
        parts.append("Architect sign-off (set ARCHITECT_SIGNOFF=1)")
    raise ClientPublishGateError("Client publish blocked: " + "; ".join(parts) + ".")


# ─────────────────────────────────────────────────────────────────────────────
# Booking codes — SportyBet codes captured from the day's accas
# ─────────────────────────────────────────────────────────────────────────────
# booking/booking_codes.py writes acca_<date>_codes.json next to the acca
# payload. The /admin view surfaces them so the Architect can paste a code into
# SportyBet to recall the slip — a pre-fill, never a stake (Phase-2 bright
# line). Missing file → None; the renderer says NO DATA — PENDING (HR35).
BOARD_DIR = Path(__file__).parent.parent / "output" / "boards"


def read_booking_codes(date_str: str) -> Optional[dict]:
    """Read the day's SportyBet booking codes, or None when not captured yet.

    Codes are Architect-sensitive (they recall a betslip), so this is an
    admin-only read — the client view never calls it."""
    path = BOARD_DIR / f"acca_{date_str}_codes.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Guard: a codes file must at least carry results; anything else is
        # treated as absent rather than rendered as a fabricated code (HR35).
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Published store — the APPROVE gate boundary
# ─────────────────────────────────────────────────────────────────────────────
# The /admin board is the raw run_daily board (all model internals). The client
# dashboard and static export MUST read from the PUBLISHED store, which is
# written ONLY by the "Approve → Publish to Client" action. This enforces the
# Architect's intent: nothing reaches the client without an explicit approval,
# same principle as capital staying Architect-only.
PUBLISHED_DIR = BOARD_DIR / "published"
AUDIT_LOG = PUBLISHED_DIR / "publish_audit.jsonl"


def _ensure_published_dir() -> None:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)


def list_published_dates() -> list[str]:
    """Return sorted (descending) list of published board dates (YYYY-MM-DD)."""
    _ensure_published_dir()
    dates = [p.stem.replace("board_", "") for p in PUBLISHED_DIR.glob("board_*.json")]
    return sorted(dates, reverse=True)


def read_published(date_str: str) -> dict:
    """Read a published board. Returns trimmed payload (client-safe)."""
    path = PUBLISHED_DIR / f"board_{date_str}.json"
    if not path.exists():
        raise FileNotFoundError(f"no published board for {date_str}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return trim_payload(payload)


def write_published(admin_payload: dict, approved_by: str = "admin") -> Path:
    """Write an admin-reviewed board to the published store + append audit log.

    `admin_payload` is the FULL board payload as seen in admin (with all model
    internals). We store the TRIMMED version and log the action.

    HARD GATE: This call will raise ClientPublishGateError if the Phase 3
    CLV gate is not met (≥30 legs with CLV + positive mean CLV + Architect
    sign-off), unless ARCHITECT_SIGNOFF=1 explicitly overrides it (2026-08-10).
    The gate state — including the override flag and the live gate numbers — is
    stamped into the audit entry so an override is never silent.
    """
    # Hard gate — mirrors config.assert_paper_only() for capital
    gate_state = check_client_publish_gate(admin_payload)

    date_str = admin_payload.get("date", "")
    if not date_str:
        raise ValueError("payload must include 'date'")
    trimmed = trim_payload(admin_payload)
    path = PUBLISHED_DIR / f"board_{date_str}.json"
    _ensure_published_dir()
    path.write_text(json.dumps(trimmed, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    # Append audit log
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "publish",
        "date": date_str,
        "approved_by": approved_by,
        "leagues_scanned": trimmed.get("leagues_scanned", []),
        "n_leagues": trimmed.get("n_leagues", 0),
        "n_fixtures": len(trimmed.get("board", [])),
        "n_rated": sum(1 for bf in trimmed.get("board", []) if bf.get("probs") is not None),
        "schema_version": SCHEMA_VERSION,
        # Gate evidence at publish time (Architect 2026-08-10): the numbers the
        # Architect published against + whether it was an explicit override.
        "gate_at_publish": {
            "legs_with_clv": gate_state["legs_with_clv"],
            "gate_requirement": gate_state["gate_requirement"],
            "mean_clv_pct": gate_state["mean_clv_pct"],
            "gate_met": gate_state["gate_met"],
            "architect_signed_off": gate_state["architect_signed_off"],
            "override": gate_state["override"],
        },
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    return path


def read_audit_log(limit: int = 50) -> list[dict]:
    """Read the publish audit log (most recent first)."""
    if not AUDIT_LOG.exists():
        return []
    entries = []
    with AUDIT_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return list(reversed(entries))[-limit:]


def read_payload(path) -> dict:
    """Read a board JSON. A missing file raises FileNotFoundError (the caller
    turns that into an honest 404/NO DATA, never a guess). A newer schema is
    refused rather than adapted (HR35 — the brain does the same)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no board at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version", 0) > SCHEMA_VERSION:
        raise ValueError(
            f"board schema v{payload['schema_version']} is newer than this "
            f"build supports (v{SCHEMA_VERSION}) — NO DATA — PENDING")
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# Daily feed — the Telegram board, served to the web (Architect 2026-08-11)
# ─────────────────────────────────────────────────────────────────────────────
# One render, two outlets: the daily run's production builds the Telegram
# message, and THAT same output feeds the web. The web page is the Telegram
# board — same content, same honesty (NO DATA — PENDING when a pick or code is
# genuinely missing, HR35). `build_feed_payload` starts from the client-safe
# trim (never a model internal) and adds back exactly the honest gate/edge
# numbers the Telegram message already carries: data flags, calibration count,
# mean CLV, the gate state (incl. the ARCHITECT_SIGNOFF override — never
# silent), yesterday-graded and the 7-day rolling bar.
#
# Nothing here is written by the web layer; the raw board_<date>.json is the
# single source. `read_feed` is the read path; `stamp_feed_audit` records the
# gate numbers on the feed's side of the boundary so an override is stamped,
# never silent.
FEED_AUDIT = BOARD_DIR / "feed_audit.jsonl"


def list_board_dates() -> list[str]:
    """Return sorted (descending) list of raw board dates (YYYY-MM-DD)."""
    dates = [p.stem.replace("board_", "") for p in BOARD_DIR.glob("board_*.json")]
    return sorted(dates, reverse=True)


def _feed_safe_yesterday(yesterday_graded: Optional[list]) -> Optional[list]:
    """Yesterday-graded as the Telegram board shows it: fixture, outcome and a
    per-engine ✓/✗ mark. The engine probabilities each mark was derived from
    are model internals and never leave this module."""
    if not yesterday_graded:
        return None
    out = []
    for g in yesterday_graded:
        marks = {}
        for engine, markets in (g.get("engines") or {}).items():
            row = markets.get("1X2_HOME") or markets.get("1X2_DRAW") \
                or markets.get("1X2_AWAY")
            if row and row.get("hit") is not None:
                marks[engine] = bool(row["hit"])
        out.append({
            "fixture": g.get("fixture"),
            "league": g.get("league"),
            "outcome": g.get("outcome"),
            "engines_hit": marks,
        })
    return out


def _feed_safe_rolling(rolling_7d: Optional[dict]) -> Optional[dict]:
    """7-day rolling as the Telegram board shows it: per-engine hit rates plus
    the honest legs/CLV/gate line. Prediction volumes are dropped — the
    Telegram bar never shows them."""
    if not rolling_7d:
        return None
    engines = {}
    for eng, st in (rolling_7d.get("engines") or {}).items():
        if st and st.get("hit_rate") is not None:
            engines[eng] = {"hit_rate": st["hit_rate"]}
    return {
        "engines": engines,
        "legs_logged": rolling_7d.get("legs_logged", 0),
        "legs_with_clv": rolling_7d.get("legs_with_clv", 0),
        "avg_clv_pct": rolling_7d.get("avg_clv_pct"),
        "gate": rolling_7d.get("gate"),
    }


def build_feed_payload(payload: dict) -> dict:
    """The daily feed — what the web page renders. Structurally the Telegram
    board: starts from `trim_payload` (so the data-leak boundary holds by
    construction), then adds back the honest gate/edge fields the Telegram
    message already carries. Never mutates the source payload, never carries
    elo/xg/consensus/EV/verification internals."""
    feed = trim_payload(payload)
    feed["data_flags"] = payload.get("data_flags", [])
    feed["calibration_count"] = payload.get("calibration_count", 0)
    feed["mean_clv"] = payload.get("mean_clv")
    feed["gate_state"] = _gate_state(payload)
    if payload.get("yesterday_graded") is not None:
        feed["yesterday_graded"] = _feed_safe_yesterday(payload["yesterday_graded"])
    if payload.get("rolling_7d") is not None:
        feed["rolling_7d"] = _feed_safe_rolling(payload["rolling_7d"])
    return feed


def read_feed(date_str: str) -> dict:
    """The feed for a date: the raw board → build_feed_payload. A missing board
    raises FileNotFoundError (the caller turns that into an honest 404, never a
    guess — HR35)."""
    path = BOARD_DIR / f"board_{date_str}.json"
    return build_feed_payload(read_payload(path))


def stamp_feed_audit(date_str: str, payload: dict) -> None:
    """Best-effort stamp of the day's gate numbers into the feed audit — the
    feed-side mirror of publish_audit, so an ARCHITECT_SIGNOFF override on the
    auto-published feed is recorded, never silent. A failed write never kills
    the run."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "date": date_str,
        "gate": _gate_state(payload),
    }
    try:
        FEED_AUDIT.parent.mkdir(parents=True, exist_ok=True)
        with FEED_AUDIT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
