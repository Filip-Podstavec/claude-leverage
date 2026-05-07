#!/usr/bin/env bash
# block-secrets-precommit.sh
#
# Claude Code PreToolUse hook (Bash matcher).
# Scans staged diff for potential secrets before allowing git commit.
#
# Hook protocol:
#   - Receives JSON on stdin with tool_input.command
#   - Exit 0: allow the tool call
#   - Exit 2: block the tool call (stderr message shown to user)
#
# Install: register in ~/.claude/settings.json under hooks.PreToolUse
# Dependencies: jq, git, grep

set -euo pipefail

# Check for jq dependency. Without it we cannot parse the hook input - fail
# loudly rather than silently allow everything.
if ! command -v jq >/dev/null 2>&1; then
  cat >&2 <<'EOF'
[block-secrets-precommit] WARNING: jq is not installed - this hook is DISABLED.
Install jq to enable secret scanning before commits.
  macOS:   brew install jq
  Ubuntu:  sudo apt install jq
EOF
  exit 0
fi

# Parse command from stdin JSON. Fail-open on malformed input.
cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -z "$cmd" ] && exit 0

# Normalize for keyword matching only: strip shell quotes and backslashes that
# could be used to evade `git commit` detection (e.g., `git "commit"`).
cmd_norm=$(printf '%s' "$cmd" | tr -d "'\"\\\\")

# Only inspect git commit commands
case "$cmd_norm" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

# Get staged diff. Nothing staged = nothing to check.
staged_diff=$(git diff --cached 2>/dev/null) || exit 0
[ -z "$staged_diff" ] && exit 0

# Extract only added lines (skip diff metadata and context)
added_lines=$(echo "$staged_diff" | grep -E '^\+[^+]' || true)
[ -z "$added_lines" ] && exit 0

# Drop lines explicitly allowlisted with the marker comment.
# Use sparingly - this is a per-line escape hatch for legitimate matches
# (test fixtures, docs examples, mock tokens). Marker is load-bearing -
# future readers may not recognize it.
added_lines=$(echo "$added_lines" | grep -v 'claude-leverage-allow-secret' || true)
[ -z "$added_lines" ] && exit 0

# Secret patterns - name and extended regex
declare -a pattern_names=(
  "AWS Access Key"
  "GitHub Personal Access Token"
  "GitHub OAuth Token"
  "Stripe Live Key"
  "Anthropic API Key"
  "OpenAI-style Key"
  "Google API Key"
  "Slack Token"
  "Private Key Block"
  "Generic Password Assignment"
)

declare -a patterns=(
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36}'
  'gho_[A-Za-z0-9]{36}'
  'sk_live_[A-Za-z0-9]{24,}'
  'sk-ant-[A-Za-z0-9_-]{90,}'
  'sk-[A-Za-z0-9]{40,}'
  'AIza[0-9A-Za-z_-]{35}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  '-----BEGIN.*PRIVATE KEY-----'
  '(password|passwd|pwd|secret|api[_-]?key|access[_-]?token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"'$\{<]{8,}["'"'"']'
)

# Extract current file from diff for reporting
current_file="unknown"

for i in "${!patterns[@]}"; do
  matched_line=$(echo "$added_lines" | grep -iE -- "${patterns[$i]}" | head -1) || true
  if [ -n "$matched_line" ]; then
    # Try to find the file this line belongs to
    current_file=$(echo "$staged_diff" | grep -B 9999 -F "$matched_line" | grep '^+++ b/' | tail -1 | sed 's|^+++ b/||') || current_file="unknown"

    # Redact sensitive portion for preview
    preview=$(echo "$matched_line" | head -c 80 | sed -E 's/[A-Za-z0-9_-]{12,}/***/g')

    cat >&2 <<EOF
[block-secrets-precommit] Potential secret detected in staged diff.

Pattern: ${pattern_names[$i]}
File: $current_file
Line preview: $preview

If this is a false positive, you can:
- Commit manually outside Claude Code
- Adjust patterns in ~/.claude/hooks/block-secrets-precommit.sh
- Temporarily disable the hook in ~/.claude/settings.json
EOF
    exit 2
  fi
done

exit 0
