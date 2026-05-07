# Hooks

## What hooks are

Hooks are shell scripts executed by Claude Code at lifecycle events - primarily `PreToolUse`, which fires before a tool call runs. A hook can inspect the pending call and block it by exiting with code 2. Unlike subagents and slash commands, hooks don't involve the LLM - they are deterministic shell logic. This is why hooks are the right primary layer for security guardrails: they work in the main session, inside subagents, and even when the LLM is told otherwise.

## Why this matters

Defense in depth has three layers, in order of reliability:

1. **Hooks** - deterministic lock, runs on every tool call from every session
2. **Slash commands** - workflow that does things the right way by default
3. **Subagent prompt rules** - last-resort guidance for the LLM

A subagent rule like "never use `--no-verify`" only applies when that subagent is active. A hook applies to every `Bash` call from any session. Use hooks for security, prompts for workflow.

## Available hooks

- `block-secrets-precommit.sh` - Scans staged diff before `git commit` for API keys, tokens, and private keys. Blocks commit if found.
- `block-dangerous-git.sh` - Blocks force push, `--no-verify` commits, and hard reset on protected branches.
- `track-delegations.sh` - PostToolUse observability hook (non-blocking). Logs subagent delegations to `~/.claude/claude-leverage-stats.jsonl` and prints a one-line stderr note like `(claude-leverage: code-reviewer -> sonnet)` after each delegation.

## Known limits (read before relying on hooks for security)

- **`jq` dependency, fail-open posture.** All hooks need `jq` to parse Claude Code's hook input JSON. If `jq` is missing, hooks print a warning to stderr and exit 0 (allow). This is intentional — blocking every Bash call when `jq` is missing would break unrelated work — but the trade-off is that until `jq` is installed, **the security guardrails are not enforced.** Install `jq` before treating hooks as a guarantee.
- **Pattern-based detection has false negatives.** Secret patterns are heuristics; custom or novel formats may slip through. Hooks are defense-in-depth, not a substitute for CI-side secret scanning (e.g., gitleaks, trufflehog).
- **False positives have a per-line escape hatch.** When a pattern matches a legitimate value (test fixture, documentation example, mock token), append the literal comment `claude-leverage-allow-secret` on the same line. The secrets hook skips lines containing that marker. Use sparingly — the marker is load-bearing, and future readers may not recognize it.

## Install

### Plugin install (automatic)

If you installed claude-leverage as a plugin (`/plugin install`), hooks are registered automatically via `hooks/hooks.json`. No manual `settings.json` editing needed. The steps below are for standalone copy-paste installs only.

### Step 1: Copy scripts

```bash
mkdir -p ~/.claude/hooks
cp hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

### Step 2: Install jq

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt install jq
```

### Step 3: Register in settings.json

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "$HOME/.claude/hooks/block-secrets-precommit.sh" },
          { "type": "command", "command": "$HOME/.claude/hooks/block-dangerous-git.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          { "type": "command", "command": "$HOME/.claude/hooks/track-delegations.sh" }
        ]
      }
    ]
  }
}
```

Restart Claude Code or run `/hooks` in an active session to pick up changes.

## Permissions as a complementary layer

`permissions.deny` in `settings.json` is a declarative complement to hooks. Hooks handle logic (regex matching, conditional checks). Permissions handle static deny lists for specific files and patterns.

```json
{
  "permissions": {
    "deny": [
      { "type": "Read", "pattern": "**/.env" },
      { "type": "Read", "pattern": "**/.env.*" },
      { "type": "Edit", "pattern": "**/.env" },
      { "type": "Edit", "pattern": "**/.env.*" },
      { "type": "Bash", "pattern": "git push --force*" },
      { "type": "Bash", "pattern": "git push -f *" }
    ]
  }
}
```

`permissions.deny` is faster than a hook (no shell startup), but less flexible. Use it for clear-cut deny patterns; use hooks for logic.

## Verify install

```bash
# Test secrets hook with fake AWS key
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > test-secret.txt
git add test-secret.txt
# Ask Claude Code to commit. Hook should block.
git rm --cached test-secret.txt && rm test-secret.txt
```

## Disabling temporarily

When a hook blocks a legitimate commit:

- **Simplest:** run the commit manually outside Claude Code
- **Temporary:** remove the hook entry from `settings.json`, restart session
- **Permanent exception:** fork the hook script and adjust patterns

## Platform notes

- **macOS, Linux, WSL2:** works out of the box
- **Native Windows (PowerShell):** hooks need rewriting to PowerShell. PRs welcome.
