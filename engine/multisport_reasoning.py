"""
MULTI-SPORT REASONING + SCOUT (framework#353; config/sport_connections.json "scout_reasoning").

Every rollout sport inherits football's and the NBA's thinking step (standing order 50): ice hockey
(output/ice_hockey/ih_<date>.json) and every engine/multisport.py sport (american_football, snooker, darts,
volleyball, table_tennis, cricket, rugby, tennis, baseball: output/multisport/<sport>/ms_<date>.json).

For each sport's board, per day:

  * SCOUT (engine/scout.py, Gemini with Google Search, then the panel's free members without search): the
    board's pick fixtures, plus a few unbet games Matchbook lists, are searched for what the model cannot
    see (the sport's own team news: starting goalie, starting pitcher, quarterback, playing XI, team
    sheets, line-ups, player withdrawals and retirements). One record per fixture, written to
    output/reasoning/scout_ms_<sport>_<date>.json; engine/scout.grade() scores every directional call
    against the graded result, exactly like football's and the NBA's.
  * REASONING (engine/reasoning.py's judgement, the sport's own prompt): every pick gets a verdict
    back | lower | veto, its own chance, a confidence and the reasons, with the scout's finding for the
    fixture in its context. Written to output/reasoning/reasoning_ms_<sport>_<date>.json. A pick is
    judged once (a new pick frozen later in the day is judged on the next run); --force judges again.
  * RECORD: record() scores every verdict against its graded pick (won / lost, flat return, value
    against the exchange close, Brier of the model's chance v the reasoning's) into
    memory/ms_reasoning_record.json; summary_line() is the multi-sport reasoning line.

ADVISORY ONLY, RECORDED: nothing here drops, restakes, re-prices or adds a pick; every verdict carries
stake_factor 1.0 and "advisory": true, and no bot reads these files to size a bet. Making a verdict act
is the Architect's decision. Simulated games (SportyBet's "Simulated Reality" league) are skipped: there
is no news to find. No key, no network or a malformed answer: the pick reads PENDING (HR35), never a
made-up verdict. No steam (order 50). Kill switch: MS_REASONING=0 (the scout part also obeys SCOUT_ENABLED).
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from engine import reasoning as R
from engine import scout as SC

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "reasoning"
MS_DIR = ROOT / "output" / "multisport"
IH_DIR = ROOT / "output" / "ice_hockey"
RECORD = ROOT / "memory" / "ms_reasoning_record.json"
SPORTS = ("ice_hockey", "american_football", "snooker", "darts", "volleyball", "table_tennis",
          "cricket", "rugby", "tennis", "baseball")
LABEL = {"ice_hockey": "ice hockey", "american_football": "American football (NFL, NCAA)",
         "snooker": "snooker", "darts": "darts", "volleyball": "volleyball", "table_tennis": "table tennis",
         "cricket": "cricket", "rugby": "rugby union", "tennis": "tennis", "baseball": "baseball"}
# what "team news" means in each sport (framework#354): what the scout searches for and the judgement weighs
NEWS = {
    "ice_hockey": "the confirmed or expected STARTING GOALIE of each side (a backup in net is the biggest single "
                  "news item in hockey), skaters out injured or suspended, back-to-back games",
    "american_football": "the starting QUARTERBACK and the official injury report (Out / Doubtful / Questionable), "
                         "offensive line and top receivers out, weather for totals",
    "baseball": "the STARTING PITCHER of each side (a late scratch changes the price most), the line-up, bullpen use",
    "cricket": "the PLAYING XI (named at the toss), the toss result, pitch and weather, rain risk",
    "rugby": "the announced TEAM SHEETS (starting XV and bench), how many changes from the last match, "
             "key players rested or injured",
    "volleyball": "the expected LINE-UP, key players (opposite, outside hitters, setter) out or rested",
    "tennis": "player WITHDRAWALS, injuries, illness, retirements in the previous match, fatigue from a long "
              "previous match, surface",
    "darts": "player WITHDRAWALS, illness, form in the event so far",
    "snooker": "player WITHDRAWALS, illness, form in the event so far",
    "table_tennis": "player WITHDRAWALS, injuries, form in the event so far",
}
ROLES = ("goalie", "pitcher", "quarterback", "starter", "rotation", "player")
MAX_UNBET = int(os.getenv("MS_SCOUT_UNBET", "4"))        # unbet Matchbook-listed games scouted per sport and day
MAX_PICKS = int(os.getenv("MS_REASON_MAX", "30"))        # picks judged per sport and day (the free tier's cap)
BUDGET_S = float(os.getenv("MS_REASONING_BUDGET_S", "600"))
WINNER_MARKETS = {"186", "219", "251", "340", "406", "1"}
FAMILY = {"186": "winner", "219": "winner", "251": "winner", "340": "winner", "406": "winner (incl. OT)",
          "1": "result (regulation)", "410": "winner (regulation, no draw)", "60": "1st half result",
          "10": "double chance", "11": "draw no bet", "16": "handicap", "223": "handicap", "256": "handicap",
          "493": "frame handicap", "187": "game handicap", "188": "set handicap", "237": "point handicap",
          "14": "European handicap", "18": "total", "225": "total", "258": "total", "494": "total frames",
          "189": "total games", "238": "total points", "202": "set winner", "29": "both teams to score"}


def enabled() -> bool:
    return (os.getenv("MS_REASONING") or "1").strip().lower() not in ("0", "false", "off", "no")


# ---------------------------------------------------------------- boards
def board_path(sport: str, day: str, ms_dir: Path | None = None, ih_dir: Path | None = None) -> Path:
    if sport == "ice_hockey":
        return (ih_dir or IH_DIR) / f"ih_{day}.json"
    return (ms_dir or MS_DIR) / sport / f"ms_{day}.json"


def load_board(sport: str, day: str, ms_dir: Path | None = None, ih_dir: Path | None = None) -> dict | None:
    try:
        return json.loads(board_path(sport, day, ms_dir, ih_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def split(key: str) -> tuple[str, str, str]:
    """A side key -> (market id, specifier, outcome). Hockey keys read 'H:406||Home', the rest 'tennis:186||Home'."""
    body = str(key or "").split(":", 1)[-1]
    mid, spec, out = (body.split("|") + ["", ""])[:3]
    return mid, spec, out


def simulated(g: dict) -> bool:
    """SportyBet's virtual 'Simulated Reality' games: nothing to scout or reason about."""
    text = " ".join(str(g.get(k) or "") for k in ("country", "comp", "home", "away")).lower()
    return "simulated reality" in text or "(srl)" in text


