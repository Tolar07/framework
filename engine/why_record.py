"""
WHY RECORD (Architect 2026-10-28: learning must capture WHY a pick won or
lost — "outplayed v unlucky v the game changed" — not only THAT a market
misleads).

RECORD ONLY. Nothing here selects, stakes or moves a chance. Every graded
single on the picks ledger (output/picks/picks_<date>.json) is set against the
match as studied from FotMob (data/match_study — xG, shots, red cards, game
state) and given one class:

  RIGHT-WON      won, and the chances backed it (xG gave the pick >= 50%)
  LUCKY-WON      won, but the chances did not (xG gave it < 50%)
  RIGHT-UNLUCKY  lost, but the chances backed it (our side won the xG /
                 the xG total was on our side of the line)
  OUTPLAYED      lost, and the chances were against it: the model was wrong
  GAME-CHANGED   lost after the game changed under it: a red card for the
                 side we needed (any red for a goals pick) before the 80th
                 minute, an early goal against the run of play (our side
                 behind for 60+ minutes after creating as much before it), or
                 a lineup flag (CAUTION / RISK) on the pick at kick-off
  UNCLASSED      the match was not studied, the market is not settled on
                 goals (corners, cards, first half), or no xG -> PENDING,
                 never guessed (HR35)

"The chances backed it" is the pick's win probability on a Poisson grid
built from the two sides' ACTUAL xG — the result the chances deserved,
settled with the same rule as the ledger (engine/picks_ledger._settle). A
pick whose market the grid cannot settle the same way as the real score is
UNCLASSED rather than misread.

Output: memory/why_record.jsonl (rebuilt in full from the ledger each run, so
a late-studied match or a re-graded pick is picked up) and summary_lines()
for the daily scorecard. engine/learning.py reads it only through the
SHADOW strategy "why-weighted learning" (weights OUTPLAYED misses over
UNLUCKY ones), which must earn promotion like any other strategy.

    python -m engine.why_record            # rebuild + print the last day
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
LEDGER_DIR = ROOT / "output" / "picks"
STUDY_DIR = ROOT / "data" / "match_study"
RECORD = ROOT / "memory" / "why_record.jsonl"

CLASSES = ("RIGHT-WON", "LUCKY-WON", "RIGHT-UNLUCKY", "OUTPLAYED", "GAME-CHANGED", "UNCLASSED")
RED_BEFORE = 80          # a red after this barely changes a game
EARLY_TRAIL_MIN = 60     # behind for 60+ min = went behind by ~the 30th minute
MAX_GOALS = 10


def _pois(lam: float) -> list[float]:
    lam = max(lam, 0.01)
    p = [math.exp(-lam)]
    for k in range(1, MAX_GOALS + 1):
        p.append(p[-1] * lam / k)
    return p


def deserved(market: str, xg_h: float, xg_a: float) -> float | None:
    """The pick's chance of winning had the goals followed the xG: P(win) /
    P(win or lose) on the Poisson grid (pushes left out). None when the market
    cannot be settled on a full-time score."""
    from engine.picks_ledger import _settle
    ph, pa = _pois(xg_h), _pois(xg_a)
    win = lose = 0.0
    for i, a in enumerate(ph):
        for j, b in enumerate(pa):
            r = _settle(market, i, j)
            if r == "unknown":
                return None
            if r == "won":
                win += a * b
            elif r == "lost":
                lose += a * b
    return win / (win + lose) if win + lose > 0 else None


def _side(market: str, xg_h: float, xg_a: float) -> str | None:
    """Which side the pick needs: 'home' / 'away', or None for a goals pick
    that both sides' chances feed the same way (or neither)."""
    up_h = deserved(market, xg_h + 0.5, xg_a)
    up_a = deserved(market, xg_h, xg_a + 0.5)
    if up_h is None or up_a is None:
        return None
    if (up_h - up_a) > 0.05 and not (up_a > (deserved(market, xg_h, xg_a) or 0) + 0.02):
        return "home"
    if (up_a - up_h) > 0.05 and not (up_h > (deserved(market, xg_h, xg_a) or 0) + 0.02):
        return "away"
    return None


