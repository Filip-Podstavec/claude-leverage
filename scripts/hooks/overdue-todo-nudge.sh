#!/usr/bin/env bash
# overdue-todo-nudge.sh
#
# Claude Code / Codex SessionStart hook. Network-free.
#
# Surfaces AIDEV-TODO / AIDEV-QUESTION anchors whose ISO-8601 deadline has
# already passed. Deadlines otherwise rot silently — /stack-check reports
# them, but only when the user thinks to run it. This passive nudge closes
# that gap by flagging overdue anchors at session start, one line, once per
# repo per day.
#
# Deadline forms recognized (matching the stack-check convention):
#   AIDEV-TODO(by: 2026-08-01):        AIDEV-QUESTION(by: 2026-08-01):
#   AIDEV-TODO(2026-08-01):            (bare ISO date)
#   AIDEV-TODO(deadline: 2026-08-01):
#
# Scope is deliberately tight to keep false positives near zero (a chatty
# SessionStart nudge gets disabled, and then it protects nothing):
#   - Source code only. Markdown / json / txt / rst are skipped — that's
#     where the convention's own *example* anchors live (docs, templates,
#     tests, this plugin's own CHANGELOG), and firing on those would be
#     pure noise.
#   - doc / template / test / bench / workflow trees skipped outright.
#   - First-token rule: the FIRST AIDEV-* token on the line must itself be
#     TODO/QUESTION. This drops lines where an AIDEV-NOTE merely *mentions*
#     an example `AIDEV-TODO(by: …)` while documenting the convention.
#
# Hook protocol:
#   - SessionStart receives a small JSON payload on stdin (unused here).
#   - Exit 0 always; never blocks.
#   - Nudges via stdout JSON hookSpecificOutput.additionalContext (stderr
#     from SessionStart is NOT injected into the model context window).
#
# Opt-out: CLAUDE_LEVERAGE_SKIP_OVERDUE_TODO=1.

set -euo pipefail

# AIDEV-NOTE: SessionStart fires on EVERY new session — keep this fast and
# silent on the happy path. git grep over tracked files is cheap; the
# per-line subprocess work only runs on the handful of deadline anchors.

[ "${CLAUDE_LEVERAGE_SKIP_OVERDUE_TODO:-0}" = "1" ] && exit 0

# Drain stdin so callers piping JSON don't get SIGPIPE.
cat >/dev/null 2>&1 || true

NUDGE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || NUDGE_DIR="$HOME/.claude/claude-leverage"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || exit 0

# Emit stdout JSON for SessionStart context injection. Escapes the two
# characters that would corrupt the JSON literal; control chars never
# appear in nudge messages.
emit_additional_context() {
  local msg="$1"
  msg=${msg//\\/\\\\}
  msg=${msg//\"/\\\"}
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
}

canon() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m -- "$p" 2>/dev/null && return
  fi
  if command -v realpath >/dev/null 2>&1; then
    realpath "$p" 2>/dev/null && return
  fi
  printf '%s' "$p"
}

command -v git >/dev/null 2>&1 || exit 0

cwd=$(pwd 2>/dev/null) || exit 0
[ -z "$cwd" ] && exit 0
repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -z "$repo_root" ] && exit 0

# Today as YYYY-MM-DD. ISO dates are fixed-width, so lexical string compare
# is chronological — no date arithmetic (and its GNU-vs-BSD portability
# headaches) required. If `date` is unavailable we can't compare; bail.
today=$(date +%F 2>/dev/null) || exit 0
case "$today" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;; *) exit 0 ;; esac

# Per-repo-per-day rate limit.
TODAY_KEY=$(date +%Y%m%d 2>/dev/null || printf '00000000')
NUDGE_FILE="$NUDGE_DIR/overdue-todo-nudges-$TODAY_KEY.txt"
touch "$NUDGE_FILE" 2>/dev/null || exit 0
repo_key=$(canon "$repo_root")
if grep -Fxq "$repo_key" "$NUDGE_FILE" 2>/dev/null; then
  exit 0
fi

# Candidate lines: an AIDEV-TODO/QUESTION anchor carrying an ISO date in its
# parenthesized head. `|| true` because git grep exits 1 on no match, which
# under `set -e` would otherwise kill the hook.
anchor_re='AIDEV-(TODO|QUESTION)\((by:[[:space:]]*|deadline:[[:space:]]*)?[0-9]{4}-[0-9]{2}-[0-9]{2}\)'
matches=$(git -C "$repo_root" grep -nIE "$anchor_re" 2>/dev/null || true)
[ -z "$matches" ] && { printf '%s\n' "$repo_key" >> "$NUDGE_FILE" 2>/dev/null || true; exit 0; }

overdue_count=0
examples=""
MAX_EXAMPLES=5

while IFS= read -r match; do
  [ -z "$match" ] && continue
  path=${match%%:*}
  rest=${match#*:}
  lineno=${rest%%:*}
  content=${rest#*:}

  # Non-code + example-bearing trees: skip (see header rationale).
  case "$path" in
    *.md|*.markdown|*.mdx|*.txt|*.rst|*.json) continue ;;
  esac
  case "$path" in
    docs/*|templates/*|tests/*|test/*|*/tests/*|*/test/*|bench/*|workflows/*|*/node_modules/*|*/vendor/*) continue ;;
  esac

  # First-token rule: the anchor must be the line's own AIDEV token, not an
  # AIDEV-NOTE that merely quotes a TODO example.
  first_tok=$(printf '%s' "$content" | grep -oE 'AIDEV-[A-Z]+' | head -1)
  case "$first_tok" in
    AIDEV-TODO|AIDEV-QUESTION) ;;
    *) continue ;;
  esac

  deadline=$(printf '%s' "$content" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
  [ -z "$deadline" ] && continue

  # Lexical compare == chronological for fixed-width ISO dates.
  if [[ "$deadline" < "$today" ]]; then
    overdue_count=$((overdue_count + 1))
    if [ "$overdue_count" -le "$MAX_EXAMPLES" ]; then
      examples="${examples}${examples:+; }${path}:${lineno} (due ${deadline})"
    fi
  fi
done <<EOF
$matches
EOF

# Always record the per-day cap key, even when nothing is overdue, so we
# don't re-walk on every session that day.
printf '%s\n' "$repo_key" >> "$NUDGE_FILE" 2>/dev/null || true

[ "$overdue_count" -eq 0 ] && exit 0

more=""
if [ "$overdue_count" -gt "$MAX_EXAMPLES" ]; then
  more=" (+$((overdue_count - MAX_EXAMPLES)) more)"
fi

noun="anchor"
[ "$overdue_count" -gt 1 ] && noun="anchors"

emit_additional_context "claude-leverage: ${overdue_count} overdue AIDEV-TODO/QUESTION ${noun} (deadline already passed) in this repo — ${examples}${more}. These are load-bearing follow-ups whose deadline lapsed; resolve them or push the deadline out. Run /stack-check for the full anchor report."
exit 0
