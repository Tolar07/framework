"""
EXPERIMENT ENGINE — strategies compete in shadow; the better one fills the slot
(Architect 2026-10-20: "total autonomous ... learn from mistakes ... decision
making properly"; auto-promotion approved the same day).

A STRATEGY is a fixed rule that decides which of the day's candidates fill one
board SLOT:

  singles  TABLE 2 deploy singles (the board's own picks)
  accas    TABLE 3 accas
  safe3    TABLE 3A 50%+ accas

Board strategies are SUBSET rules: they keep or drop the board's own picks /
slips, never invent new ones, and a dropped pick or slip is still recorded in
the ledger (`singles_dropped`, `accas_dropped`, `safe3_dropped`) and graded. So
every strategy — the live one and every shadow — is scored on the same
candidates each day, and the default ("S0 board singles" etc.) stays
reproducible after another rule has gone live.

The universe paper rules (engine/paper_book.py F/P singles, A1-A4 accas) are
registered too and scored over every graded SportyBet game, but they pick from
games the board doesn't hold, so they can't be wired into a slot: if one
qualifies it is FLAGGED to the Architect, never swapped in. "Drop Gemini
vetoes" is scored the same way and not wireable either: the reasoning step runs
after the board is built.

PROMOTION (automatic). A shadow with >= MIN_BETS graded bets since it was
registered that beats the slot's live strategy over the same days on BOTH
mean CLV (entry / close - 1) and flat return per £1, each by a one-sided
z-test (difference of means over its standard error >= Z_BAR), replaces it;
the old live rule is DEMOTED to shadow. At most one change per slot per
COOLDOWN_DAYS. Every change -> memory/strategy_log.jsonl and one Telegram line.

A rule written after results were seen counts only from the day it was
written (`since`) — the evidence that suggested a rule can't also be its test.
Results before `since` are shown as in-sample, never counted.

NOT CHANGED by this engine: stakes and staking rules (order 21), the CLV gate,
ARCHITECT_SIGNOFF, the league list — only which picks / slips fill the
existing slots. Switch: ON by default (Architect 2026-10-20); set the
environment variable OLP_EXPERIMENTS=off to freeze every slot on its default.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "memory" / "strategies.json"
LOG = ROOT / "memory" / "strategy_log.jsonl"
PICKS_DIR = ROOT / "output" / "picks"
REASONING_DIR = ROOT / "output" / "reasoning"

MIN_BETS = 100          # graded bets a challenger needs in its window
MIN_CLV = 30            # bets with a closing price, each side, before CLV can count
Z_BAR = 1.645           # one-sided 95%
COOLDOWN_DAYS = 7
WRITTEN = "2026-10-20"  # the day the board strategies below were written down

SLOTS = ("singles", "accas", "safe3")
DEFAULT = {"singles": "S0 board singles", "accas": "A0 board accas", "safe3": "T0 board 50%+ accas"}


def enabled() -> bool:
    return os.environ.get("OLP_EXPERIMENTS", "on").strip().lower() not in ("off", "0", "false", "no")


# ── legs: one normalised shape for the ledger and the live board ─────────────
def band(price: float | None) -> str:
    if not price:
        return "?"
    for hi, name in ((1.30, "<1.30"), (1.50, "1.30-1.50"), (1.75, "1.50-1.75"), (2.00, "1.75-2.00")):
        if price < hi:
            return name
    return "2.00+"


def leg(s: dict, verdict: str | None = None) -> dict:
    """A ledger single (or picks_ledger._single(bf) at board time) -> leg."""
    from engine.learning import family
    return {"fixture": s.get("fixture"), "league": s.get("league") or "?",
            "market": s.get("market"), "family": family(s.get("market")),
            "price": s.get("price"), "chance": s.get("chance"),
            "close": s.get("closing_price"), "result": s.get("result"),
            "certainty": s.get("certainty") or "?",
            "news": s.get("news_level") or "?", "verdict": verdict}


# ── strategies ───────────────────────────────────────────────────────────────
Keep = Callable[[dict, dict], bool]          # (leg, day context) -> keep?


@dataclass
class Strategy:
    name: str
    slot: str
    desc: str
    keep: Keep | None = None              # board rules: which legs may stay
    universe: str | None = None           # paper_book rule / acca name
    since: str = ""
    wireable: bool = True
    why_not: str = ""
    extra: dict = field(default_factory=dict)


def _all(_l: dict, _c: dict) -> bool:
    return True


def _band(lo: float, hi: float) -> Keep:
    return lambda x, _c: x["price"] is not None and lo <= x["price"] < hi


GEMINI_WHY = "the reasoning step runs after the board is built — no verdict exists at selection time"
UNIVERSE_WHY = "picks from every SportyBet game, not the board's candidates"


def _board_rules() -> list[Strategy]:
    w = WRITTEN
    singles = [
        Strategy(DEFAULT["singles"], "singles", "every deploy single the board picks (orders 3, 4, 11)", _all),
        Strategy("S1 HIGH certainty only", "singles", "singles whose certainty is HIGH (order 15)",
                 lambda x, _c: x["certainty"] == "HIGH", since=w),
        Strategy("S2 price 1.20-1.30", "singles", "singles priced 1.20-1.30", _band(1.20, 1.30), since=w),
        Strategy("S3 price 1.30-2.00", "singles", "singles priced 1.30-2.00", _band(1.30, 2.01), since=w),
        Strategy("S4 value only", "singles", "singles priced at or above our fair odds (chance x price >= 1)",
                 lambda x, _c: bool(x["chance"] and x["price"]) and x["chance"] * x["price"] >= 1.0, since=w),
        Strategy("S5 clean news", "singles", "singles with no injury / lineup flag (news OK)",
                 lambda x, _c: x["news"] == "OK", since=w),
        Strategy("S6 no double chance", "singles", "singles outside the Double chance family",
                 lambda x, _c: x["family"] != "Double chance", since=w),
        Strategy("S7 drop Gemini vetoes", "singles", "singles the reasoning step did not veto",
                 lambda x, _c: x["verdict"] != "veto", since=w, wireable=False, why_not=GEMINI_WHY),
    ]
    slips = []
    for slot, code, label in (("accas", "A", "accas"), ("safe3", "T", "50%+ accas")):
        slips += [
            Strategy(DEFAULT[slot], slot, f"every {label} slip the board builds", _all),
            Strategy(f"{code}5 {label}: HIGH-certainty legs", slot, f"{label} whose every leg is HIGH certainty",
                     lambda x, _c: x["certainty"] == "HIGH", since=w),
            Strategy(f"{code}6 {label}: value legs", slot, f"{label} whose every leg is priced at or above fair",
                     lambda x, _c: bool(x["chance"] and x["price"]) and x["chance"] * x["price"] >= 1.0, since=w),
            Strategy(f"{code}7 {label}: no Gemini veto", slot, f"{label} with no leg the reasoning step vetoed",
                     lambda x, _c: x["verdict"] != "veto", since=w, wireable=False, why_not=GEMINI_WHY),
        ]
    return singles + slips


def _universe_rules() -> list[Strategy]:
    from engine import paper_book as pb
    out = [Strategy(f"U:{n}", "singles", f"paper rule — {d}", universe=n, since=pb.SINCE.get(n, ""),
                    wireable=False, why_not=UNIVERSE_WHY)
           for n, (sport, d, _f) in pb.STRATEGIES.items() if sport == "football"]
    out += [Strategy(f"U:{n}", "accas", f"paper acca — {d}", universe=n,
                     since="2026-10-09" if n.startswith("A4") else "", wireable=False, why_not=UNIVERSE_WHY)
            for n, (d, _r) in pb.ACCAS.items()]
    return out


def _postmortem() -> Any:
    """engine/leg_postmortem.py (item 2), imported by name so this module
    stands alone; ImportError when it isn't there."""
    import importlib
    return importlib.import_module("engine.leg_postmortem")


