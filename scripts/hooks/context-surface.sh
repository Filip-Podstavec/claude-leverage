#!/usr/bin/env bash
# context-surface.sh
#
# Claude Code / Codex PreToolUse hook (Read|Edit|Write|MultiEdit matcher).
#
# Surfaces just-in-time context for the file the agent is about to read
# or edit: AIDEV anchors in the file + sibling files, plus optional
# per-dir AGENTS.md chain and ADR cross-references (verbose mode only).
# Reads a pre-built manifest at .claude-leverage-context-map.json
# (produced by scripts/build-context-map.py).
#
# Design goal: reduce per-session token tax from leverage docs by NOT
# preemptively loading them — surface only what's relevant per tool call.
# See docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md.
#
# Graceful no-op behavior:
#   - manifest missing            → silent, exit 0
#   - file not in manifest        → silent, exit 0
#   - file in manifest, no items  → silent, exit 0 (no marker-only emission)
#   - manifest corrupt JSON       → silent, exit 0
#   - schema_version mismatch     → silent, exit 0
#   - no Python on PATH           → silent, exit 0
#   - cwd outside git repo        → silent, exit 0
#   - tool not Read|Edit|Write|MultiEdit → silent, exit 0
#
# Output (when context found):
#   stdout: JSON {hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:"..."}}
#   exit:   0
#
# Tunables (env vars):
#   CLAUDE_LEVERAGE_CTX_MAX_CHARS=4096       cap on additionalContext size
#   CLAUDE_LEVERAGE_CTX_MAX_SIBLINGS=5       cap on anchors_in_dir lines
#   CLAUDE_LEVERAGE_CTX_VERBOSE=1            also surface agents_md + adrs refs
#   CLAUDE_LEVERAGE_CTX_DISABLE=1            opt-out entirely (kill switch)

set -euo pipefail

# Opt-out kill switch — hard-stop before any work.
if [ "${CLAUDE_LEVERAGE_CTX_DISABLE:-0}" = "1" ]; then
  exit 0
fi

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

has_parser || exit 0

# canon_path: normalize a path so paths from different sources (tool_input
# .file_path, git rev-parse, cygpath, raw env vars) compare equal. Same
# logic as scripts/hooks/ai-first-nudge.sh — duplicated to keep this hook
# self-contained; promote to json_parse.sh if a third hook needs it.
canon_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m -- "$p" 2>/dev/null && return
  fi
  local PY
  PY=$(command -v python3 || command -v python || true)
  if [ -n "$PY" ]; then
    printf '%s' "$p" | "$PY" -c '
import os, sys
print(os.path.abspath(sys.stdin.read()).replace("\\", "/"), end="")
' 2>/dev/null && return
  fi
  printf '%s' "$p"
}

read_stdin

# Filter by tool name early — case-statement is essentially free vs the
# regex matchers configured upstream in hooks.json.
tool=$(get_field '.tool_name' 2>/dev/null) || exit 0
case "$tool" in
  Read|Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

