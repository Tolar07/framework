"""
THE MONEY DESK - a daily, rules-only decision-maker that puts PAPER lanes on small real stakes to test them,
steps the winners up and drops the losers back to paper. It acts by default; the Architect sees every decision in
the Control Room app with its evidence and can VETO it (undone at once) or AGREE.

The Architect, 2026-11-13: "most times I tend to allocate [funds] to anything responsible to tag as paper ... I want
not all the time I have to do the money decision. I want you to be able to make some money decision. I will still
have the power to veto it and change it, but make some money decisions and show me and tell me, and I will agree or
not. ... Then everything should be updated on the app too, so I can see it on the app."

LANES (paper records the framework already keeps, with a SportyBet event id and a market the desk can book):
  list:<list>                 each list of the live list test (engine/list_picks.py): the list's picks the
                              framework did NOT agree with.
  analyst:disagree:<list>     the analyst's DISAGREE and NO VIEW picks of a list (engine/analyst.py). AGREE picks
  analyst:no_view:<list>      are already on money at NGN 500 by the Architect's own rule: never a desk lane, never
                              booked here.
  lower:<gap band>            the lower-league value paper board (engine/lower_league_value.py), by gap band.
  africa:value                the Africa paper board's value picks (engine/africa_paper.py, national-team model).
Basketball is inside: the two basketball totals lists are lanes like the football ones (SportyBet's basketball total).

RULES (config/money_desk.json - the Architect's to change; no model is asked, it is arithmetic on the records):
  PROMOTE     paper -> NGN 200 a pick: 30+ graded paper picks, paper return above zero, and a win rate above the
              average chance their prices implied.
  STEP UP     200 -> 500 -> 1,000, one step a decision: 30+ REAL graded picks since the lane went on money at a
              return of +5% or better, and 7 days since its last step.
  BACK TO PAPER   a real return of -15% or worse over 20+ real graded picks. The paper record keeps running; the
              lane needs 30 NEW paper picks before it can be promoted again.
HARD CAPS (constants below - the config cannot lift them): NGN 1,000 a pick; 5 lanes on money at once; NGN 5,000 of
desk stakes per UTC kick-off day (soonest kick-offs first, the rest stay paper that day); SportyBet account 1 only;
singles only. The desk writes its own files and nothing else: no other section, stake, threshold or rule of any bot.

DECISIONS  MD-<n>, time, lane, from -> to, the rule that fired, the evidence, status acting -> agreed / vetoed.
  /veto MD-n   (Telegram, the Architect's chat only) undoes it at once - the lane goes back to its previous stake,
               its unplayed desk picks leave the bot's file - and the desk may not make that same move for that lane
               for 14 days.   /agree MD-n   marks it confirmed.
  Every vote is also one line in memory/money_desk_votes.jsonl; each sweep replays the log, so a vote can never be
  lost to two jobs writing at once.

BOOKING (every sweep): a money lane's pick starting within BOOK_WINDOW hours and not within 20 minutes is booked as
a SportyBet single from SportyBet's own match page (ids never assumed) and written to
output/money_desk/stake_<kick-off date>.json, the same shape as the analyst's agree file plus `stake_ngn` and
`lane`; the SportyBet bot places it (sportybet-agent place.py, section `desk`). A list pick that turns AGREE after
it was booked is taken out again (the analyst's NGN 500 covers it).
REAL RECORD of a lane: the picks the desk booked for it since it went on money, at the booked price.

Undo: MONEY_DESK=0 (framework repo variable, passed in universe.yml) - no lane on money: nothing is booked, every
unplayed desk pick leaves the bot's files, no decision is made. The bot's own switch is SB_MONEY_DESK=0.
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine import analyst as an
from engine import list_picks as lp

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "money_desk.json"
VOTES = "memory/money_desk_votes.jsonl"

# ---- HARD CAPS: not read from the config, so no rule change can lift them
MAX_STAKE = 1000                      # NGN a pick
MAX_LANES = 5                         # lanes on money at once
DAY_CAP = 5000                        # NGN of desk stakes per UTC kick-off day
ACCOUNTS = [1]                        # SportyBet account 1 only
MAX_TRIES = 6                         # booking attempts per pick

DEFAULTS = {
    "promote": {"min_graded": 30, "min_roi": 0.0, "stake": 200},
    "step_up": {"min_real_graded": 30, "min_roi": 0.05, "ladder": [200, 500, 1000], "cooldown_days": 7},
    "back_to_paper": {"min_real_graded": 20, "max_roi": -0.15, "new_paper_needed": 30},
    "veto_block_days": 14,
    "book_lead_min": 20,
    "book_window_h": 4,
    "decide_hour_utc": 6,
}
LOWER_SEL = {"BTTS Yes": ("29", "", "Yes"), "BTTS No": ("29", "", "No"),
             **{f"{s} {ln}": ("18", f"total={ln}", f"{s} {ln}") for s in ("Over", "Under") for ln in ("1.5", "2.5", "3.5")}}
AFRICA_SEL = {"1": ("1", "", "Home"), "X": ("1", "", "Draw"), "2": ("1", "", "Away"),
              "1X": ("10", "", "Home or Draw"), "12": ("10", "", "Home or Away"), "X2": ("10", "", "Draw or Away"),
              "BY": ("29", "", "Yes"), "BN": ("29", "", "No"),
              **{f"{k}{ln}": ("18", f"total={ln}", f"{s} {ln}") for k, s in (("O", "Over"), ("U", "Under"))
                 for ln in ("1.5", "2.5", "3.5")}}
_EVENT = "https://www.sportybet.com/api/ng/factsCenter/event?eventId={eid}&productId=3"


def enabled(env=os.environ) -> bool:
    return (env.get("MONEY_DESK") or "1").strip() != "0"


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except ValueError:
        return default


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%MZ")


def _time(s) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def rules(root: Path = ROOT) -> dict:
    """The desk's rules from config/money_desk.json over the defaults, held inside the hard caps."""
    doc = _read(root / "config" / "money_desk.json", {})
    r = {k: ({**v, **(doc.get(k) or {})} if isinstance(v, dict) else doc.get(k, v)) for k, v in DEFAULTS.items()}
    ladder = sorted({int(s) for s in r["step_up"]["ladder"] if 0 < int(s) <= MAX_STAKE}) or [200]
    r["step_up"]["ladder"] = ladder
    r["promote"]["stake"] = min(max(int(r["promote"]["stake"]), 1), MAX_STAKE)
    return r


