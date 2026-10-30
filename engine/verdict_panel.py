"""
VERDICT PANEL — to-do #5 (the Architect, 2026-10-27), built on the cognitive core (to-do #3).

The verdict becomes a PROBABILITY anchored on the de-margined sharp price (market_prob = sharp_p,
framework PR #177), judged by a panel of FREE models:

    gemini      GEMINI_API_KEY      (Google AI Studio free tier)
    nvidia      NVIDIA_API_KEY      (NVIDIA NIM, free at build.nvidia.com)
    openrouter  OPENROUTER_API_KEY  (":free" models ONLY)

No Anthropic API (the Architect, 2026-10-27: no money for it). A missing key leaves that member
out and the document says which. OPENROUTER MUST NEVER COST MONEY (the Architect, 2026-10-27
13:34): only model ids ending ":free" may be sent (openrouter_guard raises before the call), and an
answer that reports any cost above 0 switches OpenRouter off for the run and is logged. With no
free model on the account the panel runs on Gemini + NVIDIA.

Each member gives its probability for each pick. The panel's probability is

    anchor + sum(w_m * clamp(p_m - anchor, +-MAX_SHIFT)) / sum(w_m)

where anchor = market_prob (else the model's chance) and the weights come from each member's
OUT-OF-SAMPLE record (memory/panel_record.json: every row was predicted before its result was in).
A member that was rate-limited this run, or whose record never beats the others or the anchor,
gets weight 0.

Edge = panel_prob x price - 1 sets the single's stake factor: < 0 -> 0.5, >= EDGE_STRONG -> 1.15,
else 1.0 (approved with #3's multipliers on 2026-10-27, standing order 48; same off switch
COGNITIVE_STAKES). It is applied ONLY where the panel has earned authority in that (domain,
family): >= MIN_EARNED_N graded rows, a lower Brier than the live verdict, and CLV FIRST: on picks
whose close is in, the panel's edge sign must agree with the closing-line move more often than the
live verdict did. Until then it is shadow advice, scored every night (grade()).

The LINE-UP PASS (lineup_pass) runs the panel again at T-75..T-45 min on picks whose line-up check
is in (news_check.py, every 20 min), as a separate "lineup" stage with its own record and authority.
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).parent.parent
PANEL_RECORD = ROOT / "memory" / "panel_record.json"
OUT_DIR = ROOT / "output" / "reasoning"
LEDGER_DIR = ROOT / "output" / "picks"

MAX_SHIFT = 0.08                  # a member moves the anchor at most this far (as the core's firewall)
PROB_FLOOR, PROB_CAP = 0.02, 0.98
EDGE_STRONG = 0.05
STAKE_BY_EDGE = {"negative": 0.5, "positive": 1.0, "strong": 1.15}
MIN_EARNED_N = 30
MIN_CLV_N = 20
BRIER_MARGIN = 0.002
MIN_MEMBER_N = 30                 # below this a member keeps an equal weight
BATCH = 10
TEMPERATURE = 0.15
LINEUP_WINDOW_MIN = (45, 75)      # minutes before kick-off
MAX_HISTORY = 5000

MEMBERS = {
    "gemini": {"key": "GEMINI_API_KEY", "base": "https://generativelanguage.googleapis.com/v1beta/openai",
               "env": "PANEL_GEMINI_MODEL", "prefer": ["gemini-3.5-flash", "gemini-3.5-flash-lite"]},
    "nvidia": {"key": "NVIDIA_API_KEY", "base": "https://integrate.api.nvidia.com/v1",
               "env": "PANEL_NVIDIA_MODEL", "prefer": ["nvidia/nemotron-3.5-lightning-30b-a3b",
                                                       "mistralai/mistral-large-4-1t-a52b"]},
    "openrouter": {"key": "OPENROUTER_API_KEY", "base": "https://openrouter.ai/api/v1",
                   "env": "PANEL_OPENROUTER_MODEL", "prefer": ["google/gemma-4-31b-it:free",
                                                               "google/gemma-4-26b-a4b-it:free",
                                                               "nvidia/nemotron-3.5-super-vl:free"]},
}

PROMPT = """You are one member of a panel that prices sports picks. For each pick give YOUR probability
that it wins ("prob", 0-1).
Rules:
- START from "anchor": the sharp bookmaker's de-margined chance ("anchor_source": "market"), or the
  model's chance when there is no sharp line ("model"). The market is well calibrated: move away from
  the anchor only for a concrete fact in the context (line-ups, absences, the tactical matchup, flags),
  and by at most 0.08.
