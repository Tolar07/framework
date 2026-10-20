"""
LEG-LEVEL POST-MORTEMS — which kinds of leg sink our slips (autonomy item 2,
Architect 2026-10-20: "learn from mistakes").

For every graded slip (50%+ accas, Table 3 accas, alt accas, combined codes,
megas) each leg is looked up — a main slip's legs are that day's singles, an alt
slip's legs carry their own market — and classed by:

  family     market family (engine/learning.family)
  band       price band (engine/experiments.band)
  league
  certainty  HIGH / MEDIUM / LOW (order 15)
  news       the single's team-news level (order 17)
  gemini     the reasoning step's verdict (engine/reasoning.py), when there is one

Per class, over every distinct leg that sat in a graded slip (a leg counted
once however many slips held it): legs, legs lost, the losses its stated
chances promised (sum of 1 - chance), z = (lost - promised) / sd, and how
many losing slips it helped kill. A class is a SLIP KILLER when it has 50+
legs and z >= Z_BAR — it loses significantly more than it says.

Fed back through the experiment engine, not as a hard rule: "AK" / "TK"
(accas / 50%+ accas with no killer-class leg) compete in shadow and only reach
the board if they earn promotion. The killers a day's strategy sees are built
only from slips graded BEFORE that day (no look-ahead). The gemini dimension is
reported but not used by the rule: no verdict exists when the board is built.

Writes memory/leg_postmortem.json. Nothing here changes a stake.
"""
from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from typing import Any

from engine import experiments as X

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "memory" / "leg_postmortem.json"
MIN_LEGS = 50
Z_BAR = 2.0
KINDS = ("safe3", "accas", "alts", "megas", "combined")
RULE_DIMS = ("family", "band", "league", "certainty", "news")   # gemini: report only


def classes(lg: dict) -> list[str]:
    out = [f"family={lg.get('family') or '?'}", f"band={X.band(lg.get('price'))}",
           f"league={lg.get('league') or '?'}", f"certainty={lg.get('certainty') or '?'}",
           f"news={lg.get('news') or '?'}"]
    if lg.get("verdict"):
        out.append(f"gemini={lg['verdict']}")
    return out


def _alt_leg(a: dict) -> dict:
    lg = X.leg({**a, "certainty": None, "news_level": None})
    return lg


def slips_of(doc: dict, verdicts: dict) -> list[dict]:
    """[{kind, name, day, result, legs}] — every slip of a ledger, legs resolved."""
    day = doc["date"]
    singles = {s["fixture"]: X.leg(s, verdicts.get((s.get("fixture"), s.get("market"))))
               for s in doc.get("singles", []) + doc.get("singles_dropped", [])}
    out: list[dict] = []
    by_kind: dict[str, list[dict]] = {}
    for kind in ("safe3", "accas", "megas", "alts"):
        for s in doc.get(kind, []):
            if kind == "alts":
                legs = [_alt_leg(a) for a in s.get("alt_legs", [])]
            else:
                legs = [singles[f] for f in s.get("legs", []) if f in singles]
            row = {"kind": kind, "name": s.get("name"), "day": day, "result": s.get("result"), "legs": legs}
            by_kind.setdefault(kind, []).append(row)
            out.append(row)
    for c in doc.get("combined", []):           # one code over every slip of a kind
        legs = [lg for s in by_kind.get(c.get("of"), []) for lg in s["legs"]]
        out.append({"kind": "combined", "name": c.get("name"), "day": day, "result": c.get("result"),
                    "legs": legs})
    return out


