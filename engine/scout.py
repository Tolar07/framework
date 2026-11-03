"""
SCOUT — a daily section of the reasoning step (Architect 2026-11-03).
Nothing here selects, stakes, drops, re-prices or moves a chance, a verdict, a threshold or the CLV gate.
If the scout fails or finds nothing, the reasoning step goes on exactly as before.

HOW IT CAN AFFECT PICKS (Architect 2026-11-03: "if the scout sees a news ... it should be able to affect the
picks", e.g. a first-choice goalkeeper out -> more goals, both teams to score): each starter the scout reports
OUT is checked against FotMob's team news; only a CONFIRMED absence counts. pick_effect() signs it on every
pick (+1 helps, -1 hurts: a goalkeeper or defender out lifts goals and weakens his side, a forward out lowers
goals and weakens his side). The experiment engine (order 45) scores "no pick / leg a confirmed scout absence
hurts" in shadow (S10, A8, T8); it changes the board only if it beats the live rule on CLV AND return over
100+ graded bets, like every other strategy. Unconfirmed findings never move anything.

For every football fixture on the day's board (and the NBA board's games) Gemini, with Google Search,
looks for what the model cannot see: confirmed team news and injuries, line-ups, late line moves and
notable chatter on X. One record per fixture:

    {"tag": "scout", "sport", "id", "fixture", "finding", "direction", "confidence", "sources": [urls], "via"}

direction: home | away | draw | over | under | none (over/under = 2.5 goals, football only).
confidence: the probability that the direction's outcome happens (0 < p < 1); none -> null.
If Gemini is off (no key / 429 on every model) the panel's free NVIDIA then OpenRouter ":free" members
answer from the framework's own data, with no search (via says which; sources stay empty).

Saved to output/reasoning/scout_<date>.json (and scout_nba_<date>.json), beside the verdicts. Re-searched once per
board (evening + morning refresh); in between, absences are re-checked against FotMob without a search.
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
"confidence": <probability 0-1 that the direction's outcome happens, null if none>, "sources": ["https://..."]{absences}}}]}}
{extra}
FIXTURES:
"""
PROMPT_FOOTBALL = PROMPT_BODY.format(
    sport="football", dirs="home|away|draw|over|under|none",
    absences=', "absences": [{"player": "full name", "team": "home|away", '
             '"role": "goalkeeper|defender|midfielder|forward", "status": "out|doubtful"}]',
    extra='"over"/"under" mean 2.5 goals in regular time. "absences": only REGULAR STARTERS reported missing for this '
          'match by a named source; [] if none.')
PROMPT_NBA = PROMPT_BODY.format(sport="NBA", dirs="home|away|none", absences="",
                                extra='Direction is the side to win the game (overtime counts).')
ROLES = ("goalkeeper", "defender", "midfielder", "forward")


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
    absences = []
    for x in (row.get("absences") or [])[:8] if isinstance(row.get("absences"), list) else []:
        if not isinstance(x, dict):
            continue
        team, role = str(x.get("team") or "").lower(), str(x.get("role") or "").lower()
        status, name = str(x.get("status") or "").lower(), str(x.get("player") or "").strip()
        if team in ("home", "away") and role in ROLES and status in ("out", "doubtful") and len(name) > 2:
            absences.append({"player": name[:60], "team": team, "role": role, "status": status,
                             "confirmed_by": None})
    srcs = [str(u)[:300] for u in (row.get("sources") or []) if isinstance(u, str) and u.startswith("http")][:5]
    return {"finding": str(row.get("finding") or "")[:400], "direction": d,
            "confidence": None if conf is None else round(conf, 3), "sources": srcs, "absences": absences}


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


