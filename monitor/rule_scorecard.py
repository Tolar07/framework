"""
RULE SCORECARD — "where am I?" (Architect 2026-10-28 / 2026-11-02, framework #258).

Reads the graded bets of all bots (monitor/bot_grader.py, called from its run()) and writes
data/bots/scorecard.json: per bot x rule x market family the bets count, mean CLV with a 90% band
and the flat (level-stake) return, plus a `position` block (7 / 30 days: what is working, what is
not, which loops have no new evidence), proposals of kind grow / shrink / stop / test-market /
timing, and a Benjamini-Hochberg cut over the research and tactics hypotheses.

RECORD-ONLY. Nothing here changes a pick, stake, threshold, rule or bot: the proposals go to
scripts/self_improve.py and to one line in the Architect's 23:00 report. Ratios only: this repo is
public, so no stake, money figure, code or bet id is written. CLV the bot did not record reads
PENDING (HR35), never zero.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bots" / "scorecard.json"
Z90 = 1.645
MIN_BAND = 5          # fewer CLV readings than this: no band (PENDING)
MIN_ACT = 30          # bets before a stop / grow is proposed; fewer only earns a shrink
MIN_FAMILY = 10


def family(bet: dict) -> str:
    """Market family of a bet: the market of a single, 'acca' for a multi-leg slip."""
    legs = bet.get("legs") or []
    if len(legs) != 1:
        return "acca" if legs else "PENDING"
    from monitor import bot_grader as bg
    market, _ = bg._label(legs[0].get("key"))
    return market


def rule_of(bet: dict) -> str:
    return str(bet.get("kind") or "unlabelled")


def flat_return(bet: dict) -> float | None:
    """One unit on the bet: odds-1 if won, -1 if lost; void / open bets do not count."""
    if bet.get("result") == "won":
        return float(bet.get("odds") or 0) - 1.0
    if bet.get("result") == "lost":
        return -1.0
    return None


def mean_band(xs: list[float]) -> dict:
    """Mean with a 90% band (normal approximation); no band below MIN_BAND readings."""
    n = len(xs)
    if n < MIN_BAND:
        return {"n": n, "mean": round(sum(xs) / n, 4) if n else None, "lo": None, "hi": None}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = Z90 * sd / math.sqrt(n)
    return {"n": n, "mean": round(m, 4), "lo": round(m - h, 4), "hi": round(m + h, 4)}


def verdict(clv: dict) -> str:
    if clv["lo"] is None:
        return "PENDING"
    if clv["lo"] > 0:
        return "working"
    if clv["hi"] < 0:
        return "not working"
    return "undecided"


def _cell(bets: list[dict]) -> dict:
    flat = [r for r in map(flat_return, bets) if r is not None]
    clv = mean_band([float(b["clv"]) for b in bets if b.get("clv") is not None])
    return {"bets": len(bets), "graded": len(flat),
            "flat_return": round(sum(flat) / len(flat), 4) if flat else None,
            "clv": clv, "verdict": verdict(clv)}


def _real(b: dict, since: str, today: str) -> bool:
    return not b.get("paper") and b.get("bot") != "board" and since <= b.get("date", "") <= today


def scorecard(bets: list[dict], today: str, days: int = 30) -> list[dict]:
    since = (date.fromisoformat(today) - timedelta(days=days - 1)).isoformat()
    g: dict[tuple, list[dict]] = defaultdict(list)
    for b in bets:
        if _real(b, since, today):
            g[(b["bot"], rule_of(b), family(b))].append(b)
    return [{"bot": k[0], "rule": k[1], "family": k[2], **_cell(v)} for k, v in sorted(g.items())]


def position(bets: list[dict], today: str, loops: list[dict] | None = None) -> dict:
    """Where am I: per bot over 7 and 30 days, what works, what does not, loops with no evidence."""
    out: dict = {"as_of": today, "bots": {}}
    for days in (7, 30):
        since = (date.fromisoformat(today) - timedelta(days=days - 1)).isoformat()
        by: dict[str, list[dict]] = defaultdict(list)
        for b in bets:
            if _real(b, since, today):
                by[b["bot"]].append(b)
        for bot, bs in by.items():
            out["bots"].setdefault(bot, {})[f"{days}d"] = _cell(bs)
    rows = scorecard(bets, today)
    out["working"] = [f"{r['bot']} | {r['rule']} | {r['family']}" for r in rows if r["verdict"] == "working"]
    out["not_working"] = [f"{r['bot']} | {r['rule']} | {r['family']}" for r in rows
                          if r["verdict"] == "not working"]
    out["no_clv_yet"] = sum(1 for r in rows if r["verdict"] == "PENDING")
    out["stalled_loops"] = [r["loop"] for r in loops or [] if not r.get("ok")]
    return out


def _score(mean: float, n: int) -> float:
    return round(min(5.0, abs(mean) * 100 * math.sqrt(max(n, 1)) / 10), 2)


def proposals(rows: list[dict]) -> list[dict]:
    """grow / shrink / stop / test-market / timing, each with an EV score and the evidence needed.
    Never applied: a stake, threshold or rule change is the Architect's decision."""
    out = []
    rules: dict[tuple, list[dict]] = defaultdict(list)
    bots_by_family: dict[str, set] = defaultdict(set)
    for r in rows:
        rules[(r["bot"], r["rule"])].append(r)
        bots_by_family[r["family"]].add(r["bot"])
    for (bot, rule), rs in rules.items():
        n = sum(r["bets"] for r in rs)
        clv_n = sum(r["clv"]["n"] for r in rs)
        if not clv_n:
            continue                                    # no CLV recorded: PENDING, nothing to propose
        clv_m = sum((r["clv"]["mean"] or 0) * r["clv"]["n"] for r in rs) / clv_n
        g = sum(r["graded"] for r in rs)
        flat_ret = sum((r["flat_return"] or 0) * r["graded"] for r in rs) / g if g else None
        bands = [r["clv"] for r in rs if r["clv"]["lo"] is not None]
        who = f"{bot} / {rule}"
        bad = bool(bands) and all(c["hi"] < 0 for c in bands)
        good = bool(bands) and all(c["lo"] > 0 for c in bands)
        if bad and n >= MIN_ACT:
            out.append({"kind": "stop", "who": who, "ev": _score(clv_m, n),
                        "line": f"STOP {who}: {n} bets, CLV {clv_m:+.1%}, whole band below 0. Needs: your OK to switch it off.",
                        "needs": "Architect sign-off to switch the rule off"})
        elif bad:
            out.append({"kind": "shrink", "who": who, "ev": _score(clv_m, n),
                        "line": f"SHRINK {who}: CLV {clv_m:+.1%} over {n} bets, band below 0. Needs: {MIN_ACT - n} more "
                                "graded bets to confirm, then a smaller share.",
                        "needs": f"{MIN_ACT - n} more graded bets"})
        elif good and n >= MIN_ACT:
            out.append({"kind": "grow", "who": who, "ev": _score(clv_m, n),
                        "line": f"GROW {who}: {n} bets, CLV {clv_m:+.1%}, band above 0. Needs: your OK to raise its share.",
                        "needs": "Architect sign-off to raise its share"})
        if clv_m > 0 and flat_ret is not None and flat_ret < 0 and n >= MIN_ACT:
            out.append({"kind": "timing", "who": who, "ev": _score(clv_m, n),
                        "line": f"TIMING {who}: CLV {clv_m:+.1%} but flat return {flat_ret:+.1%} over {n} bets: the edge "
                                "is there at the close and lost at the price taken. Needs: first-look vs take-time prices.",
                        "needs": "price at pick time vs price taken"})
    for r in rows:
        if (r["verdict"] == "working" and r["graded"] >= MIN_FAMILY and r["family"] not in ("acca", "PENDING")
                and len(bots_by_family[r["family"]]) == 1):
            m = r["clv"]["mean"]
            out.append({"kind": "test-market", "who": f"{r['bot']} / {r['family']}",
                        "ev": round(min(5.0, abs(m) * 50), 2),
                        "line": f"TEST-MARKET {r['family']}: only {r['bot']} bets it, CLV {m:+.1%} (band above 0, "
                                f"{r['clv']['n']} bets). Needs: a paper run on the other bots.",
                        "needs": "paper run on the other bots"})
    return sorted(out, key=lambda p: -p["ev"])


