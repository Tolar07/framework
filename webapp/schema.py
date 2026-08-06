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
from pathlib import Path
from typing import Any, Optional

from output.produce_bet import BoardFixture
from engine.dixon_coles import FixtureProbabilities

SCHEMA_VERSION = 1


def _opt(x) -> Any:
    return None if x is None else x


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
    }


def fixture_to_dict(bf: BoardFixture) -> dict:
    """Every BoardFixture field, JSON-safe. Tuples (elo/xg) become lists."""
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
                  recommendation: str = "") -> dict:
    """The full board_<date>.json payload, ready to write to disk.

    `recommendation` is the already-rendered ⭐ TODAY'S PICKS parlay text
    (produce_bet.render_daily_recommendation) — computed from the REAL
    BoardFixture list at run time so the web never re-implements the pick
    rule and drifts from the phone board."""
    return {
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


def write_payload(payload: dict, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


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
