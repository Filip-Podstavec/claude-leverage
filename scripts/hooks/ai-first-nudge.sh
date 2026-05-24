#!/usr/bin/env bash
# ai-first-nudge.sh
#
# Claude Code / Codex PostToolUse hook (Write|Edit|MultiEdit matcher).
#
# Prints non-blocking stderr nudges when AI-first conventions look unmet:
#   1. Large net-new code (>=50 LOC) in a single file with no AIDEV-NOTE
#      anchor in the added lines.
#   2. New top-level module directory created without an AGENTS.md.
#
# Never blocks (always exits 0). Frequency cap: one nudge per file per
# session (tracked in $XDG_STATE_HOME/claude-leverage/session-nudges.txt
# or ~/.claude/claude-leverage/session-nudges.txt).
#
# Hook protocol:
#   - Receives JSON on stdin with tool_name + tool_input/tool_response
#   - Exit 0 always; messages go to stderr

set -euo pipefail

# AIDEV-NOTE: this hook never modifies state besides the session-nudges
# file. Keep it that way — a PostToolUse that mutates user files would be
# surprising and dangerous.

# Source the shared JSON parser helper from the same dir.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

# Without any JSON parser, silently skip (do not nag with parser warnings
# on every Write — security hooks already cover that case).
if ! has_parser; then
  exit 0
fi

# Threshold for "large net-new" — declared here so it's easy to find and tune.
THRESHOLD_LOC="${CLAUDE_LEVERAGE_NUDGE_LOC:-50}"

# Session-nudge tracking file. Per-machine, per-session-day granularity
# (we don't have a real session id from the hook payload, so we use date).
NUDGE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || NUDGE_DIR="$HOME/.claude/claude-leverage"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || exit 0
NUDGE_FILE="$NUDGE_DIR/session-nudges-$(date +%Y%m%d).txt"
touch "$NUDGE_FILE" 2>/dev/null || exit 0

# Read hook input from stdin and pull the file path the tool acted on.
read_stdin
tool=$(get_field '.tool_name') || exit 0
case "$tool" in
  Write|Edit|MultiEdit) ;;
  *) exit 0 ;;
esac

# Resolve the file path from tool_input. Different tools use slightly
# different keys; try the common ones in order.
file_path=$(get_field '.tool_input.file_path' 2>/dev/null) || true
[ -z "${file_path:-}" ] && file_path=$(get_field '.tool_input.path' 2>/dev/null) || true
[ -z "${file_path:-}" ] && exit 0

# Ignore patterns: tests, fixtures, generated code, dotfiles, archive.
case "$file_path" in
  *_test.*|*test_*.py|*.test.ts|*.test.tsx|*.test.js|*.test.jsx) exit 0 ;;
  */tests/*|*/test/*|*/__tests__/*|*/fixtures/*|*/__pycache__/*) exit 0 ;;
  */node_modules/*|*/.git/*|*/dist/*|*/build/*|*/.next/*) exit 0 ;;
  */bench/archive-token-savings-thesis/*) exit 0 ;;
  *.lock|*.lockb|*.snap) exit 0 ;;
esac

# Already nudged this file today?
if grep -Fxq "$file_path" "$NUDGE_FILE" 2>/dev/null; then
  exit 0
fi

# Try to count added LOC. For Write: count all non-empty lines (whole-file
# write is net-new). For Edit/MultiEdit: count new_string lines minus
# old_string lines (approximation: just count new_string lines as an
# upper bound — we want a heuristic, not accounting).
added_loc=0
# Defensive: each branch falls back to 0 if anything in the pipeline fails
# under `set -euo pipefail`. grep -c always emits a number when given input,
# but the safety belt costs nothing.
count_non_blank() {
  local body="$1"
  local n
  n=$(printf '%s\n' "$body" | grep -cv '^[[:space:]]*$' 2>/dev/null || printf '0')
  case "$n" in ''|*[!0-9]*) printf '0' ;; *) printf '%s' "$n" ;; esac
}
case "$tool" in
  Write)
    content=$(get_field '.tool_input.content' 2>/dev/null) || content=""
    added_loc=$(count_non_blank "$content")
    ;;
  Edit)
    new_string=$(get_field '.tool_input.new_string' 2>/dev/null) || new_string=""
    added_loc=$(count_non_blank "$new_string")
    ;;
  MultiEdit)
    # Sum non-blank lines across edits[*].new_string. The earlier
    # implementation counted lines in the raw JSON blob, which counted
    # JSON brackets and old_string content too — producing inflated
    # counts that triggered spurious nudges. This Python pass walks the
    # array properly. Falls back to 0 if no python is available.
    PY_BIN=$(command -v python3 || command -v python || true)
    if [ -n "$PY_BIN" ]; then
      added_loc=$(printf '%s' "$JSON_INPUT" | "$PY_BIN" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    edits = (data.get("tool_input", {}) or {}).get("edits", []) or []
    n = 0
    for e in edits:
        if isinstance(e, dict):
            s = e.get("new_string", "")
            if isinstance(s, str):
                n += sum(1 for ln in s.splitlines() if ln.strip())
    print(n)
except Exception:
    print(0)
' 2>/dev/null || printf '0')
      case "$added_loc" in ''|*[!0-9]*) added_loc=0 ;; esac
    else
      added_loc=0
    fi
    ;;
esac

# Check: large net-new code, no AIDEV-NOTE in the change.
#
# We deliberately do NOT also nudge about missing per-directory AGENTS.md
# files. That check is too easy to get wrong from a hook (almost every
# directory has 3+ files; the "new module" intent is hard to infer from a
# single Write event). Phase 3's docs-sync skill handles that case at PR
# time, where the author can actually answer "is this a non-trivial
# module that warrants its own AGENTS.md?".
if [ "$added_loc" -lt "$THRESHOLD_LOC" ]; then
  exit 0
fi

# Check whether the new content contains an AIDEV-* anchor.
blob=""
case "$tool" in
  Write)     blob=$(get_field '.tool_input.content' 2>/dev/null || true) ;;
  Edit)      blob=$(get_field '.tool_input.new_string' 2>/dev/null || true) ;;
  MultiEdit) blob=$(get_field '.tool_input.edits' 2>/dev/null || true) ;;
esac

if printf '%s' "$blob" | grep -q 'AIDEV-' ; then
  exit 0
fi

short_path=$(printf '%s' "$file_path" | sed "s|^$HOME|~|")
printf '(claude-leverage: %s LOC of net-new code in %s with no AIDEV-NOTE anchor — consider anchoring load-bearing parts)\n' \
  "$added_loc" "$short_path" >&2

printf '%s\n' "$file_path" >> "$NUDGE_FILE" 2>/dev/null || true
exit 0
