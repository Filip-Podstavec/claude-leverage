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

# Debug logging — set CLAUDE_LEVERAGE_CTX_DEBUG_LOG=/path/to/log to record
# every invocation's outcome (always-invoked vs each early-exit reason).
# Tag {invoked|opt-out|no-parser|wrong-tool|no-cwd|no-repo|no-manifest|no-file-path|no-python|no-entry|emit}.
# Diagnostic-only; do not enable in production sessions long-term.
DEBUG_LOG="${CLAUDE_LEVERAGE_CTX_DEBUG_LOG:-}"
log_dbg() {
  [ -n "$DEBUG_LOG" ] && printf '[%s] %s\n' "$(date -Iseconds 2>/dev/null || date +%s)" "$*" >> "$DEBUG_LOG" 2>/dev/null
  return 0
}
log_dbg "invoked pid=$$"

# Opt-out kill switch — hard-stop before any work.
if [ "${CLAUDE_LEVERAGE_CTX_DISABLE:-0}" = "1" ]; then
  log_dbg "exit: opt-out via CLAUDE_LEVERAGE_CTX_DISABLE=1"
  exit 0
fi

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

if ! has_parser; then
  log_dbg "exit: no JSON parser on PATH (need jq, python3, or python)"
  exit 0
fi

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
    # AIDEV-NOTE: convert backslashes BEFORE abspath so that Windows-style
    # paths (e.g. \tmp\foo or C:\Users\…) sent to a Linux interpreter — as
    # happens in CI when the regression test simulates a Windows path on
    # the Linux runner — are recognized as absolute, not relative. Without
    # the early replace, abspath prepends cwd, the result no longer
    # matches repo_root, and the manifest lookup silently misses.
    printf '%s' "$p" | "$PY" -c '
import os, sys
text = sys.stdin.read().replace("\\", "/")
print(os.path.abspath(text).replace("\\", "/"), end="")
' 2>/dev/null && return
  fi
  printf '%s' "$p"
}

read_stdin

# Filter by tool name early — case-statement is essentially free vs the
# regex matchers configured upstream in hooks.json.
tool=$(get_field '.tool_name' 2>/dev/null) || { log_dbg "exit: get_field tool_name failed"; exit 0; }
case "$tool" in
  Read|Edit|Write|MultiEdit) log_dbg "tool=$tool — matched, continuing" ;;
  *) log_dbg "exit: tool=$tool — not in Read|Edit|Write|MultiEdit"; exit 0 ;;
esac

# Resolve repo root from cwd (hook input) or pwd fallback.
cwd_hook=$(get_field '.cwd' 2>/dev/null)
[ -n "$cwd_hook" ] || cwd_hook=$(pwd 2>/dev/null) || { log_dbg "exit: cannot determine cwd"; exit 0; }
log_dbg "cwd=$cwd_hook"
repo_root=$(git -C "$cwd_hook" rev-parse --show-toplevel 2>/dev/null) || { log_dbg "exit: git rev-parse failed (cwd=$cwd_hook not in a git repo, or git not on PATH)"; exit 0; }
[ -n "$repo_root" ] || { log_dbg "exit: repo_root empty"; exit 0; }
log_dbg "repo_root=$repo_root"

manifest="$repo_root/.claude-leverage-context-map.json"
if [ ! -f "$manifest" ]; then
  log_dbg "exit: manifest missing at $manifest"
  exit 0
fi
log_dbg "manifest=$manifest"

# Extract + canonicalize file_path. canon_path handles backslash, drive-
# letter case, and relative → absolute.
file_raw=$(get_field '.tool_input.file_path' 2>/dev/null)
if [ -z "$file_raw" ]; then
  log_dbg "exit: tool_input.file_path empty (tool=$tool — unexpected for Read/Edit/Write/MultiEdit)"
  exit 0
fi
log_dbg "file_raw=$file_raw"

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
if [ -z "$python_bin" ]; then
  log_dbg "exit: no python on PATH"
  exit 0
fi
log_dbg "python_bin=$python_bin file_rel=$file_rel"

MAX_CHARS="${CLAUDE_LEVERAGE_CTX_MAX_CHARS:-4096}"
MAX_SIBLINGS="${CLAUDE_LEVERAGE_CTX_MAX_SIBLINGS:-5}"
VERBOSE="${CLAUDE_LEVERAGE_CTX_VERBOSE:-0}"

