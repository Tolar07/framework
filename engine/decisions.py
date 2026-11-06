"""
DECISION LAYER (standing order 51; Architect 2026-11-06 05:51 UK: "stake size ... rung 3 within the range. Market and
league versus real money ... handle it. Per market value ... handle it. I can still undo it later ... undo everything").

Every automatic money decision goes through here, inside config/decision_caps.json (the Architect's limits):

  stake_multiplier  per group (bot | market | side): x0.5 .. x1.5 of the bot's own stake, one step (0.25) at a time,
                    up on ROI >= +5%, down on ROI <= -10%, over 30+ graded real bets in 30 days, 7-day cool-down
  real_or_paper     per group: ROI <= -15% over 30+ real bets -> paper; a paper group at ROI >= +5% over 30+ -> real
  value_threshold   per (sport, market) of the hockey / multi-sport boards: the value bar whose graded sides made the
                    most profit (ROI >= 0, 50+ sides), kept inside 0.5x .. 2x of the board's default

Every decision is written to memory/decisions.jsonl with its evidence, the bar it must keep meeting and its undo.
watch() checks each live decision against that bar on the bets placed SINCE it was made (20+): worse than -10% ->
undone automatically, the reason recorded, the Architect told at once. DECISIONS_AUTO=0 (repo variable) undoes
everything on the next run. Published state: output/decisions/state.json (the bots and boards read it).

A group is group_of(<market key>): the key's first field and its outcome with numbers as N, e.g.
"SB:18 Over N", "NBA:223 Home (N)", "tennis:186 Home". Bots compute the same from the pick key they bet.
Never touches the CLV gate, ARCHITECT_SIGNOFF, the capital bright line, the loss stop or the caps themselves.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPS_FILE = ROOT / "config" / "decision_caps.json"
STATE_FILE = ROOT / "output" / "decisions" / "state.json"
LOG_FILE = ROOT / "memory" / "decisions.jsonl"


def caps(path: Path = CAPS_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def group_of(key: str | None, bot: str = "") -> str:
    """'SB:18|total=2.5|Over 2.5' -> 'SB:18 Over N' (with the bot in front when given)."""
    if not key:
        return ""
    parts = key.split("|")
    token, outcome = parts[0], parts[-1] if len(parts) > 1 else ""
    side = re.sub(r"[+-]?\d+(?:[.:]\d+)?", "N", outcome).strip()
    return f"{bot + ' | ' if bot else ''}{token} {side}".strip()


def baseline() -> dict:
    return {"auto": True, "stake_mult": {}, "paper_groups": [], "value_threshold": {}, "updated": None}


def load_state(path: Path = STATE_FILE) -> dict:
    try:
        return {**baseline(), **json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return baseline()


def load_log(path: Path = LOG_FILE) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _roi(bets: list[dict]) -> tuple[float | None, int]:
    st = sum(b.get("stake_gbp") or 0 for b in bets)
    pr = sum(b.get("profit_gbp") or 0 for b in bets)
    return (pr / st if st > 0 else None), len(bets)


def _last_change(log: list[dict], kind: str, key: str) -> datetime | None:
    ts = [_ts(d["at"]) for d in log if d.get("kind") == kind and d.get("key") == key]
    return max(ts) if ts else None


def _decision(kind: str, key: str, frm, to, evidence: dict, bar: str, now: datetime) -> dict:
    return {"id": f"D{now:%Y%m%d}-{secrets.token_hex(2)}", "at": now.isoformat(timespec="minutes"), "kind": kind,
            "key": key, "from": frm, "to": to, "evidence": evidence, "bar": bar, "undo": {"set": frm},
            "status": "live"}


def decide_stakes(groups: dict[str, list[dict]], state: dict, log: list[dict], c: dict, now: datetime) -> list[dict]:
    sc = c["stake_multiplier"]
    out = []
    for g, bets in sorted(groups.items()):
        roi, n = _roi(bets)
        if roi is None or n < sc["min_bets"] or g in state["paper_groups"]:
            continue
        last = _last_change(log, "stake_multiplier", g)
        if last and now - last < timedelta(days=sc["cooldown_days"]):
            continue
        cur = float(state["stake_mult"].get(g, sc["baseline"]))
        new = cur
        if roi >= sc["up_roi"]:
            new = min(sc["max"], cur + sc["step"])
        elif roi <= sc["down_roi"]:
            new = max(sc["min"], cur - sc["step"])
        if new != cur:
            out.append(_decision("stake_multiplier", g, cur, new, {"bets": n, "roi": round(roi, 4), "days": 30},
                                 f"ROI on the next {c['rollback']['min_bets_after']}+ bets above "
                                 f"{c['rollback']['roi_below']:+.0%}", now))
    return out


def decide_paper(groups: dict[str, list[dict]], paper_groups: dict[str, list[dict]], state: dict, log: list[dict],
                 c: dict, now: datetime) -> list[dict]:
    rp = c["real_or_paper"]
    out = []
    for g, bets in sorted(groups.items()):
        roi, n = _roi(bets)
        last = _last_change(log, "real_or_paper", g)
        if roi is None or n < rp["min_bets"] or g in state["paper_groups"] or (
                last and now - last < timedelta(days=rp["cooldown_days"])):
            continue
        if roi <= rp["to_paper_roi"]:
            out.append(_decision("real_or_paper", g, "real", "paper", {"bets": n, "roi": round(roi, 4)},
                                 "paper ROI must recover to the to_real bar before it returns", now))
    for g in sorted(state["paper_groups"]):
        bets = paper_groups.get(g.split(" | ", 1)[-1], [])
        roi, n = _roi(bets)
        last = _last_change(log, "real_or_paper", g)
        if roi is None or n < rp["min_bets"] or (
                last and now - last < timedelta(days=rp["cooldown_days"])):
            continue
        if roi >= rp["to_real_roi"]:
            out.append(_decision("real_or_paper", g, "paper", "real", {"paper_bets": n, "roi": round(roi, 4)},
                                 f"real ROI on the next {c['rollback']['min_bets_after']}+ bets above "
                                 f"{c['rollback']['roi_below']:+.0%}", now))
    return out


def decide_thresholds(sides: dict[str, list[tuple[float, int, float]]], defaults: dict[str, float], state: dict,
                      log: list[dict], c: dict, now: datetime) -> list[dict]:
    """sides: {'sport|market': [(value at first look, won 1/0, price), ...]} of graded board sides."""
    vt = c["value_threshold"]
    out = []
    for key, rows in sorted(sides.items()):
        default = defaults.get(key)
        if default is None:
            continue
        last = _last_change(log, "value_threshold", key)
        if last and now - last < timedelta(days=vt["cooldown_days"]):
            continue
        lo, hi = default * vt["band"][0], default * vt["band"][1]
        best = None                     # the bar with the most total profit (ties: the higher bar), ROI >= 0
        for t in vt["candidates"]:
            if not lo <= t <= hi:
                continue
            pick = [(won, price) for v, won, price in rows if v >= t]
            if len(pick) < vt["min_sides"]:
                continue
            profit = sum((p - 1) if w else -1 for w, p in pick)
            roi = profit / len(pick)
            if roi >= 0 and (best is None or profit >= best[3]):
                best = (t, len(pick), roi, profit)
        cur = float(state["value_threshold"].get(key, default))
        if best and abs(best[0] - cur) > 1e-9:
            out.append(_decision("value_threshold", key, cur, best[0],
                                 {"sides": best[1], "roi": round(best[2], 4), "band": [lo, hi]},
                                 "picks at this bar keep ROI >= -10% over the next 20+", now))
    return out


def apply(state: dict, ds: list[dict]) -> dict:
    for d in ds:
        if d["kind"] == "stake_multiplier":
            state["stake_mult"][d["key"]] = d["to"]
        elif d["kind"] == "real_or_paper":
            pg = set(state["paper_groups"])
            (pg.add if d["to"] == "paper" else pg.discard)(d["key"])
            state["paper_groups"] = sorted(pg)
        elif d["kind"] == "value_threshold":
            state["value_threshold"][d["key"]] = d["to"]
    return state


def watch(log: list[dict], groups: dict[str, list[dict]], c: dict, now: datetime) -> list[dict]:
    """Live decisions whose bets SINCE the decision fall below the rollback bar -> undo decisions."""
    rb = c["rollback"]
    out = []
    for d in log:
        if d.get("status") != "live" or d["kind"] not in ("stake_multiplier", "real_or_paper"):
            continue
        if d["kind"] == "real_or_paper" and d["to"] == "paper":
            continue                                    # nothing is staked on a paper group to judge
        if d["kind"] == "stake_multiplier" and d["to"] <= d["from"]:
            continue                                    # a cut only lowers risk
        after = [b for b in groups.get(d["key"], []) if (b.get("date") or "") > d["at"][:10]]
        roi, n = _roi(after)
        if roi is not None and n >= rb["min_bets_after"] and roi < rb["roi_below"]:
            u = _decision(d["kind"], d["key"], d["to"], d["from"], {"bets_since": n, "roi_since": round(roi, 4)},
                          f"undo of {d['id']}: below its bar", now)
            u["undoes"] = d["id"]
            out.append(u)
    return out


def run(bets: list[dict], paper_bets: list[dict], sides: dict, defaults: dict, now: datetime | None = None,
        state_path: Path = STATE_FILE, log_path: Path = LOG_FILE, caps_path: Path = CAPS_FILE) -> dict:
    """One pass: undo, decide, apply, publish. bets / paper_bets: graded singles with group, stake_gbp, profit_gbp,
    placed_at. Returns {"made": [...], "undone": [...], "state": ...}."""
    now = now or datetime.now(timezone.utc)
    c = caps(caps_path)
    log = load_log(log_path)
    state = load_state(state_path)
    if (os.environ.get(c["master_switch_var"]) or "1") == "0":
        if state != {**baseline(), "updated": state.get("updated"), "auto": False}:
            state = {**baseline(), "auto": False, "updated": now.isoformat(timespec="minutes")}
            _save(state, state_path)
        return {"made": [], "undone": [], "state": state, "off": True}
    groups: dict[str, list[dict]] = {}
    for b in bets:
        groups.setdefault(b["group"], []).append(b)
    pgroups: dict[str, list[dict]] = {}
    for b in paper_bets:
        pgroups.setdefault(b["group"], []).append(b)
    undone = watch(log, groups, c, now)
    made = decide_stakes(groups, state, log, c, now) + decide_paper(groups, pgroups, state, log, c, now) \
        + decide_thresholds(sides, defaults, state, log, c, now)
    ids = {u["undoes"] for u in undone}
    log = [dict(d, status="undone") if d["id"] in ids else d for d in log]
    state = apply(state, undone + made)
    state["auto"], state["updated"] = True, now.isoformat(timespec="minutes")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in log + undone + made), encoding="utf-8")
    _save(state, state_path)
    return {"made": made, "undone": undone, "state": state, "off": False}


def _save(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")


def report_line(res: dict) -> str:
    if res.get("off"):
        return "DECISIONS: OFF (DECISIONS_AUTO=0): every decision is back at its baseline."
    st = res["state"]
    live = len(st["stake_mult"]) + len(st["paper_groups"]) + len(st["value_threshold"])
    made = "; ".join(f"{d['kind'].replace('_', ' ')} {d['key']}: {d['from']} -> {d['to']}" for d in res["made"][:6])
    und = "; ".join(f"{d['key']}: back to {d['to']} ({d['evidence'].get('roi_since', 0):+.0%} since)"
                    for d in res["undone"][:6])
    return (f"DECISIONS: {len(res['made'])} made" + (f" ({made})" if made else "")
            + f", {len(res['undone'])} undone" + (f" ({und})" if und else "")
            + f", {live} live. Undo everything: DECISIONS_AUTO=0.")


def stake_mult(state: dict, group: str) -> float:
    """What a bot multiplies its stake by (1.0 when off or unknown), always inside the caps."""
    if not state.get("auto", True):
        return 1.0
    sc = caps()["stake_multiplier"]
    return min(sc["max"], max(sc["min"], float((state.get("stake_mult") or {}).get(group, 1.0))))


def value_threshold(state: dict, key: str, default: float) -> float:
    if not state.get("auto", True):
        return default
    lo, hi = (default * x for x in caps()["value_threshold"]["band"])
    return min(hi, max(lo, float((state.get("value_threshold") or {}).get(key, default))))
