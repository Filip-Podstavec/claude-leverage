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

**TRIVIAL** (commit and push directly from this session, do NOT delegate):
- Total changed lines (insertions + deletions) under 50, AND
- Affected files: 1 or 2, AND
- No security-sensitive paths (anything matching `auth`, `crypto`, `secret`, `token`, `key`, `password`, `payment`, `billing`, `.env`)

**NON-TRIVIAL** (delegate to the `git-committer` subagent):
- Anything not matching all three TRIVIAL conditions

## Action

If TRIVIAL:
1. Read the staged diff. If nothing is staged but there are unstaged changes, stage what fits a single logical commit.
2. Scan for credentials, leftover debug code, broken syntax. If found, STOP and report to user.
3. Write a Conventional Commits message matching the repo's existing style (check recent `git log --oneline -10` if uncertain).
4. Commit and push. If branch has no upstream, use `--set-upstream origin <branch>`.
5. Report commit hash, subject, push confirmation. Brief.
6. Do NOT write or fix any code, even if you spot issues. Report and let the user handle it.

If NON-TRIVIAL:
1. Invoke the `git-committer` subagent with: "Stage, commit, and push the current changes. Match the repo's existing commit style."
2. Pass back the subagent's report.

## Hard rules (apply to both paths)

- Refuse to commit `.env`, API keys, tokens, or anything that looks like a credential
- Never force push
- Never use `--no-verify` to bypass pre-commit hooks
- Never amend or rebase

## Optional: Haiku tier for trivial commits

If the commit qualifies as TRIVIAL by current criteria AND is a single-file change under 20 lines AND the user has installed `git-committer-quick`, you can optionally delegate to that subagent instead of committing in the main session. This is opt-in - default behavior is to commit in the main session for trivial scope.

Trade-off: Haiku adds delegation overhead for tiny commits but uses a separate rate pool, which can matter on busy Opus sessions. Use the Haiku path when:
- The user explicitly requested it
- The main session's Opus pool is rate-limited

Otherwise, the default (commit in main session) is faster and simpler.
