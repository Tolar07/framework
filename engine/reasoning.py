"""
REASONING — the framework's thinking step (Architect 2026-10-19: "give the entire
framework the thinking superpower", one brain built here and read by the Matchbook agent).

After the board is built, a language model (Gemini, the Architect's Google AI Studio key)
reads each single with its context and judges it:

    verdict     back | lower | veto
    ai_chance   its own probability for the pick
    confidence  0-1, how sure it is of that
    reasons     one or two sentences

Context per pick: the framework's pick, price, chance, tier, certainty and news/lineup notes;
the framework's own graded record for that market family (memory/knowledge.json); and the
Matchbook agent's record for that family (data/matchbook/summary.json).

ADVISORY ONLY until it earns weight. Nothing here changes, drops or stakes a pick. It writes
output/reasoning/reasoning_<date>.json, and record() scores every past verdict against the
graded picks ledger: did the vetoed picks lose more often than the backed ones? The Architect
decides from that record whether the reasoning gets a say.

No key, no network, a refused call or a malformed answer: the pick reads PENDING (HR35),
never a made-up verdict.
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output" / "reasoning"
LEDGER_DIR = ROOT / "output" / "picks"
KNOWLEDGE = ROOT / "memory" / "knowledge.json"
MB_SUMMARY = ROOT / "data" / "matchbook" / "summary.json"
RECORD = ROOT / "memory" / "reasoning_record.json"

BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
BATCH = 15                       # picks per request: few requests on the free tier's daily cap
VERDICTS = ("back", "lower", "veto")
_SKIP_MODELS = ("preview", "exp", "tts", "image", "live", "embedding", "audio", "thinking", "learnlm", "gemma")

PROMPT = """You are the reasoning step of a football betting model. For each pick below, the
model has already calculated a probability. Your job is judgement: weigh what the numbers may
miss (team news and absences in the notes, motivation, the model's own record in that market
family, the exchange record) and say whether the pick should be backed as is, backed with less
confidence ("lower"), or not backed ("veto"). Be calibrated: "back" should be your usual answer
when nothing argues against the pick; use "veto" only with a concrete reason. Do not invent
facts that are not in the context; if you lack information, say so and keep the model's view.

Rules:
- "ai_chance" is YOUR estimate, not a copy. Start from model_chance and move it for each concrete
  reason in the context: a LOSING record in the family (the model has been overconfident there)
  pulls it down by about the gap between "won" and "needs"; key absences for the picked side pull
  it down; nothing in the context = stay within 0.02 of model_chance with confidence <= 0.4.
- "break_even_chance" is 1/price. If your ai_chance is below it, the verdict cannot be "back".
- The records are given as plain sentences that start with WINNING, LOSING or TOO FEW. Quote that
  word in your reasons when you use a record; never call a LOSING record strong or a TOO FEW one
  evidence.
- Each reason names the specific fact it rests on (a number or a news item from the context).

Return JSON only: {"picks": [{"id": <id>, "verdict": "back"|"lower"|"veto",
"ai_chance": <0-1>, "confidence": <0-1>, "reasons": "<one or two sentences>"}]}

