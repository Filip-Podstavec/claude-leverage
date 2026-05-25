#!/usr/bin/env bash
# bare-repo-nudge.sh
#
# Claude Code / Codex SessionStart hook. When the current working
# directory is NOT inside a git repo and is also not a "just-opened-
# terminal" location ($HOME, /tmp, /, etc.), emits a one-time-per-day
# nudge suggesting `git init` + /init-repo before writing project code.
#
# Why this exists: the security-nudge Stop hook is git-only by design
# (it reads `git diff HEAD`), so fresh non-git projects get zero
# guardrail signal — exactly the situation where guardrails are most
# valuable. This hook fills the gap by nudging the model proactively at
# SessionStart instead of waiting for the missing security-review hook
# to fire (it never will).
#
# Hook protocol:
#   - SessionStart receives a small JSON payload on stdin (not used here).
#   - Exit 0 always.
#   - When nudging, emits stdout JSON with hookSpecificOutput.additionalContext
#     per Claude Code SessionStart spec. The model sees this in its context
#     window (stderr from SessionStart would NOT be injected).
#
# Rate limit: one nudge per cwd per day, tracked in
# $STATE_DIR/bare-repo-nudges-YYYYMMDD.txt.

set -euo pipefail

# AIDEV-NOTE: SessionStart hooks fire on EVERY new session. Keep this
# fast and silent on the happy path — slow or chatty SessionStart turns
# into UX paper cuts.

NUDGE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || NUDGE_DIR="$HOME/.claude/claude-leverage"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || exit 0

# Drain stdin so callers piping JSON don't get SIGPIPE.
cat >/dev/null 2>&1 || true

# Emit stdout JSON for SessionStart context injection. Escapes the two
# characters that would corrupt the JSON literal; control chars never
# appear in nudge messages.
emit_additional_context() {
  local msg="$1"
  msg=${msg//\\/\\\\}
  msg=${msg//\"/\\\"}
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
}

# Canonicalize a path for cross-platform comparison. Git Bash on Windows
# emits MSYS-form paths from pwd but env vars like $HOME may be passed
# in native form; cygpath -m brings both sides into the same shape.
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

cwd=$(pwd 2>/dev/null) || exit 0
[ -z "$cwd" ] && exit 0
cwd_canon=$(canon "$cwd")

# Skip "uninteresting" cwds where a no-git nudge is noise rather than
# signal: terminal just opened in $HOME, scratch dirs, system roots.
for skip in "${HOME:-}" "${USERPROFILE:-}" "/" "/tmp" "/var" "/etc" "/root"; do
  [ -n "$skip" ] || continue
  skip_canon=$(canon "$skip")
  if [ "$cwd_canon" = "$skip_canon" ]; then
    exit 0
  fi
done

# Skip if already inside a git repo — there's a real project here, the
# other hooks will pick up from `git diff HEAD`.
if git -C "$cwd" rev-parse --show-toplevel >/dev/null 2>&1; then
  exit 0
fi

# Per-cwd-per-day rate limit. Repeated sessions in the same bare dir
# during one day get exactly one nudge.
TODAY=$(date +%Y%m%d 2>/dev/null || printf '00000000')
NUDGE_FILE="$NUDGE_DIR/bare-repo-nudges-$TODAY.txt"
touch "$NUDGE_FILE" 2>/dev/null || exit 0

if grep -Fxq "$cwd_canon" "$NUDGE_FILE" 2>/dev/null; then
  exit 0
fi

short=$(printf '%s' "$cwd" | sed "s|^$HOME|~|" 2>/dev/null || printf '%s' "$cwd")
emit_additional_context "claude-leverage: working directory ${short} is not a git repo — if you're starting project work here, run \`git init\` and then invoke /init-repo to drop AGENTS.md + .gitignore + structured-logging template before writing code. Skip if this is throwaway scratch work."

printf '%s\n' "$cwd_canon" >> "$NUDGE_FILE" 2>/dev/null || true
exit 0
