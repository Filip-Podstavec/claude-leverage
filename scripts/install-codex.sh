#!/usr/bin/env bash
# install-codex.sh — Install the claude-leverage stack into Codex CLI.
#
# Codex has no plugin marketplace, so this script is the equivalent of
# `/plugin install` for Codex:
#   1. Resolves __CLAUDE_LEVERAGE_DIR__ in .codex/hooks.json to this repo's
#      absolute path and writes the resolved file to ~/.codex/hooks.json
#      (creating a backup of any existing file).
#   2. Appends an `@<absolute-path>/AGENTS.md` reference to ~/.codex/AGENTS.md
#      so the canonical guidance loads in every Codex session.
#   3. Copies .codex/agents/*.toml (if any) to ~/.codex/agents/.
#
# Idempotent: re-running detects existing install via the marker comment in
# ~/.codex/AGENTS.md and updates in place instead of duplicating.
#
# Prerequisites: codex CLI installed (npm i -g @openai/codex) — checked but
# not installed by this script.

set -euo pipefail

# Resolve this repo's absolute path (script is in scripts/, so go up one).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
MARKER="# claude-leverage: managed import — do not edit between markers"
MARKER_END="# claude-leverage: end managed import"

say() { printf '[install-codex] %s\n' "$*"; }
die() { printf '[install-codex] ERROR: %s\n' "$*" >&2; exit 1; }

# --- Sanity checks -----------------------------------------------------------

command -v codex >/dev/null 2>&1 || \
  say "WARNING: codex CLI not found on PATH. Install with: npm i -g @openai/codex"

[ -f "$REPO_DIR/.codex/hooks.json" ] || \
  die "expected $REPO_DIR/.codex/hooks.json — are you running from the repo?"
[ -f "$REPO_DIR/AGENTS.md" ] || \
  die "expected $REPO_DIR/AGENTS.md"

mkdir -p "$CODEX_HOME" "$CODEX_HOME/agents"

# --- Resolve hooks.json ------------------------------------------------------

target_hooks="$CODEX_HOME/hooks.json"
if [ -f "$target_hooks" ] && ! grep -q '__CLAUDE_LEVERAGE_DIR__' "$target_hooks" 2>/dev/null \
                          && ! grep -q "claude-leverage" "$target_hooks" 2>/dev/null; then
  cp "$target_hooks" "$target_hooks.pre-claude-leverage.bak"
  say "backed up existing hooks.json -> $target_hooks.pre-claude-leverage.bak"
fi

# Use sed to substitute the placeholder. Use # as delimiter so /-bearing paths
# don't break it.
sed "s#__CLAUDE_LEVERAGE_DIR__#$REPO_DIR#g" \
  "$REPO_DIR/.codex/hooks.json" > "$target_hooks"
say "wrote $target_hooks (paths resolved to $REPO_DIR)"

# --- Wire AGENTS.md import ---------------------------------------------------

target_agents="$CODEX_HOME/AGENTS.md"
touch "$target_agents"

if grep -qF "$MARKER" "$target_agents"; then
  # Already installed — replace the marker block in place.
  # Use awk to delete the existing marker block, then append a fresh one.
  awk -v start="$MARKER" -v end="$MARKER_END" '
    $0 == start { skip = 1; next }
    $0 == end   { skip = 0; next }
    !skip
  ' "$target_agents" > "$target_agents.tmp"
  mv "$target_agents.tmp" "$target_agents"
  say "removed previous claude-leverage block from $target_agents"
fi

{
  printf '\n%s\n' "$MARKER"
  printf '# Imports the canonical guidance from the claude-leverage stack at:\n'
  printf '#   %s\n' "$REPO_DIR"
  printf '# Re-running scripts/install-codex.sh keeps this block fresh.\n'
  printf '@%s/AGENTS.md\n' "$REPO_DIR"
  printf '%s\n' "$MARKER_END"
} >> "$target_agents"
say "added @import to $target_agents"

# --- Copy Codex agents -------------------------------------------------------

agents_src="$REPO_DIR/.codex/agents"
if [ -d "$agents_src" ] && [ -n "$(ls -A "$agents_src" 2>/dev/null)" ]; then
  cp -f "$agents_src"/*.toml "$CODEX_HOME/agents/" 2>/dev/null && \
    say "copied $(ls "$agents_src" | wc -l) agent definition(s) to $CODEX_HOME/agents/"
else
  say "no agents in $agents_src yet — skipping"
fi

# --- Done --------------------------------------------------------------------

say "install complete."
say "next: start a Codex session and verify with: codex --version"
say "uninstall: delete the marker block from $target_agents and remove $target_hooks"
