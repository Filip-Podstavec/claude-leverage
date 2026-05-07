#!/usr/bin/env bash
# track-delegations.sh
#
# Claude Code PostToolUse hook (Task matcher).
# Observability for claude-leverage subagent delegations:
#   - Logs each delegation as a JSONL record to ~/.claude/claude-leverage-stats.jsonl
#   - Prints a single parenthesized stderr note per delegation, e.g.
#     (claude-leverage: code-reviewer -> sonnet)
#
# Hook protocol:
#   - Receives JSON on stdin with tool_name and tool_input
#   - Always exits 0 - this is observability, never blocks
#
# Dependencies: jq OR python preferred. With no parser available, falls back
# to anonymous logging (a record per delegation with subagent="unknown",
# tier="unknown") so total counts still work even without a parser installed.

set -euo pipefail

# Source shared parser helper.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

read_stdin

stats_file="${HOME}/.claude/claude-leverage-stats.jsonl"
mkdir -p "$(dirname "$stats_file")" 2>/dev/null || true
ts=$(date -u +%FT%TZ 2>/dev/null || echo "unknown")

# No parser available - log anonymously and exit silently.
# We rely on Claude Code's matcher (configured as "Task" in hooks.json) to
# ensure this hook only fires on Task tool calls. Without a parser we cannot
# extract the subagent name, but the delegation count is still useful signal.
if ! has_parser; then
  printf '{"ts":"%s","subagent":"unknown","tier":"unknown"}\n' "$ts" >> "$stats_file" 2>/dev/null || true
  exit 0
fi

# Parser available - extract subagent name.
subagent=$(get_field '.tool_input.subagent_type')
if [ -z "$subagent" ]; then
  # Empty subagent (e.g. malformed input). Log anonymously rather than skip.
  printf '{"ts":"%s","subagent":"unknown","tier":"unknown"}\n' "$ts" >> "$stats_file" 2>/dev/null || true
  exit 0
fi

# Sanitize: strip control chars (newlines, ESC, NUL, DEL, etc.) before
# writing to the JSONL log or stderr. Without this, a hostile subagent_type
# value containing a literal newline would inject a forged JSONL record
# (CWE-116, log injection), and ESC sequences could mislead the terminal
# (terminal escape attacks). Defense-in-depth: identifiers should not
# contain control chars anyway.
subagent=$(printf '%s' "$subagent" | tr -d '\000-\037\177')
[ -z "$subagent" ] && {
  printf '{"ts":"%s","subagent":"unknown","tier":"unknown"}\n' "$ts" >> "$stats_file" 2>/dev/null || true
  exit 0
}

# Map subagent name to model tier. Best-effort; non-leverage agents get "other".
case "$subagent" in
  *git-committer-quick*|*repo-explorer*) tier="haiku" ;;
  *git-committer*|*code-reviewer*|*test-runner*|*research-agent*|*context-gatherer*|*docs-updater*) tier="sonnet" ;;
  *) tier="other" ;;
esac

# Append JSONL record. Best-effort - never block on filesystem errors.
printf '{"ts":"%s","subagent":"%s","tier":"%s"}\n' "$ts" "$subagent" "$tier" >> "$stats_file" 2>/dev/null || true

# Subtle stderr note - only for claude-leverage agents to keep noise low.
# Non-leverage delegations are logged but not announced.
if [ "$tier" != "other" ]; then
  printf '(claude-leverage: %s -> %s)\n' "$subagent" "$tier" >&2
fi

exit 0
