"""
AI SURVIVOR — the heartbeat lineage (Architect model 2026-08-29, rulings
2026-09-17/19), carried onto the cloud framework 2026-10-02.

The heartbeat is a LIFEFORM under selection pressure. Its lifeforce is its
bankroll (virtual, paper — no real capital is routed).

  - Every living lineage holds ONE pick a day, staking STAKE units.
  - WIN  -> bankroll += stake x (price - 1); at the next breeding the lineage
            REPRODUCES into up to OFFSPRING_PER_WIN children that split its
            bankroll (the parent retires; the bloodline continues).
  - LOSS -> EXTINCTION. One loss ends the bloodline (ruling 2026-09-17); the
            stake is debited first so the ledger shows what it was worth.
  - VOID / no 90-minute result -> stake back, the lineage carries on.
  - At most MAX_LINEAGES alive. Slots are allocated BEFORE breeding — every
    survivor keeps one, spare slots go to the richest winners — so no living
    lineage or its capital is ever deleted (fix of 2026-09-19).
  - If every lineage dies, ONE is reseeded at STARVATION_FLOOR.

What changed on the cloud framework: picks come from the daily board's own
selection (full SportyBet market ladder, model + bookmaker consensus,
certainty, learned corrections) instead of the old edge ranking that leaned on
Under-goals. Because one loss is death, a lineage takes the board's most
LIKELY winner: non-LOW certainty first, then the highest chance; Under-goals
picks only when nothing else is left (Architect preference). Strongest
lineage gets the strongest pick, one fixture per lineage, pre-match only.

Results come from Flashscore (regular time only) via the same matcher as the
picks ledger. Never guessed (HR35): an unmatched match stays PENDING.

State: data/survivor/lineage.json (population) and history.jsonl (every pick
with its lineage, graded in place).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

STATE_DIR = Path(__file__).parent.parent / "data" / "survivor"
LINEAGE_FILE = STATE_DIR / "lineage.json"
HISTORY_FILE = STATE_DIR / "history.jsonl"

GENESIS_BANKROLL = 100.0
STAKE = 1.0
OFFSPRING_PER_WIN = 2
MAX_LINEAGES = 8
STARVATION_FLOOR = 1.0
UNGRADED_DAYS = 4


def _new_id() -> str:
    return "ln_" + uuid.uuid4().hex[:10]


def _lineage(parent=None, generation=0, bankroll=GENESIS_BANKROLL, born=None) -> dict:
    return {"lineage_id": _new_id(), "parent_id": parent, "generation": generation,
            "bankroll": round(bankroll, 2), "stake": STAKE, "wins": 0, "losses": 0,
            "alive": True, "born_date": born or date.today().isoformat(),
            "last_result": None, "to_breed": False, "holding": None}


# ---------------------------------------------------------------- persistence
def load(state_dir: Path = STATE_DIR) -> tuple[dict, list[dict]]:
    lf, hf = state_dir / "lineage.json", state_dir / "history.jsonl"
    pop = (json.loads(lf.read_text(encoding="utf-8")) if lf.exists()
           else {"lineages": [_lineage()], "last_bred_date": None})
    hist = ([json.loads(x) for x in hf.read_text(encoding="utf-8").splitlines() if x.strip()]
            if hf.exists() else [])
    return pop, hist


def save(pop: dict, hist: list[dict], state_dir: Path = STATE_DIR) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = state_dir / "lineage.json.tmp"
    tmp.write_text(json.dumps(pop, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_dir / "lineage.json")
    (state_dir / "history.jsonl").write_text(
        "".join(json.dumps(h, ensure_ascii=False) + "\n" for h in hist), encoding="utf-8")


def living(pop: dict) -> list[dict]:
    return [ln for ln in pop["lineages"] if ln["alive"]]


# ------------------------------------------------------------------ results
def apply_result(pop: dict, rec: dict, result: str) -> None:
    """WIN / LOSS / VOID / NO_RESULT for one history record -> its lineage."""
    rec["result"] = result
    ln = next((x for x in pop["lineages"] if x["lineage_id"] == rec["lineage_id"]), None)
    if ln is None or rec.get("applied"):
        return
    rec["applied"] = True
    ln["holding"] = None
    if result == "WIN":
        ln["bankroll"] = round(ln["bankroll"] + ln["stake"] * (rec["price"] - 1.0), 2)
        ln["wins"] += 1
        ln["to_breed"] = True
    elif result == "LOSS":
        ln["bankroll"] = round(ln["bankroll"] - ln["stake"], 2)
        ln["losses"] += 1
        ln["alive"] = False                       # one loss is extinction
    ln["last_result"] = result


def grade(pop: dict, hist: list[dict], events: list[dict],
          today: Optional[str] = None) -> list[str]:
    """Grade PENDING picks from Flashscore events; returns flag lines.

    A pick still unmatched UNGRADED_DAYS after its date is released as
    NO_RESULT (stake back, lineage carries on) — never guessed a win or loss,
    and a lineage can't be frozen forever by a match the feed never shows."""
    from data.flashscore_results import find_result
    from engine.picks_ledger import _settle
    today = today or date.today().isoformat()
    out = []
    for rec in hist:
        if rec.get("result") != "PENDING":
            continue
        ev = find_result(events, rec["home"], rec["away"], rec["date"])
        if not ev:
            if (date.fromisoformat(today) - date.fromisoformat(rec["date"])).days > UNGRADED_DAYS:
                rec["graded_by"] = f"unmatched after {UNGRADED_DAYS} days"
                apply_result(pop, rec, "NO_RESULT")
                out.append(rec)
            continue
        if ev["finished_regular"]:
            hg, ag = ev["fthg"], ev["ftag"]
            res = {"won": "WIN", "lost": "LOSS", "void": "VOID"}.get(
                _settle(rec["market_key"], hg, ag))
            if res is None:
                continue
            rec["score"] = f"{hg}-{ag}"
            rec["graded_by"] = "flashscore"
        elif ev["finished_other"]:
            res = "NO_RESULT"
        else:
            continue
        apply_result(pop, rec, res)
        out.append(rec)
    return [f"AI Survivor: graded {len(out)} pick(s)"] if out else []