def strategies() -> list[Strategy]:
    out = _board_rules() + _universe_rules()
    try:                                     # item 2: the slip-killer rule, if built
        extra = _postmortem().strategies()
    except ImportError:
        extra = []
    return out + extra


# ── candidates and bets ──────────────────────────────────────────────────────
def _verdicts(day: str, folder: Path) -> dict:
    p = folder / f"reasoning_{day}.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {(x.get("fixture"), x.get("market")): x.get("verdict") for x in doc.get("picks", [])}


def load_days(picks_dir: Path = PICKS_DIR, reasoning_dir: Path = REASONING_DIR) -> list[dict]:
    """[{day, legs, slips: {slot: [{name, odds, result, legs}]}}], oldest first,
    from the live ledgers (superseded ones are left out, as in the scorecard)."""
    days = []
    for path in sorted(picks_dir.glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        v = _verdicts(doc["date"], reasoning_dir)
        legs = [leg(s, v.get((s.get("fixture"), s.get("market"))))
                for s in doc.get("singles", []) + doc.get("singles_dropped", [])]
        by_fix = {lg["fixture"]: lg for lg in legs}
        slips = {slot: [{"name": s.get("name"), "odds": s.get("odds"), "result": s.get("result"),
                         "legs": [by_fix.get(f) for f in s.get("legs", [])]}
                        for s in doc.get(slot, []) + doc.get(f"{slot}_dropped", [])]
                 for slot in ("accas", "safe3")}
        days.append({"day": doc["date"], "legs": legs, "slips": slips})
    return days


def single_bet(lg: dict, day: str) -> dict | None:
    if lg["result"] not in ("won", "lost") or not lg["price"]:
        return None
    won = lg["result"] == "won"
    return {"day": day, "won": int(won), "pnl": (lg["price"] - 1) if won else -1.0,
            "clv": (lg["price"] / lg["close"] - 1) if lg["close"] else None}


def slip_bet(s: dict, day: str) -> dict | None:
    if s["result"] not in ("won", "lost") or not s["odds"]:
        return None
    won = s["result"] == "won"
    legs = s["legs"]
    clv = None
    if legs and all(lg and lg["price"] and lg["close"] for lg in legs):
        entry = close = 1.0
        for lg in legs:
            entry *= lg["price"]
            close *= lg["close"]
        clv = entry / close - 1
    return {"day": day, "won": int(won), "pnl": (s["odds"] - 1) if won else -1.0, "clv": clv}


def board_bets(st: Strategy, days: list[dict], contexts: dict | None = None) -> list[dict]:
    """Every graded bet a board strategy would have had, day by day."""
    out = []
    keep = st.keep or _all
    for d in days:
        ctx = (contexts or {}).get(d["day"], {})
        if st.slot == "singles":
            bets = [single_bet(lg, d["day"]) for lg in d["legs"] if keep(lg, ctx)]
        else:
            bets = [slip_bet(s, d["day"]) for s in d["slips"][st.slot]
                    if all(lg is None or keep(lg, ctx) for lg in s["legs"])]
        out += [b for b in bets if b]
    return out


def universe_bets(rows: list[dict]) -> dict[str, list[dict]]:
    """{'U:<rule>': bets} for the paper rules, from data/universe/ rows."""
    from engine import paper_book as pb
    out: dict[str, list[dict]] = {}
    for row in rows:
        for b in pb.bets(row):
            out.setdefault(f"U:{b['strategy']}", []).append(
                {"day": b["day"], "won": b["won"], "pnl": b["pnl"], "clv": b["clv"]})
    for a in pb.accas(rows):
        out.setdefault(f"U:{a['acca']}", []).append(
            {"day": a["day"], "won": a["won"], "pnl": a["pnl"], "clv": None})
    return out


# ── scoring and the promotion test ───────────────────────────────────────────
def _mean_se(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, float("inf")
    m = sum(xs) / n
    if n < 2:
        return m, float("inf")
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, sqrt(var / n)


def summary(bets: list[dict]) -> dict:
    clv = [b["clv"] for b in bets if b["clv"] is not None]
    roi, roi_se = _mean_se([b["pnl"] for b in bets])
    c, c_se = _mean_se(clv)
    return {"n": len(bets), "won": sum(b["won"] for b in bets),
            "roi": round(roi, 4) if bets else None, "roi_se": round(roi_se, 4) if len(bets) > 1 else None,
            "n_clv": len(clv), "clv": round(c, 4) if clv else None,
            "clv_se": round(c_se, 4) if len(clv) > 1 else None,
            "first": min((b["day"] for b in bets), default=None),
            "last": max((b["day"] for b in bets), default=None)}


def _z(a: list[float], b: list[float]) -> float:
    ma, sa = _mean_se(a)
    mb, sb = _mean_se(b)
    se = sqrt(sa * sa + sb * sb)
    return (ma - mb) / se if se and se != float("inf") else 0.0


def beats(challenger: list[dict], incumbent: list[dict]) -> tuple[bool, str, dict]:
    """Does the challenger beat the incumbent on BOTH flat return and mean CLV,
    each significantly (one-sided z >= Z_BAR)? Both lists cover the same days."""
    c_pnl, i_pnl = [b["pnl"] for b in challenger], [b["pnl"] for b in incumbent]
    c_clv = [b["clv"] for b in challenger if b["clv"] is not None]
    i_clv = [b["clv"] for b in incumbent if b["clv"] is not None]
    stats: dict[str, Any] = {"n": len(c_pnl), "n_live": len(i_pnl), "z_return": None, "z_clv": None}
    if len(c_pnl) < MIN_BETS:
        return False, f"{len(c_pnl)}/{MIN_BETS} graded bets", stats
    if not i_pnl:
        return False, "the live rule has no graded bets in this window", stats
    if len(c_clv) < MIN_CLV or len(i_clv) < MIN_CLV:
        return False, f"too few closing prices ({len(c_clv)} v {len(i_clv)}, {MIN_CLV} each needed)", stats
    zr, zc = _z(c_pnl, i_pnl), _z(c_clv, i_clv)
    stats.update(z_return=round(zr, 2), z_clv=round(zc, 2))
    if zr >= Z_BAR and zc >= Z_BAR:
        return True, f"beats live: return z {zr:.2f}, CLV z {zc:.2f}", stats
    return False, f"not significantly better (return z {zr:.2f}, CLV z {zc:.2f}; {Z_BAR} needed on both)", stats


def _in(bets: list[dict], start: str) -> list[dict]:
    return [b for b in bets if b["day"] >= start]


# ── registry and evaluation ──────────────────────────────────────────────────
def load_registry(path: Path = REGISTRY) -> dict:
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reg = {}
    reg.setdefault("live", dict(DEFAULT))
    reg.setdefault("flagged", [])
    reg.setdefault("last_change", {})
    for slot in SLOTS:
        reg["live"].setdefault(slot, DEFAULT[slot])
    return reg


def evaluate(days: list[dict], universe: dict[str, list[dict]], reg: dict, today: str,
             contexts: dict | None = None) -> tuple[dict, list[dict]]:
    """Score every strategy, apply promotions / demotions. Returns
    (registry, events) — events are what was changed or flagged today."""
    sts = strategies()
    by_name = {s.name: s for s in sts}
    bets = {s.name: (universe.get(s.name, []) if s.universe else board_bets(s, days, contexts)) for s in sts}
    events: list[dict] = []
    standings: dict[str, dict] = {}
    for slot in SLOTS:
        live_name = reg["live"].get(slot, DEFAULT[slot])
        if live_name not in by_name:                        # a rule was removed: back to the default
            live_name = reg["live"][slot] = DEFAULT[slot]
        live = by_name[live_name]
        qualified: list[tuple] = []
        for st in (s for s in sts if s.slot == slot):
            counted = _in(bets[st.name], st.since)
            row = {"slot": slot, "desc": st.desc, "since": st.since or "start",
                   "status": "LIVE" if st.name == live_name else "shadow",
                   "wireable": st.wireable, "why_not": st.why_not or None,
                   "counted": summary(counted), "in_sample": summary(bets[st.name])}
            if st.name != live_name:
                start = st.since or (counted[0]["day"] if counted else "")
                ok, why, z = beats(counted, _in(bets[live_name], start))
                row["vs_live"] = why
                if ok:
                    qualified.append((st, z, why))
            standings[st.name] = row
        for st, z, why in qualified:                       # flagged once, never swapped in
            if not st.wireable and st.name not in reg["flagged"]:
                reg["flagged"].append(st.name)
                events.append({"at": today, "slot": slot, "event": "qualifies-not-wireable", "strategy": st.name,
                               "live": live_name, "why": why, "why_not": st.why_not, **z})
        wired = [q for q in qualified if q[0].wireable]
        if not wired:
            continue
        st, z, why = max(wired, key=lambda q: (q[1]["z_return"] or 0) + (q[1]["z_clv"] or 0))
        last = reg["last_change"].get(slot)
        if last and (date.fromisoformat(today) - date.fromisoformat(last)).days < COOLDOWN_DAYS:
            continue
        if not enabled():
            continue
        reg["live"][slot] = st.name
        reg["last_change"][slot] = today
        standings[st.name]["status"], standings[live.name]["status"] = "LIVE", "shadow"
        events.append({"at": today, "slot": slot, "event": "promote", "strategy": st.name,
                       "demoted": live.name, "why": why, **z})
    reg["standings"] = standings
    reg["evaluated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
    reg["engine_on"] = enabled()
    return reg, events


def save(reg: dict, events: list[dict], path: Path = REGISTRY, log: Path = LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=1, sort_keys=True), encoding="utf-8")
    if events:
        with log.open("a", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")


def telegram_line(e: dict) -> str:
    if e["event"] == "promote":
        return (f"🧪 Experiment engine — {e['slot']}: \"{e['strategy']}\" now fills the slot, "
                f"\"{e['demoted']}\" back to shadow ({e['why']}; {e['n']} bets). Stakes unchanged.")
    return (f"🧪 Experiment engine — {e['slot']}: \"{e['strategy']}\" beats the live rule "
            f"({e['why']}) but can't be wired ({e['why_not']}). Your call.")


def brief(reg: dict) -> str:
    """One line per slot: what is live and the leading shadow."""
    st = reg.get("standings") or {}
    parts = []
    for slot in SLOTS:
        live = reg.get("live", {}).get(slot, DEFAULT[slot])
        lc = (st.get(live) or {}).get("counted") or {}
        rivals = [(n, r["counted"]) for n, r in st.items()
                  if r["slot"] == slot and n != live and r["counted"]["n"]]
        lead = max(rivals, key=lambda x: x[1]["roi"] or -9, default=None)
        roi = f"{lc['roi']:+.0%}" if lc.get("roi") is not None else "—"
        s = f"{slot}: {live} ({lc.get('n', 0)} bets, {roi})"
        if lead:
            s += f"; best shadow {lead[0]} ({lead[1]['n']} bets, {lead[1]['roi']:+.0%})"
        parts.append(s)
    return " · ".join(parts)


# ── the live board: which picks / slips the live rules keep ──────────────────
def live_rules(path: Path = REGISTRY) -> dict[str, Strategy]:
    """{slot: Strategy} for slots whose live rule is not the default. Empty
    when the switch is off or every slot runs its default."""
    if not enabled():
        return {}
    reg = load_registry(path)
    by_name = {s.name: s for s in strategies()}
    out = {}
    for slot in SLOTS:
        st = by_name.get(reg["live"].get(slot, DEFAULT[slot]))
        if st and st.name != DEFAULT[slot] and st.wireable and st.keep:
            out[slot] = st
    return out


def board_context(path: Path = REGISTRY) -> dict:
    """The day context live rules read at board time (item 2: slip killers)."""
    try:
        return _postmortem().context_now()
    except ImportError:
        return {}
