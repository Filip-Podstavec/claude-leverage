---
name: codex-sandbox
description: |
  USE WHEN setting up Codex CLI in a project, tightening sandbox for
  prod/CI, or when user asks about Codex permissions. Interactive
  helper for per-project `.codex/config.toml`: `dev` / `prod` /
  `custom` profiles, idempotent via markers, preserves unmanaged
  config below the block. Codex-only artifact.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(ls:*)
  - Bash(test:*)
  - Bash(git rev-parse:*)
argument-hint: "[target-dir] [--profile dev|staging|prod|custom] [--noninteractive]"
---

# /codex-sandbox

## What it does

Codex CLI runs each agent inside a sandbox with a configurable
permission model (filesystem, network, dangerous commands). The
defaults are conservative; per-project overrides live in
`.codex/config.toml` at the project root.

This skill asks 3–5 questions, recommends a profile, and writes the
file. Re-running on an already-configured project detects the managed
block (marker comments) and offers update-in-place.

## What lives in `.codex/config.toml`

The skill writes only the policy-relevant sections (and leaves room
for the user to add unrelated config below):

```toml
# <!-- claude-leverage:codex-sandbox START -->
# Managed by /codex-sandbox. Edit between markers and re-run the skill
# to update; do not delete the markers.

[project_doc]
max_bytes = 32768                # explicit; matches Codex default

[sandbox]
mode = "<workspace-write | read-only | full>"

[approval]
mode = "<on-request | on-failure | never>"
# <!-- claude-leverage:codex-sandbox END -->
```

## The pre-baked profiles

| Profile | Sandbox | Approval | Use for |
|---|---|---|---|
| `dev` | `workspace-write` | `on-request` | Local development. Agent can write inside the project but asks before risky actions (network, package install, shell commands outside cwd). |
| `prod` | `read-only` | `never` | Production / CI runs. Agent can only read; any write requires running outside the sandbox. |
| `custom` | (asks) | (asks) | Anything else; skill walks you through each field. |

> Earlier drafts proposed a `staging` profile with "audit logging" — that
> claim was incorrect (Codex config has no audit-log field). For CI /
> staging behavior, use `dev` if you want approvals or `prod` if you want
> the safer read-only sandbox, and pipe Codex's own stderr to your log
> aggregator if you need an audit trail.

Field names below are what Codex currently documents. If the spec
evolves, this skill will need a refresh — `/stack-check` does not yet
verify Codex spec freshness (v1.1 candidate).

## Workflow

1. **Resolve target dir.** Default cwd. If `$ARGUMENTS` has a path,
   use that. Verify it's a git repo or ask "this isn't a git repo;
   proceed anyway?".

2. **Detect existing config.** If `.codex/config.toml` exists:
   - With managed markers: parse current sandbox + approval modes,
     show them to the user, offer to keep, update, or pick a new
     profile.
   - Without managed markers: ask "an unmanaged `.codex/config.toml`
     exists; prepend a managed block above it, replace, or skip?".

3. **Choose profile** (unless `--profile <name>`):
   ```
   Pick a profile:
     1. dev      — workspace-write, on-request approvals (recommended for local)
     2. prod     — read-only sandbox, no approvals (CI / production)
     3. custom   — answer each question individually
   ```
   Unless `--noninteractive`, wait for a choice. With
   `--noninteractive` and no `--profile`, default to `dev`.

4. **For `custom`**, walk the user through:
   - Sandbox mode: read-only / workspace-write / full + explain each.
   - Approval mode: never / on-request / on-failure + explain each.
   - `project_doc.max_bytes`: keep default 32768 or set higher
     (warns this exceeds Codex's silent-drop cap if user picks higher).
   - **TODO**: additional Codex sandbox fields like writable-roots /
     network-allowlist are not yet documented stably across Codex
     versions; this skill emits only the mode fields for now. Verify
     against the live spec before adding more.

5. **Write the managed block.**
   - If no `.codex/config.toml` exists: create file with managed
     block as the only content.
   - If file exists with managed block: replace the block in place
     via `Edit` (markers stay byte-identical).
   - If file exists without managed block: prepend managed block
     above existing content.

6. **Report.** Print the resolved config + a one-line summary.
   Suggest the user runs `codex --version` or starts a fresh Codex
   session to pick up the change.

## Hard rules

- **Never delete unmanaged config below the managed block.** The
  block contract is "I own what's between my markers; everything
  else is yours."
- **Never lower the sandbox below `read-only` without explicit
  acknowledgement.** If the user picks `full`, surface a one-line
  reminder: "full sandbox lets the agent do anything in the
  filesystem; only use for trusted scripts."
- **Never invent fields outside the spec.** If a future Codex
  version adds new fields, this skill doesn't auto-include them;
  re-run after a plugin update.
- **Refuse on non-git dirs unless explicitly allowed.** Same as
  `/init-repo` — protect against random-dir foot-guns.

## Tunables

- `--profile dev|prod|custom` — skip the picker. Default is `dev`.
- `--noninteractive` — confirm nothing, use profile (default `dev`).
- `--dry-run` — print what would be written, write nothing.

## When to run

- First time setting up Codex in a project.
- After a Codex CLI version bump that changes default sandbox
  behavior (rare, but documented in changelogs).
- When tightening a project's sandbox for production / CI runs.

## What this skill does NOT do

- **Configure `~/.codex/config.toml` (global).** Global Codex config
  is a user-level decision; this skill only writes the per-project
  `.codex/config.toml`. For global, edit by hand.
- **Touch `~/.codex/hooks.json` or `~/.codex/AGENTS.md`.** Those are
  owned by `scripts/install-codex.sh` (and its uninstall path).
- **Install Codex CLI.** Codex must already be installed
  (`npm i -g @openai/codex`); this skill just configures it.

## Notes for Claude Code users

If you invoke `/codex-sandbox` from a Claude Code session, the skill
will note up front:

> This skill writes `.codex/config.toml`, which only affects how
> Codex CLI behaves in this project. Claude Code does not read
> Codex config; your Claude Code experience is unchanged.

The skill still runs (it's a file-writer; the file just happens to
be Codex-relevant). This is useful when setting up a fresh project
in Claude Code that you also plan to work on from Codex.
