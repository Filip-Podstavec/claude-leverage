---
description: Check documentation freshness after code changes. Delegates to docs-updater subagent (Sonnet) to propose doc/changelog updates - main session applies approved fixes.
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git status:*), Bash(ls:*)
argument-hint: "[commit-range or branch] [--changelog-only]"
---

## Context

Branch: !`git branch --show-current`
Status: !`git status --short`
Last commit: !`git log -1 --oneline`
Last commit shortstat: !`git diff HEAD~1 --shortstat 2>/dev/null || echo "no previous commit"`
Branch diff vs main shortstat: !`git diff main...HEAD --shortstat 2>/dev/null || git diff origin/main...HEAD --shortstat 2>/dev/null || echo "n/a"`
CHANGELOG present: !`ls CHANGELOG.md 2>/dev/null && echo "yes" || echo "no"`

## Your role

You are orchestrating a documentation-sync workflow:

- Phase 1: a Sonnet-based subagent reads the diff and existing docs, returns prose-direction suggestions with confidence labels.
- Phase 2: you (the main session) apply approved updates using Edit/Write.

You do NOT analyze the docs yourself in the main session. The subagent does that. Your job is to delegate, summarize, get user direction, and then apply edits.

## Workflow

1. **Determine diff scope:**
   - If `$ARGUMENTS` contains a commit range or branch (e.g., `HEAD~3..HEAD` or `feature-branch`), pass that to the subagent.
   - If `$ARGUMENTS` contains `--changelog-only`, tell the subagent to skip README/inline doc analysis and focus only on CHANGELOG.
   - Otherwise let the subagent default to `git diff HEAD~1` (last commit).

2. **Invoke the `docs-updater` subagent** with the scope. Wait for its structured report.

3. **If the subagent reports "No Update Needed":** relay that to the user briefly and stop. Do not propose unsolicited improvements.

4. **If updates are needed:** present the report's "Documentation Updates Needed" and "CHANGELOG Entry" sections to the user. Each suggestion has a `confidence: high|low` field - call those out explicitly so the user knows which are obvious wins versus judgment calls.

5. **Ask for direction.** Offer these options:
   - Apply all high-confidence items, ask per low-confidence item
   - Apply all (including low-confidence)
   - Apply only specific items (user picks)
   - Skip - user will handle docs manually

   Wait for explicit confirmation. Never apply edits preemptively.

6. **Apply approved updates** using Edit (or Write for new files like an initial CHANGELOG). Read the live file first - the subagent's prose direction tells you *what and why*, you write the actual edit fresh from current state. Do not paste the subagent's "suggested entry" verbatim if the live file has shifted.

7. **After edits, ask whether to commit the doc changes** via `/commit-smart`. Do not auto-commit.

## Hard rules

- Do not analyze documentation yourself in the main session before delegating. That defeats the purpose - the subagent reads the docs in its own context.
- Do not ask the subagent to "also apply the edits" - it is read-only by design.
- Do not paste the subagent's prose suggestions verbatim into doc files. Apply them as Edits to the live file, written fresh.
- For low-confidence suggestions, surface the question to the user. Do not silently auto-apply.
- If the subagent flags a CHANGELOG format mismatch (e.g., the repo uses a custom format), match the existing style - do not "fix" it to Keep-a-Changelog without user approval.
- Never commit doc changes silently. Doc commits should be explicit and reviewed.
