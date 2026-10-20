"""
RESEARCH RUNNER (autonomy plan item 4, 2026-10-20) — every hypothesis in
memory/hypotheses.jsonl gets a walk-forward test on the saved history and a
written verdict. Hypotheses are DECLARATIVE (a JSON test spec, below): the
runner never executes code from the file, so a research session can add ideas
but cannot add behaviour.

One JSON object per line:
  {"id": "H001", "added": "YYYY-MM-DD", "idea": "...", "source": "where it came from",
   "data_needed": ["data/universe", ...], "status": "proposed",
   "test": {...}}

Test kinds
  bet_rule  — a paper betting rule on every graded universe game
              (data/universe/, both sports, covered or not), entry at the
              first price the sweep saw, settled from the real result:
                market        outcome key (or a list of them) as engine.universe.outcomes names it
                              ("1x2:home", "o/u2.5:over", "btts:no", "dc:1x",
                              "win:home", "total:under" ...)
                sport         "football" (default) | "basketball"
                price_min / price_max   band on the price taken
                covered       true / false — only covered / uncovered leagues
                country_has / comp_has  case-insensitive substring filters
                sharp_ev_min  SportyBet's price over Matchbook's fair price - 1
                              (Matchbook's first look, margin removed) at least this
                drift_max     first / last price - 1 at most this (a steam filter)
              engine/walkforward.bet_test: return ± se, CLV vs the last price,
              earlier half vs later half.
  feature   — does a feature add information beyond the model?
                outcome  "home win" | "over 2.5" | "BTTS yes"
                feature  a row name of backtest/FEATURES_STUDY.md
              engine/walkforward.feature_test on the graded rated fixtures.

Verdicts (status after a run)
  accepted      bet_rule ACCEPT AS SHADOW: 60+ bets, both halves in profit and the
                later half beat the close — queued as a SHADOW strategy
                (memory/strategy_queue.jsonl) for the experiment engine, which
                paper-trades it and alone may promote it (100+ graded bets beating
                the live strategy on CLV and return). Never straight to money.
                feature ADDS INFORMATION: queued as a candidate model feature.
  rejected      the later half lost (or lost against the close)
  inconclusive  / pending-data — retested on every run as data grows
A hypothesis keeps its id forever; a verdict is rewritten each run with the
date, so the record shows when an idea turned.

    python research/runner.py            # test all, write research/RESULTS.md
    python research/runner.py --id H002  # one hypothesis
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import features as F  # noqa: E402
from engine import walkforward as wf  # noqa: E402

HYPOTHESES = ROOT / "memory" / "hypotheses.jsonl"
QUEUE = ROOT / "memory" / "strategy_queue.jsonl"
RESULTS = ROOT / "research" / "RESULTS.md"
KINDS = ("bet_rule", "feature")
FINAL = ("accepted", "rejected", "retired")      # retired: withdrawn by the Architect / a session


def load(path: Path = HYPOTHESES) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def save(hyps: list[dict], path: Path = HYPOTHESES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(h, sort_keys=True) + "\n" for h in hyps), encoding="utf-8")


def validate(h: dict) -> list[str]:
    """Problems with a hypothesis line; [] when it can be tested."""
    errs = [f"missing {k}" for k in ("id", "idea", "source", "test") if not h.get(k)]
    t = h.get("test") or {}
    if t.get("kind") not in KINDS:
        errs.append(f"test.kind must be one of {KINDS}")
    elif t["kind"] == "bet_rule" and not t.get("market"):
        errs.append("bet_rule needs test.market")
    elif t["kind"] == "feature" and not (t.get("outcome") and t.get("feature")):
        errs.append("feature test needs test.outcome and test.feature")
    return errs


# ── bet rules on the universe ────────────────────────────────────────────────
def _price_key(market: str) -> tuple[str, int] | None:
    """Outcome key -> (prices key, side index) of the universe's price dict."""
    fam, _, side = market.partition(":")
    if fam == "1x2":
        return "1x2", ("home", "draw", "away").index(side)
    if fam.startswith("o/u"):
        return "ou" + fam[3:], 0 if side == "over" else 1
    if fam == "btts":
        return "btts", 0 if side == "yes" else 1
    if fam == "dc":
        return "dc", ("1x", "12", "x2").index(side)
    return None


