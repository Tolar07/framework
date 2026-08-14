"""One-shot api-football plan re-check: clear the cached plan (so the probe
is forced fresh) and print whether the key resolves to a paid plan.

Used by the plan-flip watch loop. Does not fail the process on a network
blip — a probe failure prints 'probe failed (fail-closed -> Free)'.
"""
import os
import sys
from pathlib import Path

os.chdir(r"c:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv")
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from data.api_football_plan import (  # noqa: E402
    PLAN_CACHE_PATH,
    is_paid_plan,
    _probe_plan,
)

# Force a fresh probe this run — the 7-day cache would otherwise hide a
# plan flip for up to a week.
try:
    PLAN_CACHE_PATH.unlink(missing_ok=True)
except OSError:
    pass

live = _probe_plan()
print("probed plan:", live if live else "(probe failed / no key) -> Free (fail-closed)")
print("Paid plan:", is_paid_plan())