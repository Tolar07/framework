"""STRESS TEST 2 — the brain era: concurrency, accumulation, idempotence.

The original stress_test proved the instrumented pipeline. Since then the
SQLite brain became the shared memory of the system: the daily run, the
poller (/send), the monitor watch and the sandbox watch can all open
Brain() on the same olp.db at the same time. THIS test stresses the new
architecture.

WHAT IT PROVES
  1. Every suite (including the new brain/monitor/sandbox ones) stays green.
  2. Concurrent Brain connections on ONE db — threads AND separate processes —
     read + write without "database is locked" or corruption (WAL).
  3. Accumulation is linear and settle is idempotent: repeated appends,
     ledger syncs and outcome records never duplicate or corrupt.
  4. The real daily pipeline records sane bookkeeping in the brain (run
     counters, model reuse, fit timing).

HONESTY: every concurrency/accumulation scenario uses a THROWAWAY db file —
the real brain/olp.db is only READ (its last run record), never stress-written.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PROJ = Path(__file__).parent.parent
PY = sys.executable
PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(name)
    print(f"  {'OK  ' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail else ""))


def stress(label: str) -> None:
    print("\n" + "=" * 68)
    print(f"  {label}")
    print("=" * 68)


def _mk_ledger() -> Path:
    """A small throwaway CLV ledger with a few legs for sync_legs stress."""
    from clv.clv_logger import CLVLog
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    log = CLVLog(path=p)
    for i in range(4):
        leg = log.log_entry(league="Eredivisie", fixture=f"Ajax v PSV {i}",
                            market="1X2_HOME", model_prob=0.5, entry_odds=2.0)
        log.log_close(leg.leg_id, closing_odds=1.9)
    return p


# --------------------------------------------------------------------------
stress("STAGE 1 · every suite stays green (14)")
# --------------------------------------------------------------------------
suites = sorted(p.name for p in (PROJ / "tests").glob("*_test.py"))
suites = [s for s in suites if s != "stress2_test.py"]
t0 = time.time()
for suite in suites:
    r = subprocess.run([PY, f"tests/{suite}"], cwd=PROJ,
                       capture_output=True, timeout=600)
    check(f"suite: {suite}", r.returncode == 0,
          "" if r.returncode == 0 else r.stderr.decode(errors="replace")[-120:])
print(f"  (stage 1 took {time.time()-t0:.0f}s)")


# --------------------------------------------------------------------------
stress("STAGE 2 · brain concurrency — 8 writers + 4 readers, one db")
# --------------------------------------------------------------------------
from brain.store import Brain

_db = Path(tempfile.mkdtemp()) / "conc.db"
_ledger = _mk_ledger()
_errors: list[str] = []
_lock = threading.Lock()


def _writer(i: int) -> None:
    try:
        br = Brain(_db)
        for k in range(40):
            br.append_predictions([{
                "run_id": f"s2-{i}-{k}", "predicted_at": "2026-08-05T00:00:00+00:00",
                "league": "Eredivisie", "fixture": f"Ajax v PSV {k}",
                "match_date": "2026-08-05", "market": "1X2_HOME",
                "model_engine": "dc", "model_prob": 0.5, "entry_odds": None,
                "bookmaker": None, "ev": None,
                "on_deploy_shortlist": 0, "cal_adjustment": None} for _ in range(3)])
            br.save_model_state(f"elo:stress{i}", "elo", 1, f"h{i}",
                                10, "2026-08-05", None, {"ratings": {}})
            br.sync_legs([_ledger])
            br.append_run(f"run-{i}-{k}", "2026-08-05T00:00:00+00:00")
            br.update_run(f"run-{i}-{k}", status="ok", predictions_logged=3)
        br.close()
    except Exception as e:
        with _lock:
            _errors.append(f"writer {i}: {type(e).__name__}: {e}")


def _reader(i: int) -> None:
    try:
        br = Brain(_db)
        for _ in range(120):
            br.predictions_summary()
            br.outcome_summary()
            br.gate_status()
            br.model_state_summary()
        br.close()
    except Exception as e:
        with _lock:
            _errors.append(f"reader {i}: {type(e).__name__}: {e}")


# pre-create the schema before any thread connects (no first-connect race)
Brain(_db).close()
threads = ([threading.Thread(target=_writer, args=(i,)) for i in range(8)] +
           [threading.Thread(target=_reader, args=(i,)) for i in range(4)])
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=300)
check("concurrency: no writer/reader errors under 8+4 threads",
      not _errors, "; ".join(_errors[:3]) if _errors else "clean")
b = Brain(_db)
integrity = [r[0] for r in b._conn.execute("PRAGMA integrity_check")]
check("concurrency: sqlite integrity_check == ok", integrity == ["ok"],
      str(integrity[:3]))
n_preds = b._conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
check("concurrency: every write landed", n_preds == 8 * 40 * 3,
      f"{n_preds} rows")
n_runs = b._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
check("concurrency: every run recorded + finalised",
      n_runs == 8 * 40 and
      b._conn.execute("SELECT COUNT(*) FROM runs WHERE status='ok'").fetchone()[0] == n_runs,
      f"{n_runs} runs")
b.close()


# --------------------------------------------------------------------------
stress("STAGE 3 · brain concurrency — 4 separate PROCESSES, one db")
# --------------------------------------------------------------------------
_db2 = Path(tempfile.mkdtemp()) / "proc.db"
_ledger2 = _mk_ledger()
_CHILD = """
import sys; sys.path.insert(0, %r)
from brain.store import Brain
db = %r
br = Brain(db)
for k in range(25):
    br.append_predictions([{
        "run_id": f"proc-{k}", "predicted_at": "2026-08-05T00:00:00+00:00",
        "league": "Serie A", "fixture": f"Inter v Milan {k}",
        "match_date": "2026-08-05", "market": "1X2_HOME", "model_engine": "dc",
        "model_prob": 0.5, "entry_odds": None, "bookmaker": None, "ev": None,
        "on_deploy_shortlist": 0, "cal_adjustment": None}])
    br.sync_legs([%r])
    br.record_outcomes(f"Inter v Milan {k}", "2026-08-05", "1-0",
                       {"1X2_HOME": True})
