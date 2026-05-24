---
description: Commit current changes safely — scans for secrets, writes a Conventional Commits message, pushes. All inline on the main session; no subagent dispatch (benchmark data showed delegation overhead exceeds Sonnet/Haiku per-token savings on commit-sized work).
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git rev-parse:*)
---

## Diff stats (computed before prompt)

Status: !`git status --short`
Branch: !`git branch --show-current`
Staged shortstat: !`git diff --cached --shortstat`
Unstaged shortstat: !`git diff --shortstat`
Staged files: !`git diff --cached --name-only`
Unstaged files: !`git diff --name-only`

## Why this is all-inline

Earlier versions of this command routed by diff size: trivial commits → `git-committer-quick` (Haiku), non-trivial → `git-committer` (Sonnet). We measured this rigorously against vanilla Claude Code on Opus 4.7 ([`bench/`](../bench/)) and found that the `Task`-tool dispatch overhead consistently exceeded the per-token savings from delegating to Sonnet/Haiku — by 50-200% depending on scope. So this command now does everything inline.

The agents are still available in [`extras/agents/`](../extras/agents/) for users who want to opt in (e.g., to draw from Haiku's separate rate pool when Opus is rate-limited), but they are no longer the default routing.

## Action

1. **Read the diff.** Run `git diff --cached`. If nothing is staged but there are unstaged changes, stage what fits a single logical commit (`git add` the files; do NOT use `git add -A` blindly — review what you're staging).
2. **Scan for problems.** Look for: leftover debug print/log statements, broken syntax, anything matching `.env` content / API keys / tokens / passwords / private keys. If found, **STOP** and report to the user. Do not commit.
3. **Check for unsafe paths.** If staged files match `auth*`, `*secret*`, `*token*`, `*key*`, `*password*`, `payment*`, `billing*`, `.env*`, `*.pem`, `*.key` — pause and ask the user to confirm before committing.
4. **Write a Conventional Commits message.** Match the repo's existing style (check `git log --oneline -10` if uncertain). Subject only for small/single-purpose commits; add a body when the *why* needs explaining and isn't obvious from the diff.
5. **Commit and push.** If branch has no upstream: `git push --set-upstream origin <branch>`.
6. **Report.** Commit hash, subject, push confirmation. Brief. Do NOT write or fix any code, even if you spot issues. Report and let the user handle it.

## Hard rules

- Refuse to commit `.env`, API keys, tokens, or anything that looks like a credential.
- Never force push.
- Never use `--no-verify` to bypass pre-commit hooks (the `block-secrets-precommit` and `block-dangerous-git` hooks enforce this independently — if you somehow get past them, you've gotten past the wrong layer).
- Never amend or rebase.
- Never write code. You commit what's staged; the human decides what to write.

## When to opt into the subagent variants

If `git-committer-quick` (Haiku) or `git-committer` (Sonnet) are installed from `extras/agents/`, the main session can invoke them explicitly (e.g., `@git-committer-quick`) when it specifically wants a different model tier for a commit (e.g., Opus is rate-limited and Haiku is still available). The benchmark data shows this is not a cost win, but the rate-pool separation can be a workflow win.