PICKS:
"""


# ---------------------------------------------------------------- context
def _family(market: str) -> str:
    from engine.learning import family
    return family(market)


def family_records() -> tuple[dict, dict]:
    """(framework segments by family, Matchbook groups by family) — empty when missing."""
    fw, mb = {}, {}
    try:
        k = json.loads(KNOWLEDGE.read_text(encoding="utf-8"))
        for s in k.get("segments") or []:
            if s.get("league") == "all":
                fw[s.get("segment")] = {"n": s.get("n"), "hit": s.get("hit"), "need": s.get("need"),
                                        "pl": s.get("pl")}
    except (OSError, ValueError):
        pass
    try:
        g = json.loads(MB_SUMMARY.read_text(encoding="utf-8")).get("groups") or {}
        for name, v in g.items():
            if name.startswith("family: "):
                mb[name[8:]] = {"bets": v.get("bets"), "won": v.get("won"),
                                "expected_wins": v.get("expected_wins"), "mean_clv": v.get("mean_clv")}
    except (OSError, ValueError):
        pass
    return fw, mb


def say_framework(r: Optional[dict]) -> str:
    if not r or not r.get("n"):
        return "TOO FEW: no graded framework picks in this family yet"
    n, hit, need, pl = r["n"], r.get("hit") or 0, r.get("need") or 0, r.get("pl") or 0
    word = "TOO FEW" if n < 15 else ("WINNING" if pl > 0 else "LOSING")
    return (f"{word}: framework graded {n} picks in this family, won {hit:.0%}, needs {need:.0%} "
            f"to break even at its prices, profit {pl:+.2f} units")


def say_matchbook(r: Optional[dict]) -> str:
    if not r or not r.get("bets"):
        return "TOO FEW: no Matchbook bets in this family yet"
    n, won, exp = r["bets"], r.get("won") or 0, r.get("expected_wins") or 0
    clv = r.get("mean_clv")
    word = "TOO FEW" if n < 10 else ("WINNING" if won >= exp else "LOSING")
    clv_s = f", mean closing-line value {clv:+.1%}" if clv is not None else ""
    return f"{word}: Matchbook {n} bets, won {won} vs {exp:.1f} expected{clv_s}"


def context(singles: list[dict]) -> list[dict]:
    fw, mb = family_records()
    out = []
    for i, s in enumerate(singles):
        fam = _family(s.get("market") or "")
        out.append({
            "id": i, "fixture": s.get("fixture"), "league": s.get("league"),
            "kickoff_utc": s.get("kickoff_utc"), "pick": s.get("pick") or s.get("market"),
            "price": s.get("price"), "model_chance": s.get("chance"),
            "break_even_chance": round(1 / float(s["price"]), 4) if s.get("price") else None,
            "model_edge_pts": round(100 * (float(s["chance"]) - 1 / float(s["price"])), 1)
            if s.get("price") and s.get("chance") is not None else None,
            "tier": s.get("tier"),
            "certainty": s.get("certainty"), "market_family": fam,
            "news": " · ".join(x for x in (s.get("news_level"), s.get("news_note"),
                                           (s.get("lineup_check") or {}).get("note")) if x),
            "framework_record_in_family": say_framework(fw.get(fam)),
            "matchbook_record_in_family": say_matchbook(mb.get(fam)),
        })
    return out


# ---------------------------------------------------------------- the model
def _version(name: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", name)[:3]) or (0,)


def pick_model(get: Callable, key: str) -> Optional[str]:
    """GEMINI_MODEL if set; else the newest stable Flash-Lite (most free requests a day),
    else the newest stable Flash, from the account's own model list."""
    if os.getenv("GEMINI_MODEL"):
        return os.getenv("GEMINI_MODEL")
    r = get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    names = [m.get("id", "").removeprefix("models/") for m in r.json().get("data") or []]
    names = [n for n in names if n.startswith("gemini") and not any(x in n for x in _SKIP_MODELS)]
    for want in ("flash-lite", "flash"):
        hits = [n for n in names if n.endswith(want) or f"{want}-0" in n or n.endswith(f"{want}-latest")]
        hits = [n for n in hits if want != "flash" or "lite" not in n]
        if hits:
            return max(hits, key=_version)
    return None


