"""engine/wb_ladder.py + backtest/wb_ladder_study.py - record-only ladder / shape twin (framework#397). Offline."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import wb_ladder_study as study  # noqa: E402
from engine import nba_shape  # noqa: E402
from engine import ncaa_lines as ncl  # noqa: E402
from engine import wb_ladder as wl  # noqa: E402


def _ladder(mid, key, centre, sd, lines):
    from statistics import NormalDist
    n = NormalDist(centre, sd)
    out = []
    for ln in lines:
        p = 1 - n.cdf(ln)                      # Over chance, margin added (5%)
        out.append({"id": mid, "spec": f"{key}={ln}", "open": True,
                    "outcomes": [["Over" if key == "total" else "Home", round(1 / (p * 1.05), 3)],
                                 ["Under" if key == "total" else "Away", round(1 / ((1 - p) * 1.05), 3)]]})
    return out


MK = _ladder("225", "total", 140.5, 17.0, [124.5, 130.5, 135.5, 140.5, 145.5, 150.5, 156.5])


def test_fit_recovers_centre_and_spread():
    c, sd, n = wl.fits(MK)["225"]
    assert abs(c - 140.5) < 0.6 and abs(sd - 17.0) < 0.6 and n == 7


def test_closed_lines_and_short_ladders_are_not_fitted():
    closed = [{**m, "open": False} for m in MK]
    assert wl.ladders(closed) == {}
    assert wl.fits(MK[:2])["225"] is None            # < 3 lines: PENDING, not a guess
    assert wl.ladders(None) == {}


def test_verdict_pending_without_measure():
    assert wl.verdict(None, 17.0) == "PENDING" and wl.verdict(17.0, None) == "PENDING"
    assert wl.verdict(20.0, 17.0).startswith("WIDER") and wl.verdict(14.0, 17.0).startswith("NARROWER")
    assert wl.verdict(17.2, 17.0) == "about right"


def test_shape_uses_ncaa_curves_and_nba_default_unchanged():
    ncaa = wl.shape(140.5, -5.5)
    assert ncaa and ncaa["score"] == [round((140.5 + 5.5) / 2), round((140.5 - 5.5) / 2)]
    assert abs(sum(ncaa["total"].values()) - 1) < 0.02
    assert wl.shape(None, -5.5) is None
    assert nba_shape.shape(225.0, -5.5) != nba_shape.shape(225.0, -5.5, msd=ncl.MARGIN_SD, tsd=ncl.TOTAL_SD)


def test_study_reports_pending_without_data_and_fits_with_data():
    assert any("PENDING" in x for x in study.build([]))
    looks = [{"event_id": "1", "markets": MK, "sharp": {"total": 139.5, "spread": -4.0}}]
    txt = "\n".join(study.build(looks))
    assert "Full-game total" in txt and "+1.0" in txt
