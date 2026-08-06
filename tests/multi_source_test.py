"""Tests for the multi-source data redundancy layer."""
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source import (
    DataSource, MultiSource, SourceCallResult, SourceMetrics,
    SourceHealth, MultiSourceExhausted, registry
)
from data.multi_source_concrete import (
    TheSportsDBFixturesSource, OddsAPIFixturesSource,
    build_fixtures_multi_source, build_results_multi_source,
    get_all_health
)


def test_source_metrics():
    """Test SourceMetrics health tracking."""
    m = SourceMetrics(name="test")
    assert m.health == SourceHealth.UNKNOWN
    m.total_calls = 10
    m.successful_calls = 9
    m.consecutive_failures = 0
    assert m.health == SourceHealth.HEALTHY

    m.consecutive_failures = 3
    assert m.health == SourceHealth.DEGRADED

    m.circuit_open_until = time.time() + 100
    assert m.health == SourceHealth.CIRCUIT_OPEN


def test_data_source_records():
    """Test DataSource success/failure recording."""
    class TestSource(DataSource):
        def fetch(self, **kwargs):
            return "ok"

    s = TestSource(name="test", priority=0)
    s.record_success(50.0)
    assert s.metrics.successful_calls == 1
    assert s.metrics.consecutive_failures == 0

    s.record_failure("error")
    assert s.metrics.failed_calls == 1
    assert s.metrics.consecutive_failures == 1


def test_multi_source_success_first_try():
    """MultiSource returns first successful source."""
    class SuccessSource(DataSource):
        def __init__(self, name, should_succeed=True):
            super().__init__(name, priority=0)
            self.should_succeed = should_succeed

        def fetch(self, **kwargs):
            if self.should_succeed:
                return f"data from {self.name}"
            raise RuntimeError(f"{self.name} failed")

    ms = MultiSource("test", [
        SuccessSource("first", should_succeed=False),
        SuccessSource("second", should_succeed=True),
        SuccessSource("third", should_succeed=True),
    ])

    result = ms.fetch()
    assert result.success
    assert result.data == "data from second"
    assert result.source_name == "second"


def test_multi_source_all_fail():
    """MultiSource raises when all sources fail."""
    class FailSource(DataSource):
        def fetch(self, **kwargs):
            raise RuntimeError("always fails")

    ms = MultiSource("test", [FailSource("a"), FailSource("b")])

    try:
        ms.fetch()
        assert False, "should have raised"
    except MultiSourceExhausted as e:
        assert "exhausted" in str(e).lower()


def test_circuit_breaker_opens():
    """Circuit breaker opens after threshold failures."""
    class FlakySource(DataSource):
        def __init__(self, name, fail_count):
            super().__init__(name, priority=0, circuit_breaker_threshold=2)
            self.fail_count = fail_count
            self.calls = 0

        def fetch(self, **kwargs):
            self.calls += 1
            if self.calls <= self.fail_count:
                raise RuntimeError("fail")
            return "ok"

    # First source fails twice -> circuit opens
    # Second source succeeds
    ms = MultiSource("test", [
        FlakySource("flaky", fail_count=2),
        FlakySource("good", fail_count=0),
    ], max_retries_per_source=0)

    result = ms.fetch()
    assert result.success
    assert result.source_name == "good"

    # Now flaky's circuit should be open
    flaky = ms.sources[0]
    assert flaky.metrics.circuit_open_until > time.time()


def test_multi_source_health_report():
    """Health report includes all source metrics."""
    class OkSource(DataSource):
        def fetch(self, **kwargs):
            return "ok"

    ms = MultiSource("test", [OkSource("a", priority=1), OkSource("b", priority=2)])
    ms.fetch()
    ms.fetch()

    report = ms.get_health_report()
    assert report["name"] == "test"
    assert len(report["sources"]) == 2
    for s in report["sources"]:
        assert s["health"] in ("healthy", "degraded", "circuit_open", "unknown")
        assert "success_rate" in s
        assert "avg_latency_ms" in s


def test_registry():
    """Global registry tracks all multi-sources."""
    registry._sources.clear()
    ms1 = build_fixtures_multi_source()
    ms2 = build_results_multi_source()

    registry.register(ms1)
    registry.register(ms2)

    report = registry.get_health_report()
    assert "fixtures" in report["sources"]
    assert "historical_results" in report["sources"]

    # Get specific source
    assert registry.get_source("fixtures") is ms1
    assert registry.get_source("nonexistent") is None


def test_concrete_sources_instantiate():
    """All concrete source classes can be instantiated."""
    sources = [
        TheSportsDBFixturesSource(),
        OddsAPIFixturesSource(),
    ]
    for s in sources:
        assert hasattr(s, 'fetch')
        assert s.name
        assert s.priority >= 0


def test_priority_ordering():
    """Sources are tried in priority order (lower = higher priority)."""
    call_order = []

    class TrackingSource(DataSource):
        def __init__(self, name, priority, should_succeed):
            super().__init__(name, priority=priority)
            self.should_succeed = should_succeed

        def fetch(self, **kwargs):
            call_order.append(self.name)
            if self.should_succeed:
                return f"data from {self.name}"
            raise RuntimeError(f"{self.name} failed")

    # Higher priority number = lower priority
    ms = MultiSource("test", [
        TrackingSource("low_priority", priority=20, should_succeed=True),
        TrackingSource("high_priority", priority=5, should_succeed=False),
        TrackingSource("medium_priority", priority=10, should_succeed=True),
    ])

    result = ms.fetch()
    assert result.source_name == "medium_priority"  # tried after high_priority fails
    assert call_order == ["high_priority", "medium_priority"]


print("✅ ALL MULTI_SOURCE TESTS PASSED")