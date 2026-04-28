#!/usr/bin/env bash
# block-dangerous-git.sh
#
# Claude Code PreToolUse hook (Bash matcher).
# Blocks dangerous git operations: force push, --no-verify, hard reset on
# protected branches, and warns on force branch delete.
#
# Hook protocol:
#   - Receives JSON on stdin with tool_input.command
#   - Exit 0: allow the tool call
#   - Exit 2: block the tool call (stderr message shown to user)
#
# Install: register in ~/.claude/settings.json under hooks.PreToolUse
# Dependencies: jq

set -euo pipefail

# Parse command from stdin JSON. Fail-open on malformed input.
cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -z "$cmd" ] && exit 0

# --- Force push ---
if echo "$cmd" | grep -qE 'git\s+push' && echo "$cmd" | grep -qE '(--force|--force-with-lease|\s-f\s|\s-f$)'; then
  cat >&2 <<'EOF'
[block-dangerous-git] Force push detected.

Force push overwrites remote history and can destroy teammates' work.

Safer alternative: push to a new branch and open a PR. If you must overwrite
remote, run the command manually outside Claude Code.
EOF
  exit 2
fi

# --- No-verify commits ---
if echo "$cmd" | grep -qE 'git\s+commit' && echo "$cmd" | grep -qE '(--no-verify)'; then
  cat >&2 <<'EOF'
[block-dangerous-git] --no-verify detected on git commit.

Skipping pre-commit hooks bypasses safety checks (linting, secret scanning,
formatting). Fix the hook failure instead of bypassing it.

If the hook is genuinely wrong, disable it in the project's git config rather
than skipping it silently.
EOF
  exit 2
fi

# --- Hard reset to protected branch ---
if echo "$cmd" | grep -qE 'git\s+reset\s+--hard\s+\S*\b(main|master|develop|trunk)\b'; then
  cat >&2 <<'EOF'
[block-dangerous-git] Hard reset to a protected branch detected.

This discards all local changes and moves HEAD to match the target branch.
Any uncommitted or unpushed work will be permanently lost.

Safer alternative: create a new branch from the target, or use git stash
before resetting.
EOF
  exit 2
fi

# --- Force branch delete (warning only, does not block) ---
if echo "$cmd" | grep -qE 'git\s+branch\s+-D\s'; then
  cat >&2 <<'EOF'
[block-dangerous-git] Warning: force branch delete (git branch -D) detected.

This deletes the branch even if it has unmerged changes. Consider using
git branch -d (lowercase) which refuses to delete unmerged branches.
EOF
  # Warning only - do not block
  exit 0
fi

exit 0

# To extend, add new patterns as:
#   if echo "$cmd" | grep -qE '...'; then ...; exit 2; fi
# blocks. Test in project scope first via .claude/settings.json before
# promoting to user scope.
