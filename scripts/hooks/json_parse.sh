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

# has_parser: returns 0 if any supported JSON parser is on PATH, 1 otherwise.
has_parser() {
  command -v jq >/dev/null 2>&1 && return 0
  command -v python3 >/dev/null 2>&1 && return 0
  command -v python >/dev/null 2>&1 && return 0
  return 1
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
# terminal escape attacks. See track-delegations.sh for an example.
get_field() {
  local query="$1"
  local result=""

  if command -v jq >/dev/null 2>&1; then
    result=$(printf '%s' "$JSON_INPUT" | jq -r "${query} // empty" 2>/dev/null) || result=""
    printf '%s\n' "$result"
    return 0
  fi

  local python_bin=""
  if command -v python3 >/dev/null 2>&1; then
    python_bin="python3"
  elif command -v python >/dev/null 2>&1; then
    python_bin="python"
  fi

  if [ -n "$python_bin" ]; then
    # Pass query via env var, single-quoted Python script (no shell interpolation
    # inside the script body). Defensive against malformed JSON, missing keys,
    # non-dict intermediates, and non-string leaf values.
    result=$(printf '%s' "$JSON_INPUT" | JSON_PATH="$query" "$python_bin" -c '
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
