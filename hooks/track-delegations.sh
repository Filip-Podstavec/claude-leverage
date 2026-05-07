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
# Dependencies: jq. Silently disabled if missing (telemetry must never break a session).

set -euo pipefail

# Fail-open silently if jq missing. Telemetry is not security.
command -v jq >/dev/null 2>&1 || exit 0

input=$(cat) || exit 0

tool=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null) || exit 0
[ "$tool" = "Task" ] || exit 0

subagent=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null) || exit 0
[ -z "$subagent" ] && exit 0

# Map subagent name to model tier. Best-effort; non-leverage agents get "other".
case "$subagent" in
  *git-committer-quick*|*repo-explorer*) tier="haiku" ;;
  *git-committer*|*code-reviewer*|*test-runner*|*research-agent*|*context-gatherer*|*docs-updater*) tier="sonnet" ;;
  *) tier="other" ;;
esac

# Append JSONL record. Best-effort - never block on filesystem errors.
stats_file="${HOME}/.claude/claude-leverage-stats.jsonl"
mkdir -p "$(dirname "$stats_file")" 2>/dev/null || true
ts=$(date -u +%FT%TZ 2>/dev/null || echo "unknown")
printf '{"ts":"%s","subagent":"%s","tier":"%s"}\n' "$ts" "$subagent" "$tier" >> "$stats_file" 2>/dev/null || true

# Subtle stderr note - only for claude-leverage agents to keep noise low.
# Non-leverage delegations are logged but not announced.
if [ "$tier" != "other" ]; then
  printf '(claude-leverage: %s -> %s)\n' "$subagent" "$tier" >&2
fi

exit 0
