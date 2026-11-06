"""
Basketball side of the Telegram commands (basketball inherits football, sport_parity.json).

READ-ONLY. Everything here reads files the NBA loops already wrote; nothing is fetched,
guessed or staked (HR59: a missing file reads PENDING, HR35).

  /board nba         tonight's NBA board (output/boards/nba_<night>.txt)
  /board basketball  world basketball + NCAA picks (output/world_basketball/wb_<day>.json)
  /why nba <n>       one NBA pick: chance, fair price, blend weight, the market group's record
  /status            gains an NBA block: board, grading, loop health (nba_status)
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
BOARD_DIR = ROOT / "output" / "boards"
LEDGER_DIR = ROOT / "output" / "picks"
WB_DIR = ROOT / "output" / "world_basketball"
SHADOW_DIR = ROOT / "output" / "nba_shadow"
SHADOW_REPORT = ROOT / "backtest" / "NBA_SHADOW.md"
LIVE_DIR = ROOT / "data" / "study" / "nba"   # <night>/live.jsonl, written by monitor/nba_live.py

PENDING = "NO DATA — PENDING"


def latest_night(board_dir: Path = BOARD_DIR) -> str | None:
    """Newest NBA board night on record (YYYY-MM-DD)."""
    nights = sorted(p.stem[4:] for p in board_dir.glob("nba_*.txt")) if board_dir.exists() else []
    return nights[-1] if nights else None


def nba_board(board_dir: Path = BOARD_DIR) -> str:
    night = latest_night(board_dir)
    if night is None:
        return f"No NBA board has been produced yet. {PENDING}."
    return (board_dir / f"nba_{night}.txt").read_text(encoding="utf-8")


def world_board(today: date | None = None, folder: Path = WB_DIR) -> str:
    """World basketball + NCAA picks frozen for today and tomorrow (kickoff day)."""
    today = today or date.today()
    lines: list[str] = []
    for off in (0, 1):
        day = (today + timedelta(days=off)).isoformat()
        p = folder / f"wb_{day}.json"
        try:
            picks = json.loads(p.read_text(encoding="utf-8")).get("picks", [])
        except (OSError, ValueError):
            continue
        for k in sorted(picks, key=lambda x: x.get("ko") or ""):
            price = k.get("price")
            chance = k.get("chance", k.get("fair"))
            lines.append(
                f"{(k.get('ko') or '')[11:16] or 'PENDING'}  {k.get('home')} v {k.get('away')}"
                f" ({k.get('comp') or 'PENDING'})\n"
                f"   {k.get('pick')} @{price:.2f} · chance {chance:.0%} · code {k.get('code') or 'PENDING'}"
                if isinstance(price, (int, float)) and isinstance(chance, (int, float)) else
                f"{k.get('home')} v {k.get('away')}: {k.get('pick')} (price PENDING)")
    if not lines:
        return f"No world-basketball / NCAA picks frozen for today or tomorrow. {PENDING}."
    return "WORLD BASKETBALL + NCAA — recorded picks (nothing booked by the framework)\n\n" + "\n".join(lines)


def _picks(night: str, ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    try:
        doc = json.loads((ledger_dir / f"nba_{night}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(doc.get("picks") or [], key=lambda p: p.get("tip") or "")


def group_record(family_name: str, report: Path = SHADOW_REPORT) -> str:
    """The family's row of backtest/NBA_SHADOW.md, in words; PENDING when there is none."""
    try:
        text = report.read_text(encoding="utf-8")
    except OSError:
        return PENDING
    for row in text.splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0].lower() == family_name.lower():
            return (f"{cells[1]} graded, won {cells[2]} against a stated {cells[3]}, "
                    f"return {cells[4]}, {cells[5]}")
    return f"no graded shadow pick yet ({PENDING})"


