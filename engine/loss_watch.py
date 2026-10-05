"""
LOSING-MARKET WATCH, KNOWLEDGE FILE AND PROPOSALS — standing order 39
(Architect 2026-10-05: "build the flagging for losing markets"; "make sure
everything is connected to something and has a function").

The loop, once per board run, after the day's grading:

  1. WATCH  — every graded single in the last WINDOW_DAYS is grouped by
     market segment (the learning module's market family, with handicaps split
     into underdog and favourite sides) x competition, and by segment across
     all competitions. A group that is losing money and winning less often
     than its price needs is FLAGGED.
  2. KNOW   — the day's segments, flags and the learning corrections in force
     are written to memory/knowledge.json (daily.yml commits memory/), so
     every later run, session, the weekly review and the supervisor read
     what the framework has learned instead of starting from nothing.
  3. PROPOSE — a flagged group with enough evidence becomes a PROPOSAL in
     memory/proposals.json: "stop picking <segment> in <competition>". It is
     shown on the heartbeat with its id.
  4. DECIDE — the Architect answers /approve P3 or /reject P3 on Telegram
     (output/telegram_commands.py, his chat only). Nothing is applied on the
     framework's own say-so (CLAUDE.md: rules need the Architect).
  5. APPLY  — run_daily drops every candidate in an approved block before the
     pick is chosen, exactly as order 38 does for FA Cup underdog handicaps;
     /reject on an approved block lifts it.

Only won/lost singles with a price count (HR35); nothing is guessed.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from engine import learning

MEMORY = Path(__file__).parent.parent / "memory"
KNOWLEDGE_FILE = MEMORY / "knowledge.json"
PROPOSALS_FILE = MEMORY / "proposals.json"

WINDOW_DAYS = 21
# FLAG: at least FLAG_MIN_N graded picks, down FLAG_MAX_PL units or worse at
# 1 unit each, and a hit rate under the rate its prices need to break even.
FLAG_MIN_N = 8
FLAG_MAX_PL = -2.0
# PROPOSE: a flag with more evidence — PROPOSE_MIN_N picks, down
# PROPOSE_MAX_PL units, and wins at least PROPOSE_Z standard deviations under
# the chances we stated (so it is not just short prices losing now and then).
PROPOSE_MIN_N = 12
PROPOSE_MAX_PL = -3.0
PROPOSE_Z = -1.5
REJECT_QUIET_DAYS = 14     # a rejected or lifted proposal is not raised again for 2 weeks
HISTORY_DAYS = 120


def segment(key: Optional[str]) -> str:
    """Market segment of a pick: its learning family, with handicaps split by
    side ('Asian handicap (underdog)' / 'Asian handicap (favourite)')."""
    from engine import full_markets as fm
    fam = learning.family(key)
    if key and key.startswith(("SB:14|", "SB:16|")):
        return f"{fam} ({'underdog' if fm.is_underdog_handicap(key) else 'favourite'})"
    return fam


def _rows(ledger_dir: Path, today: str) -> list[dict]:
    since = (date.fromisoformat(today) - timedelta(days=WINDOW_DAYS)).isoformat()
    out = []
    for path in sorted(Path(ledger_dir).glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not (since <= doc.get("date", "") < today):
            continue
        for s in doc.get("singles", []):
            if s.get("result") not in ("won", "lost") or not s.get("price"):
                continue
            out.append({"segment": segment(s.get("market")),
                        "league": s.get("league") or learning.league_of(s.get("fixture", "")),
                        "won": s["result"] == "won", "price": float(s["price"]),
                        "chance": float(s.get("chance_raw", s.get("chance")) or 0),
                        "day": (s.get("kickoff") or doc["date"])[:10]})
    return out


def _stats(rows: list[dict]) -> dict:
    n = len(rows)
    wins = sum(r["won"] for r in rows)
    pl = sum((r["price"] - 1) if r["won"] else -1.0 for r in rows)
    need = sum(1 / r["price"] for r in rows) / n
    exp = sum(r["chance"] for r in rows)
    sd = sum(r["chance"] * (1 - r["chance"]) for r in rows) ** 0.5
    return {"n": n, "wins": wins, "hit": round(wins / n, 3), "need": round(need, 3),
            "pl": round(pl, 2), "z": round((wins - exp) / sd, 2) if sd > 0 else 0.0,
            "days": len({r["day"] for r in rows})}


def watch(ledger_dir: Path, today: Optional[str] = None) -> dict:
    """{'segments': [...], 'flags': [...]} over the last WINDOW_DAYS."""
    today = today or date.today().isoformat()
    rows = _rows(ledger_dir, today)
    groups: dict = {}
    for r in rows:
        groups.setdefault((r["segment"], r["league"]), []).append(r)
        groups.setdefault((r["segment"], "all"), []).append(r)
    segs = []
    for (seg, lg), rs in groups.items():
        st = _stats(rs)
        st.update(segment=seg, league=lg)
        st["flag"] = (st["n"] >= FLAG_MIN_N and st["pl"] <= FLAG_MAX_PL and st["hit"] < st["need"])
        st["propose"] = (st["flag"] and st["n"] >= PROPOSE_MIN_N
                         and st["pl"] <= PROPOSE_MAX_PL and st["z"] <= PROPOSE_Z)
        segs.append(st)
    segs.sort(key=lambda s: (s["pl"], -s["n"]))
    return {"date": today, "window_days": WINDOW_DAYS, "graded": len(rows),
            "segments": segs, "flags": [s for s in segs if s["flag"]]}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_proposals(path: Optional[Path] = None) -> list[dict]:
    return _load(path or PROPOSALS_FILE, [])


def _evidence(s: dict) -> str:
    return (f"{s['wins']}/{s['n']} won ({s['hit']:.0%}; its prices need {s['need']:.0%}), "
            f"{s['pl']:+.2f} units over {s['days']} match day(s)")


def propose(w: dict, path: Optional[Path] = None) -> list[dict]:
    """Open a proposal for every proposable flag not already open, approved or
    recently rejected. Returns the proposals opened now."""
    path = path or PROPOSALS_FILE
    props = load_proposals(path)
    today = w["date"]
    quiet = (date.fromisoformat(today) - timedelta(days=REJECT_QUIET_DAYS)).isoformat()
    new = []
    for s in w["flags"]:
        if not s["propose"]:
            continue
        same = [p for p in props if p["segment"] == s["segment"] and p["league"] == s["league"]]
        if any(p["status"] in ("open", "approved") for p in same):
            for p in same:
                if p["status"] == "open":
                    p["evidence"] = _evidence(s)     # keep the evidence current
            continue
        if any(p["status"] in ("rejected", "lifted") and (p.get("decided") or "") >= quiet
               for p in same):
            continue
        where = "any competition" if s["league"] == "all" else s["league"]
        p = {"id": f"P{len(props) + 1}", "segment": s["segment"], "league": s["league"],
             "action": "block", "text": f"stop picking {s['segment']} in {where}",
             "evidence": _evidence(s), "status": "open", "opened": today, "decided": None}
        props.append(p)
        new.append(p)
    _save(path, props)
    return new


def decide(pid: str, approve: bool, today: Optional[str] = None,
           path: Optional[Path] = None) -> str:
    """The Architect's answer to a proposal. /reject on an approved block lifts it."""
    path = path or PROPOSALS_FILE
    props = load_proposals(path)
    today = today or date.today().isoformat()
    p = next((x for x in props if x["id"].lower() == pid.strip().lower()), None)
    if p is None:
        return f"No proposal {pid}. Open ones: " + (", ".join(
            x["id"] for x in props if x["status"] == "open") or "none")
    if approve:
        if p["status"] == "approved":
            return f"{p['id']} is already in force: {p['text']}."
        p["status"], p["decided"] = "approved", today
        msg = f"APPROVED {p['id']}: {p['text']}. In force from the next board."
    else:
        was = p["status"]
        p["status"], p["decided"] = ("lifted" if was == "approved" else "rejected"), today
        msg = (f"LIFTED {p['id']}: {p['segment']} is back in "
               f"{'every competition' if p['league'] == 'all' else p['league']} from the next board."
               if was == "approved" else f"REJECTED {p['id']}: {p['text']} — not applied.")
    _save(path, props)
    return msg