def load(picks_dir: Path = X.PICKS_DIR, reasoning_dir: Path = X.REASONING_DIR) -> list[dict]:
    out = []
    for path in sorted(picks_dir.glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out += slips_of(doc, X._verdicts(doc["date"], reasoning_dir))
    return out


def build(slips: list[dict], before: str | None = None) -> dict[str, Any]:
    """The post-mortem over graded slips (only those dated before `before`)."""
    graded = [s for s in slips if s["result"] in ("won", "lost") and (before is None or s["day"] < before)]
    legs: dict[tuple, dict] = {}
    kills: dict[str, int] = {}
    lost_slips = 0
    for s in graded:
        for lg in s["legs"]:
            if lg["result"] in ("won", "lost") and lg.get("chance"):
                legs[(s["day"], lg["fixture"], lg["market"])] = lg
        if s["result"] == "lost":
            lost_slips += 1
            for c in {c for lg in s["legs"] if lg["result"] == "lost" for c in classes(lg)}:
                kills[c] = kills.get(c, 0) + 1
    acc: dict[str, list[float]] = {}           # class -> [n, lost, promised losses, variance]
    for lg in legs.values():
        q = 1 - lg["chance"]
        for c in classes(lg):
            a = acc.setdefault(c, [0, 0, 0.0, 0.0])
            a[0] += 1
            a[1] += lg["result"] == "lost"
            a[2] += q
            a[3] += q * (1 - q)
    table = {}
    for c, (n, lost, exp, var) in acc.items():
        z = (lost - exp) / sqrt(var) if var > 0 else 0.0
        table[c] = {"legs": int(n), "lost": int(lost), "loss_rate": round(lost / n, 4),
                    "stated_loss": round(exp / n, 4), "z": round(z, 2), "slips_killed": kills.get(c, 0),
                    "killer": n >= MIN_LEGS and z >= Z_BAR}
    return {"slips_graded": len(graded), "slips_lost": lost_slips, "legs": len(legs),
            "killers": sorted(c for c, r in table.items() if r["killer"]), "classes": table}


def rule_killers(pm: dict) -> set[str]:
    return {c for c in pm.get("killers", []) if c.split("=", 1)[0] in RULE_DIMS}


def contexts(days: list[dict]) -> dict[str, dict]:
    """{day: {"killers": set}} — each day sees only slips graded before it."""
    slips = load()
    return {d["day"]: {"killers": rule_killers(build(slips, before=d["day"]))} for d in days}


def context_now(path: Path = OUT) -> dict:
    try:
        pm = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"killers": set()}
    return {"killers": rule_killers(pm)}


def _no_killer(lg: dict, ctx: dict) -> bool:
    k = ctx.get("killers") or set()
    return not any(c in k for c in classes(lg))


def strategies() -> list:
    return [X.Strategy("AK accas: no slip-killer leg", "accas",
                       "accas with no leg from a class that loses significantly more than stated "
                       f"({MIN_LEGS}+ legs, z >= {Z_BAR})", _no_killer, since=X.WRITTEN, extra={"kind": "killer"}),
            X.Strategy("TK 50%+ accas: no slip-killer leg", "safe3",
                       "50%+ accas with no leg from a slip-killer class", _no_killer, since=X.WRITTEN,
                       extra={"kind": "killer"})]


def save(pm: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pm, indent=1, sort_keys=True), encoding="utf-8")


def worst(pm: dict, k: int = 5) -> list[tuple[str, dict]]:
    """Classes losing most beyond what they state (15+ legs), worst first."""
    rows = [(c, r) for c, r in pm.get("classes", {}).items() if r["legs"] >= 15]
    return sorted(rows, key=lambda x: -x[1]["z"])[:k]


def line(pm: dict) -> str:
    """One line for the supervisor."""
    if not pm.get("slips_graded"):
        return "post-mortem: no graded slips yet"
    w = worst(pm, 1)
    top = (f"; worst class {w[0][0]}: lost {w[0][1]['lost']}/{w[0][1]['legs']} legs "
           f"({w[0][1]['loss_rate']:.0%} v {w[0][1]['stated_loss']:.0%} stated, z {w[0][1]['z']:+.1f})") if w else ""
    return (f"post-mortem: {pm['slips_lost']}/{pm['slips_graded']} slips lost; "
            f"{len(pm.get('killers', []))} killer class(es){top}")


def section(pm: dict) -> list[str]:
    """Weekly-review lines."""
    out = ["*Slip post-mortem* (legs in graded slips: lost v stated)",
           f"{pm.get('slips_lost', 0)} of {pm.get('slips_graded', 0)} slips lost, {pm.get('legs', 0)} distinct legs"]
    for c, r in worst(pm):
        out.append(f"  {c}: lost {r['lost']}/{r['legs']} ({r['loss_rate']:.0%} v {r['stated_loss']:.0%} stated, "
                   f"z {r['z']:+.1f}), killed {r['slips_killed']} slip(s)" + (" — KILLER" if r["killer"] else ""))
    out.append("Killer classes (50+ legs, z >= 2): " + (", ".join(pm.get("killers") or []) or "none yet"))
    return out


if __name__ == "__main__":
    pm = build(load())
    save(pm)
    print("\n".join(section(pm)))
