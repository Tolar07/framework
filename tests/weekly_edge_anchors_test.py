"""The weekly review's edge-anchor block: model vs consensus edge and decay,
with PENDING where a figure is absent (HR35). Reporting only."""
from scripts.weekly_review import _pct, edge_anchor_summary


def test_pct_formats_signed_or_pending():
    assert _pct(None) == "PENDING"
    assert _pct(0) == "+0.00%"
    assert _pct(6.4) == "+6.40%"
    assert _pct(-3.2) == "-3.20%"


def test_summary_shows_all_three_anchors():
    s = {"legs_with_clv": 40, "mean_entry_edge_pct": 6.4,
         "mean_consensus_edge_pct": 2.1, "mean_edge_decay_pct": 4.3}
    out = edge_anchor_summary(s)
    assert "graded legs: 40" in out
    assert "+6.40%" in out and "+2.10%" in out and "+4.30%" in out
    assert "drives no selection or stake" in out.lower()


def test_summary_pends_missing_figures():
    # No consensus-priced legs yet -> PENDING, never a fake zero.
    s = {"legs_with_clv": 0, "mean_entry_edge_pct": None,
         "mean_consensus_edge_pct": None, "mean_edge_decay_pct": None}
    out = edge_anchor_summary(s)
    assert out.count("PENDING") == 3
    assert "graded legs: 0" in out
