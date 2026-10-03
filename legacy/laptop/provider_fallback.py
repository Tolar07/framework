"""
Generic provider fallback infrastructure for OLP XDV
Provides ProviderChain class with retry logic, circuit breaker, and health monitoring.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class ProviderStatus(Enum):
    """Status of a provider in the chain."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class ProviderMetrics:
    """Metrics for a single provider."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_error: Optional[str] = None
    status: ProviderStatus = ProviderStatus.HEALTHY
    circuit_open_until: Optional[datetime] = None

    def record_success(self) -> None:
        """Record a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.status = ProviderStatus.HEALTHY
        self.circuit_open_until = None

    def record_failure(self, error: str) -> None:
        """Record a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()
        self.last_error = error

        # Circuit breaker logic: open after 5 consecutive failures
        if self.consecutive_failures >= 5:
            self.status = ProviderStatus.CIRCUIT_OPEN
            # Keep circuit open for 5 minutes
            self.circuit_open_until = datetime.now()
            logger.warning(f"Circuit breaker OPENED for provider '{self.name}' after {self.consecutive_failures} consecutive failures")

    def is_available(self) -> bool:
        """Check if provider is available for calls."""
        if self.status == ProviderStatus.CIRCUIT_OPEN:
            if self.circuit_open_until:
                # Auto-close circuit after timeout (5 minutes)
                if (datetime.now() - self.circuit_open_until).total_seconds() > 300:
                    self.status = ProviderStatus.HEALTHY
                    self.consecutive_failures = 0
                    self.circuit_open_until = None
                    logger.info(f"Circuit breaker CLOSED for provider '{self.name}' after timeout")
                    return True
                return False
        return self.status != ProviderStatus.FAILED

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_calls == 0:
            return 100.0
        return (self.successful_calls / self.total_calls) * 100


@dataclass
class ProviderResult(Generic[T]):
    """Result from a provider execution."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    provider_name: str = ""
    execution_time_ms: float = 0.0
    metrics: Optional[ProviderMetrics] = None


class Provider(Generic[T], ABC):
    """Abstract base class for a provider."""

    def __init__(self, name: str):
        self.name = name
        self.metrics = ProviderMetrics(name=name)

    @abstractmethod
    def fetch(self, *args, **kwargs) -> T:
        """Fetch data from this provider. Should raise on failure."""
        pass

    def is_available(self) -> bool:
        """Check if provider is available."""
        return self.metrics.is_available()