def fixture(p: dict) -> str:
    return f"{p.get('home')} v {p.get('away')}"


def family(sport: str, key: str) -> str:
    return f"{LABEL.get(sport, sport)} {FAMILY.get(split(key)[0], 'market ' + split(key)[0])}"


def real_picks(doc: dict) -> list[dict]:
    return [p for p in doc.get("picks") or [] if not simulated(p)][:MAX_PICKS]


def pick_id(p: dict) -> str:
    return f"{p.get('sb_event_id') or p.get('event_id')}|{p.get('key')}"


# ---------------------------------------------------------------- scout
def scout_prompt(sport: str) -> str:
    """The scout's question for one rollout sport: the side to win, and the sport's own team news."""
    return SC.PROMPT_BODY.format(
        sport=LABEL.get(sport, sport), dirs="home|away|none",
        absences=', "absences": [{"player": "full name", "team": "home|away", '
                 '"role": "goalie|pitcher|quarterback|starter|rotation|player", "status": "out|doubtful"}]',
        extra=(f'Direction is the side (player or team) to win the match. Team news to look for: {NEWS[sport]}. '
               '"absences": only regular starters (or, in a one-on-one sport, the player himself) reported '
               'missing, withdrawn or doubtful for THIS match by a named source; [] if none.'))


