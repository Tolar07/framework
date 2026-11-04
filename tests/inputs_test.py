"""Candidate inputs (2026-10-28): H2H venue-aware + time-decayed, form split, xG form — no leakage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import inputs_study as st  # noqa: E402
from engine import inputs as ip  # noqa: E402

ms = [{"date": "2020-01-01", "home": "A", "away": "B", "hg": 0, "ag": 3},   # old, same venue
      {"date": "2025-09-01", "home": "B", "away": "A", "hg": 1, "ag": 1},   # reverse venue
      {"date": "2026-03-01", "home": "A", "away": "B", "hg": 2, "ag": 0},   # recent, same venue
      {"date": "2026-10-28", "home": "A", "away": "B", "hg": 9, "ag": 0}]   # the day itself: never read
H = ip.History(ms)
h = ip.h2h(H, "A", "B", "2026-10-28")
assert h["n"] == 2 and 0 < h["gd"] < 2, h   # 2020 is past H2H_MAX_YEARS; the 2-0 at home outweighs the away draw
assert ip.h2h(H, "A", "B", "2020-01-01") is None, "nothing before the first meeting"
assert ip.h2h(H, "A", "B", "2025-12-01")["n"] == 2, "within six years the 2020 meeting counts"
assert ip.h2h(H, "A", "C", "2026-10-28") is None
for i, (hg, ag) in enumerate([(2, 0), (1, 1), (0, 1), (3, 0), (2, 2), (1, 0), (0, 0)]):
    ms.append({"date": f"2026-0{1 + i % 8}-1{i}", "home": "A" if i % 2 == 0 else "C",
               "away": "C" if i % 2 == 0 else "A", "hg": hg, "ag": ag})
H = ip.History(ms)
f = ip.form(H, "A", "2026-10-01")
assert f and f["n"] == 6, f
assert ip.form(H, "A", "2026-10-01", "home")["n"] >= 3
assert ip.fixture_features(H, "A", "B", "2026-10-28")["h2h_gd"] is not None
print("h2h venue-aware + decayed, form split, before-the-day only: OK")

rows = [(f"2026-01-{1 + i // 10:02d}", 0.5, i % 2, float(i % 2), None) for i in range(400)]
s, scored = st.wf_preds(rows)
assert s["brier_gain"] > 0 and s["verdict"] == "ADDS INFORMATION", s
assert all(d > "2026-01-01" for d, *_ in scored), "the first days only train"
noise = [(f"2026-01-{1 + i // 10:02d}", 0.5, i % 2, float((i * 7) % 3), None) for i in range(400)]
assert st.wf_preds(noise)[0]["verdict"] != "ADDS INFORMATION"
print("walk-forward input test: a real signal passes, noise does not: OK")

# lineups / injuries (issue #217): the missing-share feature, walk-forward, never filled in
docs = [(f"2026-10-{1 + i // 10:02d}", {f"H{i} v A{i}": {
    "ft": "1-0" if i % 2 else "0-1", "model_p": [0.4, 0.3, 0.3, 0.8, 0.5, 0.2, 0.5],
    "news": {"home_missing": 0.0 if i % 2 else 0.4, "away_missing": 0.4 if i % 2 else 0.0}}}) for i in range(300)]
docs.append(("2026-11-01", {"X v Y": {"ft": "1-0", "model_p": [0.4, 0.3, 0.3, 0.8, 0.5, 0.2, 0.5],
                                      "news": {"home_missing": "PENDING", "away_missing": "PENDING"}},
                            "P v Q": {"ft": "PENDING", "model_p": [0.4, 0.3, 0.3, 0.8, 0.5, 0.2, 0.5],
                                      "news": {"home_missing": 0.1, "away_missing": 0.2}}}))
nr = st.news_rows(docs)
assert len(nr["home win | missing edge"]) == 300, "PENDING news or result is skipped, not invented"
s, _ = st.wf_preds(nr["home win | missing edge"])
assert s["verdict"] == "ADDS INFORMATION", s   # an absence edge that decides the result is picked up
print("lineup / injury missing-share input: skipped when PENDING, walk-forward verdict: OK")
vc = st.vs_close(st.wf_preds(nr["home win | missing edge"])[1])
assert vc["n"] == 0 and vc["clv"] == "PENDING", "no sharp close in the rows: PENDING, not invented"
for d_, doc in docs[:300]:
    for r_ in doc.values():
        r_["close"] = {"sharp": {"home": 0.5, "away": 0.3, "over25": 0.5, "btts": 0.5}}
nr2 = st.news_rows(docs)
vc = st.vs_close(st.wf_preds(nr2["home win | missing edge"])[1])
assert vc["n"] > 0 and vc["sharp_close"] is not None and vc["clv"] == "PENDING", vc
print("lineup / injury vs the sharp close: Brier compared, CLV PENDING (no opening price stored): OK")

# motivation / table (issue #218): season-to-date table before the day, stakes only late in the season
tm = []
names = [f"T{i}" for i in range(10)]
d = 0
for rnd in range(2):                       # a full double round robin: 18 games each
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d += 1
            h, w = (a, b) if rnd == 0 else (b, a)
            tm.append({"date": f"2026-{9 + d // 100:02d}-{1 + d % 28:02d}", "home": h, "away": w,
                       "hg": 1 if names.index(h) < names.index(w) else 0, "ag": 0 if names.index(h) < names.index(w) else 1})
HT = ip.History(tm)
late = "2027-06-01"
tf = ip.table_features(HT, "T0", "T9", late)
assert tf["table_ppg_gap"] > 2 and tf["table_stakes"] == 0.0, tf   # both ends of the table have a stake
assert ip.table_features(HT, "T0", "T5", late)["table_stakes"] == 1.0
early = ip.table_features(HT, "T0", "T9", "2026-08-15")
assert early["table_ppg_gap"] is None and early["table_stakes"] is None, "thin table reads None, not 0"
assert all(r["played"] == 18 for r in ip.table_asof(HT, late).values())
tm.append({"date": "2027-05-31", "home": "T0", "away": "T9", "hg": 9, "ag": 0})
assert ip.table_asof(ip.History(tm), "2027-05-31")["T0"]["played"] == 18, "the day itself is never read"
assert "table_ppg_gap" in ip.fixture_features(HT, "T0", "T9", late)
print("motivation / table input: before-the-day table, late-season stakes, thin table None: OK")
