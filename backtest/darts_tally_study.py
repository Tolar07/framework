"""
Darts tries tally (framework#341, Week A; record-only). Writes backtest/DARTS_TALLY_STUDY.md.

The issue asks for "every try counted". Each darts study counts its own tries, but the many studies together are a
bigger search: with enough tries on one small sample, a few "leads" appear by luck. This reads the verdict line and the
try count of every other DARTS_*_STUDY.md and adds them up, so a reader can see how many looks were taken and how many
came out better on the sealed half. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_tally_study.py
"""
from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BT = ROOT / "backtest"
OUT = BT / "DARTS_TALLY_STUDY.md"
SELF = OUT.name
TRIES_RE = re.compile(r"(\d+) tries")
BETTER_RE = re.compile(r"\(better by ([0-9.]+)")


def classify(verdict: str) -> str:
    """'better' | 'not better' | 'no lead' | 'other' from a study's Verdict line."""
    v = verdict.lower()
    if "not better" in v:
        return "not better"
    if "no " in v and "lead" in v:
        return "no lead"
    if "confirmed" in v or "(better by" in v:
        return "better"
    return "other"


def read_study(text: str) -> dict:
    tries = TRIES_RE.search(text)
    verdict = next((ln[len("Verdict:"):].strip() for ln in text.splitlines() if ln.startswith("Verdict:")), "")
    gap = BETTER_RE.search(verdict)
    return {
        "tries": int(tries.group(1)) if tries else None,
        "verdict": verdict,
        "kind": classify(verdict) if verdict else "pending",
        "gap": float(gap.group(1)) if gap else None,
    }


def collect(folder: Path = BT) -> dict[str, dict]:
    out = {}
    for p in sorted(folder.glob("DARTS_*_STUDY.md")):
        if p.name == SELF:
            continue
        out[p.name] = read_study(p.read_text(encoding="utf-8"))
    return out


def _short(name: str) -> str:
    return name.removeprefix("DARTS_").removesuffix("_STUDY.md").lower()


def render(studies: dict[str, dict], now: datetime) -> str:
    lines = [
        "# Darts tries tally",
        "",
        f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_tally_study.py` (framework#341). Record only.",
        "",
    ]
    if not studies:
        return "\n".join(lines + ["PENDING: no darts study reports to read.", "",
                                  "Record only: nothing here changes a stake, a bar or the live switch.", ""])
    total_tries = sum(s["tries"] or 0 for s in studies.values())
    judged = [s for s in studies.values() if s["kind"] != "pending"]
    better = [n for n, s in studies.items() if s["kind"] == "better"]
    lines += [
        f"{len(studies)} study reports read, {len(judged)} with a sealed-half verdict, "
        f"{total_tries} tries counted where a report states its tries (others do not state a count).",
        "",
        "| Study | Tries | Verdict |",
        "|---|---|---|",
    ]
    for name, s in studies.items():
        t = "n/a" if s["tries"] is None else str(s["tries"])
        lines.append(f"| {_short(name)} | {t} | {s['verdict'] or 'PENDING (no verdict line)'} |")
    lines += [
        "",
        f"Sealed-half verdicts that came out better than the board: {len(better)} of {len(judged)}"
        + (f" ({', '.join(_short(n) for n in better)})." if better else "."),
    ]
    gaps = [studies[n]["gap"] for n in better if studies[n]["gap"] is not None]
    if gaps:
        lines.append(f"Largest gap: {max(gaps):.4f} Brier. Under about 0.005 on a few hundred matches is noise.")
    lines += [
        "",
        "Read it as: the more studies looked at the same small sample, the more likely a 'better' is luck. "
        "No study here is a reason to change the Elo; every lead needs new matches.",
        "",
        "Record only: nothing here changes a stake, a bar or the live switch.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT.write_text(render(collect(), datetime.now(UTC)), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
