"""
Multi-source data redundancy layer — automatic failover for all pipeline data.

Every data type gets multiple redundant providers with:
- Priority ordering (cheapest/fastest first)
- Circuit breakers (failure count + timeout)
- Health tracking (latency, success rate, recency)
- Automatic retry with exponential backoff
- Structured logging of which source succeeded/failed

This replaces the ad-hoc try/except chains in orchestrator.py with a
systematic, observable, testable redundancy fabric.
"""
from __future__ import annotations

import abc
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Generic, Optional, TypeVar
from collections import deque

T = TypeVar("T")

log = logging.getLogger("multi_source")


class SourceHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


@dataclass
class SourceMetrics:
    """Rolling metrics for a single data source."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    total_latency_ms: float = 0.0
    recent_latencies: deque = field(default_factory=lambda: deque(maxlen=50))
    circuit_breaker_failures: int = 0
    circuit_open_until: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls

    @property
    def health(self) -> SourceHealth:
        now = time.time()
        if self.circuit_open_until > now:
            return SourceHealth.CIRCUIT_OPEN
        if self.consecutive_failures >= 3:
            return SourceHealth.DEGRADED
        if self.total_calls > 10 and self.success_rate < 0.5:
            return SourceHealth.DEGRADED
        return SourceHealth.HEALTHY


@dataclass
class SourceCallResult(Generic[T]):
    """Result of calling a source, with metadata."""
    data: Optional[T]
    source_name: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class DataSource(abc.ABC, Generic[T]):
    """Abstract base for a data source with metrics."""

    def __init__(
        self,
        name: str,
        priority: int = 0,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 300.0,  # seconds
        timeout: float = 30.0,
    ):
        self.name = name
        self.priority = priority
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.timeout = timeout
        self.metrics = SourceMetrics(name=name)

    @abc.abstractmethod
    def fetch(self, **kwargs) -> T:
        """Fetch data from this source. Must raise on failure."""
        pass

    def record_success(self, latency_ms: float) -> None:
        self.metrics.total_calls += 1
        self.metrics.successful_calls += 1
        self.metrics.consecutive_failures = 0
        self.metrics.last_success = time.time()
        self.metrics.total_latency_ms += latency_ms
        self.metrics.recent_latencies.append(latency_ms)
        self.metrics.circuit_breaker_failures = 0

    def record_failure(self, error: str) -> None:
        self.metrics.total_calls += 1
        self.metrics.failed_calls += 1
        self.metrics.consecutive_failures += 1
        self.metrics.last_failure = time.time()
        self.metrics.circuit_breaker_failures += 1
        if self.metrics.circuit_breaker_failures >= self.circuit_breaker_threshold:
            self.metrics.circuit_open_until = time.time() + self.circuit_breaker_timeout
            log.warning(f"Circuit breaker OPENED for {self.name} after "
                        f"{self.metrics.circuit_breaker_failures} consecutive failures")


class MultiSource(Generic[T]):
    """
    Orchestrates multiple data sources with automatic failover.

    Sources are tried in priority order (lower = higher priority).
    First successful response wins. All attempts are logged with metrics.
    """

    def __init__(
        self,
        name: str,
        sources: list[DataSource[T]],
        max_retries_per_source: int = 1,
        backoff_base: float = 0.5,
        backoff_max: float = 5.0,
    ):
        self.name = name
        self.sources = sorted(sources, key=lambda s: s.priority)
        self.max_retries_per_source = max_retries_per_source
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.call_history: list[SourceCallResult[T]] = []

    def fetch(self, **kwargs) -> SourceCallResult[T]:
        """Try all sources in priority order until one succeeds."""
        last_error = None

        for source in self.sources:
            # Skip if circuit breaker is open
            if source.metrics.circuit_open_until > time.time():
                log.debug(f"{self.name}: skipping {source.name} (circuit open)")
                self.call_history.append(SourceCallResult(
                    data=None, source_name=source.name, success=False,
                    latency_ms=0, error="circuit_breaker_open"))
                continue

            for attempt in range(self.max_retries_per_source + 1):
                start = time.time()
                try:
                    data = source.fetch(**kwargs)
                    latency_ms = (time.time() - start) * 1000
                    source.record_success(latency_ms)
                    result = SourceCallResult(
                        data=data, source_name=source.name,
                        success=True, latency_ms=latency_ms)
                    self.call_history.append(result)
                    log.info(f"{self.name}: SUCCESS via {source.name} "
                             f"({latency_ms:.0f}ms, attempt {attempt+1})")
                    return result
                except SourceNoData as e:
                    # A valid "nothing here for this query" answer — fall
                    # through to the next source WITHOUT opening the circuit
                    # (a quiet league must not starve the leagues after it).
                    latency_ms = (time.time() - start) * 1000
                    last_error = str(e)
                    self.call_history.append(SourceCallResult(
                        data=None, source_name=source.name, success=False,
                        latency_ms=latency_ms, error=str(e)))
                    log.info(f"{self.name}: {source.name} has no data for this "
                             f"query — trying next source: {e}")
                    break
                except Exception as e:
                    latency_ms = (time.time() - start) * 1000
                    last_error = str(e)
                    if attempt < self.max_retries_per_source:
                        backoff = min(
                            self.backoff_base * (2 ** attempt) +
                            random.uniform(0, 0.1),
                            self.backoff_max
                        )
                        log.debug(f"{self.name}: {source.name} failed "
                                  f"(attempt {attempt+1}), retrying in {backoff:.1f}s: {e}")
                        time.sleep(backoff)
                    else:
                        source.record_failure(str(e))
                        result = SourceCallResult(
                            data=None, source_name=source.name,
                            success=False, latency_ms=latency_ms,
                            error=str(e))
                        self.call_history.append(result)
                        log.warning(f"{self.name}: {source.name} FAILED "
                                    f"after {attempt+1} attempts: {e}")

        # All sources exhausted
        raise MultiSourceExhausted(
            f"{self.name}: all {len(self.sources)} sources exhausted. "
            f"Last error: {last_error}")

    def get_health_report(self) -> dict:
        """Return health status of all sources."""
        return {
            "name": self.name,
            "sources": [
                {
                    "name": s.name,
                    "priority": s.priority,
                    "health": s.metrics.health.value,
                    "success_rate": s.metrics.success_rate,
                    "avg_latency_ms": s.metrics.avg_latency_ms,
                    "total_calls": s.metrics.total_calls,
                    "consecutive_failures": s.metrics.consecutive_failures,
                    "circuit_open": s.metrics.circuit_open_until > time.time(),
                }
                for s in self.sources
            ],
            "recent_calls": [
                {
                    "source": r.source_name,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                    "timestamp": r.timestamp,
                }
                for r in self.call_history[-10:]
            ],
        }


class MultiSourceExhausted(Exception):
    """Raised when all sources in a MultiSource fail."""
    pass


class SourceNoData(Exception):
    """A source answered but has NO data for this particular query.

    Deliberately distinct from a failure: "no fixtures in this window" or "no
    VERIFIED league ID" is a valid answer for one league, not an outage of the
    source. MultiSource.fetch lets SourceNoData fall through to the next source
    WITHOUT recording a circuit-breaker failure — otherwise a run of quiet
    leagues on the SHARED fixture source opens the circuit and starves every
    league scanned after them (the bug that dropped Primeira Liga)."""
    pass


# ---------------------------------------------------------------------------
# Decorator for simple function-to-source adaptation
# ---------------------------------------------------------------------------

def as_source(
    name: str,
    priority: int = 0,
    circuit_breaker_threshold: int = 3,
    circuit_breaker_timeout: float = 300.0,
    timeout: float = 30.0,
) -> Callable[[Callable[..., T]], DataSource[T]]:
    """Decorator to turn a function into a DataSource."""
    def decorator(func: Callable[..., T]) -> DataSource[T]:
        class _FuncSource(DataSource[T]):
            def fetch(self, **kwargs) -> T:
                return func(**kwargs)

        source = _FuncSource(
            name=name,
            priority=priority,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_timeout=circuit_breaker_timeout,
            timeout=timeout,
        )
        source._func = func
        return source
    return decorator


# ---------------------------------------------------------------------------
# Convenience: build a MultiSource from a list of functions
# ---------------------------------------------------------------------------

def build_multi_source(
    name: str,
    funcs: list[tuple[Callable[..., T], str, int]],  # (func, name, priority)
    **multi_source_kwargs,
) -> MultiSource[T]:
    """Build a MultiSource from a list of (function, name, priority) tuples."""
    sources = []
    for func, src_name, priority in funcs:
        sources.append(as_source(src_name, priority=priority)(func))
    return MultiSource(name, sources, **multi_source_kwargs)


# ---------------------------------------------------------------------------
# Health reporting aggregation
# ---------------------------------------------------------------------------

class SourceRegistry:
    """Global registry of all multi-sources for health reporting."""

    _instance: Optional["SourceRegistry"] = None
    _sources: dict[str, MultiSource] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, multi_source: MultiSource) -> None:
        self._sources[multi_source.name] = multi_source

    def get_health_report(self) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": {
                name: ms.get_health_report()
                for name, ms in self._sources.items()
            },
        }

    def get_source(self, name: str) -> Optional[MultiSource]:
        return self._sources.get(name)


registry = SourceRegistry()