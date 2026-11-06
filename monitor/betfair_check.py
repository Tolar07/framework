"""
BETFAIR CHECK: is each sport and market beating the market? (Architect 2026-11-06: every new-sport pick is
placed on Betfair; judge each sport fast, by the closing price, and find chances that are too confident.)

Reads the Betfair bot's published ledgers (.bots/betfair-agent/ledger/paper_<day>.json), live bets that were
matched and settled, every sport incl. basketball (nba) and football. Two numbers per group (sport, then sport × market):

  CLV       our matched price ÷ Betfair's last back price before the start − 1 (liq_close.price, recorded
            since 05-11). Positive = we beat the closing price. It shows within a few weeks whether picks have
            an edge, long before wins and losses do.
  wins      actual wins next to the wins the PRICE expected (Σ 1/price) and the wins OUR CHANCE expected
            (Σ chance). z = (actual − price-expected) / sd. A group far below its price (z ≤ −2) loses more
            than bad luck explains: the picks are chosen badly or the chances are too confident.

Flags are for the Architect to decide on: nothing here stops, stakes or changes a bet. Record only (HR35: a
group without enough bets reads "too few yet").
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / ".bots" / "betfair-agent" / "ledger"
MIN_CLV = 20        # bets with a closing price before a sport's CLV is judged
MIN_WINS = 30       # settled bets before a group's wins are judged
Z_FLAG = -2.0


def settled(folder: Path = LEDGER) -> list[dict]:
    out = []
    for f in sorted(folder.glob("paper_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for b in d.get("bets") or []:
            if (b.get("mode") == "live" and b.get("result") in ("WON", "LOST")
                    and (b.get("size_matched") or 0) > 0 and "/" not in str(b.get("code"))):
                out.append(b)
    return out


def _price(b: dict) -> float:
    return float(b.get("avg_price") or b.get("price"))


def group(bets: list[dict]) -> dict:
    n = len(bets)
    won = sum(b["result"] == "WON" for b in bets)
    staked = sum(float(b.get("size_matched") or 0) for b in bets)
    pnl = sum(float(b.get("pnl") or 0) for b in bets)
    exp_price = sum(1 / _price(b) for b in bets)
    var = sum((1 / _price(b)) * (1 - 1 / _price(b)) for b in bets)
    chances = [b["chance"] for b in bets if isinstance(b.get("chance"), (int, float))]
    clv = [_price(b) / b["liq_close"]["price"] - 1 for b in bets
           if (b.get("liq_close") or {}).get("price")]
    return {"n": n, "won": won, "staked": round(staked, 2), "pnl": round(pnl, 2),
            "roi": round(pnl / staked, 4) if staked else None,
            "exp_price": round(exp_price, 1), "exp_chance": round(sum(chances), 1) if chances else None,
            "z": round((won - exp_price) / math.sqrt(var), 2) if var > 0 else None,
            "clv_n": len(clv), "clv": round(sum(clv) / len(clv), 4) if clv else None,
            "beat_close": sum(x > 0 for x in clv)}


def check(bets: list[dict]) -> dict:
    by_sport, by_market = defaultdict(list), defaultdict(list)
    for b in bets:
        sp = b.get("sport") or "football"
        by_sport[sp].append(b)
        by_market[(sp, b.get("market_type") or "?")].append(b)
    sports = {k: group(v) for k, v in by_sport.items()}
    markets = {f"{k[0]}|{k[1]}": group(v) for k, v in by_market.items()}
    flags = []
    for sp, g in sorted(sports.items()):
        if g["clv_n"] >= MIN_CLV and g["clv"] is not None and g["clv"] < 0:
            flags.append(f"{sp}: losing to the closing price ({g['clv']:+.1%} on {g['clv_n']} bets)")
    for key, g in sorted(markets.items()):
        if g["n"] >= MIN_WINS and g["z"] is not None and g["z"] <= Z_FLAG:
            sp, mt = key.split("|")
            flags.append(f"{sp} {mt.lower().replace('_', ' ')}: won {g['won']} of {g['n']}, the prices expected "
                         f"{g['exp_price']:.0f} (z {g['z']}); picks lose more than luck explains")
    return {"bets": len(bets), "sports": sports, "markets": markets, "flags": flags}


def lines(res: dict) -> list[str]:
    """The board's BETFAIR CHECK section."""
    if not res["bets"]:
        return ["No settled live Betfair bets yet — PENDING."]
    out = []
    for sp, g in sorted(res["sports"].items(), key=lambda kv: -kv[1]["n"]):
        clv = (f"CLV {g['clv']:+.1%} ({g['beat_close']}/{g['clv_n']} beat the close)" if g["clv_n"] >= MIN_CLV
               else f"CLV too few yet ({g['clv_n']} of {MIN_CLV})")
        roi = f"{g['roi']:+.1%}" if g["roi"] is not None else "PENDING"
        out.append(f"{sp.replace('_', ' ')}: {g['n']} bets, £{g['pnl']:+.2f} ({roi}) · won {g['won']}, "
                   f"prices expected {g['exp_price']:.0f} · {clv}")
    out += [f"⚠ {f}" for f in res["flags"]] or ["No sport or market flagged."]
    out.append("Flags are yours to decide on; nothing is stopped automatically.")
    return out


def main() -> None:
    res = check(settled())
    print("\n".join(lines(res)))
    p = ROOT / "data" / "study" / "betfair_check.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