def blocks(path: Optional[Path] = None) -> list[tuple[str, str]]:
    """[(segment, league)] the Architect approved; league 'all' = everywhere."""
    return [(p["segment"], p["league"]) for p in load_proposals(path)
            if p.get("status") == "approved" and p.get("action") == "block"]


def blocked(key: Optional[str], league: str, blk: list[tuple[str, str]]) -> bool:
    if not blk:
        return False
    seg = segment(key)
    return any(seg == s and lg in ("all", league) for s, lg in blk)


def remember(w: dict, learned: Optional[dict] = None, path: Optional[Path] = None) -> dict:
    """Write the day's knowledge: segments, flags, learning corrections and the
    proposals' state; keep a dated history of flags and corrections."""
    path = path or KNOWLEDGE_FILE
    k = _load(path, {})
    hist = [h for h in k.get("history", []) if h.get("date") != w["date"]]
    corr = {f"{kind}:{name}": v["shift"] for kind in ("family", "league")
            for name, v in (learned or {}).get(kind, {}).items() if v.get("shift")}
    hist.append({"date": w["date"], "graded": w["graded"], "corrections": corr,
                 "flags": [f"{s['segment']} · {s['league']} · {s['pl']:+.2f}u ({s['wins']}/{s['n']})"
                           for s in w["flags"]]})
    cutoff = (date.fromisoformat(w["date"]) - timedelta(days=HISTORY_DAYS)).isoformat()
    k = {"updated": w["date"], "window_days": w["window_days"], "graded": w["graded"],
         "segments": [{x: s[x] for x in ("segment", "league", "n", "wins", "hit", "need",
                                          "pl", "z", "days", "flag")}
                      for s in w["segments"] if s["n"] >= 3],
         "learning": corr, "blocks_in_force": [list(b) for b in blocks()],
         "history": [h for h in hist if h["date"] >= cutoff]}
    _save(path, k)
    return k


