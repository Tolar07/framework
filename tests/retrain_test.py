"""Nightly retrain (engine/retrain.py, retrain.yml; Architect 2026-10-20 "auto").
Offline: synthetic ledgers in a temp folder, nothing real is read or written."""
from __future__ import annotations

import json
import math
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import calibration as cal  # noqa: E402
from engine import retrain  # noqa: E402


def _ledger(folder: Path, n_days: int, per_day: int, truth, seed: int = 1) -> None:
    """Picks files whose rated fixtures' outcomes follow truth(raw) for every family."""
    rnd = random.Random(seed)
    for d in range(n_days):
        day = f"2026-09-{d + 1:02d}"
        rated = []
        for k in range(per_day):
            raw = [rnd.uniform(0.15, 0.85) for _ in range(7)]
            # one score that reproduces the BTTS draw; the other families get their
            # own score-free outcome via a monkeypatched _outcomes below
            rated.append({"home": f"H{d}_{k}", "away": f"A{d}_{k}", "kickoff": day, "src": "model",
                          "p": [round(x, 3) for x in raw],
                          "ft": "|".join(str(int(rnd.random() < truth(x))) for x in raw)})
        rated.append({"home": "M", "away": "N", "kickoff": day, "src": "market",
                      "p": [0.5] * 7, "ft": "1|1|1|1|1|1|1"})
        (folder / f"picks_{day}.json").write_text(json.dumps({"date": day, "rated": rated}))


def _bits(ft):
    try:
        return [int(c) for c in ft.split("|")]
    except (AttributeError, ValueError):
        return None


retrain._outcomes = _bits  # synthetic outcomes, one independent draw per family


def _run(folder: Path, truth, n_days=20, per_day=20, live_doc=None):
    _ledger(folder, n_days, per_day, truth)
    live = folder / "calibration_live.json"
    if live_doc is not None:
        live.write_text(json.dumps(live_doc))
    log = folder / "retrain_log.jsonl"
    return retrain.run(picks_dir=folder, live_path=live, log_path=log), live, log


def test_split_is_time_ordered() -> None:
    rows = [{"day": f"2026-09-{d:02d}", "p": [0.5] * 7, "y": [0] * 7} for d in range(1, 11) for _ in range(5)]
    fit, hold, cut = retrain.split(rows)
    assert cut == "2026-09-09" and len(hold) == 10 and len(fit) == 40
    assert max(r["day"] for r in fit) < min(r["day"] for r in hold)


def test_fit_never_reads_holdout() -> None:
    # poison the holdout's raw chances: if the fit touched them, it would blow up
    rows = [{"day": f"2026-09-{d:02d}", "p": [0.3 + 0.04 * (k % 10)] * 7, "y": [k % 2] * 7}
            for d in range(1, 21) for k in range(15)]
    fit, hold, _ = retrain.split(rows)
    seen = []
    real = retrain.fit_platt
    retrain.fit_platt = lambda xs, ys, prior, weight=retrain.PRIOR_WEIGHT: (seen.extend(xs), real(xs, ys, prior))[1]
    try:
        for r in hold:
            r["p"] = [float("nan")] * 7
        retrain.evaluate(rows, dict(cal.DEFAULTS))
    finally:
        retrain.fit_platt = real
    assert seen and all(math.isfinite(x) for x in seen)
    assert len(seen) == len(fit) * len(retrain.FAMILIES)


def test_adopts_a_better_fit_and_calibration_reads_it() -> None:
    with tempfile.TemporaryDirectory() as t:
        # reality = the raw chance exactly; the live BTTS (B 0.44) is far too flat
        summary, live, log = _run(Path(t), truth=lambda x: x)
        btts = next(r for r in summary["results"] if r["family"] == "btts")
        assert btts["decision"] == "adopt", btts
        assert btts["brier_new"] < btts["brier_live"] and btts["logloss_new"] < btts["logloss_live"]
        doc = json.loads(live.read_text())
        assert "btts" in doc["families"] and abs(doc["families"]["btts"]["b"] - 1) < 0.35
        assert len(log.read_text().splitlines()) == len(retrain.FAMILIES)
        try:
            cal.use(live)
            a, b = cal.PARAMS["btts"]
            assert (a, b) == (doc["families"]["btts"]["a"], doc["families"]["btts"]["b"])
            assert abs(cal.btts_yes(0.75) - 0.75) < 0.1      # follows the refit, not 0.661
        finally:
            cal.use(cal.LIVE_PATH)
        assert "BTTS CHANGED" in retrain.message(summary)


def test_refuses_a_worse_fit() -> None:
    with tempfile.TemporaryDirectory() as t:
        # the live parameters ARE the truth; the refit can only add noise
        live_doc = {"families": {f: {"a": 0.0, "b": 1.0} for f in retrain.FAMILIES}}
        summary, live, _ = _run(Path(t), truth=lambda x: x, live_doc=live_doc)
        for r in summary["results"]:
            assert r.get("choice") != "raw", "raw is the live calibration here: never a challenger"
            if r["decision"] == "adopt":   # adopted only when strictly better on both scores
                assert r["brier_new"] < r["brier_live"] and r["logloss_new"] < r["logloss_live"]
            else:
                assert json.loads(live.read_text())["families"][r["family"]] == {"a": 0.0, "b": 1.0}
    # and a fit that is plainly worse is refused outright
    hold = [{"day": "2026-09-30", "p": [0.5] * 7, "y": [1] * 7}] * 60
    fit = [{"day": "2026-09-01", "p": [0.5] * 7, "y": [0] * 7}] * 240
    for r in retrain.evaluate(fit + hold, dict(cal.DEFAULTS)):
        assert r.get("choice") != "refit", r
        if r["decision"] == "adopt":   # the raw chance may still beat live, on both scores
            assert r["choice"] == "raw" and r["adopt"] == [0.0, 1.0]
            assert r["brier_raw"] < r["brier_live"] and r["logloss_raw"] < r["logloss_live"]


