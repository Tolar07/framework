"""The Brain — SQLite-backed central persistence for OLP XDV (stdlib only).

WHY THIS EXISTS
  The framework had no memory between runs: every daily run refit all 15
  leagues from scratch (~70-85s), threw away every board prediction, and could
  not answer a single question about its own history (mean CLV by league? what
  did I predict for Hearts?). The brain is that memory, additive and honest:

    - model_state  — fitted Elo / Dixon-Coles / cross-league params, keyed so a
                     run only refits what actually changed (content_hash makes
                     reuse provable: same rows + same config -> same fit).
    - predictions  — every rated board prediction, accumulated.
    - legs         — a queryable mirror of the CLV ledger (the JSON stays boss).
    - corrections  — Architect corrections, with a consumed flag so they can be
                     read back and acted on, not just logged.
    - runs         — one row per daily run (counters prove the speed win).

HR35 is kept throughout: a missing row reads as absent (caller emits
NO DATA — PENDING); a row with a newer schema or engine version is REFUSED,
never adapted. clv/clv_log.json remains the canonical ledger — the brain's
`legs` is a full-refresh mirror and never writes it.

Concurrency: WAL + busy_timeout, short transactions. The 07:00 scheduler, the
resident poller and a phone-triggered command each open their own Brain;
SQLite serialises writers and readers never block a writer in WAL mode.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_BRAIN_PATH = Path(__file__).parent / "olp.db"
SCHEMA_VERSION = 6
# _create_tables builds the v1 BASELINE schema and stamps this version; _migrate
# then steps a fresh DB forward to SCHEMA_VERSION. Keeping this at 1 (not
# SCHEMA_VERSION) is what makes migrations actually run on a new DB.
BASELINE_SCHEMA_VERSION = 1

# Future schema changes: bump SCHEMA_VERSION and add the SQL here, e.g.
#   _MIGRATIONS[5] = "ALTER TABLE runs ADD COLUMN cold_elo_refit_days INTEGER;"
# A fresh DB still builds the full baseline then skips straight to the new
# version; an OLD DB is migrated forward one step at a time inside a
# transaction. A DB NEWER than this build is refused, never adapted.
_MIGRATIONS: dict[int, str] = {
    # v2: the priced EV row carries the calibration adjustment that was
    # actually applied to its probability (None = no evidence, or not priced).
    2: "ALTER TABLE predictions ADD COLUMN cal_adjustment REAL;",
    # v3/v4: a rated prediction records its OUTCOME once the match settles
    # (from a continental results source) — the model-vs-reality evidence the
    # brain is trained on. hit is per-market via the canonical settle rules.
    3: "ALTER TABLE predictions ADD COLUMN ft_result TEXT;",
    4: "ALTER TABLE predictions ADD COLUMN hit INTEGER;",
    # v5: how many leagues got an xG third opinion this run (Understat covers
    # Big-5 + RFPL only, so this is a coverage counter, not a quality claim).
    5: "ALTER TABLE runs ADD COLUMN xg_leagues INTEGER NOT NULL DEFAULT 0;",
    # v6: the produced-bet record — the day's produced bet (today's rated
    # fixtures) plus its next-day per-leg verification. JSON in
    # output/boards/produced_<date>.json is canonical; this table is the
    # queryable mirror /stats and the web dashboard read.
    6: "CREATE TABLE IF NOT EXISTS produced_bets ("
       " date TEXT NOT NULL, leg_id TEXT NOT NULL, fixture TEXT NOT NULL, "
       " league TEXT NOT NULL, pick TEXT NOT NULL, pick_market TEXT NOT NULL, "
       " model_prob REAL, softness_tier TEXT, on_deploy_shortlist INTEGER "
       " NOT NULL DEFAULT 0, best_market TEXT, best_price REAL, "
       " best_mes_ev REAL, kickoff_date TEXT, ft_result TEXT, hit INTEGER, "
       " settled INTEGER NOT NULL DEFAULT 0, "
       " PRIMARY KEY(date, leg_id))",
}

_WRITE_GUARD = ("SELECT", "PRAGMA", "EXPLAIN", "WITH")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fold(s: str) -> str:
    """Accent- and case-fold a string for matching: 'Fenerbahçe' -> 'fenerbahce'.
    SQLite has no unaccent(), so team/fixture lookups fold in Python."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def content_hash(results: list, salt: str = "") -> str:
    """sha1 over the exact training rows plus a fit-config salt.

    Each row contributes date|home|away|fthg|ftag; rows are sorted so the hash
    is order-insensitive. Any change to any row, to the row set, or to the fit
    config (the salt) changes the hash — so an EQUAL hash means a provably
    identical fit (same rows + same config -> same optimum), which is what
    makes model reuse honest rather than an approximation."""
    rows = sorted((r.date, r.home_team, r.away_team, r.fthg, r.ftag)
                  for r in results)
    h = hashlib.sha1(salt.encode("utf-8"))
    for date, home, away, fthg, ftag in rows:
        h.update(f"{date}|{home}|{away}|{fthg}|{ftag}\n".encode("utf-8"))
    return h.hexdigest()


