---
name: explain-diff
description: |
  Read `git diff HEAD` (or a passed ref range) and return a plain-English
  3–5 bullet narration: what changed, why it looks important, what should
  attract a reviewer's attention. Useful as warm-up for a PR description
  or a code review request. Read-only — never modifies code.
  Cross-tool (Claude Code and Codex).
allowed-tools:
  - Read
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git status:*)
  - Bash(git rev-parse:*)
argument-hint: "[ref-range, default HEAD] [--for pr|review|self]"
---

# /explain-diff

## What it does

Reads a git diff and produces a tight English narration of what
changed, why a reviewer should care, and where the risk concentrates.
Lives next to `/commit-smart` (mechanical Conventional Commits message)
and `/security-review` (structured security audit) — covers the
"narrative" niche neither does.

Three audience modes:

- `--for pr` (default) — output is a PR-description-shaped block:
  `## Summary`, `## Why`, `## How to verify`. Copy-pasteable into the
  PR body.
- `--for review` — emphasizes what's load-bearing and what's mechanical;
  flags non-obvious decisions that the reviewer might miss without
  the author's voice ("the new `IF EXISTS` clause on line 47 is
  load-bearing — without it the migration is non-idempotent").
- `--for self` — terse 3–5 bullet self-narration; useful before
  switching context or coming back to a branch later.

## Workflow

1. **Resolve diff range.**
   - Default: `git diff HEAD` (working tree + staged vs last commit).
   - If `$ARGUMENTS` starts with `^` or contains `..` or `...`, treat
     as a ref range and use `git diff <range>`.
   - If `--for pr` and the current branch has commits beyond `main`,
     use `git diff main...HEAD` instead (covers the whole branch).

2. **Get supporting context** (parallel-OK):
   - `git status --short` for file-state breakdown.
   - `git log --oneline -10` for repo style of commit messages.
   - `git rev-parse --abbrev-ref HEAD` for branch name.

3. **Read the diff** in full. If the diff is enormous (>50k tokens
   estimated), STOP and report: "diff is too large — narrow with
   `--paths <pattern>` or `<file>...`". Don't try to chunk and
   summarize partial diffs; the result would be incoherent.

4. **Walk the diff** and identify:
   - Files added vs modified vs deleted.
   - Hunks that look mechanical (renames, type-only changes, formatting).
   - Hunks that look load-bearing (new branches, new functions, condition
     changes, new dependencies).
   - Test changes (file paths matching `*_test.*`, `*.test.*`,
     `tests/`, etc.).
   - Doc / config-only changes.
   - Anything that touches a sensitive path (`auth*`, `crypto*`,
     `*.env*`, `routes/`, etc.) — surface as a "consider /security-review"
     reminder, not a substitute for it.

5. **Emit narration in the requested shape.**

### `--for pr` output template

```markdown
## Summary

- <one sentence per key change, ordered by importance>

## Why

<one paragraph: the motivation. If the diff doesn't make the motivation
obvious, say so explicitly — "motivation not inferable from the diff;
add to PR body".>

## How to verify

- [ ] <reviewer step 1>
- [ ] <reviewer step 2>
- <commands to run if applicable>
```

### `--for review` output template

```markdown
## What changed (load-bearing)

- `file:line` — <description of load-bearing change>
- ...

## What changed (mechanical, low-risk)

- <bulk list, less detail>

## What to look at first

<top 1–2 things the reviewer should NOT skip>

## What's untested

- <files modified without corresponding test changes, IF the language
  conventionally tests, IF the file is non-trivial>
```

### `--for self` output template

```
- <bullet 1, ≤80 chars>
- <bullet 2>
- <bullet 3>
[max 5]
```

## Hard rules

- **Read-only.** No Edit/Write in the tool list. If the user asks
  "while you're at it, fix X" — STOP and surface that as a separate
  request.
- **Never invent intent.** If the diff doesn't make motivation
  obvious, explicitly say "motivation not inferable from diff" rather
  than guess.
- **Never expand scope to security audit.** If sensitive paths show
  up, ONE LINE: "diff touches `routes/auth/...` — consider
  `/security-review`". Don't try to be that skill.
- **Always cite file:line** for load-bearing claims.
- **Skip noise.** Don't list every renamed file individually if there
  are 30 of them; aggregate ("renamed 30 files from `services/old/*`
  to `services/new/*`").

## When to run

- Before opening a PR — paste the `--for pr` output into the PR body.
- After receiving a code review request from a teammate, run
  `--for review` to make sure the diff is honestly readable.
- Coming back to a branch after a few days — `--for self` to
  re-orient.

## What this skill does NOT do

- **Generate the commit message.** That's `/commit-smart`. They're
  different shapes: a commit message is per-commit; a PR description
  is per-branch. Don't conflate.
- **Audit for security/correctness.** Cite when sensitive paths
  appear; let `/security-review` do the actual audit.
- **Run tests or verify claims.** "How to verify" is suggestions for
  the reviewer; this skill doesn't execute anything.
- **Compare against `main` automatically in --for self / --for review
  modes.** Default is `HEAD` (working tree vs last commit). User
  picks the range explicitly when they want branch-wide.