class ProviderChain(Generic[T]):
    """
    Generic provider chain with fallback logic, retry mechanism,
    circuit breaker, and health monitoring.
    """

    def __init__(
        self,
        providers: List[Provider[T]],
        max_retries: int = 2,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        timeout: float = 30.0
    ):
        """
        Initialize provider chain.

        Args:
            providers: List of Provider instances in priority order
            max_retries: Max retries per provider before falling back
            retry_delay: Initial delay between retries in seconds
            retry_backoff: Multiplier for retry delay (exponential backoff)
            timeout: Max execution time per provider call in seconds
        """
        self.providers = providers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.timeout = timeout
        self._lock = threading.RLock()

    def execute(self, *args, **kwargs) -> ProviderResult[T]:
        """
        Execute provider chain with fallback, retry, and circuit breaker.

        Returns:
            ProviderResult with data from first successful provider
        """
        last_error = None

        for provider in self.providers:
            with self._lock:
                if not provider.is_available():
                    logger.warning(f"Provider '{provider.name}' unavailable (status: {provider.metrics.status.value}), skipping")
                    continue

            delay = self.retry_delay
            for attempt in range(self.max_retries + 1):
                start_time = time.time()
                try:
                    logger.info(f"Executing provider '{provider.name}' (attempt {attempt + 1}/{self.max_retries + 1})")
                    result = provider.fetch(*args, **kwargs)
                    execution_time = (time.time() - start_time) * 1000

                    with self._lock:
                        provider.metrics.record_success()

                    logger.info(f"Provider '{provider.name}' succeeded in {execution_time:.1f}ms")
                    return ProviderResult(
                        success=True,
                        data=result,
                        provider_name=provider.name,
                        execution_time_ms=execution_time,
                        metrics=provider.metrics
                    )

                except Exception as e:
                    execution_time = (time.time() - start_time) * 1000
                    last_error = str(e)
                    logger.warning(f"Provider '{provider.name}' failed (attempt {attempt + 1}): {e}")

                    with self._lock:
                        provider.metrics.record_failure(last_error)

                    if attempt < self.max_retries:
                        logger.debug(f"Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= self.retry_backoff
                    else:
                        break  # Move to next provider

        # All providers failed
        return ProviderResult(
            success=False,
            error=last_error or "All providers failed",
            provider_name="chain"
        )

    def get_provider_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all providers."""
        health = {}
        for provider in self.providers:
            with self._lock:
                m = provider.metrics
                health[provider.name] = {
                    "status": m.status.value,
                    "total_calls": m.total_calls,
                    "success_rate": round(m.get_success_rate(), 2),
                    "consecutive_failures": m.consecutive_failures,
                    "last_success": m.last_success.isoformat() if m.last_success else None,
                    "last_failure": m.last_failure.isoformat() if m.last_failure else None,
                    "last_error": m.last_error,
                    "circuit_open_until": m.circuit_open_until.isoformat() if m.circuit_open_until else None
                }
        return health

    def reset_provider(self, provider_name: str) -> bool:
        """Reset a provider's circuit breaker and metrics."""
        with self._lock:
            for provider in self.providers:
                if provider.name == provider_name:
                    provider.metrics = ProviderMetrics(name=provider_name)
                    logger.info(f"Reset provider '{provider_name}'")
                    return True
        return False

    def reset_all(self) -> None:
        """Reset all providers."""
        with self._lock:
            for provider in self.providers:
                provider.metrics = ProviderMetrics(name=provider.name)
        logger.info("Reset all providers")


class FunctionProvider(Provider[T]):
    """Adapter to use a plain function as a provider."""

    def __init__(self, name: str, func: Callable[..., T]):
        super().__init__(name)
        self.func = func

    def fetch(self, *args, **kwargs) -> T:
        return self.func(*args, **kwargs)


def create_provider_chain(
    provider_specs: List[tuple],
    max_retries: int = 2,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    timeout: float = 30.0
) -> ProviderChain:
    """
    Create a ProviderChain from a list of (name, function) tuples.

    Args:
        provider_specs: List of (provider_name, provider_function) tuples
        max_retries: Max retries per provider
        retry_delay: Initial retry delay
        retry_backoff: Retry backoff multiplier
        timeout: Execution timeout per call

    Returns:
        Configured ProviderChain instance
    """
    providers = [FunctionProvider(name, func) for name, func in provider_specs]
    return ProviderChain(
        providers=providers,
        max_retries=max_retries,
        retry_delay=retry_delay,
        retry_backoff=retry_backoff,
        timeout=timeout
    )


# Example usage for fixtures and odds
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example provider functions
    def api_football(league: str) -> List[dict]:
        """Primary provider - API-Football"""
        # Simulate API call
        time.sleep(0.1)
        if league == "Bundesliga":
            return [{"fixture_id": "1", "home": "Bayern", "away": "Dortmund", "date": "2026-09-02"}]
        raise ConnectionError("API-Football unavailable")

    def the_sports_db(league: str) -> List[dict]:
        """Fallback provider - TheSportsDB"""
        time.sleep(0.1)
        if league == "Bundesliga":
            return [{"fixture_id": "2", "home": "Bayern", "away": "Dortmund", "date": "2026-09-02"}]
        raise ConnectionError("TheSportsDB unavailable")

    def sportybet(league: str) -> List[dict]:
        """Last resort - SportyBet"""
        time.sleep(0.1)
        return [{"fixture_id": "3", "home": "Bayern", "away": "Dortmund", "date": "2026-09-02"}]

    # Create chain
    chain = create_provider_chain([
        ("API-Football", api_football),
        ("TheSportsDB", the_sports_db),
        ("SportyBet", sportybet)
    ])

    # Execute
    result = chain.execute("Bundesliga")

    print(f"Success: {result.success}")
    print(f"Provider: {result.provider_name}")
    print(f"Data: {result.data}")
    print(f"Health: {chain.get_provider_health()}")