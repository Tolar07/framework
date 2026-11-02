"""
FACT SHEET — step 2 of the bot-training plan (the Architect, 2026-11-01: "Ok start").
RECORDED ONLY. Nothing here selects, stakes or moves a chance.

Asked for a probability, the language models did no better than the plain model (reasoning record
01-11: Brier 0.171 v 0.170), and the vetoed picks won more often than the backed ones. So here they
are asked for FACTS instead, the context checklist every pick on the ledger still reads as "unknown"
(engine/records/context_facts.CHECKLIST), plus absences and rotation:

    1. Gemini searches the web (Google Search tool) for each fixture and fills the sheet, quoting what
       it found ("evidence", source names included).
    2. NVIDIA and OpenRouter (":free" only, the panel's guards) read that evidence and fill the same
       sheet on their own.
    3. A field counts only when at least two members agree (counts within 1 of each other); otherwise
       it stays PENDING (HR35). A fact found by one model alone is never used.

Agreed facts are signed for each pick the same way as context_facts (direction +1 helps the pick,
-1 hurts it, 0 can't be signed) and saved to output/facts/facts_<date>.json. study() sets every
graded pick's facts against the market: a fact earns attention only if the picks it touched won more
(or less) often than the de-margined price said. The study is the evidence for step 3 (learned
weights); until then the facts change nothing.

    python -m engine.fact_sheet --study      # print the study
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Optional

from engine import verdict_panel as VP
from engine.records.context_facts import pick_side

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output" / "facts"
LEDGER_DIR = ROOT / "output" / "picks"
RECORD = ROOT / "memory" / "fact_record.json"
NATIVE_URL = os.getenv("GEMINI_NATIVE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

BATCH = 6                                   # fixtures per call
BUDGET_S = float(os.getenv("FACT_SHEET_BUDGET_S", "420"))
MIN_AGREE = 2
# Readers of Gemini's (or FotMob's) evidence: reader -> panel member whose key and endpoint it uses.
# nvidia_alt is a second, different model family on NVIDIA's free key (2026-11-01 23:00: OpenRouter's
# free allowance was spent on every model, so one reader was left and no fact could be agreed).
READERS = {"nvidia": "nvidia", "nvidia_alt": "nvidia", "openrouter": "openrouter"}
NVIDIA_ALT_MODEL = os.getenv("FACT_NVIDIA_ALT_MODEL", "")   # override; else the first of NVIDIA_ALT_PREFER listed
# Picked from NVIDIA's LIVE model list each run (2026-11-01: mistral-large too slow, llama-3.3-70b 410 Gone)
NVIDIA_ALT_PREFER = ("openai/gpt-oss-20b", "google/gemma-3-12b-it", "nvidia/nemotron-3.5-super-vl-120b-a12b")


def alt_model(get: Callable) -> str:
    """The second NVIDIA reader's model: the override, else the first preferred id NVIDIA lists now."""
    if NVIDIA_ALT_MODEL:
        return NVIDIA_ALT_MODEL
    try:
        r = get(str(VP.MEMBERS["nvidia"]["base"]) + "/models", timeout=30)
        r.raise_for_status()
        listed = {str(m.get("id", "")) for m in r.json().get("data") or []}
    except Exception:  # noqa: BLE001
        return NVIDIA_ALT_PREFER[0]
    return next((m for m in NVIDIA_ALT_PREFER if m in listed), NVIDIA_ALT_PREFER[0])
WAIT_429_S = 45                             # one wait on a 429 before the next Gemini model
MAX_RATED = 20                              # rated games NOT bet on, also sheeted (learning beyond our bets)
MIN_STUDY_N = 30                            # below this a fact's residual is shown but not trusted

# field -> kind. Per side: <field>_home / <field>_away.
SIDE_FIELDS = {"rest_days": "int", "key_absences": "int", "rotation": "bool", "motivation": "level",
               "new_manager": "bool"}
GAME_FIELDS = {"away_long_travel": "bool", "derby": "bool", "weather_severe": "bool", "referee": "text"}
LEVELS = ("low", "normal", "high")

