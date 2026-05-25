#!/usr/bin/env bash
# bare-repo-nudge.sh
#
# Claude Code / Codex SessionStart hook. Two-branch proactive nudge for
# the cases where claude-leverage's *convention* layer would otherwise
# be inert because the project hasn't been bootstrapped:
#
#   Branch A — cwd is NOT inside a git repo (and is not a
#              just-opened-terminal location like $HOME / /tmp / /etc).
#              Nudge: `git init` + /init-repo before writing code.
#
#   Branch B — cwd IS inside a git repo, but the repo root has neither
#              AGENTS.md nor CLAUDE.md AND looks like a real project
#              (has a recognizable project marker file like
#              package.json / pyproject.toml / Cargo.toml / go.mod /
#              pom.xml / Gemfile / composer.json / mix.exs / *.csproj).
#              Nudge: /init-repo to drop AGENTS.md so the convention
#              layer (AIDEV anchors, structured logging, per-dir
#              AGENTS.md, module org) actually gets loaded.
#
# Without branch B, the plugin's hooks fire but the conventions they
# reference live in AGENTS.md and stay invisible to the model. v1.4.3
# added branch B after field feedback "leverage assumes AGENTS.md and
# doesn't run much when it's missing." (It's true — by design. The
# nudge surfaces /init-repo as the bootstrap.)
#
# Hook protocol:
#   - SessionStart receives a small JSON payload on stdin (not used here).
#   - Exit 0 always.
#   - When nudging, emits stdout JSON with hookSpecificOutput.additionalContext
#     per Claude Code SessionStart spec. The model sees this in its context
#     window (stderr from SessionStart would NOT be injected).
#
# Rate limit: one nudge per cwd (branch A) or per repo root (branch B)
# per day, tracked in $STATE_DIR/bare-repo-nudges-YYYYMMDD.txt.

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

# Detect whether a directory holds a recognizable project (i.e. is
# worth bootstrapping with AGENTS.md). Excludes scratch/docs-only repos
# from branch B's nudge so users don't get pinged on personal-notes
# repos that have no codebase.
has_project_marker() {
  local d="$1"
  for marker in \
    package.json pyproject.toml setup.py setup.cfg requirements.txt \
    Cargo.toml go.mod pom.xml build.gradle build.gradle.kts \
    Gemfile composer.json mix.exs Package.swift CMakeLists.txt
  do
    [ -f "$d/$marker" ] && return 0
  done
  # *.csproj is a glob; check via globbing.
  for f in "$d"/*.csproj; do [ -e "$f" ] && return 0; done
  return 1
}

cwd=$(pwd 2>/dev/null) || exit 0
[ -z "$cwd" ] && exit 0
cwd_canon=$(canon "$cwd")

# Skip "uninteresting" cwds where any no-conventions nudge is noise
# rather than signal: terminal just opened in $HOME, scratch dirs,
# system roots.
for skip in "${HOME:-}" "${USERPROFILE:-}" "/" "/tmp" "/var" "/etc" "/root"; do
  [ -n "$skip" ] || continue
  skip_canon=$(canon "$skip")
  if [ "$cwd_canon" = "$skip_canon" ]; then
    exit 0
  fi
done

TODAY=$(date +%Y%m%d 2>/dev/null || printf '00000000')
NUDGE_FILE="$NUDGE_DIR/bare-repo-nudges-$TODAY.txt"
touch "$NUDGE_FILE" 2>/dev/null || exit 0

# ----------------------------------------------------------------------
# Branch selection
# ----------------------------------------------------------------------
nudge_key=""
nudge_msg=""

if repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) && [ -n "$repo_root" ]; then
  # Branch B candidate: inside a git repo.
  if [ -f "$repo_root/AGENTS.md" ] || [ -f "$repo_root/CLAUDE.md" ]; then
    exit 0  # conventions already loaded somehow
  fi
  if ! has_project_marker "$repo_root"; then
    exit 0  # docs/scratch repo — branch B not applicable
  fi
  nudge_key=$(canon "$repo_root")
  short=$(printf '%s' "$repo_root" | sed "s|^$HOME|~|" 2>/dev/null || printf '%s' "$repo_root")
  nudge_msg="claude-leverage: git repo ${short} has no AGENTS.md or CLAUDE.md at the root — the plugin's hooks fire but the project-level conventions (AIDEV-NOTE/TODO/QUESTION anchors, JSON-lines structured logging, per-directory AGENTS.md, module organization) live in AGENTS.md and stay invisible without it. Invoke /init-repo to drop AGENTS.md from the per-language template before writing code, so future agents inherit the conventions you're about to set."
else
  # Branch A: cwd is not inside any git repo.
  nudge_key="$cwd_canon"
  short=$(printf '%s' "$cwd" | sed "s|^$HOME|~|" 2>/dev/null || printf '%s' "$cwd")
  nudge_msg="claude-leverage: working directory ${short} is not a git repo — if you're starting project work here, run \`git init\` and then invoke /init-repo to drop AGENTS.md + .gitignore + structured-logging template before writing code. Skip if this is throwaway scratch work."
fi

# Per-key-per-day rate limit. Branch A keys on cwd; branch B keys on
# repo root, so opening sessions in different subdirs of the same
# unconfigured repo nudges only once per day.
if grep -Fxq "$nudge_key" "$NUDGE_FILE" 2>/dev/null; then
  exit 0
fi

emit_additional_context "$nudge_msg"
printf '%s\n' "$nudge_key" >> "$NUDGE_FILE" 2>/dev/null || true
exit 0
