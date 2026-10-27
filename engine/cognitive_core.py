"""
COGNITIVE CORE — the Architect's five-stage judgement on top of the reasoning step (spec of
2026-10-27, to-do #3). engine/reasoning.py calls it for every pick it judges; the Matchbook
agent's oracle carries a port of the same logic.

    1. detect_regime_flags(ctx)  deterministic, BEFORE the model: regime flags and the inputs
                                 that are missing (None, "" or "PENDING" -> epistemic risk, HR35)
    2. debate(...)               one structured-JSON Gemini call per batch: a blue-team thesis,
                                 a red-team attack, a CIO verdict BACK | LOWER | VETO and a
                                 probability adjustment. No answer -> a deterministic fallback.
    3. firewall(...)             the adjustment is clamped to +-MAX_PROB_SHIFT; VETO forces it
                                 <= -0.03, LOWER <= -0.01; the result is kept inside [0.02, 0.98]
    4. earned_authority(...)     per (domain, family) from the graded history: >= MIN_EARNED_N
                                 rows, the cognitive Brier beats the base Brier by BRIER_MARGIN
                                 and vetoes lose >= VETO_LOSS_MIN of the time. Without it the
                                 core is a SHADOW: effective_prob = base_prob, stake x1.0.
    5. grade_and_learn(...)      each graded pick is appended to the history with both Brier
                                 scores; a BACK at base_prob >= 0.62 that lost gets a post-mortem
                                 whose lesson is fed back into later prompts (relevant_lessons).

STAKES: the multipliers (BACK 1.15, LOWER 0.5, VETO 0.0) were APPROVED by the Architect on 2026-10-27
10:35 (standing order 48): they act in every (domain, family) where authority is earned, shadow mode
everywhere else. The repo variable COGNITIVE_STAKES is the off switch (default ON; "0" turns the
multipliers off, leaving them as advice logged as advised_stake_multiplier).

The output is a probability (cognitive_prob, effective_prob) so the verdict work of to-do #5 can
blend it with the de-margined sharp price (market_prob = sharp_p, framework PR #177).
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).parent.parent
RECORD = ROOT / "memory" / "reasoning_record.json"      # history lives under "cognitive_history"
LESSONS = ROOT / "memory" / "reasoning_lessons.json"    # post-mortems live under "cognitive"
NATIVE_URL = os.getenv("GEMINI_NATIVE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

MAX_PROB_SHIFT = 0.08
PROB_FLOOR, PROB_CAP = 0.02, 0.98
VETO_MAX_ADJ, LOWER_MAX_ADJ = -0.03, -0.01
MIN_EARNED_N = 30
BRIER_MARGIN = 0.002
VETO_LOSS_MIN = 0.45
POSTMORTEM_MIN_BASE = 0.62
MAX_POSTMORTEM_LESSONS = 200
SHORT_REST_DAYS = 3
HIGH_VOLATILITY = 0.40
OVERBOUGHT_RSI = 68
ENGINE_DIVERGENCE = 0.10          # Elo v Dixon-Coles chance gap that counts as disagreement
TEMPERATURE = 0.15
BATCH = 10
STAKE_MULT = {"BACK": 1.15, "LOWER": 0.5, "VETO": 0.0}
VERDICTS = tuple(STAKE_MULT)
FAILURE_MODES = ("TACTICAL_MISMATCH", "LINEUP_OR_FATIGUE", "SHARP_LINE_MOVED_AGAINST",
                 "VARIANCE_BAD_BEAT", "OVERCONFIDENT_CALIBRATION")
REQUIRED = ("price", "base_prob", "market_prob", "news_level", "profile_lean")
_CUP = re.compile(r"\b(cup|trophy|pokal|copa|coupe|coppa|beker|taca|ta[cç]a)\b", re.I)


def model() -> str:
    return os.getenv("OLP_GEMINI_MODEL", "").strip() or "gemini-2.5-flash"


def stakes_on() -> bool:
    """The off switch (standing order 48): on unless COGNITIVE_STAKES says 0 / false / off / no."""
    return os.getenv("COGNITIVE_STAKES", "1").strip().lower() not in ("0", "false", "off", "no")


def _absent(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() in ("", "PENDING"))


def _num(v) -> Optional[float]:
    try:
        return None if _absent(v) else float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 1. regime (deterministic)
def detect_regime_flags(ctx: dict) -> tuple[list[str], list[str]]:
    """(flags, missing) for one pick's context. Unknown inputs raise no flag; they are listed as missing
    only when they are among the five the judgement needs (REQUIRED)."""
    missing = [k for k in REQUIRED if _absent(ctx.get(k))]
    flags = []
    for side in ("home", "away"):
        d = _num(ctx.get(f"rest_days_{side}"))
        if d is not None and d <= SHORT_REST_DAYS:
            flags.append(f"SHORT_REST_{side.upper()}")
    if ctx.get("post_international_window"):
        flags.append("FIFA_VIRUS_WINDOW")
    if _CUP.search(str(ctx.get("league") or "")):
        flags.append("DOMESTIC_CUP_ROTATION_RISK")
    news = str(ctx.get("news_level") or "").upper()
    for lvl in ("RISK", "CAUTION"):
        if lvl in news:
            flags.append(f"TEAM_NEWS_{lvl}")
            break
    elo, dc = _num(ctx.get("elo_prob")), _num(ctx.get("dc_prob"))
    if ctx.get("engine_divergence") or (elo is not None and dc is not None and abs(elo - dc) > ENGINE_DIVERGENCE):
        flags.append("ELO_DC_ENGINE_DIVERGENCE")
    vol = _num(ctx.get("volatility"))
    if vol is not None and vol > HIGH_VOLATILITY:
        flags.append("HIGH_VOLATILITY_REGIME")
    rsi = _num(ctx.get("rsi"))
    if rsi is not None and rsi > OVERBOUGHT_RSI:
        flags.append("OVERBOUGHT_EXTENSION")
    return flags, missing


def context_from_single(s: dict, domain: str = "football") -> dict:
    """The core's context from a board single (or an NBA pick) as reasoning.py holds it."""
    from engine.reasoning import _family, nba_family
    m = s.get("matchup") or {}
    return {"fixture": s.get("fixture") or (f"{s.get('home')} v {s.get('away')}" if s.get("home") else None),
            "league": s.get("league") or ("NBA" if domain == "nba" else None), "pick": s.get("pick"),
            "family": nba_family(s.get("market_id")) if domain == "nba" else _family(s.get("market") or ""),
            "price": s.get("price"), "base_prob": s.get("chance"),
            "market_prob": s.get("sharp_p") if domain != "nba" else (s.get("sharp_p") or s.get("chance")),
            "news_level": s.get("news_level") if domain != "nba" else (s.get("news_level") or "n/a"),
            "news_note": s.get("news_note"),
            "profile_lean": s.get("profile_lean") if s.get("profile_lean") is not None else m.get("pick_matchup_chance"),
            "rest_days_home": s.get("rest_days_home"), "rest_days_away": s.get("rest_days_away"),
            "post_international_window": s.get("post_international_window"),
            "elo_prob": s.get("elo_p"), "dc_prob": s.get("dc_p"), "volatility": s.get("volatility"),
            "rsi": s.get("rsi"), "domain": domain}