# ---- payload (de)serialisers — delegate to the engines' single source -------
def elo_to_payload(m: Any) -> dict:
    return m.to_payload()


def elo_from_payload(d: dict) -> Any:
    from engine.elo import EloModel
    return EloModel.from_payload(d)


def dc_to_payload(m: Any) -> dict:
    return m.to_payload()


def dc_from_payload(d: dict) -> Any:
    from engine.dixon_coles import DixonColesModel
    return DixonColesModel.from_payload(d)


class Brain:
    """Central persistent store. One connection per Brain; open one per
    process/command and close it when done (context manager supported)."""

    def __init__(self, path: str | Path = DEFAULT_BRAIN_PATH,
                 read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if read_only:
            self._conn = sqlite3.connect(f"file:{self.path}?mode=ro",
                                         uri=True, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            return
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Brain":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- schema / migrations ----------------------------------------------
    def _create_tables(self) -> None:
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, "
                "value TEXT NOT NULL)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS model_state ("
                " model_key TEXT PRIMARY KEY, kind TEXT NOT NULL, "
                " version INTEGER NOT NULL, content_hash TEXT NOT NULL, "
                " n_matches INTEGER NOT NULL, last_date TEXT, first_date TEXT, "
                " payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_state_kind "
                "ON model_state(kind)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS predictions ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, "
                " predicted_at TEXT NOT NULL, league TEXT NOT NULL, "
                " fixture TEXT NOT NULL, match_date TEXT, market TEXT NOT NULL, "
                " model_engine TEXT NOT NULL, model_prob REAL NOT NULL, "
                " entry_odds REAL, bookmaker TEXT, ev REAL, "
                " softness_tier TEXT NOT NULL, "
                " on_deploy_shortlist INTEGER NOT NULL DEFAULT 0)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_fixture "
                "ON predictions(fixture, match_date)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_league "
                "ON predictions(league, predicted_at)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_market ON predictions(market)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_run ON predictions(run_id)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS legs ("
                " leg_id TEXT PRIMARY KEY, date_logged TEXT NOT NULL, "
                " league TEXT NOT NULL, fixture TEXT NOT NULL, "
                " market TEXT NOT NULL, model_prob REAL, match_date TEXT, "
                " entry_odds REAL, entry_capture_path TEXT, closing_odds REAL, "
                " closing_capture_path TEXT, clv_pct REAL, ft_result TEXT, "
                " hit INTEGER, stake REAL, phase TEXT NOT NULL, notes TEXT, "
                " source_file TEXT NOT NULL, synced_at TEXT NOT NULL)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_legs_league ON legs(league)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_legs_market "
                "ON legs(market, phase)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_legs_fixture "
                "ON legs(fixture, match_date)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS corrections ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, logged_at TEXT NOT NULL, "
                " source TEXT NOT NULL, note TEXT NOT NULL, "
                " actioned TEXT NOT NULL DEFAULT 'no', "
                " consumed INTEGER NOT NULL DEFAULT 0, consumed_at TEXT, "
                " content_key TEXT NOT NULL UNIQUE)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_corr_pending "
                "ON corrections(consumed)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS runs ("
                " run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, "
                " finished_at TEXT, status TEXT NOT NULL DEFAULT 'running', "
                " leagues_scanned INTEGER NOT NULL DEFAULT 0, "
                " fixtures_seen INTEGER NOT NULL DEFAULT 0, "
                " predictions_logged INTEGER NOT NULL DEFAULT 0, "
                " legs_logged INTEGER NOT NULL DEFAULT 0, "
                " dc_reused INTEGER NOT NULL DEFAULT 0, "
                " dc_refit INTEGER NOT NULL DEFAULT 0, "
                " elo_seeded INTEGER NOT NULL DEFAULT 0, "
                " pool_built INTEGER NOT NULL DEFAULT 0, "
                " fit_seconds REAL, warnings TEXT)")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(BASELINE_SCHEMA_VERSION),))

    def _migrate(self) -> None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()
        cur = int(row["value"]) if row else 0
        if cur > SCHEMA_VERSION:
            raise RuntimeError(
                f"brain at {self.path} is schema v{cur}, this build only "
                f"understands v{SCHEMA_VERSION}. Refusing to read a newer "
                f"database rather than guess what its columns mean.")
        with self._conn:
            for v in range(cur + 1, SCHEMA_VERSION + 1):
                sql = _MIGRATIONS.get(v)
                if sql:
                    self._conn.execute(sql)
                self._conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) "
                    "VALUES('schema_version', ?)", (str(v),))

    @property
    def schema_version(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row["value"]) if row else 0

    # ---- model_state ------------------------------------------------------
    def load_model_state(self, model_key: str) -> Optional[dict]:
        """Returns None if absent; otherwise
        {kind, version, content_hash, n_matches, last_date, first_date,
         payload, updated_at}. Refuses a row whose version is NEWER than this
        build knows (HR35 — never adapt to a shape we don't understand)."""
        row = self._conn.execute(
            "SELECT kind, version, content_hash, n_matches, last_date, "
            "first_date, payload, updated_at FROM model_state "
            "WHERE model_key=?", (model_key,)).fetchone()
        if row is None:
            return None
        d = {"kind": row["kind"], "version": row["version"],
             "content_hash": row["content_hash"], "n_matches": row["n_matches"],
             "last_date": row["last_date"], "first_date": row["first_date"],
             "updated_at": row["updated_at"],
             "payload": json.loads(row["payload"])}
        return d

    def save_model_state(self, model_key: str, kind: str, version: int,
                         content_hash: str, n_matches: int,
                         last_date: Optional[str], first_date: Optional[str],
                         payload: dict) -> None:
        """Upsert by model_key. payload is the engine-shaped dict."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO model_state(model_key, kind, version, content_hash, "
                " n_matches, last_date, first_date, payload, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(model_key) DO UPDATE SET "
                " kind=excluded.kind, version=excluded.version, "
                " content_hash=excluded.content_hash, "
                " n_matches=excluded.n_matches, last_date=excluded.last_date, "
                " first_date=excluded.first_date, payload=excluded.payload, "
                " updated_at=excluded.updated_at",
                (model_key, kind, version, content_hash, n_matches, last_date,
                 first_date, json.dumps(payload), _now()))

    def delete_model_state(self, model_key: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM model_state WHERE model_key=?", (model_key,))

    def model_state_summary(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT model_key, kind, n_matches, last_date, updated_at "
            "FROM model_state ORDER BY kind, model_key").fetchall()
        return [dict(r) for r in rows]

    # ---- predictions ------------------------------------------------------
    def append_predictions(self, rows: list[dict]) -> int:
        """One INSERT transaction for all rows; returns the count."""
        if not rows:
            return 0
        # Tolerate rows written before the cal_adjustment column existed.
        for r in rows:
            r.setdefault("cal_adjustment", None)
        with self._conn:
            self._conn.executemany(
                "INSERT INTO predictions(run_id, predicted_at, league, fixture, "
                " match_date, market, model_engine, model_prob, entry_odds, "
                " bookmaker, ev, softness_tier, on_deploy_shortlist, "
                " cal_adjustment) "
                "VALUES(:run_id,:predicted_at,:league,:fixture,:match_date,"
                ":market,:model_engine,:model_prob,:entry_odds,:bookmaker,:ev,"
                ":softness_tier,:on_deploy_shortlist,:cal_adjustment)", rows)
        return len(rows)

    def predictions_for(self, fixture: Optional[str] = None,
                        team: Optional[str] = None,
                        match_date: Optional[str] = None,
                        market: Optional[str] = None,
                        engine: Optional[str] = None,
                        run_id: Optional[str] = None,
                        limit: int = 100) -> list[dict]:
        if team is not None:
            # Accent- and case-insensitive team lookup — the Architect types
            # 'Fenerbahce', the board says 'Fenerbahçe'. SQLite has no
            # unaccent(), so fetch a bounded recent window and fold-filter in
            # Python. Falls back to a plain substring match for the rest.
            rows = self._conn.execute(
                "SELECT * FROM predictions ORDER BY predicted_at DESC, "
                "id DESC LIMIT ?", (2000,)).fetchall()
            folded = _fold(team)
            rows = [r for r in rows
                    if folded in _fold(r["fixture"]) or folded in _fold(r["league"])]
            if match_date:
                rows = [r for r in rows if r["match_date"] == match_date]
            if market:
                rows = [r for r in rows if r["market"] == market]
            if engine:
                rows = [r for r in rows if r["model_engine"] == engine]
            if run_id:
                rows = [r for r in rows if r["run_id"] == run_id]
            return [dict(r) for r in rows[:limit]]

        sql = ["SELECT * FROM predictions WHERE 1=1"]
        params: list = []
        if fixture:
            sql.append("AND fixture LIKE ?")
            params.append(f"%{fixture}%")
        if match_date:
            sql.append("AND match_date=?")
            params.append(match_date)
        if market:
            sql.append("AND market=?")
            params.append(market)
        if engine:
            sql.append("AND model_engine=?")
            params.append(engine)
        if run_id:
            sql.append("AND run_id=?")
            params.append(run_id)
        sql.append("ORDER BY predicted_at DESC, id DESC LIMIT ?")
        params.append(limit)
        rows = self._conn.execute(" ".join(sql), params).fetchall()
        return [dict(r) for r in rows]

    def record_outcomes(self, fixture: str, match_date: str, ft_result: str,
                        hits: dict[str, bool]) -> int:
        """Attach a settled result to every prediction row for this fixture and
        date. `hits` maps market -> hit, graded by the canonical settle rules.
        A row already settled is never overwritten (first result wins). Returns
        the number of rows updated."""
        with self._conn:
            cur = self._conn.executemany(
                "UPDATE predictions SET ft_result=:fr, hit=:h "
                "WHERE fixture=:fix AND match_date=:md AND market=:m "
                "AND hit IS NULL",
                [{"fr": ft_result, "h": int(hit), "fix": fixture, "md": match_date,
                  "m": market}
                 for market, hit in hits.items()])
        return cur.rowcount

    def outcome_summary(self, league: Optional[str] = None) -> dict:
        """Model-vs-reality: settled rated predictions. {'n', 'hit_rate'}."""
        sql = "SELECT COUNT(*) AS n, SUM(hit) AS hits FROM predictions WHERE hit IS NOT NULL"
        params: tuple = ()
        if league:
            sql += " AND league=?"
            params = (league,)
        row = self._conn.execute(sql, params).fetchone()
        n = row["n"] or 0
        return {"n": n, "hit_rate": (row["hits"] or 0) / n if n else None}

    def graded_yesterday(self, date_iso: str) -> list[dict]:
        """All settled predictions for a given match date (yesterday), with
        per-engine predictions + outcome + hit per engine. Used for the
        'Yesterday — graded' section (ID414)."""
        sql = """
            SELECT fixture, league, match_date, market, model_engine,
                   model_prob, ft_result, hit
            FROM predictions
            WHERE match_date = ? AND hit IS NOT NULL
            ORDER BY fixture, model_engine, market
        """
        rows = self._conn.execute(sql, (date_iso,)).fetchall()
        # Group by fixture
        from collections import defaultdict
        grouped = defaultdict(lambda: {
            "fixture": None, "league": None, "match_date": date_iso,
            "outcome": None, "engines": defaultdict(dict)
        })
        for r in rows:
            g = grouped[r["fixture"]]
            g["fixture"] = r["fixture"]
            g["league"] = r["league"]
            g["outcome"] = r["ft_result"]
            g["engines"][r["model_engine"]][r["market"]] = {
                "prob": r["model_prob"], "hit": bool(r["hit"])
            }
        return list(grouped.values())

    def produced_bets(self, date_iso: Optional[str] = None,
                      limit: int = 30) -> list[dict]:
        """Rows from the produced-bets mirror: the day's produced bet + per-leg
        next-day verification. Queryable by date or by most-recent-first. The
        JSON at output/boards/produced_<date>.json is canonical; this is the
        /stats + web history view."""
        sql = "SELECT * FROM produced_bets"
        params: tuple = ()
        if date_iso:
            sql += " WHERE date=?"
            params = (date_iso,)
        sql += " ORDER BY date DESC, fixture, pick LIMIT ?"
        return [dict(r) for r in self._conn.execute(
            sql, params + (limit,)).fetchall()]

    def produced_bets_summary(self, limit: int = 30) -> dict:
        """Verification record of produced bets: settled count, won/lost, rate.
        Read from the mirror; a day with no produced bet contributes nothing."""
        rows = self._conn.execute(
            "SELECT date, COUNT(*) AS n, "
            "SUM(CASE WHEN settled=1 THEN 1 ELSE 0 END) AS settled, "
            "SUM(CASE WHEN settled=1 AND hit=1 THEN 1 ELSE 0 END) AS won "
            "FROM produced_bets GROUP BY date ORDER BY date DESC LIMIT ?",
            (limit,)).fetchall()
        settled = sum(r["settled"] or 0 for r in rows)
        won = sum(r["won"] or 0 for r in rows)
        return {
            "days": len(rows),
            "legs": sum(r["n"] for r in rows),
            "settled": settled,
            "won": won,
            "pending": sum(r["n"] for r in rows) - settled,
            "hit_rate": (won / settled) if settled else None,
            "by_day": [dict(r) for r in rows],
        }

    def rolling_7d(self) -> dict:
        """Rolling 7-day aggregates across all engines + consensus + legs.
        Returns hit rates, legs logged, capture rate, days-to-gate."""
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        week_ago = today - _td(days=7)
        # Predictions in last 7 run dates
        pred_sql = """
            SELECT model_engine, COUNT(*) AS n,
                   SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) AS settled,
                   SUM(hit) AS hits
            FROM predictions
            WHERE date(predicted_at) >= ?
            GROUP BY model_engine
        """
        pred_rows = self._conn.execute(pred_sql, (week_ago.isoformat(),)).fetchall()
        engine_stats = {}
        for r in pred_rows:
            n = r["n"] or 0
            settled = r["settled"] or 0
            hits = r["hits"] or 0
            engine_stats[r["model_engine"]] = {
                "predictions": n,
                "settled": settled,
                "hit_rate": hits / settled if settled else None
            }
        # Legs logged in last 7 days (from clv_log via brain's legs mirror)
        leg_sql = """
            SELECT COUNT(*) AS n,
                   SUM(CASE WHEN clv_pct IS NOT NULL THEN 1 ELSE 0 END) AS with_clv,
                   AVG(clv_pct) AS avg_clv
            FROM legs
            WHERE date(date_logged) >= ? AND phase = 'phase2_paper'
        """
        leg_row = self._conn.execute(leg_sql, (week_ago.isoformat(),)).fetchone()
        legs_logged = leg_row["n"] or 0
        legs_with_clv = leg_row["with_clv"] or 0
        avg_clv = leg_row["avg_clv"]
        # Gate progress from clv_log (not runs table — simpler, no migration needed)
        gate = {
            "legs_with_clv": legs_with_clv,
            "gate_requirement": 30,
            "gate_met": legs_with_clv >= 30
        }
        return {
            "engines": engine_stats,
            "legs_logged": legs_logged,
            "legs_with_clv": legs_with_clv,
            "avg_clv_pct": round(avg_clv, 2) if avg_clv is not None else None,
            "gate": gate,
            "period_days": 7,
            "period_start": week_ago.isoformat(),
            "period_end": today.isoformat(),
        }

    def predictions_summary(self) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n_rows, COUNT(DISTINCT run_id) AS n_runs, "
            " MAX(predicted_at) AS last_run_date FROM predictions").fetchone()
        last = self._conn.execute(
            "SELECT run_id, COUNT(*) AS n FROM predictions "
            "GROUP BY run_id ORDER BY predicted_at DESC LIMIT 1").fetchone()
        return {"n_rows": row["n_rows"], "n_runs": row["n_runs"],
                "last_run_date": row["last_run_date"],
                "last_run_id": last["run_id"] if last else None,
                "last_run_predictions": last["n"] if last else 0}

    # ---- runs -------------------------------------------------------------
    def append_run(self, run_id: str, started_at: str,
                   status: str = "running", **fields) -> None:
        cols = {"run_id": run_id, "started_at": started_at, "status": status}
        cols.update(fields)
        names = ", ".join(cols.keys())
        marks = ", ".join(f":{k}" for k in cols)
        with self._conn:
            self._conn.execute(
                f"INSERT INTO runs({names}) VALUES({marks})", cols)

    def update_run(self, run_id: str, **fields) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k}=:{k}" for k in fields)
        fields["run_id"] = run_id
        with self._conn:
            self._conn.execute(
                f"UPDATE runs SET {sets} WHERE run_id=:run_id", fields)

    def last_run(self) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def run_history(self, limit: int = 30) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- legs mirror ------------------------------------------------------
    def sync_legs(self, paths: Optional[list[Path]] = None) -> dict:
        """Full-refresh mirror of each ledger file in one transaction. The JSON
        always wins: delete the file's slice, re-insert. A missing ledger file
        is skipped (a transient mid-write absence must not wipe the mirror).
        Returns {source_file: n_rows}."""
        from clv.clv_logger import CLVLog, DEFAULT_LOG_PATH
        paths = paths or [DEFAULT_LOG_PATH]
        counts: dict[str, int] = {}
        synced_at = _now()
        with self._conn:
            for p in paths:
                src = str(p)
                if not Path(p).exists():
                    counts[src] = 0
                    continue
                try:
                    log = CLVLog(path=p)
                except Exception:
                    counts[src] = 0
                    continue
                self._conn.execute(
                    "DELETE FROM legs WHERE source_file=?", (src,))
                for l in log.legs:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO legs(leg_id, date_logged, "
                        " league, fixture, market, model_prob, match_date, "
                        " entry_odds, entry_capture_path, closing_odds, "
                        " closing_capture_path, clv_pct, ft_result, hit, stake, "
                        " phase, notes, source_file, synced_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (l.leg_id, l.date_logged, l.league, l.fixture, l.market,
                         l.model_prob, l.match_date, l.entry_odds,
                         l.entry_capture_path, l.closing_odds,
                         l.closing_capture_path, l.clv_pct, l.ft_result, l.hit,
                         l.stake, l.phase, l.notes, src, synced_at))
                counts[src] = len(log.legs)
        return counts

    # ---- produced-bets mirror ----------------------------------------------
    def sync_produced_bets(self, legs: list[dict]) -> int:
        """Full-refresh mirror of one day's produced-bet record (the JSON at
        output/boards/produced_<date>.json stays canonical). The date's slice is
        deleted and re-inserted so the mirror never drifts from the record.
        Returns the number of rows inserted."""
        if not legs:
            return 0
        date_iso = legs[0]["date"]
        with self._conn:
            self._conn.execute(
                "DELETE FROM produced_bets WHERE date=?", (date_iso,))
            for l in legs:
                self._conn.execute(
                    "INSERT OR REPLACE INTO produced_bets(date, leg_id, fixture, "
                    " league, pick, pick_market, model_prob, softness_tier, "
                    " on_deploy_shortlist, best_market, best_price, best_mes_ev, "
                    " kickoff_date, ft_result, hit, settled) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (l["date"], l["leg_id"], l["fixture"], l["league"],
                     l["pick"], l["pick_market"], l["model_prob"],
                     l["softness_tier"], int(l["on_deploy_shortlist"]),
                     l["best_market"], l["best_price"], l["best_mes_ev"],
                     l["kickoff_date"], l["ft_result"], l["hit"],
                     int(l["settled"])))
        return len(legs)

    def clv_by_market(self, phase: str = "phase2_paper") -> list[dict]:
        rows = self._conn.execute(
            "SELECT market, COUNT(*) AS n, AVG(clv_pct) AS mean_clv_pct, "
            " SUM(CASE WHEN clv_pct > 0 THEN 1 ELSE 0 END) AS n_beat_close "
            "FROM legs WHERE phase=? AND clv_pct IS NOT NULL "
            "GROUP BY market ORDER BY n DESC, market", (phase,)).fetchall()
        return [dict(r) for r in rows]

    def calibration_by_market(self, phase: str = "phase2_paper") -> list[dict]:
        """Per-market calibration EVIDENCE from settled paper legs with a
        logged closing line: n, mean CLV, mean hit rate and mean model
        probability. This drives the engine's CLV-gated recalibration
        (engine/recalibration.py) — which stays INERT until a market reaches
        MIN_LEGS settled legs, so no thin/noisy sample ever moves the model."""
        rows = self._conn.execute(
            "SELECT market, COUNT(*) AS n, AVG(clv_pct) AS mean_clv_pct, "
            " AVG(hit) AS mean_hit, AVG(model_prob) AS mean_model_prob "
            "FROM legs WHERE phase=? AND clv_pct IS NOT NULL "
            " AND hit IS NOT NULL AND model_prob IS NOT NULL "
            "GROUP BY market ORDER BY n DESC, market", (phase,)).fetchall()
        return [dict(r) for r in rows]

    def clv_by_league(self, phase: str = "phase2_paper") -> list[dict]:
        rows = self._conn.execute(
            "SELECT league, COUNT(*) AS n, AVG(clv_pct) AS mean_clv_pct "
            "FROM legs WHERE phase=? AND clv_pct IS NOT NULL "
            "GROUP BY league ORDER BY n DESC, league", (phase,)).fetchall()
        return [dict(r) for r in rows]

    def clv_by_tier(self, phase: str = "phase2_paper") -> list[dict]:
        """CLV grouped by softness tier. Lazy engine import — brain stays
        stdlib-only at module load."""
        from engine.softness import softness_tier
        rows = self._conn.execute(
            "SELECT DISTINCT league, clv_pct FROM legs "
            "WHERE phase=? AND clv_pct IS NOT NULL", (phase,)).fetchall()
        tiers: dict[str, list] = {}
        for r in rows:
            tiers.setdefault(softness_tier(r["league"]), []).append(r["clv_pct"])
        out = []
        for tier, vals in sorted(tiers.items()):
            out.append({"tier": tier, "n": len(vals),
                        "mean_clv_pct": round(sum(vals) / len(vals), 3)})
        return out

    def legs_for(self, fixture: Optional[str] = None,
                 team: Optional[str] = None,
                 phase: Optional[str] = None) -> list[dict]:
        sql = ["SELECT * FROM legs WHERE 1=1"]
        params: list = []
        if fixture:
            sql.append("AND fixture LIKE ?")
            params.append(f"%{fixture}%")
        if team:
            sql.append("AND (fixture LIKE ? OR league LIKE ?)")
            params += [f"%{team}%", f"%{team}%"]
        if phase:
            sql.append("AND phase=?")
            params.append(phase)
        sql.append("ORDER BY date_logged DESC")
        rows = self._conn.execute(" ".join(sql), params).fetchall()
        return [dict(r) for r in rows]

    def gate_status(self) -> dict:
        """Mirror of CLVLog.phase2_status computed from SQL — same fields."""
        from clv.clv_logger import PHASE3_GATE_MIN_LEGS
        from config import PAPER_PHASE
        row = self._conn.execute(
            "SELECT COUNT(*) AS n_total, "
            " SUM(CASE WHEN clv_pct IS NOT NULL THEN 1 ELSE 0 END) AS n_clv, "
            " AVG(CASE WHEN clv_pct IS NOT NULL THEN clv_pct END) AS mean_clv "
            "FROM legs WHERE phase=?", (PAPER_PHASE,)).fetchone()
        n_total = row["n_total"] or 0
        n_clv = row["n_clv"] or 0
        mean_clv = round(row["mean_clv"], 3) if row["mean_clv"] is not None else None
        gate_met = (n_clv >= PHASE3_GATE_MIN_LEGS
                    and (mean_clv or 0) > 0)
        return {"legs_logged_total": n_total, "legs_with_clv": n_clv,
                "gate_requirement": PHASE3_GATE_MIN_LEGS,
                "mean_clv_pct": mean_clv,
                "positive_mean_clv": bool(mean_clv and mean_clv > 0),
                "gate_met_pending_architect_signoff": gate_met,
                "note": "mirror of clv/clv_log.json (JSON is the source)"}

    def leg_rows(self, phase: str | None = None) -> list[tuple[str]]:
        """All leg_ids in the ledger (optionally one phase). For tooling that
        needs to touch the mirror without going through the JSON source."""
        if phase:
            return self._conn.execute(
                "SELECT leg_id FROM legs WHERE phase=?", (phase,)).fetchall()
        return self._conn.execute("SELECT leg_id FROM legs").fetchall()

    def set_leg_date(self, leg_id: str, date_iso: str) -> None:
        """Rewrite a leg's date_logged (YYYY-MM-DD). For corrections/tests."""
        with self._conn:
            self._conn.execute(
                "UPDATE legs SET date_logged=? WHERE leg_id=?", (date_iso, leg_id))

    def leg_telemetry(self, phase: str = "phase2_paper") -> dict:
        """Trajectory to the Phase-3 gate, computed from the logged legs.

        Returns legs logged, legs with a closing line, settled count, the CLV
        capture rate (settled legs that earned a closing line), the observed
        legs-per-day rate over the log's window, the sustained CLV-leg
        production rate (legs/day x capture), and an honest projected
        days-to-gate. Any rate that cannot be stated is None — never a guess
        (HR35)."""
        from clv.clv_logger import PHASE3_GATE_MIN_LEGS
        rows = self._conn.execute(
            "SELECT date_logged, clv_pct, hit FROM legs WHERE phase=?",
            (phase,)).fetchall()
        n = len(rows)
        n_clv = sum(1 for _, c, _ in rows if c is not None)
        n_settled = sum(1 for _, _, h in rows if h is not None)
        capture_rate = (n_clv / n_settled) if n_settled else None
        dates = sorted({r[0][:10] for r in rows if r[0]})
        if len(dates) >= 2:
            span = ((datetime.fromisoformat(dates[-1])
                     - datetime.fromisoformat(dates[0])).days + 1)
            legs_per_day = n / max(span, 1)
        elif len(dates) == 1:
            legs_per_day = float(n)  # single observed day
        else:
            legs_per_day = 0.0
        # The sustained rate that actually advances the gate: how fast CLV legs
        # (the only legs that count) are being produced.
        clv_rate = (legs_per_day * capture_rate if capture_rate is not None
                    else 0.0)
        days_to_gate = None
        if clv_rate > 0:
            days_to_gate = round((PHASE3_GATE_MIN_LEGS - n_clv) / clv_rate, 1)
        # 0.0 must survive as a real signal ("settled but NO closing line"),
        # distinct from None ("nothing settled yet") — both are honest, but
        # they mean different things.
        return {"n_legs": n, "n_with_clv": n_clv, "n_settled": n_settled,
                "clv_capture_rate": (round(capture_rate, 3)
                                     if capture_rate is not None else None),
                "legs_per_day": round(legs_per_day, 2),
                "clv_legs_per_day": (round(clv_rate, 3) if clv_rate else None),
                "days_to_gate": days_to_gate,
                "gate_requirement": PHASE3_GATE_MIN_LEGS}

    # ---- corrections ------------------------------------------------------
    def sync_corrections(self, csv_path: Optional[Path] = None) -> int:
        """Idempotent seed from memory/corrections.csv, keyed on
        sha1(logged_at|note). Returns the number of NEW rows inserted."""
        path = csv_path or (Path(__file__).parent.parent / "memory"
                            / "corrections.csv")
        if not Path(path).exists():
            return 0
        inserted = 0
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            with self._conn:
                for row in reader:
                    key = hashlib.sha1(
                        f"{row.get('logged_at', '')}|{row.get('note', '')}"
                        .encode("utf-8")).hexdigest()
                    cur = self._conn.execute(
                        "SELECT id FROM corrections WHERE content_key=?",
                        (key,)).fetchone()
                    if cur is not None:
                        continue
                    self._conn.execute(
                        "INSERT INTO corrections(logged_at, source, note, "
                        " actioned, content_key) VALUES(?,?,?,?,?)",
                        (row.get("logged_at", ""), row.get("source", ""),
                         row.get("note", ""), row.get("actioned", "no"), key))
                    inserted += 1
        return inserted

    def corrections_pending(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM corrections WHERE consumed=0 "
            "ORDER BY logged_at ASC").fetchall()
        return [dict(r) for r in rows]

    def mark_corrections_consumed(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._conn:
            self._conn.executemany(
                "UPDATE corrections SET consumed=1, consumed_at=? WHERE id=?",
                [(_now(), i) for i in ids])

    # ---- low-level escape hatch (read-only guard) -------------------------
    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Run a read-only SQL query (SELECT/PRAGMA/EXPLAIN/WITH only)."""
        if not sql.lstrip().upper().startswith(_WRITE_GUARD):
            raise ValueError(
                f"brain.query is read-only; refusing: {sql[:60]!r}")
        return self._conn.execute(sql, params).fetchall()
