"""Compatibility shim for the `orchestrator` module.

`orchestrator.py` was renamed to `orchestrator_DEPRECATED.py` as part of the
migration to the `pipeline/` package, but the ten modules that import it were
never updated, so `import orchestrator` raised ModuleNotFoundError.

That break was not obvious, because only `run_scan.py` imports it at module
scope and fails loudly. `output/telegram_commands.py` and `webapp/produce.py`
import it INSIDE a function, so they import cleanly and only fail at the moment
a Telegram command or a webapp production request actually runs -- the paths a
person exercises by hand rather than in a test. Seven test modules import it at
module scope and error during collection, which reads as "the tests are broken"
rather than "a module is missing".

This shim re-exports the symbols those callers use so every one of them works
again, without moving code and without reversing the deprecation. It is
deliberately thin: when the `pipeline/` migration is finished and the remaining
callers are repointed, delete this file and `orchestrator_DEPRECATED.py`
together.

Do NOT add new code here, and do not import this module in new code -- use the
`pipeline/` package.
"""
from __future__ import annotations

import warnings

from orchestrator_DEPRECATED import (  # noqa: F401  (re-export)
    FULL_WHITELIST,
    next_season_code,
    scan_one_league,
)

__all__ = ["FULL_WHITELIST", "next_season_code", "scan_one_league"]


def _warn() -> None:
    warnings.warn(
        "orchestrator is a compatibility shim over orchestrator_DEPRECATED; "
        "new code should use the pipeline/ package.",
        DeprecationWarning,
        stacklevel=3,
    )


_warn()