# ----------------------------------------------------------------- breeding
def breed(pop: dict, today: str) -> int:
    """Reproduce lineages that won since the last breeding. Returns births.

    Runs on EVERY daily run (grade -> breed -> select), not once per day: a
    once-per-day guard let the 7am run "use up" the day before any result was
    in, so the evening's winners never reproduced (2026-10-03). Double
    breeding can't happen — `to_breed` is cleared when a lineage breeds. A
    winner already holding a pending pick waits until that pick is graded."""
    survivors = living(pop)
    winners = [ln for ln in survivors if ln.get("to_breed") and not ln.get("holding")]
    slots = {ln["lineage_id"]: 1 for ln in survivors}
    spare = max(0, MAX_LINEAGES - len(survivors))
    for ln in sorted(winners, key=lambda x: -x["bankroll"]):
        if spare <= 0:
            break
        extra = min(OFFSPRING_PER_WIN - 1, spare)
        slots[ln["lineage_id"]] += extra
        spare -= extra
    births = 0
    new = [ln for ln in pop["lineages"] if not ln["alive"]]    # keep the dead on record
    for ln in survivors:
        if ln.get("to_breed") and not ln.get("holding"):
            ln["to_breed"] = False
            n = slots[ln["lineage_id"]]
            if n > 1:
                share = ln["bankroll"] / n
                for _ in range(n):
                    new.append(_lineage(ln["lineage_id"], ln["generation"] + 1, share, today))
                    births += 1
                ln["alive"], ln["retired"] = False, today      # parent retires into children
                new.append(ln)
                continue
            ln["generation"] += 1
        new.append(ln)
    if not living({"lineages": new}):
        new.append(_lineage(None, 0, STARVATION_FLOOR, today))  # starvation floor
        births += 1
    pop["lineages"] = new
    pop["last_bred_date"] = today
    return births


# ---------------------------------------------------------------- selection
_CERT = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _is_under(key: str) -> bool:
    return "|Under" in key or "& Under" in key or key.startswith("UNDER_")


def candidates(board: list, target: str, now: Optional[datetime] = None) -> list:
    """Board singles a lineage may hold: deployed, on the target day, not
    started, priced. Ranked most-likely-to-win first."""
    now = now or datetime.now(timezone.utc)
    out = []
    for b in board:
        if not (b.on_deploy_shortlist and b.probs is not None and b.best_market_key
                and b.best_price and b.best_model_prob):
            continue
        if (b.kickoff_date or "")[:10] != target:
            continue
        ko = getattr(b, "kickoff_utc", None)
        if ko:
            try:
                if datetime.fromisoformat(str(ko).replace("Z", "+00:00")) <= now:
                    continue
            except ValueError:
                pass
        if getattr(b, "news_level", None) == "RISK":
            continue
        out.append(b)
    out.sort(key=lambda b: (_is_under(b.best_market_key),
                            _CERT.get(b.certainty, 2) == 2, -b.best_model_prob))
    return out