def test_no_calibration_is_a_candidate() -> None:
    """Architect's "auto" rule: the raw model chance (identity) competes too."""
    random.seed(3)
    rows = []
    for d in range(30):
        for _ in range(10):
            x = random.uniform(0.2, 0.8)
            rows.append({"day": f"2026-09-{1 + d:02d}",
                         "p": [x] * 7, "y": [int(random.random() < x)] * 7})
    # live calibration badly off, refit pulled toward it can't escape: raw is truth
    bad = {f: (1.5, 0.3) for f in retrain.FAMILIES}
    res = retrain.evaluate(rows, bad)
    for r in res:
        if isinstance(retrain.FAMILIES[r["family"]], tuple):
            continue    # these rows aren't a coherent home/draw/away split; see test_double_chance_sums
        assert r["decision"] == "adopt", r
        assert r["brier_raw"] < r["brier_live"] and r["logloss_raw"] < r["logloss_live"]
        assert r["brier_after"] in (r["brier_raw"], r["brier_new"])
    with tempfile.TemporaryDirectory() as t:
        live = Path(t) / "cal.json"
        live.write_text(json.dumps({"families": {f: {"a": 1.5, "b": 0.3} for f in retrain.FAMILIES}}))
        _ledger(Path(t), n_days=30, per_day=10, truth=lambda x: x)
        summary = retrain.run(Path(t), live, Path(t) / "log.jsonl")
        doc = json.loads(live.read_text())["families"]
        for r in summary["results"]:
            if r["decision"] == "adopt":
                assert doc[r["family"]]["choice"] == r["choice"]
                assert [doc[r["family"]]["a"], doc[r["family"]]["b"]] == r["adopt"]
                if r["choice"] == "raw":
                    assert r["adopt"] == [0.0, 1.0] and "no calibration" in retrain.message(summary)
        assert all("logloss_raw" in json.loads(x) for x in (Path(t) / "log.jsonl").read_text().splitlines()
                   if "brier_new" in x)


def test_refuses_small_samples() -> None:
    with tempfile.TemporaryDirectory() as t:
        summary, live, log = _run(Path(t), truth=lambda x: x, n_days=10, per_day=10)
        assert all(r["decision"] == "keep" and "too small" in r["reason"] for r in summary["results"])
        assert not live.exists(), "nothing adopted, nothing written"
        assert log.exists()
        assert "kept (sample too small)" in retrain.message(summary)


def test_falls_back_when_file_missing_or_bad() -> None:
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "nope.json"
        assert cal.load_params(p) == cal.DEFAULTS
        p.write_text("{not json")
        assert cal.load_params(p) == cal.DEFAULTS
        p.write_text(json.dumps({"families": {"btts": {"a": 0.1, "b": -1.0},
                                              "over_2.5": {"a": "x"}, "home": {"a": 0, "b": 1}}}))
        assert cal.load_params(p) == cal.DEFAULTS, "bad slope, bad value, unknown family ignored"
        p.write_text(json.dumps({"families": {"over_2.5": {"a": 0.0, "b": 1.0}}}))
        got = cal.load_params(p)
        assert got["over_2.5"] == (0.0, 1.0) and got["btts"] == cal.DEFAULTS["btts"]
    assert retrain.message({"date": "2026-10-20", "results": []}).endswith("NO DATA — PENDING")


if __name__ == "__main__":
    test_split_is_time_ordered()
    test_fit_never_reads_holdout()
    test_adopts_a_better_fit_and_calibration_reads_it()
    test_refuses_a_worse_fit()
    test_no_calibration_is_a_candidate()
    test_refuses_small_samples()
    test_falls_back_when_file_missing_or_bad()
    print("retrain: OK")


def test_double_chance_sums() -> None:
    """Double chance (2026-10-21): its raw chance is the sum of two result outcomes, and it
    lands when either does."""
    random.seed(5)
    rows = []
    for d in range(30):
        for _ in range(10):
            h = random.uniform(0.2, 0.6)
            dr = random.uniform(0.15, 0.3)
            u = random.random()
            y3 = [int(u < h), int(h <= u < h + dr), int(u >= h + dr)]
            rows.append({"day": f"2026-09-{1 + d:02d}", "p": [h, dr, 1 - h - dr, .5, .5, .5, .5],
                         "y": y3 + [0, 0, 0, 0]})
    r0 = rows[0]
    assert abs(retrain._x(r0, retrain.FAMILIES["dc_1x"]) - (r0["p"][0] + r0["p"][1])) < 1e-12
    assert retrain._y(r0, retrain.FAMILIES["dc_x2"]) == max(r0["y"][1], r0["y"][2])
    res = {r["family"]: r for r in retrain.evaluate(rows, dict(cal.DEFAULTS))}
    for f in ("dc_1x", "dc_x2", "dc_12", "home", "draw", "away"):
        assert res[f]["live"] == [0.0, 1.0], "result families start uncalibrated"
        assert "brier_raw" in res[f]
    assert cal.model_prob("SB:10||Home or Draw", 0.8) == 0.8, "uncalibrated until a fit is adopted"
    print("double chance sums: OK")


test_double_chance_sums()
