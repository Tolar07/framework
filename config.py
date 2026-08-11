"""
Framework-wide operating constants and the capital bright line.

HR51 / master v303.15 Section 8: the framework is in **Phase 2 — paper only,
zero capital**. Phase 3 (live capital) is gated on >=30 paper legs with logged
CLV AND positive mean CLV AND the Architect's V7 sign-off.

Before this module existed the phase was a display string only — nothing
branched on it, and `CLVLog.log_entry(phase="live", stake=250.0)` would have
been accepted and written to disk without a single check. The blueprint
requires the bright line to be enforced in code as a hard fail, not a warning,
so a pipeline bug can never quietly stake money.

Nothing here decides whether a bet is good. It only decides whether the code
is permitted to record a stake at all — and in Phase 2 it never is.
"""
from __future__ import annotations

import os
from pathlib import Path


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
    path = path or (Path(__file__).parent / ".env")
    loaded: list[str] = []
    if not path.exists():
        return loaded
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
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

    A stake of None is what a paper leg carries and is always allowed. Any
    numeric stake — including 0.0, which would otherwise slip through a
    truthiness check — is a capital action and is refused below Phase 3.
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