# ── Benjamini-Hochberg over hypotheses (research runner, tactics lessons) ──────────────
def p_from_z(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


def bh_cut(pvals: dict[str, float], q: float = 0.10) -> set[str]:
    """Names that survive the Benjamini-Hochberg false-discovery cut at level q."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, k = len(items), 0
    for i, (_, p) in enumerate(items, 1):
        if p <= q * i / m:
            k = i
    return {name for name, _ in items[:k]}


_EFFECT = re.compile(r"([+-]\d+(?:\.\d+)?)%?\s*\D{1,3}?\s*(\d+(?:\.\d+)?)")


def hypothesis_z(h: dict) -> float | None:
    """z of a research hypothesis from its stored result ('return +19.4% ± 14.1%', 'gain +0.0038 ± 0.00165')."""
    m = _EFFECT.search(str(h.get("result") or ""))
    if not m or float(m.group(2)) == 0:
        return None
    return float(m.group(1)) / float(m.group(2))


def multiplicity(hypotheses: list[dict], lessons: dict, q: float = 0.10) -> dict:
    """How many tested ideas survive a false-discovery cut. Record-only: the shadow queue is unchanged."""
    p: dict[str, float] = {}
    for h in hypotheses:
        z = hypothesis_z(h)
        if z is not None:
            p[f"research {h.get('id')}"] = p_from_z(z)
    for name, les in (lessons or {}).items():
        if isinstance(les, dict) and les.get("train_z") is not None:
            p[f"tactics {name}"] = p_from_z(float(les["train_z"]))
    keep = bh_cut(p, q)
    return {"q": q, "tested": len(p), "pass": sorted(keep), "fail": sorted(set(p) - keep)}


def report_line(props: list[dict]) -> str:
    if not props:
        return "Rule scorecard: no rule has enough CLV evidence to grow, shrink or stop yet (PENDING)."
    more = f" (+{len(props) - 1} more in the weekly review)" if len(props) > 1 else ""
    return "Rule scorecard: " + props[0]["line"] + more


def build(bets: list[dict], today: str, loops: list[dict] | None = None,
          hypotheses: list[dict] | None = None, lessons: dict | None = None) -> dict:
    rows = scorecard(bets, today)
    props = proposals(rows)
    return {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "rows": rows,
            "position": position(bets, today, loops), "proposals": props,
            "multiplicity": multiplicity(hypotheses or [], lessons or {}), "report_line": report_line(props)}


def save(card: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=1), encoding="utf-8")


def load(path: Path = OUT) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
