#!/usr/bin/env python3
"""
open_questions_report.py — compiles every open question scattered across
the vault into one place.

IMPORTANT, read before running this expecting it to close anything: this
tool finds and lists open questions. It does not answer them. Actually
resolving "is Away Win banned or not" or "does the whitelist reach Euro
qualifiers" requires a judgment call from the Architect (some of these
are explicitly marked Architect-only bright lines) or a deep read of the
specific module by whoever has real access to the current code -- not a
keyword scan. Running this is the honest first step: see everything
that's actually still open, in one list, instead of it being scattered
across dozens of notes where it's easy to lose track of.

Once you have this list, the fastest path to actually closing items is:
run it, go through the list with Claude Code (which has real access to
the current vault and code), decide each one, and have Claude Code
update the source note directly -- removing it from this report on the
next run.

Looks for common open-question markers: "Open Question", "TBD", "TO
VERIFY", "unresolved", "pending Architect", "not yet ratified". Extend
MARKERS if your notes use different phrasing.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

MARKERS = [
    r"open question",
    r"\bTBD\b",
    r"TO VERIFY",
    r"unresolved",
    r"pending architect",
    r"not yet ratified",
    r"architect to rule",
    r"architect-only",
    r"unreconciled",
    r"NOT.{0,10}confirmed",
]

MARKER_RE = re.compile("|".join(MARKERS), re.IGNORECASE)


def find_matches(text: str) -> list[str]:
    """Return the sentence/line containing each marker hit, deduplicated."""
    hits = []
    for line in text.splitlines():
        if MARKER_RE.search(line):
            cleaned = line.strip().lstrip("-* ").strip()
            if cleaned and cleaned not in hits:
                hits.append(cleaned)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default="olp_xdv_agent/olp_xdv/docs/obsidian-vault")
    parser.add_argument("--output", default="OPEN_QUESTIONS_REPORT.md")
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    if not vault_dir.exists():
        print(f"Vault not found at {vault_dir}")
        return 1

    report_lines = [
        "# Open Questions Report",
        "",
        "Auto-compiled by open_questions_report.py — this is a scan, not a "
        "resolution. Each item below needs an actual decision (many are "
        "explicitly Architect-only) before it can be marked closed.",
        "",
    ]
    total = 0
    for md in sorted(vault_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        hits = find_matches(text)
        if not hits:
            continue
        report_lines.append(f"## {md.stem}")
        for h in hits:
            report_lines.append(f"- [ ] {h}")
            total += 1
        report_lines.append("")

    if total == 0:
        report_lines.append("No open-question markers found — either everything's "
                             "genuinely closed, or your notes use different phrasing "
                             "than the MARKERS list expects. Worth spot-checking.")

    Path(args.output).write_text("\n".join(report_lines), encoding="utf-8")
    print(f"{total} open item(s) found across the vault, written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())