def summary(w: dict, props: Optional[list] = None) -> str:
    """Heartbeat lines: flags, open proposals (with how to answer), blocks in force."""
    props = load_proposals() if props is None else props
    lines = []
    if w["flags"]:
        lines.append(f"Losing markets (last {w['window_days']} days, order 39):")
        lines += [f"  ⚠ {s['segment']} · {'all competitions' if s['league'] == 'all' else s['league']}: "
                  f"{_evidence(s)}" for s in w["flags"][:5]]
    else:
        lines.append(f"Losing markets (last {w['window_days']} days): none flagged — no market "
                     f"x competition with {FLAG_MIN_N}+ picks is down {abs(FLAG_MAX_PL):.0f}+ units "
                     f"below break-even ({w['graded']} graded).")
    opn = [p for p in props if p["status"] == "open"]
    if opn:
        lines.append("Proposals waiting for you (reply /approve ID or /reject ID):")
        lines += [f"  {p['id']}: {p['text']} — {p['evidence']}" for p in opn]
    inforce = [p for p in props if p["status"] == "approved"]
    if inforce:
        lines.append("Blocks in force: " + "; ".join(f"{p['id']} {p['text']}" for p in inforce))
    return "\n".join(lines)


CORRECTIONS_FILE = MEMORY / "corrections.csv"


def open_notes(path: Optional[Path] = None) -> list[dict]:
    """The Architect's /note corrections not yet actioned (memory/corrections.csv)."""
    import csv
    path = path or CORRECTIONS_FILE
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return [r for r in csv.DictReader(fh)
                    if (r.get("actioned") or "").strip().lower() not in ("yes", "done")]
    except OSError:
        return []


def notes_line(notes: list[dict]) -> Optional[str]:
    if not notes:
        return None
    last = notes[-1]
    return (f"Your /note corrections not yet acted on: {len(notes)} — latest "
            f"{(last.get('logged_at') or '')[:10]}: \"{(last.get('note') or '')[:80]}\" "
            f"(a session or the weekly review acts on them)")
