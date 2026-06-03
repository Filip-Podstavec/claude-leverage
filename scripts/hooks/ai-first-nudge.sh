#!/usr/bin/env bash
# ai-first-nudge.sh
#
# Claude Code / Codex PostToolUse hook (Write|Edit|MultiEdit matcher).
#
# Two independent, non-blocking nudges:
#
#   1. AIDEV-NOTE anchor missing — when >=50 net-new LOC ship in a single
#      non-test file without any AIDEV-* anchor in the change.
#      Frequency cap: one nudge per file per day.
#
#   2. Per-directory AGENTS.md missing — when a file lands inside a
#      detected source root (src/, lib/, app/, apps/, pkg/, internal/,
#      services/, api/, cmd/, crates/, packages/, including monorepo-
#      nested variants) AND the parent dir has 8+ source files AND no
#      AGENTS.md is present in the parent or any ancestor up to the
#      repo root. Frequency cap: one nudge per directory per day. Only
#      fires inside a git repo (so /tmp scratch dirs don't trip it).
#
# Never blocks (always exits 0). State files in
# $XDG_STATE_HOME/claude-leverage/ (or $HOME/.claude/claude-leverage/
# as fallback). Override the LOC threshold with CLAUDE_LEVERAGE_NUDGE_LOC,
# the per-dir file-count threshold with CLAUDE_LEVERAGE_DIR_AGENTS_MIN.
#
# Hook protocol:
#   - Receives JSON on stdin with tool_name + tool_input/tool_response
#   - Exit 0 always; messages go to stderr

set -euo pipefail

# AIDEV-NOTE: this hook never modifies state besides the session-nudges
# file. Keep it that way — a PostToolUse that mutates user files would be
# surprising and dangerous.

# Source the shared JSON parser helper from the same dir.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

# Without any JSON parser, silently skip (do not nag with parser warnings
# on every Write — security hooks already cover that case).
if ! has_parser; then
  exit 0
fi

# Tunables.
THRESHOLD_LOC="${CLAUDE_LEVERAGE_NUDGE_LOC:-50}"
DIR_AGENTS_MIN="${CLAUDE_LEVERAGE_DIR_AGENTS_MIN:-8}"

# State dir (file-level + dir-level nudge caps live here).
NUDGE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || NUDGE_DIR="$HOME/.claude/claude-leverage"
[ -d "$NUDGE_DIR" ] || mkdir -p "$NUDGE_DIR" 2>/dev/null || exit 0
TODAY=$(date +%Y%m%d 2>/dev/null || printf '00000000')
FILE_NUDGE_FILE="$NUDGE_DIR/session-nudges-$TODAY.txt"
DIR_NUDGE_FILE="$NUDGE_DIR/dir-agents-nudges-$TODAY.txt"
CONV_NUDGE_FILE="$NUDGE_DIR/conv-nudges-$TODAY.txt"
touch "$FILE_NUDGE_FILE" "$DIR_NUDGE_FILE" "$CONV_NUDGE_FILE" 2>/dev/null || exit 0

# Read hook input from stdin and pull the tool + file path.
read_stdin
tool=$(get_field '.tool_name') || exit 0
case "$tool" in
  Write|Edit|MultiEdit) ;;
  *) exit 0 ;;
esac

file_path=$(get_field '.tool_input.file_path' 2>/dev/null) || true
[ -z "${file_path:-}" ] && file_path=$(get_field '.tool_input.path' 2>/dev/null) || true
[ -z "${file_path:-}" ] && exit 0

