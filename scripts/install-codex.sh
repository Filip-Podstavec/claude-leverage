#!/usr/bin/env bash
# install-codex.sh — Install the claude-leverage stack into Codex CLI.
#
# Codex's plugin marketplace delivers skills + hooks, but not subagents, the
# global @AGENTS.md import, or slash commands. This script is the full-stack
# install for Codex — the equivalent of `/plugin install` plus those extras:
#   1. Resolves __CLAUDE_LEVERAGE_DIR__ in .codex/hooks.json to this repo's
#      absolute path and writes the resolved file to ~/.codex/hooks.json
#      (creating a backup of any existing file).
#   2. Appends an `@<absolute-path>/AGENTS.md` reference to ~/.codex/AGENTS.md
#      so the canonical guidance loads in every Codex session.
#   3. Copies .codex/agents/*.toml (if any) to ~/.codex/agents/.
#   4. Copies skills/* to ~/.agents/skills/claude-leverage/ so Codex's
#      skills resolver finds them (cross-tool SKILL.md spec).
#
# Idempotent: re-running detects existing install via the marker comment in
# ~/.codex/AGENTS.md, replaces it in place, and overwrites
# ~/.agents/skills/claude-leverage/ rather than appending.
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

# --- Copy skills -------------------------------------------------------------
#
# Codex's skills resolver looks in ~/.agents/skills/ for user-scope skills
# (per agentskills.io spec). We install ours under a namespaced subdir so
# uninstall is a single `rm -rf`. Re-run replaces the whole dir.

SKILLS_SRC="$REPO_DIR/skills"
SKILLS_HOME="${CLAUDE_LEVERAGE_AGENTS_HOME:-$HOME/.agents}"
SKILLS_DEST="$SKILLS_HOME/skills/claude-leverage"
SKILLS_STAGING="$SKILLS_DEST.new"

if [ -d "$SKILLS_SRC" ]; then
  mkdir -p "$SKILLS_HOME/skills"

  # AIDEV-NOTE: copy to a staging sibling dir first, then atomically swap.
  # If any cp fails mid-loop, the previous install stays intact rather
  # than getting wiped to a half-installed state.
  rm -rf "$SKILLS_STAGING"
  mkdir -p "$SKILLS_STAGING"

  installed_count=0
  copy_failed=0
  for skill_dir in "$SKILLS_SRC"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    # Only copy directories that contain a SKILL.md (skip stray dirs).
    if [ -f "$skill_dir/SKILL.md" ]; then
      if cp -R "$skill_dir" "$SKILLS_STAGING/$skill_name" 2>/dev/null; then
        installed_count=$((installed_count + 1))
      else
        copy_failed=1
        say "WARNING: failed to copy $skill_name; aborting skills install"
        break
      fi
    fi
  done

  if [ "$copy_failed" -eq 1 ]; then
    rm -rf "$SKILLS_STAGING"
    say "skills install aborted; previous install (if any) at $SKILLS_DEST is untouched"
  elif [ "$installed_count" -gt 0 ]; then
    # Atomic-ish swap. mv replaces an existing directory only if both
    # are on the same filesystem (always true here — same $HOME).
    if [ -d "$SKILLS_DEST" ]; then
      rm -rf "$SKILLS_DEST.old"
      mv "$SKILLS_DEST" "$SKILLS_DEST.old"
    fi
    mv "$SKILLS_STAGING" "$SKILLS_DEST"
    rm -rf "$SKILLS_DEST.old"
    say "copied $installed_count skill(s) to $SKILLS_DEST/"
  else
    rm -rf "$SKILLS_STAGING"
    say "no skills with SKILL.md found in $SKILLS_SRC — skipping"
  fi
else
  say "no skills/ dir in $REPO_DIR — skipping"
fi

# --- Done --------------------------------------------------------------------

say "install complete."
say "next: start a Codex session and verify with: codex --version"
say ""
say "to uninstall, run:"
say "  rm -rf $SKILLS_DEST"
say "  rm -f $CODEX_HOME/agents/security-reviewer.toml $CODEX_HOME/agents/flaky-test-isolator.toml"
say "  rm -f $target_hooks  # (or restore $target_hooks.pre-claude-leverage.bak if present)"
say "  # then edit $target_agents and remove the block between the two '# claude-leverage:' markers"