FIELD_DOC = """Fields (null when the sources do not say; NEVER guess):
- rest_days_home / rest_days_away: whole days since that team's previous competitive match
- key_absences_home / key_absences_away: players listed as ruled out (injury, suspension) for that team
- rotation_home / rotation_away: true if the team is expected to rest several regulars (cup, Europe
  midweek, title/relegation already decided)
- motivation_home / motivation_away: "low" | "normal" | "high" (high = title, relegation, qualification,
  derby at stake; low = nothing to play for)
- new_manager_home / new_manager_away: true if the head coach was appointed in the last 30 days
- away_long_travel: true if the away team travels more than ~500 km or crosses a border
- derby: true if it is a local or traditional rivalry
- weather_severe: true if heavy rain, snow, storm or extreme heat is forecast at kick-off
- referee: the referee's name, or null"""

SEARCH_PROMPT = """Search the web for each football fixture below (today's team news, line-ups, injuries,
the league table, the weather forecast, the referee). Fill the fact sheet from what you FIND.
""" + FIELD_DOC + """
Also give "evidence": 2-5 short sentences of what the sources said, each naming its source.
Return JSON only: {"fixtures": [{"id": <id>, "evidence": "...", <fields>}]}

FIXTURES:
"""

READ_PROMPT = """You check a fact sheet. For each football fixture, fill the fields from the evidence given.
Two fields are STABLE facts you may answer from general knowledge when the evidence is silent: "derby"
(a known local or traditional rivalry) and "away_long_travel" (the two clubs' cities are more than
~500 km apart or in different countries). Every other field must come from the evidence only: a field
the evidence does not settle is null.
""" + FIELD_DOC + """
Return JSON only: {"fixtures": [{"id": <id>, <fields>}]}

FIXTURES:
"""


def all_fields() -> list[str]:
    return [f"{f}_{s}" for f in SIDE_FIELDS for s in ("home", "away")] + list(GAME_FIELDS)


def kind(field: str) -> str:
    base = re.sub(r"_(home|away)$", "", field)
    return SIDE_FIELDS.get(base) or GAME_FIELDS.get(field) or "text"


def clean(field: str, v):
    """The value in its field's kind, or None (unknown)."""
    if v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none", "pending", "unknown")):
        return None
    k = kind(field)
    try:
        if k == "int":
            x = int(round(float(v)))
            return x if 0 <= x <= 40 else None
        if k == "bool":
            if isinstance(v, bool):
                return v
            s = str(v).strip().lower()
            return True if s in ("true", "yes", "1") else False if s in ("false", "no", "0") else None
        if k == "level":
            s = str(v).strip().lower()
            return s if s in LEVELS else None
    except (TypeError, ValueError):
        return None
    return str(v).strip()[:80]