def scout_fixtures(sport: str, doc: dict, max_unbet: int = MAX_UNBET) -> list[dict]:
    """The board's pick fixtures first, then up to max_unbet unbet games Matchbook lists (most liquid news)."""
    seen: dict[str, dict] = {}
    for p in real_picks(doc):
        fx = fixture(p)
        seen.setdefault(fx, {"fixture": fx, "home": p.get("home"), "away": p.get("away"),
                             "league": p.get("comp"), "kickoff_utc": p.get("ko"), "sport": sport, "pick": True})
    extra = 0
    for g in sorted((doc.get("games") or {}).values(), key=lambda g: str(g.get("ko"))):
        fx = fixture(g)
        if extra >= max_unbet or fx in seen or simulated(g) or not g.get("matchbook") or g.get("result"):
            continue
        seen[fx] = {"fixture": fx, "home": g.get("home"), "away": g.get("away"), "league": g.get("comp"),
                    "kickoff_utc": g.get("ko"), "sport": sport, "pick": False}
        extra += 1
    return [{**r, "id": i} for i, r in enumerate(seen.values())]


def scout_path(sport: str, day: str, out_dir: Path = OUT_DIR) -> Path:
    return out_dir / f"scout_ms_{sport}_{day}.json"


def scout_day(sport: str, day: str, doc: dict, out_dir: Path = OUT_DIR, force: bool = False, **kw) -> tuple[dict, int]:
    """Scout the fixtures of one sport's board not scouted yet (all again with force). Returns (scout doc, new)."""
    path = scout_path(sport, day, out_dir)
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = None
    have = {} if (force or not old) else {r["fixture"]: r for r in old.get("fixtures") or []}
    fxs = [f for f in scout_fixtures(sport, doc) if f["fixture"] not in have]     # unanswered ones are asked again
    fxs = [{**f, "id": i} for i, f in enumerate(fxs)]
    res: dict = {"members": (old or {}).get("members") or {}, "fixtures": []}
    if fxs and SC.enabled():
        res = SC.scout(fxs, prompt=scout_prompt(sport), allowed=SC.NBA_DIRECTIONS, roles=ROLES, **kw)
    for r in res["fixtures"]:
        have[r["fixture"]] = {**r, "pick": next((f["pick"] for f in fxs if f["fixture"] == r["fixture"]), False)}
    out = {"tag": "scout", "recorded_only": True, "sport": sport, "date": day,
           "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "asked": len(have) + len(fxs) - len(res["fixtures"]),
           "members": res["members"],
           "fixtures": [{**r, "id": i} for i, r in enumerate(have.values())]}
    if res["fixtures"] or old is None:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out, len(res["fixtures"])


# ---------------------------------------------------------------- reasoning
def prompt_for(sport: str) -> str:
    """Football's judgement prompt, re-worded for one rollout sport, and advisory."""
    p = R.PROMPT.replace("a football betting model", f"a {LABEL.get(sport, sport)} betting model")
    p = p.replace("(team news and absences in the notes, motivation,",
                  f"(the sport's team news: {NEWS[sport]}; the scout's finding in the context, motivation,")
    p = p.replace("Your verdict now sets the stake: back = full, lower = 3/4, veto = 1/2.",
                  "Your verdict is RECORDED and scored against the result; it does not set a stake yet.")
    note = (f"{LABEL.get(sport, sport).upper()} notes: model_chance is the framework's chance (\"source\" says from "
            "where: the Matchbook exchange's de-margined price, or 75% SportyBet + 25% the sport's own Elo), so it is "
            "already a market view; \"value_pts\" is how far the SportyBet price sits above it. \"scout\" is what a "
            "web search found for the fixture (unconfirmed unless it names a source); \"team_news\" is the sport's "
            "own fetched team news (starting goalie / pitcher, QB report, team sheet, XI, withdrawal) with its "
            "level. Missing facts: keep the model's view.\n\n")
    return p.replace("PICKS:\n", note + "PICKS:\n")


def family_records(sport: str, ms_dir: Path = MS_DIR, ih_dir: Path = IH_DIR) -> dict:
    """{family: {n, won, flat_return, close_value}} from the sport's graded board picks."""
    folder = ih_dir if sport == "ice_hockey" else ms_dir / sport
    pat = "ih_*.json" if sport == "ice_hockey" else "ms_*.json"
    g: dict = {}
    for f in sorted(folder.glob(pat)) if folder.exists() else []:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in doc.get("picks") or []:
            if p.get("result") not in ("won", "lost") or not p.get("price"):
                continue
            r = g.setdefault(family(sport, p.get("key") or ""), {"n": 0, "won": 0, "ret": 0.0, "cv": []})
            r["n"] += 1
            r["won"] += p["result"] == "won"
            r["ret"] += (float(p["price"]) - 1) if p["result"] == "won" else -1.0
            if p.get("clv_fair") is not None:
                r["cv"].append(float(p["clv_fair"]))
    return {k: {"n": v["n"], "won": v["won"], "flat_return": round(v["ret"] / v["n"], 4),
                "close_value": round(sum(v["cv"]) / len(v["cv"]), 4) if v["cv"] else None} for k, v in g.items()}