# ---------------------------------------------------------------- the lanes and their picks
def _list_sel(key: str, line=None):
    """A list pick's SportyBet market, specifier and outcome: the analyst's own table (full-time markets, 1st-half
    goals, corners, bookings, the basketball total), so the desk and the analyst can never book a pick differently."""
    return an._target(key or "", line)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def gather(root: Path = ROOT) -> tuple[dict, dict]:
    """({lane id: {"title", "bookable", "why"}}, {pick id: pick}) from the paper books. Each pick: event, ko,
    home, away, pick, price, result (1 / 0 / None), sel (SportyBet market, specifier, outcome), lanes (the most
    specific first), agree (the analyst agreed: never a desk pick)."""
    lanes: dict = {}
    picks: dict = {}
    # the analyst's verdicts: the full-time book's and (since the analyst also reads the lines book) the lines book's
    verdicts = {**_read(root / "data" / "analyst" / "state.json", {}),
                **_read(root / "data" / "analyst" / "state_lines.json", {})}
    for source in ("universe", "lines"):
        book = lp.load_book(source, root / "data" / "list_picks")
        for lid, (title, src, _market) in lp.LISTS.items():
            if src != source:
                continue
            lanes[f"list:{lid}"] = {"title": title, "bookable": True, "why": None}
        for pid, p in (book.get("picks") or {}).items():
            lid = p.get("list")
            if f"list:{lid}" not in lanes or not p.get("price"):
                continue
            verdict = (verdicts.get(pid) or {}).get("verdict") if isinstance(verdicts.get(pid), dict) else None
            mine = [f"list:{lid}"]
            if pid in verdicts and lanes[f"list:{lid}"]["bookable"]:      # a pick the analyst has looked at
                kind = "disagree" if verdict == "disagree" else "no_view"
                lanes.setdefault(f"analyst:{kind}:{lid}", {
                    "title": f"{title} - framework {'disagrees' if kind == 'disagree' else 'has no view'}",
                    "bookable": True, "why": None})
                mine.insert(0, f"analyst:{kind}:{lid}")
            picks[pid] = {"pid": pid, "event": p.get("event"), "ko": p.get("ko"), "home": p.get("home"),
                          "away": p.get("away"), "pick": p.get("pick"), "price": p["price"],
                          "result": p["result"] if p.get("result") in (0, 1) else None, "sel": _list_sel(p.get("key"), p.get("line")),
                          "sport": p.get("sport", "football"), "list": lid, "title": title,
                          "agree": verdict == "agree", "lanes": [] if verdict == "agree" else mine}
    low = _read(root / "data" / "lower_league_value" / "book.json", {}).get("picks") or {}
    for gid, p in low.items():
        if not p.get("price") or not p.get("band"):
            continue
        lane = f"lower:{_slug(p['band'])}"
        lanes.setdefault(lane, {"title": f"Lower-league value, gap {p['band']}", "bookable": True, "why": None})
        picks[f"lower|{gid}"] = {"pid": f"lower|{gid}", "event": gid, "ko": p.get("ko"), "home": p.get("home"),
                                 "away": p.get("away"), "pick": p.get("option"), "price": p["price"],
                                 "result": int(bool(p["won"])) if "won" in p else None,
                                 "sel": LOWER_SEL.get(p.get("option")), "sport": "football", "list": "lower_league_value",
                                 "title": lanes[lane]["title"], "agree": False, "lanes": [lane]}
    afr = _read(root / "data" / "africa_paper" / "book.json", {})
    for rid, p in afr.items():
        if not isinstance(p, dict) or not p.get("price") or p.get("kind") != "model" or not p.get("value"):
            continue
        lanes.setdefault("africa:value", {"title": "Africa paper board - value picks", "bookable": True, "why": None})
        res = {"won": 1, "lost": 0}.get(p.get("result"))
        picks[f"africa|{rid}"] = {"pid": f"africa|{rid}", "event": rid, "ko": p.get("kickoff_utc"), "home": p.get("home"),
                                  "away": p.get("away"), "pick": p.get("pick"), "price": p["price"], "result": res,
                                  "sel": AFRICA_SEL.get(p.get("key")), "sport": "football", "list": "africa_paper",
                                  "title": "Africa paper board - value picks", "agree": False, "lanes": ["africa:value"]}
    return lanes, picks


