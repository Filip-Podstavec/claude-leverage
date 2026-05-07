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

Three-tier routing. Match top-down:

**ULTRA-TRIVIAL** (delegate to `git-committer-quick`, Haiku tier — cheapest):
- Exactly 1 file changed, AND
- Under 20 lines total (insertions + deletions), AND
- No security-sensitive paths (anything matching `auth`, `crypto`, `secret`, `token`, `key`, `password`, `payment`, `billing`, `.env`)
- AND `git-committer-quick` agent is installed

**TRIVIAL** (commit and push directly from this session, Opus inline):
- 1-2 files, AND
- Under 50 lines total, AND
- No security-sensitive paths
- AND did not match ULTRA-TRIVIAL above (or `git-committer-quick` is not installed)

**NON-TRIVIAL** (delegate to `git-committer` subagent, Sonnet):
- Anything else

## Action

If **ULTRA-TRIVIAL**:
1. Invoke the `git-committer-quick` subagent (Haiku) with: "Stage, commit, and push the change. Single-file trivial scope, message subject only."
2. Pass back the subagent's report.

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

## Why Haiku is the default for ultra-trivial

The whole pitch of this plugin is "use the cheapest tier that works." For a 5-line typo fix, an Opus inline commit is overkill — the message can be derived directly from the diff with no architectural reasoning. Haiku via `git-committer-quick` uses a separate rate pool (helps when Opus is rate-limited) and is dramatically cheaper.

If `git-committer-quick` is not installed, the ULTRA-TRIVIAL path falls through to TRIVIAL (Opus inline) automatically. To opt out of Haiku for a specific commit, run the commit manually outside this command.
