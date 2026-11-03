"""
TIP BOARD — the prediction sites' tips run like the board, on paper (Architect 2026-11-03: "as the framework
produces a board and grades it at the end of the day, the same should happen for the tips; then you determine
if it is eligible to influence"). Nothing here picks, stakes or places anything.

Every run (tip_sites.yml, 3 times a day):
  1. BOARD   output/tip_boards/tips_<UK day>.json + .md: each game's tips from every site, whether the sites
             agree, and our model's own 1/X/2 view where the model rated that game (output/picks rated).
  2. GRADE   the day's tips once their games are graded (engine/tipsters.py via monitor/tipster_run.py):
             won / lost per site and for the games where the sites agree.
  3. COMPARE every graded tip with the market (SportyBet's last 1X2 prices before kick-off, de-margined, from
             data/universe) and with our model on the games it rated. Brier scores on the same games, and the
             test that matters: does mixing the site into the market (or the model) make the forecast better?
  4. DECIDE  each site's stage, data/tip_sites/eligibility.json:
               collecting       fewer than MIN_N graded games matched to the market
               no added value   enough games, and the site does not improve the market / the model
               eligible:shadow  enough games and a real improvement (z >= Z_PASS) over the market, and not
                                worse than our model where both exist -> a framework `self-improvement` issue is
                                opened (once) to build it as a SHADOW input, recorded only, walk-forward
             Going live is never automatic: a shadow that beats the live model walk-forward still needs the
             Architect, like every other input (Protected Constants, the CLV gate, staking untouched).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from engine import tip_sites as ts
from engine import tipsters as tp

ROOT = Path(__file__).parent.parent
BOARDS = ROOT / "output" / "tip_boards"
PICKS = ROOT / "output" / "picks"
ELIGIBILITY = ts.FOLDER / "eligibility.json"
UK = ZoneInfo("Europe/London")
MIN_N = 300          # graded games matched to the market before a site can pass (as engine/why_learning.py)
Z_PASS = 1.645       # one-sided 95 %
MIX = 0.2            # the site's weight in the mixed forecast: (1 - MIX) * market + MIX * site


def _uk_day(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UK).date().isoformat()


def _alike(a: str, b: str) -> bool:
    from monitor.bot_grader import _alike as al
    return al(a, b) >= 0.8


def _same_game(h1: str, a1: str, h2: str, a2: str) -> bool:
    return _alike(h1, h2) and _alike(a1, a2)


def _norm3(p) -> list[float] | None:
    if not p or len(p) < 3 or any(x is None for x in p[:3]) or sum(p[:3]) <= 0:
        return None
    s = sum(p[:3])
    return [x / s for x in p[:3]]


def _brier(p: list[float], o: int) -> float:
    return sum((p[i] - (i == o)) ** 2 for i in range(3))


def _outcome(score) -> int | None:
    if not score or len(score) != 2:
        return None
    h, a = score
    return 0 if h > a else 1 if h == a else 2


# ── our model's view ─────────────────────────────────────────────────────────
def model_views(day: str, folder: Path = PICKS) -> list[dict]:
    """The model's 1/X/2 for every game it rated that day (picks_<day>.json "rated")."""
    path = folder / f"picks_{day}.json"
    try:
        rated = json.loads(path.read_text(encoding="utf-8")).get("rated") or []
    except (OSError, ValueError):
        return []
    out = []
    for r in rated:
        p = _norm3(r.get("p"))
        if p and r.get("home") and r.get("away"):
            out.append({"home": r["home"], "away": r["away"], "p": p})
    return out


def _find(views: list[dict], home: str, away: str) -> dict | None:
    return next((v for v in views if _same_game(v["home"], v["away"], home, away)), None)


# ── 1. the board ─────────────────────────────────────────────────────────────
def _pick_of(leg: dict) -> str:
    return {"home": "1", "draw": "X", "away": "2", "1x": "1X", "x2": "X2", "12": "12"}.get(leg.get("selection"), "?")


# which way a tip leans: a double chance leans to its non-draw side; 12 leans nowhere
LEAN = {"1": "home", "1X": "home", "X": "draw", "2": "away", "X2": "away"}