def _stats(ps: list[dict]) -> dict:
    """list_picks._stats (graded, won, return, 90% range at 100+) plus the average chance the prices implied."""
    s = lp._stats(ps)
    g = [p for p in ps if p["result"] in (0, 1)]
    s["implied"] = round(sum(1 / p["price"] for p in g) / len(g), 4) if g else None
    s["win_rate"] = round(s["won"] / len(g), 4) if g else None
    return s


def _real(lane_id: str, lane: dict, book: dict, picks: dict) -> dict:
    """The lane's real record: what the desk booked for it since it went on money, at the booked price."""
    since = lane.get("since") or ""
    rows = [{"price": e.get("price") or 0, "result": (picks.get(pid) or e).get("result")}
            for pid, e in book.items()
            if e.get("lane") == lane_id and e.get("code") and not e.get("pulled") and since
            and (e.get("booked") or "") >= since and e.get("price")]
    return _stats(rows)


def refresh(state: dict, lanes: dict, picks: dict, book: dict) -> None:
    """Every lane's paper and real record, written into the state (stake and history are kept)."""
    known = state.setdefault("lanes", {})
    for lid, meta in lanes.items():
        ln = known.setdefault(lid, {"stake": 0, "since": None, "last_step": None, "paper_from": None, "blocks": {}})
        mine = [p for p in picks.values() if lid in p["lanes"]]
        fresh = [p for p in mine if not ln.get("paper_from") or (p.get("ko") or "") >= ln["paper_from"]]
        ln.update({"title": meta["title"], "bookable": meta["bookable"], "why": meta["why"],
                   "paper": _stats(mine), "paper_new": _stats(fresh), "real": _real(lid, ln, book, picks)})


