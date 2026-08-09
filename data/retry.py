"""Shared HTTP retry + circuit-breaker utilities for all data sources.

Why this exists:
  Every data source (football-data.co.uk, TheSportsDB, API-Football, The Odds
  API) makes HTTP calls that can fail transiently — a dropped connection, a
  429 rate limit, a 5xx server error. Each source historically implemented its
  own retry (or none), and API-Football has a HARD daily quota that a naive
  retry loop can burn through in seconds. This module is the single place
  that decides when to retry and when to stop hammering a quota-limited API.

Design:
  - _request() retries with exponential backoff + jitter on transient failures
    (429, 5xx, network exceptions). 4xx client errors are never retried — they
    are deterministic.
  - CircuitBreaker protects quota-limited endpoints. After `failure_threshold`
    consecutive failures it OPENS (refuses calls for `cooldown_seconds`) so the
    run degrades to NO DATA — PENDING instead of burning quota. It half-opens
    after cooldown to probe whether the API recovered.

HR35 is preserved: a breaker that refuses a call surfaces as NO DATA — PENDING
at the caller, never as a fabricated value.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Callable, Optional, TypeVar

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]  # optional-import idiom

T = TypeVar("T")

# Defaults (tunable per call site).
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_BACKOFF = 2.0
DEFAULT_MAX_BACKOFF = 30.0


class CircuitBreaker:
    """Simple per-endpoint circuit breaker.

    States: CLOSED (normal) -> OPEN (refusing, after failures) -> HALF_OPEN
    (probing) -> CLOSED (recovered) or OPEN again.

    Thread-safe via a lock; the daily run, the poller and a phone command can
    all touch the same endpoint concurrently.
    """

    def __init__(self, failure_threshold: int = 5,
                 cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._state = "CLOSED"          # CLOSED | OPEN | HALF_OPEN
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "OPEN" and self._opened_at is not None and \
                    time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._state = "HALF_OPEN"
            return self._state

    def allow_request(self) -> bool:
        return self.state != "OPEN"

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state in ("OPEN", "HALF_OPEN"):
                self._state = "CLOSED"
                self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            if self._state == "HALF_OPEN":
                # Probe failed — straight back to OPEN for a full cooldown.
                self._state = "OPEN"
                self._opened_at = time.monotonic()
                self._failures = 0
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = "OPEN"
                self._opened_at = time.monotonic()
                self._failures = 0

    def __repr__(self) -> str:
        return f"<CircuitBreaker state={self.state} failures={self._failures}>"


# One breaker per API host, shared by every call site in the module tree.
BREAKERS: dict[str, CircuitBreaker] = {}
_BREAKER_LOCK = threading.Lock()


def get_breaker(name: str) -> CircuitBreaker:
    with _BREAKER_LOCK:
        if name not in BREAKERS:
            BREAKERS[name] = CircuitBreaker()
        return BREAKERS[name]


def _is_transient(status_code: Optional[int]) -> bool:
    if status_code is None:
        return True  # network-level exception
    return status_code == 429 or status_code >= 500


def request(method: str, url: str, breaker_name: Optional[str] = None,
            max_retries: int = DEFAULT_MAX_RETRIES,
            base_backoff: float = DEFAULT_BASE_BACKOFF,
            max_backoff: float = DEFAULT_MAX_BACKOFF,
            **kwargs) -> "requests.Response":
    """GET/POST with exponential backoff, optionally guarded by a circuit
    breaker. Mirrors the requests API so call sites change minimally.

    Raises requests.RequestException when all retries are exhausted (or the
    breaker is OPEN). Callers catch and surface NO DATA — PENDING.
    """
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live data")

    breaker = get_breaker(breaker_name) if breaker_name else None
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", "OLP-XDV/1.0")

    attempts = 0
    while True:
        if breaker is not None and not breaker.allow_request():
            raise RuntimeError(
                f"circuit breaker '{breaker_name}' OPEN — refusing request "
                f"to {url} (degrade to NO DATA — PENDING)")

        attempts += 1
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
        except (requests.RequestException, OSError) as e:
            # Network-level failure (no HTTP response at all) -> transient.
            if breaker is not None:
                breaker.record_failure()
            if attempts >= max_retries:
                raise
            _sleep_backoff(attempts, base_backoff, max_backoff)
            continue

        if _is_transient(resp.status_code):
            if breaker is not None:
                breaker.record_failure()
            if attempts >= max_retries:
                resp.raise_for_status()  # raise the last 429/5xx
            _sleep_backoff(attempts, base_backoff, max_backoff)
            continue

        # Deterministic 4xx -> record + raise NOW, never retry (wastes quota).
        if resp.status_code >= 400:
            if breaker is not None:
                breaker.record_failure()
            resp.raise_for_status()
        if breaker is not None:
            breaker.record_success()
        return resp


def _sleep_backoff(attempt: int, base: float, cap: float) -> None:
    backoff = min(base * (2 ** (attempt - 1)), cap)
    time.sleep(backoff + random.uniform(0, 0.5))  # jitter: avoid thundering herd


def get(url: str, **kwargs) -> "requests.Response":
    """Convenience: GET without a breaker (no quota to protect)."""
    return request("GET", url, **kwargs)


def get_protected(url: str, breaker_name: str, **kwargs) -> "requests.Response":
    """GET behind a circuit breaker — use for quota-limited endpoints."""
    return request("GET", url, breaker_name=breaker_name, **kwargs)
