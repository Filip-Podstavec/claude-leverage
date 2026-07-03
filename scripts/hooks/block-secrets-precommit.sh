#!/usr/bin/env bash
# block-secrets-precommit.sh
#
# Claude Code PreToolUse hook (Bash matcher).
# Scans staged diff for potential secrets before allowing git commit.
#
# Hook protocol:
#   - Receives JSON on stdin with tool_input.command
#   - Exit 0: allow the tool call
#   - Exit 2: block the tool call (stderr message shown to user)
#
# Install: register in ~/.claude/settings.json under hooks.PreToolUse
# Dependencies: jq OR python (3 or 2), plus git, grep. See json_parse.sh.

set -euo pipefail

# Source shared parser helper.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

# Without any JSON parser we cannot inspect the command. Fail-open with a
# loud warning rather than blocking every Bash call. Documented limitation.
if ! has_parser; then
  cat >&2 <<'EOF'
[block-secrets-precommit] WARNING: no JSON parser available - this hook is DISABLED.
Install one of:
  jq:     brew install jq | sudo apt install jq | winget install jqlang.jq
  python: usually preinstalled on macOS/Linux; Windows: python.org or Microsoft Store
Until then, secret scanning before commits is inactive.
EOF
  exit 0
fi

read_stdin
cmd=$(get_field '.tool_input.command') || exit 0
[ -z "$cmd" ] && exit 0

# Normalize for keyword matching only: strip shell quotes and backslashes that
# could be used to evade `git commit` detection (e.g., `git "commit"`).
cmd_norm=$(printf '%s' "$cmd" | tr -d "'\"\\\\")

# Only inspect git commit commands
case "$cmd_norm" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

# Get staged diff. Nothing staged = nothing to check.
staged_diff=$(git diff --cached 2>/dev/null) || exit 0
[ -z "$staged_diff" ] && exit 0

# Extract only added lines (skip diff metadata and context)
added_lines=$(echo "$staged_diff" | grep -E '^\+[^+]' || true)
[ -z "$added_lines" ] && exit 0

# Drop lines explicitly allowlisted with the marker comment.
# Use sparingly - this is a per-line escape hatch for legitimate matches
# (test fixtures, docs examples, mock tokens). Marker is load-bearing -
# future readers may not recognize it.
added_lines=$(echo "$added_lines" | grep -v 'claude-leverage-allow-secret' || true)
[ -z "$added_lines" ] && exit 0

# Secret patterns - name and extended regex
declare -a pattern_names=(
  "AWS Access Key"
  "GitHub Personal Access Token"
  "GitHub Fine-grained PAT"
  "GitHub OAuth Token"
  "GitHub User-to-Server Token"
  "GitHub Server-to-Server Token"
  "GitLab PAT"
  "Stripe Live Key"
  "Stripe Test Key"
  "Anthropic API Key"
  "OpenAI-style Key"
  "Google API Key"
  "Slack Token"
  "Private Key Block"
  "Generic Password Assignment"
)

declare -a patterns=(
  # AIDEV-NOTE: the trailing "Generic Password Assignment" pattern below
  # uses an exclusion character class `[^"'$\{<]` to skip placeholder
  # interpolations: `$` excludes `$VAR` references, `{` excludes `${VAR}`
  # references (the `\{` here is literal because backslash-`{` inside a
  # bracket expression in ERE is the same as bare `{`), `<` excludes
  # template-style `<placeholder>` markers. Don't "simplify" the class
  # without checking what each character is exempting.
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36}'
  'github_pat_[A-Za-z0-9_]{36,}'
  'gho_[A-Za-z0-9]{36}'
  'ghu_[A-Za-z0-9]{36}'
  'ghs_[A-Za-z0-9]{36}'
  'glpat-[A-Za-z0-9_-]{20,}'
  'sk_live_[A-Za-z0-9]{24,}'
  'sk_test_[A-Za-z0-9]{24,}'
  'sk-ant-[A-Za-z0-9_-]{90,}'
  'sk-[A-Za-z0-9]{40,}'
  'AIza[0-9A-Za-z_-]{35}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  '-----BEGIN.*PRIVATE KEY-----'
  '(password|passwd|pwd|secret|api[_-]?key|access[_-]?token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"'$\{<]{8,}["'"'"']'
)

# AIDEV-NOTE: collect EVERY offending added line across all patterns in one
# pass (was head -1 + exit on the first match), so a fixture with N secret-
# shaped lines is fixed in one round instead of whack-a-mole. Dedupe by line
# so a line matching two patterns (e.g. Stripe key inside an api_key=) reports
# once, first pattern winning.
declare -a findings=()
seen_lines=""

for i in "${!patterns[@]}"; do
  while IFS= read -r matched_line; do
    [ -z "$matched_line" ] && continue
    # -Fxq: fixed-string, whole-line, quiet - safe against glob/regex metachars
    # that a code line may contain.
    grep -Fxq -- "$matched_line" <<< "$seen_lines" && continue
    seen_lines="${seen_lines}${matched_line}"$'\n'

    # Find the file this line belongs to via single forward pass.
    # Earlier versions used `grep -B 9999 -F "$matched_line" | grep '^+++ b/' | tail -1`
    # which is O(N^2) on large staged diffs (re-buffering up to 9999 preceding
    # lines per match). The awk pass tracks the current `+++ b/` header as it
    # streams and emits it on first substring match - O(N) and identical output.
    # MATCHED is exported via env var rather than awk -v to avoid backslash
    # interpretation in the matched line.
    current_file=$(MATCHED="$matched_line" awk '
      BEGIN { m = ENVIRON["MATCHED"] }
      /^\+\+\+ b\// { f = substr($0, 7); next }
      index($0, m) { print f; exit }
    ' <<< "$staged_diff") || current_file="unknown"
    [ -z "$current_file" ] && current_file="unknown"

    # Redact sensitive portion for preview
    preview=$(echo "$matched_line" | head -c 80 | sed -E 's/[A-Za-z0-9_-]{12,}/***/g')

    findings+=("Pattern: ${pattern_names[$i]}"$'\n'"File: $current_file"$'\n'"Line preview: $preview")
  done < <(echo "$added_lines" | grep -iE -- "${patterns[$i]}" || true)
done

if [ "${#findings[@]}" -gt 0 ]; then
  {
    echo "[block-secrets-precommit] Potential secret(s) detected in staged diff."
    echo
    for finding in "${findings[@]}"; do
      echo "$finding"
      echo
    done

    # AIDEV-NOTE: a PreToolUse hook can only see the index as it was BEFORE the
    # tool call. `git add -A && git commit` in ONE command stages and commits
    # atomically, so the fresh staging (and any edit/marker just applied) is not
    # in the scanned diff - the top cause of "the marker doesn't work" reports.
    case "$cmd_norm" in
      *"git add"*)
        cat <<'HINT'
NOTE: this command also runs 'git add'. The hook scanned the index as it was
BEFORE the command ran, so staging done in this same command - and any edit or
'claude-leverage-allow-secret' marker you just added - is NOT in the scanned
diff. Run 'git add' as a SEPARATE step first, then commit, so your fix is what
gets scanned.

HINT
        ;;
    esac

    cat <<'EOF'
If a match is a false positive, you can:
- Add the marker comment 'claude-leverage-allow-secret' on the same line
- Commit manually outside Claude Code
- Adjust patterns by forking the script from the plugin source
  (scripts/hooks/block-secrets-precommit.sh in the claude-leverage repo)
  into a project-local hook and pointing settings.json at your copy
- Temporarily disable the hook in ~/.claude/settings.json
EOF
  } >&2
  exit 2
fi

exit 0
