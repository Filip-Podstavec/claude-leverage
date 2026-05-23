---
description: Smart commit - main session handles trivial commits directly, delegates non-trivial ones to git-committer subagent (Sonnet) to save Opus context
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git log:*)
---

## Diff stats (computed before prompt)

Status: !`git status --short`
Branch: !`git branch --show-current`
Staged shortstat: !`git diff --cached --shortstat`
Unstaged shortstat: !`git diff --shortstat`
Staged files: !`git diff --cached --name-only`
Unstaged files: !`git diff --name-only`

## Routing decision (apply to numbers above)

Two-tier routing. Match top-down:

**TRIVIAL** (commit directly from this session, Opus inline):
- 1-2 files changed, AND
- Under 80 lines total (insertions + deletions), AND
- No security-sensitive paths (anything matching `auth`, `crypto`, `secret`, `token`, `key`, `password`, `payment`, `billing`, `.env`)

**NON-TRIVIAL** (delegate to `git-committer` subagent, Sonnet):
- Anything else (3+ files, 80+ lines, or any sensitive path)

> **Note on the Haiku tier.** Earlier versions of this command had an "ultra-trivial → `git-committer-quick` (Haiku)" path. Benchmarking ([`bench/`](../bench/)) showed that the Task-tool round-trip overhead for very small commits exceeds the per-token savings of Haiku vs Opus, so the Haiku tier no longer auto-fires. The agent is still installed; invoke it manually (`@git-committer-quick`) if Opus is rate-limited or you specifically want a separate rate pool for plumbing commits.

## Action

If **TRIVIAL**:
1. Read the staged diff. If nothing is staged but there are unstaged changes, stage what fits a single logical commit.
2. Scan for credentials, leftover debug code, broken syntax. If found, STOP and report to user.
3. Write a Conventional Commits message matching the repo's existing style (check recent `git log --oneline -10` if uncertain).
4. Commit and push. If branch has no upstream, use `--set-upstream origin <branch>`.
5. Report commit hash, subject, push confirmation. Brief.
6. Do NOT write or fix any code, even if you spot issues. Report and let the user handle it.

If **NON-TRIVIAL**:
1. Invoke the `git-committer` subagent (Sonnet) with: "Stage, commit, and push the current changes. Match the repo's existing commit style."
2. Pass back the subagent's report.

## Hard rules (apply to all paths)

- Refuse to commit `.env`, API keys, tokens, or anything that looks like a credential
- Never force push
- Never use `--no-verify` to bypass pre-commit hooks
- Never amend or rebase
