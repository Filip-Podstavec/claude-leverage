---
description: Commit current changes safely — scans for secrets, writes a Conventional Commits message, pushes. All inline (no subagent dispatch). Refuses .env / credentials, never force-pushes, never uses --no-verify.
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

Earlier versions of this command routed by diff size: trivial commits →
`git-committer-quick` (Haiku), non-trivial → `git-committer` (Sonnet). We
measured this rigorously against vanilla Claude Code on Opus 4.7
([archive](../bench/archive-token-savings-thesis/)) and found that the
`Task`-tool dispatch overhead consistently exceeded the per-token savings
from delegating to Sonnet/Haiku — by 50–200 % depending on scope. So this
command does everything inline.

Both retired `git-committer*` agents are frozen under
`bench/archive-token-savings-thesis/agents/` for historical reference.
There is no opt-in path in v1.0.0 — if you want them back, copy them out
of the archive into your `~/.claude/agents/` and invoke explicitly
(`@git-committer-quick`).

## Action

1. **Read the diff.** Run `git diff --cached`. If nothing is staged but
   there are unstaged changes, stage what fits a single logical commit
   (`git add` the files; do NOT use `git add -A` blindly — review what
   you're staging).
2. **Scan for problems.** Look for: leftover debug print/log statements,
   broken syntax, anything matching `.env` content / API keys / tokens /
   passwords / private keys. If found, **STOP** and report to the user.
   Do not commit.
3. **Check for unsafe paths.** If staged files match `auth*`, `*secret*`,
   `*token*`, `*key*`, `*password*`, `payment*`, `billing*`, `.env*`,
   `*.pem`, `*.key` — pause and ask the user to confirm before committing.
   Consider whether `/security-review` should run first.
4. **Write a Conventional Commits message.** Match the repo's existing
   style (check `git log --oneline -10` if uncertain). Subject only for
   small/single-purpose commits; add a body when the *why* needs
   explaining and isn't obvious from the diff.
5. **Commit and push.** If branch has no upstream:
   `git push --set-upstream origin <branch>`.
6. **Report.** Commit hash, subject, push confirmation. Brief. Do NOT
   write or fix any code, even if you spot issues. Report and let the
   user handle it.

## Hard rules

- Refuse to commit `.env`, API keys, tokens, or anything that looks like
  a credential.
- Never force push.
- Never use `--no-verify` to bypass pre-commit hooks (the
  `block-secrets-precommit` and `block-dangerous-git` hooks enforce this
  independently — if you somehow get past them, you've gotten past the
  wrong layer).
- Never amend or rebase.
- Never write code. You commit what's staged; the human decides what to
  write.
