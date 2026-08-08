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
        "softness_tier": bf.softness_tier,
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
                  rolling_7d: Optional[dict] = None) -> dict:
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
})
CLIENT_TOP_KEYS = frozenset({
    "schema_version", "date", "phase",
    "leagues_scanned", "n_leagues", "board",
})


def trim_payload(payload: dict) -> dict:
    """The public-facing payload — predictions only, no model internals.

    Never mutates the source payload; builds fresh dicts. A fixture's `probs`
    is reduced to the market-probability fields the grid needs (lambdas and the
    modal scoreline are Dixon-Coles internals and are dropped)."""
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
    return out


class ClientPublishGateError(RuntimeError):
    """Raised when attempting to publish to client before Phase 3 gate is met."""


def check_client_publish_gate(admin_payload: dict, require_architect_signoff: bool = True) -> None:
    """
    Hard gate: publishing to the client-facing dashboard is blocked until
    the Phase 3 CLV gate is met (≥30 legs with logged CLV + positive mean CLV
    + Architect sign-off). This mirrors config.assert_paper_only() — a code-level
    hard fail, not a UI-only restriction.

    Args:
        admin_payload: The full board payload (must include 'gate' dict with
                       legs_with_clv, mean_clv_pct, gate_requirement)
        require_architect_signoff: If True, also requires ARCHITECT_SIGNOFF=1 in env

    Raises:
        ClientPublishGateError: If gate requirements are not met
    """
    gate = admin_payload.get("gate", {})
    legs_with_clv = gate.get("legs_with_clv", 0)
    mean_clv = gate.get("mean_clv_pct")
    gate_req = gate.get("gate_requirement", 30)

    if legs_with_clv < gate_req:
        raise ClientPublishGateError(
            f"Client publish blocked: {legs_with_clv}/{gate_req} legs with CLV "
            f"(need ≥{gate_req} for Phase 3 gate)."
        )
    if mean_clv is None or mean_clv <= 0:
        raise ClientPublishGateError(
            f"Client publish blocked: mean CLV is {mean_clv!r} "
            f"(must be positive for Phase 3 gate)."
        )

    # Architect sign-off — explicit env flag (defaults to required)
    if require_architect_signoff:
        signoff = os.environ.get("ARCHITECT_SIGNOFF", "0").strip().lower()
        if signoff not in ("1", "true", "yes"):
            raise ClientPublishGateError(
                "Client publish blocked: Architect sign-off required. "
                "Set ARCHITECT_SIGNOFF=1 in .env after reviewing the board."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Published store — the APPROVE gate boundary
# ─────────────────────────────────────────────────────────────────────────────
# The /admin board is the raw run_daily board (all model internals). The client
# dashboard and static export MUST read from the PUBLISHED store, which is
# written ONLY by the "Approve → Publish to Client" action. This enforces the
# Architect's intent: nothing reaches the client without an explicit approval,
# same principle as capital staying Architect-only.
PUBLISHED_DIR = Path(__file__).parent.parent / "output" / "boards" / "published"
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
    CLV gate is not met (≥30 legs with CLV + positive mean CLV + Architect sign-off).
    """
    # Hard gate — mirrors config.assert_paper_only() for capital
    check_client_publish_gate(admin_payload)

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