def on_money(state: dict) -> list[str]:
    return [lid for lid, ln in (state.get("lanes") or {}).items() if ln.get("stake", 0) > 0]


# ---------------------------------------------------------------- decisions
def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def _line(tag: str, s: dict) -> str:
    if not s.get("graded"):
        return f"{tag}: no graded picks"
    return (f"{tag}: {s['graded']} graded, {s['won']} won, return {_pct(s['roi'])}, win rate "
            f"{s['win_rate'] * 100:.1f}% v {s['implied'] * 100:.1f}% priced")


def _blocked(ln: dict, move: str, now: datetime) -> bool:
    until = _time((ln.get("blocks") or {}).get(move))
    return until is not None and now < until


def _restake(book: dict, lane_id: str, stake: int, now: datetime) -> int:
    """A lane's unplayed desk picks follow it down: lower stake, or out of the bot's file when it is paper."""
    n = 0
    for e in book.values():
        ko = _time(e.get("ko"))
        if e.get("lane") != lane_id or not e.get("code") or e.get("pulled") or ko is None or ko <= now:
            continue
        if stake <= 0:
            e["pulled"] = "lane back to paper"
            n += 1
        elif e.get("stake", 0) > stake:
            e["stake"] = stake
            n += 1
    return n


def _apply(state: dict, dec: dict, lane_id: str, to: int, rule: str, now: datetime, book: dict) -> dict:
    ln = state["lanes"][lane_id]
    d = {"id": f"MD-{dec.get('next', 1)}", "at": _stamp(now), "lane": lane_id, "title": ln.get("title"),
         "from": ln.get("stake", 0), "to": to, "rule": rule,
         "evidence": {"paper": ln.get("paper_new") or ln.get("paper"), "real": ln.get("real")},
         "text": f"{_line('paper', ln.get('paper_new') or {})}; {_line('real', ln.get('real') or {})}",
         "status": "acting",
         "prev": {k: ln.get(k) for k in ("stake", "since", "last_step", "paper_from")}}
    dec["next"] = dec.get("next", 1) + 1
    dec.setdefault("decisions", []).append(d)
    if d["from"] <= 0 < to:
        ln["since"] = _stamp(now)
    if to <= 0:
        ln.update({"since": None, "paper_from": _stamp(now), "paper_new": _stats([])})   # 30 NEW picks from here
    ln.update({"stake": to, "last_step": _stamp(now)})
    _restake(book, lane_id, to, now)
    return d


def decide(state: dict, dec: dict, book: dict, now: datetime, r: dict) -> list[dict]:
    """The day's decisions: losers back to paper first (it frees a place), then steps up, then promotions."""
    new = []
    up, down, pro = r["step_up"], r["back_to_paper"], r["promote"]
    ladder = up["ladder"]
    for lid in sorted(on_money(state)):
        ln = state["lanes"][lid]
        real, stake = ln.get("real") or {}, ln["stake"]
        if (real.get("graded", 0) >= down["min_real_graded"] and real.get("roi") is not None
                and real["roi"] <= down["max_roi"] and not _blocked(ln, f"{stake}>0", now)):
            new.append(_apply(state, dec, lid, 0, f"back to paper: real return {_pct(real['roi'])} over "
                              f"{real['graded']} real picks (rule: {_pct(down['max_roi'])} or worse over "
                              f"{down['min_real_graded']}+)", now, book))
            continue
        higher = [s for s in ladder if s > stake]
        last = _time(ln.get("last_step"))
        if (higher and real.get("graded", 0) >= up["min_real_graded"] and real.get("roi") is not None
                and real["roi"] >= up["min_roi"] and (last is None or now - last >= timedelta(days=up["cooldown_days"]))
                and not _blocked(ln, f"{stake}>{higher[0]}", now)):
            new.append(_apply(state, dec, lid, higher[0], f"step up: real return {_pct(real['roi'])} over "
                              f"{real['graded']} real picks (rule: {_pct(up['min_roi'])} or better over "
                              f"{up['min_real_graded']}+, {up['cooldown_days']} days since the last step)", now, book))
    cands = []
    for lid, ln in state["lanes"].items():
        s = ln.get("paper_new") or {}
        need = down["new_paper_needed"] if ln.get("paper_from") else pro["min_graded"]   # dropped back: NEW picks
        if (ln.get("stake", 0) <= 0 and ln.get("bookable") and s.get("graded", 0) >= need
                and s.get("roi") is not None and s["roi"] > pro["min_roi"] and s["win_rate"] > s["implied"]
                and not _blocked(ln, f"0>{pro['stake']}", now)):
            cands.append((-s["roi"], lid))
    for _roi, lid in sorted(cands):
        if len(on_money(state)) >= MAX_LANES:
            break
        s = state["lanes"][lid]["paper_new"]
        new.append(_apply(state, dec, lid, pro["stake"], f"promote: paper return {_pct(s['roi'])} over {s['graded']} "
                          f"graded picks, win rate above the price (rule: {pro['min_graded']}+ graded, return above "
                          f"{_pct(pro['min_roi'])})", now, book))
    return new


