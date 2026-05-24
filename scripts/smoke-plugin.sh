#!/usr/bin/env bash
# smoke-plugin.sh — run every pre-push verification gate in one shot.
#
# Exit codes:
#   0 — all green, safe to push
#   non-zero — something's broken; the offending check has already
#              printed details to stderr.
#
# Usage:
#   bash scripts/smoke-plugin.sh
#   bash scripts/smoke-plugin.sh --quiet       # only print failures
#
# This script is intentionally NOT a hook — it's a developer tool you
# run by hand before push. CI also runs the same gates individually
# (see .github/workflows/ci.yml).

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

say() { [ "$QUIET" -eq 0 ] && printf '\n== %s ==\n' "$*"; return 0; }
say_pass() { [ "$QUIET" -eq 0 ] && printf '   ✓ %s\n' "$*"; return 0; }
say_fail() { printf '   ✗ %s\n' "$*" >&2; }

failed=0

# ----------------------------------------------------------------------
# 1. pytest
# ----------------------------------------------------------------------
say "1. pytest tests/"
if pytest tests/ -q >/tmp/smoke-pytest.log 2>&1; then
  passed=$(grep -oE '[0-9]+ passed' /tmp/smoke-pytest.log | head -1)
  say_pass "${passed:-tests passed}"
else
  say_fail "pytest failed — see /tmp/smoke-pytest.log"
  tail -20 /tmp/smoke-pytest.log >&2
  failed=$((failed + 1))
fi

# ----------------------------------------------------------------------
# 2. version sync
# ----------------------------------------------------------------------
say "2. plugin.json == marketplace.json version"
if python scripts/check_version_sync.py >/tmp/smoke-version.log 2>&1; then
  say_pass "$(tail -1 /tmp/smoke-version.log)"
else
  say_fail "version sync failed"
  cat /tmp/smoke-version.log >&2
  failed=$((failed + 1))
fi

# ----------------------------------------------------------------------
# 3. codex agents parity
# ----------------------------------------------------------------------
say "3. .codex/agents/*.toml matches agents/*.md"
if python scripts/gen-codex-agents.py --check >/tmp/smoke-codex.log 2>&1; then
  say_pass "all generated TOMLs match"
else
  say_fail "codex agents parity drifted — run: python scripts/gen-codex-agents.py"
  cat /tmp/smoke-codex.log >&2
  failed=$((failed + 1))
fi

# ----------------------------------------------------------------------
# 4. shellcheck (if available)
# ----------------------------------------------------------------------
say "4. shellcheck scripts/hooks/"
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -S warning scripts/hooks/*.sh >/tmp/smoke-shellcheck.log 2>&1; then
    say_pass "no shellcheck warnings"
  else
    say_fail "shellcheck flagged issues"
    cat /tmp/smoke-shellcheck.log >&2
    failed=$((failed + 1))
  fi
else
  say_pass "(skipped — shellcheck not installed locally; CI will run it)"
fi

# ----------------------------------------------------------------------
# 5. hooks load with sample JSON
# ----------------------------------------------------------------------
say "5. every hook returns 0 on minimal stdin"
for hook in scripts/hooks/*.sh; do
  name=$(basename "$hook")
  case "$name" in
    json_parse.sh) continue ;;  # library, not a hook
  esac
  if echo '{}' | bash "$hook" >/dev/null 2>&1; then
    say_pass "$name"
  else
    say_fail "$name returned non-zero on empty input"
    failed=$((failed + 1))
  fi
done

# ----------------------------------------------------------------------
# 6. install-codex end-to-end against scratch
# ----------------------------------------------------------------------
say "6. install-codex.sh end-to-end (scratch dirs)"
SCRATCH=$(mktemp -d)
# AIDEV-NOTE: trap also cleans up on early exit from any later step
trap 'rm -rf "$SCRATCH"' EXIT

if CODEX_HOME="$SCRATCH/codex" \
   CLAUDE_LEVERAGE_AGENTS_HOME="$SCRATCH/agents" \
   bash scripts/install-codex.sh >/tmp/smoke-install.log 2>&1; then
  # Verify expected install artifacts
  install_ok=1
  for expect in \
    "$SCRATCH/codex/hooks.json" \
    "$SCRATCH/codex/AGENTS.md" \
    "$SCRATCH/agents/skills/claude-leverage"
  do
    if [ ! -e "$expect" ]; then
      say_fail "expected install artifact missing: $expect"
      install_ok=0
      failed=$((failed + 1))
    fi
  done

  if [ "$install_ok" -eq 1 ]; then
    # Skill count
    skill_count=$(ls "$SCRATCH/agents/skills/claude-leverage/" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$skill_count" -lt 8 ]; then
      say_fail "expected >=8 skills installed; got $skill_count"
      failed=$((failed + 1))
    else
      say_pass "$skill_count skills installed"
    fi

    # Agent TOML count
    toml_count=$(ls "$SCRATCH/codex/agents/" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$toml_count" -lt 2 ]; then
      say_fail "expected >=2 agent TOMLs installed; got $toml_count"
      failed=$((failed + 1))
    else
      say_pass "$toml_count agent TOML(s) installed"
    fi

    # Placeholder must be fully resolved
    if grep -q '__CLAUDE_LEVERAGE_DIR__' "$SCRATCH/codex/hooks.json" 2>/dev/null; then
      say_fail "placeholder __CLAUDE_LEVERAGE_DIR__ remained in resolved hooks.json"
      failed=$((failed + 1))
    else
      say_pass "all placeholders resolved"
    fi

    # AGENTS.md must contain the @import line
    if grep -q "@.*$(pwd | sed 's|/|\\/|g').*/AGENTS.md" "$SCRATCH/codex/AGENTS.md" 2>/dev/null; then
      say_pass "AGENTS.md @import wired up"
    elif grep -q '@.*AGENTS.md' "$SCRATCH/codex/AGENTS.md" 2>/dev/null; then
      # Looser match — some platforms canonicalize the path differently
      say_pass "AGENTS.md @import present (path canonicalized differently than expected)"
    else
      say_fail "AGENTS.md missing @import line"
      failed=$((failed + 1))
    fi
  fi
else
  say_fail "install-codex.sh failed"
  cat /tmp/smoke-install.log >&2
  failed=$((failed + 1))
fi

# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------
if [ "$QUIET" -eq 0 ]; then printf '\n'; fi
if [ "$failed" -eq 0 ]; then
  if [ "$QUIET" -eq 0 ]; then
    printf '\033[32m✓ all smoke checks passed — safe to push\033[0m\n'
  fi
  exit 0
else
  printf '\033[31m✗ %d smoke check(s) failed — DO NOT push until fixed\033[0m\n' "$failed" >&2
  exit 1
fi