# ---------------------------------------------------------------- 2. the debate (one Gemini call per batch)
DEBATE = """You are the cognitive core of a sports betting model: a blue team, a red team and a CIO.
For each pick: the blue team states the strongest case FOR it (blue_team_thesis), the red team
attacks it (red_team_attack), the CIO decides BACK, LOWER or VETO and gives prob_adjustment, the
change to the model's probability (negative pulls it down; at most 0.08 either way).
Rules:
- HR59: never invent a number, a line-up or a news item. Use only what is in the context; if a fact
  is missing, say it is missing.
- "missing" lists inputs that read PENDING or are absent: that is EPISTEMIC RISK. It argues for
  caution (LOWER), never for a bigger chance.
- "flags" were computed from the data before you: weigh each one the red team can use.
- "market_prob" is the de-margined sharp price: a base_prob far above it needs a concrete reason.
- Past lessons for this family (from your own lost picks) come first; do not repeat those mistakes.
"""
DEBATE_SCHEMA = {"type": "OBJECT", "properties": {"picks": {"type": "ARRAY", "items": {
    "type": "OBJECT", "properties": {
        "id": {"type": "INTEGER"}, "blue_team_thesis": {"type": "STRING"}, "red_team_attack": {"type": "STRING"},
        "cio_verdict": {"type": "STRING", "enum": list(VERDICTS)}, "prob_adjustment": {"type": "NUMBER"}},
    "required": ["id", "blue_team_thesis", "red_team_attack", "cio_verdict", "prob_adjustment"]}}},
    "required": ["picks"]}
