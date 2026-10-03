"""One-shot robust verification of the 2026-08-22 production run.

Settles BOTH the 9-accumulator file (46 legs) AND the full produced-bet
record (52 legs) against the corrected ESPN-authoritative scores in
data/manual_verification_2026-08-22.json.

DESIGN NOTES (why this exists as a separate, honest pass):
  * football-data.co.uk 2627-season files are EMPTY, so run_daily's
    verify_produced_bet() left all 52 produced legs PENDING — the daily run
    never settled its own picks (a structural gap, not a calibration truth).
  * The manual file was built to cover the acca legs; it carries NAME VARIANTS
    (Athletic Club vs Ath Bilbao, Espanyol vs Espanol, KV Mechelen, Sheffield
    Utd, Nottingham Forest, Celta Vigo, Estac Troyes, Como 1907, Fenerbahce
    accent, Le Mans v Stade Brestois 29). This pass normalizes names (accent-
    strip + lowercase + punctuation-strip + alias map) so every played fixture
    settles exactly once.
  * Two acca legs are DUPLICATES of settled legs (Fenerbahce v Konyaspor in
    Acca E, Espanyol v Real Madrid in Acca F). They settle from the same score.
  * Two Eredivisie legs (Feyenoord v AZ, Ajax v Zwolle) were MIS-DATED: ESPN
    shows Feyenoord's next match is 2026-08-23 and Ajax's is 2026-08-30 — they
    did NOT play on 2026-08-22, so they stay PENDING (honest, not fabricated).
  * Four legs are genuine ESPN coverage gaps (Ligue 2 / La Liga 2 / Swiss Super
    League) and stay PENDING — HR35, never guessed.

HR35: any fixture with no authoritative score stays PENDING. Nothing fabricated.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import markets as mkt  # noqa: E402

MANUAL = ROOT / "data" / "manual_verification_2026-08-22.json"
ACCA = ROOT / "acca_2026-08-22.json"
PRODUCED = ROOT / "output" / "boards" / "produced_2026-08-22.json"

# Known team-name aliases (normalize both sides before matching)
ALIASES = {
    "ath bilbao": "athletic club",
    "espanol": "espanyol",
    "sheffield utd": "sheffield united",
    "nottm forest": "nottingham forest",
    "celta vigo": "celta",
    "estac troyes": "troyes",
    "kv mechelen": "mechelen",
    "stade brestois 29": "brest",
    "le mans fc": "le mans",
    "como 1907": "como",
    "fenerbahce": "fenerbahce",   # accent handled by norm() anyway
    "ajax amsterdam": "ajax",
    "feyenoord rotterdam": "feyenoord",
    "az alkmaar": "az",
    "pec zwolle": "zwolle",
}


def norm(s: str) -> str:
    """Accent-strip + lowercase + strip punctuation + apply aliases."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIASES.get(s, s)


def load_scores():
    """Return dict keyed (norm_home, norm_away) -> (h, a, status)."""
    data = json.loads(MANUAL.read_text(encoding="utf-8"))
    out = {}
    for r in data.get("results", []):
        h, a = r["fixture"].split(" v ")
        key = (norm(h), norm(a))
        out[key] = (r.get("home_score"), r.get("away_score"), r.get("status"))
    return out


def settle(pick: str, h: int, a: int):
    """Return hit bool/None and the 1X2 result label."""
    hit = mkt.settle(pick, h, a)
    res = "HOME_WIN" if h > a else ("DRAW" if h == a else "AWAY_WIN")
    return hit, res


def settle_leg_from_scores(fixture: str, pick: str, scores: dict):
    """Return (hit, result_label, score_str) or (None, 'PENDING', None)."""
    h, a = fixture.split(" v ")
    key = (norm(h), norm(a))
    sc = scores.get(key)
    if not sc:
        return None, "PENDING", None
    hs, aw, status = sc
    if status == "postponed":
        return None, "POSTPONED", f"{hs}-{aw}"
    if status != "completed" or hs is None or aw is None:
        return None, "PENDING", None
    hit, res = settle(pick, hs, aw)
    return hit, res, f"{hs}-{aw}"


def main():
    scores = load_scores()
    print(f"[verify_aug22] authoritative scores loaded: {len(scores)}")

    # ---- ACCA FILE (46 legs) ----
    acca = json.loads(ACCA.read_text(encoding="utf-8"))
    total_w = total_l = total_p = 0
    print("\n=== ACCUMULATOR RESULTS (2026-08-22) ===")
    for acc in acca["accas"]:
        w = l = p = 0
        parts = []
        for leg in acc["legs"]:
            hit, res, sc = settle_leg_from_scores(leg["fixture"],
                                                   leg["market_key"], scores)
            mark = "✓" if hit else ("✗" if hit is False else "⏳")
            parts.append(f"   {mark} {leg['fixture']} [{leg['market_key']}] "
                         f"-> {res} {sc or ''}")
            if hit is None:
                p += 1
            elif hit:
                w += 1
            else:
                l += 1
        total_w += w; total_l += l; total_p += p
        outcome = "WIN" if p == 0 and l == 0 else ("LOSS" if l > 0 else "PENDING")
        print(f"\n{acc['label']} — {outcome} ({w}/{acc['n_legs']} won, "
              f"{l} lost, {p} pending)  @ {acc['combined_odds']:.2f}")
        for line in parts:
            print(line)
    print(f"\nACCA TOTALS: {total_w}W / {total_l}L / {total_p}P "
          f"of {total_w+total_l+total_p} legs "
          f"(win rate settled: {100*total_w/(total_w+total_l):.1f}%)")

    # ---- PRODUCED-BET RECORD (52 legs) ----
    prod = json.loads(PRODUCED.read_text(encoding="utf-8"))["legs"]
    pw = pl = pp = 0
    miss = []
    pend = []
    for leg in prod:
        hit, res, sc = settle_leg_from_scores(leg["fixture"], leg["pick"], scores)
        if hit is None:
            pp += 1
            pend.append(leg["fixture"])
            continue
        if hit:
            pw += 1
        else:
            pl += 1
            miss.append((leg["fixture"], sc, leg["pick"]))
    print("\n\n=== PRODUCED-BET RECORD (52 rated legs, 2026-08-22) ===")
    print(f"Settled: {pw}W / {pl}L  |  Pending/coverage: {pp}")
    print(f"Win rate (settled): {100*pw/(pw+pl):.1f}%")
    print("\nMISSES:")
    for m in miss:
        print(f"   ✗ {m[0]}  actual {m[1]}  [{m[2]}]")
    print(f"\nPENDING / NOT IN AUTHORITATIVE FILE ({pp}):")
    for p in pend:
        print(f"   ⏳ {p}")


if __name__ == "__main__":
    main()
