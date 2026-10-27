"""
NIGHTLY MATCH STUDY + LESSONS (Architect 2026-10-26: "the framework needs to
study each match. The ones that we bet and the one that we do not bet ...
understand the profile, understand why, what happened").

Every studied match (data/match_study — every match of the covered
competitions) is replayed walk-forward: the profiles AS THEY STOOD BEFORE it
(engine/tactics.build_profiles(as_of=kickoff)) give the matchup read, and the
match is set against it:

  * what the read expected (each side's xG, BTTS, Over 2.5, the tags in play)
  * what happened (score, xG, how the chances came: open play / counter /
    set piece / penalty, formations used)
  * why it differed: red card, early goal (game state), finishing above or
    below the chances, a counter or set-piece game, a formation the profile
    hadn't seen.

LESSONS (memory/tactics_lessons.json). A tag ("counter side v high line",
"formation 3-5-2 v 4-3-3" ...) is a CANDIDATE when the attacking side's xG
beat (or fell short of) the read by 2+ standard errors over 20+ sides up to
the day it was written. It is PROVEN only when the matches played AFTER it
was written — ones it had not seen — show the same direction at z >= 1.645
over 20+ sides. Only proven lessons move the read (half the measured effect,
capped at +/-0.30 xG). A proven lesson whose later matches turn against it
is RETIRED.

WEIGHT (data/tactics/calibration.json): how far the board's chance moves
toward the matchup's. Fitted on graded matches that had SportyBet prices
(the universe sweep's last price, margin removed): the w that minimises the
Brier score of price + w x (matchup - price) for BTTS, Over 1.5 / 2.5 and
each team to score. Kept only when it is above 0 by 1.645 standard errors
(bootstrap); otherwise 0 and the read is a label. Capped at 0.5.
"""
from __future__ import annotations

import gzip
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from engine import tactics as tx

ROOT = Path(__file__).parent.parent
STUDY_LOG = ROOT / "memory" / "match_study_log.jsonl"
UNIVERSE = ROOT / "data" / "universe"
REPORT = ROOT / "backtest" / "TACTICS_STUDY.md"

MIN_SIDES = 20
Z_CANDIDATE = 2.0
Z_PROVEN = 1.645
EFFECT_SHRINK = 0.5
EFFECT_CAP = 0.30
WEIGHT_CAP = 0.5


def _strength() -> dict:
    try:
        from data import league_strength as ls
        return ls.load()
    except Exception:  # noqa: BLE001
        return {}


def walk_forward(rows: list[dict], start: str, end: Optional[str] = None, step_days: int = 7,
                 effects: Optional[dict] = None, strength: Optional[dict] = None) -> list[dict]:
    """Each match from `start` read from the profiles of the matches before its
    week (rebuilt weekly — a match never sees itself or anything after)."""
    from data import league_strength as ls
    strength = _strength() if strength is None else strength
    effects = {} if effects is None else effects
    t0 = datetime.fromisoformat(start)
    t_end = datetime.fromisoformat(end) if end else max(tx._ts(r["ko"]) for r in rows) + timedelta(days=1)
    out = []
    while t0 < t_end:
        t1 = t0 + timedelta(days=step_days)
        db = tx.build_profiles(rows, as_of=t0)
        for r in rows:
            ko = tx._ts(r["ko"])
            if not (t0 <= ko < t1):
                continue
            th, ta = db["teams"].get(str(r["home"]["id"])), db["teams"].get(str(r["away"]["id"]))
            if not th or not ta:
                continue
            rd = tx.read(th, ta, db, ls.gap(strength, th.get("league_id"), ta.get("league_id")), effects)
            if rd is None:
                continue
            out.append({"row": r, "read": rd})
        t0 = t1
    return out


# ── lessons ────────────────────────────────────────────────────────────────