def say(r: dict | None) -> str:
    if not r or not r.get("n"):
        return "TOO FEW: no graded picks in this family yet"
    n, ret = r["n"], r.get("flat_return") or 0
    word = "TOO FEW" if n < 15 else ("WINNING" if ret > 0 else "LOSING")
    cv = r.get("close_value")
    return (f"{word}: the board graded {n} picks in this family, won {r['won']}, flat return {ret:+.1%}"
            + (f", value against the exchange close {cv:+.1%}" if cv is not None else ""))


def context(sport: str, picks: list[dict], scout_doc: dict | None, records: dict,
            team_news: dict | None = None) -> list[dict]:
    found = {r.get("fixture"): r for r in (scout_doc or {}).get("fixtures") or []}
    team_news = team_news or {}
    out = []
    for i, p in enumerate(picks):
        price, ch = p.get("price"), p.get("chance") if p.get("chance") is not None else p.get("fair")
        sc = found.get(fixture(p))
        fam = family(sport, p.get("key") or "")
        out.append({
            "id": i, "sport": sport, "fixture": fixture(p), "competition": p.get("comp"), "kickoff_utc": p.get("ko"),
            "pick": p.get("pick"), "price": price, "model_chance": ch, "source": p.get("source"),
            "break_even_chance": round(1 / float(price), 4) if price else None,
            "value_pts": round(100 * float(p["value"]), 1) if p.get("value") is not None else None,
            "market_chance": p.get("fair") if p.get("source") == "matchbook" else None,
            "market_family": fam, "framework_record_in_family": say(records.get(fam)), "pool": False,
            "scout": ({"finding": sc.get("finding"), "direction": sc.get("direction"),
                       "absences": sc.get("absences"), "sources": sc.get("sources")} if sc else None),
            # the sport's own team news (engine/ms_team_news.py, framework#354): fetched, recorded-only flag
            "team_news": team_news.get(pick_id(p)),
        })
    return out


def reason_path(sport: str, day: str, out_dir: Path = OUT_DIR) -> Path:
    return out_dir / f"reasoning_ms_{sport}_{day}.json"


def teaching(sport: str, rows: list[dict]) -> str:
    """The sport's own scorecard and recent mistakes, put before the picks (as football's teaching())."""
    lines = [f"YOUR RECORD ({LABEL.get(sport, sport)}, {len(rows)} graded verdicts):"]
    for v in R.VERDICTS:
        g = [r for r in rows if r["verdict"] == v]
        if g:
            won = sum(r["won"] for r in g)
            ret = sum((float(r["price"] or 0) - 1) if r["won"] else -1 for r in g) / len(g)
            lines.append(f"- {v}: {won}/{len(g)} won; flat return {ret:+.1%}")
    if not rows:
        lines.append("- nothing graded yet")
    bad = R.mistakes(rows)
    if bad:
        lines.append("YOUR RECENT MISTAKES (learn from these):")
        lines += [f"- {r['date']} {r['fixture']} {r['pick']} @{r['price']}: you said {r['verdict'].upper()} "
                  f"({str(r['reasons'])[:160]}) -> it {'WON' if r['won'] else 'LOST'}" for r in bad]
    return "\n".join(lines) + "\n\n"


def _clean(a: dict | None) -> dict:
    c = R._clean(a)
    c["stake_factor"] = 1.0                        # ADVISORY: a multi-sport verdict never sizes a bet
    c.pop("advised_stake_factor", None)
    return c


