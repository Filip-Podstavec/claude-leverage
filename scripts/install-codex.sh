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

# Use Python for the substitution. sed with any single-byte delimiter can
# silently mis-parse when the delimiter character appears literally in
# REPO_DIR (e.g. '#' in '~/projects/my#project/...'), producing a broken
# JSON file with no error. Python's str.replace is delimiter-free.
PY_BIN=$(command -v python3 || command -v python || true)
if [ -z "$PY_BIN" ]; then
  die "python3 or python is required for install-codex (path substitution); install one and re-run"
fi
"$PY_BIN" -c '
import sys
src_path, repo_dir, dst_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src_path, encoding="utf-8") as f:
    body = f.read()
body = body.replace("__CLAUDE_LEVERAGE_DIR__", repo_dir)
with open(dst_path, "w", encoding="utf-8") as f:
    f.write(body)
' "$REPO_DIR/.codex/hooks.json" "$REPO_DIR" "$target_hooks"
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
toml_files=()
if [ -d "$agents_src" ]; then
  # Iterate via explicit existence check rather than `cp ... *.toml`, which
  # would expand to a literal "*.toml" if the glob matches nothing and
  # then `cp` would error out with a noisy "No such file" that the && chain
  # would swallow — making the failure invisible.
  for f in "$agents_src"/*.toml; do
    [ -f "$f" ] && toml_files+=("$f")
  done
fi
if [ "${#toml_files[@]}" -gt 0 ]; then
  cp -f "${toml_files[@]}" "$CODEX_HOME/agents/"
  say "copied ${#toml_files[@]} agent definition(s) to $CODEX_HOME/agents/"
else
  say "no Codex agents in $agents_src yet — skipping"
fi

# --- Done --------------------------------------------------------------------

say "install complete."
say "next: start a Codex session and verify with: codex --version"
say "uninstall: delete the marker block from $target_agents and remove $target_hooks"