# Resolve repo root from cwd (hook input) or pwd fallback.
cwd_hook=$(get_field '.cwd' 2>/dev/null)
[ -n "$cwd_hook" ] || cwd_hook=$(pwd 2>/dev/null) || exit 0
repo_root=$(git -C "$cwd_hook" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$repo_root" ] || exit 0

manifest="$repo_root/.claude-leverage-context-map.json"
[ -f "$manifest" ] || exit 0

# Extract + canonicalize file_path. canon_path handles backslash, drive-
# letter case, and relative → absolute.
file_raw=$(get_field '.tool_input.file_path' 2>/dev/null)
[ -n "$file_raw" ] || exit 0

file_canon=$(canon_path "$file_raw")
repo_canon=$(canon_path "$repo_root")

# Make file path relative to repo_root for manifest lookup. If file is
# outside the repo, manifest lookup will miss and we exit silently.
case "$file_canon" in
  "$repo_canon"/*) file_rel=${file_canon#"$repo_canon"/} ;;
  *)               file_rel="$file_canon" ;;
esac

# Locate python interpreter for the lookup heredoc.
python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
fi
[ -n "$python_bin" ] || exit 0

MAX_CHARS="${CLAUDE_LEVERAGE_CTX_MAX_CHARS:-4096}"
MAX_SIBLINGS="${CLAUDE_LEVERAGE_CTX_MAX_SIBLINGS:-5}"
VERBOSE="${CLAUDE_LEVERAGE_CTX_VERBOSE:-0}"

# Single Python subprocess does manifest load + lookup + formatting +
# JSON encoding. Two subprocesses cost ~300-500ms p99 on Windows Python
# cold-start; merging halves the budget.
MANIFEST_PATH="$manifest" FILE_REL="$file_rel" \
  MAX_CHARS="$MAX_CHARS" MAX_SIBLINGS="$MAX_SIBLINGS" \
  VERBOSE="$VERBOSE" \
  "$python_bin" - <<'PY'
import json, os, sys

manifest_path = os.environ["MANIFEST_PATH"]
file_rel = os.environ["FILE_REL"]
max_chars = int(os.environ.get("MAX_CHARS", "4096"))
max_siblings = int(os.environ.get("MAX_SIBLINGS", "5"))
verbose = os.environ.get("VERBOSE", "0") not in ("", "0", "false", "False")

try:
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)

# Schema-version gate: if the manifest was built by a future schema, skip
# rather than risk misreading it. Treat missing schema_version as "1" for
# backward compat with the first release.
meta = manifest.get("_meta", {})
schema = meta.get("schema_version", 1)
if schema != 1:
    sys.exit(0)

entry = manifest.get("files", {}).get(file_rel)
if not entry:
    sys.exit(0)

parts = ["[claude-leverage:context-surface]"]

anchors_in_file = entry.get("anchors_in_file") or []
if anchors_in_file:
    parts.append(f"AIDEV anchors in {file_rel}:")
    for a in anchors_in_file:
        kind = a.get("type", "AIDEV-NOTE").replace("AIDEV-", "")
        deadline = f"(by:{a['deadline']})" if a.get("deadline") else ""
        parts.append(f"  L{a['line']} {kind}{deadline}: {a.get('text','')}")

anchors_in_dir = entry.get("anchors_in_dir") or []
if anchors_in_dir:
    parts.append("")
    parts.append("Anchors in same directory:")
    shown = anchors_in_dir[:max_siblings]
    for a in shown:
        kind = a.get("type", "AIDEV-NOTE").replace("AIDEV-", "")
        parts.append(f"  {a.get('file','?')}:{a.get('line','?')} {kind}: {a.get('text','')}")
    if len(anchors_in_dir) > max_siblings:
        parts.append(f"  (+{len(anchors_in_dir) - max_siblings} more — see manifest)")

# AGENTS.md and ADR refs gated behind VERBOSE because Run-3 showed that
# even surfacing "see X" is wasted tax when the task has no specific
# trap. The anchor sections above carry the load-bearing trap-catch
# value; refs are supplementary.
if verbose:
    agents_md = entry.get("agents_md") or []
    if agents_md:
        parts.append("")
        parts.append("For project conventions, see (Read on demand):")
        parts.append(f"  {', '.join(agents_md)}")

    adrs = entry.get("adrs") or []
    if adrs:
        parts.append("")
        parts.append("Related ADRs:")
        for a in adrs:
            parts.append(f"  {a}")

# If only the marker line is present (no actual content), suppress entirely.
if len(parts) <= 1:
    sys.exit(0)

out = "\n".join(parts)
if len(out) > max_chars:
    out = out[: max_chars - 50].rstrip() + f"\n... (truncated; cap={max_chars})"

# Emit the full hookSpecificOutput JSON in the same process.
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": out,
    }
}))
PY
exit 0