# ---------------------------------------------------------------- veto / agree
def _vote_one(state: dict, dec: dict, book: dict, did: str, kind: str, at: datetime, r: dict) -> str:
    d = next((x for x in dec.get("decisions") or [] if x["id"].lower() == did.strip().lower()), None)
    if d is None:
        acting = ", ".join(x["id"] for x in dec.get("decisions") or [] if x["status"] == "acting") or "none"
        return f"No desk decision {did}. Acting now: {acting}."
    if d["status"] == "vetoed":
        return f"{d['id']} is already vetoed."
    if kind == "agree":
        if d["status"] == "agreed":
            return f"{d['id']} is already agreed."
        d.update({"status": "agreed", "decided_at": _stamp(at)})
        return f"AGREED {d['id']}: {d['title']} {_money(d['from'])} -> {_money(d['to'])} stays."
    ln = (state.get("lanes") or {}).get(d["lane"])
    later = [x for x in dec["decisions"] if x["lane"] == d["lane"] and x["status"] != "vetoed"
             and int(x["id"].split("-")[1]) > int(d["id"].split("-")[1])]
    if ln is None or later:
        return (f"{d['id']} is not the lane's latest decision ({later[-1]['id']} came after it): veto that one."
                if later else f"{d['id']}: its lane is no longer kept.")
    prev = d.get("prev") or {"stake": d["from"]}
    back = int(prev.get("stake") or 0)
    full = back > 0 and ln.get("stake", 0) <= 0 and len(on_money(state)) >= MAX_LANES
    if full:                                    # the cap holds even for an undo: the lane waits on paper
        back = 0
    else:
        ln.update({k: prev.get(k) for k in ("since", "last_step", "paper_from")})
    ln["stake"] = back
    ln.setdefault("blocks", {})[f"{d['from']}>{d['to']}"] = _stamp(at + timedelta(days=r["veto_block_days"]))
    _restake(book, d["lane"], back, at)
    d.update({"status": "vetoed", "decided_at": _stamp(at)})
    note = f" ({MAX_LANES} lanes are already on money, so it waits on paper)" if full else ""
    return (f"VETOED {d['id']}: {d['title']} is back at {_money(back)}{note}. The desk will not make that move "
            f"again for {r['veto_block_days']} days.")


def _money(stake: int) -> str:
    return "paper" if not stake or stake <= 0 else f"NGN {stake:,}"


def read_votes(root: Path = ROOT, extra: str = "") -> list[dict]:
    """The vote log, oldest first: this checkout's lines and any passed in (the newest copy fetched by the sweep)."""
    p = root / VOTES
    text = (p.read_text(encoding="utf-8") if p.exists() else "") + "\n" + (extra or "")
    seen, out = set(), []
    for ln in text.splitlines():
        try:
            v = json.loads(ln)
        except ValueError:
            continue
        key = (v.get("id"), v.get("vote"), v.get("at")) if isinstance(v, dict) else None
        if key and key not in seen and v.get("vote") in ("veto", "agree") and _time(v.get("at")):
            seen.add(key)
            out.append(v)
    return sorted(out, key=lambda v: v["at"])


