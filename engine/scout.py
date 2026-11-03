"""
SCOUT — a daily section of the reasoning step (Architect 2026-11-03).
RECORDED ONLY. Nothing here selects, stakes, drops, re-prices or moves a chance, a verdict, a threshold
or the CLV gate. If the scout fails or finds nothing, the reasoning step goes on exactly as before.

For every football fixture on the day's board (and the NBA board's games) Gemini, with Google Search,
looks for what the model cannot see: confirmed team news and injuries, line-ups, late line moves and
notable chatter on X. One record per fixture:

    {"tag": "scout", "sport", "id", "fixture", "finding", "direction", "confidence", "sources": [urls], "via"}

direction: home | away | draw | over | under | none (over/under = 2.5 goals, football only).
confidence: the probability that the direction's outcome happens (0 < p < 1); none -> null.
If Gemini is off (no key / 429 on every model) the panel's free NVIDIA then OpenRouter ":free" members
answer from the framework's own data, with no search (via says which; sources stay empty).

Saved to output/reasoning/scout_<date>.json (and scout_nba_<date>.json), beside the verdicts.
grade() scores each directional call against the result into memory/scout_record.json; summary_line()
is the one "Scout" line of the 23:02 bot report. Kill switch: SCOUT_ENABLED=0.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Optional

from engine import verdict_panel as VP

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output" / "reasoning"
LEDGER_DIR = ROOT / "output" / "picks"
RECORD = ROOT / "memory" / "scout_record.json"
NATIVE_URL = os.getenv("GEMINI_NATIVE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

BATCH = 6
BUDGET_S = float(os.getenv("SCOUT_BUDGET_S", "300"))
WAIT_429_S = 45
MAX_UNBET = 20
DIRECTIONS = ("home", "away", "draw", "over", "under", "none")
NBA_DIRECTIONS = ("home", "away", "none")


def enabled() -> bool:
    """SCOUT_ENABLED: default on; 0 / false / off / no switches the scout off."""
    return (os.getenv("SCOUT_ENABLED") or "1").strip().lower() not in ("0", "false", "off", "no")


PROMPT_BODY = """Search the web (Google, and X / Twitter posts) for each {sport} fixture below. Look ONLY for what a
statistical model cannot see: confirmed team news and injuries, line-ups, late line moves, and notable chatter
from credible accounts. Never guess; if you find nothing material say direction "none".
Return JSON only: {{"fixtures": [{{"id": <id>, "finding": "1-2 short sentences", "direction": "{dirs}",
"confidence": <probability 0-1 that the direction's outcome happens, null if none>, "sources": ["https://..."]}}]}}
{extra}
FIXTURES:
"""
PROMPT_FOOTBALL = PROMPT_BODY.format(sport="football", dirs="home|away|draw|over|under|none",
                                     extra='"over"/"under" mean 2.5 goals in regular time.')
PROMPT_NBA = PROMPT_BODY.format(sport="NBA", dirs="home|away|none",
                                extra='Direction is the side to win the game (overtime counts).')


# ---------------------------------------------------------------- inputs
def football_fixtures(picks_doc: dict) -> list[dict]:
    from engine import fact_sheet as FS
    singles = list(picks_doc.get("singles") or [])
    rows = FS.fixtures(singles + FS.rated_unbet(picks_doc, MAX_UNBET))
    return [{**r, "sport": "football"} for r in rows]


def nba_fixtures(board: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for p in (board.get("picks") or []) + (board.get("picks_dropped") or []):
        if not (p.get("home") and p.get("away")):
            continue
        fx = f"{p['home']} v {p['away']}"
        if fx not in seen:
            seen[fx] = {"id": len(seen), "fixture": fx, "home": p["home"], "away": p["away"],
                        "league": "NBA", "kickoff_utc": p.get("tip"), "sport": "nba"}
    return list(seen.values())


# ---------------------------------------------------------------- cleaning
def clean(row: dict, allowed: tuple = DIRECTIONS) -> Optional[dict]:
    """One model answer -> {finding, direction, confidence, sources}, or None when unusable (HR35)."""
    if not isinstance(row, dict):
        return None
    d = str(row.get("direction") or "none").strip().lower()
    if d not in allowed:
        return None
    conf = VP._num(row.get("confidence"))
    if d == "none":
        conf = None
    elif conf is None or not 0.0 < conf < 1.0:
        return None                      # a call without a usable probability is not recorded as a call
    srcs = [str(u)[:300] for u in (row.get("sources") or []) if isinstance(u, str) and u.startswith("http")][:5]
    return {"finding": str(row.get("finding") or "")[:400], "direction": d,
            "confidence": None if conf is None else round(conf, 3), "sources": srcs}


# ---------------------------------------------------------------- the model calls
def _search(post: Callable, key: str, model: str, prompt: str, rows: list[dict]) -> dict:
    slim = [{k: r.get(k) for k in ("id", "fixture", "league", "kickoff_utc")} for r in rows]
    r = post(f"{NATIVE_URL}/models/{model}:generateContent", headers={"x-goog-api-key": key}, timeout=180,
             json={"contents": [{"role": "user", "parts": [{"text": prompt + json.dumps(slim, ensure_ascii=False)}]}],
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


def _fallback(name: str, get: Callable, post: Callable, key: str, prompt: str, rows: list[dict]) -> dict:
    model = VP.pick_model(name, get, key)
    if not model:
        return {}
    slim = [{k: r.get(k) for k in ("id", "fixture", "league", "kickoff_utc")} for r in rows]
    note = "\n(No web search is available to you: answer only from what you reliably know, else direction none.)\n"
    obj = VP.chat_json(name, model, key, prompt + note + json.dumps(slim, ensure_ascii=False), post)
    return {VP.as_id(f.get("id")): f for f in obj.get("fixtures") or []}


def scout(fxs: list[dict], keys: Optional[dict] = None, get: Optional[Callable] = None,
          post: Optional[Callable] = None, clock: Callable = time.monotonic,
          sleep: Callable = time.sleep) -> dict:
    """{"members": {...}, "fixtures": [record, ...]}. Never raises; a fixture nobody answered is absent."""
    sport = fxs[0]["sport"] if fxs else "football"
    prompt, allowed = (PROMPT_NBA, NBA_DIRECTIONS) if sport == "nba" else (PROMPT_FOOTBALL, DIRECTIONS)
    info: dict = {}
    got: dict = {}                                     # fixture id -> (cleaned, via)
    try:
        if get is None or post is None:
            import requests  # type: ignore[import-untyped]
            get, post = get or requests.get, post or requests.post
        keys = keys if keys is not None else {n: VP.member_key(n) for n in VP.MEMBERS}
        t0 = clock()
        gkey = keys.get("gemini") or ""
        model: Optional[str] = None
        if not gkey:
            info["gemini"] = {"status": "missing secret GEMINI_API_KEY"}
        else:
            model = VP.pick_model("gemini", get, gkey)
            info["gemini"] = {"model": model, "status": "ok", "answered": 0}
        for j in range(0, len(fxs), BATCH):
            rows = fxs[j:j + BATCH]
            if clock() - t0 > BUDGET_S:
                info.setdefault("budget", "time budget used")
                break
            ans: dict = {}
            via = ""
            if gkey and model and not str(info["gemini"]["status"]).startswith("off"):
                waited = False
                while True:
                    try:
                        ans, via = _search(post, gkey, str(model), prompt, rows), str(model)
                        break
                    except VP.RateLimited:
                        if not waited:                     # a per-minute limit clears: wait once
                            waited = True
                            sleep(WAIT_429_S)
                            continue
                        nxt = VP._next_gemini(str(model))
                        if not nxt:
                            info["gemini"]["status"] = "off for this run: 429 on every Gemini model"
                            break
                        model, waited = nxt, False
                        info["gemini"]["model"] = nxt
                    except Exception as e:  # noqa: BLE001
                        info["gemini"]["status"] = f"partly failed: {type(e).__name__}"
                        break
            if not ans:                                # NVIDIA, then OpenRouter ":free": no search
                for name in ("nvidia", "openrouter"):
                    k = keys.get(name) or ""
                    if not k:
                        continue
                    try:
                        ans = _fallback(name, get, post, k, prompt, rows)
                        via = f"{name} (no search)"
                    except Exception as e:  # noqa: BLE001
                        info[name] = {"status": f"failed: {type(e).__name__}"}
                        ans = {}
                    if ans:
                        break
            for i, f in ans.items():
                c = clean(f, allowed)
                if c and isinstance(i, int):
                    got[i] = (c, via)
    except Exception as e:  # noqa: BLE001 — the scout must never break the run
        info["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    recs = []
    for fx in fxs:
        if fx["id"] in got:
            c, via = got[fx["id"]]
            recs.append({"tag": "scout", "sport": fx["sport"], "id": fx["id"], "fixture": fx["fixture"],
                         "home": fx.get("home"), "away": fx.get("away"), **c, "via": via})
    return {"members": info, "fixtures": recs}


def build(day: str, fxs: list[dict], **kw) -> dict:
    sport = fxs[0]["sport"] if fxs else "football"
    res = scout(fxs, **kw) if fxs else {"members": {}, "fixtures": []}
    return {"tag": "scout", "recorded_only": True, "sport": sport, "date": day,
            "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "asked": len(fxs), "members": res["members"], "fixtures": res["fixtures"]}


def run(dates: list[str], force: bool = False, ledger_dir: Path = LEDGER_DIR, out_dir: Path = OUT_DIR,
        **kw) -> list[str]:
    """Scout each date's football and NBA board. Never raises; returns the lines to print."""
    if not enabled():
        return ["scout: switched off (SCOUT_ENABLED=0)"]
    lines = []
    for d in dates:
        for sport, src, dst in (("football", f"picks_{d}.json", f"scout_{d}.json"),
                                ("nba", f"nba_{d}.json", f"scout_nba_{d}.json")):
            try:
                path = ledger_dir / src
                if not path.exists():
                    continue
                board = json.loads(path.read_text(encoding="utf-8"))
                out = out_dir / dst
                if out.exists() and not force:
                    continue                         # one scout per board per day
                fxs = football_fixtures(board) if sport == "football" else nba_fixtures(board)
                if not fxs:
                    continue
                doc = build(d, fxs, **kw)
                out_dir.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
                calls = sum(1 for f in doc["fixtures"] if f["direction"] != "none")
                lines.append(f"scout {sport} {d}: {len(doc['fixtures'])}/{doc['asked']} answered · {calls} calls")
            except Exception as e:  # noqa: BLE001
                lines.append(f"scout {sport} {d}: failed: {type(e).__name__}: {e}")
    return lines


# ---------------------------------------------------------------- grading
def outcome(sport: str, direction: str, score: str) -> Optional[bool]:
    """Did the direction's outcome happen? score = 'home-away' (football: regular time). None = can't say."""
    m = re.match(r"^(\d+)-(\d+)$", str(score or ""))
    if not m or direction == "none":
        return None
    h, a = int(m.group(1)), int(m.group(2))
    if direction == "home":
        return h > a
    if direction == "away":
        return a > h
    if sport != "football":
        return None
    return {"draw": h == a, "over": h + a > 2, "under": h + a < 3}.get(direction)


def _result_index(sport: str, day: str, ledger_dir: Path) -> dict:
    """fixture -> 'h-a' final from the graded ledger."""
    try:
        if sport == "football":
            d = json.loads((ledger_dir / f"picks_{day}.json").read_text(encoding="utf-8"))
            rows = (d.get("rated") or []) + (d.get("singles") or [])
            return {r["fixture"]: r["ft"] for r in rows if r.get("fixture") and r.get("ft")}
        d = json.loads((ledger_dir / f"nba_{day}.json").read_text(encoding="utf-8"))
        return {f"{p['home']} v {p['away']}": p["score"] for p in (d.get("picks") or []) + (d.get("picks_dropped") or [])
                if p.get("score") and p.get("stage", "regular") == "regular"}
    except (OSError, ValueError, KeyError):
        return {}


def load_record(path: Path = RECORD) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"history": []}


def grade(out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR, record_path: Path = RECORD) -> int:
    """Append each directional call that now has a result to the record once. Returns newly graded."""
    rec = load_record(record_path)
    hist = rec.setdefault("history", [])
    seen = {h["id"] for h in hist}
    added = 0
    for f in sorted(out_dir.glob("scout_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            sport, day = doc["sport"], doc["date"]
        except (OSError, ValueError, KeyError):
            continue
        results = _result_index(sport, day, ledger_dir)
        for c in doc.get("fixtures") or []:
            uid = f"{sport}|{day}|{c.get('fixture')}"
            if uid in seen or c.get("direction") in (None, "none") or c.get("confidence") is None:
                continue
            won = outcome(sport, c["direction"], results.get(c.get("fixture"), ""))
            if won is None:
                continue
            seen.add(uid)
            added += 1
            hist.append({"id": uid, "sport": sport, "date": day, "fixture": c["fixture"],
                         "direction": c["direction"], "p": c["confidence"], "won": bool(won), "via": c.get("via")})
    if added:
        rec["built_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return added


def stats(history: list[dict]) -> dict:
    n = len(history)
    if not n:
        return {"n": 0}
    eps = 1e-6
    brier = sum((h["p"] - h["won"]) ** 2 for h in history) / n
    ll = -sum(math.log(max(eps, h["p"] if h["won"] else 1 - h["p"])) for h in history) / n
    return {"n": n, "hit": sum(h["won"] for h in history) / n, "brier": brier, "logloss": ll}


def summary_line(record_path: Path = RECORD) -> str:
    """The one 'Scout' line of the daily bot report: calls made, hit rate, Brier and log-loss."""
    if not enabled():
        return "Scout: switched off"
    s = stats(load_record(record_path).get("history") or [])
    if not s["n"]:
        return "Scout: no graded calls yet (recorded only)"
    return (f"Scout (recorded only): {s['n']} graded calls, hit {s['hit']:.0%}, "
            f"Brier {s['brier']:.3f}, log-loss {s['logloss']:.3f}")
