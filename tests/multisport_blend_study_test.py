"""framework#383: the Elo-vs-price blend study (record only). No network."""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import multisport_blend_study as st  # noqa: E402


def _doc(n, elo_is_better, seed=1):
    rnd = random.Random(seed)
    games = {}
    for i in range(n):
        true = rnd.uniform(0.25, 0.75)
        won = int(rnd.random() < true)
        price_p = min(max(true + rnd.uniform(-0.12, 0.12), 0.05), 0.95)
        model = true if elo_is_better else min(max(0.5 + rnd.uniform(-0.3, 0.3), 0.05), 0.95)
        games[f"g{i}"] = {"sides": {
            "darts:186||Home": {"first": {"price": round(1 / price_p, 2), "fair": price_p, "model": model},
                                "won": won},
            "darts:186||Away": {"first": {"price": round(1 / (1 - price_p), 2), "fair": 1 - price_p,
                                          "model": 1 - model}, "won": 1 - won}}}
    return {"games": games}


def _run(doc):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "darts"
        d.mkdir()
        (d / "ms_2026-11-06.json").write_text(json.dumps(doc), encoding="utf-8")
        return st.run(Path(td))["sports"]["darts"]


def test_too_few_games_is_pending_and_price_default():
    r = _run(_doc(20, True))
    assert r["status"] == "PENDING" and r["w"] == 0.0


def test_useless_elo_gets_no_weight():
    r = _run(_doc(1500, False))
    assert r["w"] == 0.0 and r["status"] == "PRICE"


def test_good_elo_earns_weight():
    r = _run(_doc(1500, True))
    assert r["status"] == "BLEND" and r["w"] > 0 and r["blend_brier_test"] < r["price_brier_test"]


def test_every_sport_listed_and_tries_counted():
    with tempfile.TemporaryDirectory() as td:
        res = st.run(Path(td))
    assert res["tries_per_sport"] == len(st.GRID) and len(res["sports"]) == 9
    assert all(v["status"] == "PENDING" for v in res["sports"].values())
