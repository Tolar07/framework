"""
WEEKLY SELF-IMPROVEMENT REVIEW (Architect 2026-10-28: "the autonomous engine
should be asking, what do I need to do better? How can I improve things? And
an answer should be provided to it").

Every week (self_improve.yml) the framework asks itself three questions and
writes the answers down — no LLM needed for these:

 (a) INPUTS — what do strong football models use, and does this framework use
     it? Each input is checked against the code and the latest evidence
     (memory/inputs_gate.json, the study reports), not a hand-kept list:
     LIVE (moves the probability), TESTED (walk-forward said no gain — stays
     out until the data says otherwise), CONTEXT (shown / veto / LLM prompt
     only, never tested as a probability input) or MISSING.
 (b) LOOPS — every learning loop and whether it produced new tested
     evidence this week (monitor/learning_watch, 7-day allowance).
 (c) PROPOSALS — the improvements ranked by expected value (value of the
     input in published football models x how far we are from using it x
     data we already hold), each written as a framework issue labelled
     `self-improvement` (one per title, never duplicated).

 (e) EVERY SPORT (framework#356, order 50: every sport inherits football + basketball) -
     the same question for basketball (NBA + world basketball / NCAA) and each rollout sport
     (ice hockey and engine/multisport.SPORTS): its graded record (data/ice_hockey/scoreboard.json,
     data/multisport/<sport>/scoreboard.json, the NBA and world basketball picks), its experiment
     slot (memory/strategies.json) and its model's walk-forward Brier. Each sport gets at most ONE
     proposal a week with ONE buildable deliverable from data already held (a study script + report,
     a grading fix, a promotion for the Architect). Too little graded yet = PENDING, never an issue:
     a proposal is never blocked on data that does not exist. Opened as `self-improvement` issues
     (one per title); an open one gets this week's numbers as a comment instead of a duplicate.

 (d) SEARCH, BUILD, MERGE, TELL (order 49) — the workflow's second job is a
     fresh Claude Code run (Sonnet, GitHub Actions): it searches the web for
     what strong models use, opens what's lacking as issues, builds the top
     open proposal RECORD-ONLY or as a SHADOW with tests, merges it on green
     (Architect 2026-10-28: an unmerged PR can be lost) and the Architect gets
     a plain summary on Telegram (`--telegram`). Nothing it builds changes a
     pick, stake or threshold: promotion stays with the walk-forward machinery.

Output: backtest/SELF_IMPROVEMENT.md, memory/self_improvement.json.

    python scripts/self_improve.py [--issues]   # --issues: open the proposals
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_MD = ROOT / "backtest" / "SELF_IMPROVEMENT.md"
OUT_JSON = ROOT / "memory" / "self_improvement.json"
LABEL = "self-improvement"


def _grep(pattern: str, paths: tuple[str, ...]) -> list[str]:
    import re
    rx = re.compile(pattern, re.I)
    hits = []
    for p in paths:
        base = ROOT / p
        files = [base] if base.is_file() else list(base.rglob("*.py")) if base.exists() else []
        for f in files:
            try:
                if rx.search(f.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(str(f.relative_to(ROOT)).replace("\\", "/"))
            except OSError:
                continue
    return hits


def _gate() -> dict:
    try:
        return json.loads((ROOT / "memory" / "inputs_gate.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


MODEL = ("engine/dixon_coles.py", "engine/elo.py", "engine/calibration.py", "engine/national_elo.py")
CONTEXT = ("engine/reasoning.py", "engine/records", "engine/form.py", "engine/team_news.py",
           "pipeline", "engine/features.py", "engine/tactics.py")

# (input, why strong models use it, value 1-5, detector pattern, gate key prefix, study report)
INPUTS = [
    ("team strength", "ratings from results / goals (Dixon-Coles, Elo)", 5, r"dixon|elo", None, None),
    ("xG for / against", "chance quality beats goals as a strength signal", 5, r"\bxg\b|xg_", "xG", None),
    ("recent form", "last 5-6, home/away split", 3, r"form(_|)", "form_", "backtest/INPUTS_STUDY.md"),
    ("head-to-head", "last meetings, venue-aware", 1, r"h2h_gd|head.to.head", "h2h_", "backtest/INPUTS_STUDY.md"),
    ("rest days / congestion", "days since last match, games in 14 days", 2, r"rest.days|congestion",
     None, "backtest/REST_STUDY.md"),
    ("travel distance", "away-side travel, time zones", 1, r"travel", None, None),
    ("lineups / injuries", "expected XI strength v full strength", 5, r"lineup|injur", "missing ",
     "backtest/INPUTS_STUDY.md"),            # part C (PR #262 / #304)
    ("motivation / table", "title, Europe, relegation stakes late in season", 2, r"motivation|standings",
     "table_", "backtest/INPUTS_STUDY.md"),  # part A: table_ppg_gap, table_stakes (PR #268)
    ("referee", "card and penalty tendencies", 1, r"referee", None, None),
    ("weather", "wind / rain lowers goals", 1, r"weather", None, None),
    ("market moves", "opening -> closing drift, sharp money", 4, r"drift_pct|bsteamb", None,
     "backtest/MATCHBOOK_PRICE_STUDY.md"),
]


def audit_inputs() -> list[dict]:
    gate = _gate()
    rows = []
    for name, why, value, pat, gkey, study in INPUTS:
        in_model = _grep(pat, MODEL)
        in_ctx = _grep(pat, CONTEXT)
        tested = []
        if gkey:
            for part in ("part_a", "part_b", "part_c"):
                for k, s in (gate.get(part) or {}).items():
                    feat = k.split(" | ")[-1]
                    if feat.startswith(gkey) or gkey in k:
                        tested.append(f"{k}: {s.get('verdict')} (Brier {s.get('brier_gain'):+.5f})")
        passed = [k for k in gate.get("passes", []) if gkey and gkey in k]
        if in_model or passed:
            status = "LIVE"
        elif tested or (study and (ROOT / study).exists()):
            status = "TESTED"
        elif in_ctx:
            status = "CONTEXT"
        else:
            status = "MISSING"
        rows.append({"input": name, "why": why, "value": value, "status": status,
                     "where": (in_model or in_ctx)[:3], "evidence": tested[:3] or ([study] if study else [])})
    return rows


def audit_loops() -> list[dict]:
    from monitor import learning_watch as lw
    loops = [(n, w, k, r, f, 7) for n, w, k, r, f, _a in lw.LOOPS]
    return lw.check(loops=loops)


GAP = {"MISSING": 1.0, "CONTEXT": 0.7, "TESTED": 0.15, "LIVE": 0.0}


def promotions(root: Path | None = None) -> list[dict]:
    """Bot-training plan (2026-11-01): a learning loop that has EARNED a say becomes a proposal for the
    Architect — the evidence and what promotion would change. Nothing here promotes anything."""
    root = root or ROOT

    def rd(rel: str) -> dict:
        try:
            return json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    out = []
    lw = rd("memory/learned_weights.json")
    wf = lw.get("walk_forward") or {}
    if wf.get("beats_market"):
        top = sorted(((k, v["w"]) for k, v in (lw.get("weights") or {}).items()), key=lambda kv: -abs(kv[1]))[:4]
        out.append({"title": "Promotion ready: learned weights beat the market out of sample", "ev": 5.0,
                    "kind": "promote",
                    "body": f"engine/learned_weights.py: {wf['n']} walk-forward picks, Brier {wf['learned_brier']} "
                            f"v market {wf['market_brier']}. Largest weights: {top}. Promotion = the board's chance "
                            "(or the panel's probability) uses the learned model. Architect decision."})
    for k, v in (rd("memory/fact_record.json").get("facts") or {}).items():
        if v.get("trusted") and abs(v.get("residual") or 0) >= 0.05:
            out.append({"title": f"Promotion ready: fact '{k}' moves results beyond the market", "ev": 4.0,
                        "kind": "promote",
                        "body": f"engine/fact_sheet.py study: {v['n']} graded picks, won {v['won_rate']:.0%} v market "
                                f"{v['market_rate']:.0%} (residual {v['residual']:+.1%}). Promotion = the fact becomes "
                                "a model input via engine/learned_weights.py. Architect decision."})
    for b in rd("data/bots/learning.json").get("bots") or []:
        for v in b.get("variants") or []:
            if str(v.get("verdict") or "") == "challenger beats live":
                out.append({"title": f"Promotion ready: {b['bot']} challenger {v['variant']} beats {v['baseline']}",
                            "ev": 4.5, "kind": "promote",
                            "body": f"monitor/bot_learning.py (the bot's own paper challenger): graded {v['graded']} v "
                                    f"{v['baseline_graded']}, level-stake ROI {(v.get('roi') or 0):+.1%} v "
                                    f"{(v.get('baseline_roi') or 0):+.1%}, CLV {(v.get('clv') or 0):+.1%} v "
                                    f"{(v.get('baseline_clv') or 0):+.1%}. Promotion = the bot's live rule takes the "
                                    "challenger's setting. Architect decision (stakes / thresholds)."})
    qpath = root / "memory" / "strategy_queue.jsonl"
    try:
        queue = [json.loads(x) for x in qpath.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        queue = []
    for q in queue:
        if q.get("kind") == "candidate_feature":
            out.append({"title": f"Model input proven: {q.get('hypothesis')} — wire it in as a shadow feature",
                        "ev": 3.5, "kind": "build",
                        "body": f"research/runner.py accepted {q.get('hypothesis')}: {str(q.get('idea'))[:200]} "
                                f"(evidence {q.get('evidence')}). Nothing consumes candidate features yet: build it as "
                                "a model input in SHADOW (engine/inputs.py style), add it to engine/learned_weights.py "
                                "and report walk-forward Brier / CLV. Promotion to the live model stays with the "
                                "Architect."})
    for fam, a in (rd("memory/panel_record.json").get("authority") or {}).items():
        if (a or {}).get("earned"):
            out.append({"title": f"Promotion ready: verdict panel earned authority in {fam}", "ev": 4.0,
                        "kind": "promote",
                        "body": f"engine/verdict_panel.py earned_authority: {a}. Promotion = VERDICT_STAKES on for this "
                                "family. Architect decision."})
    return out


def proposals(inputs: list[dict], loops: list[dict]) -> list[dict]:
    out = promotions()
    for r in loops:
        if not r["ok"]:
            out.append({"title": f"Learning loop stalled: {r['loop']}", "ev": 10.0, "kind": "fix",
                        "body": f"{r['what']} produced no new tested evidence in 7 days ({r['note']}). "
                                "Find why at source and fix it (see monitor/learning_watch.py)."})
    for r in inputs:
        ev = r["value"] * GAP[r["status"]]
        if ev <= 0.3:
            continue
        if r["status"] == "CONTEXT":
            what = (f"'{r['input']}' is read ({', '.join(r['where']) or 'context'}) but never tested as a "
                    "probability input. Build it as a feature (engine/inputs.py style, before-the-day only), "
                    "add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.")
        elif r["status"] == "MISSING":
            what = (f"'{r['input']}' ({r['why']}) is not used anywhere. Find a free source, capture it "
                    "RECORD-ONLY first, then test it walk-forward like backtest/inputs_study.py.")
        else:
            what = (f"'{r['input']}' was tested and is not a live probability input "
                    f"({'; '.join(r['evidence'][:2])}). Re-test when the data has grown; nothing to build now.")
        out.append({"title": f"Model input: {r['input']} ({r['status'].lower()})", "ev": round(ev, 2),
                    "kind": "input", "body": what})
    return sorted(out, key=lambda x: -x["ev"])


# -- (e) every sport (framework#356) ----------------------------------------------------------
MIN_PICKS = 30            # graded picks before the picks' CLV is judged
MIN_SIDES = 100           # graded sides before "the board makes no picks" is a finding, not noise
MIN_BRIER_N = 200         # walk-forward scored games before the model's Brier is judged
COIN_BRIER = 0.25         # a 50/50 guess on a two-way winner market


def rollout_sports() -> list[str]:
    """Basketball, ice hockey and every engine/multisport.SPORTS entry (the order-50 rollout)."""
    from engine import multisport as ms
    return ["basketball", "ice_hockey", *ms.SPORTS]


def _label(sport: str) -> str:
    return sport.replace("_", " ").capitalize()


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _graded(picks: list[dict], clv_key: str) -> dict:
    g = [p for p in picks if p.get("result") in ("won", "lost") and p.get("price")]
    clv = [p[clv_key] for p in g if p.get(clv_key) is not None]
    return {"picks": len(g), "won": sum(p["result"] == "won" for p in g),
            "pnl": round(sum((p["price"] - 1) if p["result"] == "won" else -1.0 for p in g), 3),
            "clv_avg": round(sum(clv) / len(clv), 4) if clv else None, "clv_n": len(clv)}


def sport_record(sport: str, root: Path | None = None) -> dict:
    """One sport's graded record: picks, won, return (1 unit), value vs close, graded sides, model Brier.
    Basketball = the NBA board's regular-season picks + world basketball / NCAA picks (close_value);
    the rollout sports = their board's scoreboard (written by run_hockey.py / run_multisport.py --grade)."""
    root = root or ROOT
    if sport == "basketball":
        picks: list[dict] = []
        boards = 0
        for f in sorted((root / "output" / "picks").glob("nba_2*.json")):
            boards += 1
            picks += [p for p in _read(f).get("picks") or [] if p.get("stage") != "preseason"]
        for f in sorted((root / "output" / "world_basketball").glob("wb_*.json")):
            boards += 1
            picks += _read(f).get("picks") or []
        return {"sport": sport, "boards": boards, "scoreboard": "output/picks/nba_*.json + output/world_basketball/",
                **_graded(picks, "close_value"), "sides": None, "brier": None, "brier_n": 0}
    if sport == "ice_hockey":
        rel, boards = "data/ice_hockey/scoreboard.json", len(list((root / "output" / "ice_hockey").glob("ih_*.json")))
    else:
        rel = f"data/multisport/{sport}/scoreboard.json"
        boards = len(list((root / "output" / "multisport" / sport).glob("ms_*.json")))
    sb = _read(root / rel)
    elo = sb.get("elo") or {}
    by = sb.get("all_sides_by_market") or {}
    return {"sport": sport, "boards": boards, "scoreboard": rel if sb else None, "picks": sb.get("picks", 0),
            "won": sb.get("won", 0), "pnl": sb.get("pnl", 0), "clv_avg": sb.get("clv_fair_avg"),
            "clv_n": sb.get("picks", 0), "sides": sum(b.get("sides", 0) for b in by.values()) if sb else None,
            "brier": elo.get("walk_forward_brier"), "brier_n": elo.get("scored") or 0}


