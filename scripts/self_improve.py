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

 (d) BUILD — the workflow's second job hands the top open proposal to a
     fresh Claude Code run (Sonnet, GitHub Actions) that builds it RECORD-ONLY
     or as a SHADOW with tests, as a PR. Nothing it builds changes a pick,
     stake or threshold: promotion stays with the walk-forward machinery.

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
    ("lineups / injuries", "expected XI strength v full strength", 5, r"lineup|injur", None,
     "backtest/LINEUP_STUDY.md"),
    ("motivation / table", "title, Europe, relegation stakes late in season", 2, r"motivation|standings",
     None, None),
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
            for part in ("part_a", "part_b"):
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


def proposals(inputs: list[dict], loops: list[dict]) -> list[dict]:
    out = []
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


def render(inputs, loops, props, when) -> str:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", action="store_true")
    a = ap.parse_args(argv)
    when = datetime.now(UTC).strftime("%Y-%m-%d")
    inputs, loops = audit_inputs(), audit_loops()
    props = proposals(inputs, loops)
    OUT_MD.write_text(render(inputs, loops, props, when), encoding="utf-8")
    made = open_issues(props) if a.issues else []
    OUT_JSON.write_text(json.dumps({"reviewed": when, "inputs": inputs, "loops": loops,
                                    "proposals": props, "issues_opened": made}, indent=1), encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))
    if made:
        print("issues opened:", *made, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
