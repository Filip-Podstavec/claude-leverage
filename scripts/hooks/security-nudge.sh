#!/usr/bin/env bash
# security-nudge.sh
#
# Claude Code / Codex Stop hook. Prints a non-blocking suggestion to run
# /security-review when:
#   1. Net-new (added) LOC in the working tree since session start crosses
#      a threshold (default 80, override via CLAUDE_LEVERAGE_SECURITY_NUDGE_LOC).
#   2. At least one changed file matches a sensitive-path pattern.
#
# Frequency cap: at most one nudge per session day per branch (tracked in
# $XDG_STATE_HOME/claude-leverage/security-nudges-<date>.txt).
#
# Hook protocol:
#   - Stop hook receives a small JSON payload on stdin (not used here).
#   - Exit 0 always; the message goes to stderr.

set -euo pipefail

# AIDEV-NOTE: Stop hooks fire on EVERY session end. Keep this fast and
# always-non-blocking — a slow Stop hook turns into a UX paper cut.

THRESHOLD_LOC="${CLAUDE_LEVERAGE_SECURITY_NUDGE_LOC:-80}"

NUDGE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || NUDGE_DIR="$HOME/.claude/claude-leverage"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || exit 0

NUDGE_FILE="$NUDGE_DIR/security-nudges-$(date +%Y%m%d).txt"
touch "$NUDGE_FILE" 2>/dev/null || exit 0

# Drain stdin so callers that pipe in JSON don't get SIGPIPE.
cat >/dev/null 2>&1 || true

# Are we inside a git repo? If not, nothing to nudge about.
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  exit 0
fi

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "_unknown_")

# Already nudged on this branch today?
key="$branch"
if grep -Fxq "$key" "$NUDGE_FILE" 2>/dev/null; then
  exit 0
fi

# Count added LOC across staged + unstaged combined.
# "Added" = lines beginning with '+' but not '+++' file headers.
added=$(
  {
    git diff --cached 2>/dev/null
    git diff 2>/dev/null
  } | grep -E '^\+[^+]' 2>/dev/null | wc -l | tr -d ' '
) || added=0
case "$added" in ''|*[!0-9]*) added=0 ;; esac

if [ "$added" -lt "$THRESHOLD_LOC" ]; then
  exit 0
fi

# Check whether any changed file matches a sensitive-path pattern.
changed_files=$(
  {
    git diff --cached --name-only 2>/dev/null
    git diff --name-only 2>/dev/null
  } | sort -u
)
[ -z "$changed_files" ] && exit 0

# Pattern set — kept inline so this script is grep-able. Tunable by
# forking (per-project sensitivity sets are a v1.1 candidate).
sensitive_match=""
while IFS= read -r f; do
  case "$f" in
    *auth*|*login*|*signup*|*session*) sensitive_match="$f"; break ;;
    *crypto*|*encrypt*|*decrypt*|*hash*|*password*|*passwd*) sensitive_match="$f"; break ;;
    *secret*|*token*|*credential*|*.env*|*.pem|*.key) sensitive_match="$f"; break ;;
    *payment*|*billing*|*invoice*|*charge*|*stripe*) sensitive_match="$f"; break ;;
    routes/*|*/routes/*|api/*|*/api/*|controllers/*|*/controllers/*) sensitive_match="$f"; break ;;
    templates/*|*/templates/*|views/*|*/views/*) sensitive_match="$f"; break ;;
    middleware/*|*/middleware/*) sensitive_match="$f"; break ;;
  esac
done <<< "$changed_files"

if [ -z "$sensitive_match" ]; then
  exit 0
fi

printf '(claude-leverage: %s LOC of net-new code touches %s — consider running /security-review before commit)\n' \
  "$added" "$sensitive_match" >&2

printf '%s\n' "$key" >> "$NUDGE_FILE" 2>/dev/null || true
exit 0