def explain(arg: str, ledger_dir: Path = LEDGER_DIR, report: Path = SHADOW_REPORT,
            board_dir: Path = BOARD_DIR) -> str:
    """/why nba <n> — pick n on the newest NBA board."""
    arg = arg.strip()
    if not arg.isdigit() or int(arg) < 1:
        return "Usage: /why nba 2   (the number of a pick on /board nba, counted from the top)"
    night = latest_night(board_dir)
    picks = _picks(night, ledger_dir) if night else []
    if not picks:
        return f"No NBA picks on record. {PENDING}."
    n = int(arg)
    if n > len(picks):
        return f"No NBA pick {n}: the {night} board has {len(picks)}."
    p = picks[n - 1]
    from engine import nba_shadow as sh
    from engine import nba_value as nv
    mid, spec = str(p.get("market_id", "")), p.get("specifier") or ""
    fam = sh.family(mid, spec) if mid else PENDING
    group = nv.blend_group(mid, spec) if mid else None
    w = nv.BLEND.get(group or "", 1.0) if group else None
    tip = p.get("tip") or PENDING
    out = [
        f"NBA pick {n} of {len(picks)} — {p.get('home')} v {p.get('away')} (tip {tip[:16]})",
        f"Pick: {p.get('pick')} @{p['price']:.2f}" if isinstance(p.get("price"), (int, float))
        else f"Pick: {p.get('pick')} (price PENDING)",
        f"Our chance {p['chance']:.0%} vs fair price {p['fair_price']:.2f} "
        f"(chance in the fair price {1 / p['fair_price']:.0%}); value {p['ev']:+.1%}"
        if all(isinstance(p.get(k), (int, float)) for k in ("chance", "fair_price", "ev"))
        else "Chance / fair price: PENDING",
        (f"Blend weight {w:.2f} on the sharp-line model, {1 - w:.2f} on SportyBet's own price "
         f"(group: {group}; backtest/NBA_BLEND_STUDY.md)") if w is not None else "Blend weight: PENDING",
        f"Market record (backtest/NBA_SHADOW.md, {fam}): {group_record(fam, report)}",
        f"Code: {p.get('code') or 'PENDING'} · result: {p.get('result') or 'PENDING'}",
        "Live test; recorded only. The framework never stakes.",
    ]
    return "\n".join(out)[:3500]


def nba_status(ledger_dir: Path = LEDGER_DIR, shadow_dir: Path = SHADOW_DIR, wb_dir: Path = WB_DIR,
               live_dir: Path = LIVE_DIR, board_dir: Path = BOARD_DIR, now: datetime | None = None) -> str:
    """NBA block for /status: the newest board, graded picks, shadow record, loop heartbeat."""
    now = now or datetime.now(timezone.utc)
    night = latest_night(board_dir)
    L = ["", "NBA / BASKETBALL"]
    if night is None:
        L.append(f"NBA board: {PENDING}")
    else:
        picks = _picks(night, ledger_dir)
        done = sum(1 for p in picks if p.get("result") in ("won", "lost", "void"))
        L.append(f"NBA board {night}: {len(picks)} picks, {done} graded")
    graded = won = 0
    for f in sorted(ledger_dir.glob("nba_*.json")) if ledger_dir.exists() else []:
        try:
            for p in json.loads(f.read_text(encoding="utf-8")).get("picks", []):
                if p.get("result") in ("won", "lost"):
                    graded += 1
                    won += p["result"] == "won"
        except (OSError, ValueError):
            continue
    L.append(f"All NBA board picks graded: {graded}" + (f", won {won / graded:.0%}" if graded else f" ({PENDING})"))
    sg = sp = 0
    for f in sorted(shadow_dir.glob("shadow_*.json")) if shadow_dir.exists() else []:
        try:
            for p in json.loads(f.read_text(encoding="utf-8")).get("picks", []):
                if p.get("result") in ("won", "lost"):
                    sg += 1
                elif not p.get("result"):
                    sp += 1
        except (OSError, ValueError):
            continue
    L.append(f"Shadow record (every market family): {sg} graded, {sp} waiting")
    wb = 0
    for f in sorted(wb_dir.glob("wb_*.json")) if wb_dir.exists() else []:
        try:
            wb += len(json.loads(f.read_text(encoding="utf-8")).get("picks", []))
        except (OSError, ValueError):
            continue
    L.append(f"World basketball / NCAA picks recorded: {wb}")
    newest = None
    for f in live_dir.glob("*/live.jsonl") if live_dir.exists() else []:
        m = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
        newest = m if newest is None or m > newest else newest
    if newest is None:
        L.append(f"NBA live tracker last snapshot: {PENDING}")
    else:
        hrs = (now - newest).total_seconds() / 3600
        L.append(f"NBA live tracker last snapshot: {newest:%Y-%m-%d %H:%MZ} ({hrs:.0f} h ago)")
    return "\n".join(L)


_NBA_WORDS = re.compile(r"^(nba|basketball|world)\b\s*", re.I)


def split_sport(arg: str) -> tuple[str | None, str]:
    """('nba'|'basketball'|None, rest) from a command argument."""
    m = _NBA_WORDS.match(arg.strip())
    if not m:
        return None, arg
    word = m.group(1).lower()
    return ("nba" if word == "nba" else "basketball"), arg.strip()[m.end():]