# Single Python subprocess does manifest load + lookup + formatting +
# JSON encoding. Two subprocesses cost ~300-500ms p99 on Windows Python
# cold-start; merging halves the budget.
#
# When debug logging is active, capture the output FIRST so we can log
# its length/preview, then emit on stdout. Without debug, stream directly
# to stdout to avoid the bash-variable-roundtrip overhead.
if [ -n "$DEBUG_LOG" ]; then
  ctx_out=$(MANIFEST_PATH="$manifest" FILE_REL="$file_rel" \
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
except (OSError, json.JSONDecodeError) as e:
    sys.stderr.write(f"[ctx-py] manifest load failed: {e!r}\n")
    sys.exit(0)

meta = manifest.get("_meta", {})
schema = meta.get("schema_version", 1)
if schema != 1:
    sys.stderr.write(f"[ctx-py] schema mismatch: schema={schema}\n")
    sys.exit(0)

conv = (manifest.get("_meta", {}) or {}).get("conventions")

entry = manifest.get("files", {}).get(file_rel)
if not entry:
    sys.stderr.write(f"[ctx-py] file_rel not in manifest.files (file_rel={file_rel!r}, n_files={len(manifest.get('files',{}))})\n")

parts = ["[claude-leverage:context-surface]"]
if entry:
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

SRC_EXTS = {".py"}
ext = os.path.splitext(file_rel)[1].lower()
if conv and ext in SRC_EXTS:
    cparts = ["", "Conventions (this repo):"]
    casing = conv.get("casing") or {}
    if casing:
        cparts.append("  casing: " + " ".join(f"{k}={v}" for k, v in casing.items()))
    deny = conv.get("vague_denylist") or []
    if deny:
        cparts.append("  avoid vague names: " + ", ".join(deny[:8]))
    rules = conv.get("consistency") or []
    if rules:
        cparts.append("  house rules: " + "; ".join(rules[:4]))
    roots = conv.get("structure_roots") or {}
    best = None
    for k in roots:
        if file_rel.startswith(k) and (best is None or len(k) > len(best)):
            best = k
    if best is not None:
        cparts.append(f"  this dir: {roots[best]}")
    if len(cparts) > 2:
        parts.extend(cparts)

if len(parts) <= 1:
    sys.stderr.write("[ctx-py] all-empty entry, suppressing\n")
    sys.exit(0)

out = "\n".join(parts)
if len(out) > max_chars:
    if "Conventions (this repo):" in out:
        out = out[: max_chars - 50].rstrip() + f"\n... (conventions truncated; cap={max_chars})"
    else:
        out = out[: max_chars - 50].rstrip() + f"\n... (truncated; cap={max_chars})"

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": out,
    }
}))
sys.stderr.write(f"[ctx-py] emitted {len(out)} chars of additionalContext\n")
PY
    )
  ctx_exit=$?
  log_dbg "python exit=$ctx_exit output_len=${#ctx_out}"
  if [ -n "$ctx_out" ]; then
    log_dbg "python stdout preview: $(printf '%s' "$ctx_out" | tr '\n' '|' | head -c 300)"
    printf '%s\n' "$ctx_out"
  else
    log_dbg "python stdout was EMPTY (Python took a silent sys.exit(0) branch — see stderr if captured)"
  fi
  log_dbg "script end reached"
  exit 0
fi

# Production path (no debug logging) — stream directly, no variable capture.
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

conv = (manifest.get("_meta", {}) or {}).get("conventions")

entry = manifest.get("files", {}).get(file_rel)

parts = ["[claude-leverage:context-surface]"]

if entry:
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

SRC_EXTS = {".py"}
ext = os.path.splitext(file_rel)[1].lower()
if conv and ext in SRC_EXTS:
    cparts = ["", "Conventions (this repo):"]
    casing = conv.get("casing") or {}
    if casing:
        cparts.append("  casing: " + " ".join(f"{k}={v}" for k, v in casing.items()))
    deny = conv.get("vague_denylist") or []
    if deny:
        cparts.append("  avoid vague names: " + ", ".join(deny[:8]))
    rules = conv.get("consistency") or []
    if rules:
        cparts.append("  house rules: " + "; ".join(rules[:4]))
    roots = conv.get("structure_roots") or {}
    best = None
    for k in roots:
        if file_rel.startswith(k) and (best is None or len(k) > len(best)):
            best = k
    if best is not None:
        cparts.append(f"  this dir: {roots[best]}")
    if len(cparts) > 2:
        parts.extend(cparts)

# If only the marker line is present (no actual content), suppress entirely.
if len(parts) <= 1:
    sys.exit(0)

out = "\n".join(parts)
if len(out) > max_chars:
    if "Conventions (this repo):" in out:
        out = out[: max_chars - 50].rstrip() + f"\n... (conventions truncated; cap={max_chars})"
    else:
        out = out[: max_chars - 50].rstrip() + f"\n... (truncated; cap={max_chars})"

# Emit the full hookSpecificOutput JSON in the same process. The debug
# log line on the bash side after the heredoc records whether anything
# was actually emitted (Python's exit-0-with-no-output for "no entry"
# vs exit-0-with-JSON for "emitted").
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": out,
    }
}))
PY
# Note: bash here cannot easily know if Python printed anything (we don't
# capture stdout — Claude Code reads it directly). The log line below is
# best-effort: it records that we reached the end of the script. The
# distinction between "Python found an entry and emitted" vs "Python
# silently sys.exit(0) on no-entry / corrupt manifest" lives inside the
# heredoc and is not surfaced here.
log_dbg "script end reached (Python heredoc completed without bash error)"
exit 0
