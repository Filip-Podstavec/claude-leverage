#!/usr/bin/env bash
# block-dangerous-git.sh
#
# Claude Code PreToolUse hook (Bash matcher).
# Blocks dangerous git operations: force push, --no-verify, hard reset on
# protected branches, and warns on force branch delete.
#
# Hook protocol:
#   - Receives JSON on stdin with tool_input.command
#   - Exit 0: allow the tool call
#   - Exit 2: block the tool call (stderr message shown to user)
#
# Install: register in ~/.claude/settings.json under hooks.PreToolUse
# Dependencies: jq OR python (3 or 2). Either is sufficient. See json_parse.sh.

set -euo pipefail

# Source shared parser helper.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

# Without any JSON parser we cannot inspect the command. Fail-open with a
# loud warning rather than blocking every Bash call. Documented limitation.
if ! has_parser; then
  cat >&2 <<'EOF'
[block-dangerous-git] WARNING: no JSON parser available - this hook is DISABLED.
Install one of:
  jq:     brew install jq | sudo apt install jq | winget install jqlang.jq
  python: usually preinstalled on macOS/Linux; Windows: python.org or Microsoft Store
Until then, force push, --no-verify, and hard-reset detection are inactive.
EOF
  exit 0
fi

read_stdin
cmd=$(get_field '.tool_input.command') || exit 0
[ -z "$cmd" ] && exit 0

# Normalize for keyword matching. Two concerns to balance:
#
#   1. Evasion via shell quoting/escaping: `git "commit"`, `git\ push --force`
#      should still be caught. We strip backslashes from unquoted positions
#      after quote-aware stripping below.
#
#   2. False positives from quoted-string DATA: a commit message body that
#      *mentions* `--force` or `--no-verify` as prose (e.g. documenting why
#      the hook refuses them) must NOT trip the detector. v1.4.4 surfaced
#      this when a commit message containing the literal "force-push" was
#      blocked because the pre-v1.4.5 strip flattened the message into the
#      same string as a chained `git push`.
#
# Solution: strip the contents of `'...'` and `"..."` (DATA, not command
# tokens) via Python regex with DOTALL — handles multi-line bodies including
# `$(cat <<'EOF' ... EOF)` substitutions nested inside outer `"..."`. Then
# strip remaining backslash escapes (those are in unquoted positions —
# real evasion attempts like `git\ push\ --force`).
#
# Deliberate trade-off: someone who quotes a flag (`git push '--force'`)
# now slips past detection — pre-v1.4.5 the `tr` strip caught this because
# it removed only the quote characters and kept the content. We accept the
# weaker adversarial-evasion posture because (a) the hook is a safety net
# for accidents, not an adversary firewall — documented in hooks/README,
# (b) determined evasion can always shell out manually, (c) the
# false-positive rate on common prose ("don't use --force") was breaking
# legitimate commits in v1.4.4 daily use.
#
# If Python is unavailable but jq is (rare), fall back to the old
# aggressive `tr` strip — same false-positive surface as pre-v1.4.5 but
# real attacks still block.
PY_STRIP_BIN=$(command -v python3 || command -v python || true)
if [ -n "$PY_STRIP_BIN" ]; then
  cmd_norm=$(printf '%s' "$cmd" | "$PY_STRIP_BIN" -c '
import re, sys
text = sys.stdin.read()
text = re.sub(r"\x27[^\x27]*\x27", " ", text)
text = re.sub(r"\"(?:[^\"\\]|\\.)*\"", " ", text, flags=re.DOTALL)
text = text.replace("\\", "")
sys.stdout.write(text)
' 2>/dev/null) || cmd_norm=$(printf '%s' "$cmd" | tr -d "'\"\\\\")
else
  cmd_norm=$(printf '%s' "$cmd" | tr -d "'\"\\\\")
fi

# --- Force push ---
# Match --force, --force-with-lease, or any short-option cluster containing 'f'
# (catches `-f`, `-fu`, `-uf`, `-fud` - all valid getopt-style combinations).
if echo "$cmd_norm" | grep -qE 'git\s+push' && \
   echo "$cmd_norm" | grep -qE '(--force|--force-with-lease|(\s|^)-[A-Za-z]*f[A-Za-z]*(\s|$))'; then
  cat >&2 <<'EOF'
[block-dangerous-git] Force push detected.

Force push overwrites remote history and can destroy teammates' work.

Safer alternative: push to a new branch and open a PR. If you must overwrite
remote, run the command manually outside Claude Code.
EOF
  exit 2
fi

# --- No-verify commits ---
if echo "$cmd_norm" | grep -qE 'git\s+commit' && echo "$cmd_norm" | grep -qE '(--no-verify)'; then
  cat >&2 <<'EOF'
[block-dangerous-git] --no-verify detected on git commit.

Skipping pre-commit hooks bypasses safety checks (linting, secret scanning,
formatting). Fix the hook failure instead of bypassing it.

If the hook is genuinely wrong, disable it in the project's git config rather
than skipping it silently.
EOF
  exit 2
fi

# --- Hard reset to protected branch ---
if echo "$cmd_norm" | grep -qE 'git\s+reset\s+--hard\s+\S*\b(main|master|develop|trunk)\b'; then
  cat >&2 <<'EOF'
[block-dangerous-git] Hard reset to a protected branch detected.

This discards all local changes and moves HEAD to match the target branch.
Any uncommitted or unpushed work will be permanently lost.

Safer alternative: create a new branch from the target, or use git stash
before resetting.
EOF
  exit 2
fi

# --- Force branch delete (warning only, does not block) ---
if echo "$cmd_norm" | grep -qE 'git\s+branch\s+-D\s'; then
  cat >&2 <<'EOF'
[block-dangerous-git] Warning: force branch delete (git branch -D) detected.

This deletes the branch even if it has unmerged changes. Consider using
git branch -d (lowercase) which refuses to delete unmerged branches.
EOF
  # Warning only - do not block
  exit 0
fi

exit 0

# To extend, add new patterns as:
#   if echo "$cmd" | grep -qE '...'; then ...; exit 2; fi
# blocks. Test in project scope first via .claude/settings.json before
# promoting to user scope.
