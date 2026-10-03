"""Pytest collection control for the OLP XDV test suite.

This repo's tests are a mix of two styles:
  1. Proper pytest functions (`def test_*`) — multi_source_test.py, clv_grade_test.py.
  2. Standalone script tests (`python tests/<name>.py`) — module-level asserts
     that print OK/FAIL and exit. Under `pytest tests/` they are IMPORTED
     (their asserts run during collection) and report as 0 items.

Some standalone scripts are environment-sensitive by design and hard-crash
collection when their live checks fail:
  - closing_capture_test.py  needs live bookmaker/Polymarket feeds for one section
  - stress_test.py / stress2_test.py  launch the full daily pipeline and carry
    timing checks (e.g. "warm reuse < 30s") that are flaky on slow machines
  - sandbox_live_test.py     talks to a live sandbox
  - integration_test.py      runs the full synthetic pipeline; CI executes it
    explicitly as its own step (`python tests/integration_test.py`), so it is
    not re-run as a side effect of collection

They remain runnable as standalone scripts — this file only keeps `pytest
tests/` from hard-crashing on their environment-dependent asserts.
"""
collect_ignore = [
    "closing_capture_test.py",
    "stress_test.py",
    "stress2_test.py",
    "sandbox_live_test.py",
    "integration_test.py",
    "sportybet_continental_test.py",  # reads live SportyBet cache for a
                                       # date-specific continental slate;
                                       # hard-crashes when the market's day
                                       # rolls over (section 4 asserts the
                                       # 2026-08-11 qualifier fixtures are
                                       # priced; they move off the page next
                                       # day). Standalone runnable.
]