def replay(state: dict, dec: dict, book: dict, votes: list[dict], r: dict) -> int:
    """Apply every vote not yet applied (a vote on a decision already vetoed or agreed changes nothing)."""
    n = 0
    for v in votes:
        d = next((x for x in dec.get("decisions") or [] if x["id"].lower() == str(v["id"]).lower()), None)
        if d is None or d["status"] == "vetoed" or (v["vote"] == "agree" and d["status"] == "agreed"):
            continue
        before = d["status"]
        _vote_one(state, dec, book, d["id"], v["vote"], _time(v["at"]), r)
        n += d["status"] != before
    return n


def vote(did: str, kind: str, now: datetime | None = None, root: Path = ROOT) -> str:
    """/veto MD-n and /agree MD-n (output/telegram_commands.py, the Architect's chat only): applied to the desk's
    files at once and added to the vote log, which every sweep replays."""
    now = now or datetime.now(UTC)
    state, dec, book = _load(root)
    r = rules(root)
    msg = _vote_one(state, dec, book, did, kind, now, r)
    d = next((x for x in dec.get("decisions") or [] if x["id"].lower() == did.strip().lower()), None)
    if d is not None and d.get("decided_at") == _stamp(now):
        p = root / VOTES
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": d["id"], "vote": kind, "at": _stamp(now)}) + "\n")
        lanes, picks = gather(root)
        refresh(state, lanes, picks, book)
        _save(root, state, dec, book, now, picks)
    return msg


def summary(root: Path = ROOT) -> str:
    """/desk: the lanes on money and the decisions still acting."""
    state, dec, _book = _load(root)
    lanes = state.get("lanes") or {}
    money = [f"  {ln.get('title')}: {_money(ln['stake'])} a pick; {_line('real', ln.get('real') or {})}"
             for lid, ln in sorted(lanes.items()) if ln.get("stake", 0) > 0]
    acting = [f"  {d['id']} {d['title']}: {_money(d['from'])} -> {_money(d['to'])}. {d['rule']}"
              for d in dec.get("decisions") or [] if d["status"] == "acting"]
    return ("MONEY DESK" + ("" if state.get("enabled", True) else " - OFF (MONEY_DESK=0)")
            + f"\n{len(lanes)} lanes, {len(money)} on money (cap {MAX_LANES}; NGN {MAX_STAKE:,} a pick, "
            f"NGN {DAY_CAP:,} a day)\n" + ("\n".join(money) or "  no lane on money") + "\n\nActing decisions:\n"
            + ("\n".join(acting) or "  none") + "\n\n/veto MD-n undoes one, /agree MD-n confirms it.")


# ---------------------------------------------------------------- booking
def selection(event: dict, sel: tuple) -> dict | None:
    """The SportyBet selection on the match page for (market id, specifier, outcome), from SportyBet's own ids
    (never assumed), open markets and active outcomes only. None when it is not there (the pick stays paper)."""
    mid, spec, want = sel
    want = want.strip().lower()
    for m in event.get("markets") or []:
        if str(m.get("id")) != mid or (m.get("specifier") or "") != spec or m.get("status") not in (None, 0, "0"):
            continue
        for o in m.get("outcomes") or []:
            desc = (o.get("desc") or "").strip().lower()
            same = desc == want or (want.split(" ")[0] in ("over", "under") and desc.split(" ")[0] == want.split(" ")[0])
            if same and o.get("id") is not None and o.get("isActive", 1) in (1, "1", True, None):
                try:
                    odds = float(o.get("odds"))
                except (TypeError, ValueError):
                    odds = None
                return {"eventId": event.get("eventId"), "marketId": m.get("id"), "specifier": spec,
                        "outcomeId": o.get("id"), "odds": odds}
    return None


