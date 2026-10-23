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
the framework's own graded record for that market family (memory/knowledge.json); the
Matchbook agent's record for that family and its paper study of every framework pick at
Matchbook prices (both in data/matchbook/summary.json). Since 2026-10-23 also Google Search
(today's line-ups, injuries, rotation, motivation) and the strongest Gemini model the key has.

IT ACTS AND LEARNS (the Architect, 2026-10-23: "let it keep acting until it gets itself right ...
recursive self-improvement"). Each verdict carries a stake_factor (back 1, lower 0.75, veto 0.5)
that the SportyBet placer and the Matchbook agent apply to that single; nothing here drops a pick
or raises a stake. Every run is shown its own scorecard, its recent mistakes with the reasons it
gave, and the lessons it wrote for itself (memory/reasoning_lessons.json, rewritten once a day by
reflect()). It writes output/reasoning/reasoning_<date>.json, and record() scores every past
verdict against the graded picks ledger: did the vetoed picks lose more often than the backed ones?

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
POOL_MIN_CHANCE = 0.80           # the Matchbook agent trades pool legs only from 80% (survivor rule, 2026-10-15)

BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
BATCH = 15                       # picks per request: few requests on the free tier's daily cap
VERDICTS = ("back", "lower", "veto")
# THE VERDICT ACTS (the Architect, 2026-10-23: "let it keep acting until it gets itself right ...
# recursive self-improvement"): the bots scale a single's stake by its verdict. A pick is never
# dropped and never staked above the rule's amount; PENDING (no answer) keeps the full stake.
STAKE_FACTOR = {"back": 1.0, "lower": 0.75, "veto": 0.5, "PENDING": 1.0}
NATIVE_URL = os.getenv("GEMINI_NATIVE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
LESSONS = ROOT / "memory" / "reasoning_lessons.json"
MAX_LESSONS = 12
MISTAKES_SHOWN = 10
_SKIP_MODELS = ("preview", "exp", "tts", "image", "live", "embedding", "audio", "thinking", "learnlm", "gemma")

PROMPT = """You are the reasoning step of a football betting model. For each pick below, the
model has already calculated a probability. Your job is judgement: weigh what the numbers may
miss (team news and absences in the notes, motivation, the model's own record in that market
family, the exchange record) and say whether the pick should be backed as is, backed with less
confidence ("lower"), or not backed ("veto"). Be calibrated: "back" should be your usual answer
when nothing argues against the pick; use "veto" only with a concrete reason. Do not invent
facts that are not in the context; if you lack information, say so and keep the model's view.

SEARCH FIRST (2026-10-23): use Google Search for each fixture before judging it: confirmed or
expected line-ups, injuries and suspensions, rotation (cup ties, European nights), rest days and
travel, motivation (title race, relegation, dead rubber), weather for totals. This is what the
model cannot see, and it is why you are here. Name what you found and where in the reasons.

LEARN FROM YOUR RECORD: your own scorecard, your recent mistakes and the lessons you wrote for
yourself come before the picks. Apply the lessons; do not repeat a mistake listed there.

Rules:
- "ai_chance" is YOUR estimate, not a copy. Start from model_chance and move it for each concrete
  reason in the context: a LOSING record in the family (the model has been overconfident there)
  pulls it down by about the gap between "won" and "needs"; key absences for the picked side pull
  it down; nothing in the context or the search = stay within 0.02 of model_chance with confidence <= 0.4.
- Your verdict now sets the stake: back = full, lower = 3/4, veto = 1/2. Be honest, not timid:
  a "veto" that keeps winning costs money just as a "back" that keeps losing does.
- "break_even_chance" is 1/price. If your ai_chance is below it, the verdict cannot be "back".
  Picks with "pool": true have no bookmaker price (the exchange agent prices them itself): judge
  the chance only.
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


def paper_records() -> dict:
    """The agent's paper study of ALL framework picks at Matchbook prices (rule FW-ALL), by family."""
    try:
        p = json.loads(MB_SUMMARY.read_text(encoding="utf-8")).get("paper") or {}
    except (OSError, ValueError):
        return {}
    return {k.split(" | ", 1)[1]: v for k, v in p.items() if k.startswith("FW-ALL | ")}


def say_paper(r: Optional[dict]) -> str:
    if not r or not r.get("graded"):
        return "TOO FEW: no paper-study picks in this family yet"
    n, won, exp, ret = r["graded"], r["won"], r.get("expected_wins") or 0, r.get("flat_return") or 0
    word = "TOO FEW" if n < 20 else ("WINNING" if ret > 0 else "LOSING")
    return f"{word}: paper study at Matchbook prices, {won}/{n} won vs {exp:.1f} expected, flat return {ret:+.1%}"


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
    paper = paper_records()
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
            "tier": s.get("tier"), "pool": bool(s.get("pool")),
            "certainty": s.get("certainty"), "market_family": fam,
            "news": " · ".join(x for x in (s.get("news_level"), s.get("news_note"),
                                           (s.get("lineup_check") or {}).get("note")) if x),
            "framework_record_in_family": say_framework(fw.get(fam)),
            "matchbook_record_in_family": say_matchbook(mb.get(fam)),
            "paper_record_in_family": say_paper(paper.get(fam)),
        })
    return out


# ---------------------------------------------------------------- the model
def _version(name: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", name)[:3]) or (0,)


def model_chain(get: Callable, key: str) -> list[str]:
    """The models to try, strongest first (2026-10-23, the Architect: a stronger reasoner): GEMINI_MODEL
    if set, then the newest stable Pro, Flash and Flash-Lite on the account. A model whose free quota
    is spent (429) or that fails hands the batch to the next one."""
    chain = [os.getenv("GEMINI_MODEL")] if os.getenv("GEMINI_MODEL") else []
    try:
        r = get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        r.raise_for_status()
        names = [m.get("id", "").removeprefix("models/") for m in r.json().get("data") or []]
    except Exception:  # noqa: BLE001 — GEMINI_MODEL alone, if set
        names = []
    names = [n for n in names if n.startswith("gemini") and not any(x in n for x in _SKIP_MODELS)]
    for want in ("pro", "flash", "flash-lite"):
        hits = [n for n in names if n.endswith(want) or f"{want}-0" in n or n.endswith(f"{want}-latest")]
        hits = [n for n in hits if want != "flash" or "lite" not in n]
        if hits:
            chain.append(max(hits, key=_version))
    return list(dict.fromkeys(m for m in chain if m))


def pick_model(get: Callable, key: str) -> Optional[str]:
    chain = model_chain(get, key)
    return chain[0] if chain else None


def _parse(text: str) -> dict:
    """The first JSON object in the answer (a grounded answer may wrap it in prose or add a second)."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    i = text.find("{")
    obj, _ = json.JSONDecoder().raw_decode(text[i:] if i >= 0 else text)
    return {p.get("id"): p for p in obj.get("picks") or []}


SEARCH_LOG: list = []        # per batch: searches run, or why search failed (copied into the doc)


def _ask_grounded(post: Callable, key: str, model: str, rows: list[dict], prompt: str) -> dict:
    """Gemini's own endpoint with the Google Search tool, so the judgement can use today's news."""
    r = post(f"{NATIVE_URL}/models/{model}:generateContent", params={"key": key}, timeout=180,
             json={"contents": [{"role": "user", "parts": [{"text": prompt + json.dumps(rows, ensure_ascii=False)}]}],
                   "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.2}})
    r.raise_for_status()
    cand = (r.json().get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    got = _parse("".join(p.get("text", "") for p in parts))
    SEARCH_LOG.append({"model": model, "searches": len((cand.get("groundingMetadata") or {}).get("webSearchQueries") or [])})
    return got


def _ask(post: Callable, key: str, model: str, rows: list[dict], sleep: Optional[Callable] = None,
         prompt: str = PROMPT, search: bool = True) -> dict:
    """One batch: with Google Search first; without it (the OpenAI-compatible endpoint) if that fails."""
    import time
    sleep = sleep or time.sleep
    if search:
        try:
            return _ask_grounded(post, key, model, rows, prompt)
        except Exception as e:  # noqa: BLE001 — search refused or unparsable: judge without it
            SEARCH_LOG.append({"model": model, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    for attempt in range(3):           # the free tier answers 503/429 when busy: wait and retry
        r = post(f"{BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=120,
                 json={"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                       "messages": [{"role": "user", "content": prompt + json.dumps(rows, ensure_ascii=False)}]})
        if getattr(r, "status_code", 200) not in (429, 500, 502, 503, 504) or attempt == 2:
            break
        sleep(20 * (attempt + 1))
    r.raise_for_status()
    return _parse(r.json()["choices"][0]["message"]["content"])


def _clean(p: Optional[dict]) -> dict:
    if not p:
        return {"verdict": "PENDING", "reasons": "no answer for this pick", "stake_factor": 1.0}
    v = str(p.get("verdict") or "").lower()
    try:
        ch, cf = float(p.get("ai_chance")), float(p.get("confidence"))
    except (TypeError, ValueError):
        return {"verdict": "PENDING", "reasons": "malformed answer", "stake_factor": 1.0}
    if v not in VERDICTS or not (0 <= ch <= 1 and 0 <= cf <= 1):
        return {"verdict": "PENDING", "reasons": "malformed answer", "stake_factor": 1.0}
    return {"verdict": v, "stake_factor": STAKE_FACTOR[v], "ai_chance": round(ch, 4), "confidence": round(cf, 3),
            "reasons": str(p.get("reasons") or "")[:400]}


def pool_legs(picks_doc: dict) -> list[dict]:
    """The rated pool's legs the Matchbook agent can trade (chance >= POOL_MIN_CHANCE) that are not
    already singles, shaped like singles so they get a verdict too (2026-10-19: on 20-10 only 3 of
    the 17 tradable legs were singles, so the agent's bets mostly carried no verdict)."""
    singles = {(s.get("fixture"), s.get("market")) for s in picks_doc.get("singles") or []}
    ko = {s.get("fixture"): s.get("kickoff_utc") for s in picks_doc.get("singles") or []}
    out = []
    for r in picks_doc.get("rated") or []:
        for mk, ch in r.get("pool") or []:
            if ch is None or ch < POOL_MIN_CHANCE or (r.get("fixture"), mk) in singles:
                continue
            out.append({"fixture": r.get("fixture"), "league": r.get("league"),
                        "kickoff_utc": ko.get(r.get("fixture")) or r.get("kickoff"),
                        "market": mk, "pick": mk.rsplit("|", 1)[-1], "chance": ch, "pool": True})
    return out


def value_legs(picks_doc: dict) -> list[dict]:
    """The value singles (one leg each, own booking code) that are not already board singles, so the
    SportyBet placer can apply their verdict to the value codes it places (2026-10-23)."""
    singles = {(s.get("fixture"), s.get("market")) for s in picks_doc.get("singles") or []}
    out = []
    for v in picks_doc.get("value") or []:
        legs = v.get("alt_legs") or []
        if not isinstance(v, dict) or len(legs) != 1 or (legs[0].get("fixture"), legs[0].get("market")) in singles:
            continue
        leg = legs[0]
        out.append({"fixture": leg.get("fixture"), "league": leg.get("league"), "kickoff_utc": leg.get("kickoff"),
                    "market": leg.get("market"), "pick": leg.get("pick"), "price": leg.get("price"),
                    "chance": leg.get("chance"), "code": v.get("code"), "tier": "value"})
    return out


def reason(picks_doc: dict, key: Optional[str] = None, get: Optional[Callable] = None,
           post: Optional[Callable] = None, now: Optional[datetime] = None) -> dict:
    """The reasoning document for one picks file. Never raises on a model failure."""
    singles = (picks_doc.get("singles") or []) + pool_legs(picks_doc) + value_legs(picks_doc)
    return _reason(picks_doc, singles, context(singles), PROMPT, key, get, post, now)


def _reason(picks_doc: dict, singles: list[dict], rows: list[dict], prompt: str, key: Optional[str],
            get: Optional[Callable], post: Optional[Callable], now: Optional[datetime]) -> dict:
    import requests
    key = key if key is not None else os.getenv("GEMINI_API_KEY", "").strip()
    get, post = get or requests.get, post or requests.post
    now = now or datetime.now(UTC)
    doc = {"date": picks_doc.get("date"), "picks_generated_at": picks_doc.get("generated_at"),
           "run_at": now.isoformat(timespec="seconds"), "model": None, "advisory": False,
           "acts_on": "stake: back x1, lower x0.75, veto x0.5 (never dropped)", "note": None, "picks": []}
    prompt = teaching("football" if prompt is PROMPT else "nba") + prompt
    answers: dict = {}
    if not key:
        doc["note"] = "NO DATA — PENDING: GEMINI_API_KEY not set"
    else:
        SEARCH_LOG.clear()
        chain = model_chain(get, key)
        doc["model"] = chain[0] if chain else None
        if not chain:
            doc["note"] = "NO DATA — PENDING: no Gemini model on this key"
        used = []
        for i in range(0, len(rows), BATCH) if chain else ():
            err = None
            for m in chain:          # a spent quota or a failure hands the batch to the next model
                try:
                    answers.update(_ask(post, key, m, rows[i:i + BATCH], prompt=prompt))
                    used.append(m)
                    err = None
                    break
                except Exception as e:  # noqa: BLE001
                    err = e
            if err is not None:      # one failed batch leaves only its own picks PENDING
                doc["note"] = f"PARTLY PENDING: {type(err).__name__}: {str(err)[:160]}"
        if used:
            doc["model"] = ", ".join(dict.fromkeys(used))
        doc["search"] = {"batches_searched": sum(1 for x in SEARCH_LOG if "searches" in x),
                         "queries": sum(x.get("searches", 0) for x in SEARCH_LOG),
                         "errors": [x["error"] for x in SEARCH_LOG if "error" in x][:3]}
    for row, s in zip(rows, singles):
        doc["picks"].append({"fixture": s.get("fixture"), "market": s.get("market"),
                             "pick": row["pick"], "price": s.get("price"),
                             "model_chance": s.get("chance"), "code": s.get("code"),
                             "pool": bool(s.get("pool")),
                             **_clean(answers.get(row["id"]))})
    return doc


# ---------------------------------------------------------------- NBA (Architect 2026-10-20: "The way we
# are treating football, that's how NBA should be treated too ... the Gemini reasoning, build the NBA")
NBA_FAMILY = {"219": "NBA winner", "223": "NBA handicap", "225": "NBA total", "227": "NBA team total",
              "228": "NBA team total", "68": "NBA 1st half total", "66": "NBA 1st half handicap",
              "236": "NBA quarter total", "303": "NBA quarter handicap"}
PROMPT_NBA = PROMPT.replace("a football betting model", "an NBA betting model").replace(
    "(team news and absences in the notes, motivation,",
    "(the sharp line it was priced from, how far the price sits above fair, motivation,") + ""
PROMPT_NBA = PROMPT_NBA.replace("PICKS:\n", "NBA notes: model_chance is the sharp bookmaker's line (ESPN BET) with its "
                                "margin removed, so it is already a market view; \"value_pts\" is how far the "
                                "SportyBet price sits above that fair price. Totals and handicaps include overtime "
                                "unless the pick names a half or a quarter.\n\nPICKS:\n")


def nba_family(market_id) -> str:
    return NBA_FAMILY.get(str(market_id), "NBA other")


def nba_records(ledger_dir: Path = LEDGER_DIR) -> dict:
    """{family: {n, won, flat_return, close_value}} — graded regular-season NBA board picks."""
    g: dict = {}
    for f in sorted(ledger_dir.glob("nba_2*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in doc.get("picks") or []:
            if p.get("stage") != "regular" or p.get("result") not in ("won", "lost") or not p.get("price"):
                continue
            r = g.setdefault(nba_family(p.get("market_id")), {"n": 0, "won": 0, "ret": 0.0, "cv": []})
            r["n"] += 1
            r["won"] += p["result"] == "won"
            r["ret"] += (float(p["price"]) - 1) if p["result"] == "won" else -1.0
            if p.get("close_value") is not None:
                r["cv"].append(float(p["close_value"]))
    return {k: {"n": v["n"], "won": v["won"], "flat_return": round(v["ret"] / v["n"], 4),
                "close_value": round(sum(v["cv"]) / len(v["cv"]), 4) if v["cv"] else None}
            for k, v in g.items()}


def say_nba(r: Optional[dict]) -> str:
    if not r or not r.get("n"):
        return "TOO FEW: no graded regular-season NBA picks in this family yet"
    n, ret = r["n"], r.get("flat_return") or 0
    word = "TOO FEW" if n < 15 else ("WINNING" if ret > 0 else "LOSING")
    cv = r.get("close_value")
    return (f"{word}: NBA board graded {n} picks in this family, won {r['won']}, flat return {ret:+.1%}"
            + (f", value against the closing line {cv:+.1%}" if cv is not None else ""))


def nba_context(picks: list[dict], ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    rec = nba_records(ledger_dir)
    out = []
    for i, p in enumerate(picks):
        price, ch = p.get("price"), p.get("chance")
        fam = nba_family(p.get("market_id"))
        out.append({
            "id": i, "fixture": f"{p.get('home')} v {p.get('away')}", "tip_utc": p.get("tip"),
            "stage": p.get("stage"), "pick": p.get("pick"), "price": price, "model_chance": ch,
            "break_even_chance": round(1 / float(price), 4) if price else None,
            "value_pts": round(100 * float(p["ev"]), 1) if p.get("ev") is not None else None,
            "market_family": fam, "sharp_line": p.get("sharp"), "pool": False,
            "framework_record_in_family": say_nba(rec.get(fam)),
        })
    return out


def reason_nba(nba_doc: dict, key: Optional[str] = None, get: Optional[Callable] = None,
               post: Optional[Callable] = None, now: Optional[datetime] = None,
               ledger_dir: Path = LEDGER_DIR) -> dict:
    """The reasoning document for one NBA board (output/picks/nba_<date>.json): the same
    judgement as football's, on the board's picks (kept and dropped)."""
    picks = (nba_doc.get("picks") or []) + (nba_doc.get("picks_dropped") or [])
    doc = _reason(nba_doc, picks, nba_context(picks, ledger_dir), PROMPT_NBA, key, get, post, now)
    doc["sport"] = "nba"
    for x, p in zip(doc["picks"], picks):
        x["fixture"], x["market"] = f"{p.get('home')} v {p.get('away')}", \
            f"NBA:{p.get('market_id')}|{p.get('specifier') or ''}|{p.get('outcome')}"
    return doc


def record_nba(out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    """NBA verdicts against their graded results (regular season), and close_value per verdict."""
    rows, cvs = [], {v: [] for v in VERDICTS}
    for f in sorted(out_dir.glob("reasoning_nba_*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            d = json.loads((ledger_dir / f"nba_{r['date']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        by = {(f"{p.get('home')} v {p.get('away')}",
               f"NBA:{p.get('market_id')}|{p.get('specifier') or ''}|{p.get('outcome')}"): p
              for p in (d.get("picks") or []) + (d.get("picks_dropped") or [])}
        for x in r.get("picks") or []:
            p = by.get((x.get("fixture"), x.get("market"))) or {}
            if x.get("verdict") not in VERDICTS or p.get("stage") != "regular":
                continue
            if p.get("close_value") is not None:
                cvs[x["verdict"]].append(float(p["close_value"]))
            if p.get("result") in ("won", "lost"):
                rows.append((x["verdict"], p["result"] == "won", float(p.get("price") or 0)))
    out: dict = {}
    for v in VERDICTS:
        g = [r for r in rows if r[0] == v]
        out[v] = {"n": len(g)}
        if g:
            won = sum(1 for r in g if r[1])
            out[v].update(won=won, flat_return=round(sum((r[2] - 1) if r[1] else -1 for r in g) / len(g), 4))
        if cvs[v]:
            out[v]["close_value"] = round(sum(cvs[v]) / len(cvs[v]), 4)
    return {"graded": len(rows), "by_verdict": out}


# ---------------------------------------------------------------- learning (the Architect, 2026-10-23:
# "the whole point of the whole reasoning is for it to be able to improve on its mistakes ... recursive
# self-improvement"). Every run shows the model its own scorecard, its recent mistakes with the reasons
# it gave, and the lessons it wrote for itself; once a day reflect() rewrites those lessons from the
# graded record. Lessons live in memory/reasoning_lessons.json, so they persist from run to run.
def graded_verdicts(sport: str = "football", out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    """Every past verdict with its result, oldest first: date, fixture, pick, verdict, chances, reasons, won."""
    out = []
    pat, src = ("reasoning_nba_*.json", "nba_{}.json") if sport == "nba" else ("reasoning_2*.json", "picks_{}.json")
    for f in sorted(out_dir.glob(pat)):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            d = json.loads((ledger_dir / src.format(r["date"])).read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        if sport == "nba":
            by = {(f"{p.get('home')} v {p.get('away')}",
                   f"NBA:{p.get('market_id')}|{p.get('specifier') or ''}|{p.get('outcome')}"): p
                  for p in (d.get("picks") or []) + (d.get("picks_dropped") or [])}
        else:
            by = {(s.get("fixture"), s.get("market")): s for s in d.get("singles") or []}
        for x in r.get("picks") or []:
            s = by.get((x.get("fixture"), x.get("market"))) or {}
            if x.get("verdict") in VERDICTS and s.get("result") in ("won", "lost"):
                out.append({"date": r["date"], "fixture": x.get("fixture"), "pick": x.get("pick"),
                            "price": x.get("price"), "verdict": x["verdict"], "model_chance": x.get("model_chance"),
                            "ai_chance": x.get("ai_chance"), "reasons": x.get("reasons") or "",
                            "won": s["result"] == "won"})
    return out


def mistakes(rows: list[dict], n: int = MISTAKES_SHOWN) -> list[dict]:
    """The newest wrong calls: a veto or lower that won, a back that lost."""
    bad = [r for r in rows if (r["verdict"] in ("veto", "lower") and r["won"]) or (r["verdict"] == "back" and not r["won"])]
    return bad[-n:]


def load_lessons(path: Path = LESSONS) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def teaching(sport: str = "football", out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR,
             lessons_path: Path = LESSONS) -> str:
    """The text put before the picks: scorecard, calibration, recent mistakes, own lessons."""
    rows = graded_verdicts(sport, out_dir, ledger_dir)
    lines = [f"YOUR RECORD ({sport}, {len(rows)} graded verdicts):"]
    for v in VERDICTS:
        g = [r for r in rows if r["verdict"] == v]
        if g:
            won = sum(r["won"] for r in g)
            said = [r["ai_chance"] for r in g if r["ai_chance"] is not None]
            ret = sum((float(r["price"] or 0) - 1) if r["won"] else -1 for r in g) / len(g)
            lines.append(f"- {v}: {won}/{len(g)} won ({won / len(g):.0%}); you said {sum(said) / len(said):.0%} "
                         f"on average; flat return {ret:+.1%}" if said else f"- {v}: {won}/{len(g)} won")
    if not rows:
        lines.append("- nothing graded yet")
    else:
        hit = {v: sum(r["won"] for r in rows if r["verdict"] == v) / max(1, sum(r["verdict"] == v for r in rows))
               for v in VERDICTS}
        if hit["veto"] >= hit["back"] and sum(r["verdict"] == "veto" for r in rows) >= 10:
            lines.append("- WARNING: your vetoes win as often as your backs. Your vetoes are not finding losers yet; "
                         "veto only on a concrete fact you found, and say which.")
    bad = mistakes(rows)
    if bad:
        lines.append("YOUR RECENT MISTAKES (learn from these):")
        for r in bad:
            lines.append(f"- {r['date']} {r['fixture']} {r['pick']} @{r['price']}: you said {r['verdict'].upper()} "
                         f"({r['reasons'][:160]}) -> it {'WON' if r['won'] else 'LOST'}")
    les = (load_lessons(lessons_path).get(sport) or {}).get("lessons") or []
    if les:
        lines.append("YOUR LESSONS (written by you from your record; apply them):")
        lines += [f"- {x}" for x in les[:MAX_LESSONS]]
    return "\n".join(lines) + "\n\n"


REFLECT = """You are the reasoning step of a betting model, reviewing your own graded verdicts so you
improve. Below: your verdicts with what happened, and your current lessons. Write the lessons that
would have made you right more often: short, concrete, testable rules ("a veto on team news alone
won 8 of 10: only veto when a starter is confirmed out"). Keep a current lesson only if the record
supports it; drop or rewrite one the record contradicts. At most {n} lessons. Return JSON only:
{{"lessons": ["...", ...], "summary": "<one sentence on what changed>"}}

CURRENT LESSONS:
{lessons}

GRADED VERDICTS (oldest first):
{rows}
"""


def reflect(sport: str, key: Optional[str] = None, get: Optional[Callable] = None, post: Optional[Callable] = None,
            now: Optional[datetime] = None, out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR,
            lessons_path: Path = LESSONS) -> Optional[dict]:
    """Once a day per sport: the sport's new lessons entry, rewritten from the graded record (the
    runner saves it to memory/reasoning_lessons.json). None when skipped or failed: the old lessons stay."""
    import requests
    key = key if key is not None else os.getenv("GEMINI_API_KEY", "").strip()
    get, post, now = get or requests.get, post or requests.post, now or datetime.now(UTC)
    allx = load_lessons(lessons_path)
    cur = allx.get(sport) or {}
    rows = graded_verdicts(sport, out_dir, ledger_dir)
    if not key or not rows or cur.get("date") == now.date().isoformat() or cur.get("graded") == len(rows):
        return None
    text = REFLECT.format(n=MAX_LESSONS, lessons="\n".join(f"- {x}" for x in cur.get("lessons") or []) or "(none yet)",
                          rows="\n".join(f"{r['date']} {r['fixture']} | {r['pick']} @{r['price']} | model "
                                         f"{r['model_chance']} you {r['ai_chance']} | {r['verdict']} | "
                                         f"{r['reasons'][:140]} | {'WON' if r['won'] else 'LOST'}"
                                         for r in rows[-120:]))
    for m in model_chain(get, key):
        try:
            r = post(f"{BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=180,
                     json={"model": m, "temperature": 0.2, "response_format": {"type": "json_object"},
                           "messages": [{"role": "user", "content": text}]})
            r.raise_for_status()
            body = r.json()["choices"][0]["message"]["content"]
            got = json.loads(re.sub(r"^```(?:json)?|```$", "", body.strip()).strip())
            les = [str(x)[:240] for x in got.get("lessons") or [] if str(x).strip()][:MAX_LESSONS]
            if not les:
                continue
            return {"date": now.date().isoformat(), "graded": len(rows), "model": m, "lessons": les,
                    "summary": str(got.get("summary") or "")[:300],
                    "history": ((cur.get("history") or []) + [{"date": now.date().isoformat(),
                                                               "graded": len(rows), "n": len(les)}])[-60:]}
        except Exception:  # noqa: BLE001 — the next model, else the old lessons stay
            continue
    return None


# ---------------------------------------------------------------- the record
def record(out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    """Every past verdict against the graded result: hit rate and flat-stake return by
    verdict. Thinking earns weight only if 'veto' loses more and 'back' wins more.
    Closing-line value (%) is scored per verdict too, once the close is in, result or not:
    'back' should beat the close more often than 'veto'."""
    rows = []
    clvs: dict = {v: [] for v in VERDICTS}
    for f in sorted(out_dir.glob("reasoning_2*.json")):        # football; NBA is reasoning_nba_*
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            p = json.loads((ledger_dir / f"picks_{r['date']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        sing = {(s.get("fixture"), s.get("market")): s for s in p.get("singles") or []}
        for x in r.get("picks") or []:
            s = sing.get((x.get("fixture"), x.get("market"))) or {}
            got = s.get("result")
            if x.get("verdict") in VERDICTS and s.get("clv") is not None:
                clvs[x["verdict"]].append(float(s["clv"]))
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
    for v in VERDICTS:
        c = clvs[v]
        if c:
            by[v].update({"clv_n": len(c), "mean_clv": round(sum(c) / len(c), 2),
                          "beat_close": sum(1 for x in c if x > 0)})
    # who was closer: the model's chance or the reasoning's own (Brier score, lower is better)
    sc = [r for r in rows if r[3] is not None and r[4] is not None]
    brier = {"n": len(sc)}
    if sc:
        brier["model"] = round(sum((float(r[3]) - r[1]) ** 2 for r in sc) / len(sc), 4)
        brier["ai"] = round(sum((float(r[4]) - r[1]) ** 2 for r in sc) / len(sc), 4)
    return {"updated": datetime.now(UTC).date().isoformat(), "graded": len(rows), "by_verdict": by,
            "brier": brier, "nba": record_nba(out_dir, ledger_dir)}


def summary_line(rec: dict) -> str:
    b = rec.get("by_verdict") or {}
    parts = [f"{v} {b[v]['won']}/{b[v]['n']} ({b[v]['flat_return']:+.1%})" for v in VERDICTS if b.get(v, {}).get("n")]
    clv = [f"{v} {b[v]['mean_clv']:+.2f}% (beat {b[v]['beat_close']}/{b[v]['clv_n']})"
           for v in VERDICTS if b.get(v, {}).get("clv_n")]
    if clv:
        parts.append("CLV " + ", ".join(clv))
    br = rec.get("brier") or {}
    if br.get("n"):
        better = ("level" if br["ai"] == br["model"] else
                  "the reasoning is closer" if br["ai"] < br["model"] else "the plain model is closer")
        parts.append(f"Brier model {br['model']:.3f} vs AI {br['ai']:.3f}: {better}")
    nb = (rec.get("nba") or {}).get("by_verdict") or {}
    nba = [f"{v} {nb[v]['won']}/{nb[v]['n']} ({nb[v]['flat_return']:+.1%})" for v in VERDICTS if nb.get(v, {}).get("n")]
    return (f"Reasoning record ({rec.get('graded', 0)} graded): " + (" · ".join(parts) or "nothing graded yet")
            + f" · NBA ({(rec.get('nba') or {}).get('graded', 0)} graded): " + (" · ".join(nba) or "nothing graded yet"))
