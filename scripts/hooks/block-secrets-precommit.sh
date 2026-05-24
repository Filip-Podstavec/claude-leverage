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
# Dependencies: jq OR python (3 or 2), plus git, grep. See json_parse.sh.

set -euo pipefail

# Source shared parser helper.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

# Without any JSON parser we cannot inspect the command. Fail-open with a
# loud warning rather than blocking every Bash call. Documented limitation.
if ! has_parser; then
  cat >&2 <<'EOF'
[block-secrets-precommit] WARNING: no JSON parser available - this hook is DISABLED.
Install one of:
  jq:     brew install jq | sudo apt install jq | winget install jqlang.jq
  python: usually preinstalled on macOS/Linux; Windows: python.org or Microsoft Store
Until then, secret scanning before commits is inactive.
EOF
  exit 0
fi

read_stdin
cmd=$(get_field '.tool_input.command') || exit 0
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
  "GitHub Fine-grained PAT"
  "GitHub OAuth Token"
  "GitHub User-to-Server Token"
  "GitHub Server-to-Server Token"
  "GitLab PAT"
  "Stripe Live Key"
  "Stripe Test Key"
  "Anthropic API Key"
  "OpenAI-style Key"
  "Google API Key"
  "Slack Token"
  "Private Key Block"
  "Generic Password Assignment"
)

declare -a patterns=(
  # AIDEV-NOTE: the trailing "Generic Password Assignment" pattern below
  # uses an exclusion character class `[^"'$\{<]` to skip placeholder
  # interpolations: `$` excludes `$VAR` references, `{` excludes `${VAR}`
  # references (the `\{` here is literal because backslash-`{` inside a
  # bracket expression in ERE is the same as bare `{`), `<` excludes
  # template-style `<placeholder>` markers. Don't "simplify" the class
  # without checking what each character is exempting.
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36}'
  'github_pat_[A-Za-z0-9_]{36,}'
  'gho_[A-Za-z0-9]{36}'
  'ghu_[A-Za-z0-9]{36}'
  'ghs_[A-Za-z0-9]{36}'
  'glpat-[A-Za-z0-9_-]{20,}'
  'sk_live_[A-Za-z0-9]{24,}'
  'sk_test_[A-Za-z0-9]{24,}'
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
    # Find the file this line belongs to via single forward pass.
    # Earlier versions used `grep -B 9999 -F "$matched_line" | grep '^+++ b/' | tail -1`
    # which is O(N^2) on large staged diffs (re-buffering up to 9999 preceding
    # lines per match). The awk pass tracks the current `+++ b/` header as it
    # streams and emits it on first substring match - O(N) and identical output.
    # MATCHED is exported via env var rather than awk -v to avoid backslash
    # interpretation in the matched line.
    current_file=$(MATCHED="$matched_line" awk '
      BEGIN { m = ENVIRON["MATCHED"] }
      /^\+\+\+ b\// { f = substr($0, 7); next }
      index($0, m) { print f; exit }
    ' <<< "$staged_diff") || current_file="unknown"
    [ -z "$current_file" ] && current_file="unknown"

    # Redact sensitive portion for preview
    preview=$(echo "$matched_line" | head -c 80 | sed -E 's/[A-Za-z0-9_-]{12,}/***/g')

    cat >&2 <<EOF
[block-secrets-precommit] Potential secret detected in staged diff.

Pattern: ${pattern_names[$i]}
File: $current_file
Line preview: $preview

If this is a false positive, you can:
- Add the marker comment 'claude-leverage-allow-secret' on the same line
- Commit manually outside Claude Code
- Adjust patterns in ~/.claude/hooks/block-secrets-precommit.sh
- Temporarily disable the hook in ~/.claude/settings.json
EOF
    exit 2
  fi
done

exit 0