def build_board(day: str, slips: list[dict], views: list[dict]) -> dict:
    games: list[dict] = []
    for s in slips:
        if not str(s.get("poster", "")).startswith("site:"):
            continue
        leg = (s.get("legs") or [{}])[0]
        if not leg.get("kickoff") or _uk_day(leg["kickoff"]) != day:
            continue
        g = next((g for g in games if _same_game(g["home"], g["away"], leg["home"], leg["away"])), None)
        if g is None:
            g = {"home": leg["home"], "away": leg["away"], "kickoff": leg["kickoff"], "tips": {}}
            games.append(g)
        g["tips"][s["poster"][5:]] = {"pick": _pick_of(leg), "p": leg.get("p"), "key": s["post_url"]}
    for g in games:
        dirs = {LEAN.get(t["pick"]) for t in g["tips"].values()}
        g["sites_agree"] = len(g["tips"]) >= 2 and len(dirs) == 1 and None not in dirs
        v = _find(views, g["home"], g["away"])
        if v:
            g["model"] = [round(x, 3) for x in v["p"]]
            fav = ("home", "draw", "away")[max(range(3), key=lambda i: v["p"][i])]
            g["model_agrees"] = sorted({d for d in dirs if d}) == [fav]
    games.sort(key=lambda g: g["kickoff"])
    return {"day": day, "paper_only": True, "games": games,
            "counts": {site: sum(site in g["tips"] for g in games) for site in ts.SITES}}


def board_md(board: dict) -> str:
    L = [f"# Tip board {board['day']} (paper only, nothing placed)", "",
         "| Kick-off (UK) | Game | " + " | ".join(ts.SITES) + " | Sites agree | Our model 1/X/2 |",
         "|---|---|" + "---|" * len(ts.SITES) + "---|---|"]
    for g in board["games"]:
        ko = datetime.fromisoformat(g["kickoff"].replace("Z", "+00:00")).astimezone(UK).strftime("%H:%M")
        cells = [g["tips"].get(s, {}).get("pick", "") for s in ts.SITES]
        m = "/".join(f"{x:.0%}" for x in g["model"]) if g.get("model") else ""
        L.append(f"| {ko} | {g['home']} v {g['away']} | " + " | ".join(cells)
                 + f" | {'yes' if g['sites_agree'] else ''} | {m} |")
    return "\n".join(L) + "\n"


# ── 2. the day's results ─────────────────────────────────────────────────────
def day_results(day: str, board: dict, graded: dict[str, dict]) -> dict:
    """graded: post_url -> graded row (engine/tipsters.py). Won / lost per site and for agreed games."""
    out: dict[str, dict] = defaultdict(lambda: {"won": 0, "lost": 0, "open": 0})
    for g in board["games"]:
        rs = []
        for site, t in g["tips"].items():
            st = (graded.get(t["key"]) or {}).get("status")
            k = "won" if st == "won" else "lost" if st == "lost" else "open"
            out[site][k] += 1
            rs.append(k)
        if g.get("sites_agree"):
            out["sites agree"]["won" if all(r == "won" for r in rs) else "open" if "open" in rs else "lost"] += 1
    return {"day": day, "results": dict(out)}


# ── 3. compare with the market and the model ─────────────────────────────────
def market_index(rows: list[dict]) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("sport") != "football" or not r.get("ko"):
            continue
        last = (r.get("last") or {}).get("p") or {}
        odds = last.get("1x2")
        if not odds or len(odds) != 3 or any(not x or x <= 1 for x in odds):
            continue
        idx[r["ko"][:10]].append({"home": r.get("home", ""), "away": r.get("away", ""),
                                  "p": _norm3([1 / x for x in odds])})
    return idx


def compare(graded_rows: list[dict], market: dict[str, list[dict]], views_by_day: dict[str, list[dict]]) -> dict:
    """Per site: Brier of the site, the market and the model on the same graded games, and the paired gain of
    mixing the site into the market (and into the model)."""
    acc: dict[str, dict] = defaultdict(lambda: {"vs_market": [], "vs_model": []})
    for g in graded_rows:
        if not str(g.get("poster", "")).startswith("site:") or g.get("status") not in ("won", "lost"):
            continue
        leg = (g.get("legs") or [{}])[0]
        p, o = _norm3(leg.get("p")), _outcome(leg.get("score"))
        if p is None or o is None or not leg.get("kickoff"):
            continue
        site = g["poster"][5:]
        day = leg["kickoff"][:10]
        m = next((x for d in {day, _uk_day(leg["kickoff"])} for x in market.get(d, [])
                  if _same_game(x["home"], x["away"], leg["home"], leg["away"])), None)
        if m:
            mix = [(1 - MIX) * m["p"][i] + MIX * p[i] for i in range(3)]
            acc[site]["vs_market"].append((_brier(p, o), _brier(m["p"], o), _brier(mix, o)))
        v = _find(views_by_day.get(_uk_day(leg["kickoff"]), []), leg["home"], leg["away"])
        if v:
            mix = [(1 - MIX) * v["p"][i] + MIX * p[i] for i in range(3)]
            acc[site]["vs_model"].append((_brier(p, o), _brier(v["p"], o), _brier(mix, o)))
    out = {}
    for site, a in acc.items():
        out[site] = {k: _summ(v) for k, v in a.items()}
    return out