def _flagged(sport: str, root: Path) -> list[tuple[str, dict]]:
    """Experiment-engine shadows on the sport's slot that passed the promotion test (memory/strategies.json)."""
    reg = _read(root / "memory" / "strategies.json")
    slot = "nba" if sport == "basketball" else sport
    st = reg.get("standings") or {}
    return [(n, st.get(n) or {}) for n in reg.get("flagged") or [] if (st.get(n) or {}).get("slot") == slot]


def _where(sport: str) -> str:
    if sport == "basketball":
        return "`output/picks/nba_*.json`, `output/world_basketball/`"
    if sport == "ice_hockey":
        return "`data/ice_hockey/`, `output/ice_hockey/`"
    return f"`data/multisport/{sport}/`, `output/multisport/{sport}/`"


def sport_question(sport: str, root: Path | None = None) -> dict:
    """'What do I need to do better?' for one sport: the record, the answer, and at most one proposal
    with ONE buildable deliverable (never a proposal that waits on data the framework does not hold)."""
    root = root or ROOT
    r = sport_record(sport, root)
    lab, up = _label(sport), sport.upper()
    rec = (f"{r['picks']} graded picks (won {r['won']}, {r['pnl']:+.2f}u"
           + (f", value vs close {r['clv_avg']:+.1%} over {r['clv_n']}" if r.get("clv_avg") is not None else "")
           + ")" + (f", {r['sides']} graded sides" if r.get("sides") is not None else "")
           + (f", model walk-forward Brier {r['brier']} over {r['brier_n']}" if r.get("brier") is not None else ""))
    data_note = (f" Data: {_where(sport)} (private, laid over the workspace by `python monitor/fdata.py pull`). "
                 "RECORD-ONLY: nothing here changes a pick rule, stake or threshold.")
    prop = None
    flagged = _flagged(sport, root)
    if r["boards"] == 0:
        answer = "no board file yet: PENDING (the board has not run for this sport)"
    elif sport != "basketball" and not r["scoreboard"]:
        answer = f"{r['boards']} board files but no scoreboard: the grading run is not writing it"
        prop = {"title": f"{lab}: the grading run writes no scoreboard - fix it at source", "ev": 6.0, "kind": "fix",
                "body": f"Deliverable: find why the nightly grading (`run_multisport.py --grade` / `run_hockey.py "
                        f"--grade`) leaves no scoreboard for {sport} although {r['boards']} board files exist, fix it, "
                        "and add a test that grading one saved board file writes the scoreboard. Done when the next "
                        "grading run writes it." + data_note}
    elif flagged:
        n, row = flagged[0]
        answer = f"experiment shadow '{n}' passed the promotion test on the {sport} slot"
        prop = {"title": f"{lab}: experiment shadow '{n}' beats the board's own picks - Architect decision",
                "ev": 4.5, "kind": "promote",
                "body": f"engine/experiments.py: {row.get('vs_live')}; counted {(row.get('counted') or {}).get('n')} "
                        "bets. Deliverable: a short report in this issue of what wiring it into the board would "
                        "change (picks kept / dropped over the graded record). Wiring it is the Architect's decision."
                        + data_note}
    elif r["picks"] == 0 and (r.get("sides") or 0) >= MIN_SIDES:
        answer = f"the board made no graded pick from {r['sides']} graded sides: which gate stops every side?"
        prop = {"title": f"{lab}: the board makes no picks - study which gate removes every side (record-only)",
                "ev": 5.0, "kind": "study",
                "body": f"{lab} has {r['sides']} graded sides and {r['picks']} graded picks. Deliverable: "
                        f"`backtest/sport_gate_study.py --sport {sport}` (one script for every sport; create it if "
                        f"missing) writing `backtest/{up}_GATE_STUDY.md`: for every graded side, the first board gate "
                        "that removes it (price band 1.20-2.00, chance 50%+, value bar, exchange quote / liquidity, "
                        "value cap) and how each removed group did at its first price (won rate, return per unit, "
                        "value vs close), plus a test of the gate counter. Done when the report is merged."
                        + data_note}
    elif r["picks"] < MIN_PICKS:
        answer = f"{r['picks']}/{MIN_PICKS} graded picks: PENDING, collecting (no proposal until the record is big enough)"
    elif r.get("clv_avg") is not None and r["clv_avg"] < 0:
        answer = f"picks lose to the close ({r['clv_avg']:+.1%} over {r['clv_n']}): where is the value lost?"
        prop = {"title": f"{lab}: picks lose to the closing price - split value vs close by market and price band",
                "ev": 4.0, "kind": "study",
                "body": f"{lab}: {rec}. Deliverable: `backtest/sport_clv_study.py --sport {sport}` (one script for "
                        f"every sport; create it if missing) writing `backtest/{up}_CLV_STUDY.md`: the graded picks' "
                        "value vs close by market, price band, competition and source (exchange / model), with the "
                        "standard error of each cell, plus a test. Done when the report is merged." + data_note}
    elif ((r.get("brier") or 0) >= COIN_BRIER and r["brier_n"] >= MIN_BRIER_N
          and not (root / "backtest" / f"{up}_K_STUDY.md").exists()):
        answer = f"the model's walk-forward Brier {r['brier']} is no better than a coin over {r['brier_n']} games"
        prop = {"title": f"{lab}: the Elo is no better than a coin walk-forward - tune K and the start rating",
                "ev": 3.0, "kind": "study",
                "body": f"{lab}: {rec}. Deliverable: `backtest/{sport}_k_study.py` writing `backtest/{up}_K_STUDY.md`: "
                        "walk-forward Brier over the learned games for K in 8-48 and start ratings, against the "
                        "exchange's fair price where held, plus a test. Done when the report is merged." + data_note}
    else:
        answer = "on track: picks hold value against the close; keep grading"
    return {"sport": sport, "record": r, "summary": rec, "answer": answer, "proposal": prop}