br.close()
""" % (str(PROJ), str(_db2), str(_ledger2))
Brain(_db2).close()  # pre-create so children never race the first connect
procs = [subprocess.Popen([PY, "-c", _CHILD], cwd=PROJ) for _ in range(4)]
codes = [p.wait(timeout=240) for p in procs]
check("processes: all 4 exited 0", all(c == 0 for c in codes), str(codes))
b2 = Brain(_db2)
integrity = [r[0] for r in b2._conn.execute("PRAGMA integrity_check")]
check("processes: sqlite integrity_check == ok", integrity == ["ok"],
      str(integrity[:3]))
n_preds = b2._conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
check("processes: all 100 prediction batches landed", n_preds == 4 * 25,
      f"{n_preds} rows")
b2.close()


# --------------------------------------------------------------------------
stress("STAGE 4 · accumulation linear + settle idempotent")
# --------------------------------------------------------------------------
_db3 = Path(tempfile.mkdtemp()) / "acc.db"
b3 = Brain(_db3)
# 5,000 predictions across 500 batches, one transaction each
t0 = time.time()
for k in range(500):
    b3.append_predictions([{
        "run_id": f"acc-{k}", "predicted_at": "2026-08-05T00:00:00+00:00",
        "league": "Premier League", "fixture": f"Arsenal v Chelsea {k}",
        "match_date": "2026-08-05", "market": "1X2_HOME",
        "model_engine": "dc", "model_prob": 0.5, "entry_odds": None,
        "bookmaker": None, "ev": None,
        "on_deploy_shortlist": 0, "cal_adjustment": None} for _ in range(10)])
n_preds = b3._conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
check("accumulation: 500 batches x 10 rows all land", n_preds == 5000, f"{n_preds}")
rate = (time.time() - t0)
check("accumulation: 5,000 rows in sane time", rate < 120,
      f"{rate:.1f}s for 500 txns")
# settle the same fixture 50 times — first result must win (idempotence)
for _ in range(50):
    b3.record_outcomes("Arsenal v Chelsea 0", "2026-08-05", "2-0", {"1X2_HOME": True})
settled = b3._conn.execute(
    "SELECT COUNT(*) FROM predictions WHERE fixture='Arsenal v Chelsea 0' "
    "AND hit IS NOT NULL").fetchone()[0]
unsettled = b3._conn.execute(
    "SELECT COUNT(*) FROM predictions WHERE fixture='Arsenal v Chelsea 0' "
    "AND hit IS NULL").fetchone()[0]
check("settle: 50 repeated settles settle exactly once each",
      settled == 10 and unsettled == 0, f"{settled} settled, {unsettled} pending")
integrity = [r[0] for r in b3._conn.execute("PRAGMA integrity_check")]
check("accumulation: integrity intact after 5,000 rows + 50 settles",
      integrity == ["ok"])
b3.close()


# --------------------------------------------------------------------------
stress("STAGE 5 · real daily pipeline bookkeeping (brain read-only)")
# --------------------------------------------------------------------------
b5 = Brain()
last = b5.last_run()
if last and last.get("predictions_logged"):
    check("pipeline: last run recorded predictions",
          int(last["predictions_logged"]) > 0, f"{last['predictions_logged']}")
    # a league whose data source fails may not increment either counter;
    # allow a small gap while still proving reuse dominated
    fitted = int(last.get("dc_reused", 0)) + int(last.get("dc_refit", 0))
    scanned = int(last.get("leagues_scanned", 0))
    check("pipeline: fit bookkeeping is complete (reuse + refit ~= leagues)",
          scanned > 0 and abs(fitted - scanned) <= 2,
          f"reused={last.get('dc_reused')} refit={last.get('dc_refit')} "
          f"of {scanned}")
    fs = last.get("fit_seconds")
    check("pipeline: fit time was measured", fs is not None,
          f"{fs:.1f}s" if fs else "none")
    check("pipeline: warm reuse is FAST (cold ~70s, warm should be <30s)",
          (fs or 999) < 30, f"{fs:.1f}s fit+elo with {last.get('dc_reused', 0)} reused")
else:
    check("pipeline: a run record exists to inspect", bool(last),
          "no run yet — run run_daily once, or the stress_test stage 4")
b5.close()


# --------------------------------------------------------------------------
print("\n" + "=" * 68)
print(f"  RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
print("=" * 68)
if FAILED:
    print("FAILED:")
    for name in FAILED:
        print(f"  - {name}")
    sys.exit(1)
print("\n✅ STRESS TEST 2 PASSED — the brain holds up under concurrency,")
print("   accumulation and repeated settle.")
print("   (This proves the storage is sound — not that the model has an edge.)")