# Ignore patterns: tests, fixtures, generated code, dotfiles, archive.
# Applied to BOTH nudges — these paths are noise for both checks.
#
# AIDEV-NOTE: split into basename-only vs path patterns so a directory
# named e.g. slevomat_test_api/ does not silently swallow nudges for
# production code inside it (v1.4.0 field-feedback #1). Also normalize
# Windows backslashes before path matching so paths Claude Code sends
# in C:\…\node_modules\… form still hit the ignore list (#2).
fp_norm=${file_path//\\//}
fp_base=${fp_norm##*/}
case "$fp_base" in
  test_*.py|*_test.py|*_test.go|*_test.ts|*_test.tsx|*_test.js|*_test.jsx) exit 0 ;;
  *.test.ts|*.test.tsx|*.test.js|*.test.jsx|*.spec.ts|*.spec.js) exit 0 ;;
  *.lock|*.lockb|*.snap) exit 0 ;;
esac
case "$fp_norm" in
  */tests/*|*/test/*|*/__tests__/*|*/fixtures/*|*/__pycache__/*) exit 0 ;;
  */node_modules/*|*/.git/*|*/dist/*|*/build/*|*/.next/*|*/target/*|*/vendor/*) exit 0 ;;
  */bench/archive-token-savings-thesis/*) exit 0 ;;
esac

# Helper: count non-blank lines in a string.
count_non_blank() {
  local body="$1"
  local n
  n=$(printf '%s\n' "$body" | grep -cv '^[[:space:]]*$' 2>/dev/null || printf '0')
  case "$n" in ''|*[!0-9]*) printf '0' ;; *) printf '%s' "$n" ;; esac
}

# Helper: canonicalize a path so paths from different sources can be compared.
# Git Bash on Windows has three flavors that don't string-compare equal:
#   /tmp/foo            (MSYS mount)
#   /c/Users/.../foo    (drive-prefix)
#   C:/Users/.../foo    (native, with forward slashes)
# `cygpath -m` translates all of them to the native-with-forward-slashes
# form, which is what `git rev-parse --show-toplevel` returns. On non-Git-Bash
# systems the paths are already canonical; fall back to Python abspath.
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

# ----------------------------------------------------------------------
# Check 1: per-directory AGENTS.md (runs independently of LOC threshold)
# ----------------------------------------------------------------------
#
# Only fires inside a git repo + recognized source root, so /tmp scratch
# work doesn't trip it. The earlier removal of this check was because the
# original version fired on any dir with 3+ files anywhere — including
# /tmp. This version is scoped to "actual project source dirs growing
# past the in-AGENTS.md threshold."

per_dir_agents_md_nudge() {
  local parent_dir
  parent_dir=$(dirname "$file_path")

  # Must be inside a git repo. `cd "$parent_dir"` only works if the path
  # exists — for fresh Write of a new file in a new dir, parent_dir may
  # not exist yet. Use git -C with the deepest existing ancestor.
  local probe="$parent_dir"
  while [ ! -d "$probe" ] && [ "$probe" != "/" ] && [ "$probe" != "." ]; do
    probe=$(dirname "$probe")
  done
  [ -d "$probe" ] || return 0

  local repo_root
  repo_root=$(git -C "$probe" rev-parse --show-toplevel 2>/dev/null) || return 0
  [ -z "$repo_root" ] && return 0

  # Canonicalize both sides — they may come in different path forms on
  # Git Bash on Windows (MSYS mount vs native), and would otherwise fail
  # the prefix-match below despite pointing at the same location.
  local fp_canon rr_canon
  fp_canon=$(canon_path "$file_path")
  rr_canon=$(canon_path "$repo_root")

  case "$fp_canon" in
    "$rr_canon"/*) ;;
    *) return 0 ;;  # file not under any known repo root (e.g. an absolute path elsewhere)
  esac
  local rel_path=${fp_canon#"$rr_canon"/}

  # Must be under a recognized source root. First-level OR nested in a
  # monorepo (`apps/web/src/foo.ts` should fire; `docs/foo.md` should not).
  case "$rel_path" in
    src/*|lib/*|app/*|apps/*|pkg/*|internal/*|services/*|api/*|cmd/*|crates/*|packages/*) ;;
    */src/*|*/lib/*|*/app/*|*/apps/*|*/pkg/*|*/internal/*|*/services/*|*/api/*|*/cmd/*|*/crates/*|*/packages/*) ;;
    *) return 0 ;;
  esac

  # Per-dir frequency cap. Canonicalize the dir before grep + append so
  # the same dir in different path forms (Git Bash mount vs native)
  # doesn't double-nudge or accumulate duplicate cap entries.
  local parent_canon
  parent_canon=$(canon_path "$parent_dir")
  if grep -Fxq "$parent_canon" "$DIR_NUDGE_FILE" 2>/dev/null; then
    return 0
  fi

  # Walk parent → repo_root looking for an AGENTS.md. Codex merges
  # nested AGENTS.md from the cwd up to git root; if any ancestor has
  # one, the convention is satisfied for this file.
  local d="$parent_dir"
  while :; do
    [ -f "$d/AGENTS.md" ] && return 0
    [ "$d" = "$repo_root" ] && break
    local parent
    parent=$(dirname "$d")
    [ "$parent" = "$d" ] && break  # hit / safely
    d="$parent"
  done

  # Parent dir must exist and have a meaningful number of source files
  # before we suggest an AGENTS.md. Brand-new dir with one file is
  # premature; established dir with 8+ siblings is the right moment.
  [ -d "$parent_dir" ] || return 0
  local file_count
  file_count=$(find "$parent_dir" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')
  case "$file_count" in ''|*[!0-9]*) file_count=0 ;; esac
  [ "$file_count" -lt "$DIR_AGENTS_MIN" ] && return 0

  local short_path
  short_path=$(printf '%s' "$parent_dir" | sed "s|^$HOME|~|")
  printf '(claude-leverage: %s has %s source files but no AGENTS.md anywhere up to repo root — as the module grows, an AGENTS.md helps next agents orient)\n' \
    "$short_path" "$file_count" >&2

  printf '%s\n' "$parent_canon" >> "$DIR_NUDGE_FILE" 2>/dev/null || true
}

convention_violation_nudge() {
  case "$file_path" in *.py) ;; *) return 0 ;; esac

  local parent probe repo_root
  parent=$(dirname "$file_path")
  probe="$parent"
  while [ ! -d "$probe" ] && [ "$probe" != "/" ] && [ "$probe" != "." ]; do
    probe=$(dirname "$probe")
  done
  [ -d "$probe" ] || return 0
  repo_root=$(git -C "$probe" rev-parse --show-toplevel 2>/dev/null) || return 0
  [ -n "$repo_root" ] || return 0
  [ -f "$repo_root/conventions.yml" ] || return 0

  local py_bin
  py_bin=$(command -v python3 || command -v python || true)
  [ -n "$py_bin" ] || return 0

  local blob=""
  case "$tool" in
    Write) blob=$(get_field '.tool_input.content' 2>/dev/null || true) ;;
    Edit)  blob=$(get_field '.tool_input.new_string' 2>/dev/null || true) ;;
    MultiEdit)
      blob=$(printf '%s' "$JSON_INPUT" | "$py_bin" -c '
import json, sys
try:
    d = json.load(sys.stdin)
    e = (d.get("tool_input", {}) or {}).get("edits", []) or []
    print("\n".join(x.get("new_string", "") for x in e if isinstance(x, dict)))
except Exception:
    pass' 2>/dev/null || true) ;;
  esac
  [ -n "$blob" ] || return 0

  if grep -Fxq "$file_path" "$CONV_NUDGE_FILE" 2>/dev/null; then
    return 0
  fi

  local scripts_dir names
  scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
  # AIDEV-NOTE: blob is passed via BLOB_DATA env var, not stdin, because
  # `printf ... | python - <<'PY'` is ambiguous: bash resolves the heredoc as
  # the script source and the pipe as stdin, but Python then reads stdin as
  # empty. Env var sidesteps the conflict cleanly.
  names=$(SCRIPTS_DIR="$scripts_dir" CONV_PATH="$repo_root/conventions.yml" BLOB_DATA="$blob" \
    "$py_bin" - <<'PY' 2>/dev/null || true
import os, sys
sys.path.insert(0, os.environ["SCRIPTS_DIR"])
try:
    from conventions import parse_conventions
    from score_adherence import flag_blob_violations
except Exception:
    sys.exit(0)
try:
    text = open(os.environ["CONV_PATH"], encoding="utf-8", errors="replace").read()
except OSError:
    sys.exit(0)
prof = parse_conventions(text) or {}
flags = flag_blob_violations(os.environ.get("BLOB_DATA", ""), casing=prof.get("casing"), denylist=prof.get("vague_denylist"))
names = sorted({f["name"] for f in flags})
if names:
    print(",".join(names))
PY
)
  [ -n "$names" ] || return 0

  local short_path
  short_path=$(printf '%s' "$file_path" | sed "s|^$HOME|~|")
  printf '(claude-leverage: %s introduces names that drift from conventions.yml — %s; prefer intent-revealing, repo-cased names)\n' \
    "$short_path" "$names" >&2
  printf '%s\n' "$file_path" >> "$CONV_NUDGE_FILE" 2>/dev/null || true
}

per_dir_agents_md_nudge
convention_violation_nudge

# ----------------------------------------------------------------------
# Check 2: missing AIDEV-NOTE on large diffs (original logic)
# ----------------------------------------------------------------------
#
# Independent of Check 1 — both can fire (rare) or neither.

# Count added LOC per tool type.
added_loc=0
case "$tool" in
  Write)
    content=$(get_field '.tool_input.content' 2>/dev/null) || content=""
    added_loc=$(count_non_blank "$content")
    ;;
  Edit)
    new_string=$(get_field '.tool_input.new_string' 2>/dev/null) || new_string=""
    added_loc=$(count_non_blank "$new_string")
    ;;
  MultiEdit)
    # Sum non-blank lines across edits[*].new_string via Python (the JSON
    # blob shape needs proper array walking; the older regex-on-blob
    # approach over-counted JSON syntax and triggered spurious nudges).
    PY_BIN=$(command -v python3 || command -v python || true)
    if [ -n "$PY_BIN" ]; then
      added_loc=$(printf '%s' "$JSON_INPUT" | "$PY_BIN" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    edits = (data.get("tool_input", {}) or {}).get("edits", []) or []
    n = 0
    for e in edits:
        if isinstance(e, dict):
            s = e.get("new_string", "")
            if isinstance(s, str):
                n += sum(1 for ln in s.splitlines() if ln.strip())
    print(n)
except Exception:
    print(0)
' 2>/dev/null || printf '0')
      case "$added_loc" in ''|*[!0-9]*) added_loc=0 ;; esac
    else
      added_loc=0
    fi
    ;;
esac

if [ "$added_loc" -lt "$THRESHOLD_LOC" ]; then
  exit 0
fi

# Per-file frequency cap.
if grep -Fxq "$file_path" "$FILE_NUDGE_FILE" 2>/dev/null; then
  exit 0
fi

# Check whether the new content contains an AIDEV-* anchor.
blob=""
case "$tool" in
  Write)     blob=$(get_field '.tool_input.content' 2>/dev/null || true) ;;
  Edit)      blob=$(get_field '.tool_input.new_string' 2>/dev/null || true) ;;
  MultiEdit) blob=$(get_field '.tool_input.edits' 2>/dev/null || true) ;;
esac

if printf '%s' "$blob" | grep -q 'AIDEV-' ; then
  exit 0
fi

short_path=$(printf '%s' "$file_path" | sed "s|^$HOME|~|")
printf '(claude-leverage: %s LOC of net-new code in %s with no AIDEV-NOTE anchor — consider anchoring load-bearing parts)\n' \
  "$added_loc" "$short_path" >&2

printf '%s\n' "$file_path" >> "$FILE_NUDGE_FILE" 2>/dev/null || true
exit 0