def _summ(rows: list[tuple[float, float, float]]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    gain = [b - c for _, b, c in rows]            # > 0: mixing the site in lowered the Brier score
    mean = sum(gain) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in gain) / (n - 1)) if n > 1 else 0.0
    z = mean / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"n": n, "brier_site": round(sum(r[0] for r in rows) / n, 4),
            "brier_base": round(sum(r[1] for r in rows) / n, 4), "mix_gain": round(mean, 5), "z": round(z, 2)}


# ── 4. the decision ──────────────────────────────────────────────────────────
def decide(cmp: dict) -> dict:
    stages = {}
    for site in ts.SITES:
        c = cmp.get(site) or {}
        vm, vd = c.get("vs_market") or {"n": 0}, c.get("vs_model") or {"n": 0}
        if vm["n"] < MIN_N:
            stage, why = "collecting", f"{vm['n']}/{MIN_N} graded games matched to the market"
        elif vm.get("z", 0) >= Z_PASS and (vd["n"] < 30 or vd.get("mix_gain", 0) >= 0):
            stage, why = "eligible:shadow", (f"mixing it into the market improves the forecast (z {vm['z']}, "
                                             f"{vm['n']} games); not worse than our model ({vd['n']} games)")
        else:
            stage, why = "no added value", (f"z {vm.get('z')} on {vm['n']} games (needs {Z_PASS})"
                                            + (f"; worse than our model on {vd['n']}" if vd.get("mix_gain", 0) < 0
                                               and vd["n"] >= 30 else ""))
        stages[site] = {"stage": stage, "why": why, "vs_market": vm, "vs_model": vd}
    return stages


ISSUE_TITLE = "tip site {site}: build as a SHADOW model input (passed the tip-board eligibility test)"


def issue_body(site: str, st: dict) -> str:
    return (f"The tip board's eligibility test (engine/tip_board.py) passed for **{site}**: {st['why']}.\n\n"
            f"Numbers: vs market {json.dumps(st['vs_market'])}; vs our model {json.dumps(st['vs_model'])}.\n\n"
            "**Build (shadow only):** add the site's 1/X/2 percentages as a recorded-only input next to the live "
            "model, evaluated walk-forward like engine/why_learning.py. Never change a pick rule, stake, the CLV gate, "
            "ARCHITECT_SIGNOFF or any protected file. Going live needs the Architect.\n\n"
            "**Reject if:** the walk-forward gain disappears out of sample, or the site's coverage is too thin to "
            "matter.\n\n_Opened automatically by tip_sites.yml._")


def run(now: datetime, open_issue=None) -> list[str]:
    """Board for today and tomorrow, results for the last 3 days, the comparison and the stages."""
    from engine import universe as uv
    slips = tp.load_slips(ts.FOLDER)
    graded_rows = tp.load_graded(ts.FOLDER)
    graded = {g["post_url"]: g for g in graded_rows}
    BOARDS.mkdir(parents=True, exist_ok=True)
    notes = []
    today = now.astimezone(UK).date()
    days = sorted({_uk_day((s.get("legs") or [{}])[0].get("kickoff") or now.isoformat()) for s in slips})
    views_by_day = {d: model_views(d) for d in days}
    for d in days:
        if d < (today - timedelta(days=3)).isoformat():
            continue
        board = build_board(d, slips, views_by_day[d])
        board["results"] = day_results(d, board, graded)["results"]
        (BOARDS / f"tips_{d}.json").write_text(json.dumps(board, indent=1, ensure_ascii=False), encoding="utf-8")
        (BOARDS / f"tips_{d}.md").write_text(board_md(board), encoding="utf-8")
        notes.append(f"tip board {d}: {len(board['games'])} games")
    stages = decide(compare(graded_rows, market_index(uv.load_graded()), views_by_day))
    old = {}
    try:
        old = json.loads(ELIGIBILITY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    for site, st in stages.items():
        st["issue"] = (old.get(site) or {}).get("issue")
        if st["stage"] == "eligible:shadow" and not st["issue"] and open_issue is not None:
            st["issue"] = open_issue(ISSUE_TITLE.format(site=site), issue_body(site, st))
        notes.append(f"{site}: {st['stage']} ({st['why']})")
    ELIGIBILITY.write_text(json.dumps({**stages, "_updated": now.strftime("%Y-%m-%dT%H:%MZ")}, indent=1),
                           encoding="utf-8")
    return notes


def report_lines(day: str) -> list[str]:
    """Lines for the 23:00 report: the day's paper record per site and each site's stage."""
    try:
        board = json.loads((BOARDS / f"tips_{day}.json").read_text(encoding="utf-8"))
        stages = json.loads(ELIGIBILITY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    L = ["TIP SITES (paper, nothing placed)"]
    for site, r in sorted((board.get("results") or {}).items()):
        stage = (stages.get(site) or {}).get("stage", "")
        L.append(f"{site}: {r['won']} won, {r['lost']} lost, {r['open']} open"
                 + (f" · {stage}" if stage else ""))
    return L if len(L) > 1 else []