def _ask(post: Callable, key: str, model: str, rows: list[dict], sleep: Optional[Callable] = None) -> dict:
    import time
    sleep = sleep or time.sleep
    for attempt in range(3):           # the free tier answers 503/429 when busy: wait and retry
        r = post(f"{BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=120,
                 json={"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                       "messages": [{"role": "user", "content": PROMPT + json.dumps(rows, ensure_ascii=False)}]})
        if getattr(r, "status_code", 200) not in (429, 500, 502, 503, 504) or attempt == 2:
            break
        sleep(20 * (attempt + 1))
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    return {p.get("id"): p for p in json.loads(text).get("picks") or []}


def _clean(p: Optional[dict]) -> dict:
    if not p:
        return {"verdict": "PENDING", "reasons": "no answer for this pick"}
    v = str(p.get("verdict") or "").lower()
    try:
        ch, cf = float(p.get("ai_chance")), float(p.get("confidence"))
    except (TypeError, ValueError):
        return {"verdict": "PENDING", "reasons": "malformed answer"}
    if v not in VERDICTS or not (0 <= ch <= 1 and 0 <= cf <= 1):
        return {"verdict": "PENDING", "reasons": "malformed answer"}
    return {"verdict": v, "ai_chance": round(ch, 4), "confidence": round(cf, 3),
            "reasons": str(p.get("reasons") or "")[:400]}


def reason(picks_doc: dict, key: Optional[str] = None, get: Optional[Callable] = None,
           post: Optional[Callable] = None, now: Optional[datetime] = None) -> dict:
    """The reasoning document for one picks file. Never raises on a model failure."""
    import requests
    key = key if key is not None else os.getenv("GEMINI_API_KEY", "").strip()
    get, post = get or requests.get, post or requests.post
    now = now or datetime.now(UTC)
    singles = picks_doc.get("singles") or []
    rows = context(singles)
    doc = {"date": picks_doc.get("date"), "picks_generated_at": picks_doc.get("generated_at"),
           "run_at": now.isoformat(timespec="seconds"), "model": None, "advisory": True,
           "note": None, "picks": []}
    answers: dict = {}
    if not key:
        doc["note"] = "NO DATA — PENDING: GEMINI_API_KEY not set"
    else:
        try:
            doc["model"] = pick_model(get, key)
            if not doc["model"]:
                doc["note"] = "NO DATA — PENDING: no Gemini Flash model on this key"
        except Exception as e:  # noqa: BLE001 — a failed call reads PENDING, never stops anything
            doc["note"] = f"NO DATA — PENDING: {type(e).__name__}: {str(e)[:160]}"
        for i in range(0, len(rows), BATCH) if doc["model"] else ():
            try:                     # one failed batch leaves only its own picks PENDING
                answers.update(_ask(post, key, doc["model"], rows[i:i + BATCH]))
            except Exception as e:  # noqa: BLE001
                doc["note"] = f"PARTLY PENDING: {type(e).__name__}: {str(e)[:160]}"
    for row, s in zip(rows, singles):
        doc["picks"].append({"fixture": s.get("fixture"), "market": s.get("market"),
                             "pick": row["pick"], "price": s.get("price"),
                             "model_chance": s.get("chance"), "code": s.get("code"),
                             **_clean(answers.get(row["id"]))})
    return doc


# ---------------------------------------------------------------- the record
def record(out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    """Every past verdict against the graded result: hit rate and flat-stake return by
    verdict. Thinking earns weight only if 'veto' loses more and 'back' wins more."""
    rows = []
    for f in sorted(out_dir.glob("reasoning_*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            p = json.loads((ledger_dir / f"picks_{r['date']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        res = {(s.get("fixture"), s.get("market")): s.get("result") for s in p.get("singles") or []}
        for x in r.get("picks") or []:
            got = res.get((x.get("fixture"), x.get("market")))
            if x.get("verdict") in VERDICTS and got in ("won", "lost"):
                rows.append((x["verdict"], got == "won", float(x.get("price") or 0),
                             x.get("model_chance"), x.get("ai_chance")))
    by: dict = {}
    for v in VERDICTS:
        g = [r for r in rows if r[0] == v]
        if not g:
            by[v] = {"n": 0}
            continue
        won = sum(1 for r in g if r[1])
        by[v] = {"n": len(g), "won": won, "hit": round(won / len(g), 3),
                 "flat_return": round(sum((r[2] - 1) if r[1] else -1 for r in g) / len(g), 4),
                 "model_said": round(sum(r[3] or 0 for r in g) / len(g), 3),
                 "ai_said": round(sum(r[4] or 0 for r in g) / len(g), 3)}
    # who was closer: the model's chance or the reasoning's own (Brier score, lower is better)
    sc = [r for r in rows if r[3] is not None and r[4] is not None]
    brier = {"n": len(sc)}
    if sc:
        brier["model"] = round(sum((float(r[3]) - r[1]) ** 2 for r in sc) / len(sc), 4)
        brier["ai"] = round(sum((float(r[4]) - r[1]) ** 2 for r in sc) / len(sc), 4)
    return {"updated": datetime.now(UTC).date().isoformat(), "graded": len(rows), "by_verdict": by,
            "brier": brier}


def summary_line(rec: dict) -> str:
    b = rec.get("by_verdict") or {}
    parts = [f"{v} {b[v]['won']}/{b[v]['n']} ({b[v]['flat_return']:+.1%})" for v in VERDICTS if b.get(v, {}).get("n")]
    br = rec.get("brier") or {}
    if br.get("n"):
        better = ("level" if br["ai"] == br["model"] else
                  "the reasoning is closer" if br["ai"] < br["model"] else "the plain model is closer")
        parts.append(f"Brier model {br['model']:.3f} vs AI {br['ai']:.3f}: {better}")
    return f"Reasoning record ({rec.get('graded', 0)} graded): " + (" · ".join(parts) or "nothing graded yet")
