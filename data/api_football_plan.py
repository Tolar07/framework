"""
API-Football plan probe — the gate that lifts the free-plan guards.

API-Football serves seasons 2022-2024 on the free plan and the CURRENT season
on paid plans (Standard/Pro). Every free-plan assumption in this repo (the
2024 history guard, the today±1 odds window, the season-scoped fixture refusals)
is gated on `is_paid_plan()`, so the moment the Architect pastes a paid key into
`API_FOOTBALL_KEY` the current-season rating fix enables itself — no code
change. Until then the probe reports Free and the gates stay closed.

VERIFIED LIVE 2026-08-12: the key in `.env` is Free (`/status` →
`{"plan":"Free","end":"2027-08-03"}`) and current-season standings return the
"Free plans do not have access to this season" error.

FAIL-OPEN NEVER — this is a gate, and a gate fails closed: any probe failure
(key missing, network down, parse change) is treated as Free, so a transient
error can never silently open the current-season path. The plan is stable for
the whole season, so the probe result is cached for 7 days (same TTL policy as
the plan-error cache in fixtures_source.py); a plan upgrade surfaces within a
week.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

from data.retry import get_protected

API_BASE = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).parent / "cache" / "api_football"
PLAN_CACHE_PATH = CACHE_DIR / "plan.json"
# The plan is stable for the whole billing period — re-probe weekly (same
# policy as PLAN_ERROR_TTL_SECONDS in fixtures_source.py). A paid upgrade
# surfaces within a week.
PLAN_TTL_SECONDS = 7 * 24 * 3600

# Plan names that count as FREE (no current season). Anything else that
# resolves to a real plan name (Standard, Pro, ...) is treated as paid.
FREE_PLANS = {"free"}


def _key() -> Optional[str]:
    return os.environ.get("API_FOOTBALL_KEY")


def _read_cached_plan() -> Optional[str]:
    """The cached plan name, or None if absent/stale/unreadable.

    A stale cache is treated as absent — the caller probes again rather than
    trusting a week-old reading of a gate (HR35: never guess at a gate)."""
    try:
        blob = json.loads(PLAN_CACHE_PATH.read_text(encoding="utf-8"))
        if time.time() - blob.get("probed_at", 0) > PLAN_TTL_SECONDS:
            return None
        name = blob.get("plan")
        return name if isinstance(name, str) and name else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _write_cached_plan(name: str) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        PLAN_CACHE_PATH.write_text(
            json.dumps({"plan": name, "probed_at": time.time()}),
            encoding="utf-8")
    except OSError:
        pass  # a cache write failure must never fail the probe


def _probe_plan() -> Optional[str]:
    """Live GET /status -> the plan name, or None on any failure.

    The account plan appears in several shapes across API-Football responses:
    `response.subscription.plan` (the /status shape — VERIFIED live 2026-08-12:
    "Free"), `response.account.plan.name` (the documented dashboard shape), and
    a flat `response.plan` string. All are read defensively; a shape none of
    them matches returns None (treated as Free, fail-closed)."""
    key = _key()
    if not key or requests is None:
        return None
    try:
        resp = get_protected(
            f"{API_BASE}/status", breaker_name="api_football",
            headers={"x-apisports-key": key}, timeout=20)
        payload = resp.json()
    except Exception:
        return None
    try:
        r = payload.get("response") or {}
        name = ((r.get("subscription") or {}).get("plan")
                or ((r.get("account") or {}).get("plan") or {}).get("name")
                or r.get("plan"))
        if isinstance(name, dict):
            name = name.get("name")
        return str(name).strip() if name else None
    except (AttributeError, ValueError):
        return None


def plan_name() -> str:
    """The cached/live plan name, defaulting to "Free" on any failure.

    Callers use this for DISPLAY (e.g. the board saying a league is fitted on
    a stale free-plan history). Use is_paid_plan() for gating — it is the same
    read, just a boolean."""
    cached = _read_cached_plan()
    if cached is not None:
        return cached
    live = _probe_plan()
    if live:
        _write_cached_plan(live)
        return live
    # Probe failed: fail CLOSED. Free is the honest default — it is what the
    # current key verifiably is, and a failure must never open the gates.
    return "Free"


def is_paid_plan() -> bool:
    """True only when the key resolves to a non-free plan.

    A missing key, a failed probe, an unparseable response, or an explicit
    "Free" all return False — the free-plan gates stay in force until a paid
    key is verifiably live."""
    name = plan_name().strip().lower()
    return bool(name) and name not in FREE_PLANS