def audit_sports(root: Path | None = None) -> list[dict]:
    out = []
    for sp in rollout_sports():
        try:
            out.append(sport_question(sp, root))
        except Exception as e:  # noqa: BLE001 - one unreadable sport never hides the others
            out.append({"sport": sp, "record": {}, "summary": "NO DATA - PENDING", "answer": f"unreadable ({e})",
                        "proposal": None})
    return out


def position(loops: list[dict], card: dict | None = None) -> dict:
    """Where am I: the bots' per-rule CLV scorecard (monitor/rule_scorecard.py, written nightly by
    bot_grader) plus the loops with no new evidence. Missing scorecard reads PENDING (HR35)."""
    from monitor import rule_scorecard
    card = rule_scorecard.load() if card is None else card
    stalled = [r["loop"] for r in loops if not r["ok"]]
    if not card:
        return {"status": "PENDING", "why": "data/bots/scorecard.json not written yet (bot grader has not run)",
                "stalled_loops": stalled}
    return {**card.get("position", {}), "stalled_loops": stalled, "proposals": card.get("proposals", []),
            "multiplicity": card.get("multiplicity"), "built_at": card.get("built_at")}


def render_sports(sports: list[dict]) -> list[str]:
    L = ["", "## (e) Every sport: what do I need to do better?", "",
         "| sport | graded record | answer | proposal |", "|---|---|---|---|"]
    for q in sports:
        p = q.get("proposal")
        L.append(f"| {q['sport']} | {q['summary']} | {q['answer']} | {p['title'] if p else '-'} |")
    return L