def load_study(folder: Path = STUDY_DIR) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(folder.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[str(r["fotmob_id"])] = r
    return out


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _find(single: dict, study: dict[str, dict], by_day: dict) -> dict | None:
    fid = single.get("fotmob_id")
    if fid is not None and str(fid) in study:
        return study[str(fid)]
    try:
        from engine.name_match import same_club
    except Exception:  # noqa: BLE001
        same_club = None  # type: ignore[assignment]
    for r in by_day.get((single.get("kickoff") or "")[:10], []):
        hn, an = r["home"]["name"], r["away"]["name"]
        if same_club:
            if same_club(hn, single.get("home", "")) and same_club(an, single.get("away", "")):
                return r
        elif _norm(hn) == _norm(single.get("home", "")) and _norm(an) == _norm(single.get("away", "")):
            return r
    return None


def classify(single: dict, row: dict | None) -> dict:
    """One why-record row for a graded single."""
    res = single.get("result")
    out = {"date": None, "fixture": single.get("fixture"), "league": single.get("league"),
           "market": single.get("market"), "pick": single.get("pick"), "price": single.get("price"),
           "chance": single.get("chance"), "result": res, "ft": single.get("ft"),
           "class": "UNCLASSED", "deserved": None, "side": None, "evidence": []}
    ev = out["evidence"]
    if row is None:
        ev.append("match not studied (FotMob) — PENDING")
        return out
    h, a = row["home"], row["away"]
    xh, xa = h.get("xg"), a.get("xg")
    out["fotmob_id"] = str(row["fotmob_id"])
    if xh is None or xa is None:
        ev.append("no xG for this match — PENDING")
        return out
    market = single.get("market") or ""
    from engine import half
    from engine.picks_ledger import _settle
    if half.is_first_half(market):
        ev.append("first-half market: full-match xG does not settle it")
        return out
    if h.get("goals") is not None and a.get("goals") is not None:
        if _settle(market, int(h["goals"]), int(a["goals"])) != res:
            ev.append("market not settled on goals (corners / cards / player) — xG can't judge it")
            return out
    d = deserved(market, xh, xa)
    if d is None:
        ev.append("market not settled on goals — xG can't judge it")
        return out
    side = _side(market, xh, xa)
    out["deserved"], out["side"] = round(d, 3), side
    hn, an = h.get("name", "home"), a.get("name", "away")
    ev.append(f"xG {hn} {xh:.2f} v {an} {xa:.2f} (score {h.get('goals')}-{a.get('goals')}): "
              f"the chances gave the pick {100 * d:.0f}%")
    if h.get("shots") is not None and a.get("shots") is not None:
        ev.append(f"shots {h['shots']:.0f}-{a['shots']:.0f}, on target {h.get('sot') or 0:.0f}-{a.get('sot') or 0:.0f}"
                  + (f", big chances {h.get('big_chances') or 0:.0f}-{a.get('big_chances') or 0:.0f}"
                     if h.get("big_chances") is not None else ""))
    if res == "won":
        out["class"] = "RIGHT-WON" if d >= 0.5 else "LUCKY-WON"
        return out
    if res != "lost":
        ev.append(f"result {res} — not judged")
        return out

    changed = []
    for s_key, team, opp in (("home", h, a), ("away", a, h)):
        reds = [m for m in (team.get("reds") or []) if m is not None and m < RED_BEFORE]
        if reds and (side is None or side == s_key):
            changed.append(f"red card for {team.get('name')} at {reds[0]:.0f}'")
        st = (team.get("state") or {})
        trail = (st.get("trailing") or {}).get("min") or 0
        lvl = st.get("level") or {}
        if side == s_key and trail >= EARLY_TRAIL_MIN:
            even = (lvl.get("min") or 0) < 15 or (lvl.get("xg_for") or 0) >= (lvl.get("xg_against") or 0)
            if even:
                changed.append(f"{team.get('name')} went behind early (behind {trail:.0f} min) "
                               f"against the run of play")
    lc = (single.get("lineup_check") or {}).get("level")
    if lc in ("CAUTION", "RISK"):
        changed.append(f"lineup flag {lc} at kick-off: {(single.get('lineup_check') or {}).get('note', '')[:80]}")
    if changed:
        out["class"] = "GAME-CHANGED"
        ev.extend(changed)
    elif d >= 0.5:
        out["class"] = "RIGHT-UNLUCKY"
    else:
        out["class"] = "OUTPLAYED"
    return out


def build(ledger_dir: Path = LEDGER_DIR, study_dir: Path = STUDY_DIR,
          path: Path | None = RECORD) -> list[dict]:
    """Every graded single on the ledger, classed. Writes `path` (full rebuild)."""
    study = load_study(study_dir)
    by_day: dict[str, list[dict]] = {}
    for r in study.values():
        by_day.setdefault(r["ko"][:10], []).append(r)
    rows = []
    for f in sorted(ledger_dir.glob("picks_*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for s in doc.get("singles", []):
            if s.get("result") not in ("won", "lost"):
                continue
            row = classify(s, _find(s, study, by_day))
            row["date"] = doc.get("date")
            rows.append(row)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
                                for r in rows), encoding="utf-8")
    return rows


def load(path: Path = RECORD) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def summary_lines(rows: list[dict] | None = None, day: str | None = None, max_lines: int = 6) -> list[str]:
    """Daily-debrief block: the latest graded day by class, then each loss with
    its first evidence line."""
    rows = load() if rows is None else rows
    if not rows:
        return []
    day = day or max(r["date"] for r in rows if r.get("date"))
    today = [r for r in rows if r.get("date") == day]
    if not today:
        return []
    c = Counter(r["class"] for r in today)
    L = [f"🔎 WHY ({day}, record only): " + " · ".join(f"{c[k]} {k.lower()}" for k in CLASSES if c[k])]
    losses = [r for r in today if r["result"] == "lost" and r["class"] != "UNCLASSED"]
    for r in losses[:max_lines]:
        why = next((e for e in r["evidence"][1:] if "red card" in e or "behind" in e or "lineup" in e), None)
        first = r["evidence"][0] if r["evidence"] else ""
        L.append(f"  {r['class']}: {r['fixture']} — {r['pick']} · {why or first}")
    if len(losses) > max_lines:
        L.append(f"  … {len(losses) - max_lines} more in memory/why_record.jsonl")
    last30 = [r for r in rows if r["class"] in ("RIGHT-UNLUCKY", "OUTPLAYED")]
    if last30:
        un = sum(r["class"] == "RIGHT-UNLUCKY" for r in last30)
        L.append(f"  All judged losses so far: {len(last30) - un} outplayed v {un} unlucky")
    return L


if __name__ == "__main__":
    rows = build()
    print(f"why record: {len(rows)} graded single(s); "
          + ", ".join(f"{k} {v}" for k, v in Counter(r['class'] for r in rows).most_common()))
    print("\n".join(summary_lines(rows)))
