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

## Install

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
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > /tmp/test-secret.txt
git add /tmp/test-secret.txt
# Ask Claude Code to commit. Hook should block.
git rm --cached /tmp/test-secret.txt && rm /tmp/test-secret.txt
```

## Disabling temporarily

When a hook blocks a legitimate commit:

- **Simplest:** run the commit manually outside Claude Code
- **Temporary:** remove the hook entry from `settings.json`, restart session
- **Permanent exception:** fork the hook script and adjust patterns

## Platform notes

- **macOS, Linux, WSL2:** works out of the box
- **Native Windows (PowerShell):** hooks need rewriting to PowerShell. PRs welcome.
