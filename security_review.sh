#!/usr/bin/env bash
# security_review.sh — honest secret-scan + dependency-CVE check for OLP XDV.
#
# Runs two tools IF they are installed, and says so loudly when they are not
# (honest-edge: a missing tool is reported as SKIP, never papered over):
#   gitleaks   — secret scanner over the git working tree + history
#   pip-audit  — PyPA CVE scanner against requirements.txt
#
# Exit codes:
#   0 — clean (no findings), OR tools absent (each reported as SKIP)
#   1 — at least one tool found findings or failed to scan
#
# Not wired into pre-commit: neither tool is installed on the dev box, so a
# hard hook would block every commit. Run manually when reviewing, or wire
# into CI where the tools are provisioned:
#   bash security_review.sh
set -uo pipefail

cd "$(dirname "$0")"

fail=0

echo "== security_review.sh =="
echo ""

# --- gitleaks: secret scan over working tree + history ---
if command -v gitleaks >/dev/null 2>&1; then
  echo "[gitleaks] scanning working tree + git history for secrets..."
  if gitleaks detect --source . --redact --no-banner; then
    echo "[gitleaks] OK — no secrets found."
  else
    echo "[gitleaks] FINDINGS — review the lines above." >&2
    fail=1
  fi
else
  echo "[gitleaks] SKIP — not installed."
  echo "  install: winget install gitleaks   (or: scoop install gitleaks / brew install gitleaks)"
fi

echo ""

# --- pip-audit: known CVEs in pinned/constrained deps ---
if command -v pip-audit >/dev/null 2>&1; then
  if [ -f requirements.txt ]; then
    echo "[pip-audit] auditing requirements.txt for known vulnerabilities..."
    if pip-audit -r requirements.txt; then
      echo "[pip-audit] OK — no known vulnerabilities."
    else
      echo "[pip-audit] FINDINGS — review the report above." >&2
      fail=1
    fi
  else
    echo "[pip-audit] SKIP — no requirements.txt in repo root." >&2
  fi
else
  echo "[pip-audit] SKIP — not installed."
  echo "  install: pip install pip-audit"
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "== security_review.sh: PASS (clean scans, or tools SKIPped) =="
else
  echo "== security_review.sh: FAIL — review the findings above ==" >&2
fi
exit "$fail"
