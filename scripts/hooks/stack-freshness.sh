#!/usr/bin/env bash
# stack-freshness.sh
#
# Claude Code / Codex SessionStart hook. NETWORK-FREE — only reads a
# local timestamp file. Emits a one-line nudge via SessionStart
# additionalContext when the stack has not been checked in
# `threshold_days` (default 30; override via CLAUDE_LEVERAGE_FRESHNESS_DAYS
# env var or by editing stack.toml).
#
# Hook protocol:
#   - SessionStart receives a small JSON payload on stdin (not used here).
#   - Exit 0 always.
#   - When nudging, emits stdout JSON: hookSpecificOutput.additionalContext
#     per Claude Code SessionStart spec. This is what makes the model
#     actually see the nudge — stderr from SessionStart is shown to the
#     user but is NOT injected into the model's context window (the
#     v1.4.0 field-feedback report caught this gap; pre-1.4.1 used
#     stderr and the model never acted on it).
#
# The actual version check (Claude Code, Codex, plugin, CLI deps) lives
# in the /stack-check skill — it shells out to the dep tools, hits the
# marketplace catalog over the network, and resets this timestamp on
# successful completion. This hook never does any of that.

set -euo pipefail

# AIDEV-NOTE: SessionStart hooks run on EVERY new Claude/Codex session.
# Keep this fast and silent on the happy path — a slow or chatty
# SessionStart turns into UX paper cuts.

# Emit a SessionStart additionalContext payload on stdout. The message
# may contain arbitrary UTF-8; JSON-escape backslash and double-quote
# (the only two characters that would corrupt the JSON literal —
# control chars are never present in nudge messages).
emit_additional_context() {
  local msg="$1"
  msg=${msg//\\/\\\\}
  msg=${msg//\"/\\\"}
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
}

THRESHOLD_DAYS="${CLAUDE_LEVERAGE_FRESHNESS_DAYS:-30}"

STATE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$STATE_DIR" ] || mkdir -p "$STATE_DIR" 2>/dev/null || STATE_DIR="$HOME/.claude/claude-leverage"
[ -d "$STATE_DIR" ] || mkdir -p "$STATE_DIR" 2>/dev/null || exit 0

LAST_CHECK_FILE="$STATE_DIR/.last-stack-check"

# Drain stdin so callers that pipe in JSON don't get SIGPIPE.
cat >/dev/null 2>&1 || true

# Allow disabling entirely with THRESHOLD_DAYS=0.
case "$THRESHOLD_DAYS" in
  ''|0|*[!0-9]*) exit 0 ;;
esac

now=$(date +%s 2>/dev/null || printf '0')
# Defensive: on a strictly POSIX-conformant system, `date +%s` may emit
# the literal "%s" rather than the epoch. Refuse to do math on it.
case "$now" in ''|*[!0-9]*|0) exit 0 ;; esac

if [ ! -f "$LAST_CHECK_FILE" ]; then
  emit_additional_context "claude-leverage: stack never checked — run /stack-check to verify Claude Code, Codex, plugin, and CLI dep versions"
  exit 0
fi

last=$(cat "$LAST_CHECK_FILE" 2>/dev/null || printf '0')
case "$last" in ''|*[!0-9]*) last=0 ;; esac

age_days=$(( (now - last) / 86400 ))

if [ "$age_days" -ge "$THRESHOLD_DAYS" ]; then
  emit_additional_context "claude-leverage: stack last checked ${age_days}d ago — run /stack-check to look for updates"
fi

exit 0