def _side_residuals(preds: list[dict]) -> list[tuple[str, str, float]]:
    """(ko, tag, actual xG - expected xG) for every attacking side and tag
    (plus its formation clash)."""
    out = []
    for p in preds:
        r, rd = p["row"], p["read"]
        for side, opp, lam, tags in (("home", "away", rd["xg_home"], rd["tags_home"]),
                                     ("away", "home", rd["xg_away"], rd["tags_away"])):
            xg = r[side].get("xg")
            if xg is None:
                continue
            res = xg - lam
            fa, fd = r[side].get("formation"), r[opp].get("formation")
            all_tags = list(tags) + ([f"formation {fa} v {fd}"] if fa and fd else [])
            for t in all_tags:
                out.append((r["ko"], t, res))
    return out


def _stats(vals: list[float]) -> tuple[int, float, float]:
    n = len(vals)
    if n < 2:
        return n, (vals[0] if vals else 0.0), float("inf")
    m = sum(vals) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))
    return n, m, sd / math.sqrt(n) if sd > 0 else float("inf")


def update_lessons(preds: list[dict], today: str, lessons: Optional[dict] = None) -> dict:
    """Write new candidates (as of `today`), test every candidate / proven
    lesson on the sides played after it was written."""
    lessons = tx.load_lessons() if lessons is None else lessons
    book = lessons.setdefault("lessons", {})
    res = _side_residuals(preds)
    by_tag: dict[str, list[tuple[str, float]]] = {}
    for ko, tag, r in res:
        by_tag.setdefault(tag, []).append((ko, r))
    for tag, xs in by_tag.items():
        entry = book.get(tag)
        if entry is None:
            n, m, se = _stats([r for ko, r in xs if ko < today])
            if n >= MIN_SIDES and se > 0 and abs(m) / se >= Z_CANDIDATE:
                book[tag] = {"status": "candidate", "written_at": today, "train_n": n,
                             "train_effect": round(m, 3), "train_z": round(m / se, 2)}
            continue
        n, m, se = _stats([r for ko, r in xs if ko >= entry["written_at"]])
        entry.update({"test_n": n, "test_effect": round(m, 3),
                      "test_z": round(m / se, 2) if se not in (0, float("inf")) else None, "checked": today})
        same = (m > 0) == (entry["train_effect"] > 0)
        z = abs(m) / se if se not in (0, float("inf")) else 0.0
        if entry["status"] == "candidate" and n >= MIN_SIDES and same and z >= Z_PROVEN:
            entry["status"] = "proven"
            entry["proven_at"] = today
            eff = EFFECT_SHRINK * m
            entry["effect"] = round(max(-EFFECT_CAP, min(EFFECT_CAP, eff)), 3)
        elif entry["status"] == "proven" and n >= MIN_SIDES and not same and z >= Z_PROVEN:
            entry["status"] = "retired"
            entry["retired_at"] = today
    lessons["updated"] = today
    return lessons


# ── weight against SportyBet's price ──────────────────────────────────────


def _devig2(pair) -> Optional[float]:
    try:
        a, b = 1 / pair[0], 1 / pair[1]
        return a / (a + b)
    except (TypeError, ZeroDivisionError, IndexError):
        return None


