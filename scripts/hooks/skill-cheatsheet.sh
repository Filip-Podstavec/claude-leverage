#!/usr/bin/env bash
# skill-cheatsheet.sh
#
# Claude Code / Codex SessionStart hook. Gated, rate-limited nudge
# that lists high-value claude-leverage skills + their trigger
# conditions, surfacing them in the model's working context at session
# start. The point: skill auto-activation is partly broken in the 2026
# Claude Code runtime — slash invocation works, but the model's
# autonomous recall at the right moment does not. Surfacing the
# cheatsheet via SessionStart additionalContext lifts recall without
# flooding every session with marketing copy.
#
# Gating (all must pass; if any fails, the hook is silent):
#
#   1. cwd is "interesting" — not $HOME, $USERPROFILE, /, /tmp, /var,
#      /etc, /root. Same skip list as bare-repo-nudge.sh.
#   2. cwd is inside a git repo whose root AGENTS.md contains a
#      claude-leverage:* marker (i.e., user has actively adopted the
#      stack). No unsolicited nudge in repos that never opted in.
#   3. State file for THIS repo shows last cheatsheet > N days ago
#      (default 14; override via CLAUDE_LEVERAGE_SKILL_HINT_DAYS;
#      set to 0 to disable entirely).
#
# Hook protocol:
#   - SessionStart receives a small JSON payload on stdin (not used).
#   - Exit 0 always.
#   - When nudging, emits stdout JSON with hookSpecificOutput
#     .additionalContext per Claude Code SessionStart spec.
#   - The state file is per-repo (keyed on a short hash of the repo
#     root path) so opening sessions in different repos doesn't
#     suppress each other.
#
# See ADR 0006 for the rationale on gating + cadence.

set -euo pipefail

# AIDEV-NOTE: SessionStart hooks fire on EVERY new session. Keep this
# fast and silent on the happy path — slow or chatty SessionStart turns
# into UX paper cuts.

HINT_DAYS="${CLAUDE_LEVERAGE_SKILL_HINT_DAYS:-14}"

# Allow disabling entirely with HINT_DAYS=0.
case "$HINT_DAYS" in
  ''|0|*[!0-9]*) exit 0 ;;
esac

STATE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$STATE_DIR" ] || mkdir -p "$STATE_DIR" 2>/dev/null || STATE_DIR="$HOME/.claude/claude-leverage"
[ -d "$STATE_DIR" ] || mkdir -p "$STATE_DIR" 2>/dev/null || exit 0

# Drain stdin so callers piping JSON don't get SIGPIPE.
cat >/dev/null 2>&1 || true

# Emit stdout JSON for SessionStart context injection. Escapes the two
# characters that would corrupt the JSON literal; control chars never
# appear in cheatsheet messages.
emit_additional_context() {
  local msg="$1"
  msg=${msg//\\/\\\\}
  msg=${msg//\"/\\\"}
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
}

# Canonicalize a path for cross-platform comparison. Same helper as
# bare-repo-nudge.sh — Git Bash on Windows emits MSYS-form paths from
# pwd but env vars may be passed in native form.
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

# Gate 1: skip "uninteresting" cwds where any nudge is noise rather
# than signal. Same skip list as bare-repo-nudge.sh.
for skip in "${HOME:-}" "${USERPROFILE:-}" "/" "/tmp" "/var" "/etc" "/root"; do
  [ -n "$skip" ] || continue
  skip_canon=$(canon "$skip")
  if [ "$cwd_canon" = "$skip_canon" ]; then
    exit 0
  fi
done

# Gate 2: inside a git repo with claude-leverage marker in AGENTS.md.
repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$repo_root" ] || exit 0

agents_md="$repo_root/AGENTS.md"
[ -f "$agents_md" ] || exit 0

# AIDEV-NOTE: the marker pattern is intentionally permissive — any line
# mentioning "claude-leverage:" counts as adoption. The /init-repo
# template + claude-md-snippets/ stamp this on the way in, so this
# detects "did the user install the stack into this repo" without
# being brittle to wording variations.
grep -q 'claude-leverage:' "$agents_md" 2>/dev/null || exit 0

# Gate 3: rate-limit per-repo. Hash the canonical repo root path so
# the state file is unique per repo.
repo_canon=$(canon "$repo_root")
# Cheap, portable hash: cksum the path. Different repos -> different
# state files; same repo across sessions -> same state file.
repo_hash=$(printf '%s' "$repo_canon" | cksum 2>/dev/null | awk '{print $1}')
[ -n "$repo_hash" ] || exit 0
LAST_FILE="$STATE_DIR/.last-skill-cheatsheet-$repo_hash"

now=$(date +%s 2>/dev/null || printf '0')
case "$now" in ''|*[!0-9]*|0) exit 0 ;; esac

if [ -f "$LAST_FILE" ]; then
  last=$(cat "$LAST_FILE" 2>/dev/null || printf '0')
  case "$last" in ''|*[!0-9]*) last=0 ;; esac
  age_days=$(( (now - last) / 86400 ))
  if [ "$age_days" -lt "$HINT_DAYS" ]; then
    exit 0
  fi
fi

# All gates passed — emit the cheatsheet.
#
# The message is intentionally compact. Listing all 13 skills with
# triggers would be too long; the model can run /skill list to
# enumerate. This nudge focuses on the four it should reach for most
# often and the entry-point ones.
msg="claude-leverage skills (full list: /skill list). Reach for: /security-review after sensitive-path edits; /adr-new when making a load-bearing decision; /session-log at end of a substantial session; /repo-doctor to audit AI-readiness; /glossary-init + /arch-map to set up the structured discoverability layer if missing. See AGENTS.md for the full table."

emit_additional_context "$msg"
printf '%s\n' "$now" > "$LAST_FILE" 2>/dev/null || true
exit 0
