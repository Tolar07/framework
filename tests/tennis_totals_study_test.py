from datetime import UTC, datetime

from backtest import tennis_totals_study as s

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def _doc(sides, comp="ATP Paris"):
    games = {"1": {"comp": comp, "sides": {
        k: {"first": {"price": p}, "won": w} for k, (p, w) in sides.items()}}}
    return ("2026-11-09", {"games": games, "picks": []})


def test_empty_is_pending_everywhere():
    out = s.render([], [], NOW)
    assert out.count("PENDING") >= 2 and "Record only" in out


def test_total_sides_grades_over_under_and_skips_others():
    docs = [_doc({"tennis:189|total=22.5|Over": (1.9, 0), "tennis:189|total=22.5|Under": (1.9, 1),
                  "tennis:186||Home": (1.5, 1), "tennis:189|total=22.5|Under ": (1.9, None)})]
    rows = s.total_sides(docs)
    assert [(r["side"], r["won"]) for r in rows] == [("over", 0), ("under", 1)]
    assert s.roi(rows) == round(((-1.0) + 0.9) / 2, 4)


def test_level_read_from_competition():
    assert s.level_of("WTA Finals") == "WTA" and s.level_of("ITF M15") == "ITF" and s.level_of(None) == "other"


def _bets(n, year, side="under", won=1):
    return [{"day": f"{year}-06-01", "side": side, "won": won, "price": 1.9} for _ in range(n)]


def test_cut_under_min_train_is_pending():
    r = s.judge_cut(_bets(300, 2024) + _bets(300, 2025), lambda r: True)
    assert r["verdict"].startswith("PENDING") and r["seal_year"] == 2025


def test_cut_judged_against_blind_under_not_zero():
    rows = _bets(1200, 2024, "over") + _bets(150, 2025, "over", 1) + _bets(150, 2025, "under", 1)
    r = s.judge_cut(rows, lambda r: r["side"] == "over")
    assert r["verdict"].startswith("FAILED")          # profitable, but only equal to the blind under: not beaten
    r2 = s.judge_cut(rows, lambda r: r["side"] == "over", looks=4)
    assert r2["verdict"].startswith("REJECTED")


def test_distribution_skew_and_decider():
    rows = []
    for _ in range(40):
        rows.append({"Best of": 3, "Surface": "Clay", "W1": 6, "L1": 3, "W2": 6, "L2": 3})
    for _ in range(40):
        rows.append({"Best of": 3, "Surface": "Clay", "W1": 6, "L1": 4, "W2": 3, "L2": 6, "W3": 6, "L3": 4})
    rows.append({"Best of": 3, "Surface": "Clay", "W1": 6, "L1": 0, "Comment": "Retired"})
    d = s.distribution(rows)
    g = d["groups"]["Bo3 Clay"]
    assert d["n"] == 80 and g["mean"] == 23.5 and g["n"] == 80
    assert d["decider"]["Bo3"]["decider_mean"] > d["decider"]["Bo3"]["straight_mean"]
    assert d["decider"]["Bo3"]["decider_share"] == 0.5
