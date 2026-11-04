"""
INPUTS STUDY (Architect 2026-10-28): do head-to-head, recent form (home/away
split, points and goal difference) and last-5 xG add information BEYOND the
current model, on matches the fit had not seen?

PART A — head-to-head and form, football-data seasons (the same leagues and
seasons as selection_study / rest_study). The current model (Dixon-Coles,
refitted every 14 days on matches before the cut, backtest/clv_backtest)
prices every test match; H2H meetings reach back up to six seasons. Each
feature is tested walk-forward by day (engine/walkforward logic): its weight
is fitted on EARLIER days only, the day is scored with and without it —
Brier, log loss, and closing-line value of the bets each version would take
(home win / over 2.5 when chance x opening price >= 1 + EDGE; CLV = opening /
closing price - 1, Pinnacle where the file has it).

Motivation / table (issue #218): table_ppg_gap and table_stakes (engine/inputs
table_features, season-to-date table before the day) are tested in part A.

PART C — lineups / injuries (issue #217): the share of each side's best XI
that is out (data/features news block, captured before kick-off by
monitor/news_check) against the model's chance on the board's rated fixtures.

PART B — last-5 xG, the board's own rated fixtures (output/picks "rated":
the live model's chance) against xG form from data/match_study before the
day.

A study, not a selector: a feature goes live only through the retrain /
promotion path, and only with verdict ADDS INFORMATION on both Brier and log
loss. Writes backtest/INPUTS_STUDY.md and memory/inputs_gate.json.

    python backtest/inputs_study.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import inputs as ip  # noqa: E402
from engine import walkforward as wf  # noqa: E402

OUT = ROOT / "backtest" / "INPUTS_STUDY.md"
GATE = ROOT / "memory" / "inputs_gate.json"
H2H_BACK = ("1819", "1920", "2021", "2122", "2223", "2324")
EDGE = 0.03


def _prev_seasons(s: str, k: int) -> list[str]:
    a = int(s[:2])
    return [f"{a - i:02d}{a - i + 1:02d}" for i in range(1, k + 1)]


def wf_preds(rows: list[tuple]) -> tuple[dict, list[tuple]]:
    """rows: (day, p_model, y, feature, extra). Returns the summary and the
    scored rows (day, p, q, y, extra) — q = model + feature, weight fitted on
    earlier days only."""
    have = sorted((r for r in rows if isinstance(r[3], (int, float))), key=lambda r: r[0])
    days = sorted({r[0] for r in have})
    out = []
    coef = None
    j = 0
    for d in days:
        while j < len(have) and have[j][0] < d:
            j += 1
        train = have[:j]
        if len(train) < wf.MIN_TRAIN:
            continue
        mu = sum(r[3] for r in train) / len(train)
        sd = math.sqrt(sum((r[3] - mu) ** 2 for r in train) / len(train)) or 1.0
        coef = wf.fit_offset([(r[1], r[2], (r[3] - mu) / sd) for r in train])
        for r in have[j:]:
            if r[0] != d:
                break
            q = wf._sig(wf._logit(r[1]) + coef * (r[3] - mu) / sd)
            out.append((d, r[1], q, r[2], r[4]))
    gb = [(p - y) ** 2 - (q - y) ** 2 for _d, p, q, y, _e in out]
    gl = [ip.log_loss(p, y) - ip.log_loss(q, y) for _d, p, q, y, _e in out]
    mb, sb = wf._mean_se(gb)
    ml, sl = wf._mean_se(gl)
    n = len(out)

    def verdict(m, se):
        if n < 100:
            return "NOT ENOUGH DATA"
        return "ADDS INFORMATION" if m > 2 * se else "HURTS" if m < -2 * se else "NO CLEAR EFFECT"
    s = {"rows": len(have), "scored": n,
         "brier_model": round(sum((p - y) ** 2 for _d, p, _q, y, _e in out) / n, 4) if n else None,
         "brier_gain": round(mb, 5), "brier_se": round(sb, 5),
         "logloss_model": round(sum(ip.log_loss(p, y) for _d, p, _q, y, _e in out) / n, 4) if n else None,
         "logloss_gain": round(ml, 5), "logloss_se": round(sl, 5),
         "last_coef": None if coef is None else round(coef, 3),
         "verdict": verdict(mb, sb), "verdict_logloss": verdict(ml, sl)}
    return s, out


def clv(scored: list[tuple]) -> dict:
    """Bets each version takes (chance x opening >= 1 + EDGE) and their CLV."""
    def side(use_q):
        c = []
        for _d, p, q, _y, e in scored:
            o, cl = (e or {}).get("open"), (e or {}).get("close")
            if not o or not cl:
                continue
            if (q if use_q else p) * o >= 1 + EDGE:
                c.append(o / cl - 1)
        m, se = wf._mean_se(c)
        return {"bets": len(c), "clv": round(100 * m, 2), "clv_se": round(100 * se, 2)}
    return {"model": side(False), "with_feature": side(True)}


# ── part A ──────────────────────────────────────────────────────────────────


def part_a() -> tuple[dict, dict]:
    from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
    from backtest.selection_study import GROUPS
    from data.football_data_source import load_league
    from engine.dixon_coles import predict
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="", refit_every_days=14)
    feats = ("h2h_gd", "h2h_goals", "form_ppg", "form_gd", "form_venue_ppg", "form_goals",
             "table_ppg_gap", "table_stakes")
    rows: dict[tuple, list] = {(o, f): [] for o in ("home win", "over 2.5") for f in feats}
    cover = {"matches": 0, "with_h2h": 0, "leagues": 0}
    for carry_s, test_s, leagues in GROUPS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception as e:  # noqa: BLE001
                print(f"  {lg} {test_s}: skipped ({str(e)[:60]})")
                continue
            older = []
            for s in _prev_seasons(carry_s, len(H2H_BACK)):
                try:
                    older += load_league(lg, s)[0]
                except Exception:  # noqa: BLE001
                    pass
            cover["leagues"] += 1
            hist_model = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            H = ip.History(ip.from_results(older + carry + test))
            warm = None
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                if not block:
                    continue
                model, _ = get_model(lg, cut, hist_model, cfg, warm)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                for m in block:
                    p = predict(model, m.home_team, m.away_team)
                    if p is None:
                        continue
                    f = ip.fixture_features(H, m.home_team, m.away_team, m.date)
                    cover["matches"] += 1
                    cover["with_h2h"] += f["h2h_gd"] is not None
                    od = m.odds
                    eh = {"open": od.home.open, "close": od.home.close} if od else None
                    eo = {"open": od.over25.open, "close": od.over25.close} if od else None
                    yh, yo = int(m.fthg > m.ftag), int(m.fthg + m.ftag > 2)
                    for k in feats:
                        rows[("home win", k)].append((m.date, p.p_home, yh, f[k], eh))
                        rows[("over 2.5", k)].append((m.date, p.p_over_25, yo, f[k], eo))
            print(f"  {lg} {test_s}: {cover['matches']} matches so far")
    res = {}
    for key, rs in rows.items():
        s, scored = wf_preds(rs)
        s["clv"] = clv(scored)
        res[f"{key[0]} | {key[1]}"] = s
    return res, cover


# ── part B ──────────────────────────────────────────────────────────────────


def part_b() -> tuple[dict, dict]:
    from data import match_study as ms
    from engine.name_match import same_club
    study = sorted(ms.load(), key=lambda r: r["ko"])
    by_day: dict[str, list[dict]] = {}
    for r in study:
        by_day.setdefault(r["ko"][:10], []).append(r)
    rows: dict[str, list] = {"home win | xG edge": [], "over 2.5 | xG total": [], "BTTS yes | xG total": []}
    n = found = 0
    for path in sorted((ROOT / "output" / "picks").glob("picks_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for r in doc.get("rated", []):
            ft = r.get("ft") or ""
            pr = r.get("p") or []
            if "-" not in ft or len(pr) < 7 or r.get("src", "model") != "model":
                continue
            try:
                hg, ag = (int(x) for x in ft.split("-"))
            except ValueError:
                continue
            n += 1
            day = (r.get("kickoff") or doc["date"])[:10]
            home, away = r.get("home") or "", r.get("away") or ""
            if not home and " v " in (r.get("fixture") or ""):
                home, away = r["fixture"].split(" v ", 1)
            row = next((x for x in by_day.get(day, []) if same_club(x["home"]["name"], home)
                        and same_club(x["away"]["name"], away)), None)
            if row is None:
                continue
            xh = ip.xg_form(study, row["home"]["id"], day)
            xa = ip.xg_form(study, row["away"]["id"], day)
            if not xh or not xa:
                continue
            found += 1
            edge = (xh["xgf"] - xh["xga"]) - (xa["xgf"] - xa["xga"])
            total = xh["xgf"] + xh["xga"] + xa["xgf"] + xa["xga"]
            for name, pk, y, f in (("home win | xG edge", 0, int(hg > ag), edge),
                                   ("over 2.5 | xG total", 4, int(hg + ag > 2), total),
                                   ("BTTS yes | xG total", 6, int(hg > 0 and ag > 0), total)):
                p = pr[pk]
                if isinstance(p, (int, float)) and 0 < p < 1:
                    rows[name].append((day, float(p), y, f, None))
    res = {k: wf_preds(v)[0] for k, v in rows.items()}
    return res, {"rated_graded": n, "with_xg_form": found}


# ── part C ──────────────────────────────────────────────────────────────────


def news_rows(feature_docs: list[tuple[str, dict]]) -> dict[str, list]:
    """(day, doc) pairs from data/features -> rows for wf_preds. A fixture with
    no graded result, no model chance or no news edge is skipped (HR35: never
    filled in). Features: edge = away missing share - home missing share
    (positive favours the home side), total = both shares added."""
    rows: dict[str, list] = {"home win | missing edge": [], "away win | missing edge": [],
                             "over 2.5 | missing total": [], "BTTS yes | missing total": []}
    for day, doc in feature_docs:
        for r in doc.values():
            ft, pr, nw = r.get("ft") or "", r.get("model_p"), r.get("news") or {}
            hm, am = nw.get("home_missing"), nw.get("away_missing")
            if "-" not in ft or not isinstance(pr, list) or len(pr) < 7:
                continue
            if not isinstance(hm, (int, float)) or not isinstance(am, (int, float)):
                continue
            try:
                hg, ag = (int(x) for x in ft.split("-"))
            except ValueError:
                continue
            sharp = (r.get("close") or {}).get("sharp") or {}
            for name, pk, y, f, ck in (("home win | missing edge", 0, int(hg > ag), am - hm, "home"),
                                       ("away win | missing edge", 2, int(ag > hg), am - hm, "away"),
                                       ("over 2.5 | missing total", 4, int(hg + ag > 2), am + hm, "over25"),
                                       ("BTTS yes | missing total", 6, int(hg > 0 and ag > 0), am + hm, "btts")):
                p = pr[pk]
                if isinstance(p, (int, float)) and 0 < p < 1:
                    rows[name].append((day, float(p), y, f, {"sharp": sharp.get(ck)}))
    return rows


def vs_close(scored: list[tuple]) -> dict:
    """Brier of the model, model + feature and the sharp book's closing chance on the
    scored rows that have all three. The feature files hold the CLOSING chance only,
    no opening price, so a CLV (opening / closing - 1) cannot be built from them:
    it reads PENDING (HR35), never a made-up number."""
    rows = [(p, q, y, e["sharp"]) for _d, p, q, y, e in scored
            if isinstance((e or {}).get("sharp"), (int, float)) and 0 < e["sharp"] < 1]
    n = len(rows)
    if not n:
        return {"n": 0, "model": None, "with_feature": None, "sharp_close": None, "clv": "PENDING"}
    br = [round(sum((x[i] - x[2]) ** 2 for x in rows) / n, 4) for i in (0, 1, 3)]
    return {"n": n, "model": br[0], "with_feature": br[1], "sharp_close": br[2], "clv": "PENDING"}


def part_c() -> tuple[dict, dict]:
    docs = []
    for path in sorted((ROOT / "data" / "features").glob("features_*.json")):
        docs.append((path.stem.split("_", 1)[1], json.loads(path.read_text(encoding="utf-8"))))
    rows = news_rows(docs)
    total = sum(len(d) for _day, d in docs)
    res = {}
    for k, v in rows.items():
        res[k], scored = wf_preds(v)
        res[k]["vs_close"] = vs_close(scored)
    return res, {"fixtures": total, "with_news_and_result": len(rows["home win | missing edge"]),
                 "days": len(docs)}


def report(a: dict, ca: dict, b: dict, cb: dict, news: dict, cc: dict) -> str:
    L = ["# INPUTS STUDY — head-to-head, form and last-5 xG beyond the current model", "",
         "Written by `backtest/inputs_study.py` (Architect 2026-10-28). Walk-forward: each feature's "
         "weight is fitted on earlier days only and the day is scored with and without it. Gain > 0 "
         "means the feature helped; a verdict needs 100+ scored matches and 2 standard errors. CLV: "
         f"the bets each version takes at chance x opening >= {1 + EDGE:.2f}, opening / closing - 1.", "",
         f"## A. Head-to-head and form — football-data, current Dixon-Coles model "
         f"({ca['matches']} test matches, {ca['with_h2h']} with a past meeting, {ca['leagues']} league-seasons)", "",
         "| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict "
         "(Brier / log loss) | CLV model (bets) | CLV with feature (bets) |",
         "|---|---|---|---|---|---|---|---|"]
    for k, s in a.items():
        c = s["clv"]
        L.append(f"| {k} | {s['scored']} | {s['brier_model']} | {s['brier_gain']:+.5f} ± {s['brier_se']:.5f} | "
                 f"{s['logloss_gain']:+.5f} ± {s['logloss_se']:.5f} | {s['verdict']} / {s['verdict_logloss']} | "
                 f"{c['model']['clv']:+.2f}% ({c['model']['bets']}) | "
                 f"{c['with_feature']['clv']:+.2f}% ({c['with_feature']['bets']}) |")
    L += ["", f"## B. Last-5 xG — the board's rated fixtures ({cb['rated_graded']} graded, "
          f"{cb['with_xg_form']} with 3+ studied matches a side)", "",
          "| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |",
          "|---|---|---|---|---|---|"]
    for k, s in b.items():
        L.append(f"| {k} | {s['scored']} | {s['brier_model']} | {s['brier_gain']:+.5f} ± {s['brier_se']:.5f} | "
                 f"{s['logloss_gain']:+.5f} ± {s['logloss_se']:.5f} | {s['verdict']} / {s['verdict_logloss']} |")
    L += ["", f"## C. Lineups / injuries — share of the best XI unavailable ({cc['with_news_and_result']} graded "
          f"fixtures with news, of {cc['fixtures']} on {cc['days']} days)", "",
          "| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict | "
          "Brier on rows with a sharp close: model / with feature / sharp close (rows) | CLV |",
          "|---|---|---|---|---|---|---|---|"]
    for k, s in news.items():
        brier = "PENDING" if s["brier_model"] is None else s["brier_model"]
        v = s["vs_close"]
        vc = ("PENDING" if not v["n"] else f"{v['model']} / {v['with_feature']} / {v['sharp_close']} ({v['n']})")
        L.append(f"| {k} | {s['scored']} | {brier} | {s['brier_gain']:+.5f} ± {s['brier_se']:.5f} | "
                 f"{s['logloss_gain']:+.5f} ± {s['logloss_se']:.5f} | {s['verdict']} / {s['verdict_logloss']} | "
                 f"{vc} | {v['clv']} (features hold the close only) |")
    live = [k for k, s in {**a, **b, **news}.items()
            if s["verdict"] == "ADDS INFORMATION" and s["verdict_logloss"] == "ADDS INFORMATION"]
    L += ["", "## Verdict", "",
          ("Passes on both Brier and log loss (candidate for the retrain / promotion path): "
           + ", ".join(live)) if live else
          "No candidate input improves the model out of sample on both Brier and log loss: none goes live.",
          "", "A feature that adds information to the probability is still not an edge: the CLV columns say "
          "whether the bets it changes beat the close."]
    return "\n".join(L) + "\n"


def main() -> int:
    a, ca = part_a()
    b, cb = part_b()
    c, cc = part_c()
    OUT.write_text(report(a, ca, b, cb, c, cc), encoding="utf-8")
    live = sorted(k for k, s in {**a, **b, **c}.items()
                  if s["verdict"] == "ADDS INFORMATION" and s["verdict_logloss"] == "ADDS INFORMATION")
    GATE.write_text(json.dumps({"evaluated_at": date.today().isoformat(), "passes": live,
                                "coverage": {**ca, **cb, **{"news_" + k: v for k, v in cc.items()}}, "part_a": a, "part_b": b,
                                "part_c": c}, indent=1), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