def reason_day(sport: str, day: str, doc: dict, scout_doc: dict | None = None, out_dir: Path = OUT_DIR,
               force: bool = False, key: str | None = None, get: Callable | None = None,
               post: Callable | None = None, now: datetime | None = None,
               ms_dir: Path = MS_DIR, ih_dir: Path = IH_DIR) -> tuple[dict, int]:
    """Judge the picks of one sport's board not judged yet (a PENDING one is asked again). Returns (doc, new)."""
    now = now or datetime.now(UTC)
    path = reason_path(sport, day, out_dir)
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = None
    prompt = prompt_for(sport)
    same_prompt = bool(old) and old.get("prompt_version") == R.prompt_version(prompt)
    done = {} if (force or not old or not same_prompt) else \
        {x["id"]: x for x in old.get("picks") or [] if x.get("verdict") in R.VERDICTS}
    picks = real_picks(doc)
    todo = [p for p in picks if pick_id(p) not in done]
    from engine import ms_team_news as TN  # inside: ms_team_news imports this module
    rows = context(sport, todo, scout_doc, family_records(sport, ms_dir, ih_dir), TN.lines_for_context(sport, day))
    answers: dict = {}
    note = None
    model = None
    if todo:
        key = key if key is not None else os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            note = "NO DATA — PENDING: GEMINI_API_KEY not set"
        else:
            import requests  # type: ignore[import-untyped]
            get, post = get or requests.get, post or requests.post
            chain = R.model_chain(get, key)
            if not chain:
                note = "NO DATA — PENDING: no Gemini model on this key"
            full = teaching(sport, graded(sport, out_dir, ms_dir, ih_dir)) + prompt
            for i in range(0, len(rows), R.BATCH) if chain else ():
                err: Exception | None = None
                for m in chain:
                    try:
                        answers.update(R._ask(post, key, m, rows[i:i + R.BATCH], prompt=full))
                        model, err = m, None
                        break
                    except Exception as e:  # noqa: BLE001 — the next model, else these picks stay PENDING
                        err = e
                if err is not None:
                    note = f"PARTLY PENDING: {type(err).__name__}: {str(err)[:160]}"
    new = 0
    slot = {pick_id(t): r["id"] for r, t in zip(rows, todo, strict=True)}
    out_picks = []
    for p in picks:
        pid = pick_id(p)
        if pid in done:
            out_picks.append(done[pid])
            continue
        j = slot.get(pid)
        c = _clean(answers.get(j)) if j is not None else _clean(None)
        new += c["verdict"] in R.VERDICTS
        x = {"id": pid, "fixture": fixture(p), "market": p.get("key"), "pick": p.get("pick"), "price": p.get("price"),
             "model_chance": p.get("chance") if p.get("chance") is not None else p.get("fair"),
             "code": p.get("code"), "judged_at": now.isoformat(timespec="seconds"), **c}
        if p.get("source") == "matchbook":
            a = R.anchored_chance(x.get("ai_chance"), p.get("fair"))
            if a is not None and p.get("price"):
                x.update(market_chance=p.get("fair"), anchored_chance=a, anchored_edge=round(a - 1 / float(p["price"]), 4))
        out_picks.append(x)
    out = {"tag": "reasoning", "sport": sport, "date": day, "advisory": True,
           "acts_on": "nothing: recorded and scored only (Architect decides if it ever sizes a stake)",
           "run_at": now.isoformat(timespec="seconds"), "prompt_version": R.prompt_version(prompt),
           "model": model or (old or {}).get("model"), "note": note, "picks": out_picks}
    if todo or old is None or force:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out, new


