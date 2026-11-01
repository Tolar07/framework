"""
AI WEEKLY REVIEW — step 6 of the bot-training plan (the Architect, 2026-11-01).

Every Monday the free models (Gemini first, then NVIDIA, then OpenRouter ":free"; the verdict
panel's guards) read the week's graded record and answer one question: "what single change would
have helped most?". The answer must be a DECLARATIVE hypothesis in research/runner.py's test format
(at most MAX_NEW a week). It is appended to memory/hypotheses.jsonl as "proposed" and the runner
tests it walk-forward at once. The models can add ideas, never behaviour: the runner never runs code
from the file, an accepted rule only becomes a SHADOW strategy, and only the experiment engine can
promote a shadow strategy (100+ graded bets beating the live one). No Claude, no paid model.

    python research/ai_review.py            # propose + test
    python research/ai_review.py --dry-run  # show what would be proposed, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import verdict_panel as VP  # noqa: E402
from research import runner  # noqa: E402

LEDGER_DIR = ROOT / "output" / "picks"
FEATURES = ROOT / "backtest" / "FEATURES_STUDY.md"
MAX_NEW = 2
DAYS = 7
BET_RULE_KEYS = {"kind", "market", "sport", "price_min", "price_max", "covered", "country_has", "comp_has",
                 "sharp_ev_min", "drift_max"}

PROMPT = """You are the weekly research analyst of a sports-betting framework. Below: the last {days} days of
graded picks summarised (by market family and price band), the framework's own studies, and every
hypothesis already tested (do NOT repeat one). Answer: what single change would have helped most?
Express each idea as a TESTABLE hypothesis in this exact test format (it is run walk-forward on every
graded game; no code, only these keys):

{spec}

Give at most {n} hypotheses, each different from every existing one. Only use numbers from the data
below; never invent a result. Return JSON only:
{{"hypotheses": [{{"idea": "<one sentence>", "why": "<the evidence below that suggests it>",
                   "test": {{"kind": "bet_rule", "market": "...", ...}}}}]}}

