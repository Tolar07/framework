"""
MATCHBOOK EVIDENCE — what the live Matchbook agent learned, fed back here.

Architect 2026-10-15: "The framework should also be training the bots ... I
want the bot to have recursive self-improvement", and a constant back-and-forth
between the bot and the framework.

The bot (Tolar07/matchbook-agent, private; runs on the Architect's UK machine)
reads this repo's picks every 15 minutes and bets them on Matchbook. Each run it
commits its graded ledger to its own repo's ledger/. `matchbook_ledger.yml`
fetches that file with a read-only deploy key and this module turns it into
evidence the framework can see: per market family and per source, how many
bets, how many won, and the mean CLV against Matchbook's closing price — the
first measure this framework has of its picks against a sharp exchange's close.

THIS REPO IS PUBLIC. Only anonymised counts and rates are written
(data/matchbook/summary.json): no stake, no £ figure, no balance, no offer or
account id. The raw ledger never touches this repo.

ORDER 44 (Architect 2026-10-15) makes it steer selection: engine/learning.py
reads the "framework family: ..." groups (the framework's own bets only, not
the agent's oracle) and shifts each market family's chances by its mean CLV
against Matchbook's close, capped at 5 points, once it has 30 bets with a
close. The bot also acts on it itself: it pauses any source x market group
whose bets keep losing to the close.

    python monitor/matchbook_ledger.py <ledger.jsonl> <out summary.json> [<paper.jsonl>]

The agent's PAPER STUDY (ledger/paper.jsonl: rules FW-ALL / FW-MED / F2 / F9 / F10 priced at
Matchbook, no money) is summarised the same way into "paper" (2026-10-19, task item 3: the
framework results, the Matchbook ledger and the paper studies feed one shared memory).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC
from pathlib import Path

FAMILY = {"Match Odds": "1X2", "Total": "Over/Under", "Double Chance": "Double chance",
          "Handicap": "Asian handicap", "Both Teams To Score": "BTTS", "Draw No Bet": "Draw no bet"}
SOURCE = {"oracle": "oracle (blind LLM)", "pick": "framework pick", "pool": "framework rated market"}
SUMMARY = Path(__file__).resolve().parent.parent / "data" / "matchbook" / "summary.json"


def _source(row: dict) -> str:
    if row.get("source") != "framework":
        return SOURCE["oracle"]
    return SOURCE["pool"] if row.get("fw_pool") else SOURCE["pick"]


def _clv(row: dict) -> float | None:
    try:
        return float(row["avg_odds"]) / float(row["close_back"]) - 1
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def summarise(rows: list[dict]) -> dict:
    """Anonymised: counts and rates only."""
    groups: dict = {}
    for r in rows:
        if r.get("status") in (None, "VOID"):
            continue
        fam = FAMILY.get(r.get("market_name") or "", r.get("market_name") or "PENDING")
        keys = [f"family: {fam}", f"source: {_source(r)}", "all"]
        if r.get("source") == "framework":
            keys.append(f"framework family: {fam}")      # order 44 reads these
        for key in keys:
            g = groups.setdefault(key, {"bets": 0, "settled": 0, "won": 0, "lost": 0,
                                        "clv_n": 0, "clv_sum": 0.0, "chance_sum": 0.0})
            g["bets"] += 1
            if r["status"] in ("WON", "LOST"):
                g["settled"] += 1
                g["won" if r["status"] == "WON" else "lost"] += 1
                g["chance_sum"] += float(r.get("oracle_p") or 0)
                c = _clv(r)
                if c is not None:
                    g["clv_n"] += 1
                    g["clv_sum"] += c
    out = {}
    for k, g in sorted(groups.items()):
        out[k] = {"bets": g["bets"], "settled": g["settled"], "won": g["won"], "lost": g["lost"],
                  "expected_wins": round(g["chance_sum"], 2),
                  "mean_clv": round(g["clv_sum"] / g["clv_n"], 4) if g["clv_n"] else None,
                  "clv_n": g["clv_n"]}
    return out


def summarise_paper(rows: list[dict]) -> dict:
    """Anonymised, per rule and per 'rule | family': graded, won vs expected, flat return, CLV."""
    groups: dict = {}
    for r in rows:
        if r.get("status") not in ("WIN", "LOSS"):
            continue
        fam = FAMILY.get(r.get("market_name") or "", r.get("market_name") or "PENDING")
        for key in (r.get("rule") or "?", f"{r.get('rule') or '?'} | {fam}"):
            g = groups.setdefault(key, {"n": 0, "won": 0, "p": 0.0, "ret": 0.0, "clv_n": 0, "clv": 0.0})
            won = r["status"] == "WIN"
            g["n"] += 1
            g["won"] += won
            g["p"] += float(r.get("p") or 0)
            g["ret"] += (float(r.get("odds") or 1) - 1) if won else -1
            try:
                g["clv"] += float(r["odds"]) / float(r["close"]) - 1
                g["clv_n"] += 1
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                pass
    return {k: {"graded": g["n"], "won": g["won"], "expected_wins": round(g["p"], 1),
                "flat_return": round(g["ret"] / g["n"], 4),
                "mean_clv": round(g["clv"] / g["clv_n"], 4) if g["clv_n"] else None}
            for k, g in sorted(groups.items())}


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def lines(summary_path: Path = SUMMARY) -> list[str]:
    """For the weekly review / debrief."""
    if not summary_path.exists():
        return ["Matchbook (live agent): PENDING — no ledger fetched yet"]
    s = json.loads(summary_path.read_text(encoding="utf-8"))
    groups = s.get("groups") or {}
    if not groups:
        return [f"Matchbook (live agent): no bets yet (ledger read {s.get('fetched', 'PENDING')})"]
    out = [f"Matchbook (live agent, ledger read {s.get('fetched', 'PENDING')}) — "
           "won vs expected, and CLV against Matchbook's closing price:"]
    for k, g in groups.items():
        clv = "PENDING" if g["mean_clv"] is None else f"{g['mean_clv']:+.1%} over {g['clv_n']}"
        out.append(f"  {k}: {g['bets']} bets, {g['won']}/{g['settled']} won "
                   f"(expected {g['expected_wins']:.1f}), CLV {clv}")
    paper = {k: v for k, v in (s.get("paper") or {}).items() if "|" not in k}
    if paper:
        out.append("Matchbook paper study (no money), by rule:")
        for k, g in paper.items():
            clv = "PENDING" if g["mean_clv"] is None else f"{g['mean_clv']:+.1%}"
            exp = f"expected {g['expected_wins']:.1f}" if g["expected_wins"] else "no model chance"
            out.append(f"  {k}: {g['won']}/{g['graded']} won ({exp}), "
                       f"flat return {g['flat_return']:+.1%}, CLV {clv}")
    return out


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    rows = load(Path(argv[1]))
    from datetime import datetime
    doc = {"fetched": datetime.now(UTC).strftime("%Y-%m-%d"), "rows_read": len(rows),
           "groups": summarise(rows)}
    if len(argv) == 4:
        doc["paper"] = summarise_paper(load(Path(argv[3])))
    out = Path(argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
