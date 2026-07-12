#!/usr/bin/env bash
# json_parse.sh
#
# Shared JSON-parsing helper for claude-leverage hooks.
# Provides a fallback chain so users do not need to install jq specifically.
#
# Parser preference: jq -> python3 / python -> return 1 (caller decides fail-open vs fail-closed).
#
# Usage:
#
#   . "$(dirname "${BASH_SOURCE[0]}")/json_parse.sh"
#
#   if ! has_parser; then
#     # warn and decide: fail-open or fail-closed
#     exit 0
#   fi
#
#   read_stdin
#   value=$(get_field '.tool_input.command')
#
# This file is meant to be sourced, not executed. It captures stdin into
# JSON_INPUT once via read_stdin, then get_field can be called repeatedly
# to extract dotted-path values.

# JSON_INPUT holds the raw JSON received on stdin once read_stdin has been
# called. Initialized to empty string so that sourcing this file in a hook
# running under `set -u` (nounset) does not abort if a future caller forgets
# to call read_stdin before get_field.
JSON_INPUT=""

# Capture stdin into JSON_INPUT. Call once per hook invocation.
# Strips CR characters defensively: on Git Bash on Windows, Claude Code may
# deliver hook input with CRLF line endings, which would otherwise leave
# trailing \r characters embedded in extracted JSON string values, causing
# silent string-comparison failures (e.g. "code-reviewer\r" not matching
# the "code-reviewer" case pattern).
read_stdin() {
  JSON_INPUT=$(cat | tr -d '\r')
}

# Parser selection is memoized across a single sourced hook invocation:
# _CL_PARSER_KIND is "jq" | "python" | "" (none), _CL_PYTHON_BIN names the
# working interpreter when kind is "python".
_CL_PARSER_KIND=""
_CL_PYTHON_BIN=""
_CL_PARSER_DONE=""
_CL_PY_DONE=""
_CL_PY_BIN=""

# _cl_probe_python <bin>: 0 iff <bin> actually EXECUTES a trivial json script
# and emits the expected stdout — not merely that it exists on PATH.
#
# AIDEV-NOTE: presence != working. On Windows, `python3` is by default the
# Microsoft Store app-execution-alias stub: it's on PATH, but exits non-zero
# and prints nothing (a store-install prompt to stderr), while the real
# interpreter is `python`. A bare `command -v python3` check picks the stub,
# every get_field returns empty, and the SECURITY hooks silently fail open.
# Probe execution to avoid that whole class of Windows fail-open.
_cl_probe_python() {
  local out
  out=$(printf '{}' | "$1" -c 'import json,sys; json.load(sys.stdin); sys.stdout.write("ok")' 2>/dev/null) || out=""
  [ "$out" = "ok" ]
}

# cl_python_bin: echo a WORKING python interpreter name (probed), or nothing.
# Public helper for hook code that needs python for tasks OTHER than JSON
# parsing — path canonicalization, quote stripping, LOC counting. Memoized.
#
# AIDEV-NOTE: independent of _cl_select_parser's jq-first choice — a hook may
# use jq for get_field yet still need a real python here, and BOTH must skip
# the non-functional Windows `python3` Store stub (see _cl_probe_python). Every
# hook that needs python must go through this, not a bare `command -v python3`,
# or it fails open on that common Windows config.
cl_python_bin() {
  if [ -z "$_CL_PY_DONE" ]; then
    _CL_PY_DONE=1
    local bin
    for bin in python3 python; do
      if command -v "$bin" >/dev/null 2>&1 && _cl_probe_python "$bin"; then
        _CL_PY_BIN="$bin"
        break
      fi
    done
  fi
  printf '%s' "$_CL_PY_BIN"
}

# _cl_select_parser: run once, cache the first WORKING parser. jq preferred,
# then a probed python (via cl_python_bin) — each candidate is probed, not
# assumed present-means-working.
_cl_select_parser() {
  [ -n "$_CL_PARSER_DONE" ] && return 0
  _CL_PARSER_DONE=1

  if command -v jq >/dev/null 2>&1 && printf '{}' | jq -e . >/dev/null 2>&1; then
    _CL_PARSER_KIND="jq"
    return 0
  fi

  local pb
  pb=$(cl_python_bin)
  if [ -n "$pb" ]; then
    _CL_PARSER_KIND="python"
    _CL_PYTHON_BIN="$pb"
  fi
  return 0
}

# has_parser: returns 0 if a WORKING JSON parser is available, 1 otherwise.
has_parser() {
  _cl_select_parser
  [ -n "$_CL_PARSER_KIND" ]
}

# get_field <dotted-path>
#
# Extracts a string value from JSON_INPUT at the given dotted path
# (e.g. '.tool_input.command'). Echoes the value or empty string.
# Always returns 0 when a parser is available, 1 if no parser is on PATH.
#
# Security note 1 (Python injection): the dotted path is passed via environment
# variable to the Python interpreter (not interpolated into the script body)
# so that even untrusted callers cannot inject Python code. The shell-level
# interpolation into jq's query string is safe because callers only pass
# static literal paths from this codebase, never user-controlled input.
#
# Security note 2 (output sanitization): returned values are NOT sanitized.
# The string may contain newlines, NUL bytes, or terminal escape sequences
# if the source JSON contains them. Callers that write the value to logs,
# terminals, or shell-interpolate it MUST strip control characters themselves
# (e.g. `tr -d '\000-\037\177'`) to prevent log injection (CWE-116) or
# terminal escape attacks. See ai-first-nudge.sh and security-nudge.sh for
# examples of how the hooks in this repo sanitize before emitting output.
get_field() {
  local query="$1"
  local result=""

  _cl_select_parser

  if [ "$_CL_PARSER_KIND" = "jq" ]; then
    result=$(printf '%s' "$JSON_INPUT" | jq -r "${query} // empty" 2>/dev/null) || result=""
    printf '%s\n' "$result"
    return 0
  fi

  if [ "$_CL_PARSER_KIND" = "python" ]; then
    # Pass query via env var, single-quoted Python script (no shell interpolation
    # inside the script body). Defensive against malformed JSON, missing keys,
    # non-dict intermediates, and non-string leaf values.
    result=$(printf '%s' "$JSON_INPUT" | JSON_PATH="$query" "$_CL_PYTHON_BIN" -c '
import json, os, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
parts = [p for p in os.environ.get("JSON_PATH", "").lstrip(".").split(".") if p]
v = data
for p in parts:
    if isinstance(v, dict):
        v = v.get(p)
    else:
        v = None
        break
# Mirror jq -r "// empty" semantics exactly: only null and false are
# suppressed; numeric 0 IS emitted as "0" (jq behavior). True is emitted
# as lowercase "true" to match jq -r (Python would otherwise print "True").
# Empty string is also suppressed, so callers can distinguish "field
# present with empty value" from "field has data" - same as jq.
if v is None or v is False:
    pass
elif isinstance(v, bool):
    print("true")
elif isinstance(v, str):
    if v != "":
        print(v)
else:
    # Numbers (int, float) including 0, lists, dicts. Coerce to str.
    print(str(v))
' 2>/dev/null) || result=""
    printf '%s\n' "$result"
    return 0
  fi

  return 1
}