POSTMORTEM_SCHEMA = {"type": "OBJECT", "properties": {
    "failure_mode": {"type": "STRING", "enum": list(FAILURE_MODES)}, "lesson": {"type": "STRING"}},
    "required": ["failure_mode", "lesson"]}


def _gemini_json(post: Callable, key: str, prompt: str, schema: dict, timeout: int = 120) -> dict:
    """One structured-JSON call. The key goes in the x-goog-api-key header: in the URL it would
    leak into request logs."""
    r = post(f"{NATIVE_URL}/models/{model()}:generateContent", headers={"x-goog-api-key": key}, timeout=timeout,
             json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": TEMPERATURE, "responseMimeType": "application/json",
                                        "responseSchema": schema}})
    r.raise_for_status()
    parts = (((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
    return json.loads("".join(p.get("text", "") for p in parts))


def fallback(flags: list[str]) -> dict:
    """The deterministic answer when the model gives none: LOWER -0.02 on a risk or divergence flag."""
    risky = any(f.endswith("_RISK") or "DIVERGENCE" in f for f in flags)
    return {"blue_team_thesis": "", "red_team_attack": "", "cio_verdict": "LOWER" if risky else "BACK",
            "prob_adjustment": -0.02 if risky else 0.0, "source": "fallback"}


def debate(ctxs: list[dict], key: Optional[str] = None, post: Optional[Callable] = None,
           lessons_path: Path = LESSONS) -> list[dict]:
    """The debate for each context (same order). Never raises: a failed batch falls back per pick."""
    key = key if key is not None else os.getenv("GEMINI_API_KEY", "").strip()
    out: list[dict] = []
    for i in range(0, len(ctxs), BATCH):
        part = ctxs[i:i + BATCH]
        rows = [{"id": j, **{k: v for k, v in c.items() if k != "domain"}} for j, c in enumerate(part)]
        fams = {(c.get("domain"), c.get("family")) for c in part}
        les = [x for d, f in fams for x in relevant_lessons(d, f, lessons_path=lessons_path)]
        got: dict = {}
        if key and post is not None:
            prompt = (DEBATE + ("PAST LESSONS:\n" + "\n".join(f"- {x}" for x in dict.fromkeys(les)) + "\n" if les else "")
                      + "\nPICKS:\n" + json.dumps(rows, ensure_ascii=False))
            try:
                got = {p.get("id"): p for p in _gemini_json(post, key, prompt, DEBATE_SCHEMA).get("picks") or []}
            except Exception:  # noqa: BLE001 — the deterministic fallback below
                got = {}
        for j, c in enumerate(part):
            p = got.get(j)
            try:
                ok = p and str(p.get("cio_verdict")).upper() in VERDICTS and float(p.get("prob_adjustment")) == float(p.get("prob_adjustment"))
            except (TypeError, ValueError):
                ok = False
            if ok:
                out.append({"blue_team_thesis": str(p.get("blue_team_thesis") or "")[:400],
                            "red_team_attack": str(p.get("red_team_attack") or "")[:400],
                            "cio_verdict": str(p["cio_verdict"]).upper(),
                            "prob_adjustment": float(p["prob_adjustment"]), "source": "gemini"})
            else:
                out.append(fallback(c.get("flags") or detect_regime_flags(c)[0]))
    return out


# ---------------------------------------------------------------- 3. the firewall
def firewall(verdict: str, adj: float, base_prob: Optional[float]) -> tuple[float, Optional[float]]:
    """(clamped adjustment, cognitive_prob). No base probability -> no cognitive probability."""
    adj = max(-MAX_PROB_SHIFT, min(MAX_PROB_SHIFT, float(adj or 0)))
    if verdict == "VETO":
        adj = min(adj, VETO_MAX_ADJ)
    elif verdict == "LOWER":
        adj = min(adj, LOWER_MAX_ADJ)
    if base_prob is None:
        return round(adj, 4), None
    return round(adj, 4), round(max(PROB_FLOOR, min(PROB_CAP, float(base_prob) + adj)), 4)


# ---------------------------------------------------------------- 4. earned authority
def load_history(record_path: Path = RECORD) -> list[dict]:
    try:
        return json.loads(record_path.read_text(encoding="utf-8")).get("cognitive_history") or []
    except (OSError, ValueError, AttributeError):
        return []


def earned_authority(domain: str, family: str, history: list[dict]) -> dict:
    """The core earns the right to move the probability (and, with COGNITIVE_STAKES, the stake) in a
    (domain, family) only once its own graded record there beats the base model's."""
    g = [r for r in history if r.get("domain") == domain and r.get("family") == family
         and r.get("cog_brier") is not None and r.get("base_brier") is not None]
    out = {"n": len(g), "earned": False}
    if not g:
        return out
    out["cog_brier"] = round(sum(r["cog_brier"] for r in g) / len(g), 4)
    out["base_brier"] = round(sum(r["base_brier"] for r in g) / len(g), 4)
    vetoes = [r for r in g if r.get("verdict") == "VETO"]
    out["veto_loss_rate"] = round(sum(1 for r in vetoes if not r.get("won")) / len(vetoes), 3) if vetoes else None
    out["earned"] = (len(g) >= MIN_EARNED_N and out["cog_brier"] + BRIER_MARGIN <= out["base_brier"]
                     and out["veto_loss_rate"] is not None and out["veto_loss_rate"] >= VETO_LOSS_MIN)
    return out


def authority_table(history: list[dict]) -> dict:
    """{"domain | family": authority} for every pair in the history (written to the reasoning record)."""
    pairs = sorted({(r.get("domain"), r.get("family")) for r in history if r.get("family")}, key=str)
    return {f"{d} | {f}": earned_authority(d, f, history) for d, f in pairs}


# ---------------------------------------------------------------- the whole judgement
def evaluate(ctxs: list[dict], key: Optional[str] = None, post: Optional[Callable] = None,
             record_path: Path = RECORD, lessons_path: Path = LESSONS) -> list[dict]:
    """The cognitive verdict for each context: flags, missing, the debate, the firewalled probability,
    authority, and the probability/stake the bots should use."""
    for c in ctxs:
        c["flags"], c["missing"] = detect_regime_flags(c)
    debates = debate(ctxs, key, post, lessons_path)
    history = load_history(record_path)
    on = stakes_on()
    out = []
    for c, d in zip(ctxs, debates):
        base = _num(c.get("base_prob"))
        adj, cog = firewall(d["cio_verdict"], d["prob_adjustment"], base)
        auth = earned_authority(c.get("domain") or "football", c.get("family"), history)
        advised = STAKE_MULT[d["cio_verdict"]] if auth["earned"] else 1.0
        out.append({**d, "prob_adjustment": adj, "flags": c["flags"], "missing": c["missing"],
                    "domain": c.get("domain") or "football", "family": c.get("family"),
                    "base_prob": base, "market_prob": _num(c.get("market_prob")), "cognitive_prob": cog,
                    "authority": auth, "mode": "authority" if auth["earned"] else "shadow",
                    "effective_prob": cog if auth["earned"] and cog is not None else base,
                    "advised_stake_multiplier": advised, "stakes_on": on,
                    "stake_multiplier": advised if on else 1.0})
    return out


# ---------------------------------------------------------------- 5. grade and learn
def _brier(p: Optional[float], won: bool) -> Optional[float]:
    return None if p is None else round((float(p) - (1.0 if won else 0.0)) ** 2, 4)


def postmortem(verdict: dict, actual_stats: Optional[dict], key: str, post: Callable) -> Optional[dict]:
    prompt = ("A pick the betting model backed with a high probability LOST. Classify why, from the facts below "
              "only (HR59: invent nothing), as one failure_mode, and write one lesson of at most 25 words that "
              "would have caught it.\n" + json.dumps({"verdict": verdict, "actual_stats": actual_stats},
                                                   ensure_ascii=False, default=str))
    try:
        got = _gemini_json(post, key, prompt, POSTMORTEM_SCHEMA)
    except Exception:  # noqa: BLE001 — no lesson rather than an invented one
        return None
    mode, lesson = str(got.get("failure_mode") or "").upper(), " ".join(str(got.get("lesson") or "").split()[:25])
    return {"failure_mode": mode, "lesson": lesson} if mode in FAILURE_MODES and lesson else None


def grade_and_learn(verdict: dict, won: bool, actual_stats: Optional[dict] = None, key: Optional[str] = None,
                    post: Optional[Callable] = None, record_path: Path = RECORD, lessons_path: Path = LESSONS,
                    now: Optional[datetime] = None) -> Optional[dict]:
    """Append one graded verdict to the history (once per id) and, for a confident BACK that lost,
    store a post-mortem lesson. Returns the history row, or None when the id was already graded."""
    now = now or datetime.now(UTC)
    try:
        rec = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rec = {}
    hist = rec.get("cognitive_history") or []
    rid = verdict.get("id")
    if rid and any(r.get("id") == rid for r in hist):
        return None
    base, cog = _num(verdict.get("base_prob")), _num(verdict.get("cognitive_prob"))
    row = {"id": rid, "date": verdict.get("date"), "domain": verdict.get("domain") or "football",
           "family": verdict.get("family"), "verdict": verdict.get("cio_verdict"), "base_prob": base,
           "cognitive_prob": cog, "won": bool(won), "base_brier": _brier(base, won), "cog_brier": _brier(cog, won),
           "flags": verdict.get("flags") or [], "graded_at": now.isoformat(timespec="seconds")}
    rec["cognitive_history"] = hist + [row]
    record_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    key = key if key is not None else os.getenv("GEMINI_API_KEY", "").strip()
    if row["verdict"] == "BACK" and not won and base is not None and base >= POSTMORTEM_MIN_BASE and key and post:
        pm = postmortem(verdict, actual_stats, key, post)
        if pm:
            try:
                allx = json.loads(lessons_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                allx = {}
            allx["cognitive"] = ((allx.get("cognitive") or []) + [{
                "date": verdict.get("date"), "domain": row["domain"], "family": row["family"],
                "fixture": verdict.get("fixture"), **pm}])[-MAX_POSTMORTEM_LESSONS:]
            lessons_path.write_text(json.dumps(allx, indent=1, ensure_ascii=False), encoding="utf-8")
            row["postmortem"] = pm
    return row


def relevant_lessons(domain: Optional[str], family: Optional[str], n: int = 5, lessons_path: Path = LESSONS) -> list[str]:
    """The newest post-mortem lessons for this (domain, family), for the debate prompt."""
    try:
        les = json.loads(lessons_path.read_text(encoding="utf-8")).get("cognitive") or []
    except (OSError, ValueError, AttributeError):
        return []
    hits = [x for x in les if x.get("family") == family and (x.get("domain") or "football") == (domain or "football")]
    return [f"[{x.get('failure_mode')}] {x.get('lesson')}" for x in hits[-n:][::-1]]
