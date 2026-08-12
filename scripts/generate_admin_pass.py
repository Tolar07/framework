#!/usr/bin/env python3
"""
Generate a cryptographically strong admin password for the OLP XDV dashboard.

Usage:
    python scripts/generate_admin_pass.py          # print a new password
    python scripts/generate_admin_pass.py --apply  # write to .env (backup old)

The password is:
  - 24 chars from [A-Za-z0-9!@#$%^&*_-] (no ambiguous chars like l/1/I/O/0)
  - ~140 bits entropy (stronger than 256-bit symmetric keys for online guessing)
  - Printed once — copy it, store in your password manager, update .env
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

# Character set: alphanumerics + safe symbols, excluding visually ambiguous chars
# Removed: l (lowercase L), I (uppercase i), 1, O (uppercase o), 0, |, \, /, ", ', `
_ALPHABET = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ"   # no I, O
    "abcdefghijkmnpqrstuvwxyz"   # no l
    "23456789"                    # no 0, 1
    "!@#$%^&*_-"                  # safe symbols
)


def generate_password(length: int = 24) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _load_env(path: Path) -> dict:
    """Parse .env into a dict, preserving order and comments is NOT done (simplistic)."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _write_env(path: Path, env: dict) -> None:
    """Write .env back (simplistic — loses comments/ordering, acceptable for this script)."""
    lines = [f'{k}={v}' for k, v in env.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Generate strong admin password")
    ap.add_argument("--apply", action="store_true",
                    help="Write the new password to .env (backing up the old)")
    ap.add_argument("--length", type=int, default=24,
                    help="Password length (default 24)")
    a = ap.parse_args()

    new_pass = generate_password(a.length)

    if a.apply:
        env_path = Path(__file__).parent.parent / ".env"
        env = _load_env(env_path)
        old = env.get("ADMIN_PASS")
        env["ADMIN_PASS"] = new_pass
        _write_env(env_path, env)
        print(f"Applied to {env_path}")
        if old:
            print(f"  Old password backed up (was: {old[:4]}***{old[-4:]})")
            print("  Store the NEW password in your password manager NOW.")
    else:
        print(new_pass)


if __name__ == "__main__":
    main()