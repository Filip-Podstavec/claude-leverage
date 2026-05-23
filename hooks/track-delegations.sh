#!/usr/bin/env bash
# track-delegations.sh
#
# Claude Code PostToolUse hook (Task matcher).
# Observability for claude-leverage subagent delegations:
#   - Logs each delegation as a JSONL record to ~/.claude/claude-leverage-stats.jsonl
#     including real token usage extracted from tool_response.usage.* (when available)
#   - Prints a single parenthesized stderr note per delegation, e.g.
#     (claude-leverage: code-reviewer -> sonnet)
#
# Hook protocol:
#   - Receives JSON on stdin with tool_name, tool_input, tool_response
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
# extract the subagent name or token counts, but the delegation count is
# still useful signal.
if ! has_parser; then
  printf '{"ts":"%s","subagent":"unknown","tier":"unknown"}\n' "$ts" >> "$stats_file" 2>/dev/null || true
  exit 0
fi

# Parser available - extract subagent name. The `|| true` is belt-and-suspenders:
# has_parser already returned 0 above, so get_field will succeed, but the explicit
# guard makes the fail-safety visible and matches the pattern used in the
# security hooks (block-dangerous-git, block-secrets-precommit).
subagent=$(get_field '.tool_input.subagent_type') || true
if [ -z "$subagent" ]; then
  printf '{"ts":"%s","subagent":"unknown","tier":"unknown"}\n' "$ts" >> "$stats_file" 2>/dev/null || true
  exit 0
fi

# Sanitize: strip C0 controls (0x00-0x1F including NUL/TAB/LF/ESC),
# DEL (0x7F), and C1 controls (0x80-0x9F including 8-bit CSI). Without
# this, a hostile subagent_type value containing a literal newline would
# inject a forged JSONL record (CWE-116, log injection), and ESC or 8-bit
# CSI sequences could mislead the terminal in stderr output.
subagent=$(printf '%s' "$subagent" | tr -d '\000-\037\177-\237')
[ -z "$subagent" ] && {
  printf '{"ts":"%s","subagent":"unknown","tier":"unknown"}\n' "$ts" >> "$stats_file" 2>/dev/null || true
  exit 0
}

# Map subagent name to model tier. Best-effort; non-leverage agents get "other".
# context-gatherer moved to haiku in v0.11 after benchmark surfaced that
# baseline already uses Haiku for context exploration via Claude Code's
# built-in `Explore` agent; Sonnet was structurally more expensive.
case "$subagent" in
  *git-committer-quick*|*repo-explorer*|*context-gatherer*) tier="haiku" ;;
  *git-committer*|*code-reviewer*|*test-runner*|*research-agent*|*docs-updater*) tier="sonnet" ;;
  *) tier="other" ;;
esac

# Extract token-usage and duration metrics from the PostToolUse payload.
# Claude Code's hook input includes tool_response with the agent's response
# metadata. Field paths verified empirically against an actual delegation:
#   tool_response.usage.input_tokens
#   tool_response.usage.output_tokens
#   tool_response.usage.cache_read_input_tokens
#   tool_response.usage.cache_creation_input_tokens
#   tool_response.totalTokens
#   tool_response.totalDurationMs
# Each get_field call already returns empty string when the field is absent.
input_tokens=$(get_field '.tool_response.usage.input_tokens') || true
output_tokens=$(get_field '.tool_response.usage.output_tokens') || true
cache_read=$(get_field '.tool_response.usage.cache_read_input_tokens') || true
cache_create=$(get_field '.tool_response.usage.cache_creation_input_tokens') || true
total_tokens=$(get_field '.tool_response.totalTokens') || true
duration_ms=$(get_field '.tool_response.totalDurationMs') || true

# Sanitize: keep only digits, then validate against JSON integer grammar
# (no leading zeros, except the single value "0"). Float-valued fields
# would otherwise become invalid JSON like "00" after digit-stripping
# (e.g. "0.0" -> "00"), causing the aggregator to silently drop the
# entire log line. Anything that does not match returns empty -> null.
sanitize_int() {
  local s
  s=$(printf '%s' "$1" | tr -cd '0-9')
  case "$s" in
    "")        printf '' ;;
    0)         printf '0' ;;
    [1-9]*)    printf '%s' "$s" ;;
    *)         printf '' ;;
  esac
}
input_tokens=$(sanitize_int "$input_tokens")
output_tokens=$(sanitize_int "$output_tokens")
cache_read=$(sanitize_int "$cache_read")
cache_create=$(sanitize_int "$cache_create")
total_tokens=$(sanitize_int "$total_tokens")
duration_ms=$(sanitize_int "$duration_ms")

# Build JSONL record. Token fields default to null if not present so the
# record stays valid JSON even when Claude Code's payload shape differs
# from what we discovered. Old records (without these fields) remain
# parseable - aggregators should treat missing fields as null.
printf '{"ts":"%s","subagent":"%s","tier":"%s","input_tokens":%s,"output_tokens":%s,"cache_read_input_tokens":%s,"cache_creation_input_tokens":%s,"total_tokens":%s,"duration_ms":%s}\n' \
  "$ts" "$subagent" "$tier" \
  "${input_tokens:-null}" "${output_tokens:-null}" \
  "${cache_read:-null}" "${cache_create:-null}" \
  "${total_tokens:-null}" "${duration_ms:-null}" \
  >> "$stats_file" 2>/dev/null || true

# Subtle stderr note - only for claude-leverage agents to keep noise low.
# Non-leverage delegations are logged but not announced.
if [ "$tier" != "other" ]; then
  if [ -n "$total_tokens" ]; then
    printf '(claude-leverage: %s -> %s, %s tok)\n' "$subagent" "$tier" "$total_tokens" >&2
  else
    printf '(claude-leverage: %s -> %s)\n' "$subagent" "$tier" >&2
  fi
fi

exit 0