def render(inputs, loops, props, when, pos: dict | None = None, sports: list[dict] | None = None) -> str:
    L = [f"# SELF-IMPROVEMENT REVIEW — {when}", "",
         "Written weekly by `scripts/self_improve.py` (`self_improve.yml`): what the model uses, which "
         "learning loops produced tested evidence this week, and what to do better, ranked by expected "
         "value. The top open proposal is built record-only / shadow by the workflow's build job.", "",
         "## (a) Inputs strong football models use", "",
         "| input | value | status | where / evidence |", "|---|---|---|---|"]
    for r in inputs:
        L.append(f"| {r['input']} | {r['value']} | {r['status']} | "
                 f"{'; '.join(r['evidence'] or r['where']) or '—'} |")
    L += ["", "## (b) Learning loops this week", "", "| loop | produced tested evidence | evidence |",
          "|---|---|---|"]
    for r in loops:
        L.append(f"| {r['loop']} | {'yes' if r['ok'] else '**NO — stalled**'} | {r['note']} |")
    L += ["", "## (c) What to do better (by expected value)", ""]
    L += [f"{i}. **{p['title']}** (EV {p['ev']}) — {p['body']}" for i, p in enumerate(props, 1)] or ["Nothing open."]
    if pos is not None:
        L += ["", "## (d) Where am I (bot rules scored on CLV)", ""]
        if pos.get("status") == "PENDING":
            L.append(f"PENDING — {pos['why']}")
        else:
            L.append(f"Working (CLV band above 0): {', '.join(pos.get('working') or []) or 'none yet'}")
            L.append(f"Not working (band below 0): {', '.join(pos.get('not_working') or []) or 'none yet'}")
            L.append(f"Rules with no CLV recorded yet: {pos.get('no_clv_yet', 'PENDING')}")
            m = pos.get("multiplicity") or {}
            L.append(f"False-discovery cut (BH, q={m.get('q')}): {len(m.get('pass') or [])} of {m.get('tested')} "
                     "tested ideas survive; the shadow queue is unchanged (record-only).")
            L += [f"- {p['kind']}: {p['line']} (EV {p['ev']})" for p in pos.get("proposals") or []]
        if pos.get("stalled_loops"):
            L.append("Loops with no new evidence: " + ", ".join(pos["stalled_loops"]))
    if sports is not None:
        L += render_sports(sports)
    return "\n".join(L) + "\n"


