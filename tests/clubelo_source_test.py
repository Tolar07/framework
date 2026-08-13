"""ClubElo stretch source tests (Architect 2026-08-12).

Covers: snapshot cache read, placeholder-cluster DROP (a shared Elo value
across clubs is a provisional placeholder, not a rating — HR35), name
resolution via normalize + CLUBELO_ALIASES, and the honest None for a team
the snapshot does not rate.

Network: `fetch_snapshot` is best-effort (returns the cache, else empty). The
test seeds a temp cache so it is deterministic and offline — it never depends
on ClubElo being reachable.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

# Fix __file__ when running via exec
if '__file__' not in globals():
    __file__ = r'c:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\tests\clubelo_source_test.py'

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.clubelo_source as cl
import data.retry as retry


def _seed(tmp: Path, clubs: list[dict]) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "2026-08-11.json").write_text(json.dumps(
        {"date": "2026-08-11", "clubs": clubs}), encoding="utf-8")


def _patch_cache(tmp: Path) -> mock._patch:
    return mock.patch.object(cl, "CACHE_DIR", tmp)


# --- 1. snapshot cache read + normalize match --------------------------------
tmp1 = Path(tempfile.mkdtemp(prefix="olp_xdv_clubelo_"))
_seed(tmp1, [
    {"club": "Celje", "country": "SVN", "level": "1", "elo": 1455.0},
    {"club": "NK Domzale", "country": "SVN", "level": "1", "elo": 1400.0},
])
with _patch_cache(tmp1):
    table = cl.ratings()
assert table.get("celje") == 1455.0, "normalized exact match must resolve"
assert table.get("nk domzale") == 1400.0, "prefix-stripped normalize works"
print("1. snapshot cache read + normalize match: OK")

# --- 2. placeholder-cluster DROP --------------------------------------------
# Three clubs sharing one Elo value = ClubElo parking newly-added clubs on a
# shared league/default (Beveren/Lommel/Kortrijk all = 1350.29). A shared
# value is a PLACEHOLDER, never a rating — all three must be dropped (HR35).
tmp2 = Path(tempfile.mkdtemp(prefix="olp_xdv_clubelo_"))
_seed(tmp2, [
    {"club": "Beveren", "country": "BE", "level": "1", "elo": 1350.29},
    {"club": "Lommel", "country": "BE", "level": "1", "elo": 1350.29},
    {"club": "Kortrijk", "country": "BE", "level": "1", "elo": 1350.29},
    {"club": "Celje", "country": "SVN", "level": "1", "elo": 1455.0},
])
with _patch_cache(tmp2):
    table = cl.ratings()
assert "beveren" not in table, "shared-value club is a placeholder — dropped"
assert "lommel" not in table and "kortrijk" not in table, "whole cluster dropped"
assert table.get("celje") == 1455.0, "unique-value club survives the drop"
assert cl.elo_for("Beveren") is None, "elo_for must honor the drop (HR35)"
print("2. placeholder-cluster drop (shared Elo value): OK")

# --- 3. alias resolution (verified spellings only) ---------------------------
tmp3 = Path(tempfile.mkdtemp(prefix="olp_xdv_clubelo_"))
_seed(tmp3, [
    {"club": "Bodoe Glimt", "country": "NO", "level": "1", "elo": 1708.0},
    {"club": "Sabah", "country": "AZ", "level": "1", "elo": 1311.0},
    {"club": "Alkmaar", "country": "NL", "level": "1", "elo": 1531.0},
])
with _patch_cache(tmp3):
    assert cl.elo_for("Bodo/Glimt") == 1708.0, "alias Bodo/Glimt -> Bodoe Glimt"
    assert cl.elo_for("Sabah Baku") == 1311.0, "alias Sabah Baku -> Sabah"
    assert cl.elo_for("AZ Alkmaar") == 1531.0, "alias AZ Alkmaar -> Alkmaar"
print("3. CLUBELO_ALIASES resolution: OK")

# --- 4. honest None for a team the snapshot does not rate --------------------
tmp4 = Path(tempfile.mkdtemp(prefix="olp_xdv_clubelo_"))
_seed(tmp4, [{"club": "Celje", "country": "SVN", "level": "1", "elo": 1455.0}])
with _patch_cache(tmp4):
    assert cl.elo_for("Hapoel Be'er Sheva") is None, "absent team -> None (HR35)"
    assert cl.elo_for("") is None, "empty name -> None"
print("4. absent team -> None (HR35, never a guessed strength): OK")

# --- 5. fetch_snapshot best-effort on a network failure ----------------------
# fetch_snapshot with an unreachable source must fall back to the cache, and
# with NO cache at all return an honest empty payload — never raise.
tmp5 = Path(tempfile.mkdtemp(prefix="olp_xdv_clubelo_"))
_seed(tmp5, [{"club": "Celje", "country": "SVN", "level": "1", "elo": 1455.0}])
with _patch_cache(tmp5), mock.patch.object(
        retry, "request", side_effect=RuntimeError("down")):
    payload = cl.fetch_snapshot("2026-08-11")  # cache hit path
assert payload.get("clubs"), "cached snapshot served on network failure"
empty_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_clubelo_"))
with _patch_cache(empty_tmp), mock.patch.object(
        retry, "request", side_effect=RuntimeError("down")):
    payload = cl.fetch_snapshot("2026-08-12")
assert payload.get("clubs") == [], "no cache -> honest empty, never raise"
print("5. fetch_snapshot best-effort (cache on failure, empty if none): OK")

print(f"\nclubelo_source_test: ALL 5 PASSED")