# ---------------------------------------------------------------- the record
def graded(sport: str, out_dir: Path = OUT_DIR, ms_dir: Path = MS_DIR, ih_dir: Path = IH_DIR) -> list[dict]:
    """Every verdict of one sport with its graded pick, oldest first."""
    rows = []
    for f in sorted(out_dir.glob(f"reasoning_ms_{sport}_*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        doc = load_board(sport, str(r.get("date")), ms_dir, ih_dir) or {}
        by = {pick_id(p): p for p in doc.get("picks") or []}
        for x in r.get("picks") or []:
            p = by.get(x.get("id")) or {}
            if x.get("verdict") not in R.VERDICTS or p.get("result") not in ("won", "lost"):
                continue
            rows.append({"date": r.get("date"), "fixture": x.get("fixture"), "pick": x.get("pick"),
                         "price": x.get("price"), "verdict": x["verdict"], "model_chance": x.get("model_chance"),
                         "ai_chance": x.get("ai_chance"), "reasons": x.get("reasons") or "",
                         "clv_fair": p.get("clv_fair"), "won": p["result"] == "won"})
    return rows


def record(out_dir: Path = OUT_DIR, ms_dir: Path = MS_DIR, ih_dir: Path = IH_DIR) -> dict:
    """Per sport and verdict: graded n, won, flat return, value against the exchange close; Brier model v AI."""
    sports: dict = {}
    for sport in SPORTS:
        rows = graded(sport, out_dir, ms_dir, ih_dir)
        by: dict = {}
        for v in R.VERDICTS:
            g = [r for r in rows if r["verdict"] == v]
            by[v] = {"n": len(g)}
            if g:
                by[v].update(won=sum(r["won"] for r in g),
                             flat_return=round(sum((float(r["price"] or 0) - 1) if r["won"] else -1 for r in g) / len(g), 4))
                cv = [float(r["clv_fair"]) for r in g if r.get("clv_fair") is not None]
                if cv:
                    by[v]["close_value"] = round(sum(cv) / len(cv), 4)
        sc = [r for r in rows if r.get("model_chance") is not None and r.get("ai_chance") is not None]
        brier: dict = {"n": len(sc)}
        if sc:
            brier["model"] = round(sum((float(r["model_chance"]) - r["won"]) ** 2 for r in sc) / len(sc), 4)
            brier["ai"] = round(sum((float(r["ai_chance"]) - r["won"]) ** 2 for r in sc) / len(sc), 4)
        sports[sport] = {"graded": len(rows), "by_verdict": by, "brier": brier}
    return {"updated": datetime.now(UTC).date().isoformat(), "advisory": True, "sports": sports}


def summary_line(rec: dict) -> str:
    parts = []
    for sport, s in (rec.get("sports") or {}).items():
        if not s.get("graded"):
            continue
        b = s["by_verdict"]
        parts.append(f"{sport} " + ", ".join(f"{v} {b[v]['won']}/{b[v]['n']}" for v in R.VERDICTS if b[v]["n"]))
    return ("Multi-sport reasoning (advisory, recorded): "
            + (" · ".join(parts) if parts else "nothing graded yet"))


# ---------------------------------------------------------------- the run
def run(dates: list[str], force: bool = False, out_dir: Path = OUT_DIR, ms_dir: Path = MS_DIR,
        ih_dir: Path = IH_DIR, clock: Callable = time.monotonic, **kw) -> list[str]:
    """Scout, then reason over, every rollout sport's board for each date. Never raises; returns lines."""
    if not enabled():
        return ["multi-sport reasoning: switched off (MS_REASONING=0)"]
    lines = []
    t0 = clock()
    for d in dates:
        for sport in SPORTS:
            if clock() - t0 > BUDGET_S:
                lines.append(f"multi-sport reasoning: time budget used, {sport} {d} and later wait for the next run")
                return lines
            try:
                doc = load_board(sport, d, ms_dir, ih_dir)
                if not doc:
                    continue
                scout_kw = {k: v for k, v in kw.items() if k in ("keys", "get", "post", "clock", "sleep")}
                sdoc, ns = scout_day(sport, d, doc, out_dir, force, **scout_kw)
                if not real_picks(doc):
                    lines.append(f"{sport} {d}: no picks · scout {ns} new findings")
                    continue
                reason_kw = {k: v for k, v in kw.items() if k in ("key", "get", "post", "now")}
                rdoc, nr = reason_day(sport, d, doc, sdoc, out_dir, force, ms_dir=ms_dir, ih_dir=ih_dir, **reason_kw)
                counts = {v: sum(1 for p in rdoc["picks"] if p["verdict"] == v) for v in (*R.VERDICTS, "PENDING")}
                lines.append(f"{sport} {d}: {len(rdoc['picks'])} picks, {nr} judged now · {counts} · scout {ns} new"
                             + (f" · {rdoc['note']}" if rdoc.get("note") else ""))
            except Exception as e:  # noqa: BLE001 — one sport failing never stops the others
                lines.append(f"{sport} {d}: reasoning failed: {type(e).__name__}: {str(e)[:120]}")
    return lines