def _sharp_ev(row: dict, market: str, price: float) -> float | None:
    pk = _price_key(market)
    mb = ((row.get("mb_first") or {}).get("p") or {}).get(pk[0]) if pk else None
    fair = F.fair(mb)
    if not fair or pk is None or pk[1] >= len(fair):
        return None
    return price * fair[pk[1]] - 1


def rule_bets(test: dict, rows: list[dict]) -> list[tuple[str, int, float, float | None]]:
    from engine import universe as uv
    sport = test.get("sport", "football")
    markets = [test["market"]] if isinstance(test["market"], str) else list(test["market"])
    lo, hi = test.get("price_min", 1.01), test.get("price_max", 1000.0)
    out = []
    for r in rows:
        if r.get("sport") != sport or not r.get("result") or not r.get("ko"):
            continue
        if "covered" in test and bool(r.get("covered")) != bool(test["covered"]):
            continue
        if test.get("country_has") and test["country_has"].lower() not in (r.get("country") or "").lower():
            continue
        if test.get("comp_has") and test["comp_has"].lower() not in (r.get("comp") or "").lower():
            continue
        first = {k: (w, x) for k, w, x, _ in uv.outcomes(sport, (r.get("first") or {}).get("p") or {}, r["result"])}
        last = {k: x for k, _, x, _ in uv.outcomes(sport, (r.get("last") or {}).get("p") or {}, r["result"])}
        for mk in markets:
            if mk not in first:
                continue
            won, px = first[mk]
            if not (lo <= px < hi):
                continue
            lp = last.get(mk)
            if "sharp_ev_min" in test:
                ev = _sharp_ev(r, mk, px)
                if ev is None or ev < test["sharp_ev_min"]:
                    continue
            if "drift_max" in test and lp and px / lp - 1 > test["drift_max"]:
                continue
            out.append((r["ko"][:10], int(won), float(px), lp))
    return out


def run_bet_rule(test: dict, rows: list[dict]) -> tuple[str, dict]:
    res = wf.bet_test(rule_bets(test, rows))
    v = res["verdict"]
    status = {"ACCEPT AS SHADOW": "accepted", "REJECT": "rejected",
              "NOT ENOUGH DATA": "pending-data"}.get(v, "inconclusive")
    return status, res


def run_feature(test: dict, feature_rows: dict) -> tuple[str, dict]:
    rows = (feature_rows.get(test["outcome"]) or {}).get(test["feature"])
    if rows is None:
        return "inconclusive", {"verdict": "UNKNOWN FEATURE", "known": sorted(
            f"{o} / {k}" for o, fs in feature_rows.items() for k in fs)}
    res = wf.feature_test(rows)
    status = {"ADDS INFORMATION": "accepted", "HURTS": "rejected",
              "NOT ENOUGH DATA": "pending-data"}.get(res["verdict"], "inconclusive")
    return status, res


def queue(h: dict, res: dict, now: datetime, path: Path = QUEUE) -> bool:
    """Append an accepted hypothesis to the experiment engine's intake queue
    (once per hypothesis id). The engine turns it into a SHADOW strategy."""
    have = {json.loads(x).get("hypothesis") for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()} if path.exists() else set()
    if h["id"] in have:
        return False
    entry = {"hypothesis": h["id"], "strategy_id": f"research:{h['id']}",
             "kind": "shadow_strategy" if h["test"]["kind"] == "bet_rule" else "candidate_feature",
             "mode": "shadow", "rule": h["test"], "idea": h["idea"], "source": h["source"],
             "evidence": res, "queued_at": now.strftime("%Y-%m-%dT%H:%MZ")}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return True


def _summary(res: dict) -> str:
    if "all" in res:
        a, late = res["all"], res["late"]
        clv = "PENDING" if late["clv"] is None else f"{late['clv']:+.1%}"
        return (f"{a['n']} bets, hit {a['hit'] if a['hit'] is not None else 'PENDING'}, return "
                f"{a['roi']:+.1%} ± {a['roi_se']:.1%}; later half {late['roi']:+.1%}, CLV {clv}")
    if "scored" in res:
        return f"{res['scored']} scored, gain {res['gain']:+.5f} ± {res['se']:.5f}"
    return res.get("verdict", "")


