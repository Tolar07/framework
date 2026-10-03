#!/usr/bin/env python3
"""
check_protected_files.py — OLP XDV protected-file gate for Claude Code hooks.

Reads the PreToolUse hook's JSON payload from stdin, checks whether the
Bash command being run is a git operation that would change tracked files
(commit / merge / push), and if so, diffs the changed files against the
protected list from Loops.md / Protected Constants.md.

Exit 0  -> allow the tool call to proceed.
Exit 2  -> block the tool call; stderr is surfaced back to Claude as the
           reason, per Claude Code's PreToolUse blocking contract.

This is a backstop layer, not the only layer — see the companion git
pre-push hook (install_git_hook.sh) for protection against actions taken
outside a Claude Code session entirely.
"""
import json
import re
import subprocess
import sys

# Mirrors the protected list in Loops.md / Protected Constants.md.
# Keep this list in sync with that file — it is the single source of truth
# for WHAT is protected; this script only enforces it.
PROTECTED_PATTERNS = [
    r"webapp/schema\.py",
    r"clv/phase3_gate\.py",
    r"clv/clv_logger\.py",
    r"clv/closing_capture\.py",
    r"config\.py",
    r"booking/booking_codes\.py",
    r"engine/leagues\.py",
    r"engine/markets\.py",
    r"RATIFICATIONS\.md",
    r"\.env",
]

GIT_CHANGE_COMMANDS = re.compile(r"\bgit\s+(commit|merge|push|rebase)\b")


def get_changed_files():
    """Return the list of files staged/changed relative to the last commit."""
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        return set(staged) | set(unstaged)
    except subprocess.CalledProcessError:
        # If git itself fails, fail SAFE: block and let a human look, rather
        # than silently allowing an unverifiable change through (HR35 spirit
        # — no fabricated "it's fine" when we genuinely can't check).
        return None


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Malformed input — fail safe, block, surface the reason.
        print("check_protected_files: could not parse hook payload; blocking as a precaution.", file=sys.stderr)
        sys.exit(2)

    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only act on git commands that actually change repo state.
    if not GIT_CHANGE_COMMANDS.search(command):
        sys.exit(0)

    changed_files = get_changed_files()
    if changed_files is None:
        print("check_protected_files: could not verify changed files (git diff failed); blocking as a precaution.", file=sys.stderr)
        sys.exit(2)

    hits = [
        f for f in changed_files
        if any(re.search(pat, f) for pat in PROTECTED_PATTERNS)
    ]

    if hits:
        print(
            "BLOCKED: this git operation touches protected file(s):\n"
            + "\n".join(f"  - {f}" for f in hits)
            + "\n\nThese are Architect-only per Protected Constants.md. "
              "Do not merge/commit/push this change automatically — "
              "flag it for the Architect and leave the PR open instead.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()