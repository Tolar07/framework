#!/usr/bin/env bash
# install_git_hook.sh — installs a pre-push git hook that reuses the same
# check_protected_files.py logic as the Claude Code PreToolUse hook, so the
# protection holds even for pushes made outside a Claude Code session
# (a human at the terminal, CI, another tool).
#
# Run this once from the repo root: bash install_git_hook.sh

set -euo pipefail

HOOK_PATH=".git/hooks/pre-push"

cat > "$HOOK_PATH" << 'EOF'
#!/usr/bin/env bash
# Auto-installed by install_git_hook.sh — do not edit directly, edit
# .claude/hooks/check_protected_files.py instead and re-run the installer.
echo '{"tool_input": {"command": "git push"}}' | python3 .claude/hooks/check_protected_files.py
exit $?
EOF

chmod +x "$HOOK_PATH"
echo "Installed pre-push hook at $HOOK_PATH"
echo "This re-runs the exact same protected-file check on every git push,"
echo "regardless of whether it came from Claude Code or a human at the terminal."