def book_picks(state: dict, picks: dict, book: dict, now: datetime, r: dict, get=None, book_code=None) -> dict:
    """Book the money lanes' coming picks, soonest kick-off first, inside the caps. Returns counts."""
    get, book_code = get or an._sb_get, book_code or an._book
    n = {"booked": 0, "capped": 0, "pulled": 0}
    lanes = state.get("lanes") or {}
    for pid, e in book.items():                          # a pick the analyst now agrees with is the analyst's
        ko = _time(e.get("ko"))
        if e.get("code") and not e.get("pulled") and ko and ko > now and (picks.get(pid) or {}).get("agree"):
            e["pulled"] = "the analyst agreed: its NGN 500 covers it"
            n["pulled"] += 1
    if not enabled():
        for e in book.values():
            ko = _time(e.get("ko"))
            if e.get("code") and not e.get("pulled") and ko and ko > now:
                e["pulled"] = "MONEY_DESK=0"
                n["pulled"] += 1
        return n
    lead, window = timedelta(minutes=r["book_lead_min"]), timedelta(hours=r["book_window_h"])
    money = set(sorted(on_money(state))[:MAX_LANES])          # never more than the cap, whatever the state says
    day: dict = {}
    for e in book.values():
        if e.get("code") and not e.get("pulled"):
            day[(e.get("ko") or "")[:10]] = day.get((e.get("ko") or "")[:10], 0) + int(e.get("stake") or 0)
    cands = []
    for pid, p in picks.items():
        ko = _time(p.get("ko"))
        lane = next((x for x in p["lanes"] if x in money), None)
        if (lane is None or p["agree"] or p["result"] is not None or not p.get("sel") or not p.get("event")
                or ko is None or not (now + lead < ko <= now + window) or (book.get(pid) or {}).get("code")
                or (book.get(pid) or {}).get("pulled") or (book.get(pid) or {}).get("tries", 0) >= MAX_TRIES):
            continue
        cands.append((ko, pid, lane))
    for ko, pid, lane in sorted(cands):
        p = picks[pid]
        stake = min(int(lanes[lane]["stake"]), MAX_STAKE)
        d = ko.strftime("%Y-%m-%d")
        if day.get(d, 0) + stake > DAY_CAP:              # the rest of that day stays paper
            n["capped"] += 1
            continue
        e = book.setdefault(pid, {"tries": 0})
        e["tries"] = e.get("tries", 0) + 1
        try:
            sel = selection((get(_EVENT.format(eid=p["event"])) or {}).get("data") or {}, p["sel"])
        except Exception:  # noqa: BLE001 - SportyBet down: tried again next sweep
            sel = None
        code = book_code(sel) if sel else None
        if not code:
            continue
        e.update({"lane": lane, "stake": stake, "code": code, "market_id": sel["marketId"],
                  "specifier": sel["specifier"], "outcome_id": sel["outcomeId"], "price": sel.get("odds") or p["price"],
                  "ko": p["ko"], "event": p["event"], "home": p["home"], "away": p["away"], "pick": p["pick"],
                  "sport": p["sport"], "list": p["list"], "title": p["title"], "booked": _stamp(now)})
        day[d] = day.get(d, 0) + stake
        n["booked"] += 1
    return n


def stake_files(book: dict, now: datetime) -> dict[str, dict]:
    """{kick-off date: the bot's file}, from yesterday on. A day whose picks were all taken out is written empty,
    so a pick that left the desk also leaves the file the bot reads."""
    floor = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    out: dict = {}
    for pid, e in book.items():
        d = (e.get("ko") or "")[:10]
        if not e.get("code") or d < floor:
            continue
        doc = out.setdefault(d, {"date": d, "accounts": ACCOUNTS, "max_stake_ngn": MAX_STAKE,
                                 "day_cap_ngn": DAY_CAP, "picks": []})
        if e.get("pulled"):
            continue
        doc["picks"].append({"id": pid, "lane": e["lane"], "list": e.get("list"), "title": e.get("title"), "date": d,
                             "ko": e["ko"], "home": e["home"], "away": e["away"], "pick": e["pick"],
                             "price": e["price"], "code": e["code"], "sb_event_id": e["event"],
                             "market_id": e["market_id"], "specifier": e["specifier"], "outcome_id": e["outcome_id"],
                             "sport": e.get("sport", "football"), "accounts": ACCOUNTS,
                             "stake_ngn": min(int(e["stake"]), MAX_STAKE)})
    for doc in out.values():
        doc["picks"].sort(key=lambda x: x.get("ko") or "")
    return out