def _gh(*args: str, inp: str | None = None) -> str:
    r = subprocess.run(["gh", *args], input=inp, capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


def open_issues(props: list[dict], top: int = 5) -> list[str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "Tolar07/framework")
    _gh("label", "create", LABEL, "-R", repo, "--color", "5319e7", "--description",
        "weekly self-improvement proposals", "--force")
    have = {x["title"] for x in json.loads(_gh("issue", "list", "-R", repo, "--state", "open", "--label", LABEL,
                                               "--limit", "100", "--json", "title") or "[]")}
    # a proposal closed as "not planned" (a duplicate of something built) is never opened again
    # (2026-11-05: #310-#312 were re-proposals of inputs already studied)
    have |= {x["title"] for x in json.loads(_gh("issue", "list", "-R", repo, "--state", "closed", "--label", LABEL,
                                                "--limit", "200", "--json", "title,stateReason") or "[]")
             if x.get("stateReason") == "NOT_PLANNED"}
    made = []
    for p in [p for p in props if p["kind"] == "fix" or p["ev"] >= 1.0][:top]:
        if p["title"] in have:
            continue
        body = (f"{p['body']}\n\nExpected value score {p['ev']} (weekly self-improvement review, "
                "backtest/SELF_IMPROVEMENT.md). Build record-only or as a shadow with tests; nothing "
                "changes a pick, stake or threshold without passing the walk-forward / promotion "
                "machinery.\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_")
        url = _gh("issue", "create", "-R", repo, "--title", p["title"], "--label", LABEL, "--body", body)
        if url:
            made.append(url.strip())
    return made


def open_sport_issues(sports: list[dict], when: str) -> list[str]:
    """One issue per sport proposal (framework#356): opened once by title; an open one gets this week's
    numbers as a comment instead of a duplicate; one closed as not planned is never re-opened."""
    repo = os.environ.get("GITHUB_REPOSITORY", "Tolar07/framework")
    props = [q["proposal"] for q in sports if q.get("proposal")]
    if not props:
        return []
    _gh("label", "create", LABEL, "-R", repo, "--color", "5319e7", "--description",
        "weekly self-improvement proposals", "--force")
    open_ = {x["title"]: x["number"] for x in json.loads(_gh("issue", "list", "-R", repo, "--state", "open", "--label",
                                                             LABEL, "--limit", "200", "--json", "title,number") or "[]")}
    dropped = {x["title"] for x in json.loads(_gh("issue", "list", "-R", repo, "--state", "closed", "--label", LABEL,
                                                  "--limit", "300", "--json", "title,stateReason") or "[]")
               if x.get("stateReason") == "NOT_PLANNED"}
    made = []
    for p in props:
        if p["title"] in dropped:
            continue
        if p["title"] in open_:
            _gh("issue", "comment", str(open_[p["title"]]), "-R", repo, "--body",
                f"Weekly self-improvement review {when}: still open. {p['body']}")
            continue
        body = (f"{p['body']}\n\nWeekly self-improvement review, section (e) every sport "
                "(backtest/SELF_IMPROVEMENT.md). One deliverable; build it record-only with a test.\n\n---\n"
                "_Generated by [Claude Code](https://claude.ai/code)_")
        url = _gh("issue", "create", "-R", repo, "--title", p["title"], "--label", LABEL, "--body", body)
        if url:
            made.append(url.strip())
    return made


def architect_note(note_path: Path | None = None, review: dict | None = None) -> str:
    """The weekly message to the Architect: the build step's own summary when it
    wrote one, else the review's question, stalls and top proposals."""
    head = "🧠 WEEKLY SELF-IMPROVEMENT — what do I need to do better?"
    if note_path and note_path.exists() and note_path.read_text(encoding="utf-8").strip():
        return head + "\n\n" + note_path.read_text(encoding="utf-8").strip()[:3500]
    if review is None:
        try:
            review = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return head + "\n\nReview: NO DATA — PENDING (the review job did not write its report)."
    L = [head, ""]
    stalled = [r["loop"] for r in review.get("loops", []) if not r.get("ok")]
    L.append("Learning loops: " + ("all produced tested evidence this week" if not stalled
                                   else "STALLED — " + ", ".join(stalled)))
    lacking = [r["input"] for r in review.get("inputs", []) if r.get("status") in ("MISSING", "CONTEXT")]
    if lacking:
        L.append("Not yet used as a model input: " + ", ".join(lacking))
    work = [f"{q['sport']}: {q['answer']}" for q in review.get("sports", []) if q.get("proposal")]
    if work:
        L.append("Sports with something to do better: " + "; ".join(work))
    L.append("")
    L.append("Proposals (best first):")
    L += [f"{i}. {p['title']}" for i, p in enumerate(review.get("proposals", [])[:5], 1)] or ["none"]
    L.append("")
    L.append("The top safe one is built as record-only / shadow and merged on green; nothing changes "
             "a pick, stake or threshold without your OK.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", action="store_true")
    ap.add_argument("--telegram", metavar="NOTE", help="send the weekly note to the Architect and stop")
    a = ap.parse_args(argv)
    if a.telegram is not None:
        from output import notify
        ok, notes = notify.send_architect(architect_note(Path(a.telegram)))
        print("architect note", "sent" if ok else "NOT sent", *notes)
        return 0
    when = datetime.now(UTC).strftime("%Y-%m-%d")
    inputs, loops = audit_inputs(), audit_loops()
    props = proposals(inputs, loops)
    pos = position(loops)
    sports = audit_sports()
    OUT_MD.write_text(render(inputs, loops, props, when, pos, sports), encoding="utf-8")
    made = open_issues(props) if a.issues else []
    if a.issues:
        made += open_sport_issues(sports, when)
    OUT_JSON.write_text(json.dumps({"reviewed": when, "inputs": inputs, "loops": loops, "proposals": props,
                                    "position": pos, "sports": sports, "issues_opened": made}, indent=1),
                        encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))
    if made:
        print("issues opened:", *made, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