DATA:
"""


def spec_text() -> str:
    doc = runner.__doc__ or ""
    a, b = doc.find("Test kinds"), doc.find("Verdicts")
    return doc[a:b].strip() if a >= 0 and b > a else doc[:2000]


def week_summary(today: date, ledger_dir: Path = LEDGER_DIR, days: int = DAYS) -> dict:
    """{family | band: {n, won, mean_price, return}} over the last `days` graded singles."""
    from engine import experiments
    from engine.reasoning import _family
    cells: dict = {}
    for k in range(1, days + 1):
        f = ledger_dir / f"picks_{(today - timedelta(days=k)).isoformat()}.json"
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in d.get("singles") or []:
            if s.get("result") not in ("won", "lost"):
                continue
            try:
                price = float(s.get("price"))
            except (TypeError, ValueError):
                continue
            key = f"{_family(s.get('market') or '')} | {experiments.band(price)}"
            c = cells.setdefault(key, {"n": 0, "won": 0, "price": 0.0, "ret": 0.0})
            c["n"] += 1
            c["won"] += s["result"] == "won"
            c["price"] += price
            c["ret"] += (price - 1) if s["result"] == "won" else -1
    return {k: {"n": c["n"], "won": c["won"], "mean_price": round(c["price"] / c["n"], 2),
                "return_pct": round(100 * c["ret"] / c["n"], 1)} for k, c in sorted(cells.items())}


def studies() -> dict:
    out: dict = {}
    for name, fn in (("why_record", "engine.why_record"), ("fact_sheet", "engine.fact_sheet"),
                     ("learned_weights", "engine.learned_weights")):
        try:
            mod = __import__(fn, fromlist=["x"])
            if name == "why_record":
                out[name] = mod.summary_lines(max_lines=6)
            elif name == "fact_sheet":
                out[name] = mod.summary_line(json.loads(mod.RECORD.read_text(encoding="utf-8")))
            else:
                out[name] = mod.summary_line(json.loads(mod.RECORD.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001 — a missing study is PENDING, never invented
            out[name] = f"PENDING ({type(e).__name__})"
    return out


def clean_test(t: object) -> Optional[dict]:
    """The test with only the runner's keys, or None when it can't be run."""
    if not isinstance(t, dict):
        return None
    if t.get("kind") == "bet_rule":
        t = {k: v for k, v in t.items() if k in BET_RULE_KEYS}
        return t if t.get("market") else None
    if t.get("kind") == "feature":
        try:
            known = FEATURES.read_text(encoding="utf-8")
        except OSError:
            return None
        t = {k: t.get(k) for k in ("kind", "outcome", "feature")}
        return t if t["outcome"] and t["feature"] and str(t["feature"]) in known else None
    return None


def propose(today: date, hyps: list[dict], post: Callable, get: Callable,
            keys: Optional[dict] = None) -> tuple[list[dict], str]:
    """(new hypothesis lines, which model wrote them). Never raises."""
    keys = keys if keys is not None else {n: VP.member_key(n) for n in VP.MEMBERS}
    existing = [{"id": h.get("id"), "idea": h.get("idea"), "test": h.get("test"), "status": h.get("status"),
                 "verdict": h.get("verdict")} for h in hyps]
    data = {"week": week_summary(today), "studies": studies(), "existing_hypotheses": existing}
    content = PROMPT.format(days=DAYS, spec=spec_text(), n=MAX_NEW) + json.dumps(data, ensure_ascii=False)
    obj, who = None, "none"
    for name in VP.MEMBERS:
        key = keys.get(name) or ""
        model = VP.pick_model(name, get, key) if key else None
        if not model:
            continue
        try:
            obj = VP.chat_json(name, model, key, content, post, timeout=180)
            who = f"{name}:{model}"
            break
        except Exception:  # noqa: BLE001 — next member
            continue
    if not obj:
        return [], who
    seen = [json.dumps(h.get("test"), sort_keys=True) for h in hyps]
    top = max([int(str(h.get("id", "H0"))[1:] or 0) for h in hyps if str(h.get("id", "")).startswith("H")] + [0])
    out = []
    for x in (obj.get("hypotheses") or [])[:MAX_NEW]:
        t = clean_test((x or {}).get("test"))
        if not t or json.dumps(t, sort_keys=True) in seen or not str(x.get("idea") or "").strip():
            continue
        top += 1
        h = {"id": f"H{top:03d}", "added": today.isoformat(), "idea": str(x["idea"])[:300],
             "source": f"ai-review {today.isoformat()} ({who}); why: {str(x.get('why') or '')[:300]}",
             "data_needed": ["data/universe"], "status": "proposed", "test": t}
        if runner.validate(h):
            top -= 1
            continue
        seen.append(json.dumps(t, sort_keys=True))
        out.append(h)
    return out, who


def main(argv: list[str] | None = None, post: Optional[Callable] = None, get: Optional[Callable] = None) -> int:
    ap = argparse.ArgumentParser(description="AI weekly review -> hypotheses")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if get is None or post is None:
        import requests
        get, post = get or requests.get, post or requests.post
    today = datetime.now(UTC).date()
    hyps = runner.load()
    new, who = propose(today, hyps, post, get)
    print(f"ai review ({who}): {len(new)} new hypothesis(es)"
          + "".join(f"\n  {h['id']}: {h['idea']} {json.dumps(h['test'])}" for h in new))
    if a.dry_run or not new:
        return 0
    runner.save(hyps + new)
    for h in new:
        try:
            done = runner.run(only=h["id"])
            r = next(x for x in done if x.get("id") == h["id"])
            print(f"  {h['id']} tested: {r.get('status')} — {r.get('verdict')} · {r.get('result')}")
        except Exception as e:  # noqa: BLE001 — stays "proposed"; the next runner pass tests it
            print(f"  {h['id']} test failed: {type(e).__name__}: {e}")
    runner.RESULTS.write_text(runner.report(runner.load()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