def select(pop: dict, hist: list[dict], board: list, target: str,
           now: Optional[datetime] = None) -> list[dict]:
    """Give every free living lineage one pick for `target`. Idempotent: a
    lineage already holding a pick for that day keeps it."""
    from engine import markets as mkt
    held = {r["lineage_id"] for r in hist if r["date"] == target}
    taken = {r["fixture"] for r in hist if r["date"] == target}
    free = sorted((ln for ln in living(pop)
                   if ln["lineage_id"] not in held and not ln.get("holding")),
                  key=lambda x: -x["bankroll"])
    picks = [b for b in candidates(board, target, now)
             if b.fixture.split(" (")[0] not in taken]
    new = []
    for ln, b in zip(free, picks):
        p = b.probs
        rec = {"date": target, "lineage_id": ln["lineage_id"], "generation": ln["generation"],
               "fixture": b.fixture.split(" (")[0], "home": p.home_team, "away": p.away_team,
               "league": b.fixture.rsplit("(", 1)[-1].rstrip(")").strip(),
               "market_key": b.best_market_key,
               "pick": mkt.display(b.best_market_key, p.home_team, p.away_team),
               "price": b.best_price, "chance": round(b.best_model_prob, 4),
               "certainty": b.certainty, "tier": b.tier, "code": b.booking_code,
               "kickoff_utc": getattr(b, "kickoff_utc", None), "stake": ln["stake"],
               "result": "PENDING"}
        ln["holding"] = {"date": target, "fixture": rec["fixture"], "pick": rec["pick"],
                         "price": rec["price"]}
        hist.append(rec)
        new.append(rec)
    return new


# ------------------------------------------------------------------ report
def report(pop: dict, hist: list[dict], target: str) -> str:
    alive = living(pop)
    dead = [ln for ln in pop["lineages"] if not ln["alive"] and not ln.get("retired")]
    gen = max((ln["generation"] for ln in alive), default=0)
    graded = [h for h in hist if h.get("result") in ("WIN", "LOSS")]
    w = sum(h["result"] == "WIN" for h in graded)
    L = ["🧬 AI SURVIVOR",
         f"Generation {gen} · {len(alive)} alive · {len(dead)} extinct · lifeforce "
         f"£{sum(ln['bankroll'] for ln in alive):.2f} (genesis £{GENESIS_BANKROLL:.0f})",
         f"Record {w}W-{len(graded) - w}L"
         + (f" ({100 * w / len(graded):.0f}%)" if graded else "")]
    recent = [h for h in hist if h.get("result") in ("WIN", "LOSS", "VOID")][-8:]
    if recent:
        L.append("Latest results:")
        for h in recent:
            mark = {"WIN": "✅", "LOSS": "💀", "VOID": "↩"}[h["result"]]
            px = f" @{h['price']:.2f}" if h.get("price") else ""
            L.append(f" {mark} {h['fixture']} — {h.get('pick') or '?'}{px}"
                     + (f" ({h['score']})" if h.get("score") else ""))
    today = [h for h in hist if h["date"] == target and h.get("result") == "PENDING"]
    by_id = {ln["lineage_id"]: ln for ln in pop["lineages"]}
    if today:
        L.append(f"Holding for {target}:")
        for h in sorted(today, key=lambda h: -by_id.get(h["lineage_id"], {}).get("bankroll", 0)):
            ln = by_id.get(h["lineage_id"], {})
            L.append(f" • {h['lineage_id'][3:9]} G{h['generation']} £{ln.get('bankroll', 0):.2f}"
                     f" → {h['fixture']}: {h['pick']} @{h['price']:.2f} · "
                     f"{h['chance'] * 100:.0f}% {h.get('certainty') or ''}"
                     + (f" · code {h['code']}" if h.get("code") else ""))
    elif alive:
        L.append(f"No pick held for {target} yet (no eligible fixture on the board).")
    return "\n".join(L)


def daily(board: list, target: str, events: list[dict], today: Optional[str] = None,
          state_dir: Path = STATE_DIR) -> tuple[str, list[str]]:
    """Grade -> breed -> select -> save. Returns (report text, flags)."""
    pop, hist = load(state_dir)
    today = today or date.today().isoformat()
    flags = grade(pop, hist, events, today)
    births = breed(pop, today)
    if births:
        flags.append(f"AI Survivor: {births} lineage(s) born")
    new = select(pop, hist, board, target)
    flags.append(f"AI Survivor: {len(living(pop))} alive, {len(new)} new pick(s) for {target}")
    save(pop, hist, state_dir)
    return report(pop, hist, target), flags
