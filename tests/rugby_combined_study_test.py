"""Rugby combined study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_combined_study as rcs  # noqa: E402
from tests.rugby_calibration_study_test import _games  # noqa: E402


def test_run_reports_three_rules():
    text = rcs.run(_games())
    assert "Per-league home edge + shrink" in text and "2020" in text and "Settings tried" in text


def test_thin_data_pending():
    assert "PENDING" in rcs.run(_games(300))
