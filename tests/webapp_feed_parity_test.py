"""Feed parity test — the web page IS the Telegram board (Architect 2026-08-11).

One render, two outlets: `engine.acca.render_production_block` produces the
Telegram body the Architect reads, and `render_v2.render_dashboard` renders the
same content on the web. This suite builds ONE `ProductionBets` object, renders
the Telegram text from it, renders the web page from the same accas, then
asserts every substantive Telegram line (★ Acca A — HEADLINE / legs /
Combined · Booking code / singles) is a substring of the normalized page text.

The parity anchor is byte-faithful — a missing " — " separator, a dropped leg,
a reworded Combined line, or a fabricated booking code all fail here.
"""
import html as _html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import acca as A            # AccaLeg / Acca / ProductionBets
from webapp import render_v2, schema


# --- ONE production shape, shared by both outlets -----------------------------
def _leg(fixture, league, market_name, price, prob, ev):
    return A.AccaLeg(fixture=fixture, league=league, market_key="1X2_HOME",
                     market_name=market_name, price=price, prob=prob, ev=ev)


_bets = A.ProductionBets(
    acca_a=A.Acca(
        label="Acca A",
        legs=[_leg("Fenerbahce v Sturm Graz", "Champions League",
                   "Fenerbahce to win", 1.91, 0.56, 0.0696)],
        combined_odds=1.91, combined_prob=0.56),
    split_accas=[A.Acca(
        label="Acca B",
        legs=[_leg("Beta v Gamma", "Eredivisie", "Beta to win", 1.80, 0.61, 0.098),
              _leg("Delta v Epsilon", "Eredivisie", "Delta to win", 1.75, 0.55, 0.0625)],
        combined_odds=1.80 * 1.75, combined_prob=0.61 * 0.55)],
    singles=[_leg("Beta v Gamma", "Eredivisie", "Beta to win", 1.80, 0.61, 0.098),
             _leg("Delta v Epsilon", "Eredivisie", "Delta to win", 1.75, 0.55, 0.0625)])

_CODES = {"results": [
    {"label": "Acca A", "code": "AA111",
     "per_leg": [{"fixture": "Fenerbahce v Sturm Graz (Champions League)"}]},
    {"label": "Acca B", "code": "AB222",
     "per_leg": [{"fixture": "Beta v Gamma (Eredivisie)"},
                 {"fixture": "Delta v Epsilon (Eredivisie)"}]},
    {"label": "SINGLE — Beta v Gamma", "code": "SB_BETA",
     "per_leg": [{"fixture": "Beta v Gamma (Eredivisie)"}]},
    {"label": "SINGLE — Delta v Epsilon", "code": "SB_DELTA",
     "per_leg": [{"fixture": "Delta v Epsilon (Eredivisie)"}]},
]}

# --- outlet 1: Telegram text (the Architect's source of truth) ----------------
TG = A.render_production_block(_bets, codes=_CODES, today="2026-08-10")

# --- outlet 2: the web page, fed the same accas -------------------------------
def _raw_acca(a: A.Acca) -> dict:
    return {"label": a.label,
            "legs": [{"fixture": l.fixture, "league": l.league,
                      "market_key": l.market_key, "market_name": l.market_name,
                      "price": l.price, "prob": l.prob, "ev": l.ev}
                     for l in a.legs],
            "combined_odds": a.combined_odds, "combined_prob": a.combined_prob,
            "n_legs": a.n_legs}


_web_accas = ([_raw_acca(_bets.acca_a)]
              + [_raw_acca(a) for a in _bets.split_accas]
              + [_raw_acca(a) for a in A.build_single_accas(_bets.singles)])

_payload = schema.build_payload(
    date="2026-08-10", phase="Phase 2 — paper calibration, zero capital",
    leagues_scanned=["Champions League", "Eredivisie"],
    board=[], data_flags=[],
    gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.2},
    telemetry={}, calibration_count=3, mean_clv=1.2,
    accas=_web_accas)

_feed = schema.build_feed_payload(_payload)
_PAGE = render_v2.render_dashboard(_feed, booking_codes=_CODES)


# --- normalization -------------------------------------------------------------
def _norm_page(text: str) -> str:
    """Visible page text: strip tags, drop the code-pill 'Copy' label, insert a
    space after 'Booking code:' (Telegram's separator), collapse whitespace."""
    t = re.sub(r"<[^>]+>", " ", text)
    t = _html.unescape(t)
    t = t.replace("Copy", "")
    t = t.replace("Booking code:", "Booking code: ")
    return re.sub(r"\s+", " ", t).strip()


def _norm_tg(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_pg = _norm_page(_PAGE)


def _assert_line(line: str) -> None:
    want = _norm_tg(line)
    assert want in _pg, (
        f"PARITY GAP — Telegram line not on the web page.\n"
        f"  Telegram: {want!r}\n"
        f"  Web page: {_pg[:600]}...")


# --- 1. every substantive Telegram line appears on the page -------------------
_lines = [l for l in TG.splitlines() if l.strip() and not l.startswith("🎯")]
assert _lines, "Telegram block must produce content lines"
for line in _lines:
    _assert_line(line)
print(f"1. all {len(_lines)} Telegram production lines present on the web page: OK")

# --- 2. explicit parity markers (self-documenting, HR35) ----------------------
for needle in ("★ Acca A — HEADLINE, 1 legs",
               "★ Acca B  2 legs",
               "SINGLES — one standalone slip each, own booking code"):
    assert _norm_tg(needle) in _pg, f"missing parity marker {needle!r}"
print("2. headline / split / singles markers present: OK")

# --- 3. booking codes ride through both outlets -------------------------------
for code in ("AA111", "AB222", "SB_BETA", "SB_DELTA"):
    assert f'data-code="{code}"' in _PAGE, f"web page missing booking code {code}"
    assert code in TG, f"Telegram missing booking code {code}"
print("3. all four booking codes on web page + Telegram: OK")

# --- 4. the em-dash separator is real, not a substitute -----------------------
# The Telegram leg format is `fixture (league) — market @ price`. Guard the
# exact " — " token after the league paren (the historical parity gap).
assert "Sturm Graz (Champions League) — Fenerbahce to win @ 1.91" in _pg
print("4. leg separator ' — ' byte-faithful on the web page: OK")

# --- 5. honest NO DATA — PENDING code line (HR35, no fabrication) -------------
_page_nocodes = render_v2.render_dashboard(
    schema.build_feed_payload(_payload), booking_codes=None)
assert _page_nocodes.count("NO DATA — PENDING") >= 4   # 2 accas + 2 singles
assert "data-code=" not in _page_nocodes
print("5. absent codes render honest NO DATA — PENDING (HR35): OK")

print("\n[OK] ALL FEED PARITY TESTS PASSED")
