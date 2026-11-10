"""Transfers (Architect 2026-11-09 plan, step 5): FotMob moves parsed, window sums, study links."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import transfers_study as st  # noqa: E402
from data import transfers as tr  # noqa: E402

page = {"transfers": {"allTransfers": [
    {"playerId": 1, "name": "In A", "transferDate": "2026-01-10T10:00:00Z", "toClubId": 9, "fromClubId": 5,
     "marketValue": 20_000_000, "onLoan": False, "position": {"label": "ST"}},
    {"playerId": 2, "name": "Out B", "transferDate": "2026-01-20T10:00:00Z", "toClubId": 7, "fromClubId": 9,
     "marketValue": None, "fee": {"value": 50_000_000}, "onLoan": False},
    {"playerId": 3, "name": "Ext", "transferDate": "2026-01-21T10:00:00Z", "toClubId": 9, "fromClubId": 9,
     "contractExtension": True},
    {"playerId": 4, "name": "Unknown", "transferDate": "2026-01-22T10:00:00Z", "toClubId": 9, "fromClubId": 3},
    {"playerId": 5, "name": "Summer", "transferDate": "2026-08-01T10:00:00Z", "toClubId": 9, "fromClubId": 3,
     "marketValue": 99_000_000},
    {"playerId": 1, "name": "In A", "transferDate": "2026-01-10T11:00:00Z", "toClubId": 9, "fromClubId": 5,
     "marketValue": 20_000_000}]}}
mv = tr.parse(page, 9)
assert [m["name"] for m in mv] == ["In A", "Out B", "Unknown", "Summer"], mv   # extension + duplicate dropped
assert mv[1]["value"] == 50_000_000 and mv[2]["value"] is None, "fee when no market value; unknown stays None"
w = tr.window(mv, *tr.winter_window("2026-03-01"))
assert w == {"n_in": 2, "n_out": 1, "value_in": 20e6, "value_out": 50e6, "net": -30e6, "top_out": 50e6}, w
assert tr.winter_window("2026-11-09") == ("2027-01-01", "2027-02-04")
print("transfers: parse (extensions, duplicates out), fee fallback, January window sums: OK")

assert st.slog(0) == 0 and st.slog(-30e6) < 0 < st.slog(30e6)
f = st.features(w, tr.window([], "2026-01-01", "2026-02-04"))
assert f["jan_net_gap"] < 0 and f["jan_out_gap"] > 0 and f["jan_moves"] == 3, f
ln = st.link(["Manchester City", "Arsenal", "Wolverhampton Wanderers"], ["Man City", "Arsenal", "Wolves", "Leeds"])
assert ln["Arsenal"] == "Arsenal" and ln.get("Man City") == "Manchester City" and "Leeds" not in ln, ln
print("transfers study: signed-log features, strict FotMob -> football-data link: OK")