def universe_prices(folder: Path = UNIVERSE) -> list[dict]:
    """Every swept football game with SportyBet's last prices (latest file wins)."""
    seen: dict[str, dict] = {}
    for f in sorted(folder.glob("*.jsonl.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    last = r.get("last") or {}
                    # a price read at or after kick-off is in-play: never a pre-match price
                    if (r.get("sport") == "football" and last.get("p") and last.get("at")
                            and last["at"][:16] < r["ko"][:16]):
                        seen[r["id"]] = {"ko": r["ko"], "home": r["home"], "away": r["away"], "p": last["p"]}
        except (OSError, ValueError):
            continue
    return list(seen.values())


def attach_prices(preds: list[dict], prices: list[dict]) -> int:
    """Pair each prediction with a universe game: kickoff within 30 min and
    both names matching (the graders' strict rule). Returns pairs made."""
    from data import flashscore_results as fr
    by_hour: dict[str, list[dict]] = {}
    for g in prices:
        by_hour.setdefault(g["ko"][:13], []).append(g)
    made = 0
    for p in preds:
        r = p["row"]
        ko = tx._ts(r["ko"])
        pool = []
        for d in (-1, 0, 1):
            pool += by_hour.get((ko + timedelta(hours=d)).isoformat()[:13], [])
        best = [(min(fr._sim(r["home"]["name"], g["home"]), fr._sim(r["away"]["name"], g["away"])), g) for g in pool
                if abs((datetime.fromisoformat(g["ko"].replace("Z", "")[:16]) - ko).total_seconds()) <= 1800]
        best = sorted(best, key=lambda x: -x[0])
        if best and best[0][0] >= fr.MATCH_MIN and (len(best) < 2 or best[1][0] < best[0][0] - 0.02):
            p["price"] = best[0][1]["p"]
            made += 1
    return made


def _outcomes(p: dict) -> list[tuple[float, float, int]]:
    """(market chance, matchup chance, landed) for the goals markets priced."""
    r, hl, pr = p["row"], p["read"]["probs"], p.get("price") or {}
    hg, ag = r["home"]["goals"], r["away"]["goals"]
    out = []
    for key, mp_pair, tac, landed in (("btts", pr.get("btts"), hl["btts"], hg > 0 and ag > 0),
                                      ("ou2.5", pr.get("ou2.5"), hl["over25"], hg + ag >= 3),
                                      ("ou1.5", pr.get("ou1.5"), hl["over15"], hg + ag >= 2)):
        mp = _devig2(mp_pair) if mp_pair else None
        if mp is not None:
            out.append((mp, tac, int(landed)))
    return out


def fit_weight(preds: list[dict], seed: int = 7) -> dict:
    """Least-squares w for y ~ market + w (matchup - market); bootstrap SE by match."""
    per_match = [o for o in (_outcomes(p) for p in preds if p.get("price")) if o]

    def w_of(groups):
        num = sum((y - m) * (t - m) for g in groups for m, t, y in g)
        den = sum((t - m) ** 2 for g in groups for m, t, y in g)
        return num / den if den > 0 else 0.0
    if len(per_match) < 40:
        return {"weight": 0.0, "n_matches": len(per_match), "why": "fewer than 40 priced matches — label only"}
    w = w_of(per_match)
    rnd = random.Random(seed)
    boots = [w_of([rnd.choice(per_match) for _ in per_match]) for _ in range(300)]
    mb = sum(boots) / len(boots)
    se = math.sqrt(sum((b - mb) ** 2 for b in boots) / (len(boots) - 1))
    flat = [x for g in per_match for x in g]
    brier_m = sum((y - m) ** 2 for m, t, y in flat) / len(flat)
    brier_t = sum((y - t) ** 2 for m, t, y in flat) / len(flat)
    kept = min(WEIGHT_CAP, w) if w - Z_PROVEN * se > 0 else 0.0
    wb = kept or w
    brier_b = sum((y - (m + wb * (t - m))) ** 2 for m, t, y in flat) / len(flat)
    return {"weight": round(kept, 3), "fitted": round(w, 3), "se": round(se, 3), "n_matches": len(per_match),
            "n_outcomes": len(flat), "brier_price": round(brier_m, 4), "brier_matchup": round(brier_t, 4),
            "brier_blend": round(brier_b, 4),
            "why": ("matchup adds to the price on unseen matches" if kept else
                    "matchup not proven better than the price yet — label only")}


# ── the per-match study ────────────────────────────────────────────────────


def explain(p: dict) -> dict:
    """What the read expected, what happened, and why they differed."""
    r, rd = p["row"], p["read"]
    h, a = r["home"], r["away"]
    hg, ag = h["goals"], a["goals"]
    why = []
    for s in (h, a):
        for m in s.get("reds") or []:
            if m < 80:
                why.append(f"red card {s['name']} {m}'")
    for s, lam in ((h, rd["xg_home"]), (a, rd["xg_away"])):
        if s.get("xg") is None:
            continue
        if s["goals"] - s["xg"] >= 1.0:
            why.append(f"{s['name']} finished above their chances ({s['goals']} from {s['xg']:.2f} xG)")
        elif s["xg"] - s["goals"] >= 1.0:
            why.append(f"{s['name']} wasted chances ({s['goals']} from {s['xg']:.2f} xG)")
        if s["xg"] - lam >= 0.8:
            why.append(f"{s['name']} created far more than expected ({s['xg']:.2f} xG v {lam:.2f})")
        elif lam - s["xg"] >= 0.8:
            why.append(f"{s['name']} were held well below expectation ({s['xg']:.2f} xG v {lam:.2f})")
        st = s.get("shot_types") or {}
        x = st.get("xg") or {}
        if x.get("counter", 0) >= 0.5:
            why.append(f"{s['name']} hurt them on the counter ({x['counter']:.2f} xG from fast breaks)")
        if x.get("set_piece", 0) >= 0.6:
            why.append(f"{s['name']} set pieces ({x['set_piece']:.2f} xG)")
        if x.get("penalty", 0) > 0:
            why.append(f"penalty for {s['name']}")
    trail = [s for s in (h, a) if (s.get("state") or {}).get("trailing", {}).get("min", 0) >= 45]
    for s in trail:
        why.append(f"{s['name']} chased the game for {s['state']['trailing']['min']:.0f} min")
    hl = rd["probs"]
    btts = hg > 0 and ag > 0
    return {"ko": r["ko"], "fotmob_id": r["fotmob_id"], "competition": r.get("competition"),
            "match": f"{h['name']} v {a['name']}", "score": f"{hg}-{ag}",
            "formations": [h.get("formation"), a.get("formation")],
            "expected": {"xg": [rd["xg_home"], rd["xg_away"]], "btts": hl["btts"], "over25": hl["over25"],
                         "say": rd["say"]},
            "actual": {"xg": [h.get("xg"), a.get("xg")], "btts": btts, "over25": hg + ag >= 3},
            "btts_call": ("right" if (hl["btts"] >= 0.5) == btts else "wrong"),
            "why": why or ["played to the profiles"]}


def report(preds: list[dict], weight: dict, lessons: dict, path: Path = REPORT) -> None:
    n = len(preds)
    if not n:
        return
    br_b = sum((p["read"]["probs"]["btts"] - (p["row"]["home"]["goals"] > 0 and p["row"]["away"]["goals"] > 0)) ** 2
               for p in preds) / n
    base = sum(p["row"]["home"]["goals"] > 0 and p["row"]["away"]["goals"] > 0 for p in preds) / n
    br_0 = sum((base - (p["row"]["home"]["goals"] > 0 and p["row"]["away"]["goals"] > 0)) ** 2 for p in preds) / n
    ls = lessons.get("lessons") or {}
    lines = ["# TACTICS STUDY — matchup read, walk-forward (engine/tactics_study.py)", "",
             f"_Regenerated {datetime.utcnow():%Y-%m-%d %H:%M} UTC by the nightly match study._", "",
             f"- Matches read walk-forward (profiles from earlier matches only): **{n}**",
             f"- BTTS Brier: matchup {br_b:.4f} v the season base rate {br_0:.4f} (lower is better)",
             f"- Against SportyBet's price ({weight.get('n_matches', 0)} matches priced): Brier price "
             f"{weight.get('brier_price', 'PENDING')} · matchup {weight.get('brier_matchup', 'PENDING')} · "
             f"blend {weight.get('brier_blend', 'PENDING')}; fitted weight {weight.get('fitted', 'PENDING')} ± "
             f"{weight.get('se', 'PENDING')} → **weight in force {weight.get('weight', 0)}** ({weight.get('why', '')})",
             "", "## Lessons", "", "| Tag | Status | Written | Train n / effect / z | Unseen n / effect / z | In force |",
             "|---|---|---|---|---|---|"]
    for tag, x in sorted(ls.items(), key=lambda kv: (kv[1]["status"] != "proven", kv[0])):
        lines.append(f"| {tag} | {x['status']} | {x['written_at']} | {x['train_n']} / {x['train_effect']:+.2f} / "
                     f"{x['train_z']} | {x.get('test_n', 0)} / {x.get('test_effect', 0):+.2f} / {x.get('test_z')} | "
                     f"{x.get('effect', '—') if x['status'] == 'proven' else '—'} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