# ---------------------------------------------------------------- files
def _load(root: Path) -> tuple[dict, dict, dict]:
    out = root / "output" / "money_desk"
    return (_read(out / "state.json", {}), _read(out / "decisions.json", {"next": 1, "decisions": []}),
            _read(root / "data" / "money_desk" / "book.json", {}))


def _save(root: Path, state: dict, dec: dict, book: dict, now: datetime, picks: dict) -> None:
    out = root / "output" / "money_desk"
    out.mkdir(parents=True, exist_ok=True)
    (root / "data" / "money_desk").mkdir(parents=True, exist_ok=True)
    for pid, e in book.items():                          # each booked pick carries its result, for the app
        e["result"] = (picks.get(pid) or {}).get("result", e.get("result"))
    (root / "data" / "money_desk" / "book.json").write_text(json.dumps(book, ensure_ascii=False, separators=(",", ":")),
                                                            encoding="utf-8")
    state.update({"built": _stamp(now), "enabled": enabled(), "accounts": ACCOUNTS,
                  "caps": {"max_stake_ngn": MAX_STAKE, "max_lanes": MAX_LANES, "day_cap_ngn": DAY_CAP}})
    (out / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "decisions.json").write_text(json.dumps({"built": _stamp(now), **dec}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    for d, doc in stake_files(book, now).items():
        (out / f"stake_{d}.json").write_text(json.dumps({"built": _stamp(now), **doc}, ensure_ascii=False, indent=1),
                                             encoding="utf-8")


def fresh_votes() -> str:
    """The vote log as it is on the private data repo right now (a /veto sent while this sweep was running)."""
    try:
        from monitor import fdata
        if not fdata.enabled() or fdata._git("fetch", "-q", "origin", "main").returncode != 0:
            return ""
        got = fdata._git("show", f"FETCH_HEAD:{VOTES}")
        return got.stdout if got.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - the local copy is used
        return ""


def _tell(new: list[dict]) -> None:
    """Each new decision to the Architect: the Control Room app shows it from decisions.json (the status feed
    turns a new one into a phone notification); this send follows the notify route, so Telegram carries it only
    when NOTIFY_ROUTE=telegram."""
    owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip() or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    if not new or not owner or not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return
    try:
        from output import notify
        text = "MONEY DESK\n" + "\n".join(
            f"{d['id']} {d['title']}: {_money(d['from'])} -> {_money(d['to'])}. {d['rule']}.\n"
            f"/veto {d['id']} undoes it, /agree {d['id']} confirms it." for d in new)
        notify.send_telegram(text, chat_id=owner, level="info")
    except Exception:  # noqa: BLE001, S110 - the app still shows it from decisions.json
        pass


def attach(now: datetime, root: Path = ROOT, get=None, book_code=None, votes_text: str | None = None) -> str:
    """The universe sweep's hook, after the list test and the analyst: replay the votes, decide once a UTC day,
    book the money lanes' coming picks, write the files."""
    r = rules(root)
    state, dec, book = _load(root)
    lanes, picks = gather(root)
    refresh(state, lanes, picks, book)
    voted = replay(state, dec, book, read_votes(root, fresh_votes() if votes_text is None else votes_text), r)
    new: list[dict] = []
    today = now.strftime("%Y-%m-%d")
    if enabled() and now.hour >= r["decide_hour_utc"] and state.get("decided_day") != today:
        new = decide(state, dec, book, now, r)
        state["decided_day"] = today
    n = book_picks(state, picks, book, now, r, get, book_code)
    refresh(state, lanes, picks, book)
    _save(root, state, dec, book, now, picks)
    _tell(new)
    made = "; ".join(f"{d['id']} {d['lane']} {_money(d['from'])} -> {_money(d['to'])}" for d in new)
    return (f"money desk{'' if enabled() else ' OFF (MONEY_DESK=0)'}: {len(lanes)} lanes, {len(on_money(state))} on "
            f"money, {len(new)} decision(s){' [' + made + ']' if made else ''}, {voted} vote(s) applied, "
            f"{n['booked']} booked, {n['capped']} over the day cap, {n['pulled']} taken out")
