"""
Configuration package for OLP XDV
"""
from __future__ import annotations

import os
from pathlib import Path

from .manager import ConfigManager, get_config, init_config
from .betting_config import BettingConfig
from .api_config import APIConfig
from .logging_config import LoggingConfig


def load_dotenv(path: Path | None = None) -> list[str]:
    """Read .env into os.environ. Returns the names loaded.

    This lives in Python rather than in the launcher because the launcher was
    where it kept failing. run_daily.bat previously parsed .env with a cmd
    `for /f` loop; when that construct failed the batch aborted before creating
    its own log, so a scheduled run produced NO evidence at all while Task
    Scheduler still reported Last Result 0. Moving the parsing here means the
    behaviour is identical whether the run is launched by hand, by Task
    Scheduler, or by GitHub Actions — and it is testable.

    An existing environment variable always wins, so GitHub Actions secrets are
    never overwritten by a stray local .env.
    """
    # `Path(__file__)` is this FILE (config/__init__.py), so the old
    # `Path(__file__) / ".env"` built `.../config/__init__.py/.env`, which can
    # never exist. `.exists()` returned False on every call, load_dotenv()
    # returned [] silently, and no entry point ever saw API_FOOTBALL_KEY,
    # ODDS_API_KEY, THESPORTSDB_KEY, TELEGRAM_BOT_TOKEN or ARCHITECT_SIGNOFF.
    # The package root (parent of config/) is where .env actually lives.
    path = path or (Path(__file__).resolve().parent.parent / ".env")
    if not path.exists():
        return []

    loaded: list[str] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    except Exception:
        pass
    return loaded


# Loaded on import so every entry point — run_daily, the Telegram poller, the
# backtest — sees the same environment without each having to remember to.
load_dotenv()

# HR51 phase. 1 = infrastructure, 2 = paper calibration, 3 = live capital.
#
# 2026-08-11 ARCHITECT ORDER (go-live, Phase 3): PHASE moved 2 -> 3. The
# market gate (engine/markets.BLOCKED) is open, ARCHITECT_SIGNOFF=1 is set, and
# the framework is live — it now records real stakes when they are logged,
# side-by-side with the paper legs that still feed the CLV gate. Capital
# authority remains the Architect's: this code never places a bet, it only
# permits a stake to reach disk. Recorded in RATIFICATIONS.md (2026-08-11).
PHASE = 3

# Derived, never set by hand — capital is only ever enabled at Phase 3, and
# even then the Architect deploys it, not this code.
CAPITAL_ENABLED = PHASE >= 3

# Human-readable phase label for board headers (was hardcoded and had drifted
# out of sync with the CLV ledger, which already defaulted to "phase2_paper").
PHASE_LABEL = {
    1: "Phase 1 — infrastructure, zero capital",
    2: "Phase 2 — paper calibration, zero capital",
    3: "Phase 3 — live capital (Architect-deployed)",
}[PHASE]

# The phase string written on paper legs. phase2_status() filters on this
# exact literal, so anything else (e.g. backtest legs) is excluded from the
# Phase 3 gate by construction.
PAPER_PHASE = "phase2_paper"


class CapitalGateError(RuntimeError):
    """Raised when code attempts to record a stake while capital is disabled."""


def assert_paper_only(stake: float | None, phase: str | None = None) -> None:
    """Hard fail if a stake is recorded while the framework is pre-Phase-3.

    A stake of None is what a paper leg
    """
    if stake is not None and not CAPITAL_ENABLED:
        raise CapitalGateError(
            f"Refusing to record stake={stake!r} at PHASE={PHASE} "
            f"(capital enabled only at Phase 3). Capital authority is the "
            f"Architect's; this code never stakes. See config.PHASE."
        )
    if phase is not None and phase.startswith("live") and not CAPITAL_ENABLED:
        raise CapitalGateError(
            f"Refusing to write a leg with phase={phase!r} at PHASE={PHASE}."
        )


__all__ = [
    "ConfigManager",
    "get_config",
    "init_config",
    "BettingConfig",
    "APIConfig",
    "LoggingConfig",
    "PHASE_LABEL",
    "PAPER_PHASE",
    "CAPITAL_ENABLED",
    "assert_paper_only",
]