def run(only: str | None = None, now: datetime | None = None, hyp_path: Path = HYPOTHESES,
        queue_path: Path = QUEUE, urows: list[dict] | None = None,
        feature_rows: dict | None = None) -> list[dict]:
    now = now or datetime.now(UTC)
    hyps = load(hyp_path)
    if urows is None:
        from engine import universe as uv
        urows = uv.load_graded()
    for h in hyps:
        if only and h.get("id") != only:
            continue
        if h.get("status") in FINAL and not only:
            continue
        errs = validate(h)
        if errs:
            h.update(status="invalid", verdict="; ".join(errs), tested_at=now.strftime("%Y-%m-%d"))
            continue
        if h["test"]["kind"] == "bet_rule":
            status, res = run_bet_rule(h["test"], urows)
        else:
            if feature_rows is None:
                sys.path.insert(0, str(ROOT / "backtest"))
                import features_study  # type: ignore[import-not-found]
                feature_rows = features_study.feature_rows(features_study.collect())
            status, res = run_feature(h["test"], feature_rows)
        h.update(status=status, verdict=res.get("verdict"), result=_summary(res),
                 tested_at=now.strftime("%Y-%m-%d"))
        if status == "accepted":
            h["queued"] = queue(h, res, now, queue_path) or h.get("queued", True)
    save(hyps, hyp_path)
    return hyps


def report(hyps: list[dict]) -> str:
    L = ["# RESEARCH RESULTS — every hypothesis and its walk-forward verdict", "",
         "Written by `research/runner.py` from `memory/hypotheses.jsonl`. Bet rules: £1 paper bets on every "
         "graded universe game at the first price, earlier half vs later half, closing-line value against the "
         "last price. Features: walk-forward against the model (`backtest/FEATURES_STUDY.md`). **accepted** "
         "means queued as a SHADOW strategy for the experiment engine (`memory/strategy_queue.jsonl`) — paper "
         "only until the engine promotes it on 100+ graded bets. Nothing here stakes money.", ""]
    if not hyps:
        return "\n".join(L + ["No hypothesis yet — NO DATA — PENDING."]) + "\n"
    L += ["| id | idea | test | status | result | tested |", "|---|---|---|---|---|---|"]
    for h in hyps:
        t = h.get("test") or {}
        mk = t.get("market")
        spec = (", ".join(mk) if isinstance(mk, list) else mk) or f"{t.get('outcome')} / {t.get('feature')}"
        L.append(f"| {h.get('id')} | {h.get('idea', '')} | {t.get('kind')}: {spec} | {h.get('status')} | "
                 f"{h.get('result') or h.get('verdict') or 'PENDING'} | {h.get('tested_at') or 'PENDING'} |")
    return "\n".join(L) + "\n"


def summary_line(hyps: list[dict], pr: str = "") -> str:
    """The one Telegram line of a research week (the Architect only)."""
    if not hyps:
        return "Research: no hypothesis on file — NO DATA — PENDING"
    by: dict[str, list[str]] = {}
    for h in hyps:
        by.setdefault(str(h.get("status")), []).append(str(h.get("id")))
    parts = [f"{k} {len(v)} ({', '.join(v[-3:])})" for k, v in sorted(by.items())]
    return (f"Research {max((h.get('tested_at') or '') for h in hyps) or 'PENDING'}: {len(hyps)} hypotheses — "
            + "; ".join(parts) + " · accepted = shadow paper strategy only" + (f" · {pr}" if pr else ""))


def notify(pr: str = "") -> str:
    """Send summary_line to the Architect's own chat (research_note.yml)."""
    import os

    from output import notify as tg
    owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
             or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    if not owner or not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return "research note not sent (no Telegram settings here)"
    ok, notes = tg.send_telegram(summary_line(load(), pr), chat_id=owner)
    return f"research note {'sent' if ok else 'NOT sent'} {notes}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV research runner")
    ap.add_argument("--id", help="test one hypothesis (even a final one)")
    ap.add_argument("--notify", metavar="PR", nargs="?", const="",
                    help="only send the one-line summary to the Architect (no test run)")
    a = ap.parse_args(argv)
    if a.notify is not None:
        print(notify(a.notify))
        return 0
    hyps = run(only=a.id)
    RESULTS.write_text(report(hyps), encoding="utf-8")
    counts: dict[str, Any] = {}
    for h in hyps:
        st = str(h.get("status"))
        counts[st] = counts.get(st, 0) + 1
    print("research: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda x: str(x[0]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