- Never invent a number, a line-up or a news item (HR59). Inputs that read null or PENDING are
  unknown: unknown is a reason for caution, never for a bigger chance.
- "model_chance" is the framework's own model; when it is far above the anchor it has usually been
  overconfident.
Return JSON only: {"picks": [{"id": <id>, "prob": <0-1>, "why": "<one short sentence>"}]}

PICKS:
"""


class PaidModelError(RuntimeError):
    """An OpenRouter model id that is not ":free" (it could cost money)."""


class ChargedError(RuntimeError):
    """OpenRouter reported a cost above 0 for an answer."""


class RateLimited(RuntimeError):
    pass


def openrouter_guard(model_id: Optional[str]) -> str:
    """Raise unless the id ends ":free". Runs before every OpenRouter call."""
    if not model_id or not str(model_id).endswith(":free"):
        raise PaidModelError(f"OpenRouter model {model_id!r} is not ':free': refused (it could cost money)")
    return model_id


def charged(body: dict) -> float:
    """The cost an OpenRouter answer reports (usage.cost / total_cost), 0.0 when none."""
    u = (body or {}).get("usage") or {}
    total = 0.0
    for k in ("cost", "total_cost", "upstream_inference_cost"):
        try:
            total += float(u.get(k) or 0)
        except (TypeError, ValueError):
            pass
    try:
        total += float(((u.get("cost_details") or {}).get("upstream_inference_cost")) or 0)
    except (TypeError, ValueError):
        pass
    return total


def stakes_on() -> bool:
    from engine import cognitive_core as CC
    return CC.stakes_on()


def _num(v) -> Optional[float]:
    try:
        return None if v is None or (isinstance(v, str) and v.strip() in ("", "PENDING")) else float(v)
    except (TypeError, ValueError):
        return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------- members
def free_openrouter_models(get: Callable) -> list[str]:
    """Ids OpenRouter lists as ":free" AND priced 0 for prompt and completion."""
    r = get(MEMBERS["openrouter"]["base"] + "/models", timeout=30)
    r.raise_for_status()
    out = []
    for m in r.json().get("data") or []:
        p = m.get("pricing") or {}
        try:
            free = float(p.get("prompt", 1)) == 0 and float(p.get("completion", 1)) == 0
        except (TypeError, ValueError):
            free = False
        if str(m.get("id", "")).endswith(":free") and free:
            out.append(m["id"])
    return out


def pick_model(name: str, get: Callable, key: str) -> Optional[str]:
    """The member's model: its env override, else the first preferred id the account lists."""
    spec = MEMBERS[name]
    want = os.getenv(spec["env"], "").strip()
    if name == "gemini" and not want:
        from engine import cognitive_core as CC
        want = CC.model()            # OLP_GEMINI_MODEL, default gemini-3.5-flash (as the core)
    if name == "openrouter":
        try:
            free = free_openrouter_models(get)
        except Exception:  # noqa: BLE001 — can't prove a model is free: don't use OpenRouter
            return None
        cands = ([want] if want else []) + spec["prefer"]
        return next((m for m in cands if m in free and m.endswith(":free")), None)
    if want:
        return want
    try:
        r = get(spec["base"] + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        r.raise_for_status()
        listed = {str(m.get("id", "")).removeprefix("models/") for m in r.json().get("data") or []}
    except Exception:  # noqa: BLE001 — the first preference, unverified
        return spec["prefer"][0]
    return next((m for m in spec["prefer"] if m in listed), spec["prefer"][0])


def _parse(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    i = text.find("{")
    obj, _ = json.JSONDecoder().raw_decode(text[i:] if i >= 0 else text)
    return {p.get("id"): p for p in obj.get("picks") or []}


def ask(name: str, model: str, key: str, rows: list[dict], post: Callable) -> dict:
    """One member, one batch -> {id: prob}. Raises RateLimited / PaidModelError / ChargedError."""
    if name == "openrouter":
        openrouter_guard(model)
    body = {"model": model, "temperature": TEMPERATURE,
            "messages": [{"role": "user", "content": PROMPT + json.dumps(rows, ensure_ascii=False)}]}
    if name == "openrouter":
        body["usage"] = {"include": True}            # so a charge would show up and be caught
    if name != "nvidia":
        body["response_format"] = {"type": "json_object"}
    r = post(MEMBERS[name]["base"] + "/chat/completions", headers={"Authorization": f"Bearer {key}"},
             json=body, timeout=120)
    if getattr(r, "status_code", 200) == 429:
        raise RateLimited(f"{name}: 429")
    r.raise_for_status()
    got = r.json()
    if name == "openrouter" and charged(got) > 0:
        raise ChargedError(f"OpenRouter charged {charged(got)} for {model}")
    out = {}
    for i, p in _parse(got["choices"][0]["message"]["content"]).items():
        v = _num(p.get("prob"))
        if v is not None and 0 <= v <= 1:
            out[i] = v
    return out


# ---------------------------------------------------------------- weights (out of sample)
def load_record(path: Path = PANEL_RECORD) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _brier(p: Optional[float], won: bool) -> Optional[float]:
    return None if p is None else (float(p) - (1.0 if won else 0.0)) ** 2


def member_weights(history: list[dict], names: list[str]) -> dict:
    """{member: {"weight", "n", "brier", "wins", "dropped"}} from the graded history. Each row was
    predicted before its result, so this is out of sample. Thin records keep weight 1."""
    out = {}
    for m in names:
        g = [r for r in history if (r.get("members") or {}).get(m) is not None and r.get("anchor") is not None]
        if len(g) < MIN_MEMBER_N:
            out[m] = {"weight": 1.0, "n": len(g), "dropped": None}
            continue
        b = sum(_brier(r["members"][m], r["won"]) for r in g) / len(g)
        a = sum(_brier(r["anchor"], r["won"]) for r in g) / len(g)
        wins = sum(1 for r in g if _brier(r["members"][m], r["won"]) <= min(
            _brier(v, r["won"]) for v in r["members"].values() if v is not None))
        others = len({k for r in g for k in r["members"]}) > 1
        why = ("never beat the other members" if others and wins == 0 else
               "worse than the market anchor" if b > a + BRIER_MARGIN else None)
        out[m] = {"weight": 0.0 if why else round(1.0 / max(b, 1e-4), 3), "n": len(g),
                  "brier": round(b, 4), "anchor_brier": round(a, 4), "wins": wins, "dropped": why}
    return out


def edge_factor(edge: Optional[float]) -> float:
    if edge is None:
        return 1.0
    return STAKE_BY_EDGE["negative"] if edge < 0 else STAKE_BY_EDGE["strong"] if edge >= EDGE_STRONG \
        else STAKE_BY_EDGE["positive"]


def _clv_hit(says_back: bool, clv: float) -> bool:
    return (clv > 0) == says_back


def earned_authority(domain: str, family: str, history: list[dict], stage: str = "board") -> dict:
    """Authority to set the stake in (domain, family): enough graded rows, a lower Brier than the live
    verdict, and (CLV first) agreeing with the closing line more often than the live verdict did."""
    g = [r for r in history if r.get("domain") == domain and r.get("family") == family
         and (r.get("stage") or "board") == stage and r.get("panel_prob") is not None]
    out = {"n": len(g), "earned": False}
    if not g:
        return out
    live = [r for r in g if r.get("live_prob") is not None]
    out["panel_brier"] = round(sum(_brier(r["panel_prob"], r["won"]) for r in g) / len(g), 4)
    if live:
        out["live_brier"] = round(sum(_brier(r["live_prob"], r["won"]) for r in live) / len(live), 4)
        out["panel_brier_on_live"] = round(sum(_brier(r["panel_prob"], r["won"]) for r in live) / len(live), 4)
    c = [r for r in g if r.get("clv") is not None and r.get("edge") is not None and r.get("live_back") is not None]
    out["clv_n"] = len(c)
    if c:
        out["panel_clv_hit"] = round(sum(_clv_hit(r["edge"] > 0, r["clv"]) for r in c) / len(c), 3)
        out["live_clv_hit"] = round(sum(_clv_hit(r["live_back"], r["clv"]) for r in c) / len(c), 3)
    out["earned"] = bool(len(g) >= MIN_EARNED_N and live and len(c) >= MIN_CLV_N
                         and out["panel_brier_on_live"] + BRIER_MARGIN <= out["live_brier"]
                         and out["panel_clv_hit"] > out["live_clv_hit"])
    return out


def authority_table(history: list[dict]) -> dict:
    keys = sorted({(r.get("domain"), r.get("family"), r.get("stage") or "board") for r in history}, key=str)
    return {f"{d} | {f} | {s}": earned_authority(d, f, history, s) for d, f, s in keys}


# ---------------------------------------------------------------- the panel
def _row(i: int, ctx: dict, anchor: float, source: str) -> dict:
    return {"id": i, "fixture": ctx.get("fixture"), "league": ctx.get("league"), "pick": ctx.get("pick"),
            "price": ctx.get("price"), "anchor": round(anchor, 4), "anchor_source": source,
            "model_chance": ctx.get("base_prob"), "news": ctx.get("news_note") or ctx.get("news_level"),
            "lineup": ctx.get("lineup"), "missing_value_share": ctx.get("missing"),
            "matchup_chance": ctx.get("profile_lean"), "flags": ctx.get("flags") or []}


def evaluate(ctxs: list[dict], keys: Optional[dict] = None, get: Optional[Callable] = None,
             post: Optional[Callable] = None, record_path: Path = PANEL_RECORD, stage: str = "board") -> dict:
    """{"members": {...run info...}, "picks": [panel block per ctx]}. Never raises."""
    if get is None or post is None:
        import requests
        get, post = get or requests.get, post or requests.post
    keys = keys if keys is not None else {n: os.getenv(s["key"], "").strip() for n, s in MEMBERS.items()}
    hist = (load_record(record_path).get("history") or [])
    info: dict = {}
    anchors = []
    for c in ctxs:
        m, b = _num(c.get("market_prob")), _num(c.get("base_prob"))
        anchors.append((m, "market") if m is not None else (b, "model") if b is not None else (None, None))
    idx = [i for i, (a, _) in enumerate(anchors) if a is not None]
    answers: dict = {n: {} for n in MEMBERS}
    for name in MEMBERS:
        key = keys.get(name) or ""
        if not key:
            info[name] = {"status": f"missing secret {MEMBERS[name]['key']}"}
            continue
        model = pick_model(name, get, key)
        if not model:
            info[name] = {"status": "no free model available" if name == "openrouter" else "no model"}
            continue
        info[name] = {"model": model, "status": "ok", "answered": 0}
        for j in range(0, len(idx), BATCH):
            part = idx[j:j + BATCH]
            rows = [_row(i, ctxs[i], anchors[i][0], anchors[i][1]) for i in part]
            try:
                got = ask(name, model, key, rows, post)
            except (RateLimited, PaidModelError, ChargedError) as e:
                info[name]["status"] = f"off for this run: {e}"
                break
            except Exception as e:  # noqa: BLE001 — one failed batch leaves only its picks without this member
                info[name]["status"] = f"partly failed: {type(e).__name__}: {str(e)[:120]}"
                continue
            answers[name].update(got)
            info[name]["answered"] += len(got)
    names = [n for n in MEMBERS if info.get(n, {}).get("model")]
    weights = member_weights(hist, names)
    for n in names:
        if str(info[n]["status"]).startswith("off for this run"):
            weights[n] = {**weights[n], "weight": 0.0, "dropped": "rate-limited or refused this run"}
    on = stakes_on()
    picks = []
    for i, c in enumerate(ctxs):
        anchor, src = anchors[i]
        mem = {n: round(answers[n][i], 4) for n in names if i in answers[n]}
        blk = {"stage": stage, "anchor": anchor, "anchor_source": src, "members": mem,
               "domain": c.get("domain") or "football", "family": c.get("family")}
        w = {n: weights[n]["weight"] for n in mem if weights[n]["weight"] > 0}
        if anchor is not None and w:
            shift = sum(w[n] * _clamp(mem[n] - anchor, -MAX_SHIFT, MAX_SHIFT) for n in w) / sum(w.values())
            p = round(_clamp(anchor + shift, PROB_FLOOR, PROB_CAP), 4)
        else:
            p = anchor
        price = _num(c.get("price"))
        edge = round(p * price - 1, 4) if p is not None and price else None
        auth = earned_authority(blk["domain"], blk["family"], hist, stage)
        f = edge_factor(edge)
        blk.update({"panel_prob": p, "edge": edge, "advised_stake_factor": f, "authority": auth,
                    "mode": "authority" if auth["earned"] else "shadow", "stakes_on": on,
                    "stake_factor": f if auth["earned"] and on else None})
        picks.append(blk)
    return {"members": info, "weights": weights, "picks": picks}


def apply(doc: dict, singles: list[dict], sport: str, stage: str = "board", **kw) -> None:
    """Add a "panel" block (stage "lineup": "panel_lineup") to every pick of a reasoning document, and
    on the board stage panel_prob, the verdict's probability. With earned authority and
    COGNITIVE_STAKES on, the stake factor is the lower of the panel's and whatever the cognitive core
    already set (never raised past an earned VETO)."""
    field = "panel" if stage == "board" else "panel_lineup"
    from engine import cognitive_core as CC
    ctxs = []
    for s, x in zip(singles, doc["picks"]):
        c = CC.context_from_single(s, sport)
        c["flags"] = (x.get("cognitive") or {}).get("flags") or []
        c["missing"] = s.get("missing")
        c["lineup"] = (s.get("lineup_check") or {}).get("note")
        ctxs.append(c)
    try:
        res = evaluate(ctxs, stage=stage, **kw)
    except Exception as e:  # noqa: BLE001 — the panel never blocks the reasoning document
        doc[field] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
        return
    for x, blk in zip(doc["picks"], res["picks"]):
        x[field] = blk
        if stage == "board":
            x["panel_prob"] = blk["panel_prob"]
        if blk["stake_factor"] is not None:
            cog = x.get("cognitive") or {}
            earned_cog = cog.get("stakes_on") and cog.get("mode") == "authority"
            x["stake_factor"] = min(blk["stake_factor"], x["stake_factor"]) if earned_cog else blk["stake_factor"]
            x["stake_source"] = field
    doc[field] = {"members": res["members"], "weights": res["weights"],
                    "authority": sum(b["mode"] == "authority" for b in res["picks"]),
                    "missing": [MEMBERS[n]["key"] for n, i in res["members"].items()
                                if str(i.get("status", "")).startswith("missing secret")]}


# ---------------------------------------------------------------- grade (nightly, out of sample)
def grade(out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR, record_path: Path = PANEL_RECORD,
          now: Optional[datetime] = None) -> int:
    """Append every graded pick that carries a panel block (board and line-up stage) to
    memory/panel_record.json once, with the live verdict's probability and the CLV."""
    now = now or datetime.now(UTC)
    rec = load_record(record_path)
    hist = rec.get("history") or []
    seen = {r.get("id") for r in hist}
    added = 0
    for sport, pat, src in (("football", "reasoning_2*.json", "picks_{}.json"),
                            ("nba", "reasoning_nba_*.json", "nba_{}.json")):
        for f in sorted(out_dir.glob(pat)):
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                d = json.loads((ledger_dir / src.format(r["date"])).read_text(encoding="utf-8"))
            except (OSError, ValueError, KeyError):
                continue
            if sport == "nba":
                by = {(f"{p.get('home')} v {p.get('away')}",
                       f"NBA:{p.get('market_id')}|{p.get('specifier') or ''}|{p.get('outcome')}"): p
                      for p in (d.get("picks") or []) + (d.get("picks_dropped") or [])}
            else:
                by = {(s.get("fixture"), s.get("market")): s for s in d.get("singles") or []}
            for x in r.get("picks") or []:
                s = by.get((x.get("fixture"), x.get("market"))) or {}
                if s.get("result") not in ("won", "lost"):
                    continue
                for blk in (x.get("panel"), x.get("panel_lineup")):
                    if not isinstance(blk, dict) or blk.get("panel_prob") is None:
                        continue
                    rid = f"{sport}|{r['date']}|{x.get('fixture')}|{x.get('market')}|{blk.get('stage') or 'board'}"
                    if rid in seen:
                        continue
                    live = _num(x.get("ai_chance"))
                    hist.append({"id": rid, "date": r["date"], "domain": blk.get("domain") or sport,
                                 "family": blk.get("family"), "stage": blk.get("stage") or "board",
                                 "anchor": blk.get("anchor"), "members": blk.get("members") or {},
                                 "panel_prob": blk["panel_prob"], "edge": blk.get("edge"),
                                 "live_prob": live if live is not None else _num(x.get("model_chance")),
                                 "live_back": (x.get("verdict") == "back") if x.get("verdict") in ("back", "lower", "veto") else None,
                                 "clv": _num(s.get("clv")), "won": s["result"] == "won",
                                 "graded_at": now.isoformat(timespec="seconds")})
                    seen.add(rid)
                    added += 1
    rec["history"] = hist[-MAX_HISTORY:]
    rec["updated"] = now.date().isoformat()
    rec["authority"] = authority_table(rec["history"])
    rec["members"] = member_weights(rec["history"], list(MEMBERS))
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return added


def summary_line(record_path: Path = PANEL_RECORD) -> str:
    rec = load_record(record_path)
    h = rec.get("history") or []
    earned = [k for k, v in (rec.get("authority") or {}).items() if v.get("earned")]
    mem = ", ".join(f"{n} w{v.get('weight')} n{v.get('n')}" + (f" ({v['dropped']})" if v.get("dropped") else "")
                    for n, v in (rec.get("members") or {}).items())
    return f"panel: {len(h)} graded rows · members {mem or 'none yet'} · authority in {len(earned)} families"


# ---------------------------------------------------------------- the line-up pass (T-75..T-45)
def _ko(s: str) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def lineup_pass(now: Optional[datetime] = None, out_dir: Path = OUT_DIR, ledger_dir: Path = LEDGER_DIR,
                **kw) -> str:
    """Run the panel again on today's football singles kicking off in T-75..T-45 min whose line-up
    check is in (news_check.py), once per pick: a "panel_lineup" block in the reasoning file. It sets
    the stake only with the line-up stage's own earned authority."""
    now = now or datetime.now(UTC)
    day = now.date().isoformat()
    rp, lp = out_dir / f"reasoning_{day}.json", ledger_dir / f"picks_{day}.json"
    try:
        doc = json.loads(rp.read_text(encoding="utf-8"))
        led = json.loads(lp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "line-up pass: no reasoning or picks file for today"
    by = {(s.get("fixture"), s.get("market")): s for s in led.get("singles") or []}
    lo, hi = now + timedelta(minutes=LINEUP_WINDOW_MIN[0]), now + timedelta(minutes=LINEUP_WINDOW_MIN[1])
    due = []
    for x in doc.get("picks") or []:
        s = by.get((x.get("fixture"), x.get("market")))
        ko = _ko((s or {}).get("kickoff_utc"))
        if s and not x.get("panel_lineup") and s.get("lineup_check") and ko and lo <= ko <= hi:
            due.append((x, s))
    if not due:
        return "line-up pass: nothing due"
    sub = {"picks": [x for x, _ in due]}        # the same pick dicts: the blocks land in doc
    apply(sub, [s for _, s in due], "football", stage="lineup", **kw)
    doc.setdefault("lineup_passes", []).append({"at": now.isoformat(timespec="minutes"), "picks": len(due),
                                                "members": (sub.get("panel_lineup") or {}).get("members")})
    rp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return f"line-up pass: {len(due)} pick(s) re-priced with line-ups"