def agree(field: str, answers: list) -> tuple[object, int]:
    """(agreed value, members agreeing) — value None when fewer than MIN_AGREE agree."""
    vals = [a for a in answers if a is not None]
    if kind(field) == "int":
        best: tuple[object, int] = (None, 0)
        for v in vals:
            near = sorted(x for x in vals if abs(x - v) <= 1)
            if len(near) > best[1]:
                best = (near[len(near) // 2], len(near))
        return best if best[1] >= MIN_AGREE else (None, best[1])
    if kind(field) == "text":
        norm = [str(v).lower() for v in vals]
        top = max(set(norm), key=norm.count) if norm else None
        n = norm.count(top) if top else 0
        return (next(v for v in vals if str(v).lower() == top), n) if n >= MIN_AGREE else (None, n)
    top = max(set(vals), key=vals.count) if vals else None
    n = vals.count(top) if vals else 0
    return (top, n) if n >= MIN_AGREE else (None, n)


def fixtures(singles: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for s in singles:
        fx = s.get("fixture")
        if fx and fx not in seen:
            seen[fx] = {"id": len(seen), "fixture": fx, "home": s.get("home"), "away": s.get("away"),
                        "league": s.get("league"), "kickoff_utc": s.get("kickoff_utc")}
    return list(seen.values())


NEWS_DIR = ROOT / "data" / "features"


def load_news(day: Optional[str], folder: Path = NEWS_DIR) -> dict:
    """FotMob team news the pre-kickoff loop captured for every fixture (data/features/news_<date>.json)."""
    try:
        return json.loads((folder / f"news_{day}.json").read_text(encoding="utf-8")) if day else {}
    except (OSError, ValueError):
        return {}


def fotmob_evidence(news: dict, fixture: str) -> str:
    n = news.get(fixture) or {}
    if not n:
        return ""
    out = [f"FotMob ({n.get('at') or 'PENDING'}, line-ups {n.get('lineup_type') or 'PENDING'}): "
           f"home unavailable {n.get('home_unavailable', 'PENDING')}, away unavailable {n.get('away_unavailable', 'PENDING')}"]
    absent = [f"{a.get('name')} ({a.get('side')}, {a.get('type')})" for a in n.get("absent") or []][:12]
    if absent:
        out.append("absent: " + ", ".join(absent))
    return "; ".join(out)


def local_evidence(singles: list[dict], fixture: str) -> str:
    """What the framework itself already knows about a fixture (news check, line-up check, missing squad
    value), as text for the readers when Gemini can't search (2026-11-01: Gemini 429 all evening)."""
    bits: list[str] = []
    for s in singles:
        if s.get("fixture") != fixture:
            continue
        for label, v in (("team news", s.get("news_note")), ("news level", s.get("news_level")),
                         ("line-up check", (s.get("lineup_check") or {}).get("note")
                          if isinstance(s.get("lineup_check"), dict) else s.get("lineup_check")),
                         ("share of squad value missing", s.get("missing"))):
            if v not in (None, "", "None", {}) and f"{label}: {v}" not in bits:
                bits.append(f"{label}: {v}")
    return ("framework data (no web search): " + "; ".join(bits))[:1200] if bits else ""


def _search(post: Callable, key: str, model: str, rows: list[dict]) -> dict:
    r = post(f"{NATIVE_URL}/models/{model}:generateContent", headers={"x-goog-api-key": key}, timeout=180,
             json={"contents": [{"role": "user", "parts": [{"text": SEARCH_PROMPT + json.dumps(rows, ensure_ascii=False)}]}],
                   "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.1}})
    if getattr(r, "status_code", 200) == 429:
        raise VP.RateLimited("gemini: 429")
    r.raise_for_status()
    cand = (r.json().get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in ((cand.get("content") or {}).get("parts") or []))
    text = re.sub(r"```(?:json)?", "", text).strip()
    i = text.find("{")
    obj, _ = json.JSONDecoder().raw_decode(text[i:] if i >= 0 else text)
    return {VP.as_id(f.get("id")): f for f in obj.get("fixtures") or []}


def _search_retry(post: Callable, key: str, model: str, rows: list[dict],
                  sleep: Callable) -> tuple[Optional[dict], str]:
    """(answer, "") or (None, "429" | the error). A 429 is waited out once (a per-minute limit clears)."""
    for attempt in (0, 1):
        try:
            return _search(post, key, model, rows), ""
        except VP.RateLimited:
            if attempt == 0:
                sleep(WAIT_429_S)
                continue
            return None, "429"
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {str(e)[:100]}"
    return None, "429"


def gather(singles: list[dict], keys: Optional[dict] = None, get: Optional[Callable] = None,
           post: Optional[Callable] = None, clock: Callable = time.monotonic,
           sleep: Callable = time.sleep, news: Optional[dict] = None) -> dict:
    """{"members": {...}, "fixtures": [{fixture, evidence, answers: {member: {field: v}}, agreed: {...}}]}.
    Never raises."""
    if get is None or post is None:
        import requests
        get, post = get or requests.get, post or requests.post
    keys = keys if keys is not None else {n: VP.member_key(n) for n in VP.MEMBERS}
    fxs = fixtures(singles)
    info: dict = {}
    answers: dict = {n: {} for n in ("gemini", *READERS)}
    evidence: dict = {}
    t0 = clock()
    gkey = keys.get("gemini") or ""
    if not gkey:
        info["gemini"] = {"status": "missing secret GEMINI_API_KEY"}
    else:
        model: Optional[str] = VP.pick_model("gemini", get, gkey)
        info["gemini"] = {"model": model, "status": "ok", "answered": 0}
        for j in range(0, len(fxs), BATCH):
            if clock() - t0 > BUDGET_S:
                info["gemini"]["status"] = f"time budget used; {info['gemini']['answered']} answered"
                break
            rows = fxs[j:j + BATCH]
            got, why = _search_retry(post, gkey, str(model), rows, sleep)
            while got is None and why == "429":
                model = VP._next_gemini(str(model))
                if not model:
                    break
                info["gemini"]["model"] = model
                got, why = _search_retry(post, gkey, model, rows, sleep)
            if got is None:
                if why == "429":
                    info["gemini"]["status"] = "off for this run: 429 on every Gemini model"
                    break
                info["gemini"]["status"] = f"partly failed: {why}"
                continue
            for i, f in got.items():
                if isinstance(i, int) and 0 <= i < len(fxs):
                    evidence[i] = str(f.get("evidence") or "")[:1200]
                    answers["gemini"][i] = {k: clean(k, f.get(k)) for k in all_fields()}
                    info["gemini"]["answered"] += 1
    # the readers: only fixtures that have evidence, only from that evidence
    # no web evidence for a fixture (Gemini off or silent): the readers get the framework's own data;
    # FotMob's captured team news is added to every fixture's evidence (2026-11-01: framework data alone
    # left every field null)
    for fx in fxs:
        fm = fotmob_evidence(news or {}, fx["fixture"])
        if not evidence.get(fx["id"]):
            loc = local_evidence(singles, fx["fixture"])
            evidence[fx["id"]] = "; ".join(x for x in (loc or ("framework data (no web search)" if fm else ""), fm) if x)
        elif fm:
            evidence[fx["id"]] = (evidence[fx["id"]] + "; " + fm)[:1600]
    have = [i for i in range(len(fxs)) if evidence.get(i)]

    t_read = clock()     # the readers get their own budget: Gemini's 429 waits must not use it up

    def reader(name: str) -> None:
        # Each reader writes only its own info[name] / answers[name] entry.
        member = READERS[name]
        key = keys.get(member) or ""
        if not key:
            info[name] = {"status": f"missing secret {VP.MEMBERS[member]['key']}"}
            return
        model = alt_model(get) if name == "nvidia_alt" else VP.pick_model(member, get, key)
        if not model:
            info[name] = {"status": "no free model available" if name == "openrouter" else "no model"}
            return
        info[name] = {"model": model, "status": "ok", "answered": 0}
        for j in range(0, len(have), BATCH):
            if clock() - t_read > BUDGET_S:
                info[name]["status"] = f"time budget used; {info[name]['answered']} answered"
                break
            rows = [{**fxs[i], "evidence": evidence[i]} for i in have[j:j + BATCH]]
            content = READ_PROMPT + json.dumps(rows, ensure_ascii=False)
            try:
                try:
                    obj = VP.chat_json(member, model, key, content, post)
                except VP.RateLimited:
                    # a ":free" OpenRouter model is often throttled upstream; the next free one may answer
                    # (2026-11-01 22:38: gemma 429 -> OpenRouter off, 0 agreed)
                    nxt = VP._next_free(str(model), get) if name == "openrouter" else None
                    if not nxt:
                        raise
                    info[name]["model"] = model = nxt
                    obj = VP.chat_json(member, model, key, content, post)
            except (VP.RateLimited, VP.PaidModelError, VP.ChargedError) as e:
                info[name]["status"] = f"off for this run: {e}"
                break
            except Exception as e:  # noqa: BLE001
                info[name]["status"] = f"partly failed: {type(e).__name__}: {str(e)[:100]}"
                continue
            for f in obj.get("fixtures") or []:
                i = VP.as_id(f.get("id"))
                if i in have:
                    answers[name][i] = {k: clean(k, f.get(k)) for k in all_fields()}
                    info[name]["answered"] += 1

    # 2026-11-01 20:08: read one after another, NVIDIA used the whole budget and OpenRouter answered 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(READERS)) as ex:
        list(ex.map(reader, list(READERS)))
    out = []
    for fx in fxs:
        i = fx["id"]
        fmn = (news or {}).get(fx["fixture"]) or {}
        by = {n: answers[n][i] for n in answers if i in answers[n]}
        agreed: dict = {}
        support: dict = {}
        for k in all_fields():
            v, n = agree(k, [a.get(k) for a in by.values()])
            if v is not None:
                agreed[k], support[k] = v, n
        # absences are COUNTED from FotMob's list, not asked of a model (2026-11-01: both readers said
        # null to "regular starters", which the evidence can't settle)
        for side in ("home", "away"):
            listed = [a for a in fmn.get("absent") or [] if a.get("side") == side]
            if fmn.get("absent") is not None or fmn.get(f"{side}_unavailable") is not None:
                agreed[f"key_absences_{side}"] = len(listed) if fmn.get("absent") is not None                     else int(fmn.get(f"{side}_unavailable") or 0)
                support[f"key_absences_{side}"] = "fotmob"
        ev = evidence.get(i) or ""
        src = "framework" if ev.startswith("framework data") else "web" if ev else None
        out.append({**fx, "evidence": ev or "PENDING", "evidence_source": src, "answers": by, "agreed": agreed,
                    "support": support})
    return {"members": info, "fixtures": out}


def done(old: dict, picks_doc: dict) -> bool:
    """This board already has a fact sheet worth keeping: same board and two members answered.
    An empty sheet (every model rate-limited) is tried again on the next reasoning run."""
    # at least MIN_AGREE members answered: one model alone can never agree a fact (2026-11-01 22:17: a
    # NVIDIA-only sheet counted as done and the side-by-side fix was never tried on that board)
    return old.get("picks_generated_at") == picks_doc.get("generated_at") and sum(
        1 for m in (old.get("members") or {}).values() if (m or {}).get("answered")) >= MIN_AGREE


def signed(single: dict, agreed: dict) -> list[dict]:
    """The agreed facts as context_facts-style rows for one pick: direction +1 helps it, -1 hurts it."""
    backed = pick_side(single)

    def sign(about: Optional[str], good_for_about: Optional[bool]) -> int:
        if backed is None or about is None or good_for_about is None:
            return 0
        return (1 if good_for_about else -1) * (1 if about == backed else -1)

    rows = []
    rh, ra = agreed.get("rest_days_home"), agreed.get("rest_days_away")
    if rh is not None and ra is not None and abs(rh - ra) >= 2:
        rows.append({"fact": "rest_edge", "side": "home" if rh > ra else "away",
                     "direction": sign("home" if rh > ra else "away", True), "size": min(abs(rh - ra), 7) / 7})
    for side in ("home", "away"):
        n = agreed.get(f"key_absences_{side}")
        if n:
            rows.append({"fact": "key_absences", "side": side, "direction": sign(side, False),
                         "size": min(n, 5) / 5})
        if agreed.get(f"rotation_{side}") is True:
            rows.append({"fact": "rotation", "side": side, "direction": sign(side, False), "size": 1.0})
        m = agreed.get(f"motivation_{side}")
        if m in ("low", "high"):
            rows.append({"fact": f"motivation_{m}", "side": side, "direction": sign(side, m == "high"),
                         "size": 1.0})
        if agreed.get(f"new_manager_{side}") is True:
            rows.append({"fact": "new_manager", "side": side, "direction": 0, "size": 1.0})
    if agreed.get("away_long_travel") is True:
        rows.append({"fact": "away_long_travel", "side": "away", "direction": sign("away", False), "size": 1.0})
    for k in ("derby", "weather_severe"):
        if agreed.get(k) is True:
            rows.append({"fact": k, "side": None, "direction": 0, "size": 1.0})
    for r in rows:
        r["source"] = "ai_fact_sheet"
    return rows


def rated_unbet(picks_doc: dict, n: int = MAX_RATED) -> list[dict]:
    """Rated fixtures that are not on the board, earliest kick-off first, as home-side pseudo-picks."""
    on = {s.get("fixture") for s in picks_doc.get("singles") or []}
    rows = [r for r in picks_doc.get("rated") or [] if r.get("fixture") not in on and r.get("home") and r.get("away")]
    rows.sort(key=lambda r: str(r.get("kickoff_utc") or r.get("kickoff") or ""))
    return [{"fixture": r["fixture"], "home": r["home"], "away": r["away"], "league": r.get("league"),
             "kickoff_utc": r.get("kickoff_utc") or r.get("kickoff"), "market": "home win", "pick": "Home"}
            for r in rows[:n]]


def build(picks_doc: dict, **kw) -> dict:
    singles = picks_doc.get("singles") or []
    rated = rated_unbet(picks_doc)
    kw.setdefault("news", load_news(picks_doc.get("date")))
    sheet = gather(singles + rated, **kw)
    by_fx = {f["fixture"]: f for f in sheet["fixtures"]}
    picks = []
    for s in singles:
        f = by_fx.get(s.get("fixture")) or {}
        picks.append({"fixture": s.get("fixture"), "market": s.get("market"), "pick": s.get("pick"),
                      "facts": signed(s, f.get("agreed") or {})})
    rated_out = [{"fixture": r["fixture"], "facts": signed(r, (by_fx.get(r["fixture"]) or {}).get("agreed") or {})}
                 for r in rated]
    filled = sum(len(f["agreed"]) for f in sheet["fixtures"])
    return {"date": picks_doc.get("date"), "picks_generated_at": picks_doc.get("generated_at"),
            "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "recorded_only": True,
            "members": sheet["members"], "fields_agreed": filled,
            "fields_asked": len(all_fields()) * len(sheet["fixtures"]),
            "fixtures": sheet["fixtures"], "picks": picks, "rated": rated_out}


# ---------------------------------------------------------------- the study (results decide)
def _anchor(s: dict) -> Optional[float]:
    """The market's chance: the de-margined sharp price, else 1/price (a slight overestimate)."""
    sp = VP._num(s.get("sharp_p"))
    if sp is not None and 0 < sp < 1:
        return sp
    pr = VP._num(s.get("price"))
    return 1 / pr if pr and pr > 1 else None


def study(out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    """Per fact and direction: graded picks, won, the market's mean chance, residual (won - market)."""
    cells: dict = {}
    seen = set()
    for f in sorted(out_dir.glob("facts_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            led = json.loads((ledger_dir / f"picks_{doc['date']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        by = {(s.get("fixture"), s.get("market")): s for s in led.get("singles") or []}
        for p in doc.get("picks") or []:
            s = by.get((p.get("fixture"), p.get("market"))) or {}
            uid = (doc["date"], p.get("fixture"), p.get("market"))
            a = _anchor(s)
            if uid in seen or s.get("result") not in ("won", "lost") or a is None:
                continue
            seen.add(uid)
            for x in p.get("facts") or []:
                key = f"{x['fact']} ({'+' if x['direction'] > 0 else '-' if x['direction'] < 0 else '0'})"
                c = cells.setdefault(key, {"n": 0, "won": 0, "market": 0.0})
                c["n"] += 1
                c["won"] += s["result"] == "won"
                c["market"] += a
        # games we did NOT bet: the home result against the model's own chance (no market anchor here)
        rated_by = {r.get("fixture"): r for r in led.get("rated") or []}
        for p in doc.get("rated") or []:
            r = rated_by.get(p.get("fixture")) or {}
            uid = (doc["date"], p.get("fixture"), "rated")
            ft, probs = str(r.get("ft") or ""), r.get("p")
            m = re.match(r"^(\d+)-(\d+)$", ft)
            ph = VP._num(probs[0]) if isinstance(probs, list) and probs else None
            if uid in seen or not m or ph is None:
                continue
            seen.add(uid)
            won = int(m.group(1)) > int(m.group(2))
            for x in p.get("facts") or []:
                key = f"unbet: {x['fact']} ({'+' if x['direction'] > 0 else '-' if x['direction'] < 0 else '0'})"
                c = cells.setdefault(key, {"n": 0, "won": 0, "market": 0.0})
                c["n"] += 1
                c["won"] += won
                c["market"] += ph
    out = {}
    for k, c in sorted(cells.items()):
        out[k] = {"n": c["n"], "won_rate": round(c["won"] / c["n"], 3),
                  "market_rate": round(c["market"] / c["n"], 3),
                  "residual": round((c["won"] - c["market"]) / c["n"], 3), "trusted": c["n"] >= MIN_STUDY_N}
    return {"graded_picks": len(seen), "facts": out, "built_at": datetime.now(UTC).isoformat(timespec="seconds")}


def summary_line(rec: dict) -> str:
    facts = rec.get("facts") or {}
    if not facts:
        return f"fact sheet: {rec.get('graded_picks', 0)} graded picks with facts, nothing to study yet"
    top = sorted(facts.items(), key=lambda kv: -abs(kv[1]["residual"]) * min(kv[1]["n"], MIN_STUDY_N))[:3]
    return (f"fact sheet: {rec['graded_picks']} graded picks · "
            + " · ".join(f"{k} n{v['n']} {v['residual']:+.1%}" for k, v in top))


if __name__ == "__main__":
    import sys
    if "--study" in sys.argv:
        r = study()
        print(summary_line(r))
        print(json.dumps(r["facts"], indent=1))