def build(day: str, fxs: list[dict], board_at: Optional[str] = None, **kw) -> dict:
    sport = fxs[0]["sport"] if fxs else "football"
    res = scout(fxs, **kw) if fxs else {"members": {}, "fixtures": []}
    return {"tag": "scout", "recorded_only": True, "sport": sport, "date": day, "picks_generated_at": board_at,
            "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "asked": len(fxs), "members": res["members"], "fixtures": res["fixtures"]}


def run(dates: list[str], force: bool = False, ledger_dir: Path = LEDGER_DIR, out_dir: Path = OUT_DIR,
        news_folder: Optional[Path] = None, fm=None, **kw) -> list[str]:
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
                before = out.read_text(encoding="utf-8") if out.exists() else ""
                old = json.loads(before) if before else None
                fresh = old is None or force or old.get("picks_generated_at") != board.get("generated_at")
                if fresh:                           # one web search per board (evening + morning refresh)
                    fxs = football_fixtures(board) if sport == "football" else nba_fixtures(board)
                    if not fxs:
                        continue
                    doc = build(d, fxs, board_at=board.get("generated_at"), **kw)
                else:
                    doc = dict(old or {})
                if sport == "football":             # FotMob's team news, as it stands now, confirms absences
                    from engine import fact_sheet as FS
                    news = dict(FS.load_news(d, news_folder or FS.NEWS_DIR))
                    for fx, fresh_news in fotmob_news(board, doc, fm).items():
                        news[fx] = {**(news.get(fx) or {}), "absent": fresh_news["absent"]}
                    n_conf = confirm_doc(doc, news)
                else:
                    n_conf = 0
                if not fresh and json.dumps(doc, indent=1, ensure_ascii=False) == before:
                    continue                        # nothing new: no write, no line
                out_dir.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
                calls = sum(1 for f in doc["fixtures"] if f["direction"] != "none")
                lines.append(f"scout {sport} {d}: {len(doc['fixtures'])}/{doc['asked']} answered · {calls} calls"
                             + (f" · {n_conf} absences confirmed by FotMob" if sport == "football" else "")
                             + ("" if fresh else " (re-checked, no new search)"))
            except Exception as e:  # noqa: BLE001
                lines.append(f"scout {sport} {d}: failed: {type(e).__name__}: {e}")
    return lines


# ---------------------------------------------------------------- confirmation and effects
# A scout absence moves anything only when a SECOND source agrees: FotMob's team news (captured by the
# pre-kickoff loop into data/features/news_<date>.json) lists the same player out for the same side.
# A web-only claim stays in the record and moves nothing (HR59: one model's claim is not evidence).
def _norm(name: str) -> list[str]:
    import unicodedata
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return [w for w in re.split(r"[^a-z]+", t) if w]


def same_player(a: str, b: str) -> bool:
    """Same surname, and the first names (or initials) don't clash. 'T. Courtois' = 'Thibaut Courtois'."""
    x, y = _norm(a), _norm(b)
    if not x or not y or x[-1] != y[-1] or len(x[-1]) < 3:
        return len(x) == 1 and len(y) == 1 and x == y and len(x[0]) >= 4   # one-name players (Vinicius)
    if len(x) == 1 or len(y) == 1:
        return True
    return x[0][0] == y[0][0]


def _stamp(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _t(iso: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def confirm(rec: dict, news: dict, now: Optional[datetime] = None) -> int:
    """Mark each scout absence FotMob also lists as out for that side, with the time it was first confirmed
    (a board only counts confirmations made before it was built). Returns how many are confirmed now."""
    fm = (news or {}).get(rec.get("fixture")) or {}
    out = [(str(a.get("name") or ""), a.get("side")) for a in fm.get("absent") or []]
    n = 0
    for ab in rec.get("absences") or []:
        hit = any(side == ab["team"] and same_player(name, ab["player"]) for name, side in out)
        if hit and ab.get("status") == "out":
            if not ab.get("confirmed_by"):
                ab["confirmed_by"], ab["confirmed_at"] = "FotMob", _stamp(now)
            n += 1
        elif ab.get("confirmed_by") and not hit and fm:
            ab["confirmed_by"] = ab["confirmed_at"] = None    # FotMob no longer lists him: he is back
    return n


def fotmob_news(board: dict, doc: dict, fm=None) -> dict:
    """{fixture: {"absent": [...]}} straight from FotMob for each board single the scout reported a starter
    missing in, with FotMob's FULL missing list (the pre-kickoff loop's file keeps only 3 a side and is
    first written around midday, after the morning board). Only fixtures with absences: a few calls a run."""
    want = {r["fixture"] for r in doc.get("fixtures") or [] if r.get("absences")}
    ids = {s.get("fixture"): s.get("fotmob_id") for s in board.get("singles") or [] if s.get("fotmob_id")}
    if not want or not ids:
        return {}
    if fm is None:
        from data import fotmob as fm
    got: dict = {}
    for fx in sorted(want & set(ids)):
        try:
            tn = fm.team_news(ids[fx]) or {}
        except Exception:  # noqa: BLE001 — FotMob down: the captured file still counts
            continue
        absent = [{"name": m.get("name"), "side": side, "type": m.get("type")}
                  for side in ("home", "away") for m in (tn.get(side) or {}).get("missing") or []]
        if tn:
            got[fx] = {"absent": absent}
    return got


def confirm_doc(doc: dict, news: dict) -> int:
    return sum(confirm(r, news) for r in doc.get("fixtures") or [])


# What a confirmed absence does to the match, per side: (goals in the match, that side's result).
# A goalkeeper or a defender out: more goals (both teams to score, overs) and his side weaker.
# A forward out: fewer goals from his side and his side weaker. A midfielder: his side weaker.
ROLE_EFFECT = {"goalkeeper": (+1, -1), "defender": (+1, -1), "forward": (-1, -1), "midfielder": (0, -1)}


def _market_lean(key: str) -> tuple[int, int, int]:
    """A pick key -> how it leans: (on more goals, on the home side, on the away side), each -1/0/+1."""
    k = str(key or "")
    if not k.startswith("SB:"):
        up = k.upper()
        return (+1 if up.startswith("OVER") else -1 if up.startswith("UNDER") else 0,
                +1 if up.startswith("HOME") else 0, +1 if up.startswith("AWAY") else 0)
    mid, _spec, out = (k[3:].split("|") + ["", ""])[:3]
    o = out.lower()
    goals = +1 if " over " in f" {o}" or o.startswith("over") else -1 if "under" in o else 0
    home = away = 0
    if mid in ("1", "11", "12", "13", "14", "16", "37"):          # result / handicap / result & total
        side = o.split(" ")[0].split("/")[0]
        home, away = (+1, -1) if side == "home" else (-1, +1) if side == "away" else (0, 0)
    elif mid in ("10", "547", "546"):                             # double chance: X or Y
        dc = o.split(" & ")[0]
        if dc in ("home or draw", "home/draw"):
            away = -1
        elif dc in ("draw or away", "draw/away"):
            home = -1
    elif mid == "29":                                             # BTTS
        goals = +1 if o == "yes" else -1 if o == "no" else 0
    elif mid in ("33", "34"):                                     # win to nil: that side wins, the other blank
        yes = +1 if o == "yes" else -1 if o == "no" else 0
        goals = -yes
        home, away = ((yes, -yes) if mid == "33" else (-yes, yes))
    elif mid in ("31", "32"):                                     # clean sheet
        yes = +1 if o == "yes" else -1 if o == "no" else 0
        goals = -yes
    elif mid == "19":                                             # home team goals: home attack v away defence
        return (goals, 0, 0) if goals else (0, 0, 0)
    elif mid == "20":
        return (goals, 0, 0) if goals else (0, 0, 0)
    return goals, home, away


def pick_effect(market: str, absences: list[dict], before: Optional[str] = None) -> int:
    """+1 a confirmed absence helps the pick, -1 it hurts it, 0 neither / mixed / nothing confirmed.
    before: count only confirmations made by then (a board's generated_at), so the shadow is scored on what
    the board could have known."""
    cut = _t(before)
    lean_g, lean_h, lean_a = _market_lean(market)
    mid = str(market or "")[3:].split("|")[0] if str(market or "").startswith("SB:") else ""
    score = 0
    for ab in absences or []:
        if not ab.get("confirmed_by"):
            continue
        at = _t(ab.get("confirmed_at"))
        if cut is not None and (at is None or at > cut):
            continue
        g, side = ROLE_EFFECT.get(str(ab.get("role")), (0, 0))
        if mid in ("19", "20"):                    # a team total: only that team's attack / the other's defence
            mine = "home" if mid == "19" else "away"
            if ab["team"] == mine:
                g = -1 if ab["role"] == "forward" else 0
            else:
                g = +1 if ab["role"] in ("goalkeeper", "defender") else 0
        on_home = side if ab["team"] == "home" else -side
        score += g * lean_g + on_home * lean_h - on_home * lean_a
    return (score > 0) - (score < 0)


_EFFECTS: dict = {}


def effects_for(day: Optional[str], out_dir: Optional[Path] = None) -> dict:
    """{fixture: [absences]} from the day's saved scout (cached per run). {} when off or none yet."""
    if not day or not enabled():
        return {}
    folder = out_dir or OUT_DIR
    key = (str(folder), day)
    if key not in _EFFECTS:
        try:
            doc = json.loads((folder / f"scout_{day}.json").read_text(encoding="utf-8"))
            _EFFECTS[key] = {r["fixture"]: r.get("absences") or [] for r in doc.get("fixtures") or []}
        except (OSError, ValueError, KeyError):
            _EFFECTS[key] = {}
    return _EFFECTS[key]


def single_effect(s: dict, out_dir: Optional[Path] = None, before: Optional[str] = None) -> int:
    """The scout's confirmed effect on one ledger single (fixture, market, kickoff date). Never raises."""
    try:
        return pick_effect(s.get("market") or "", effects_for(s.get("kickoff"), out_dir).get(s.get("fixture")) or [],
                           before)
    except Exception:  # noqa: BLE001
        return 0


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
